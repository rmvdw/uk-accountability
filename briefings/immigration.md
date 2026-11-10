---
id: immigration
title: "Immigration: what the figures show"
status: draft
standfirst: "Five common questions, answered with the latest official figures, then the detail."
indicators:
  - net_migration
  - immigration_long_term
  - emigration_long_term
  - visas_granted
  - asylum_claims
  - asylum_initial_decisions
  - asylum_awaiting_decision
  - small_boat_arrivals
  - permanent_immigration_per_1000
  - asylum_applications_per_1000
---
{% set c = change("net_migration") %}
{% set pk = peak("net_migration") %}
{% set sh = survey("bf_tracker_2026_net_direction", "Higher") %}
{% set sl = survey("bf_tracker_2026_net_direction", "Lower") %}
{% set yr = between("net_migration", "2025-12", "2024-12") %}
{% set cb = change("small_boat_arrivals") %}
{% set hs = cited("home_office_asylum_support_2025_26") %}
{% set pp = peers("permanent_immigration_per_1000") %}
{% set vs = shares("visas_granted", {"study": "study", "work": "work", "family": "family"}) %}
<div class="answer cards" markdown="1">

<p class="hook">About half of adults in Great Britain ({{ sh.pct }}) thought net migration in 2025 was higher than in 2024, and {{ sl.pct }} thought it was lower. It was {{ yr.word }}: {{ yr.value }}, {{ "up" if yr.word == "higher" else "down" }} from {{ yr.from }}. <a href="{{ sh.url }}">Survey</a></p>

<div class="qcard" markdown="1">
<p class="q">How has net migration changed?</p>

**{{ "Up" if c.up else "Down" }} {{ c.pct }} in a year.** {{ num("net_migration") }} in the {{ when("net_migration") }}, from {{ c.from }}. Peak: {{ pk.value }} ({{ pk.when }}).

<p class="limit">Provisional; recent figures revised by up to {{ largest_revision() }}. The survey ran in {{ sh.when }}, before these figures were published.</p>
</div>

<div class="qcard" markdown="1">
<p class="q">Why do people come?</p>

**{{ "Mostly" if vs[0].share + vs[1].share > 50 else "Largely" }} to {{ vs[0].label }} ({{ vs[0].pct }}) or {{ vs[1].label }} ({{ vs[1].pct }})**, of {{ num("visas_granted") }} visas granted to people abroad in the {{ when("visas_granted") }}. Separately, {{ num("asylum_claims") }} people claimed asylum.

<p class="limit">Visas count permissions, not arrivals, and exclude visitors. Asylum claims are counted separately. Neither is a breakdown of the ONS figure.</p>
</div>

<div class="qcard" markdown="1">
<p class="q">How many people arrived by small boat?</p>

**{{ "More" if cb.up else "Fewer" }} than a year earlier.** {{ num("small_boat_arrivals") }} detected in the {{ when("small_boat_arrivals") }}, {{ cb.pct }} {{ "more" if cb.up else "fewer" }}.

<p class="limit">For scale, ONS estimates {{ num("immigration_long_term") }} people moved to the UK for a year or more in the {{ when("immigration_long_term") }}. Different measures: the first is not a share of the second.</p>
</div>

<div class="qcard" markdown="1">
<p class="q">How much does the Home Office spend on asylum support?</p>

**{{ hs.value }} in {{ hs.period_short }}** on asylum support, resettlement and accommodation.

<p class="limit">One department's spending in one year, including resettlement. Not the total cost of asylum or of immigration. <a href="{{ hs.url }}">What it covers</a></p>
</div>

<div class="qcard" markdown="1">
<p class="q">How does the UK compare?</p>

**{{ pp.position[0]|upper }}{{ pp.position[1:] }}** for permanent-type immigration in {{ pp.when }}: {{ pp.uk }} per 1,000 residents.

<p class="limit">OECD measure, not the ONS one; {{ pp.when }} is the latest year all seven report. <a href="#how-does-the-uk-compare-with-other-g7-countries">Comparison</a></p>
</div>

</div>

## How many people come and go

{{ lines([["immigration_long_term", "total", "Immigration", "imm"], ["emigration_long_term", "total", "Emigration", "emi"], ["net_migration", "total", "Net migration", "net"]]) }}

Net migration is immigration (people arriving for at least a year) minus emigration (people leaving for at least a year). Each point covers the previous 12 months. The figures count people, not visas, include British citizens, and are rounded to the nearest 1,000.

