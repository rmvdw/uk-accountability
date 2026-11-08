"""Live refresh: fetch → parse → validate → build in staging → promote only if all pass.

See docs/refresh-policy.md. This is the only module that contacts statistical sources.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .build import build
from .project import REPO_ROOT, Project, write_observations
from .schema import CheckRecord, ManifestEntry
from .sources import ADAPTERS, Adapter


@dataclass
class RefreshResult:
    ok: bool
    results: dict[str, str] = field(default_factory=dict)  # indicator_id -> ok|unchanged|failed
    errors: list[str] = field(default_factory=list)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


def refresh(
    root: Path = REPO_ROOT,
    adapters: dict[str, Adapter] | None = None,
    now: datetime | None = None,
) -> RefreshResult:
    adapters = ADAPTERS if adapters is None else adapters
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    project = Project.load(root)
    checks = project.read_checks()
    manifest = {e.path: e for e in project.read_manifest()}
    result = RefreshResult(ok=True)

    with tempfile.TemporaryDirectory(prefix="ukdash-refresh-") as tmp:
        stage = Path(tmp)
        shutil.copytree(root / "data", stage / "data")
        shutil.copytree(root / "indicators", stage / "indicators")

        for d in project.published():
            try:
                adapter = adapters[d.source.adapter]
                fetched = adapter.fetch(d)
                rows = adapter.parse(d, fetched.raw, project.geographies)
                if not rows:
                    raise ValueError("source returned no observations")
            except Exception as exc:  # noqa: BLE001 - any failure blocks promotion
                result.ok = False
                result.results[d.id] = "failed"
                result.errors.append(f"{d.id}: {type(exc).__name__}: {exc}")
                continue

            rel = f"data/raw/{d.id}/{fetched.filename}"
            digest = hashlib.sha256(fetched.raw).hexdigest()
            previous = manifest.get(rel)
            unchanged = previous is not None and previous.sha256 == digest
            result.results[d.id] = "unchanged" if unchanged else "ok"
            if not unchanged:
                raw_path = stage / rel
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(fetched.raw)
                manifest[rel] = ManifestEntry(
                    indicator_id=d.id,
                    path=rel,
                    sha256=digest,
                    request=fetched.request,
                    retrieval_method="live",
                    retrieved_at=now,
                    publisher_release_date=fetched.publisher_release_date,
                    licence=d.source.licence,
                )
            write_observations(stage / "data" / "observations" / f"{d.id}.csv", rows)

        if result.ok:
            _write_json(
                stage / "data" / "manifest.json",
                [
                    e.model_dump(mode="json")
                    for e in sorted(manifest.values(), key=lambda e: e.path)
                ],
            )
            staged = Project.load(stage, config_root=root)
            errors = build(staged, stage / "site")
            if errors:
                result.ok = False
                result.errors.extend(f"validation: {e}" for e in errors)

        if result.ok:
            # Promote the whole candidate release.
            for sub in ("raw", "observations"):
                shutil.rmtree(root / "data" / sub, ignore_errors=True)
                shutil.copytree(stage / "data" / sub, root / "data" / sub)
            shutil.copy(stage / "data" / "manifest.json", root / "data" / "manifest.json")

    # Check records: always record the attempt; only a fully successful release
    # advances last_successful_check_at.
    for d in project.published():
        prev = checks.get(d.id, CheckRecord())
        outcome = result.results.get(d.id, "failed")
        if result.ok:
            checks[d.id] = CheckRecord(
                last_attempt_at=now,
                last_attempt_result=outcome,
                last_successful_check_at=now,
            )
        else:
            err = next((e for e in result.errors if e.startswith(f"{d.id}:")), None)
            checks[d.id] = CheckRecord(
                last_attempt_at=now,
                last_attempt_result="failed",
                last_successful_check_at=prev.last_successful_check_at,
                last_error=err or "release blocked by another failure",
            )
    _write_json(
        root / "data" / "checks.json",
        {k: v.model_dump(mode="json") for k, v in sorted(checks.items())},
    )
    return result
