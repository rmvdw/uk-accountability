"""Refresh behaviour from docs/refresh-policy.md, using a fake adapter (no network)."""

import json
from datetime import UTC, datetime

from ukdash.project import Project
from ukdash.refresh import refresh
from ukdash.schema import Observation
from ukdash.sources import Adapter, Fetched
from ukdash.sources.base import geo_lookup

T1 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
T2 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)


class FakeAdapter(Adapter):
    name = "fake"

    def __init__(self, payload: str = "GBR,2025-07,4.0\nJPN,2025-07,2.6\n", fail: bool = False):
        self.payload, self.fail = payload, fail

    def fetch(self, d):
        if self.fail:
            raise ConnectionError("source unreachable")
        return Fetched(raw=self.payload.encode(), filename="response.csv", request="fake://test")

    def parse(self, d, raw, geographies):
        to_id = geo_lookup(geographies, "iso3")
        out = []
        for line in raw.decode().strip().splitlines():
            code, period, value = line.split(",")
            out.append(
                Observation(
                    indicator_id=d.id,
                    geography_id=to_id[code],
                    period=period,
                    frequency="M",
                    value=float(value),
                )
            )
        return out


def checks(root):
    return json.loads((root / "data/checks.json").read_text())["test_unemployment"]


def test_successful_refresh_promotes_and_records_check(fixture_root):
    r = refresh(fixture_root, adapters={"fake": FakeAdapter()}, now=T1)
    assert r.ok and r.results == {"test_unemployment": "ok"}
    rows = Project.load(fixture_root).read_observations("test_unemployment")
    assert {o.period for o in rows} == {"2025-07"}
    c = checks(fixture_root)
    assert c["last_successful_check_at"].startswith("2026-01-01")
    assert c["last_attempt_result"] == "ok"


def test_unchanged_refresh_still_records_check(fixture_root):
    refresh(fixture_root, adapters={"fake": FakeAdapter()}, now=T1)
    r = refresh(fixture_root, adapters={"fake": FakeAdapter()}, now=T2)
    assert r.ok and r.results == {"test_unemployment": "unchanged"}
    c = checks(fixture_root)
    assert c["last_successful_check_at"].startswith("2026-02-01")
    assert c["last_attempt_result"] == "unchanged"


def test_failed_fetch_preserves_published_data(fixture_root):
    refresh(fixture_root, adapters={"fake": FakeAdapter()}, now=T1)
    before = (fixture_root / "data/observations/test_unemployment.csv").read_bytes()

    r = refresh(fixture_root, adapters={"fake": FakeAdapter(fail=True)}, now=T2)
    assert not r.ok
    assert (fixture_root / "data/observations/test_unemployment.csv").read_bytes() == before
    c = checks(fixture_root)
    assert c["last_attempt_result"] == "failed"
    assert c["last_attempt_at"].startswith("2026-02-01")
    assert c["last_successful_check_at"].startswith("2026-01-01")  # not advanced
    assert "source unreachable" in c["last_error"]


def test_invalid_candidate_is_not_promoted(fixture_root):
    before = (fixture_root / "data/observations/test_unemployment.csv").read_bytes()
    dup = "GBR,2025-07,4.0\nGBR,2025-07,4.1\n"  # duplicate key
    r = refresh(fixture_root, adapters={"fake": FakeAdapter(payload=dup)}, now=T1)
    assert not r.ok
    assert (fixture_root / "data/observations/test_unemployment.csv").read_bytes() == before
    assert checks(fixture_root)["last_successful_check_at"] is None


def set_status(root, status):
    p = root / "indicators/test_unemployment.yml"
    p.write_text(p.read_text().replace("status: published", f"status: {status}"))


def test_scheduled_refresh_skips_drafts(fixture_root):
    set_status(fixture_root, "draft")
    r = refresh(fixture_root, adapters={"fake": FakeAdapter()}, now=T1)
    assert r.ok and r.results == {}


def test_named_refresh_seeds_a_draft(fixture_root):
    set_status(fixture_root, "draft")
    r = refresh(fixture_root, adapters={"fake": FakeAdapter()}, now=T1, only=["test_unemployment"])
    assert r.ok and r.results == {"test_unemployment": "ok"}
    rows = Project.load(fixture_root).read_observations("test_unemployment")
    assert {o.period for o in rows} == {"2025-07"}


