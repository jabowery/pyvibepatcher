from pathlib import Path
import subprocess
import pytest

from code_mod_defs import apply_modification_set, create_file, move_file, remove_file, modification_description

def test_apply_modification_set_success(tmp_git_repo):
    repo, chdir = tmp_git_repo
    with chdir(repo):
        Path("dst").mkdir(parents=True, exist_ok=True)
        mods = [
            (modification_description, ("create and move files",), {}),
            (create_file, ("src/a.txt", "A",), {"make_executable": False}),
            (create_file, ("src/b.txt", "B",), {"make_executable": False}),
            (move_file, ("src/a.txt", "dst/a.txt"), {}),
            (remove_file, ("src", True), {}),
        ]
        mgr = apply_modification_set(mods, auto_rollback_on_failure=True)
        assert Path("dst/a.txt").exists()
        assert not Path("src").exists()
        assert mgr.rollback_data.get("commit_hash")

def test_apply_modification_set_failure_rolls_back(tmp_git_repo):
    repo, chdir = tmp_git_repo
    with chdir(repo):
        initial_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()

        mods = [
            (create_file, ("x.txt", "X",), {"make_executable": False}),
            (move_file, ("does_not_exist.txt", "y.txt"), {}),
        ]
        with pytest.raises(Exception):
            apply_modification_set(mods, auto_rollback_on_failure=True)

        # HEAD should remain the same (no new commit was added)
        head_after = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        assert head_after == initial_commit

        # The file may exist untracked; ensure it was NOT staged/committed
        tracked = subprocess.check_output(["git", "ls-files", "x.txt"], text=True).strip()
        assert tracked == ""
