"""Dependency-free inline SVG charts. Colours come from CSS variables in the page."""

from __future__ import annotations

from html import escape

from .schema import IRREGULAR_STEP, Observation, period_ordinal


def _fmt(v: float, decimals: int) -> str:
    return f"{v:,.{decimals}f}"


def _axis_fmt(v: float, decimals: int, span: float) -> str:
    """Short axis labels: 934,900 becomes 935k, 1,234,000 becomes 1.23m."""
    a = abs(v)
    if span >= 10_000 or a >= 100_000:
        if a >= 1_000_000:
            return f"{v / 1_000_000:.2f}".rstrip("0").rstrip(".") + "m"
        return f"{v / 1_000:,.0f}k"
    return _fmt(v, decimals)


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
        if prev is None or (k != prev + 1 and o.frequency not in IRREGULAR_STEP):
            segments.append([])
        segments[-1].append((k, o.value))
        prev = k
    return segments


def line_chart(
    rows: list[Observation],
    label: str,
    unit: str,
    decimals: int,
    period_label=lambda p: p,
) -> str:
    rows = [o for o in rows if o.breakdown == "total"]
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
        f'dominant-baseline="middle">{_axis_fmt(t, decimals, hi - lo)}</text>'
        for t in ticks
    )
    first, last = pts[0], pts[-1]
    desc = (
        f"{label}: {_fmt(first[1], decimals)} {unit} in {period_label(first[0])}, "
        f"{_fmt(last[1], decimals)} {unit} in {period_label(last[0])}."
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{escape(desc)}" class="chart">'
        f"<title>{escape(desc)}</title>{grid}"
        f'<path d="{path}" class="line"/>{singles}'
        f'<circle cx="{x(k1):.1f}" cy="{y(last[1]):.1f}" r="4" class="dot"/>'
        f'<text x="{pl}" y="{h - 8}" class="axis">{escape(period_label(first[0]))}</text>'
        f'<text x="{w - pr}" y="{h - 8}" class="axis" text-anchor="end">'
        f"{escape(period_label(last[0]))}</text>"
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
    # Size the label and value margins to the text (labels render at ~18px in a 640 box,
    # roughly 10px per character), so nothing is clipped on a phone.
    w, row = 640, 34
    pl = min(max(80, 10 * max(len(labels[g]) for g, _ in values) + 16), 300)
    pr = 10 * max(len(_fmt(v, decimals)) for _, v in values) + 16
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


def multi_line_chart(
    series: list[tuple[str, list[Observation], str]],
    unit: str,
    decimals: int,
    period_label=lambda p: p,
) -> str:
    """Several series on one scale. `series` is [(label, rows, css class)]; a zero line is
    drawn when the range crosses zero. Labels appear in an HTML legend, not on the lines,
    so they never collide on a phone."""
    # Explicitly missing rows stay in `rows` so line_path breaks the line there (Y12 and
    # AT steps are irregular, so dates alone can't reveal a gap); `valid` sets the scale.
    usable = []
    for label, rows, cls in series:
        valid = [o for o in rows if o.value is not None]
        if len(valid) >= 2:
            usable.append((label, rows, cls, valid))
    if not usable:
        return ""
    w, h, pl, pr, pt, pb = 640, 300, 64, 24, 16, 36
    vals = [o.value for *_, valid in usable for o in valid]
    lo, hi = min(vals + [0.0]), max(vals + [0.0])
    pad = (hi - lo) * 0.08 or 1
    # Counts that can't go negative start the axis at zero rather than below it.
    lo, hi = (lo - pad if lo < 0 else 0.0), hi + pad
    ks = [period_ordinal(o.period, o.frequency) for *_, valid in usable for o in valid]
    k0, k1 = min(ks), max(ks)
    span = max(k1 - k0, 1)

    def x(k: int) -> float:
        return pl + (w - pl - pr) * (k - k0) / span

    def y(v: float) -> float:
        return pt + (h - pt - pb) * (1 - (v - lo) / (hi - lo))

    ticks = [lo + (hi - lo) * k / 4 for k in range(5)]
    grid = "".join(
        f'<line x1="{pl}" x2="{w - pr}" y1="{y(t):.1f}" y2="{y(t):.1f}" class="grid"/>'
        f'<text x="{pl - 6}" y="{y(t):.1f}" class="axis" text-anchor="end" '
        f'dominant-baseline="middle">{_axis_fmt(t, decimals, hi - lo)}</text>'
        for t in ticks
    )
    zero = (
        f'<line x1="{pl}" x2="{w - pr}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="zero"/>'
        if lo < 0 < hi
        else ""
    )
    paths, desc_parts, legend = [], [], []
    for label, rows, cls, valid in usable:
        segs = line_path(rows)
        d = " ".join(
            f"{'M' if i == 0 else 'L'}{x(k):.1f},{y(v):.1f}"
            for seg in segs
            for i, (k, v) in enumerate(seg)
        )
        last = max(valid, key=lambda o: period_ordinal(o.period, o.frequency))
        # A value isolated by gaps on both sides has no line to draw, so mark it.
        lone = "".join(
            f'<circle cx="{x(seg[0][0]):.1f}" cy="{y(seg[0][1]):.1f}" r="2.5" class="dot {cls}"/>'
            for seg in segs
            if len(seg) == 1
        )
        paths.append(
            f'<path d="{d}" class="line {cls}"/>{lone}'
            f'<circle cx="{x(period_ordinal(last.period, last.frequency)):.1f}" '
            f'cy="{y(last.value):.1f}" r="4" class="dot {cls}"/>'
        )
        desc_parts.append(
            f"{label} {_fmt(last.value, decimals)} {unit} in {period_label(last.period)}"
        )
        legend.append((cls, label, last))
    first_p = min(o.period for *_, valid in usable for o in valid)
    last_p = max(o.period for *_, valid in usable for o in valid)
    # The legend gives each series' latest value; if a series has none for the chart's
    # latest period, its value is labelled with its own period rather than passed off.
    legend = [
        f'<span class="key {cls}"><i></i>{escape(label)}: '
        f"<strong>{_fmt(last.value, decimals)}</strong>"
        + ("" if last.period == last_p else f" ({escape(period_label(last.period))})")
        + "</span>"
        for cls, label, last in legend
    ]
    desc = "; ".join(desc_parts) + "."
    return (
        f'<div class="legend">{"".join(legend)}</div>'
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{escape(desc)}" class="chart">'
        f"<title>{escape(desc)}</title>{grid}{zero}{''.join(paths)}"
        f'<text x="{pl}" y="{h - 8}" class="axis">{escape(period_label(first_p))}</text>'
        f'<text x="{w - pr}" y="{h - 8}" class="axis" text-anchor="end">'
        f"{escape(period_label(last_p))}</text></svg>"
    )
