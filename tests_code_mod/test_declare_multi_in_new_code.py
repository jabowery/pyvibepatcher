import textwrap
from pathlib import Path
import re

import pytest
from code_mod_defs import declare

def _count_in_class(source: str, class_name: str, needle: str) -> int:
    """Count occurrences of `needle` inside the lexical block of `class <class_name>:`.

    This version records the indentation of the `class` line and then
    scans subsequent lines while their leading indentation is strictly
    greater than that class indentation. This makes it robust to nested
    classes and indented class definitions.
    """
    lines = source.splitlines()
    in_class = False
    class_indent = 0
    count = 0

    def leading_spaces(s: str) -> int:
        return len(s) - len(s.lstrip(' '))

    class_re = re.compile(rf'^\s*class\s+{re.escape(class_name)}\b')

    for line in lines:
        if not in_class:
            if class_re.match(line):
                in_class = True
                class_indent = leading_spaces(line)
            continue

        # Once in the class: consider only lines that are more indented than the class header
        if line.strip() == '':
            # blank lines belong to the current block; continue
            pass
        else:
            indent = leading_spaces(line)
            if indent <= class_indent:
                # we've left the class block
                break

        if needle in line:
            count += 1

    return count


def test_multi_declare_methods_same_base_chain(tmp_path):
    p = tmp_path / "multi_class.py"
    p.write_text(textwrap.dedent("""
    class A:
        class B:
            pass
    """))
    # Provide two methods in one new_code block; target path points at the first one
    declare(str(p), "A.B.foo", textwrap.dedent("""
    def foo(self): 
        return "foo"

    def bar(self): 
        return "bar"
    """))
    s = p.read_text()
    # Both methods should appear inside class B
    assert _count_in_class(s, "B", "def foo(") == 1
    assert _count_in_class(s, "B", "def bar(") == 1
    # Ensure only one copy at top-level
    assert "def foo(" in s and "def bar(" in s
    # Quick sanity that they are not duplicated
    assert s.count("def foo(") == 1
    assert s.count("def bar(") == 1


def test_multi_declare_top_level_functions(tmp_path):
    p = tmp_path / "multi_top_level.py"
    p.write_text("")
    declare(str(p), "alpha", textwrap.dedent("""
    def alpha(): 
        return 1

    def beta(): 
        return 2
    """))
    s = p.read_text()
    # Both functions should be present at top-level
    assert "def alpha(" in s
    assert "def beta(" in s
    assert s.count("def alpha(") == 1
    assert s.count("def beta(") == 1


def test_multi_declare_assignments_in_class(tmp_path):
    p = tmp_path / "multi_assign_class.py"
    p.write_text(textwrap.dedent("""
    class C:
        pass
    """))
    declare(str(p), "C.x", textwrap.dedent("""
    x = 10

    y = 20
    """))
    s = p.read_text()
    # Both assignments should be inside class C and appear once
    assert _count_in_class(s, "C", "x = 10") == 1
    assert _count_in_class(s, "C", "y = 20") == 1
    assert s.count("x = 10") == 1
    assert s.count("y = 20") == 1
