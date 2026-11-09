# UK Dashboard

A free, public reference for how the UK is doing compared with similar countries, built only from official public data. Maintained by one owner (Ross) and AI agents.

**Status:** early. One indicator published (unemployment rate, UK + G7). Live at https://uk-accountability.pages.dev. See [issues](https://github.com/rmvdw/uk-accountability/issues) for what's next.

## Quick start

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and `make`. uv installs the right Python version itself.

```sh
make setup     # install pinned dependencies (needs network for packages)
make check     # lint, tests, validate saved data — offline
make build     # build the static site into site/ — offline
make preview   # like build, but includes draft indicators, for review only
               # (Cloudflare does this automatically for every non-main branch)
make serve     # serve site/ at http://localhost:8000
make refresh   # fetch live data; promotes only if everything validates
make refresh ID=<indicator>   # fetch one indicator, drafts included
```

**Windows without `make`:** run the underlying commands from the `Makefile`, e.g. `uv sync --locked`, `uv run pytest -q`, `uv run python -m ukdash check`, `uv run python -m ukdash build`. CI runs the tests on Windows too.

`check` and `build` never contact statistical sources, so they work in sandboxed agent environments. Only `refresh` needs access to publishers' APIs.

## How it fits together

```
indicators/*.yml      what each indicator is (definition, source, peers, caveats)
config/               canonical geographies and peer groups
src/ukdash/
  sources/            one adapter per publisher: fetch (network) + parse (offline)
  refresh.py          fetch → parse → validate → build in staging → promote
  validate.py         schema and consistency checks
  compare.py          calculations (trend, common-period peer comparison)
  chart.py            inline SVG charts, no JavaScript library
  build.py            renders templates/ into site/
data/                 saved raw responses, observations, provenance, check records
tests/fixtures/       synthetic test data — never published
docs/                 decisions, data contract, refresh policy
```

## Adding an indicator

1. Open a **New indicator** issue. Ross approves meaning, peers and wording.
2. If the publisher has no adapter yet, add `src/ukdash/sources/<publisher>.py` (see `sources/__init__.py`) with tests that parse a saved response.
3. Add `indicators/<id>.yml` (fields in `docs/data-contract.md`) with `status: draft`.
4. Get its first data while it is still a draft (drafts are never shown on the site). Either:
   - **Live:** `make refresh ID=<id>` somewhere with network access to the source, e.g. a GitHub Actions run; or
   - **Manual:** download the official file yourself, then
     `uv run python -m ukdash import-manual --indicator <id> --file <path> --request "<official URL>"`.
     It is parsed by the same adapter, checksummed and recorded as `retrieval_method: manual`. It does not count as a live check.
5. Set `status: published` in a PR for Ross to review.

## Briefings

Question-led explainers in `briefings/<id>.md` (front matter plus Markdown). Numbers are template calls such as `{{ num("net_migration") }}`, `{{ change(...).verb }}` or `{{ lines([...]) }}`, never typed figures, so every number is traceable to data.

- Review previews (any non-`main` branch) show a **candidate** built from current data.
- `uv run python -m ukdash edition <id>` freezes the candidate into `briefings/editions/<id>/<edition>.json`: page, facts and source vintages together. It refuses while any `[TO VERIFY` marker remains.
- To publish, set `status: published` and `published_edition: <edition>` in a PR. That needs Ross (decision 18). Production shows only that frozen edition, so a data refresh never changes published wording.
- `uv run python -m ukdash briefing-diff <id>` lists what a new candidate would change.

## For agents

Read [AGENTS.md](AGENTS.md) first. Work is tracked in GitHub Issues; changes come back as pull requests.

### Proven access routes

