from code_mod_defs import remove_block

def test_remove_block_removes_all_matching_functions():
    source = """
def helper():
    return "first"

def other():
    return "other"

def helper():
    return "second"

def helper():
    return "third"
"""
    result, removed = remove_block(source, "helper", [])
    assert removed == True
    assert "def helper" not in result
    assert "def other" in result  # should keep non-matching functions

def test_remove_block_removes_all_matching_assignments():
    source = """
x = "first value"
y = "some other var"
x = "second value"
z = "another var"
x = "third value"
"""
    result, removed = remove_block(source, "x", [])
    print(f"Removed: {removed}")
    print(f"Result:\n{result}")
    print(f"x count: {result.count('x = ')}")
    assert removed == True
    assert "x =" not in result
    assert "y =" in result  # should keep non-matching assignments
