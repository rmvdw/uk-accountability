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

Refreshes are serialised (workflow `concurrency`), so two runs never overwrite each other.

## Failure handling

- One persistent GitHub issue per failing source or workflow, labelled `data-failure`. Update it when the failure state changes; close it on recovery.
- Unusual value changes are flagged for investigation, not rejected automatically.

## Freshness on the page

Each indicator shows its observation period and last successful check. The page calculates "check overdue" in the reader's browser from `last_successful_check_at + check_cadence_days`, so a stopped workflow still shows up as overdue. "No newer data published" is different from "check overdue" and is displayed differently.

## Keeping the schedule alive

GitHub disables scheduled workflows in public repositories after 60 days with no repository activity. A successful unchanged check still commits an updated `data/checks.json`, which counts as activity. An independent missed-run monitor (e.g. Healthchecks.io, pinged only on success) is added before unattended operation.

## Deployment

A commit pushed with the default `GITHUB_TOKEN` does not trigger other push-triggered workflows. The refresh workflow therefore builds and deploys explicitly as later jobs in the same workflow, or dispatches deployment deliberately. Prove the actual route works; do not assume.

## Before routine operation is switched on

Demonstrate one changed refresh, one unchanged refresh and one failed refresh, and confirm that the failed candidate was not published and its issue was updated.
