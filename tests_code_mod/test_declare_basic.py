import textwrap
from pathlib import Path

from code_mod_defs import declare, parse_lexical_chain

def test_parse_lexical_chain_top_level():
    name, chain = parse_lexical_chain("foo")
    assert name == "foo" and chain == []

def test_parse_lexical_chain_nested():
    name, chain = parse_lexical_chain("A.b.c")
    assert name == "c" and chain == ["A", "b"]

def test_replace_insert_delete_roundtrip(tmp_path):
    p = tmp_path / "m.py"
    p.write_text("")
    # insert a top-level def
    declare(str(p), "foo", textwrap.dedent("""
    def foo():
        return 1
    """))
    s = p.read_text()
    assert "def foo" in s and "return 1" in s

    # replace the def
    declare(str(p), "foo", textwrap.dedent("""
    def foo():
        return 2
    """))
    s = p.read_text()
    assert "return 2" in s and "return 1" not in s

    # delete the def
    declare(str(p), "foo", None)
    s = p.read_text()
    assert "def foo" not in s

def test_nested_insertion_and_deletion(tmp_path):
    p = tmp_path / "n.py"
    p.write_text(textwrap.dedent("""
    class A:
        def b(self):
            x = 1
    """))
    # insert a method c into A
    declare(str(p), "A.c", textwrap.dedent("""
    def c(self):
        return 'ok'
    """))
    s = p.read_text()
    assert "def c(self)" in s

    # delete method b
    declare(str(p), "A.b", None)
    s = p.read_text()
    assert "def b(" not in s

def test_assignment_replace_and_delete(tmp_path):
    p = tmp_path / "v.py"
    p.write_text("x = 1\ny = 2\n")
    # replace assignment to x
    declare(str(p), "x", "x = 42\n")
    s = p.read_text()
    assert "x = 42" in s and "y = 2" in s
    # delete y
    declare(str(p), "y", None)
    s = p.read_text()
    assert "y = 2" not in s
