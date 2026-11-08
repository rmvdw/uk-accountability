# UK Dashboard

A free, public reference for how the UK is doing compared with similar countries, built only from official public data. Maintained by one owner (Ross) and AI agents.

**Status:** scaffold. No real indicators published yet. See [issues](https://github.com/rmvdw/uk-accountability/issues) for what's next.

## Quick start

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and `make`. uv installs the right Python version itself.

```sh
make setup     # install pinned dependencies (needs network for packages)
make check     # lint, tests, validate saved data — offline
make build     # build the static site into site/ — offline
make preview   # like build, but includes draft indicators, for review only
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

## For agents

Read [AGENTS.md](AGENTS.md) first. Work is tracked in GitHub Issues; changes come back as pull requests.

### Proven access routes

| Route | Status |
| --- | --- |
| Claude (claude.ai cloud session): clone, branch, push, PR, issues via REST API | Proven 2026-11-08 |
| GitHub Actions CI on pull requests | Proven by this PR's CI run (see PR) |
| Codex cloud environment | Not yet set up |
| Cloudflare Pages preview | Not yet set up (needs Ross's Cloudflare account) |
| Live fetch from statistical APIs on GitHub runners | Not yet tested |

## Licence

Code: MIT (see [LICENSE](LICENSE)). Data shown on the site remain under their publishers' licences; each indicator records its source and attribution.
