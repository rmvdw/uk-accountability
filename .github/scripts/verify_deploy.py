"""Check that Cloudflare Pages is serving this commit, in the right mode.

Production (main) must not include drafts; preview branches must. Polls the
site's build-info.json until it reports the expected commit, or times out.

    python .github/scripts/verify_deploy.py <base_url> <commit_sha> <expect_drafts: true|false>
"""

import json
import sys
import time
import urllib.request

base, sha, expect = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3] == "true"
deadline = time.time() + 15 * 60
last = None
while time.time() < deadline:
    try:
        req = urllib.request.Request(
            f"{base}/build-info.json?t={int(time.time())}",
            headers={"User-Agent": "uk-accountability-verify", "Cache-Control": "no-cache"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            last = json.load(resp)
    except Exception as exc:  # noqa: BLE001 - keep polling until the deadline
        last = {"error": str(exc)}
    if last.get("source_commit") == sha:
        break
    time.sleep(20)
else:
    sys.exit(f"Timed out: {base} never served commit {sha[:7]}. Last response: {last}")

print(json.dumps(last, indent=2))
if last["preview_with_drafts"] is not expect:
    sys.exit(f"{base} preview_with_drafts={last['preview_with_drafts']}, expected {expect}")
for ind in last["indicators"]:
    with urllib.request.urlopen(
        urllib.request.Request(
            f"{base}/{ind}/", headers={"User-Agent": "uk-accountability-verify"}
        ),
        timeout=30,
    ) as resp:
        if resp.status != 200:
            sys.exit(f"{base}/{ind}/ returned {resp.status}")
print(f"OK: {base} serves {sha[:7]}, drafts={expect}, {len(last['indicators'])} indicator page(s)")
