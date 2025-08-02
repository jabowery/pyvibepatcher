#!/usr/bin/env python3
"""
Script to apply source code and filesystem modifications with git rollback support
Usage: python modify.py
"""
import os
import shutil
import re
import logging
import subprocess
import datetime
import json
import libcst as cst
from typing import Optional, List

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

class GitRollbackManager:
    """Manages git-based rollback operations for code modifications"""
    
    def __init__(self, rollback_file='.modification_rollback.json'):
        self.rollback_file = rollback_file
        self.rollback_data = {}
    
    def is_git_repo(self):
        """Check if current directory is a git repository"""
        try:
            subprocess.run(['git', 'rev-parse', '--git-dir'], 
                         check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_current_commit(self):
        """Get current commit hash"""
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  check=True, capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    
    def get_current_branch(self):
        """Get current branch name"""
        try:
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                  check=True, capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    
    def has_uncommitted_changes(self):
        """Check if there are uncommitted changes"""
        try:
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  check=True, capture_output=True, text=True)
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return False
    
    def create_rollback_point(self, message=None, force_commit=False):
        """
        Create a git commit as a rollback point
        
        Args:
            message: Commit message (auto-generated if None)
            force_commit: If True, commit even if no changes exist
            
        Returns:
            dict: Rollback information including commit hash, branch, timestamp
        """
        if not self.is_git_repo():
            logging.warning("Not in a git repository - rollback not available")
            return None
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if message is None:
            message = f"Pre-modification snapshot {timestamp}"
        
        current_commit = self.get_current_commit()
        current_branch = self.get_current_branch()
        
        try:
            # Add all changes to staging
            subprocess.run(['git', 'add', '-A'], check=True, capture_output=True)
            
            # Check if there's anything to commit
            if not self.has_uncommitted_changes() and not force_commit:
                logging.info("No changes to commit, using current HEAD as rollback point")
                rollback_info = {
                    'commit_hash': current_commit,
                    'branch': current_branch,
                    'timestamp': timestamp,
                    'message': f"Rollback point (no changes): {message}",
                    'was_clean': True
                }
            else:
                # Create commit
                subprocess.run(['git', 'commit', '-m', message], 
                             check=True, capture_output=True)
                new_commit = self.get_current_commit()
                
                rollback_info = {
                    'commit_hash': new_commit,
                    'branch': current_branch,
                    'timestamp': timestamp,
                    'message': message,
                    'was_clean': False
                }
            
            # Save rollback info to file
            self.rollback_data = rollback_info
            self._save_rollback_data()
            
            logging.info(f"Created rollback point: {rollback_info['commit_hash']}")
            return rollback_info
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Could not create git commit: {e}")
            return None
    
    def soft_rollback(self, commit_hash=None):
        """
        Soft rollback - reset to commit but keep changes staged
        Useful for temporary rollbacks where you might want to re-apply changes
        """
        if not commit_hash:
            commit_hash = self.rollback_data.get('commit_hash')
        
        if not commit_hash:
            logging.error("No rollback commit specified")
            return False
        
        try:
            subprocess.run(['git', 'reset', '--soft', commit_hash], 
                         check=True, capture_output=True)
            logging.info(f"Soft rollback to {commit_hash} - changes staged")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Soft rollback failed: {e}")
            return False
    
    def hard_rollback(self, commit_hash=None):
        """
        Hard rollback - completely reset to commit, discarding all changes
        Use when temporarily testing modifications
        """
        if not commit_hash:
            commit_hash = self.rollback_data.get('commit_hash')
        
        if not commit_hash:
            logging.error("No rollback commit specified")
            return False
        
        try:
            subprocess.run(['git', 'reset', '--hard', commit_hash], 
                         check=True, capture_output=True)
            logging.info(f"Hard rollback to {commit_hash} - all changes discarded")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Hard rollback failed: {e}")
            return False
    
    def abandon_to_commit(self, commit_hash=None, new_branch_name=None):
        """
        Abandon current development line and make the rollback commit the new HEAD
        This creates a new branch from the rollback point and switches to it
        
        Args:
            commit_hash: Commit to abandon back to (uses stored rollback if None)
            new_branch_name: Name for new branch (auto-generated if None)
            
        Returns:
            str: Name of the new branch created, or None if failed
        """
        if not commit_hash:
            commit_hash = self.rollback_data.get('commit_hash')
        
        if not commit_hash:
            logging.error("No rollback commit specified")
            return None
        
        current_branch = self.get_current_branch()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if new_branch_name is None:
            new_branch_name = f"abandoned-from-{current_branch}-{timestamp}"
        
        try:
            # Create new branch from the rollback commit
            subprocess.run(['git', 'checkout', '-b', new_branch_name, commit_hash], 
                         check=True, capture_output=True)
            
            logging.info(f"Abandoned development line - new branch '{new_branch_name}' created from {commit_hash}")
            logging.info(f"Previous branch '{current_branch}' still exists if you need to reference it")
            
            # Update rollback data for new branch
            self.rollback_data['abandoned_from_branch'] = current_branch
            self.rollback_data['new_branch'] = new_branch_name
            self._save_rollback_data()
            
            return new_branch_name
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to abandon to commit: {e}")
            return None
    
    def force_reset_branch_to_commit(self, commit_hash=None, branch_name=None):
        """
        Force reset current or specified branch to rollback commit
        WARNING: This destroys the commit history after the rollback point
        
        Args:
            commit_hash: Commit to reset to (uses stored rollback if None)
            branch_name: Branch to reset (current branch if None)
        """
        if not commit_hash:
            commit_hash = self.rollback_data.get('commit_hash')
        
        if not commit_hash:
            logging.error("No rollback commit specified")
            return False
        
        current_branch = self.get_current_branch()
        target_branch = branch_name or current_branch
        
        try:
            # Switch to target branch if not already on it
            if current_branch != target_branch:
                subprocess.run(['git', 'checkout', target_branch], 
                             check=True, capture_output=True)
            
            # Force reset to the commit
            subprocess.run(['git', 'reset', '--hard', commit_hash], 
                         check=True, capture_output=True)
            
            logging.warning(f"DESTRUCTIVE: Reset branch '{target_branch}' to {commit_hash}")
            logging.warning("All commits after the rollback point have been permanently lost")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Force reset failed: {e}")
            return False
    
    def show_rollback_options(self):
        """Display available rollback options to user"""
        if not self.rollback_data:
            self._load_rollback_data()
        
        if not self.rollback_data:
            logging.info("No rollback data available")
            return
        
        commit_hash = self.rollback_data['commit_hash']
        branch = self.rollback_data.get('branch', 'unknown')
        timestamp = self.rollback_data.get('timestamp', 'unknown')
        
        print("\n=== ROLLBACK OPTIONS ===")
        print(f"Rollback commit: {commit_hash}")
        print(f"Original branch: {branch}")
        print(f"Created at: {timestamp}")
        print("\nAvailable actions:")
        print("1. Soft rollback - git reset --soft (keeps changes staged)")
        print("2. Hard rollback - git reset --hard (discards all changes)")
        print("3. Abandon current line - creates new branch from rollback point")
        print("4. Force reset branch - DESTRUCTIVE, permanently loses commits")
        print("\nManual commands:")
        print(f"  git reset --soft {commit_hash}")
        print(f"  git reset --hard {commit_hash}")
        print(f"  git checkout -b new-branch-name {commit_hash}")
    
    def _save_rollback_data(self):
        """Save rollback data to file"""
        try:
            with open(self.rollback_file, 'w') as f:
                json.dump(self.rollback_data, f, indent=2)
        except Exception as e:
            logging.warning(f"Could not save rollback data: {e}")
    
    def _load_rollback_data(self):
        """Load rollback data from file"""
        try:
            if os.path.exists(self.rollback_file):
                with open(self.rollback_file, 'r') as f:
                    self.rollback_data = json.load(f)
        except Exception as e:
            logging.warning(f"Could not load rollback data: {e}")
            self.rollback_data = {}

