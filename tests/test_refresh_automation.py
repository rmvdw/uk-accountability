"""Protect Actions boundaries: data-only commits, failure reporting and secret handling."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "refresh_automation", ROOT / ".github/scripts/refresh_automation.py"
)
automation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(automation)


class FakeGitHub:
    def __init__(self):
        self.issue = None
        self.writes = []

    def request(self, method, path, payload=None):
        if method == "GET":
            return [dict(self.issue)] if self.issue else []
        self.writes.append((method, path, payload))
        if method == "POST" and path == "issues":
            self.issue = {"number": 45, "state": "open", **payload}
        elif method == "PATCH":
            self.issue.update(payload)
        return self.issue


def test_issue_failure_repeat_change_recovery_and_recurrence():
    api = FakeGitHub()
    run = "https://github.com/example/repo/actions/runs/1"
    check = {"jobs": {"last_attempt_result": "failed", "last_error": "timeout"}}
    automation.sync_issue(api, False, "REFRESH", run, check)
    assert len(api.writes) == 1 and api.issue["state"] == "open"
    automation.sync_issue(api, False, "REFRESH", run + "2", check)
    assert len(api.writes) == 1  # same failure does not spam the issue
    automation.sync_issue(api, False, "VERIFY", run, check)
    assert api.writes[-1][0:2] == ("PATCH", "issues/45")
    automation.sync_issue(api, True, "", run, {})
    assert api.issue["state"] == "closed"
    assert api.writes[-2][1] == "issues/45/comments"
    automation.sync_issue(api, False, "REFRESH", run, check)
    assert api.issue["state"] == "open"
    assert sum(path == "issues" for _, path, _ in api.writes) == 1


def test_no_recovery_issue_when_nothing_has_failed():
    api = FakeGitHub()
    automation.sync_issue(api, True, "", "run", {})
    assert not api.writes


@pytest.fixture
def git_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for path in automation.DATA_PATHS[:2]:
        (root / path).mkdir(parents=True)
    for name in ["data/raw/snapshot.csv", "data/observations/metric.csv"]:
        (root / name).write_text("original\n", encoding="utf-8")
    (root / "data/manifest.json").write_text("[]\n", encoding="utf-8")
    (root / "data/checks.json").write_text(
        json.dumps(
            {
                "metric": {
                    "last_successful_check_at": "2026-01-01T00:00:00Z",
                    "last_attempt_result": "ok",
                }
            }
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text("keep\n", encoding="utf-8")
    for args in [
        ["init"],
        ["add", "."],
        ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "baseline"],
    ]:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    return root


def change_checks(root, successful=False):
    path = root / "data/checks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["metric"]["last_attempt_at"] = "2026-02-01T00:00:00Z"
    data["metric"]["last_attempt_result"] = "ok" if successful else "failed"
    if successful:
        data["metric"]["last_successful_check_at"] = "2026-02-01T00:00:00Z"
    path.write_text(json.dumps(data), encoding="utf-8")


def test_failed_attempt_commit_cannot_include_candidate_data(git_root):
    change_checks(git_root)
    (git_root / "data/observations/metric.csv").write_text("bad candidate\n", encoding="utf-8")
    (git_root / "data/raw/snapshot.csv").write_text("bad raw\n", encoding="utf-8")
    automation.commit_data(git_root, failed=True)
    assert (git_root / "data/observations/metric.csv").read_text(encoding="utf-8") == "original\n"
    assert (git_root / "data/raw/snapshot.csv").read_text(encoding="utf-8") == "original\n"
    paths = automation.git("diff", "HEAD~", "HEAD", "--name-only", root=git_root)
    assert paths == "data/checks.json"


def test_failed_attempt_rejects_advanced_success_clock(git_root):
    change_checks(git_root, successful=True)
    with pytest.raises(RuntimeError, match="advanced"):
        automation.commit_data(git_root, failed=True)


def test_successful_data_commit_and_unchanged_source_metadata(git_root):
    first = automation.git("rev-parse", "HEAD", root=git_root)
    change_checks(git_root, successful=True)
    second = automation.commit_data(git_root)
    assert second != first
    assert automation.git("show", "HEAD:data/observations/metric.csv", root=git_root) == "original"
    assert automation.commit_data(git_root) == second  # no empty commit


def test_unexpected_code_change_is_not_committed(git_root):
    change_checks(git_root)
    (git_root / "README.md").write_text("unexpected\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="outside"):
        automation.commit_data(git_root)
    assert not automation.git("diff", "--cached", "--name-only", root=git_root)


@pytest.mark.parametrize(
    "value",
    ["", "http://hc-ping.com/abc", "https://evil.test/abc", "https://hc-ping.com/abc?create=1"],
)
def test_monitor_preflight_rejects_missing_or_wrong_provider(monkeypatch, value):
    monkeypatch.setenv("HEALTHCHECKS_PING_URL", value)
    with pytest.raises(ValueError):
        automation.secret_url("HEALTHCHECKS_PING_URL")


def test_valid_urls(monkeypatch):
    for name, value in {
        "HEALTHCHECKS_PING_URL": "https://hc-ping.com/12345678-1234-1234-1234-123456789abc",
        "CLOUDFLARE_DEPLOY_HOOK": "https://api.cloudflare.com/client/v4/pages/webhooks/deploy_hooks/example-id",
    }.items():
        monkeypatch.setenv(name, value)
        assert automation.secret_url(name) == value


def test_hook_errors_do_not_disclose_secret_urls(monkeypatch, capsys):
    secret = "https://hc-ping.com/12345678-1234-1234-1234-123456789abc"

    def fail(_):
        raise RuntimeError(secret)

    monkeypatch.setattr(automation, "post_hook", fail)
    monkeypatch.setattr("sys.argv", ["refresh_automation.py", "heartbeat"])
    with pytest.raises(SystemExit) as error:
        automation.main()
    assert secret not in str(error.value)
    assert secret not in capsys.readouterr().out


def test_healthcheck_unknown_uuid_does_not_count_as_success(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b"OK (not found)"

    class Opener:
        def open(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setenv(
        "HEALTHCHECKS_PING_URL", "https://hc-ping.com/12345678-1234-1234-1234-123456789abc"
    )
    monkeypatch.setattr(automation.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises(RuntimeError, match="acknowledge"):
        automation.post_hook("heartbeat")


def test_cloudflare_failure_payload_does_not_count_as_deployment(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"success": false}'

    class Opener:
        def open(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setenv(
        "CLOUDFLARE_DEPLOY_HOOK",
        "https://api.cloudflare.com/client/v4/pages/webhooks/deploy_hooks/example-id",
    )
    monkeypatch.setattr(automation.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises(RuntimeError, match="accept"):
        automation.post_hook("deploy")
