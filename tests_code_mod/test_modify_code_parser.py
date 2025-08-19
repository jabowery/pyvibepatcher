from modify_code import parse_modification_file

SAMPLE = """\
MMM modification_description MMM
Describe the change
@@@@@@
MMM create_file MMM
path/to/file.txt
@@@@@@
content here
@@@@@@
False
@@@@@@
MMM move_file MMM
path/to/file.txt
@@@@@@
new/place.txt
"""

def test_parse_modification_file(tmp_path):
    mfile = tmp_path / "mods.txt"
    mfile.write_text(SAMPLE)
    mods = parse_modification_file(str(mfile))
    funcs = [m[0].__name__ for m in mods]
    assert funcs == ["modification_description", "create_file", "move_file"]
    assert mods[1][1][0].strip() == "path/to/file.txt"
    assert mods[1][1][1].strip() == "content here"
    assert mods[2][1][1].strip() == "new/place.txt"
