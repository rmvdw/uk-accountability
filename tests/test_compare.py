from ukdash.compare import latest, peer_comparison


def test_comparison_uses_common_period_not_mixed_latest(fixture_project):
    d = fixture_project.indicators["test_unemployment"]
    rows = fixture_project.read_observations(d.id)
    group = fixture_project.peer_groups[d.peers.group]

    # The UK has June data, but Japan stops at May: compare on May for everyone.
    assert latest(rows, "iso:GBR").period == "2025-06"
    comp = peer_comparison(d, group, rows)
    assert comp.period == "2025-05"
    assert len(comp.values) == 7

    # lower_is_better: best (lowest) first. Fixture May values: JPN 2.9, DEU 3.8, USA 4.5, UK 4.7.
    assert comp.values[0][0] == "iso:JPN"
    assert comp.uk_rank == 4


def test_peer_with_no_data_is_listed_as_excluded(fixture_project):
    d = fixture_project.indicators["test_unemployment"]
    rows = [o for o in fixture_project.read_observations(d.id) if o.geography_id != "iso:ITA"]
    group = fixture_project.peer_groups[d.peers.group]
    comp = peer_comparison(d, group, rows)
    assert comp.excluded == {"iso:ITA": "No data in source"}
    assert len(comp.values) == 6
