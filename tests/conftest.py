import shutil
from pathlib import Path

import pytest

from ukdash.project import REPO_ROOT, Project

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_project() -> Project:
    return Project.load(FIXTURES, config_root=REPO_ROOT)


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    """A writable copy of the fixture project with the real config, for refresh tests."""
    root = tmp_path / "proj"
    shutil.copytree(FIXTURES, root)
    shutil.copytree(REPO_ROOT / "config", root / "config")
    return root
