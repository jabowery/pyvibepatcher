#!/usr/bin/env python3
"""
Robust modification-file parser for the MMM ... MMM / @@@@@@ format.

Key improvements:
- Separator detection treats any line whose strip() equals '@@@@@@' as a split.
- Guardrails for declare-style operations:
  * update_declaration -> MUST have non-empty content (never delete).
  * remove_declaration -> dedicated function; MUST NOT have content (always delete).
  * declare -> legacy semantics: empty content => delete; non-empty => add/update.
- Clearer error messages for misuse, preventing accidental deletions.
- **NEW**: First split the entire file into ^MMM command blocks before processing.
"""

from __future__ import annotations

import sys
import re
from pathlib import Path
from typing import List, Tuple, Any

from code_mod_defs import (
    apply_modification_set,
    modification_description,
    create_file,
    move_file,
    declare,
    replace_file_contents,
    make_directory,
    remove_file,
    update_header,
    remove_declaration,       # NEW: import dedicated function
    interactive_rollback,     # assumed to exist in your environment
)

# Matches lines like: MMM function_name MMM
_HEADER_RE = re.compile(r'^MMM\s+([A-Za-z_][A-Za-z0-9_]*)\s+MMM\s*')

def _parse_bool(s: str) -> bool:
    s = s.strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    # default: treat non-empty as True
    return bool(s)

def _is_sep_line(ln: str) -> bool:
    """Return True if the line is a section separator ('@@@@@@'), robust to CRLF and spaces."""
    return ln.strip() == "@@@@@@"

def _split_sections(block_lines: List[str]) -> List[str]:
    """
    Split a block into text sections using lines whose strip() equals '@@@@@@' as separators.
    - Preserve inner newlines in each section.
    - Strip a single trailing newline per section for predictable behavior.
    - Do NOT drop trailing empty sections here; higher-level logic decides semantics.
    """
    sections: List[List[str]] = [[]]
    for ln in block_lines:
        if _is_sep_line(ln):
            sections.append([])
        else:
            # Allow escaping a literal '@@@@@@' by prefixing with '\'
            if ln.startswith('\\@@@@@@'):
                ln = ln[1:]
            sections[-1].append(ln)

    out: List[str] = []
    for sec in sections:
        txt = "".join(sec)
        if txt.endswith("\n"):
            txt = txt[:-1]
        out.append(txt)
    return out


def _resolve_func(name: str):
    """
    Map modification command names to callables.
    Extend here if you add new commands.
    """
    table = {
        "modification_description": modification_description,
        "create_file": create_file,
        "replace_file_contents": replace_file_contents,
        "move_file": move_file,
        "make_directory": make_directory,
        "remove_file": remove_file,
        "declare": declare,
        "update_declaration": declare,           # alias
        "remove_declaration": remove_declaration,
        "update_header": update_header,
    }
    return table.get(name)



def _has_nonempty_text(s: str | None) -> bool:
    return s is not None and s.strip() != ""

def _split_command_blocks(lines: List[str]) -> List[Tuple[str, List[str]]]:
    """
    First pass: split the entire file into command blocks using ^MMM <name> MMM headers.
    Returns a list of (func_name, block_lines) where block_lines excludes the header
    and runs up to (but not including) the next header (or EOF).
    """
    blocks: List[Tuple[str, List[str]]] = []
    i = 0
    current_name: str | None = None
    current_block: List[str] = []

    while i < len(lines):
        m = _HEADER_RE.match(lines[i])
        if m:
            # Commit the previous block if any
            if current_name is not None:
                blocks.append((current_name, current_block))
            # Start a new block
            current_name = m.group(1)
            current_block = []
        else:
            if current_name is not None:
                current_block.append(lines[i])
        i += 1

    # Commit the trailing block
    if current_name is not None:
        blocks.append((current_name, current_block))

    return blocks

