---
id: immigration
title: "What do the latest migration figures show, and what do we know about their effects?"
status: draft
standfirst: "How many people move to and from the UK, why they come, what is happening with asylum and small boats, and what the evidence says about costs and contributions."
indicators:
  - net_migration
  - immigration_long_term
  - emigration_long_term
  - visas_granted
  - asylum_claims
  - asylum_initial_decisions
  - asylum_awaiting_decision
  - small_boat_arrivals
---
{% set c = change("net_migration") %}
{% set pk = peak("net_migration") %}
{% set ci = change("immigration_long_term") %}
{% set ce = change("emigration_long_term") %}
<div class="answer" markdown="1">

**The short answer**

- **Net migration to the UK was {{ num("net_migration") }}** in the {{ when("net_migration") }} (a provisional estimate). It {{ c.verb }} by {{ c.by }} from {{ c.from }} a year earlier. At its highest in the ONS series, which starts in 2012, it was {{ pk.value }} in the {{ pk.when }}.
- **Both flows changed.** Long-term immigration {{ ci.verb }} by {{ ci.by }} to {{ num("immigration_long_term") }}, and emigration {{ ce.verb }} by {{ ce.by }} to {{ num("emigration_long_term") }}.
- **By nationality,** net migration was {{ num("net_migration", breakdown="non_eu_plus") }} for non-EU+ nationals, {{ num("net_migration", breakdown="british") }} for British nationals and {{ num("net_migration", breakdown="eu_plus") }} for EU+ nationals. A negative figure means more people left than arrived.

**Main caveat:** these are provisional estimates, and ONS revises them as more travel data arrive. Recent revisions have changed the headline figure by as much as {{ largest_revision() }} (see below).

</div>

## How many people come and go

Net migration is the difference between two large flows: people moving to the UK for at least a year (immigration) and people leaving for at least a year (emigration). Each point covers the previous 12 months.

{{ lines([["immigration_long_term", "total", "Immigration", "imm"], ["emigration_long_term", "total", "Emigration", "emi"], ["net_migration", "total", "Net migration", "net"]]) }}

These figures include British citizens moving abroad or returning, and they count people, not visas. They are rounded to the nearest 1,000.

## How much the figures change between editions

ONS publishes these estimates twice a year. Each edition revises recent periods as more information arrives about who actually stayed or left. The table shows net migration for each period as first published and as it stands now.

| Period | First published | Latest estimate | Change |
| --- | --- | --- | --- |
{% for r in revisions() %}| {{ r.when }} | {{ r.first }} ({{ r.first_pub }}) | {{ r.latest }} ({{ r.latest_pub }}) | {{ r.change }} |
{% endfor %}

The most recent periods are the most likely to change. The next ONS edition is scheduled for 26 November 2026.

## Why people come: visas granted

{% set cv = change("visas_granted") %}
In the {{ when("visas_granted") }}, **{{ num("visas_granted") }} visas** were granted to people outside the UK to come to work, study, join family or use a humanitarian scheme, excluding visitor and transit visas. That {{ cv.verb }} by {{ cv.pct }} from a year earlier.

{{ bars("visas_granted", {"study": "Study", "work": "Work", "family": "Family", "ukraine": "Ukraine schemes", "other": "Other visas", "euss": "EU Settlement Scheme permits", "bno": "BN(O) route"}) }}

Visas are not the same as migration. They count permissions granted, not people arriving: some visas go unused, one person can receive more than one, and British and Irish citizens need no visa. They also cover a different 12 months from the ONS figures above (the {{ when("visas_granted") }}, versus the {{ when("net_migration") }}), so the two cannot be added together or compared directly.

## Asylum and small boats

{% set ca = change("asylum_claims") %}
{% set cb = change("small_boat_arrivals") %}
{% set cw = change("asylum_awaiting_decision") %}
- **{{ num("asylum_claims") }} people claimed asylum** in the {{ when("asylum_claims") }}, including dependants. That {{ ca.verb }} by {{ ca.pct }} from a year earlier.
- **{{ num("small_boat_arrivals") }} people were detected arriving by small boat** over the same period, which {{ cb.verb }} by {{ cb.pct }}.
- **{{ num("asylum_initial_decisions") }} people received an initial decision.** {{ num("asylum_initial_decisions", breakdown="grants") }} were granted protection or other leave and {{ num("asylum_initial_decisions", breakdown="refusals") }} were refused.
- **{{ num("asylum_awaiting_decision") }} people were waiting for an initial decision** at the {{ when("asylum_awaiting_decision") }}. That {{ cw.verb }} by {{ cw.by }} from {{ cw.from }} a year earlier.

{{ lines([["asylum_claims", "total", "People claiming asylum", "imm"], ["small_boat_arrivals", "total", "Small boat arrivals", "net"]]) }}

These measures overlap, so they should never be added together. Many people who arrive by small boat then claim asylum. Anyone in either group who stays for a year or more is also counted in the long-term migration estimates. Decisions in a year mostly concern claims made in earlier years, so dividing grants by that year's claims does not give a grant rate.

## What it costs and contributes

There is no single official figure for "the cost of immigration". Studies ask different questions about different groups of people over different time spans, so their results cannot be added together or averaged.

<div class="evidence" markdown="1">

**What is the lifetime effect on the public finances of people arriving on different visa routes?**
[Migration Advisory Committee, 2025](https://www.gov.uk/government/publications/the-fiscal-impact-of-immigration-in-the-uk)

*Covers:* new arrivals by route, with dependants · *Time span:* their lifetime in the UK

*Finding:* positive on average for skilled-worker main applicants; negative for care workers and some dependants [TO VERIFY against the MAC report]

</div>
<div class="evidence" markdown="1">

**How does the effect depend on age at arrival and earnings?**
[Office for Budget Responsibility, 2024](https://obr.uk/frs/fiscal-risks-and-sustainability-september-2024/)

*Covers:* illustrative migrants with different profiles · *Time span:* lifetime

*Finding:* depends heavily on earnings: higher earners contribute more than they cost, low earners the reverse [TO VERIFY against the OBR report, and whether the July 2026 report updates it]

</div>
<div class="evidence" markdown="1">

**How much does the Home Office spend supporting people seeking asylum?**
[Home Office annual report and accounts 2025–26](https://www.gov.uk/government/publications/home-office-annual-report-and-accounts-2025-to-2026)

*Covers:* people receiving asylum support · *Time span:* one financial year

*Finding:* [TO VERIFY: the spending figure and the exact line in the accounts]

</div>

Spending on asylum support is a cost to one department in one year. It is not a net fiscal impact and cannot be compared with lifetime estimates. For a fuller guide to why studies differ, see the [Migration Observatory's briefing](https://migrationobservatory.ox.ac.uk/resources/briefings/the-fiscal-impact-of-immigration-in-the-uk/).

## What these figures can't tell you

- **Why the numbers changed.** The figures describe what happened. On their own, they don't show how much was due to policy, the economy or events abroad.
- **Wider effects.** Effects on wages, housing, public services and growth are different questions from public finances, and need separate evidence.
- **Everyone who moves.** People who arrive undetected, or who enter legally and stay after their permission ends, are not counted in the small boat or visa figures.
