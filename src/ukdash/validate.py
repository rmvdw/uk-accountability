"""Offline validation of config, registry and published data. Never touches the network."""

from __future__ import annotations

import hashlib

from .project import Project


def sha256_file(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(project: Project, render_candidates: bool = True) -> list[str]:
    """Return a list of human-readable problems. Empty means valid.

    render_candidates also renders each briefing's candidate from current data. A
    production build turns it off: it shows only frozen editions, so a candidate that
    no longer renders must not block it (check and previews still report it).
    """
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
        if d.peers is not None:
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
            if o.breakdown != "total" and o.breakdown not in d.breakdowns:
                errors.append(f"{where}: undeclared breakdown {o.breakdown!r}")
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

    errors.extend(validate_briefings(project, render_candidates))

    for ind_id in project.read_checks():
        if ind_id not in project.indicators:
            errors.append(f"checks.json: unknown indicator {ind_id}")

    return errors


def validate_briefings(project: Project, render_candidates: bool = True) -> list[str]:
    from . import briefing
    from .build import period_label

    errors: list[str] = []
    try:
        briefings = briefing.load_all(project.root)
    except ValueError as exc:
        return [f"briefing: {exc}"]
    for b in briefings.values():
        where = f"briefing {b.id}"
        unknown = [i for i in b.indicators if i not in project.indicators]
        if unknown:
            errors.append(f"{where}: unknown indicators {unknown}")
            continue
        if b.status == "published":
            try:
                briefing.load_edition(project.root, b)
                for ed in b.earlier_editions:
                    briefing.read_edition(project.root, b.id, ed)
            except (ValueError, FileNotFoundError) as exc:
                errors.append(f"{where}: {exc}")
            drafts = [i for i in b.indicators if project.indicators[i].status != "published"]
            if drafts:
                errors.append(f"{where}: published briefing uses draft indicators {drafts}")
        if render_candidates and all(project.read_observations(i) for i in b.indicators):
            try:
                briefing.render_candidate(project, b, period_label)
            except Exception as exc:  # noqa: BLE001 - report any template or data error
                errors.append(f"{where}: cannot render: {exc}")
    return errors