# pip install libcst

def parse_lexical_chain(target_path: str) -> tuple[str, List[str]]:
    """
    Parse a lexical chain like 'ClassName.method_name' or 'outer_func.inner_func'
    
    Args:
        target_path: Dot-separated path like 'ClassName.method_name'
        
    Returns:
        tuple: (final_target_name, list_of_container_names)
    """
    parts = target_path.split('.')
    if len(parts) == 1:
        return parts[0], []
    
    return parts[-1], parts[:-1]

class ReplaceDefOrClass(cst.CSTTransformer):
    def __init__(self, target_name: str, new_code: str,
                 kind: Optional[str] = None, lexical_chain: Optional[List[str]] = None):
        """
        target_name: name of function or class to replace.
        new_code: the full new def/class code (including decorators if any).
        kind: "def" or "class" (if None, inferred from new_code).
        lexical_chain: list of container names to traverse (e.g., ['ClassName'] for ClassName.method_name)
        """
        mod = cst.parse_module(new_code)
        if len(mod.body) != 1:
            raise ValueError("new_code must contain exactly one top-level def/class.")
        self.replacement = mod.body[0]
        if kind is None:
            if isinstance(self.replacement, cst.FunctionDef):
                kind = "def"
            elif isinstance(self.replacement, cst.ClassDef):
                kind = "class"
            else:
                raise ValueError("new_code must be a function or class definition.")
        self.kind = kind
        self.target_name = target_name
        self.lexical_chain = lexical_chain or []
        self.context_stack: List[str] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self.context_stack.append(node.name.value)
        return True

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self.context_stack.append(node.name.value)
        return True

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.BaseStatement:
        current_name = self.context_stack.pop()
        
        # Replace class definition if it matches
        if (self.kind == "class" 
            and original_node.name.value == self.target_name
            and self._matches_lexical_chain()):
            return self.replacement.with_changes(leading_lines=original_node.leading_lines)
        return updated_node

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.BaseStatement:
        current_name = self.context_stack.pop()
        
        # Replace function definition if it matches
        if (self.kind == "def"
            and original_node.name.value == self.target_name
            and self._matches_lexical_chain()):
            return self.replacement.with_changes(leading_lines=original_node.leading_lines)
        return updated_node

    def _matches_lexical_chain(self) -> bool:
        """Check if current context matches the required lexical chain"""
        if not self.lexical_chain:
            return True
        
        if len(self.context_stack) < len(self.lexical_chain):
            return False
        
        # Check if the chain matches from the end
        return self.context_stack[-len(self.lexical_chain):] == self.lexical_chain

