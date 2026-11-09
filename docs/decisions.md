# Decisions

Consequential choices only. Newest status wins. "Proposed" is not approval: Ross's review of the PR that changes a row is the approval.

## Brief (confirmed by Ross)

A free, public accountability reference for ordinary people, showing UK progress and relative strengths against appropriate peers. Maintained by one human owner and AI agents. Start small; expand indicators, analysis and tools over time. Code and project knowledge must transfer between agents.

## Decisions

| # | Topic | Decision | Status | Date |
| --- | --- | --- | --- | --- |
| 1 | Project home | `rmvdw/uk-accountability`, public | Done by Ross | 2026-11-08 |
| 2 | Code licence | MIT. Source data keep their own licences and attribution. | **Confirmed by Ross** | 2026-11-08 |
| 3 | Coordination | GitHub Issues hold queue, ownership and status. Otto is provisional lead; role is transferable. No Notion in v1. | Proposed | 2026-11-08 |
| 4 | Agents | Claude and Codex first; Gemini when a task benefits. | Proposed | 2026-11-08 |
| 5 | Build | Python + Jinja static site. Charts rendered as inline SVG in Python, so no JavaScript chart library or Node toolchain. A small inline script computes "check overdue" in the browser. | Proposed | 2026-11-08 |
| 6 | Validation | pydantic models only (no pandas/pandera) while the dataset is small. Revisit if tables grow large. | Proposed | 2026-11-08 |
| 7 | Commands | `make setup`, `make check`, `make build`, `make refresh` | Proposed | 2026-11-08 |
| 8 | Hosting | Cloudflare Pages, connected to GitHub by Ross: builds `main` to production (`uk-accountability.pages.dev`) and each PR to a preview URL. Build command: `pip install uv && uv sync --locked && uv run python -m ukdash build`; output `site`. | **Done by Ross**; proven 2026-11-09 | 2026-11-09 |
| 9 | Peers | G7 is the starting default, only where definitions and coverage support comparison. Exceptions documented per indicator. Ross wants to broaden peer groups later (e.g. similar-sized advanced economies); new groups need his approval. | **Confirmed by Ross** (start with G7) | 2026-11-08 |
| 10 | Framing | v1 shows outcomes and comparisons with context. Government-change dates are context, not causation. No scores in v1. | **Confirmed by Ross** for v1 | 2026-11-08 |
| 12 | Scoring (future) | Ross intends to add scoring once the infrastructure is in place, provided the methodology is transparent and defensible. Not started; needs its own methodology proposal for Ross before any build work. | Direction set by Ross | 2026-11-08 |
| 13 | Site name | "UK Dashboard" is a placeholder. Decide before public launch. | **Needs Ross** | |
| 11 | First indicator | OECD harmonised unemployment rate, UK + G7. Fix exact series and common period before implementing. | Proposed | 2026-11-08 |

## Agent access (evidence only)

| Environment | Verified | Not yet verified |
| --- | --- | --- |
| Claude (claude.ai cloud session) | Clone, push, branches, issues and PRs via REST API (2026-11-08). Python 3.13, uv, git available. Statistical APIs (OECD, ONS, World Bank) unreachable from this sandbox. | Reading Actions logs. |
| Claude Code GitHub Action | Documented for Pro via subscription token. | Not installed. Whether an `@claude` mention opens a PR automatically or only pushes a branch. |
| ChatGPT / Otto | Can list connected GitHub repositories (Otto, 2026-11-08). | Push and PR route. |
| Codex | Fresh checkout and setup/check/build/preview in its review environments (Windows for #5, Linux for #7); reviews posted to PRs (2026-11-08). Windows builds are separately proven by CI. | Pushing branches and opening PRs. |
| GitHub-hosted runner | Live OECD SDMX fetch and full refresh, 2026-11-08 (run 42507705905). | Other publishers (ONS, World Bank) when first used. |

## First three tasks

Tracked as GitHub issues #2, #3 and #4. Ross's open editorial decisions are in issue #1. Summary:

1. **Scaffold and prove access** (Claude; reviewer Codex). Commands, schemas, geography lookup, templates, CI. Clean runner passes setup/check/build. One real branch → PR → CI cycle. Preview via hosting, or recorded as blocked.
2. **First real indicator in preview** (OECD unemployment, UK + G7). Trend, compatible peer comparison, source link, geography, period, check or manual-retrieval date, caveat, table. Ross reviews public wording.
3. **Transferability and routine operation** (Codex from fresh checkout; reviewer Claude). Second indicator from a different publisher. Changed, unchanged and failed refreshes behave per `docs/refresh-policy.md`. Deployment route and overdue display proven.

## References

- [UK toponymic guidelines (GOV.UK)](https://www.gov.uk/government/publications/toponymic-guidelines/toponymic-guidelines-for-map-and-other-editors-united-kingdom-of-great-britain-and-northern-ireland--2)
- [GitHub: disabling and enabling workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)
- [GitHub: triggering a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
- [Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions)
- [OECD: unemployment rate](https://www.oecd.org/en/data/indicators/unemployment-rate.html)
