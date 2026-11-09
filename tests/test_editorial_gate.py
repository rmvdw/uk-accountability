import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gate", ROOT / ".github/scripts/editorial_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_patterns_come_from_codeowners():
    pats = gate.owned_patterns((ROOT / ".github/CODEOWNERS").read_text())
    assert "indicators/" in pats and "docs/decisions.md" in pats


def test_ownership_matching():
    pats = ["indicators/", "docs/decisions.md"]
    assert gate.is_owned("indicators/unemployment_rate.yml", pats)
    assert gate.is_owned("docs/decisions.md", pats)
    assert not gate.is_owned("docs/decisions.md.bak", pats)
    assert not gate.is_owned("src/ukdash/build.py", pats)


def run(tmp_path, monkeypatch, files, labels):
    monkeypatch.chdir(ROOT)
    c, lab = tmp_path / "c.txt", tmp_path / "l.txt"
    c.write_text("\n".join(files))
    lab.write_text("\n".join(labels))
    return gate.main(str(c), str(lab))


def test_gate(tmp_path, monkeypatch):
    assert run(tmp_path, monkeypatch, ["src/ukdash/build.py"], []) == 0
    assert run(tmp_path, monkeypatch, ["indicators/x.yml"], []) == 1
    assert run(tmp_path, monkeypatch, ["indicators/x.yml"], ["review"]) == 1
    assert run(tmp_path, monkeypatch, ["indicators/x.yml"], ["ross-approved"]) == 0
