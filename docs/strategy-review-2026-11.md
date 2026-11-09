# Strategy review, November 2026

Author: Claude · Status: **proposal for Ross; GPT/Otto invited to challenge** (comment on the PR).
Decisions only become decisions when recorded in `docs/decisions.md`.

## 1. The goal, restated

A free, trustworthy public reference that lets an ordinary person answer **"How is the UK doing, and how does it compare with similar countries?"** It should be in plain English, always current, honest about what the numbers can and can't show, and maintained by one person and AI agents. Later, it should support a transparent and defensible scoring layer (decision 12).

Success, concretely:

1. A non-expert finds the answer to a common question in under a minute.
2. Every figure is sourced, dated, correctly labelled by geography and comparable with its peers.
3. The site stays current without Ross's routine involvement.
4. People across the political spectrum regard it as fair.

## 2. How we are executing

### Strong

- **Engineering foundation is ahead of schedule:**
  - reproducible commands, with tests (53) on Linux and Windows;
  - provenance for every saved source response;
  - a guard against OECD changing the definition of a series;
  - promotion that rolls back on failure;
  - a live site with draft previews, and checks that the served site matches the code.
- **The two-agent review loop works and has caught real errors.** Codex found that the UK monthly figure is a centred three-month average, that the licence claim was overstated, and that a failed promotion could delete data. These would have damaged credibility in public.
- **Editorial guardrails are encoded, not just written down:**
  - UK, GB and England kept distinct;
  - peers compared on a common period;
  - outcomes rather than causation;
  - drafts never reach production.
- **The outcomes-based framing has already proved resilient.** The Prime Minister changed in 2026 (Starmer announced his resignation on 22 June 2026; IfG now refers to "Andy Burnham's government"). Pledge trackers have had to re-baseline. An outcomes-and-peers dashboard does not.

### Weak or at risk

