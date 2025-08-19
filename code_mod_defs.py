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

import libcst as cst
from typing import Tuple, List


# near other LibCST helpers
def _target_exists(source: str, target_name: str, chain: list[str]) -> bool:
    try:
        mod = cst.parse_module(source)
    except Exception:
        return False

    class _Finder(cst.CSTVisitor):
        def __init__(self):
            self.stack = []
            self.found = False
        def visit_ClassDef(self, node: cst.ClassDef) -> None:
            self.stack.append(node.name.value)
        def leave_ClassDef(self, node: cst.ClassDef) -> None:
            self.stack.pop()
        def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
            if node.name.value == target_name and (self.stack == chain or (not chain and not self.stack)):
                self.found = True
        def visit_SimpleStatementLine(self, node: cst.SimpleStatementLine) -> None:
            if len(node.body) == 1 and isinstance(node.body[0], cst.Assign):
                for t in node.body[0].targets:
                    if isinstance(t.target, cst.Name) and t.target.value == target_name and (self.stack == chain or (not chain and not self.stack)):
                        self.found = True

    f = _Finder()
    mod.visit(f)
    return f.found


def _is_assignment_to_name(stmt: cst.CSTNode, name: str) -> bool:
    # Match: x = ...   (within a SimpleStatementLine)
    if not isinstance(stmt, cst.SimpleStatementLine):
        return False
    for small in stmt.body:
        if isinstance(small, cst.Assign):
            for t in small.targets:
                tgt = t.target
                if isinstance(tgt, cst.Name) and tgt.value == name:
                    return True
    return False


class _DeletionTransformer(cst.CSTTransformer):
    """
    Removes a declaration at the given lexical chain.
    - lexical_chain == []  => operate at module level
    - lexical_chain == ["A", "B"] => operate inside class A.B
    Deletes:
      * FunctionDef with matching name
      * Assign to matching name (top-level or inside class scope)
    """
    def __init__(self, target_name: str, lexical_chain: List[str]):
        self.target_name = target_name
        self.chain = lexical_chain
        self.class_stack: List[str] = []
        self.removed = False

    # Track the current class stack
    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.class_stack.append(node.name.value)

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.CSTNode:
        # If we are exactly inside the desired class chain, filter this class body
        if self.class_stack == self.chain:
            new_body = []
            for stmt in updated_node.body.body:
                # Remove function with matching name
                if isinstance(stmt, cst.FunctionDef) and stmt.name.value == self.target_name:
                    self.removed = True
                    continue
                # Remove assignment to matching name
                if _is_assignment_to_name(stmt, self.target_name):
                    self.removed = True
                    continue
                new_body.append(stmt)
            updated_node = updated_node.with_changes(body=updated_node.body.with_changes(body=new_body))
        # Pop class stack on exit
        self.class_stack.pop()
        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.CSTNode:
        # Only act at module level when no class chain was requested
        if len(self.chain) == 0:
            new_body = []
            for stmt in updated_node.body:
                if isinstance(stmt, cst.FunctionDef) and stmt.name.value == self.target_name:
                    self.removed = True
                    continue
                if _is_assignment_to_name(stmt, self.target_name):
                    self.removed = True
                    continue
                # We do NOT remove classes at module level by name here; deletion of a class
                # itself can be supported similarly if needed.
                new_body.append(stmt)
            updated_node = updated_node.with_changes(body=new_body)
        return updated_node


def remove_block(source: str, target_name: str, lexical_chain: List[str]) -> Tuple[str, bool]:
    """
    Remove a function/method/assignment designated by (lexical_chain, target_name).
    Returns: (new_source, removed_bool)
    """
    try:
        mod = cst.parse_module(source)
    except Exception:
        # If parsing fails, do nothing
        return source, False
    tr = _DeletionTransformer(target_name, lexical_chain)
    new_mod = mod.visit(tr)
    return new_mod.code, tr.removed


