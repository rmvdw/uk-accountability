# Refresh and publication policy

## Principles

- Routine refreshes run ordinary Python in GitHub Actions. No AI model is in the refresh path; agents are for building, review and repair.
- `make check` and `make build` never contact statistical sources. Only `make refresh` does.
- Git history is the record of the revisions this project captured. It is not a full publisher revision history.

## Four timestamps, kept separate

| Field | Moves when |
| --- | --- |
| Observation period | The source publishes a newer period. |
| Publisher release date | Recorded from the source when available. |
| Last successful check (`last_successful_check_at`) | A live fetch succeeds **and** validates, whether or not values changed. |
| Site built at | Every build. An offline rebuild never advances the check time. |

## Refresh sequence (`make refresh`)

1. Fetch every published indicator into a staging directory.
2. Parse and validate the whole candidate release.
3. Build the site from the candidate.
4. Only if every required step passes: promote raw files, observations, manifest and checks into `data/`.
5. If anything fails (fetch, parse, validation, or an error while building): promote nothing except the failed attempt in `data/checks.json` (`last_attempt_*` only; never `last_successful_check_at`). The previous release stays published.

Promotion is a swap with rollback: the staged release is copied to `.release/new`, each current item is moved to `.release/old` and the new one moved in. If any step fails, every swap is undone and `data/` is exactly as before. If an earlier run was interrupted and `.release/` still exists, the next promotion refuses to run until someone inspects it; it is never deleted automatically, because it may hold the previous release.

Refreshes are serialised (workflow `concurrency`), so two runs never overwrite each other.

## Failure handling

- One persistent GitHub issue per failing source or workflow, labelled `data-failure`. Update it when the failure state changes; close it on recovery.
- Unusual value changes are flagged for investigation, not rejected automatically.

## Freshness on the page

Each indicator shows its observation period and last successful check. The page calculates "check overdue" in the reader's browser from `last_successful_check_at + check_cadence_days`, so a stopped workflow still shows up as overdue. "No newer data published" is different from "check overdue" and is displayed differently.

## Keeping the schedule alive

GitHub disables scheduled workflows in public repositories after 60 days with no repository activity. A successful unchanged check still commits an updated `data/checks.json`, which counts as activity. An independent missed-run monitor (e.g. Healthchecks.io, pinged only on success) is added before unattended operation.

## Deployment

Cloudflare Pages builds every push. `main` is production and never shows drafts; any other branch is a review preview that includes drafts and carries a "Review preview" banner. The site's `build-info.json` records the commit, branch and mode, and the **Verify deploy** workflow polls it after each push to confirm Cloudflare is serving the right commit in the right mode.


A commit pushed with the default `GITHUB_TOKEN` does not trigger other push-triggered workflows. The refresh workflow therefore builds and deploys explicitly as later jobs in the same workflow, or dispatches deployment deliberately. Prove the actual route works; do not assume.

The implementation is `.github/workflows/refresh.yml`: daily at 07:23 UTC, gated by
repository variable `REFRESH_ENABLED=true` and restricted to `main`. It explicitly
triggers a Cloudflare Pages **main** deploy hook and verifies the served commit in
the same job. Both the hook and an independent Healthchecks UUID ping URL are
required before a source fetch starts. See README for configuration and activation.
Cloudflare's Git integration can also build the bot push; the explicit hook may
produce a second build of the same commit. Verify the served SHA in either case.
The production job uses `make build` to validate refreshed data and frozen published
editions without rendering draft candidates. After verified production and its
success heartbeat, a separate non-blocking check renders briefing candidates.
A candidate-only failure opens/reopens a persistent issue labelled `review`;
candidate recovery closes that issue without approving publication. It is separate
from the production `data-failure` issue and cannot change its recovery state.
Skipped checks leave pending review work open. Reporting errors are visible in the
workflow logs; they do not invalidate an already verified production release.
Full code tests run in CI on code changes, not against a changing live release.

An unchanged source advances and commits check metadata. On source failure, the
workflow restores the prior observations/raw/manifest before committing only failed
attempts. Successful-check timestamps may not advance in that failure commit.
No code or indicator-definition changes are allowed in an automated data commit.
If the remote main branch advances during the job, its ordinary push fails; never
force or rebase the already checked candidate. A validation failure after refresh
blocks all publication; a later deployment failure may leave refreshed data committed
without being live. Inspect `build-info.json` before reporting recovery.

One persistent workflow-level issue, labelled `data-failure`, tracks production
failures and reopens on recurrence. It links to the failed run without leaking
secret URLs. It closes only after successful refresh, deployed-commit verification
and a monitor acknowledgement. Identical failures do not generate repeated comments.
A cancelled/timed-out run may not report an issue, so the independent monitor is
required; it receives no success signal for that run.

The PR/manual rehearsal fetches all registered sources into a disposable copy and
exercises changed raw capture, unchanged checks, injected source failure and recovery.
The copy includes briefings, so it also renders candidate prose and charts against
the refreshed observations while keeping published editions frozen.
It has read-only permissions and cannot publish or send a production heartbeat.
Fixture tests cover numerical changes, data-only/failed-attempt-only commits and the
failure/recovery issue lifecycle. These checks are separate from the production
activation evidence below.

## Before routine operation is switched on

Demonstrate one changed refresh, one unchanged refresh and one failed refresh, and confirm that the failed candidate was not published and its issue was updated.

Also prove a real production deploy hook, received independent-monitor heartbeat,
tested notification route, and recovery closure on the real repository. Until then,
leave the schedule disabled. Existing approved immigration drafts supply the second
publisher/adapter rehearsal; do not publish an extra indicator just to exercise this
workflow. Briefing editions remain subject to the atomic editorial-review process.