def parse_modification_file(path: str):
    """
    Parse the given modification file and return a list of entries:
        List[Tuple[callable, tuple(args), dict(kwargs)]]

    Format per block:
        MMM <func_name> MMM
        <arg or payload...>
        @@@@@@
        <next arg...>
        @@@@@@
        ... (next block)
        MMM <func_name> MMM
        ...

    Guardrails for declare-like functions are enforced here so downstream code
    can't accidentally delete when the intent was to update.
    """
    text = Path(path).read_text()
    lines = text.splitlines(keepends=True)

    entries: List[Tuple[Any, tuple, dict]] = []

    # **NEW**: First split the full file into command blocks by MMM headers
    blocks = _split_command_blocks(lines)

    for func_name, block in blocks:
        sections = _split_sections(block)
        fn = _resolve_func(func_name)

        # Special handling for known signatures
        if fn is modification_description:
            if not sections:
                raise ValueError("modification_description requires one section (the description).")
            args = (sections[0],)
            kwargs = {}

        elif fn is create_file:
            if len(sections) < 2:
                raise ValueError("create_file requires at least 2 sections: path, content, [make_executable].")
            path_arg = sections[0].strip()
            content_arg = sections[1]
            make_exec = _parse_bool(sections[2]) if len(sections) >= 3 else False
            args = (path_arg, content_arg)
            kwargs = {"make_executable": make_exec}

        elif fn is replace_file_contents:
            if len(sections) < 2:
                raise ValueError("replace_file_contents requires at least 2 sections: path, content, [make_executable].")
            path_arg = sections[0].strip()
            content_arg = sections[1]
            make_exec = _parse_bool(sections[2]) if len(sections) >= 3 else False
            args = (path_arg, content_arg)
            kwargs = {"make_executable": make_exec}

        elif fn is move_file:
            if len(sections) < 2:
                raise ValueError("move_file requires 2 sections: src, dst.")
            src = sections[0].strip()
            dst = sections[1].strip()
            args = (src, dst)
            kwargs = {}

        elif fn is declare:
            # For declare/update_declaration apply guardrails at parse time
            if len(sections) < 2:
                raise ValueError(f"{func_name} requires 2+ sections: file_path, target_path, [content].")

            file_path = sections[0].strip()
            name = sections[1].strip()
            content = sections[2] if len(sections) >= 3 else None

            if func_name == "update_declaration":
                if not _has_nonempty_text(content):
                    raise ValueError("update_declaration requires a NON-empty content section; it cannot delete. If you intend deletion, use remove_declaration.")
            else:  # bare 'declare' keeps legacy: empty => delete, non-empty => add/update
                if content is not None and content.strip() == "":
                    content = None  # normalize empty-string payload to deletion

            args = (file_path, name, content)
            kwargs = {}

        elif fn is remove_declaration:
            # Dedicated deletion primitive: exactly two sections; no content allowed
            if len(sections) < 2:
                raise ValueError("remove_declaration requires 2 sections: file_path, target_path (no content).")
            if len(sections) >= 3 and _has_nonempty_text(sections[2]):
                raise ValueError("remove_declaration must NOT include a content section. Provide only file_path and target_path.")
            file_path = sections[0].strip()
            name = sections[1].strip()
            args = (file_path, name)
            kwargs = {}

        elif fn is make_directory:
            if len(sections) < 1:
                raise ValueError("make_directory requires 1 section: path.")
            path_arg = sections[0].strip()
            args = (path_arg,)
            kwargs = {}

        elif fn is remove_file:
            if len(sections) < 1:
                raise ValueError("remove_file requires at least 1 section: path, [recursive].")
            path_arg = sections[0].strip()
            recursive = _parse_bool(sections[1]) if len(sections) >= 2 else False
            args = (path_arg,)
            kwargs = {"recursive": recursive}

        elif fn is update_header:
            if len(sections) < 2:
                raise ValueError("update_header requires 2 sections: file_path, header_content.")
            file_path_arg = sections[0].strip()
            header_content_arg = sections[1]
            args = (file_path_arg, header_content_arg)
            kwargs = {}

        else:
            # Fallback: pass all sections as positional strings
            args = tuple(sections)
            kwargs = {}

        entries.append((fn, args, kwargs))

    if not entries:
        raise ValueError("No modification blocks found in file.")

    return entries

def main():
    if len(sys.argv) == 2 and sys.argv[1] == 'rollback':
        interactive_rollback()
        return

    if len(sys.argv) != 2:
        print("Usage: python modify_code.py <modification_file>\n       python modify_code.py rollback")
        sys.exit(1)

    modification_file = sys.argv[1]
    modifications = parse_modification_file(modification_file)
    manager = apply_modification_set(modifications)
    print("\nModifications complete. Use 'python modify_code.py rollback' for rollback options.")

if __name__ == "__main__":
    main()
