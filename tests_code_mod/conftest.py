import os
import sys
import subprocess
import tempfile
import shutil
import contextlib
from pathlib import Path

import pytest

# Ensure the uploaded modules are importable
PROJECT_ROOT = Path("/mnt/data")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

@contextlib.contextmanager
def chdir(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)

@pytest.fixture()
def tmp_git_repo(tmp_path, monkeypatch):
    """Initialize a temporary git repo with configured identity and an initial commit.
    Yields: (repo_path: Path, chdir_ctx: contextmanager)
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "README.md").write_text("# temp\n")
    subprocess.check_call(["git", "add", "README.md"], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "init"], cwd=repo)

    yield repo, chdir
