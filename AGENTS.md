# Agent instructions

Shared working rules for every agent (Claude, Codex, Gemini or other). Keep this file short: detail lives in the linked docs. `CLAUDE.md` only imports this file.

## Purpose

A free public reference dashboard that helps ordinary people understand UK outcomes, progress and comparisons with appropriate peers. One human owner (Ross) and interchangeable AI agents. Start small; add coverage and tools incrementally.

## Where things live

| What | Where |
| --- | --- |
| Setup and commands | `README.md` |
| Work queue, ownership, status | GitHub Issues (labels: `ready`, `working`, `blocked`, `review`) |
| Changes and review | Pull requests |
| Consequential decisions | `docs/decisions.md` |
| Data schema, geography, periods | `docs/data-contract.md` |
| Refresh, freshness and failure rules | `docs/refresh-policy.md` |
| Indicator definitions | `indicators/*.yml` |
| Peer groups, geographies | `config/` |

Otto (Ross's GPT) is the provisional prioritisation lead. Any authorised agent can take over: coordination state lives in GitHub, not in chat memory.

## Working rules

1. Read `README.md`, `docs/decisions.md` and the issue. Check open PRs and branches for overlapping work.
2. Claim the issue (comment with your agent name, set `working`). One branch per task. Handovers transfer ownership explicitly in the issue.
3. Make the smallest complete change. Record discoveries and blockers in the issue.
4. Run `make check` and `make build` before opening a PR. The PR states: starting commit, what changed, checks run (with output), source links, open questions.
5. A second agent reviews substantive calculation, data-interpretation or workflow changes.
6. Update `README.md` when commands or setup change.
7. Never claim tests passed, permissions exist, deployment works or a source is reachable without evidence. Keep secrets out of files, issues and PRs.

## What comes back to Ross

Changes to indicator meaning, peer selection, public wording or conclusions, spending, repository visibility or licensing. Those paths are listed in `.github/CODEOWNERS`; the **Editorial gate** check blocks them until Ross adds the `ross-approved` label. Agents decide and document routine schema and engineering details. Label editorial PRs `needs-ross`.

## Merging (decision 17)

An agent may merge a PR when all of these hold:

- a *different* agent has reviewed it and said it is ready to merge (comment on the PR);
- CI (Linux and Windows), Cloudflare Pages and Verify deploy are green;
- the Editorial gate passes.

Never add `ross-approved` yourself. Use squash merges. Delete the branch after merging if you can.

All agents currently act through Ross's GitHub account, so sign every comment with your agent name.

## Non-negotiables

- Never publish invented observations. Test fixtures live under `tests/fixtures/` and are labelled as such.
- UK, GB, England, Wales, Scotland and Northern Ireland are distinct. Use canonical geography IDs (`docs/data-contract.md`); ISO `GBR` means the United Kingdom, never Great Britain.
- Peer comparisons use a common period and compatible definitions. Never silently mix latest years.
- Describe observed outcomes. Do not attribute causation to government.
- Explain, don't advocate (decision 15): say plainly what the data show; where estimates are contested, show the credible range and why it differs; never argue for a policy.
- Routine refreshes run ordinary code; no AI model in the refresh path.
