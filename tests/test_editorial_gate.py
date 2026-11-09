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


def test_rename_of_protected_file_is_caught(tmp_path, monkeypatch):
    # The workflow passes both filename and previous_filename for renames.
    renamed = ["docs/archived-decisions.md", "docs/decisions.md"]
    assert run(tmp_path, monkeypatch, renamed, []) == 1
    assert run(tmp_path, monkeypatch, renamed, ["ross-approved"]) == 0


def test_workflow_collects_previous_filename():
    wf = (ROOT / ".github/workflows/editorial-gate.yml").read_text()
    assert "previous_filename" in wf


def test_templates_and_briefings_are_ross_owned():
    pats = gate.owned_patterns((ROOT / ".github/CODEOWNERS").read_text())
    assert gate.is_owned("templates/index.html", pats)
    assert gate.is_owned("templates/indicator.html", pats)
    assert gate.is_owned("briefings/immigration.md", pats)


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def run_dirs(tmp_path, monkeypatch, files, labels, base, head):
    monkeypatch.chdir(ROOT)
    c, lab = tmp_path / "c.txt", tmp_path / "l.txt"
    c.write_text("\n".join(files))
    lab.write_text("\n".join(labels))
    return gate.main(str(c), str(lab), ".github/CODEOWNERS", str(base), str(head))


def test_draft_indicators_need_no_approval(tmp_path, monkeypatch):
    base, head = tmp_path / "base", tmp_path / "head"
    f = "indicators/new_thing.yml"
    write(head, f, "id: new_thing\nstatus: draft\n")  # new draft
    assert run_dirs(tmp_path, monkeypatch, [f], [], base, head) == 0
    write(base, f, "id: new_thing\nstatus: draft\n")  # edited draft
    assert run_dirs(tmp_path, monkeypatch, [f], [], base, head) == 0


def test_publishing_or_changing_published_needs_approval(tmp_path, monkeypatch):
    base, head = tmp_path / "base", tmp_path / "head"
    f = "indicators/x.yml"
    write(base, f, "status: draft\n")
    write(head, f, "status: published\n")  # publishing
    assert run_dirs(tmp_path, monkeypatch, [f], [], base, head) == 1
    write(base, f, "status: published\n")
    write(head, f, "status: draft\n")  # unpublishing a live indicator
    assert run_dirs(tmp_path, monkeypatch, [f], [], base, head) == 1
    (head / f).unlink()  # deleting a published one
    assert run_dirs(tmp_path, monkeypatch, [f], [], base, head) == 1
    assert run_dirs(tmp_path, monkeypatch, [f], ["ross-approved"], base, head) == 0


def test_unreadable_status_and_other_paths_still_gated(tmp_path, monkeypatch):
    base, head = tmp_path / "base", tmp_path / "head"
    write(head, "indicators/y.yml", "id: y\n")  # no status line
    assert run_dirs(tmp_path, monkeypatch, ["indicators/y.yml"], [], base, head) == 1
    write(head, "templates/index.html", "status: draft\n")  # templates are never exempt
    assert run_dirs(tmp_path, monkeypatch, ["templates/index.html"], [], base, head) == 1


def test_mixed_draft_and_owned_change_still_needs_approval(tmp_path, monkeypatch):
    base, head = tmp_path / "base", tmp_path / "head"
    write(head, "indicators/z.yml", "status: draft\n")
    files = ["indicators/z.yml", "docs/decisions.md"]
    assert run_dirs(tmp_path, monkeypatch, files, [], base, head) == 1


def test_duplicate_status_lines_fail_closed(tmp_path, monkeypatch):
    base, head = tmp_path / "base", tmp_path / "head"
    write(head, "indicators/d.yml", "id: d\nstatus: draft\nstatus: published\n")
    assert run_dirs(tmp_path, monkeypatch, ["indicators/d.yml"], [], base, head) == 1


def test_briefing_status_comes_from_front_matter_only(tmp_path, monkeypatch):
    base, head = tmp_path / "base", tmp_path / "head"
    f = "briefings/immigration.md"
    write(head, f, "---\ntitle: X\nstatus: draft\n---\n\nBody text.\n")
    assert run_dirs(tmp_path, monkeypatch, [f], [], base, head) == 0
    write(head, f, "---\ntitle: X\nstatus: draft\n---\n\nstatus: published\n")  # body ignored
    assert run_dirs(tmp_path, monkeypatch, [f], [], base, head) == 0
    write(head, f, "No front matter\nstatus: draft\n")
    assert run_dirs(tmp_path, monkeypatch, [f], [], base, head) == 1
