from pathlib import Path
import subprocess

from code_mod_defs import GitRollbackManager, create_file

def test_create_rollback_points_no_changes(tmp_git_repo):
    repo, chdir = tmp_git_repo
    with chdir(repo):
        mgr = GitRollbackManager()
        info = mgr.create_rollback_point("snapshot")
        assert "commit_hash" in info and info["was_clean"] is True

def test_commit_tracked_files_and_hard_rollback(tmp_git_repo):
    repo, chdir = tmp_git_repo
    with chdir(repo):
        mgr = GitRollbackManager()
        mgr.track_file("a.txt")
        create_file._rollback_manager = mgr  # simulate apply_modification_set attaching tracking
        create_file("a.txt", "hello", make_executable=False)

        # Create rollback point commit that includes a.txt="hello"
        info = mgr.create_rollback_point("after create", force_commit=True)
        commit_after = mgr.get_current_commit()
        assert commit_after == info["commit_hash"]

        # Dirty the working tree
        Path("a.txt").write_text("changed")

        # Roll back to the rollback point commit (not HEAD~1)
        ok = mgr.hard_rollback(info["commit_hash"])
        assert ok
        assert Path("a.txt").read_text() == "hello"

