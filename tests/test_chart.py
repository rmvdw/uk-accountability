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