By nationality, net migration was {{ num("net_migration", breakdown="non_eu_plus") }} for non-EU+ nationals, {{ num("net_migration", breakdown="british") }} for British nationals and {{ num("net_migration", breakdown="eu_plus") }} for EU+ nationals (negative means more left than arrived).

## What people think and what the figures show

| Question asked | What people said | What the official figures show |
| --- | --- | --- |
| Was net migration in 2025 higher or lower than in 2024? | Higher: {{ sh.pct }}<br>Lower: {{ sl.pct }}<br><span class="meta">{{ sh.who }}, {{ sh.when }}</span> | {{ yr.word|capitalize }}: {{ yr.value }} in the {{ yr.when }}, from {{ yr.from }} in the {{ yr.from_when }} (ONS, provisional) |

Survey results record what people said at a date, not facts; see the [full survey record]({{ sh.url }}). We add a row only where a survey question can be matched exactly to an official figure, whichever way the answer points.

## How does the UK compare with other G7 countries?

{% set pp = peers("permanent_immigration_per_1000") %}
{% set pa = peers("asylum_applications_per_1000") %}
Comparing countries needs one definition and one year for all of them, so these figures come from international sources and cover earlier years than the UK figures above.

**Permanent-type immigration (OECD).** In {{ pp.when }}, the UK granted permanent-type residence to {{ pp.uk }} foreign nationals per 1,000 residents: {{ pp.position }}.

{{ pp.chart }}

**Asylum.** In {{ pa.when }}, {{ pa.uk }} people per 1,000 residents made a new asylum application in the UK: {{ pa.position }}.

{{ pa.chart }}

<details markdown="1">
<summary>What these comparisons count</summary>

- **Permanent-type immigration (OECD)** counts foreign nationals granted residence expected to last: permanently, or on permits that can be renewed indefinitely. It includes people already living in the country who move from a temporary to a long-term status, and leaves out most temporary migration, such as students. It measures something different from the ONS figures above (who is counted, and when), so the two should not be compared directly. Some recent figures are OECD estimates.
- **Asylum** uses UNHCR's count of new applications by people, excluding repeat applications and appeals. Countries run different procedures, so small differences are not meaningful.
- Both divide by the World Bank's population estimate for the same year.

</details>

## What changed since the previous release

{% set rc = release_changes() %}
ONS published these figures in {{ rc.current }}. Compared with its previous release ({{ rc.previous }}), they add {{ rc.new|length }} new {{ "period" if rc.new|length == 1 else "periods" }} and revise {{ rc.revised|length }} that were already published. A revision is ONS re-estimating the same 12 months with more travel data. It is not a change in migration.

**New in this release**

| Period | Immigration | Emigration | Net |
| --- | --- | --- | --- |
{% for r in rc.new %}| {{ r.when }} | {{ r.figures.immigration_long_term }} | {{ r.figures.emigration_long_term }} | {{ r.figures.net_migration }} |
{% endfor %}

ONS rounds each figure to the nearest 1,000 separately, so immigration minus emigration can differ from net migration by 1,000.

**Revised net migration**

| Period | Was ({{ rc.previous }}) | Now | Revision |
| --- | --- | --- | --- |
{% for r in rc.revised %}| {{ r.when }} | {{ r.figures.net_migration.before }} | {{ r.figures.net_migration.after }} | {{ r.figures.net_migration.change }} |
{% endfor %}

<details markdown="1">
<summary>Each period as first published and as it stands now</summary>

Estimates usually move most in their first year, by up to {{ largest_revision() }} recently. The next ONS release is due on 26 November 2026.

| Period | First published | Latest estimate | Change |
| --- | --- | --- | --- |
{% for r in revisions() %}| {{ r.when }} | {{ r.first }} ({{ r.first_pub }}) | {{ r.latest }} ({{ r.latest_pub }}) | {{ r.change }} |
{% endfor %}

</details>

## Why people come: visas granted

{% set cv = change("visas_granted") %}
In the {{ when("visas_granted") }}, **{{ num("visas_granted") }} visas** were granted to people outside the UK to come to work, study, join family or use a humanitarian scheme, excluding visitor and transit visas. That {{ cv.verb }} by {{ cv.pct }} from a year earlier.

{{ bars("visas_granted", {"study": "Study", "work": "Work", "family": "Family", "ukraine": "Ukraine schemes", "other": "Other visas", "euss": "EU Settlement Scheme", "bno": "BN(O) route"}) }}

