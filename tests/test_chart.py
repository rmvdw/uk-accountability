from ukdash.chart import line_chart, line_path
from ukdash.schema import Observation


def obs(period, value, status=""):
    return Observation(
        indicator_id="x",
        geography_id="iso:GBR",
        period=period,
        frequency="M",
        value=value,
        status=status or ("missing" if value is None else ""),
    )


def test_missing_value_breaks_the_line():
    rows = [obs("2025-01", 1.0), obs("2025-02", None), obs("2025-03", 3.0), obs("2025-04", 4.0)]
    assert line_path(rows) == [[(24300, 1.0)], [(24302, 3.0), (24303, 4.0)]]


def test_absent_period_breaks_the_line_and_keeps_spacing():
    rows = [obs("2025-01", 1.0), obs("2025-02", 2.0), obs("2025-06", 6.0), obs("2025-07", 7.0)]
    segs = line_path(rows)
    assert [[k - 24300 for k, _ in s] for s in segs] == [[0, 1], [5, 6]]
    svg = line_chart(rows, "UK", "%", 1)
    # Two segments means two move-to commands, so the gap is not bridged.
    path = svg.split('class="line"')[0].rsplit('d="', 1)[1]
    assert path.count("M") == 2


def test_quarterly_and_annual_ordinals_are_consecutive():
    q = [
        Observation(indicator_id="x", geography_id="iso:GBR", period=p, frequency="Q", value=1.0)
        for p in ["2024-Q4", "2025-Q1"]
    ]
    a = [
        Observation(indicator_id="x", geography_id="iso:GBR", period=p, frequency="A", value=1.0)
        for p in ["2023", "2024"]
    ]
    assert len(line_path(q)) == 1
    assert len(line_path(a)) == 1


def test_axis_labels_are_compact_for_large_numbers():
    from ukdash.chart import _axis_fmt

    assert _axis_fmt(934_900, 0, 800_000) == "935k"
    assert _axis_fmt(1_234_000, 0, 800_000) == "1.23m"
    assert _axis_fmt(-55_900, 0, 800_000) == "-56k"
    assert _axis_fmt(4.25, 1, 2) == "4.2"


def test_multi_line_chart_breaks_at_explicitly_missing_y12_value():
    from ukdash.chart import multi_line_chart

    def y12(period, value):
        o = obs(period, value)
        return o.model_copy(update={"frequency": "Y12"})

    # Y12 steps are irregular (quarterly, then six-monthly), so only the missing row
    # itself can show the gap.
    rows = [y12("2024-06", 1.0), y12("2024-12", None), y12("2025-06", 3.0), y12("2025-12", 4.0)]
    svg = multi_line_chart([("Net", rows, "net")], "people", 0)
    path = svg.split('class="line net"')[0].rsplit('d="', 1)[1]
    assert path.count("M") == 2
    # The June 2024 value is cut off by the gap; it still gets a marker, plus the final one.
    assert svg.count('class="dot net"') == 2


def test_multi_line_legend_labels_a_value_from_an_earlier_period():
    from ukdash.chart import multi_line_chart

    a = [obs("2025-01", 1.0), obs("2025-02", 2.0), obs("2025-03", 3.0)]
    b = [obs("2025-01", 5.0), obs("2025-02", 6.0), obs("2025-03", None)]
    svg = multi_line_chart([("A", a, "imm"), ("B", b, "emi")], "people", 0)
    assert "A: <strong>3</strong></span>" in svg
    assert "B: <strong>6</strong> (2025-02)</span>" in svg


def test_nice_scale_uses_round_steps():
    from ukdash.chart import nice_scale

    assert nice_scale(0, 1_590_000)[2] == [0, 400_000, 800_000, 1_200_000, 1_600_000]
    lo, hi, ticks = nice_scale(3.3, 5.2)
    assert ticks == [3.2, 3.6, 4.0, 4.4, 4.8, 5.2] and lo <= 3.3 and hi >= 5.2
    lo, hi, ticks = nice_scale(-120_000, 950_000)  # crosses zero: zero is a tick
    assert 0 in ticks and lo <= -120_000 and hi >= 950_000
