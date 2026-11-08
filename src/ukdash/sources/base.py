from __future__ import annotations

from dataclasses import dataclass

from ..schema import Geography, IndicatorDefinition, Observation


@dataclass(frozen=True)
class Fetched:
    raw: bytes
    filename: str  # stable name under data/raw/<indicator_id>/, e.g. "response.csv"
    request: str  # URL or plain description of what was requested
    publisher_release_date: str | None = None


class Adapter:
    """Base class for a publisher adapter."""

    name: str = ""

    def fetch(self, d: IndicatorDefinition) -> Fetched:  # network
        raise NotImplementedError

    def parse(
        self, d: IndicatorDefinition, raw: bytes, geographies: dict[str, Geography]
    ) -> list[Observation]:  # offline
        raise NotImplementedError


ADAPTERS: dict[str, Adapter] = {}


def register(cls: type[Adapter]) -> type[Adapter]:
    if not cls.name:
        raise ValueError(f"{cls.__name__} needs a name")
    ADAPTERS[cls.name] = cls()
    return cls


def geo_lookup(geographies: dict[str, Geography], scheme: str) -> dict[str, str]:
    """Map a provider code scheme (e.g. 'iso3') to canonical geography IDs."""
    return {g.codes[scheme]: g.id for g in geographies.values() if scheme in g.codes}
