"""Load the project's config, registry and published data from a root directory.

Every path is relative to `root`, so tests can point the same code at
`tests/fixtures/` and the refresh can point it at a staging copy.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .schema import (
    CheckRecord,
    Geography,
    IndicatorDefinition,
    ManifestEntry,
    Observation,
    PeerGroup,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OBS_COLUMNS = ["indicator_id", "geography_id", "period", "frequency", "value", "status"]


@dataclass
class Project:
    root: Path
    config_root: Path | None = None  # defaults to root
    geographies: dict[str, Geography] = field(default_factory=dict)
    peer_groups: dict[str, PeerGroup] = field(default_factory=dict)
    indicators: dict[str, IndicatorDefinition] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path = REPO_ROOT, config_root: Path | None = None) -> Project:
        p = cls(root=Path(root), config_root=Path(config_root) if config_root else None)
        cfg = p.config_root or p.root
        geo = yaml.safe_load((cfg / "config/geographies.yml").read_text())
        p.geographies = {g["id"]: Geography(**g) for g in geo["geographies"]}
        peers = yaml.safe_load((cfg / "config/peers.yml").read_text())
        p.peer_groups = {k: PeerGroup(**v) for k, v in peers["groups"].items()}
        for f in sorted((p.root / "indicators").glob("*.yml")):
            d = IndicatorDefinition(**yaml.safe_load(f.read_text()))
            if d.id != f.stem:
                raise ValueError(f"{f.name}: id {d.id!r} does not match file name")
            p.indicators[d.id] = d
        return p

    # --- paths --------------------------------------------------------------

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    def observations_path(self, indicator_id: str) -> Path:
        return self.data_dir / "observations" / f"{indicator_id}.csv"

    # --- data ---------------------------------------------------------------

    def read_observations(self, indicator_id: str) -> list[Observation]:
        path = self.observations_path(indicator_id)
        if not path.exists():
            return []
        with path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != OBS_COLUMNS:
                raise ValueError(f"{path.name}: columns must be {OBS_COLUMNS}")
            return [
                Observation(**{**row, "value": float(row["value"]) if row["value"] != "" else None})
                for row in reader
            ]

    def read_manifest(self) -> list[ManifestEntry]:
        path = self.data_dir / "manifest.json"
        if not path.exists():
            return []
        return [ManifestEntry(**e) for e in json.loads(path.read_text())]

    def read_checks(self) -> dict[str, CheckRecord]:
        path = self.data_dir / "checks.json"
        if not path.exists():
            return {}
        return {k: CheckRecord(**v) for k, v in json.loads(path.read_text()).items()}

    def published(self) -> list[IndicatorDefinition]:
        return [d for d in self.indicators.values() if d.status == "published"]


def write_observations(path: Path, rows: list[Observation]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda o: (o.geography_id, o.period))
    with path.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(OBS_COLUMNS)
        for o in rows:
            value = "" if o.value is None else repr(o.value)
            w.writerow([o.indicator_id, o.geography_id, o.period, o.frequency, value, o.status])