class InsertIntoContainer(cst.CSTTransformer):
    """Insert a node into a specific container in the AST"""
    
    def __init__(self, node_to_insert: cst.BaseStatement, lexical_chain: List[str]):
        self.node_to_insert = node_to_insert
        self.lexical_chain = lexical_chain
        self.context_stack: List[str] = []
        self.inserted = False

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self.context_stack.append(node.name.value)
        return True

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self.context_stack.append(node.name.value)
        return True

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.BaseStatement:
        try:
            if self._matches_insertion_point():
                # Insert the node into this class
                new_body = list(updated_node.body.body) + [self.node_to_insert]
                new_suite = updated_node.body.with_changes(body=new_body)
                self.inserted = True
                return updated_node.with_changes(body=new_suite)
            return updated_node
        finally:
            self.context_stack.pop()

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.BaseStatement:
        try:
            if self._matches_insertion_point():
                # Insert the node into this function
                new_body = list(updated_node.body.body) + [self.node_to_insert]
                new_suite = updated_node.body.with_changes(body=new_body)
                self.inserted = True
                return updated_node.with_changes(body=new_suite)
            return updated_node
        finally:
            self.context_stack.pop()

    def _matches_insertion_point(self) -> bool:
        """Check if current context matches where we want to insert"""
        return self.context_stack == self.lexical_chain

