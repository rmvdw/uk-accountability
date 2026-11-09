"""Small, dependency-free Actions helpers. No statistical logic or AI calls.

Secrets are read from the environment, never passed in command arguments or errors.
The workflow owns the ordered refresh -> check/build -> commit/push -> deploy -> verify
-> heartbeat sequence. This module also maintains one failure/recovery issue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

MARKER = "<!-- ukdash:routine-refresh:production -->"
CANDIDATE_MARKER = "<!-- ukdash:routine-refresh:candidates -->"
DATA_PATHS = ["data/raw", "data/observations", "data/manifest.json", "data/checks.json"]


def git(*args: str, root: Path | None = None) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True, encoding="utf-8").strip()


def secret_url(name: str) -> str:
    value = os.environ.get(name, "").strip()
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        raise ValueError(f"{name} must be a provider HTTPS URL")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{name} must not include query parameters or fragments")
    if name == "CLOUDFLARE_DEPLOY_HOOK":
        valid = parsed.hostname == "api.cloudflare.com" and re.fullmatch(
            r"/client/v4/pages/webhooks/deploy_hooks/[A-Za-z0-9-]+", parsed.path
        )
    else:
        valid = parsed.hostname == "hc-ping.com" and re.fullmatch(
            r"/[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", parsed.path
        )
    if not valid:
        raise ValueError(f"{name} has an unexpected provider or path")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_hook(kind: str) -> None:
    name = "CLOUDFLARE_DEPLOY_HOOK" if kind == "deploy" else "HEALTHCHECKS_PING_URL"
    url = secret_url(name)
    request = urllib.request.Request(url, data=b"", method="POST")
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(request, timeout=30) as response:
        body = response.read()
        if not 200 <= response.status < 300:
            raise RuntimeError("provider rejected request")
    if kind == "heartbeat" and body.strip() != b"OK":
        # Healthchecks also returns HTTP 200 for unknown/rate-limited checks.
        raise RuntimeError("monitor did not acknowledge the heartbeat")
    if kind == "deploy":
        payload = json.loads(body)
        if payload.get("success") is not True:
            raise RuntimeError("Cloudflare did not accept the deployment")
    print(f"{kind}: acknowledged")


def commit_data(root: Path, failed: bool = False) -> str:
    """Persist only data; on a failed refresh, only failed-attempt metadata.

    Refuse unexpected working-tree changes or a dirty index. Do not rebase/force a
    racing main update: the workflow's normal fast-forward push must reject it.
    """
    if git("diff", "--cached", "--name-only", root=root):
        raise RuntimeError("refusing an already staged change")
    changed = git("diff", "--name-only", root=root).splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard", root=root).splitlines()
    if any(
        not any(p == allowed or p.startswith(allowed + "/") for allowed in DATA_PATHS)
        for p in changed + untracked
    ):
        raise RuntimeError("refresh changed files outside the data allowlist")
    if failed:
        before = json.loads(git("show", "HEAD:data/checks.json", root=root))
        after = json.loads((root / "data/checks.json").read_text(encoding="utf-8"))
        for indicator, record in after.items():
            previous = before.get(indicator, {})
            if record.get("last_successful_check_at") != previous.get("last_successful_check_at"):
                raise RuntimeError("failed refresh advanced a successful-check timestamp")
            if record != previous and record.get("last_attempt_result") != "failed":
                raise RuntimeError("failed refresh contains a healthy attempt")
        # Even if a rollback failed locally, no candidate observations enter this commit.
        git("restore", "--source=HEAD", "--", *DATA_PATHS[:-1], root=root)
        paths = ["data/checks.json"]
    else:
        paths = DATA_PATHS
    git("add", "--", *paths, root=root)
    if git("diff", "--cached", "--name-only", root=root):
        git(
            "-c",
            "user.name=github-actions[bot]",
            "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit",
            "-m",
            "Record failed refresh attempt" if failed else "Refresh published data",
            root=root,
        )
    return git("rev-parse", "HEAD", root=root)


class GitHub:
    def __init__(self):
        self.repo = os.environ["GITHUB_REPOSITORY"]
        self.token = os.environ["GH_TOKEN"]

    def request(self, method: str, path: str, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repo}/{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)


def find_issue(api, label: str, marker: str):
    """Find only this kind of issue; editorial review and production health are separate."""
    page = 1
    while True:
        items = api.request("GET", f"issues?state=all&labels={label}&per_page=100&page={page}")
        issue = next((i for i in items if marker in (i.get("body") or "")), None)
        if issue or len(items) < 100:
            return issue
        page += 1


def sync_candidate_issue(api, outcome: str, run_url: str) -> None:
    """A candidate failure is a review task, never a production failure or approval."""
    if outcome not in {"success", "failure"}:
        return  # A skipped/cancelled check must not close an outstanding review.
    issue = find_issue(api, "review", CANDIDATE_MARKER)
    if outcome == "success":
        if issue and issue["state"] == "open":
            api.request(
                "POST",
                f"issues/{issue['number']}/comments",
                {
                    "body": f"Candidate validation passed. This is not publication approval.\n\n"
                    f"[Run]({run_url})\n\nCodex (routine refresh automation)"
                },
            )
            api.request("PATCH", f"issues/{issue['number']}", {"state": "closed"})
        return
    body = (
        f"{CANDIDATE_MARKER}\nDraft briefing candidates need review.\n\n"
        f"[Inspect the candidate-validation step]({run_url}).\n\n"
        "Published briefings remain on their frozen editions. Valid production refreshes "
        "have a separate data/build/deploy gate and are not blocked by this review task. "
        "Fix the candidate and obtain editorial approval before publishing a new edition.\n\n"
        "Codex (routine refresh automation)"
    )
    if issue:
        if issue["state"] == "closed":
            api.request("PATCH", f"issues/{issue['number']}", {"state": "open", "body": body})
    else:
        api.request(
            "POST",
            "issues",
            {
                "title": "Briefing candidates need review",
                "body": body,
                "labels": ["review"],
            },
        )


def sync_issue(api, healthy: bool, stage: str, run_url: str, checks: dict) -> None:
    """Reuse the same issue across failures; no duplicate comments on unchanged errors."""
    issue = find_issue(api, "data-failure", MARKER)
    if healthy:
        if issue and issue["state"] == "open":
            api.request(
                "POST",
                f"issues/{issue['number']}/comments",
                {
                    "body": f"Recovered: refresh, deployment verification and heartbeat passed.\n\n"
                    f"[Run]({run_url})\n\nCodex (routine refresh automation)"
                },
            )
            api.request("PATCH", f"issues/{issue['number']}", {"state": "closed"})
        return
    errors = {
        k: v.get("last_error")
        for k, v in checks.items()
        if v.get("last_attempt_result") == "failed"
    }
    fingerprint = hashlib.sha256(json.dumps([stage, errors], sort_keys=True).encode()).hexdigest()
    state_marker = f"<!-- failure:{fingerprint} -->"
    body = (
        f"{MARKER}\n{state_marker}\nRoutine refresh did not complete: **{stage}**.\n\n"
        f"[Inspect the workflow run]({run_url}). No success heartbeat was sent.\n\n"
        "Source failures retain the previous observations. A later deployment failure may "
        "leave new data committed while the site still serves the previous build. "
        "Confirm the served commit before calling this recovered.\n\n"
        "Codex (routine refresh automation)"
    )
    if issue:
        if issue["state"] == "closed" or state_marker not in issue["body"]:
            api.request("PATCH", f"issues/{issue['number']}", {"state": "open", "body": body})
    else:
        api.request(
            "POST",
            "issues",
            {"title": "Routine refresh needs attention", "body": body, "labels": ["data-failure"]},
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["preflight", "persist", "deploy", "heartbeat", "report", "candidate-report"],
    )
    parser.add_argument("--failed", action="store_true")
    parser.add_argument("--healthy", action="store_true")
    parser.add_argument("--stage", default="workflow")
    parser.add_argument("--outcome", choices=["success", "failure", "skipped"], default="skipped")
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            secret_url("CLOUDFLARE_DEPLOY_HOOK")
            secret_url("HEALTHCHECKS_PING_URL")
            if os.environ.get("GITHUB_REF") != "refs/heads/main":
                raise RuntimeError("production refresh requires main")
            print("deployment and monitor configuration present; main branch confirmed")
        elif args.command == "persist":
            print(commit_data(Path.cwd(), args.failed))
        elif args.command in ("deploy", "heartbeat"):
            post_hook(args.command)
        else:
            path = Path("data/checks.json")
            checks = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            url = f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
            url += f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
            if args.command == "candidate-report":
                sync_candidate_issue(GitHub(), args.outcome, url)
            else:
                sync_issue(GitHub(), args.healthy, args.stage, url, checks)
    except Exception as exc:
        # urllib exceptions can include secret hook URLs. Never emit their text.
        message = f"{args.command} failed ({type(exc).__name__}); inspect this stage"
        raise SystemExit(message) from None


if __name__ == "__main__":
    main()