def test_build_exception_records_failure_and_keeps_release(fixture_root, monkeypatch):
    import ukdash.refresh as mod

    refresh(fixture_root, adapters={"fake": FakeAdapter()}, now=T1)
    before = (fixture_root / "data/observations/test_unemployment.csv").read_bytes()

    def boom(*a, **k):
        raise ValueError("template exploded")

    monkeypatch.setattr(mod, "build", boom)
    r = refresh(fixture_root, adapters={"fake": FakeAdapter(payload="GBR,2025-08,3.9\n")}, now=T2)
    assert not r.ok
    assert any("template exploded" in e for e in r.errors)
    assert (fixture_root / "data/observations/test_unemployment.csv").read_bytes() == before
    c = checks(fixture_root)
    assert c["last_attempt_result"] == "failed"
    assert c["last_attempt_at"].startswith("2026-02-01")
    assert c["last_successful_check_at"].startswith("2026-01-01")
    assert "template exploded" in c["last_error"]


def test_manual_import_records_provenance_not_a_check(fixture_root, tmp_path):
    from ukdash.refresh import import_manual

    set_status(fixture_root, "draft")
    f = tmp_path / "official-download.csv"
    f.write_bytes(b"GBR,2025-07,4.0\r\nJPN,2025-07,2.6\r\n")  # CRLF bytes kept exactly
    r = import_manual(
        "test_unemployment",
        f,
        "https://example.invalid/official",
        root=fixture_root,
        adapters={"fake": FakeAdapter()},
        now=T1,
    )
    assert r.ok
    entry = next(
        e
        for e in Project.load(fixture_root).read_manifest()
        if e.path.endswith("official-download.csv")
    )
    assert entry.retrieval_method == "manual"
    assert (fixture_root / entry.path).read_bytes() == f.read_bytes()
    assert not (fixture_root / "data/checks.json").exists()


def _published_state(root):
    data = root / "data"
    return {
        p.relative_to(data).as_posix(): p.read_bytes()
        for p in sorted(data.rglob("*"))
        if p.is_file() and p.name != "checks.json"
    }


def test_copy_failure_during_promotion_leaves_data_untouched(fixture_root, monkeypatch):
    import ukdash.refresh as mod

    before = _published_state(fixture_root)
    real_copytree = mod.shutil.copytree

    def failing_copytree(src, dst, *a, **k):
        if mod.WORKDIR in str(dst):
            raise OSError("disk full")
        return real_copytree(src, dst, *a, **k)

    monkeypatch.setattr(mod.shutil, "copytree", failing_copytree)
    r = refresh(fixture_root, adapters={"fake": FakeAdapter()}, now=T1)
    assert not r.ok and r.data_intact
    assert any("disk full" in e for e in r.errors)
    assert _published_state(fixture_root) == before
    assert not (fixture_root / mod.WORKDIR).exists()


def test_swap_failure_part_way_is_rolled_back(fixture_root, monkeypatch):
    import ukdash.refresh as mod

    before = _published_state(fixture_root)
    real_replace = mod._replace
    calls = {"n": 0}

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 4:  # after raw is swapped in, while swapping observations
            raise OSError("file locked")
        return real_replace(src, dst)

    monkeypatch.setattr(mod, "_replace", flaky_replace)
    r = refresh(fixture_root, adapters={"fake": FakeAdapter()}, now=T1)
    assert not r.ok and r.data_intact
    assert any("rolled back" in e and "file locked" in e for e in r.errors)
    assert _published_state(fixture_root) == before
    assert checks(fixture_root)["last_successful_check_at"] is None


def test_interrupted_promotion_blocks_the_next_one(fixture_root):
    import ukdash.refresh as mod

    (fixture_root / mod.WORKDIR / "old").mkdir(parents=True)
    before = _published_state(fixture_root)
    r = refresh(fixture_root, adapters={"fake": FakeAdapter()}, now=T1)
    assert not r.ok
    assert any("interrupted" in e for e in r.errors)
    assert _published_state(fixture_root) == before
    assert (fixture_root / mod.WORKDIR / "old").exists()  # never deleted automatically