Visas count permissions, not people: some go unused and British and Irish citizens need none. They also cover a different 12 months from the ONS figures (the {{ when("visas_granted") }}, not the {{ when("net_migration") }}), so the two can't be compared directly.

## Asylum and small boats

{% set ca = change("asylum_claims") %}
{% set cb = change("small_boat_arrivals") %}
{% set cw = change("asylum_awaiting_decision") %}
- **{{ num("asylum_claims") }} people claimed asylum** in the {{ when("asylum_claims") }}, including dependants, {{ ca.pct }} {{ "more" if ca.up else "fewer" }} than a year earlier.
- **{{ num("small_boat_arrivals") }} arrived by small boat** over the same period, {{ cb.pct }} {{ "more" if cb.up else "fewer" }}.

<details markdown="1">
<summary>Decisions and the backlog</summary>

{{ num("asylum_initial_decisions") }} people received an initial decision: {{ num("asylum_initial_decisions", breakdown="grants") }} were granted protection or other leave and {{ num("asylum_initial_decisions", breakdown="refusals") }} were refused. {{ num("asylum_awaiting_decision") }} were waiting for an initial decision at the {{ when("asylum_awaiting_decision") }}, {{ cw.by }} {{ "more" if cw.up else "fewer" }} than a year earlier. Decisions in a year mostly concern earlier claims, so grants divided by that year's claims is not a grant rate.

</details>

{{ lines([["asylum_claims", "total", "People claiming asylum", "imm"], ["small_boat_arrivals", "total", "Small boat arrivals", "net"]]) }}

These overlap, so never add them: most small-boat arrivals claim asylum, and anyone staying a year or more is also in the migration estimates above.

## Effects, evidence and uncertainty

There is no single official figure for "the cost of immigration". The studies below ask different questions about different people over different time spans, so they are not ends of one range and can't be added or averaged. Effects on wages, housing and demand for public services are separate questions; this page does not yet cover them.

<div class="evidence" markdown="1">

**What is the lifetime effect on the public finances of people arriving on skilled work visas?**
[Migration Advisory Committee, 2025](https://assets.publishing.service.gov.uk/media/6938108633c7ace9c4a41e42/The_Fiscal_Impact_of_Immigration_Final__1_.pdf)

*Covers:* people arriving on Skilled Worker visas in 2022/23, with their dependants · *Time span:* their modelled lifetime in the UK

*Finding:* for this group, the model estimates a positive average lifetime contribution from main applicants. Care-worker main applicants and some groups of dependants have negative estimated contributions. These are modelled public-finance effects, not a measure of the wider value of their work.

</div>
<div class="evidence" markdown="1">

**How does the effect depend on earnings, age at arrival and length of stay?**
[Office for Budget Responsibility, 2024](https://obr.uk/frs/fiscal-risks-and-sustainability-september-2024/)

*Covers:* an illustrative worker without dependants, in several scenarios · *Time span:* lifetime

*Finding:* in the OBR's illustrations, the fiscal effect varies with earnings, age at arrival and how long someone stays. Higher earnings and leaving before retirement improve the public-finance balance. These examples model one worker, not all migrants or households. The OBR's July 2026 report refers back to these scenarios and does not replace them.

</div>
<div class="evidence" markdown="1">

**How much did the Home Office spend on asylum support, resettlement and accommodation?**
[Home Office annual report and accounts 2025–26](https://assets.publishing.service.gov.uk/media/6a58e9953ae256c99b702f50/36.54_HO_ARA_25-26_WEB.pdf#page=212)

*Covers:* that departmental spending category, including resettlement · *Time span:* 1 April 2025 to 31 March 2026

*Finding:* the Home Office recorded {{ hs.value }} in resource spending on asylum support, resettlement and accommodation in {{ hs.period }} ([details]({{ hs.url }})). This is not a total cost of immigration or a net fiscal impact.

</div>

Annual spending by one department and lifetime fiscal models answer different questions, so they cannot be added, averaged or compared directly. For a fuller guide to why studies differ, see the [Migration Observatory's briefing](https://migrationobservatory.ox.ac.uk/resources/briefings/the-fiscal-impact-of-immigration-in-the-uk/).

## What these figures can't tell you

- **Why the numbers changed.** The figures describe what happened. On their own, they don't show how much was due to policy, the economy or events abroad.
- **Wider effects.** Effects on wages, housing, public services and growth are different questions from public finances, and need separate evidence.
- **Everyone who moves.** People who arrive undetected, or who enter legally and stay after their permission ends, are not counted in the small boat or visa figures.