1. **Content is far behind infrastructure.** There is one published indicator. A reader gets almost no value until roughly 15–20 indicators across the topics people care about. The danger is that each review cycle keeps polishing the pipeline while the product stays empty.
2. **No product definition yet.** We have not written down who the reader is, what questions they arrive with, or what the homepage answers. The current homepage is a list of cards.
3. **Differentiation is unclear** (see section 3). At least one similar site already exists.
4. **Ross is the courier.** Every Claude ↔ Codex cycle needs Ross to say "review is in". That doesn't scale, and the brief says routine maintenance should need little of his time.
5. **Data will go stale.** The scheduled refresh, failure issues and missed-run monitoring (#4) are not built. Adding indicators before #4 lands multiplies the risk.
6. **Some core public concerns have no comparable international data:** NHS waiting times, immigration levels, many crime measures, and housing supply. A peers-only design would leave out what people most want to know.

## 3. Landscape: what exists already (first pass, Claude, 9 Nov 2026)

| Product | What it does | Peers? | Lesson for us |
| --- | --- | --- | --- |
| [Full Fact Government Tracker](https://fullfact.org/politics/keir-starmer-resignation-manifesto-pledges-government-tracker/) | 92 manifesto pledges, verdicts such as "Achieved", "Appears off track", "Not kept", one page per pledge, error-report form | No | Pledge-based, so tied to one government. Copy its per-item explanation pages and its feedback route. |
| [IfG/Nuffield Public Services Performance Tracker 2026](https://www.instituteforgovernment.org.uk/publication/public-services-performance-tracker-2026) | 250+ indicators across 9 public services; spending, staffing, demand, performance; annual | No (England/UK focus) | Authoritative but annual, long-form and expert-facing. A source and benchmark for public-service indicators. |
| [ONS UK Measures of National Well-being dashboard](https://www.ons.gov.uk/peoplepopulationandcommunity/wellbeing/articles/ukmeasuresofnationalwellbeing/dashboard) | ~60 measures in 10 domains, change vs a year or five years earlier; moved to annual updates in June 2026 | No | A credible domain framework and change-assessment rules to borrow. |
| [USAFacts](https://usafacts.org/our-data/) | Nonpartisan US government data in topic sections; annual "State of the Union in Numbers"; newsletter; CC licence | No (US only) | Closest model for audience and tone. Its editorial principles and annual "state of the nation" report are worth emulating. |
| [UK Pulse](https://ukpulse.pages.dev/press) | 50+ official UK indicators in 7 categories; "G7 international comparisons" for the economy; every number linked to source; CC BY 4.0; operator not named | Partly (economy) | **Closest direct overlap.** Needs a proper look at its quality, freshness and depth before we position ourselves. |
| [Freedom Isn't Free: UK vs G7 wages](https://freedomisntfree.co.uk/tools/uk-vs-g7-economy) | Real wages vs G7, ranked; personal-finance publisher with a stated editorial stance | Yes | Shows how framing undermines trust: its narrative overstates what its own data show. |
| [UK Data Explorer](https://ukdataexplorer.com/dashboard) | Custom ONS dashboards | No | Now "no longer being maintained". This is the failure mode we are designing against. |
| [OSR: intelligent transparency](https://osr.statisticsauthority.gov.uk/guidance/regulatory-guidance-on-intelligent-transparency/pages/2/), [presenting uncertainty](https://osr.statisticsauthority.gov.uk/wp-content/uploads/2022/09/Approaches_to_presenting_uncertainty_in_the_statistical_system.pdf.) | UK statistics regulator guidance | n/a | A recognised UK standard to cite in our methodology. |

**Proposed positioning (for Ross):** *"How is the UK doing compared with similar countries: in plain English, always up to date, and honest about the limits."* Our distinctive combination is:

1. Like-for-like **peer comparison as the default view**, not an add-on.
2. **Continuous automatic updates** with visible freshness.
3. **Geographic precision** (UK vs GB vs England).
4. **Outcomes, not pledges**, so the site survives changes of government.
5. Later, a **transparent, reweightable score**.

No product found so far combines all five.

## 4. Recommendations

### A. Product (needs Ross)

1. **Write a one-paragraph reader definition and the top ~8 questions.** For example: "Am I better off?", "Is the economy growing?", "Is the NHS coping?", "Can people afford a home?", "Are children learning?", "Is the country safe?", "Are public finances sustainable?", "Are we cutting emissions?". The homepage is organised around these questions, not data sources.
2. **Allow UK-only indicators**, clearly marked "no reliable international comparison". This covers the concerns peers can't (NHS waits, migration, crime). For these, show the trend and any official target instead of a peer rank.
3. **Agree a v1 indicator list of about 20** across those questions, before building more. A candidate list for GPT to research and challenge:

   | Question | Candidates | Likely source |
   | --- | --- | --- |
   | Am I better off? | Real wages; real household disposable income per person; relative poverty | OECD (poverty data lag 2–3 years) |
   | Is the economy growing? | GDP per person (real); productivity per hour; inflation; unemployment (done) | OECD / IMF |
   | Is the NHS coping? | Life expectancy; avoidable mortality; waiting times (UK-only, England/Scotland/Wales/NI differ) | OECD / World Bank; NHS England et al. |
   | Can people afford a home? | House price-to-income; rent inflation | OECD house price database |
   | Are children learning? | PISA maths/reading/science | OECD PISA (every 3 years) |
   | Are public finances sustainable? | Government debt % GDP; deficit; tax take % GDP | IMF WEO / OECD |
   | Is the country safe? | Homicide rate (caveated); UK-only crime survey trend | UNODC / ONS CSEW (England and Wales only) |
   | Are we cutting emissions? | GHG emissions per person; renewable share of electricity | OECD / UNFCCC / Ember |

4. **Mark changes of government on charts**, including the 2024 election and the 2026 change of Prime Minister. *Which* events count as markers is editorial, so it needs Ross.
5. **Peers:** keep G7 as the default. Commission the "similar advanced economies" group now (decision 9 says broaden), with explicit selection criteria, e.g. population over 5m, high income, OECD member.

### B. Site structure (Claude builds; Ross approves)

- **Homepage = "UK at a glance":** one row per question showing 2–3 headline figures, each with:
  - the latest value;
  - direction over 1 and 5 years (one consistent rule: "improving / worsening / little change");
  - peer position (e.g. "4th of 7").

  This "level vs direction" view previews the future scoring layer without any weighting.
- **Question pages**, which group indicators and add a short neutral summary.
- **Indicator pages** (exist): add history since 2000 where available, government-change markers, "what changed in the latest update", and a "how to read this" box.
- **Methodology, corrections and changelog pages:** a feedback form (as Full Fact and USAFacts have), a corrections log and our editorial principles, citing OSR guidance.
- **Shareability later:** an auto-generated social image per indicator, embeddable charts and a monthly "UK in numbers" digest.

### C. Delivery process (agents; Ross approves the policy once)

1. **Finish #4 (scheduled refresh and alerts) before adding more than 2–3 more indicators.**
2. **Stop Ross being the courier:**
   - Set up Codex's GitHub code review so a PR comment `@codex review` (or automatic review on every PR) triggers it directly. OpenAI documents this; Otto to verify and set up.
   - Install the Claude Code GitHub Action so Codex or Otto can ask `@claude fix` on a PR.
   - Agree a **standing merge rule**: a PR approved by a second agent, with green CI and Verify deploy, that doesn't touch Ross-owned files (`CODEOWNERS`) may be merged by an agent. Ross only sees `needs-ross`.
   - Turn on branch rules so this is enforced, not trusted.
3. **A weekly digest issue**, generated automatically, covering what changed, what failed and what needs Ross. That should be his only routine touchpoint.
4. **Batch indicators.** Once the v1 list is approved, each indicator is one small PR from a template. Aim for ~10 published in two weeks and ~20 in a month, then a soft launch.
5. **Content checklist per indicator:** plain-English reading age (target ~age 12), source licence verified on the dataset page, geography verified, comparability notes, and a second-agent check of the wording.

### D. Research to commission (split between GPT and Claude)

| # | Question | Owner | Output |
| --- | --- | --- | --- |
| R1 | Landscape deep-dive: ~12 comparable products (UK and abroad: UK Pulse, Full Fact, IfG, ONS, USAFacts, OWID, OECD How's Life/Better Life Index, Gapminder, Social Progress Index, Resolution Foundation, Economics Observatory) covering audience, coverage, peers, update model, funding, maintenance status, and what to copy or avoid | GPT (deep research) | Table plus a one-page synthesis, posted to a GitHub issue |
| R2 | Indicator framework: for each of the ~8 questions, the best internationally comparable series, lag, licence, true UK coverage (UK/GB/E&W), comparability caveats, and the UK-only must-haves | GPT | Proposed v1 list with sources, for Ross's approval |
| R3 | Site patterns: how OWID, USAFacts, ONS and Full Fact structure homepages, topic and indicator pages; accessibility norms; showing uncertainty to lay readers | Claude | Homepage and question-page prototype on a preview branch |
| R4 | Peer selection criteria for a second group | GPT drafts, Claude checks data coverage | Criteria plus a coverage matrix |
| R5 | Scoring methods (OECD/JRC composite-indicator handbook, SDG Index, Social Progress Index, Better Life Index reweighting) | GPT, later | Methodology proposal (decision 12) once ~20 indicators exist |
| R6 | Five short conversations with non-expert readers: "what would you check here?", plus three tasks on the preview | Ross (30 min each) | Notes in an issue; the most valuable research on the list |

## 5. Proposed sequence

1. **This week:** Ross answers A1–A2 and the merge rule (C2). Codex: #4 scheduled refresh. Claude: second indicator (life expectancy, World Bank or OECD), which also proves a draft on a hosted preview. GPT: R1 and R2.
2. **Next week:** Ross approves the v1 indicator list. Agents batch-build. Claude prototypes the homepage (R3) once ~8 indicators exist.
3. **Weeks 3–4:** reach ~20 indicators; methodology and corrections pages; R6 reader tests; then a soft launch to a small audience.
4. **After launch:** the second peer group, the "UK in numbers" digest, then a scoring methodology proposal.

## 6. Unverified in this review

- UK Pulse's depth, freshness and operator. Only its press page was readable from Claude's environment.
- The exact setup of Codex GitHub review and whether `@codex` can push fixes, as opposed to only reviewing.
- Source availability and licences for each candidate indicator in A3. That is R2.
