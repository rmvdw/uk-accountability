"""Offline validation of config, registry and published data. Never touches the network."""

from __future__ import annotations

import hashlib

from .project import Project


def sha256_file(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(project: Project) -> list[str]:
    """Return a list of human-readable problems. Empty means valid."""
    errors: list[str] = []
    geos = project.geographies

    for name, group in project.peer_groups.items():
        for m in group.members:
            if m not in geos:
                errors.append(f"peer group {name}: unknown geography {m}")

    manifest = project.read_manifest()
    manifest_ids = {e.indicator_id for e in manifest}

    for d in project.indicators.values():
        where = f"indicator {d.id}"
        group = project.peer_groups.get(d.peers.group)
        if group is None:
            errors.append(f"{where}: unknown peer group {d.peers.group!r}")
        else:
            for g in d.peers.exclusions:
                if g not in group.members:
                    errors.append(f"{where}: excludes {g}, which is not in {d.peers.group}")
        for g, reason in d.peers.exclusions.items():
            if not reason.strip():
                errors.append(f"{where}: exclusion of {g} has no reason")

        try:
            rows = project.read_observations(d.id)
        except Exception as exc:  # noqa: BLE001 - report every parse failure as a problem
            errors.append(f"{where}: cannot read observations: {exc}")
            continue

        if d.status == "published":
            if not rows:
                errors.append(f"{where}: published but has no observations")
            if d.id not in manifest_ids:
                errors.append(f"{where}: published but has no provenance in manifest.json")

        seen: set[tuple[str, str, str]] = set()
        for o in rows:
            if o.indicator_id != d.id:
                errors.append(f"{where}: row has indicator_id {o.indicator_id}")
            if o.frequency != d.frequency:
                errors.append(
                    f"{where}: {o.period} has frequency {o.frequency}, expected {d.frequency}"
                )
            if o.geography_id not in geos:
                errors.append(f"{where}: unknown geography {o.geography_id}")
            if o.key in seen:
                errors.append(f"{where}: duplicate observation {o.key}")
            seen.add(o.key)

    for e in manifest:
        path = project.root / e.path
        if e.indicator_id not in project.indicators:
            errors.append(f"manifest: unknown indicator {e.indicator_id}")
        if not path.exists():
            errors.append(f"manifest: missing raw file {e.path}")
        elif sha256_file(path) != e.sha256:
            errors.append(f"manifest: checksum mismatch for {e.path}")

    for ind_id in project.read_checks():
        if ind_id not in project.indicators:
            errors.append(f"checks.json: unknown indicator {ind_id}")

    return errors
