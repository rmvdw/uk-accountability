"""Dependency-free inline SVG charts. Colours come from CSS variables in the page."""

from __future__ import annotations

from html import escape

from .schema import Observation, period_ordinal


def _fmt(v: float, decimals: int) -> str:
    return f"{v:,.{decimals}f}"


def line_path(rows: list[Observation]) -> list[list[tuple[int, float]]]:
    """Split a series into continuous segments of (period ordinal, value).

    A missing value, or a period absent from the data, ends the segment, so
    gaps are never bridged.
    """
    segments: list[list[tuple[int, float]]] = []
    prev: int | None = None
    for o in sorted(rows, key=lambda o: period_ordinal(o.period, o.frequency)):
        k = period_ordinal(o.period, o.frequency)
        if o.value is None:
            prev = None
            continue
        if prev is None or k != prev + 1:
            segments.append([])
        segments[-1].append((k, o.value))
        prev = k
    return segments


def line_chart(rows: list[Observation], label: str, unit: str, decimals: int) -> str:
    pts = [(o.period, o.value) for o in sorted(rows, key=lambda o: o.period) if o.value is not None]
    if len(pts) < 2:
        return ""
    w, h, pl, pr, pt, pb = 640, 280, 64, 24, 16, 36
    vals = [v for _, v in pts]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.1 or abs(hi) * 0.1 or 1
    lo, hi = lo - pad, hi + pad
    segments = line_path(rows)
    k0 = segments[0][0][0]
    k1 = segments[-1][-1][0]
    span = max(k1 - k0, 1)

    def x(k: int) -> float:
        return pl + (w - pl - pr) * (k - k0) / span

    def y(v: float) -> float:
        return pt + (h - pt - pb) * (1 - (v - lo) / (hi - lo))

    path = " ".join(
        f"{'M' if i == 0 else 'L'}{x(k):.1f},{y(v):.1f}"
        for seg in segments
        for i, (k, v) in enumerate(seg)
    )
    # Isolated points (segments of one) would be invisible as a path: mark them.
    singles = "".join(
        f'<circle cx="{x(seg[0][0]):.1f}" cy="{y(seg[0][1]):.1f}" r="2.5" class="dot"/>'
        for seg in segments
        if len(seg) == 1
    )
    ticks = [lo + (hi - lo) * k / 4 for k in range(5)]
    grid = "".join(
        f'<line x1="{pl}" x2="{w - pr}" y1="{y(t):.1f}" y2="{y(t):.1f}" class="grid"/>'
        f'<text x="{pl - 6}" y="{y(t):.1f}" class="axis" text-anchor="end" '
        f'dominant-baseline="middle">{_fmt(t, decimals)}</text>'
        for t in ticks
    )
    first, last = pts[0], pts[-1]
    desc = (
        f"{label}: {_fmt(first[1], decimals)} {unit} in {first[0]}, "
        f"{_fmt(last[1], decimals)} {unit} in {last[0]}."
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{escape(desc)}" class="chart">'
        f"<title>{escape(desc)}</title>{grid}"
        f'<path d="{path}" class="line"/>{singles}'
        f'<circle cx="{x(k1):.1f}" cy="{y(last[1]):.1f}" r="4" class="dot"/>'
        f'<text x="{pl}" y="{h - 8}" class="axis">{escape(first[0])}</text>'
        f'<text x="{w - pr}" y="{h - 8}" class="axis" text-anchor="end">{escape(last[0])}</text>'
        f"</svg>"
    )


def bar_chart(
    values: list[tuple[str, float]],
    labels: dict[str, str],
    highlight: str,
    unit: str,
    decimals: int,
    period: str,
) -> str:
    if not values:
        return ""
    w, row, pl, pr = 640, 34, 120, 72
    h = row * len(values) + 8
    top = max(abs(v) for _, v in values) or 1
    bars = []
    for i, (g, v) in enumerate(values):
        bw = (w - pl - pr) * abs(v) / top
        cls = "bar uk" if g == highlight else "bar"
        yy = 4 + i * row
        bars.append(
            f'<text x="{pl - 8}" y="{yy + row / 2:.0f}" class="label" text-anchor="end" '
            f'dominant-baseline="middle">{escape(labels[g])}</text>'
            f'<rect x="{pl}" y="{yy + 5}" width="{bw:.1f}" height="{row - 10}" '
            f'rx="3" class="{cls}"/>'
            f'<text x="{pl + bw + 6:.1f}" y="{yy + row / 2:.0f}" class="label" '
            f'dominant-baseline="middle">{_fmt(v, decimals)}</text>'
        )
    desc = f"Comparison for {period}, {unit}: " + "; ".join(
        f"{labels[g]} {_fmt(v, decimals)}" for g, v in values
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{escape(desc)}" class="chart">'
        f"<title>{escape(desc)}</title>{''.join(bars)}</svg>"
    )
