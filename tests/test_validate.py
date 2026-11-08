from ukdash.project import Project
from ukdash.validate import validate


def test_repository_data_is_valid():
    assert validate(Project.load()) == []


def test_fixture_is_valid(fixture_project):
    assert validate(fixture_project) == []


def test_duplicate_observation_is_rejected(fixture_root):
    csv = fixture_root / "data/observations/test_unemployment.csv"
    lines = csv.read_text().splitlines()
    csv.write_text("\n".join(lines + [lines[1]]) + "\n")
    errors = validate(Project.load(fixture_root))
    assert any("duplicate" in e for e in errors)


def test_checksum_mismatch_is_rejected(fixture_root):
    raw = fixture_root / "data/raw/test_unemployment/response.csv"
    raw.write_bytes(raw.read_bytes() + b"tampered")
    errors = validate(Project.load(fixture_root))
    assert any("checksum" in e for e in errors)


def test_unknown_geography_is_rejected(fixture_root):
    csv = fixture_root / "data/observations/test_unemployment.csv"
    csv.write_text(csv.read_text().replace("iso:CAN", "iso:XYZ"))
    errors = validate(Project.load(fixture_root))
    assert any("unknown geography iso:XYZ" in e for e in errors)
