"""Data contract, enforced. See docs/data-contract.md."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Frequency = Literal["A", "Q", "M", "M3"]

PERIOD_PATTERNS: dict[str, re.Pattern[str]] = {
    "A": re.compile(r"^\d{4}$"),
    "Q": re.compile(r"^\d{4}-Q[1-4]$"),
    "M": re.compile(r"^\d{4}-(0[1-9]|1[0-2])$"),
    "M3": re.compile(r"^\d{4}-(0[1-9]|1[0-2])$"),
}


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

    @field_validator("geography_id")
    @classmethod
    def _geo(cls, v: str) -> str:
        if not GEO_ID.match(v):
            raise ValueError(f"geography_id {v!r} is not a canonical ID (iso:XXX or gss:X99999999)")
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
    def key(self) -> tuple[str, str, str]:
        return (self.indicator_id, self.geography_id, self.period)


# --- Indicator definitions --------------------------------------------------


class Source(Strict):
    publisher: str
    dataset: str
    url: str
    licence: str
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
    direction: Literal["higher_is_better", "lower_is_better", "neutral"]
    coverage: Coverage
    source: Source
    peers: Peers
    comparison: Comparison = Comparison()
    caveats: list[str] = Field(default_factory=list)
    check_cadence_days: int = Field(gt=0)

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
