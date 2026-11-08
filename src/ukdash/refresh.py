"""Getting data in: live refresh and documented manual import.

Both routes stage the candidate release, validate it, build the site from it,
and promote it into data/ only if every step passes. See docs/refresh-policy.md.
This is the only module that contacts statistical sources.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .build import build
from .project import REPO_ROOT, Project, write_observations
from .schema import CheckRecord, IndicatorDefinition, ManifestEntry, Observation
from .sources import ADAPTERS, Adapter, Fetched


@dataclass
class RefreshResult:
    ok: bool
    results: dict[str, str] = field(default_factory=dict)  # indicator_id -> ok|unchanged|failed
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Candidate:
    d: IndicatorDefinition
    fetched: Fetched
    rows: list[Observation]


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", newline="\n")


def _fail(result: RefreshResult, where: str, exc: BaseException) -> None:
    result.ok = False
    result.errors.append(f"{where}: {type(exc).__name__}: {exc}")


def _targets(project: Project, only: list[str] | None) -> list[IndicatorDefinition]:
    """Scheduled refreshes cover published indicators. Naming indicators (drafts
    included) is how a new indicator gets its first data before Ross publishes it."""
    if not only:
        return project.published()
    missing = [i for i in only if i not in project.indicators]
    if missing:
        raise KeyError(f"unknown indicator(s): {', '.join(missing)}")
    return [project.indicators[i] for i in only]


def _release(
    root: Path,
    project: Project,
    candidates: list[_Candidate],
    method: Literal["live", "manual"],
    now: datetime,
    result: RefreshResult,
) -> None:
    """Stage, validate, build and (only if all pass) promote. Never raises."""
    try:
        manifest = {e.path: e for e in project.read_manifest()}
        with tempfile.TemporaryDirectory(prefix="ukdash-release-") as tmp:
            stage = Path(tmp)
            shutil.copytree(root / "data", stage / "data")
            shutil.copytree(root / "indicators", stage / "indicators")

            for c in candidates:
                rel = f"data/raw/{c.d.id}/{c.fetched.filename}"
                digest = hashlib.sha256(c.fetched.raw).hexdigest()
                previous = manifest.get(rel)
                unchanged = previous is not None and previous.sha256 == digest
                result.results[c.d.id] = "unchanged" if unchanged else "ok"
                if not unchanged:
                    raw_path = stage / rel
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_path.write_bytes(c.fetched.raw)
                    manifest[rel] = ManifestEntry(
                        indicator_id=c.d.id,
                        path=rel,
                        sha256=digest,
                        request=c.fetched.request,
                        retrieval_method=method,
                        retrieved_at=now,
                        publisher_release_date=c.fetched.publisher_release_date,
                        licence=c.d.source.licence,
                    )
                write_observations(stage / "data" / "observations" / f"{c.d.id}.csv", c.rows)

            _write_json(
                stage / "data" / "manifest.json",
                [
                    e.model_dump(mode="json")
                    for e in sorted(manifest.values(), key=lambda e: e.path)
                ],
            )
            staged = Project.load(stage, config_root=project.config_root or root)
            errors = build(staged, stage / "site")
            if errors:
                result.ok = False
                result.errors.extend(f"validation: {e}" for e in errors)
                return

            # Promote the whole candidate release.
            for sub in ("raw", "observations"):
                shutil.rmtree(root / "data" / sub, ignore_errors=True)
                shutil.copytree(stage / "data" / sub, root / "data" / sub)
            shutil.copy(stage / "data" / "manifest.json", root / "data" / "manifest.json")
    except Exception as exc:  # noqa: BLE001 - any failure blocks promotion and is recorded
        _fail(result, "release", exc)


def refresh(
    root: Path = REPO_ROOT,
    adapters: dict[str, Adapter] | None = None,
    now: datetime | None = None,
    only: list[str] | None = None,
) -> RefreshResult:
    adapters = ADAPTERS if adapters is None else adapters
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    project = Project.load(root)
    targets = _targets(project, only)
    result = RefreshResult(ok=True)

    candidates: list[_Candidate] = []
    for d in targets:
        try:
            adapter = adapters[d.source.adapter]
            fetched = adapter.fetch(d)
            rows = adapter.parse(d, fetched.raw, project.geographies)
            if not rows:
                raise ValueError("source returned no observations")
            candidates.append(_Candidate(d, fetched, rows))
        except Exception as exc:  # noqa: BLE001 - any failure blocks promotion
            result.results[d.id] = "failed"
            _fail(result, d.id, exc)

    if result.ok:
        _release(root, project, candidates, "live", now, result)

    # Always record the attempt; only a fully promoted release advances
    # last_successful_check_at.
    checks = project.read_checks()
    for d in targets:
        prev = checks.get(d.id, CheckRecord())
        if result.ok:
            checks[d.id] = CheckRecord(
                last_attempt_at=now,
                last_attempt_result=result.results.get(d.id, "ok"),
                last_successful_check_at=now,
            )
        else:
            err = next((e for e in result.errors if e.startswith(f"{d.id}:")), None)
            checks[d.id] = CheckRecord(
                last_attempt_at=now,
                last_attempt_result="failed",
                last_successful_check_at=prev.last_successful_check_at,
                last_error=err or "; ".join(result.errors) or "release failed",
            )
    _write_json(
        root / "data" / "checks.json",
        {k: v.model_dump(mode="json") for k, v in sorted(checks.items())},
    )
    return result


def import_manual(
    indicator_id: str,
    file: Path,
    request: str,
    root: Path = REPO_ROOT,
    adapters: dict[str, Adapter] | None = None,
    now: datetime | None = None,
    publisher_release_date: str | None = None,
) -> RefreshResult:
    """Seed an indicator from an official file downloaded by hand.

    The file is parsed by the indicator's normal adapter and recorded with
    retrieval_method "manual". It does not count as a live check, so
    data/checks.json is not touched.
    """
    adapters = ADAPTERS if adapters is None else adapters
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    project = Project.load(root)
    result = RefreshResult(ok=True)
    try:
        (d,) = _targets(project, [indicator_id])
        raw = Path(file).read_bytes()
        rows = adapters[d.source.adapter].parse(d, raw, project.geographies)
        if not rows:
            raise ValueError("file contained no observations")
        fetched = Fetched(
            raw=raw,
            filename=Path(file).name,
            request=request,
            publisher_release_date=publisher_release_date,
        )
    except Exception as exc:  # noqa: BLE001
        result.results[indicator_id] = "failed"
        _fail(result, indicator_id, exc)
        return result
    _release(root, project, [_Candidate(d, fetched, rows)], "manual", now, result)
    return result
