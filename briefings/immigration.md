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

*Finding:* the Home Office recorded £4.18 billion in resource spending on asylum support, resettlement and accommodation in 2025–26. This is not a total cost of immigration or a net fiscal impact.

</div>

Annual spending by one department and lifetime fiscal models answer different questions, so they cannot be added, averaged or compared directly. For a fuller guide to why studies differ, see the [Migration Observatory's briefing](https://migrationobservatory.ox.ac.uk/resources/briefings/the-fiscal-impact-of-immigration-in-the-uk/).

## What these figures can't tell you

- **Why the numbers changed.** The figures describe what happened. On their own, they don't show how much was due to policy, the economy or events abroad.
- **Wider effects.** Effects on wages, housing, public services and growth are different questions from public finances, and need separate evidence.
- **Everyone who moves.** People who arrive undetected, or who enter legally and stay after their permission ends, are not counted in the small boat or visa figures.