def replace_block(content: str,
                  new_code: str,
                  target_name: Optional[str] = None,
                  kind: Optional[str] = None,
                  lexical_chain: Optional[List[str]] = None) -> str:
    """
    Replace a function or class in `content` with `new_code` using LibCST.
    - If `target_name`/`kind` are omitted, they are inferred from `new_code`.
    - lexical_chain specifies the containment hierarchy (e.g., ['ClassName'] for a method)
    """
    # Infer target_name/kind from new_code if not provided
    mod = cst.parse_module(new_code)
    if len(mod.body) != 1:
        raise ValueError("new_code must contain exactly one top-level def/class.")
    node = mod.body[0]
    inferred_kind = "def" if isinstance(node, cst.FunctionDef) else "class" if isinstance(node, cst.ClassDef) else None
    if inferred_kind is None:
        raise ValueError("new_code must be a function or class definition.")
    inferred_name = node.name.value

    kind = kind or inferred_kind
    target_name = target_name or inferred_name

    module = cst.parse_module(content)
    new_module = module.visit(ReplaceDefOrClass(target_name, new_code, kind=kind, lexical_chain=lexical_chain))
    return new_module.code

def replace_function_class(file_path, target_path, new_code):
    """
    Replace a function or class in a file with new code using lexical chain support
    
    Args:
        file_path: Path to the Python file
        target_path: Target path like 'function_name' or 'ClassName.method_name'
        new_code: New function/class code to replace with
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    target_name, lexical_chain = parse_lexical_chain(target_path)
    new_content = replace_block(content, new_code, target_name=target_name, lexical_chain=lexical_chain)

    with open(file_path, 'w') as f:
        f.write(new_content)
    
    logging.debug(f"Replaced {target_path} in {file_path}")

def search_replace_line(file_path, search_text, replacement_text):
    """Search for a line and replace it"""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    found = False
    for i, line in enumerate(lines):
        if search_text in line:
            lines[i] = replacement_text + '\n' if not replacement_text.endswith('\n') else replacement_text
            found = True
            break
    
    if not found:
        raise ValueError(f"Search text '{search_text}' not found in {file_path}")
    
    with open(file_path, 'w') as f:
        f.writelines(lines)
    
    logging.debug(f"Replaced line containing '{search_text}' in {file_path}")

def move_file(src, dst):
    """Move/rename file or directory"""
    shutil.move(src, dst)
    logging.debug(f"Moved {src} to {dst}")

def make_directory(path):
    """Create directory"""
    os.makedirs(path, exist_ok=True)
    logging.debug(f"Created directory {path}")

def remove_file(path, recursive=False):
    """Remove file or directory"""
    if recursive and os.path.isdir(path):
        shutil.rmtree(path)
        logging.debug(f"Removed directory {path} recursively")
    elif os.path.isfile(path):
        os.remove(path)
        logging.debug(f"Removed file {path}")
    elif os.path.isdir(path):
        os.rmdir(path)
        logging.debug(f"Removed empty directory {path}")
    else:
        raise FileNotFoundError(f"Path {path} does not exist")

def apply_modification_set(modifications, auto_rollback_on_failure=True):
    """
    Apply a set of modifications with rollback support
    
    Args:
        modifications: List of (function, args, kwargs) tuples
        auto_rollback_on_failure: If True, automatically rollback on any failure
        
    Returns:
        GitRollbackManager: Manager instance for manual rollback operations
    """
    rollback_manager = GitRollbackManager()
    
    # Create rollback point
    rollback_info = rollback_manager.create_rollback_point("Before LLM modifications")
    
    if not rollback_info:
        logging.warning("Proceeding without git rollback capability")
    
    try:
        # Apply all modifications
        for func, args, kwargs in modifications:
            func(*args, **kwargs)
        
        logging.info("All modifications completed successfully")
        
        if rollback_info:
            rollback_manager.show_rollback_options()
        
        return rollback_manager
        
    except Exception as e:
        logging.error(f"Modifications failed: {e}")
        
        if auto_rollback_on_failure and rollback_info:
            logging.info("Auto-rolling back due to failure...")
            rollback_manager.hard_rollback()
        elif rollback_info:
            logging.info("Manual rollback available - use returned manager")
            rollback_manager.show_rollback_options()
        
        raise

# Interactive rollback interface
def interactive_rollback():
    """Interactive interface for rollback operations"""
    manager = GitRollbackManager()
    manager._load_rollback_data()
    
    if not manager.rollback_data:
        print("No rollback data found")
        return
    
    manager.show_rollback_options()
    
    while True:
        choice = input("\nEnter choice (1-4, or 'q' to quit): ").strip()
        
        if choice == 'q':
            break
        elif choice == '1':
            manager.soft_rollback()
            break
        elif choice == '2':
            manager.hard_rollback()
            break
        elif choice == '3':
            branch_name = input("New branch name (or press Enter for auto): ").strip()
            if not branch_name:
                branch_name = None
            manager.abandon_to_commit(new_branch_name=branch_name)
            break
        elif choice == '4':
            confirm = input("WARNING: This will permanently lose commits! Type 'yes' to confirm: ")
            if confirm.lower() == 'yes':
                manager.force_reset_branch_to_commit()
                break
        else:
            print("Invalid choice")

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        interactive_rollback()
