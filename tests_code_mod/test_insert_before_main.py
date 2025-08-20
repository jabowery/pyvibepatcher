import textwrap
from pathlib import Path
from code_mod_defs import declare

def test_declare_inserts_before_main_block(tmp_path):
    """Test that new declarations are inserted before if __name__ == '__main__' block."""
    p = tmp_path / "with_main.py"
    
    # Create a file with existing code and a __main__ block
    p.write_text(textwrap.dedent("""
    import os
    import sys
    
    def existing_function():
        return "exists"
    
    SOME_CONSTANT = 42
    
    if __name__ == '__main__':
        print("Running main")
        existing_function()
        sys.exit(0)
    """))
    
    # Insert a new function
    declare(str(p), "new_function", textwrap.dedent("""
    def new_function():
        return "new"
    """))
    
    content = p.read_text()
    lines = content.split('\n')
    
    # Find the positions of key elements
    new_func_line = next(i for i, line in enumerate(lines) if 'def new_function' in line)
    main_line = next(i for i, line in enumerate(lines) if 'if __name__ == ' in line)
    
    # New function should be inserted before the __main__ block
    assert new_func_line < main_line, f"new_function at line {new_func_line} should be before __main__ at line {main_line}"
    
    # Verify the __main__ block is still intact
    assert 'if __name__ == \'__main__\':' in content
    assert 'print("Running main")' in content
    assert 'sys.exit(0)' in content

def test_declare_inserts_before_other_executable_code(tmp_path):
    """Test that new declarations are inserted before other executable statements."""
    p = tmp_path / "with_exec.py"
    
    # Create a file with functions and trailing executable code
    p.write_text(textwrap.dedent("""
    def existing():
        pass
    
    # Some executable code at module level
    print("Module loading")
    result = existing()
    print(f"Result: {result}")
    """))
    
    # Insert a new function
    declare(str(p), "new_function", textwrap.dedent("""
    def new_function():
        return "inserted"
    """))
    
    content = p.read_text()
    lines = content.split('\n')
    
    # Find positions
    new_func_line = next(i for i, line in enumerate(lines) if 'def new_function' in line)
    print_line = next(i for i, line in enumerate(lines) if 'print("Module loading")' in line)
    
    # New function should be before executable code
    assert new_func_line < print_line, f"new_function should be inserted before executable code"

def test_declare_replaces_preserves_main_block_position(tmp_path):
    """Test that replacing a declaration doesn't move the __main__ block."""
    p = tmp_path / "replace_with_main.py"
    
    p.write_text(textwrap.dedent("""
    def target_function():
        return "original"
    
    OTHER_VAR = "unchanged"
    
    if __name__ == '__main__':
        print("Main block")
        target_function()
    """))
    
    # Replace the existing function
    declare(str(p), "target_function", textwrap.dedent("""
    def target_function():
        return "replaced"
    """))
    
    content = p.read_text()
    lines = content.split('\n')
    
    # Verify replacement happened
    assert 'return "replaced"' in content
    assert 'return "original"' not in content
    
    # Verify __main__ block is still at the end
    target_line = next(i for i, line in enumerate(lines) if 'def target_function' in line)
    main_line = next(i for i, line in enumerate(lines) if 'if __name__ == ' in line)
    
    assert target_line < main_line, "Replaced function should still be before __main__ block"
    assert 'print("Main block")' in content