| Route | Status |
| --- | --- |
| Claude (claude.ai cloud session): clone, branch, push, PR, issues via REST API | Proven 2026-11-08 |
| GitHub Actions CI on pull requests (Linux + Windows) | Proven 2026-11-08 |
| Codex: fresh checkout, `make setup/check/build/preview`, reviews posted to PRs | Proven 2026-11-08 (Codex review environments on Windows and Linux; Windows build also proven by CI) |
| Cloudflare Pages: production deploy from `main` (no drafts) and a preview per PR (drafts included) | Proven 2026-11-09; checked after every deploy by the **Verify deploy** workflow |
| Live fetch from statistical APIs on GitHub runners | Proven 2026-11-08 for OECD ([run 42507705905](https://github.com/rmvdw/uk-accountability/actions/runs/42507705905)) |

## Routine refresh and monitoring

The **Routine refresh** workflow is deliberately inactive for production until
the setup below is complete and repository variable `REFRESH_ENABLED` is `true`.
Its proposed schedule is daily at **07:23 UTC**. `make refresh` fetches only
published indicators; drafts remain for explicit review/rehearsal fetches.

### Rehearse before enabling

On a PR changing the refresh workflow, helper or adapters, a read-only runner job
executes `.github/scripts/rehearse_refresh.py`. It fetches every registered
indicator into a disposable copy, including the approved immigration drafts,
copies the briefings and renders their candidates against the refreshed data,
then exercises saved-source recapture, unchanged checks, an injected fetch
failure and recovery. Recapture stores genuine publisher bytes under new paths
to test a changed release; it does not pretend the numerical observations changed.
Numerical changed/unchanged/failure cases also run in `tests/test_refresh.py`.

To run locally: `uv run python .github/scripts/rehearse_refresh.py` (needs publisher
network access). On GitHub: Actions → Routine refresh → Run workflow → mode
`rehearsal`. It never pushes data, deploys or pings the monitor. The first rehearsal
must be green; inspect actual source and safety evidence in its logs.

### Configure the two secrets

1. In Cloudflare Pages project **uk-accountability**, Settings → Builds → Add
   deploy hook. Name it `routine-refresh`; choose branch **main**. Save the complete
   hook URL as GitHub repository Actions secret `CLOUDFLARE_DEPLOY_HOOK`. The URL
   authorises a build, so keep it out of issues, screenshots and logs. This uses
   the existing Git-connected Pages project, with no broad Cloudflare API token.
2. In Healthchecks.io, use the free Hobbyist plan and create one check for this
   workflow. Set a 1-day period with a 3-hour grace period, and configure/test an
   email notification destination. Save its UUID ping URL
   (`https://hc-ping.com/<uuid>`) as Actions secret `HEALTHCHECKS_PING_URL`.
   Do not use auto-provisioning or a paid notification channel. The workflow
   sends an empty success ping only after data refresh AND served-site
   verification pass. A missed, cancelled or failed run sends no success ping.
3. Confirm the repository has label `data-failure` and Actions may write contents
   and issues. A main-branch protection rule may require an approved bot route;
   the workflow never force-pushes or bypasses a rule. If a push is rejected,
   resolve that configuration before unattended operation.
4. After the independent review and merge, set repository Actions variable
   `REFRESH_ENABLED=true`, and manually run mode `publish` on **main**. Verify the
   committed timestamp, the exact served commit, no drafts in production, and
   receipt of the monitor ping. Exercise the failure/recovery issue lifecycle
   before calling unattended operation proven. Rehearsal tests alone do not
   establish production deployment, notification delivery or branch permissions.

Disable routine operation by setting `REFRESH_ENABLED=false`. This does not pause
Healthchecks; pause that check deliberately for planned downtime to avoid an alert.
Never disable the monitor as an automatic response to a failing refresh.

### What the production workflow does

- Requires both secret URLs before fetching; serialises refresh runs.
- Runs `make refresh`, then `uv run python -m ukdash check` and `make build`
  for a valid candidate. Full code tests stay in CI; refreshed observations must
  pass data and briefing-candidate validation, not assertions tied to an old release.
- Commits only allowlisted data paths. An unchanged source still commits its
  new successful-check timestamp. A failed refresh may commit only failed-attempt
  metadata; prior observations/raw data and successful-check times are preserved.
- Pushes normally to main. A racing main update rejects the push; retry from the
  latest main rather than rebasing a candidate validated against different code.
- Explicitly POSTs the main deploy hook and polls the served commit/draft mode in
  the same workflow. It does not depend on a `GITHUB_TOKEN` push starting CI.
  Cloudflare's Git integration may also build the push, so two builds of the same
  commit can appear; the explicit hook is retained and the exact served SHA is checked.
- Signals the independent monitor only after full success, then closes the single
  persistent `data-failure` issue. Repeated identical failures do not create more
  issues; recurrence reopens the same issue.

If validation or deployment fails after the source refresh, inspect the stage and
run linked in the issue. A deployment failure can leave new data committed while
the previous site is still live. The issue must not be closed until served-site
verification succeeds. Cancellation/timeout may prevent issue reporting; the
independent missed-run monitor is the backstop. Overdue labels are already computed
in each reader's browser, so they also work when no rebuild occurs.

This workflow refreshes indicator data. Published Briefings remain on their frozen,
reviewed editions; candidate validation does not approve a new Briefing edition.

References: [Cloudflare deploy hooks](https://developers.cloudflare.com/pages/configuration/deploy-hooks/),
[GitHub token-trigger rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow),
[Healthchecks ping API](https://healthchecks.io/docs/http_api/),
[Healthchecks free plan](https://healthchecks.io/pricing/).

## Licence

Code: MIT (see [LICENSE](LICENSE)). Data shown on the site remain under their publishers' licences; each indicator records its source and attribution.
