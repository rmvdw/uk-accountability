import pytest
from pydantic import ValidationError

from ukdash.project import Project
from ukdash.schema import Observation

BASE = dict(indicator_id="x", geography_id="iso:GBR", period="2024-03", frequency="M", value=1.0)


def test_valid_observation():
    assert Observation(**BASE).key == ("x", "iso:GBR", "2024-03")


@pytest.mark.parametrize(
    "change",
    [
        {"period": "2024-Q1"},  # quarter label on monthly data
        {"frequency": "Q"},  # monthly label on quarterly data
        {"geography_id": "GB"},  # non-canonical id
        {"geography_id": "iso:GB"},
        {"value": None},  # missing value without a status
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": float("-inf")},
    ],
)
def test_invalid_observation(change):
    with pytest.raises(ValidationError):
        Observation(**{**BASE, **change})


def test_missing_value_with_status_is_allowed():
    assert Observation(**{**BASE, "value": None, "status": "missing"}).value is None


def test_uk_and_gb_are_distinct():
    geos = Project.load().geographies
    assert geos["iso:GBR"].label == "United Kingdom"
    assert geos["gss:K03000001"].label == "Great Britain"
    # ISO codes must never point at Great Britain.
    assert "iso3" not in geos["gss:K03000001"].codes
    assert geos["iso:GBR"].codes["iso3"] == "GBR"
