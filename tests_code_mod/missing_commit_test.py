import subprocess
import pytest
from pathlib import Path

from code_mod_defs import apply_modification_set, create_file, modification_description, declare

def test_modifications_create_new_commit(tmp_git_repo):
    """This test should have caught that modifications weren't being committed."""
    repo, chdir = tmp_git_repo
    with chdir(repo):
        # Get initial commit
        initial_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        
        # Apply modifications
        mods = [
            (modification_description, ("Add test file",), {}),
            (create_file, ("test.txt", "Hello World",), {"make_executable": False}),
        ]
        
        # This should create a new commit (but currently doesn't!)
        manager = apply_modification_set(mods, auto_commit=True, commit_message="Add test file")
        
        # Get commit after modifications
        final_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        
        # CRITICAL: This should fail with current code because no commit was made
        assert final_commit != initial_commit, "Expected new commit to be created after modifications"
        
        # Verify the file was actually committed
        committed_files = subprocess.check_output(
            ["git", "ls-tree", "--name-only", "HEAD"], text=True
        ).strip().split('\n')
        assert "test.txt" in committed_files, "Modified file should be in the new commit"
        
        # Verify commit message
        commit_msg = subprocess.check_output(
            ["git", "log", "-1", "--pretty=format:%s"], text=True
        ).strip()
        assert commit_msg == "Add test file", f"Expected commit message 'Add test file', got '{commit_msg}'"

def test_rollback_points_are_different_after_commits(tmp_git_repo):
    """Test that successive modification runs create different rollback points."""
    repo, chdir = tmp_git_repo
    with chdir(repo):
        # First modification
        mods1 = [
            (modification_description, ("First change",), {}),
            (create_file, ("file1.txt", "Content 1",), {"make_executable": False}),
        ]
        manager1 = apply_modification_set(mods1, auto_commit=True, commit_message="First change")
        rollback1 = manager1.rollback_data.get("commit_hash")
        
        # Second modification (should start from new HEAD)
        mods2 = [
            (modification_description, ("Second change",), {}),
            (create_file, ("file2.txt", "Content 2",), {"make_executable": False}),
        ]
        manager2 = apply_modification_set(mods2, auto_commit=True, commit_message="Second change")
        rollback2 = manager2.rollback_data.get("commit_hash")
        
        # Rollback points should be different because HEAD changed between runs
        assert rollback1 != rollback2, "Rollback points should be different after commits"
        
        # Current HEAD should be different from both rollback points
        current_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        assert current_head != rollback1, "Current HEAD should be beyond first rollback point"
        assert current_head != rollback2, "Current HEAD should be beyond second rollback point"

def test_main_script_behavior_integration(tmp_git_repo, tmp_path):
    """Integration test that simulates the actual script usage."""
    repo, chdir = tmp_git_repo
    with chdir(repo):
        # Create a modification file like the user would
        mod_file = tmp_path / "test_mods.txt"
        mod_file.write_text("""
MMM modification_description MMM
Integration test modification
@@@@@@
MMM create_file MMM
integration_test.py
@@@@@@
def test_function():
    return "test"
@@@@@@
False
""".strip())
        
        # Get initial state
        initial_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        
        # Simulate what the main script does
        from modify_code import parse_modification_file
        modifications = parse_modification_file(str(mod_file))
        
        # Extract description (like the fixed main() does)
        description = "Code modifications"
        if modifications and modifications[0][0].__name__ == 'modification_description':
            description = modifications[0][1][0]
        
        # Apply with auto_commit=True (like the fixed script should do)
        manager = apply_modification_set(modifications, auto_commit=True, commit_message=description)
        
        # Verify new commit was created
        final_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        
        assert final_commit != initial_commit, "Script should create new commit"
        assert Path("integration_test.py").exists(), "File should be created"
        
        # Verify file is committed
        committed_files = subprocess.check_output(
            ["git", "ls-tree", "--name-only", "HEAD"], text=True
        ).strip().split('\n')
        assert "integration_test.py" in committed_files, "File should be committed"