class GitRollbackManager:
    """Manages git-based rollback operations for code modifications"""
    
    def __init__(self, rollback_file='.modification_rollback.json'):
        self.rollback_file = rollback_file
        self.rollback_data = {}
        self.tracked_files = set()
        self.accumulated_message = ""
    
    def accumulate_message(self, message):
        """Accumulate message text for commit message"""
        if self.accumulated_message:
            self.accumulated_message += "\n" + message
        else:
            self.accumulated_message = message

    def get_accumulated_message(self):
        """Get and clear accumulated message"""
        message = self.accumulated_message
        self.accumulated_message = ""
        return message

    def has_staged_changes(self):
        """Check if there are staged changes ready to commit"""
        try:
            result = subprocess.run(['git', 'diff', '--cached', '--name-only'], 
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
            
        Raises:
            RuntimeError: If rollback point cannot be created
        """
        if not self.is_git_repo():
            raise RuntimeError("Not in a git repository - rollback required for file modifications")
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if message is None:
            message = f"Pre-modification snapshot {timestamp}"
        
        current_commit = self.get_current_commit()
        current_branch = self.get_current_branch()
        
        if not current_commit:
            raise RuntimeError("Failed to get current git commit hash")
        
        # Check git configuration
        try:
            subprocess.run(['git', 'config', 'user.name'], check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.email'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            raise RuntimeError("Git user.name and user.email must be configured")
        
        # Add only tracked files to staging
        if self.tracked_files:
            for file_path in self.tracked_files:
                if os.path.exists(file_path):
                    result = subprocess.run(['git', 'add', file_path], capture_output=True)
                    if result.returncode != 0:
                        raise RuntimeError(f"Failed to stage file {file_path}: {result.stderr.decode()}")
                else:
                    # File was deleted, add it for removal
                    result = subprocess.run(['git', 'add', file_path], capture_output=True)
                    if result.returncode != 0:
                        logging.warning(f"Failed to stage deleted file {file_path}: {result.stderr.decode()}")
        
        # Check if there are staged changes to commit
        has_staged = self.has_staged_changes()
        
        if not has_staged and not force_commit:
            logging.info("No staged changes, using current HEAD as rollback point")
            rollback_info = {
                'commit_hash': current_commit,
                'branch': current_branch,
                'timestamp': timestamp,
                'message': f"Rollback point (no changes): {message}",
                'was_clean': True
            }
        else:
            if not has_staged:
                # force_commit=True but no staged changes - create empty commit
                result = subprocess.run(['git', 'commit', '--allow-empty', '-m', message], capture_output=True)
            else:
                # Normal commit with staged changes
                result = subprocess.run(['git', 'commit', '-m', message], capture_output=True)
            
            if result.returncode != 0:
                stderr_msg = result.stderr.decode().strip()
                stdout_msg = result.stdout.decode().strip()
                error_details = f"stderr: {stderr_msg}, stdout: {stdout_msg}" if stderr_msg or stdout_msg else "no error details provided"
                raise RuntimeError(f"Failed to create git commit: {error_details}")
            
            new_commit = self.get_current_commit()
            if not new_commit:
                raise RuntimeError("Failed to get commit hash after successful commit")
            
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

    def track_file(self, file_path):
        """Track a file for inclusion in git commits"""
        self.tracked_files.add(file_path)
    
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

import libcst as cst
from typing import List, Optional

class ReplaceDeclaration(cst.CSTTransformer):
    """
    Replace a function/method/assignment designated by (lexical_chain, target_name).
    Supports:
      - Module-level def/assign
      - Method/assign inside a class chain like A.B (self.chain == ["A","B"])
    """
    def __init__(self, target_name: str, lexical_chain: List[str], new_code: str, kind: Optional[str] = None):
        self.target_name = target_name
        self.chain = lexical_chain or []
        self.new_code = new_code
        self.kind = kind
        self.class_stack: List[str] = []
        self.replaced = False  # <-- add this

        try:
            self._replacement_module = cst.parse_module(self.new_code)
        except Exception:
            self._replacement_module = None

    # ---- context tracking for lexical chain ----
    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.class_stack.append(node.name.value)

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.CSTNode:
        # Replace methods/assignments inside the matched class chain is handled in the leaf visitors
        self.class_stack.pop()
        return updated_node

    def _matches_lexical_chain(self) -> bool:
        # For module-level targets, require we are NOT inside any class
        if not self.chain:
            return len(self.class_stack) == 0
        # For nested class targets, require the current stack equals the chain
        return self.class_stack == self.chain

    # ---- helpers to extract replacement nodes from new_code ----
    def _first_funcdef(self) -> Optional[cst.FunctionDef]:
        if not self._replacement_module:
            return None
        for stmt in self._replacement_module.body:
            if isinstance(stmt, cst.FunctionDef):
                return stmt
        return None

    def _first_assign_stmtline(self) -> Optional[cst.SimpleStatementLine]:
        if not self._replacement_module:
            return None
        for stmt in self._replacement_module.body:
            if isinstance(stmt, cst.SimpleStatementLine) and stmt.body and isinstance(stmt.body[0], cst.Assign):
                return stmt
        return None

    # ---- replacements ----
    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.CSTNode:
        # Replace a function (module-level or method) if names and lexical chain match
        if self.kind in (None, "func", "def"):
            if original_node.name.value == self.target_name and self._matches_lexical_chain():
                rep = self._first_funcdef()
                if rep is not None:
                    return rep
        return updated_node

    def leave_SimpleStatementLine(self, original_node: cst.SimpleStatementLine, updated_node: cst.SimpleStatementLine) -> cst.BaseStatement:
        if self.kind in (None, "assign"):
            if len(updated_node.body) == 1 and isinstance(updated_node.body[0], cst.Assign):
                assign_node = updated_node.body[0]
                for tgt in assign_node.targets:
                    if isinstance(tgt.target, cst.Name) and tgt.target.value == self.target_name:
                        if self._matches_lexical_chain():
                            rep = self._first_assign_stmtline()
                            if rep is not None:
                                self.replaced = True  # <-- set
                                return rep
        return updated_node


def replace_block(content: str,
                  new_code: str,
                  target_name: Optional[str] = None,
                  kind: Optional[str] = None,
                  lexical_chain: Optional[List[str]] = None) -> tuple[str, bool]:
    """
    Replace a function, class, or assignment in `content` with `new_code` using LibCST.
    - If `target_name`/`kind` are omitted, they are inferred from `new_code`.
    - lexical_chain specifies the containment hierarchy (e.g., ['ClassName'] for a method)
    - Handles multiple statements in new_code by extracting the target def/class/assignment
    
    Returns:
        tuple: (modified_content, was_replaced)
    """
    # Parse new_code
    mod = cst.parse_module(new_code)
    
    # Handle different cases based on content of new_code
    if len(mod.body) == 0:
        raise ValueError("new_code cannot be empty.")
    
    elif len(mod.body) == 1:
        # Original behavior - single statement
        node = mod.body[0]
        
        if isinstance(node, cst.FunctionDef):
            replacement_node = node
            inferred_kind = "def"
            inferred_name = node.name.value
        elif isinstance(node, cst.ClassDef):
            replacement_node = node
            inferred_kind = "class"
            inferred_name = node.name.value
        elif isinstance(node, cst.SimpleStatementLine):
            # Check if it's an assignment
            if (len(node.body) == 1):
                if (isinstance(node.body[0], cst.Assign) or isinstance(node.body[0], cst.AnnAssign)):
                    assign_node = node.body[0]
                    if (isinstance(node.body[0], cst.Assign)):
                        if (len(assign_node.targets) == 1 and 
                            isinstance(assign_node.targets[0].target, cst.Name)):
                            replacement_node = node
                            inferred_kind = "assign"
                            inferred_name = assign_node.targets[0].target.value
                        else:
                            raise ValueError("new_code must contain a simple assignment to a single variable.")
                    else:
                        target = assign_node.target
                        if (isinstance(target, cst.Name)):
                            replacement_node = node
                            inferred_kind = "assign"
                            inferred_name = target.value
                        else:
                            raise ValueError("Annotated assignment malformed.")
            else:
                logging.debug(f"content: {content}")
                logging.debug(f"new_code: {new_code}")
                raise ValueError("new_code must contain a function, class, or assignment definition.")
        else:
            logging.debug(f"content: {content}")
            logging.debug(f"new_code: {new_code}")
            raise ValueError("new_code must contain a function, class, or assignment definition.")
    
    else:
        # Multiple statements - find the target def/class/assignment
        replacement_node = None
        inferred_kind = None
        inferred_name = None
        
        # If target_name is provided, look for it specifically
        if target_name:
            for node in mod.body:
                if isinstance(node, (cst.FunctionDef, cst.ClassDef)):
                    if node.name.value == target_name:
                        replacement_node = node
                        inferred_kind = "def" if isinstance(node, cst.FunctionDef) else "class"
                        inferred_name = node.name.value
                        break
                elif isinstance(node, cst.SimpleStatementLine):
                    if (len(node.body) == 1 and isinstance(node.body[0], cst.Assign)):
                        assign_node = node.body[0]
                        for target in assign_node.targets:
                            if isinstance(target.target, cst.Name) and target.target.value == target_name:
                                replacement_node = node
                                inferred_kind = "assign"
                                inferred_name = target_name
                                break
                        if replacement_node:
                            break
        
        # If not found or no target_name provided, use the first def/class/assignment
        if replacement_node is None:
            for node in mod.body:
                if isinstance(node, (cst.FunctionDef, cst.ClassDef)):
                    replacement_node = node
                    inferred_kind = "def" if isinstance(node, cst.FunctionDef) else "class"
                    inferred_name = node.name.value
                    break
                elif isinstance(node, cst.SimpleStatementLine):
                    if (len(node.body) == 1 and isinstance(node.body[0], cst.Assign)):
                        assign_node = node.body[0]
                        if (len(assign_node.targets) == 1 and 
                            isinstance(assign_node.targets[0].target, cst.Name)):
                            replacement_node = node
                            inferred_kind = "assign"
                            inferred_name = assign_node.targets[0].target.value
                            break
        
        if replacement_node is None:
            raise ValueError("new_code must contain at least one function, class, or assignment definition.")
    
    # Use provided parameters or infer from the found node
    kind = kind or inferred_kind
    target_name = target_name or inferred_name
    
    # Perform the replacement using only the replacement_node
    module = cst.parse_module(content)
    
    # Create a version of new_code with just the replacement node for the transformer
    single_node_code = cst.Module(body=[replacement_node]).code

    transformer = ReplaceDeclaration(
        target_name=target_name,
        lexical_chain=lexical_chain or [],
        new_code=single_node_code,
        kind=kind,
    )
    module = cst.parse_module(content)
    new_module = module.visit(transformer)

    # Primary path result
    if transformer.replaced:
        return new_module.code, True

    # If the target exists but we didn't mark replaced, do a robust fallback:
    if _target_exists(content, target_name, lexical_chain or []):
        # 1) remove the old target in the right scope
        stripped, _ = remove_block(content, target_name, lexical_chain or [])
        # 2) insert the new one
        inserted = insert_block(stripped, new_code, target_name=target_name, lexical_chain=lexical_chain or [])
        return inserted, True

    # Otherwise: no target to replace (caller can decide to insert)
    return content, False

def insert_block(content: str,
                 new_code: str,
                 target_name: Optional[str] = None,
                 lexical_chain: Optional[List[str]] = None) -> str:
    """
    Insert a function or class into content at the appropriate location.

    Args:
        content: Source code content
        new_code: New function/class code to insert
        target_name: Name of the function/class to insert
        lexical_chain: Container hierarchy for nested insertion

    Returns:
        Modified content with inserted code
    """
    # Parse the new code to determine what we're inserting
    mod = cst.parse_module(new_code)
    if len(mod.body) != 1:
        raise ValueError("new_code must contain exactly one top-level def/class.")

    node = mod.body[0]

    module = cst.parse_module(content)

    if not lexical_chain:
        # Top-level insertion - append at end of module
        new_module = module.with_changes(
            body=list(module.body) + [node]
        )
    else:
        # Nested insertion - insert into specific container
        transformer = InsertIntoContainer(node, lexical_chain)
        new_module = module.visit(transformer)
        
        if not transformer.inserted:
            raise ValueError(f"Could not find container {'.'.join(lexical_chain)} for insertion")

    return new_module.code

def declare(file_path, target_path, new_code=None):
    """
    Declare a function, class, or assignment in a file with code using lexical chain support.
    If the target_path exists one or more times, replace all with the new declaration.
    If new_code is None, the declaration is deleted.
    """
    logging.debug(f'file: {file_path}')
    with open(file_path, 'r') as f:
        content = f.read()
    target_name, lexical_chain = parse_lexical_chain(target_path)

    # ----- DELETE fast-path -----
    if new_code is None:
        new_content, removed = remove_block(content, target_name, lexical_chain)
        if not removed:
            # Nothing removed; keep content unchanged but surface a clear error for callers/logs
            logging.error(f"Error removing {target_name}: target not found at chain {'.'.join(lexical_chain) or '<module>'}")
        with open(file_path, 'w') as f:
            f.write(new_content)
        return

    # ----- REPLACE or INSERT -----
    new_content, was_replaced = replace_block(content, new_code, target_name=target_name, lexical_chain=lexical_chain)
    if not was_replaced:
        new_content = insert_block(content, new_code, target_name=target_name, lexical_chain=lexical_chain)

    with open(file_path, 'w') as f:
        f.write(new_content)



def move_file(src, dst):
    """Move/rename file or directory"""
    # Track both source and destination for git operations
    if hasattr(move_file, '_rollback_manager'):
        move_file._rollback_manager.track_file(src)
        move_file._rollback_manager.track_file(dst)
    
    shutil.move(src, dst)
    logging.debug(f"Moved {src} to {dst}")

def make_directory(path):
    """Create directory"""
    os.makedirs(path, exist_ok=True)
    logging.debug(f"Created directory {path}")

def remove_file(path, recursive=False):
    """Remove file or directory"""
    # Track file for git operations before removal
    if hasattr(remove_file, '_rollback_manager'):
        remove_file._rollback_manager.track_file(path)
    
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
        logging.info(f"Path {path} perhaps already removed.")

def modification_description(description_text):
    """
    Add description text to the accumulated commit message
    
    Args:
        description_text: Text to append to commit message
    """
    if hasattr(modification_description, '_rollback_manager'):
        modification_description._rollback_manager.accumulate_message(description_text)
    
    logging.debug(f"Added modification description: {description_text}")

def apply_modification_set(modifications, auto_rollback_on_failure=True):
    """
    Apply a set of modifications with rollback support
    
    Args:
        modifications: List of (function, args, kwargs) tuples
        auto_rollback_on_failure: If True, automatically rollback on any failure
        
    Returns:
        GitRollbackManager: Manager instance for manual rollback operations
        
    Raises:
        RuntimeError: If rollback capability cannot be established
    """
    rollback_manager = GitRollbackManager()
    
    # Set rollback manager on modification functions
    declare._rollback_manager = rollback_manager
    move_file._rollback_manager = rollback_manager
    remove_file._rollback_manager = rollback_manager
    create_file._rollback_manager = rollback_manager
    modification_description._rollback_manager = rollback_manager
    # Register the newly added helpers:
    
    # Create rollback point - this will raise if it fails
    rollback_info = rollback_manager.create_rollback_point("Before LLM modifications")
    
    # Process modifications and build commit message
    accumulated_descriptions = []
    other_modifications = []
    
    for func, args, kwargs in modifications:
        if func == modification_description:
            accumulated_descriptions.append(args[0])
        else:
            other_modifications.append((func, args, kwargs))
    
    # Set accumulated message from all descriptions
    if accumulated_descriptions:
        full_description = "\n".join(accumulated_descriptions)
        rollback_manager.accumulate_message(full_description)
    
    try:
        # Apply all non-description modifications
        for func, args, kwargs in other_modifications:
            print(func)
            func(*args, **kwargs)
        
        # Create final commit with tracked files and accumulated message
        if rollback_manager.tracked_files:
            commit_message = rollback_manager.get_accumulated_message()
            if not commit_message:
                commit_message = "After LLM modifications"
            rollback_manager.create_rollback_point(commit_message, force_commit=True)
        
        logging.info("All modifications completed successfully")
        rollback_manager.show_rollback_options()
        return rollback_manager
        
    except Exception as e:
        logging.error(f"Modifications failed: {e}")
        
        if auto_rollback_on_failure:
            logging.info("Auto-rolling back due to failure...")
            rollback_manager.hard_rollback()
        else:
            logging.info("Manual rollback available - use returned manager")
            rollback_manager.show_rollback_options()
        
        raise
    finally:
        # Clean up rollback manager references
        if hasattr(declare, '_rollback_manager'):
            del declare._rollback_manager
        if hasattr(move_file, '_rollback_manager'):
            del move_file._rollback_manager
        if hasattr(remove_file, '_rollback_manager'):
            del remove_file._rollback_manager
        if hasattr(create_file, '_rollback_manager'):
            del create_file._rollback_manager
        if hasattr(modification_description, '_rollback_manager'):
            del modification_description._rollback_manager

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

def open_with_mkdir(filepath, mode='w', **kwargs):
    """
    Opens a file at the given filepath, creating any necessary intermediate directories if they don't exist.
    
    Args:
    filepath (str): The path to the file to open.
    mode (str): The mode in which to open the file (default: 'w' for write).
    **kwargs: Additional keyword arguments to pass to the built-in open() function.
    
    Returns:
    file: An open file object.
    
    Example:
    >>> with open_with_mkdir('path/to/new/dir/file.txt', 'w') as f:
    ...     f.write('Hello, world!')
    """
    # Extract the directory from the filepath
    directory = os.path.dirname(filepath)
    
    # Create the directory if it doesn't exist
    if directory:
        os.makedirs(directory, exist_ok=True)
    
    # Open and return the file object
    return open(filepath, mode=mode, **kwargs)

def update_file(file_path, file_content, make_executable=False):
    if os.path.exists(file_path):
        remove_file(file_path)
    create_file(file_path, file_content, make_executable=make_executable)

def create_file(file_path, file_content, make_executable=True):
    """Create a file
    
    Args:
        file_path: Path where script should be created
        file_content: Content of the script
        make_executable: If True, set executable permissions (Unix/Linux/Mac)
    """
    import stat
    
    #with open(file_path, 'w') as f:
    with open_with_mkdir(file_path, 'w') as f:
        f.write(file_content)
    
    if make_executable:
        # Add executable permissions for owner, group, and others
        current_permissions = os.stat(file_path).st_mode
        os.chmod(file_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    
    # Track file for git operations
    if hasattr(create_file, '_rollback_manager'):
        create_file._rollback_manager.track_file(file_path)
    
    logging.debug(f"Created {'executable script' if make_executable else 'file'} {file_path}")

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        interactive_rollback()
