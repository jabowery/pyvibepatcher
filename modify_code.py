#!/bin/env python
import sys
from pathlib import Path
from typing import List, Tuple, Any
import re

from code_mod_defs import (
    modification_description,
    create_file,
    move_file,
    declare,
    update_declaration,  # Add this line
    remove_declaration,  # Add this line
    update_file,
    make_directory,
    remove_file,
    module_header,
    # add others here as you introduce them
)

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
        if ln[:7] == "@@@@@@\n":
            sections.append([])
        else:
            if ln[:7] == '\\@@@@@@':    # literal @@@@@@ must be escaped
                ln = ln[1:]
            sections[-1].append(ln)
    out: List[str] = []
    for sec in sections:
        txt = "".join(sec)
        # strip a single trailing newline, keep interior newlines intact
        if txt.endswith("\n"):
            txt = txt[:-1]
        out.append(txt)
    return out


def main():
    if len(sys.argv) != 2:
        print("Usage: python modify_code.py <modification_file>")
        sys.exit(1)
    
    modification_file = sys.argv[1]
    
    modifications = parse_modification_file(modification_file)
    
    manager = apply_modification_set(modifications)
    print(f"\nModifications complete. Run 'python {sys.argv[0]} rollback' for rollback options.")
def _resolve_func(name: str):
    # Extend this map as you add more supported operations
    table = {
        "modification_description": modification_description,
        "create_file": create_file,
        "move_file": move_file,
        "declare": declare,
        "update_declaration": declare,  # Add this line as synonym
        "remove_declaration": declare,  # Add this line as synonym
        "update_file": update_file,
        "make_directory": make_directory,
        "remove_file": remove_file,
        "module_header": module_header,
    }
    if name not in table:
        raise ValueError(f"Unknown modification function: {name}")
    return table[name]
def parse_modification_file(path: str):
    """
    Format:
        mmm <func_name> mmm
        <arg or payload...>
        @@@@@
        <next arg...>
        @@@@@
        ... (next block)
        mmm <func_name> mmm
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

        elif fn is update_file:
            if len(sections) < 2:
                raise ValueError("update_file requires at least 2 sections: path, content, [make_executable].")
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

        elif fn is declare:  # This handles 'declare', 'update_declaration', and 'remove_declaration' since they resolve to the same function
            if len(sections) < 3:
                raise ValueError(f"{func_name} requires 3 sections: file_path, name, content (or None for deletion).")
            file_path = sections[0].strip()
            name = sections[1].strip()
            content = sections[2] if sections[2].strip() else None  # treat empty content as None for deletion
            args = (file_path, name, content)
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

        elif fn is module_header:
            if len(sections) < 2:
                raise ValueError("module_header requires 2 sections: file_path, header_content.")
            file_path_arg = sections[0].strip()
            header_content_arg = sections[1]  # preserve newlines and formatting
            args = (file_path_arg, header_content_arg)
            kwargs = {}

        else:
            # Fallback: all sections as positional strings
            args = tuple(sections)
            kwargs = {}

        entries.append((fn, args, kwargs))

    if not entries:
        raise ValueError("No modification blocks found in file.")

    return entries

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        interactive_rollback()
    else:
        main()
