"""Exercise real adapters and publication safety in a disposable project.

No push, deploy hook, issue write or heartbeat. The real repository is read-only.
The recapture uses identical publisher bytes under new filenames to exercise the
changed-release path; numerical changes are covered by test_refresh.py fixtures.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ukdash.briefing import load_all
from ukdash.build import build
from ukdash.project import REPO_ROOT, Project
from ukdash.refresh import refresh
from ukdash.sources import ADAPTERS, Adapter, Fetched


def release_bytes(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / "data").rglob("*")
        if p.is_file() and p.name != "checks.json"
    }


class Saved(Adapter):
    def __init__(self, project, prefix="", fail=False):
        self.project, self.prefix, self.fail = project, prefix, fail

    def fetch(self, d):
        if self.fail:
            raise ConnectionError("deliberate rehearsal failure; no production publication")
        entry = max(
            (e for e in self.project.read_manifest() if e.indicator_id == d.id),
            key=lambda e: e.retrieved_at,
        )
        return Fetched(
            raw=(self.project.root / entry.path).read_bytes(),
            filename=self.prefix + Path(entry.path).name,
            request=entry.request,
            publisher_release_date=entry.publisher_release_date,
            vintage=entry.vintage,
        )

    def parse(self, d, raw, geographies):
        return ADAPTERS[d.source.adapter].parse(d, raw, geographies)


def main():
    original = release_bytes(REPO_ROOT)
    original_checks = (REPO_ROOT / "data/checks.json").read_bytes()
    now = datetime.now(UTC).replace(microsecond=0)
    with tempfile.TemporaryDirectory(prefix="ukdash-rehearsal-") as tmp:
        root = Path(tmp)
        for folder in ("data", "indicators", "config", "briefings"):
            source = REPO_ROOT / folder
            if source.exists():
                shutil.copytree(source, root / folder)
        project = Project.load(root)
        ids = sorted(project.indicators)
        result = refresh(root, only=ids, now=now)
        if not result.ok:
            raise RuntimeError(f"live rehearsal failed: {result.errors}")
        print("LIVE", json.dumps(result.results, sort_keys=True))

        # Recapture genuine source bytes under new paths; no invented observations.
        project = Project.load(root)
        adapters = {key: Saved(project, prefix="rehearsal-") for key in ADAPTERS}
        changed = refresh(root, adapters=adapters, only=ids, now=now + timedelta(seconds=1))
        assert changed.ok and set(changed.results.values()) == {"ok"}
        project = Project.load(root)
        adapters = {key: Saved(project) for key in ADAPTERS}
        unchanged = refresh(root, adapters=adapters, only=ids, now=now + timedelta(seconds=2))
        assert unchanged.ok and set(unchanged.results.values()) == {"unchanged"}
        before = release_bytes(root)
        previous_checks = Project.load(root).read_checks()

        broken = {key: Saved(project, fail=True) for key in ADAPTERS}
        failed = refresh(root, adapters=broken, only=ids, now=now + timedelta(seconds=3))
        assert not failed.ok and failed.data_intact and release_bytes(root) == before
        for key, record in Project.load(root).read_checks().items():
            assert record.last_successful_check_at == previous_checks[key].last_successful_check_at
            assert record.last_attempt_result == "failed"
        recovered = refresh(root, adapters=adapters, only=ids, now=now + timedelta(seconds=4))
        assert recovered.ok and release_bytes(root) == before
        assert not build(Project.load(root), root / "site")
        assert not build(Project.load(root), root / "preview", include_drafts=True)
        info = json.loads((root / "site/build-info.json").read_text(encoding="utf-8"))
        assert info["preview_with_drafts"] is False
        assert info["indicators"] == [d.id for d in Project.load(root).published()]
        for briefing in load_all(root).values():
            if all(Project.load(root).read_observations(i) for i in briefing.indicators):
                assert (root / "preview/briefings" / briefing.id / "index.html").exists()
        page = (root / "site/unemployment_rate/index.html").read_text(encoding="utf-8")
        assert "data-checked=" in page and "data-cadence=" in page
        assert "Date.now()" in page and "Check overdue" in page
        print("PASS: recapture, unchanged, failure preservation, recovery and both builds")
        print("PASS: freshness timestamp/cadence and browser-time overdue hook rendered")
        print("PASS: briefing candidates rendered against refreshed data")
    assert release_bytes(REPO_ROOT) == original
    assert (REPO_ROOT / "data/checks.json").read_bytes() == original_checks
    print("PASS: repository data untouched; no deployment, issue or monitor calls")


if __name__ == "__main__":
    main()
