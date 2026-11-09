"""Data contract, enforced. See docs/data-contract.md."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# A: calendar year. Q: calendar quarter. M: month. M3: rolling 3 months ending that month.
# Y12: rolling 12 months ending that month ("year ending June 2026" = 2026-06; a calendar
# year is the year ending December). AT: a stock as at the end of that month.
Frequency = Literal["A", "Q", "M", "M3", "Y12", "AT"]

_YM = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
PERIOD_PATTERNS: dict[str, re.Pattern[str]] = {
    "A": re.compile(r"^\d{4}$"),
    "Q": re.compile(r"^\d{4}-Q[1-4]$"),
    "M": _YM,
    "M3": _YM,
    "Y12": _YM,
    "AT": _YM,
}
# Frequencies whose series may legitimately mix steps (e.g. calendar years plus the latest
# year-ending-June point), so gaps between periods are not treated as missing data.
IRREGULAR_STEP = {"Y12", "AT"}


def period_ordinal(period: str, frequency: str) -> int:
    """Consecutive integers for consecutive periods of one frequency (for spacing and gaps)."""
    if frequency == "A":
        return int(period)
    if frequency == "Q":
        y, q = period.split("-Q")
        return int(y) * 4 + int(q) - 1
    y, m = period.split("-")
    return int(y) * 12 + int(m) - 1


GEO_ID = re.compile(r"^(iso:[A-Z]{3}|gss:[A-Z]\d{8})$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9_]*$")
TOTAL = "total"
INDICATOR_ID = re.compile(r"^[a-z0-9][a-z0-9_]*$")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Observations -----------------------------------------------------------


class Observation(Strict):
    indicator_id: str
    geography_id: str
    period: str
    frequency: Frequency
    value: float | None
    status: str = ""
    breakdown: str = TOTAL  # e.g. "british", "work"; "total" for the headline series

    @field_validator("geography_id")
    @classmethod
    def _geo(cls, v: str) -> str:
        if not GEO_ID.match(v):
            raise ValueError(f"geography_id {v!r} is not a canonical ID (iso:XXX or gss:X99999999)")
        return v

    @field_validator("breakdown")
    @classmethod
    def _breakdown(cls, v: str) -> str:
        if not SLUG.match(v):
            raise ValueError(f"breakdown {v!r} must be lower_snake_case")
        return v

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(v):
            raise ValueError("value must be a finite number (NaN and infinity are not allowed)")
        return v

    @model_validator(mode="after")
    def _period_and_missing(self) -> Observation:
        if not PERIOD_PATTERNS[self.frequency].match(self.period):
            raise ValueError(f"period {self.period!r} does not match frequency {self.frequency}")
        if self.value is None and not self.status:
            raise ValueError("a missing value needs a status flag explaining why")
        return self

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.indicator_id, self.geography_id, self.breakdown, self.period)


# --- Indicator definitions --------------------------------------------------


class Source(Strict):
    publisher: str
    dataset: str
    url: str
    licence: str
    licence_url: str | None = None
    attribution: str
    adapter: str
    query: dict = Field(default_factory=dict)


class Coverage(Strict):
    population: str
    seasonal_adjustment: str
    geography_note: str


class Peers(Strict):
    group: str
    exclusions: dict[str, str] = Field(
        default_factory=dict, description="geography_id -> documented reason"
    )


class Comparison(Strict):
    rule: Literal["common_latest_period"] = "common_latest_period"


class IndicatorDefinition(Strict):
    id: str
    title: str
    status: Literal["draft", "published"]
    what_it_measures: str
    why_it_matters: str
    unit: str
    decimals: int = Field(ge=0, le=4)
    frequency: Frequency
    measure_type: Literal["rate", "flow", "stock", "index"] = Field(
        description="flow = an amount over a period; stock = a level at a date (never summed "
        "with flows); rate = a ratio or percentage; index = relative to a base."
    )
    direction: Literal["higher_is_better", "lower_is_better", "neutral"]
    coverage: Coverage
    source: Source
    peers: Peers | None = Field(
        default=None,
        description="None for UK-only indicators with no reliable international comparison "
        "(decision 16).",
    )
    breakdowns: dict[str, str] = Field(
        default_factory=dict, description="slug -> label for non-total series, e.g. british"
    )
    comparison: Comparison = Comparison()
    caveats: list[str] = Field(default_factory=list)
    check_cadence_days: int = Field(gt=0)
    period_basis: dict[str, Literal["month", "centred_3m"]] = Field(
        default_factory=dict,
        description=(
            "geography_id -> what one monthly period means for that geography. Default 'month'. "
            "'centred_3m': a three-month average labelled by its middle month (e.g. OECD UK LFS)."
        ),
    )

    @model_validator(mode="after")
    def _period_basis(self) -> IndicatorDefinition:
        if self.period_basis and self.frequency != "M":
            raise ValueError("period_basis only applies to monthly (M) indicators")
        if (self.frequency == "AT") != (self.measure_type == "stock"):
            raise ValueError("stocks use frequency AT, and AT is only for stocks")
        for slug in self.breakdowns:
            if not SLUG.match(slug) or slug == TOTAL:
                raise ValueError(f"invalid breakdown slug {slug!r}")
        return self

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not INDICATOR_ID.match(v):
            raise ValueError("id must be lower_snake_case")
        return v


# --- Provenance and checks --------------------------------------------------


class ManifestEntry(Strict):
    indicator_id: str
    path: str
    sha256: str
    request: str
    retrieval_method: Literal["live", "manual"]
    retrieved_at: datetime
    publisher_release_date: str | None = None
    vintage: str | None = None  # the publisher's edition, e.g. "YE December 2025 (May 2026)"
    licence: str


class CheckRecord(Strict):
    last_attempt_at: datetime | None = None
    last_attempt_result: Literal["ok", "unchanged", "failed"] | None = None
    last_successful_check_at: datetime | None = None
    last_error: str | None = None


# --- Config -----------------------------------------------------------------


class Geography(Strict):
    id: str
    label: str
    short_label: str
    note: str = ""
    codes: dict[str, str] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _geo(cls, v: str) -> str:
        if not GEO_ID.match(v):
            raise ValueError(f"{v!r} is not a canonical geography ID")
        return v


class PeerGroup(Strict):
    label: str
    rationale: str
    members: list[str]
