"""Calculations. Kept out of templates so they can be tested."""

from __future__ import annotations

from dataclasses import dataclass

from .schema import TOTAL, IndicatorDefinition, Observation, PeerGroup

UK = "iso:GBR"


@dataclass(frozen=True)
class PeerComparison:
    period: str | None  # None when no common period exists
    values: list[tuple[str, float]]  # (geography_id, value), best first
    included: list[str]
    excluded: dict[str, str]  # geography_id -> reason shown to readers
    uk_rank: int | None  # 1 = best, when direction is not neutral


def series(rows: list[Observation], geography_id: str, breakdown: str = TOTAL) -> list[Observation]:
    return sorted(
        (o for o in rows if o.geography_id == geography_id and o.breakdown == breakdown),
        key=lambda o: o.period,
    )


def latest(
    rows: list[Observation], geography_id: str, breakdown: str = TOTAL
) -> Observation | None:
    s = [o for o in series(rows, geography_id, breakdown) if o.value is not None]
    return s[-1] if s else None


def peer_comparison(
    d: IndicatorDefinition, group: PeerGroup, rows: list[Observation]
) -> PeerComparison:
    """Latest period for which every included peer has a value (never mixes years)."""
    excluded = dict(d.peers.exclusions)
    candidates = [g for g in group.members if g not in excluded]

    by_geo: dict[str, dict[str, float]] = {g: {} for g in candidates}
    for o in rows:
        if o.geography_id in by_geo and o.value is not None and o.breakdown == TOTAL:
            by_geo[o.geography_id][o.period] = o.value

    for g in candidates:
        if not by_geo[g]:
            excluded[g] = "No data in source"
    included = [g for g in candidates if g not in excluded]

    common = set.intersection(*(set(by_geo[g]) for g in included)) if included else set()
    if not common:
        return PeerComparison(None, [], included, excluded, None)

    period = max(common)
    values = [(g, by_geo[g][period]) for g in included]
    if d.direction == "lower_is_better":
        values.sort(key=lambda gv: gv[1])
    else:
        values.sort(key=lambda gv: gv[1], reverse=True)

    rank = None
    if d.direction != "neutral":
        rank = next((i + 1 for i, (g, _) in enumerate(values) if g == UK), None)
    return PeerComparison(period, values, included, excluded, rank)
