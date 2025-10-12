import textwrap
from pathlib import Path
import pytest

from modify_code import parse_modification_file

def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p

def test_update_declaration_with_trailing_blank_after_separator(tmp_path):
    # Content section followed by a blank line, then next block header.
    mods_text = '''MMM update_declaration MMM
mdlloss_flow.py
@@@@@@
MDLLossFlow.get_mixture_optimizer
@@@@@@
def get_mixture_optimizer(self, lr: float = 1e-3):
    return None
@@@@@@

MMM modification_description MMM
ok
'''
    mfile = _write(tmp_path, "mods.txt", mods_text)
    mods = parse_modification_file(str(mfile))
    # First entry is update_declaration with 3 sections (content present)
    assert mods[0][0].__name__ == "declare"
    file_path, name, content = mods[0][1]
    assert file_path == "mdlloss_flow.py"
    assert name == "MDLLossFlow.get_mixture_optimizer"
    assert isinstance(content, str) and content.strip().startswith("def get_mixture_optimizer")

def test_update_declaration_without_content_raises(tmp_path):
    mods_text = '''MMM update_declaration MMM
file.py
@@@@@@
A.B.method
'''
    mfile = _write(tmp_path, "mods.txt", mods_text)
    with pytest.raises(ValueError) as e:
        parse_modification_file(str(mfile))
    assert "requires a NON-empty content section" in str(e.value)

def test_remove_declaration_with_content_raises(tmp_path):
    mods_text = '''MMM remove_declaration MMM
file.py
@@@@@@
A.B.method
@@@@@@
def should_not_be_here():
    pass
'''
    mfile = _write(tmp_path, "mods.txt", mods_text)
    with pytest.raises(ValueError) as e:
        parse_modification_file(str(mfile))
    assert "must NOT include a content section" in str(e.value)

def test_legacy_declare_allows_empty_to_delete(tmp_path):
    mods_text = '''MMM declare MMM
file.py
@@@@@@
A.B.method
'''
    mfile = _write(tmp_path, "mods.txt", mods_text)
    mods = parse_modification_file(str(mfile))
    # Bare declare with no content => deletion (content normalized to None)
    assert mods[0][0].__name__ == "declare"
    file_path, name, content = mods[0][1]
    assert content is None
