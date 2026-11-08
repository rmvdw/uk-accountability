"""Saved raw responses must round-trip through Git byte for byte, CRLF included."""

import shutil
import subprocess

import pytest

from ukdash.project import REPO_ROOT

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "core.autocrlf=true", *args], cwd=cwd, check=True, capture_output=True
    ).stdout


def test_crlf_raw_snapshot_round_trips(tmp_path):
    shutil.copy(REPO_ROOT / ".gitattributes", tmp_path / ".gitattributes")
    raw = b"REF_AREA,TIME_PERIOD,OBS_VALUE\r\nGBR,2025-07,4.0\r\n"
    for rel in ("data/raw/x/response.csv", "tests/fixtures/data/raw/x/response.csv"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)

    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "t")

    for rel in ("data/raw/x/response.csv", "tests/fixtures/data/raw/x/response.csv"):
        assert git(tmp_path, "show", f"HEAD:{rel}") == raw  # stored unchanged
        (tmp_path / rel).unlink()
        git(tmp_path, "checkout", "--", rel)
        assert (tmp_path / rel).read_bytes() == raw  # checked out unchanged

    attrs = git(tmp_path, "check-attr", "text", "--", "data/raw/x/response.csv").decode()
    assert attrs.strip().endswith("text: unset")
