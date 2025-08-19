#!/usr/bin/env python3
"""
Script to read and execute code modifications from a formatted file
Usage: python modify_code.py <modification_file>
"""
import sys
import re
from code_mod_defs import *

from pathlib import Path
from typing import List, Tuple, Any
import re

# import the callables by name
from code_mod_defs import (
    modification_description,
    create_file,
    move_file,
    # add others here as you introduce them
)

_HEADER_RE = re.compile(r'^\s*MMM\s+([A-Za-z_][A-Za-z0-9_]*)\s+MMM\s*$')

def _parse_bool(s: str) -> bool:
    s = s.strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    # default: treat non-empty as True
    return bool(s)

def _split_sections(block_lines: List[str]) -> List[str]:
    """
    Split a block's lines into sections using a line that is exactly '@@@@@@'
    as a separator. Keep inner newlines; strip a single trailing newline.
    """
    sections: List[List[str]] = [[]]
    for ln in block_lines:
        if ln.strip() == "@@@@@@":
            sections.append([])
        else:
            sections[-1].append(ln)
    out: List[str] = []
    for sec in sections:
        txt = "".join(sec)
        # strip a single trailing newline, keep interior newlines intact
        if txt.endswith("\n"):
            txt = txt[:-1]
        out.append(txt)
    # drop a trailing empty section introduced by a final separator
    while out and out[-1] == "":
        out.pop()
    return out

def _resolve_func(name: str):
    # Extend this map as you add more supported operations
    table = {
        "modification_description": modification_description,
        "create_file": create_file,
        "move_file": move_file,
    }
    if name not in table:
        raise ValueError(f"Unknown modification function: {name}")
    return table[name]

def parse_modification_file(path: str):
    """
    Format:
        MMM <func_name> MMM
        <arg or payload...>
        @@@@@@
        <next arg...>
        @@@@@@
        ... (next block)
        MMM <func_name> MMM
        ...
    For known funcs we coerce argument types appropriately.
    Unknown funcs: treat all sections as positional strings.
    Returns: List[Tuple[callable, tuple(args), dict(kwargs)]]
    """
    text = Path(path).read_text()
    lines = text.splitlines(keepends=True)

    i = 0
    entries: List[Tuple[Any, tuple, dict]] = []

    while i < len(lines):
        m = _HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue

        func_name = m.group(1)
        i += 1

        # collect until next header or EOF
        block: List[str] = []
        while i < len(lines) and not _HEADER_RE.match(lines[i]):
            block.append(lines[i])
            i += 1

        sections = _split_sections(block)
        fn = _resolve_func(func_name)

        # Special handling for known signatures:
        if fn is modification_description:
            if not sections:
                raise ValueError("modification_description requires one section (the description).")
            args = (sections[0],)
            kwargs = {}

        elif fn is create_file:
            if len(sections) < 2:
                raise ValueError("create_file requires at least 2 sections: path, content, [make_executable].")
            path_arg = sections[0].strip()
            content_arg = sections[1]  # preserve newlines
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

        else:
            # Fallback: all sections as positional strings
            args = tuple(sections)
            kwargs = {}

        entries.append((fn, args, kwargs))

    if not entries:
        raise ValueError("No modification blocks found in file.")

    return entries



def main():
    if len(sys.argv) != 2:
        print("Usage: python modify_code.py <modification_file>")
        sys.exit(1)
    
    modification_file = sys.argv[1]
    
    modifications = parse_modification_file(modification_file)
    
    manager = apply_modification_set(modifications)
    print(f"\nModifications complete. Run 'python {sys.argv[0]} rollback' for rollback options.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        interactive_rollback()
    else:
        main()


