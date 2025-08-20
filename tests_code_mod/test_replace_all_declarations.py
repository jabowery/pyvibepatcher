import textwrap
from pathlib import Path
from code_mod_defs import declare

def test_declare_replaces_all_matching_declarations(tmp_path):
    """Test that declare replaces ALL declarations with the same name, not just the first one."""
    p = tmp_path / "multi_declarations.py"
    
    # Create a file with multiple functions having the same name (which is unusual but possible)
    p.write_text(textwrap.dedent("""
    def helper():
        return "first helper"
    
    class A:
        def method(self):
            return 1
    
    def helper():
        return "second helper"
    
    class B:
        def method(self):
            return 2
    
    def helper():
        return "third helper"
    """))
    
    # Replace all 'helper' functions
    declare(str(p), "helper", textwrap.dedent("""
    def helper():
        return "replaced helper"
    """))
    
    content = p.read_text()
    
    # Should have exactly one helper function with the new implementation
    helper_count = content.count('def helper():')
    assert helper_count == 1, f"Expected 1 helper function, found {helper_count}"
    
    # Should contain the new implementation
    assert 'return "replaced helper"' in content
    
    # Should not contain any of the old implementations
    assert 'return "first helper"' not in content
    assert 'return "second helper"' not in content
    assert 'return "third helper"' not in content
    
    # Other methods should be untouched
    assert 'return 1' in content
    assert 'return 2' in content

def test_declare_replaces_all_matching_assignments(tmp_path):
    """Test that declare replaces ALL assignments with the same name."""
    p = tmp_path / "multi_assignments.py"
    
    # Create a file with multiple assignments to the same variable
    p.write_text(textwrap.dedent("""
    x = "first value"
    y = "some other var"
    x = "second value"
    z = "another var"
    x = "third value"
    """))
    
    # Replace all 'x' assignments
    declare(str(p), "x", "x = \"replaced value\"\n")
    
    content = p.read_text()
    
    # Should have exactly one x assignment with the new value
    x_count = content.count('x = ')
    assert x_count == 1, f"Expected 1 x assignment, found {x_count}"
    
    # Should contain the new implementation
    assert 'x = "replaced value"' in content
    
    # Should not contain any of the old implementations
    assert 'x = "first value"' not in content
    assert 'x = "second value"' not in content
    assert 'x = "third value"' not in content
    
    # Other variables should be untouched
    assert 'y = "some other var"' in content
    assert 'z = "another var"' in content

def test_declare_replaces_all_matching_methods_in_same_class(tmp_path):
    """Test replacing multiple methods with same name in the same class."""
    p = tmp_path / "overloaded_methods.py"
    
    # Some languages allow method overloading, Python doesn't really, but test the behavior
    p.write_text(textwrap.dedent("""
    class Calculator:
        def add(self, a, b):
            return a + b
        
        def multiply(self, a, b):
            return a * b
            
        def add(self, a, b, c):  # This would override the first add in Python
            return a + b + c
    """))
    
    # Replace all 'add' methods
    declare(str(p), "Calculator.add", textwrap.dedent("""
    def add(self, *args):
        return sum(args)
    """))
    
    content = p.read_text()
    
    # Should have exactly one add method
    add_count = content.count('def add(')
    assert add_count == 1, f"Expected 1 add method, found {add_count}"
    
    # Should contain the new implementation
    assert 'def add(self, *args):' in content
    assert 'return sum(args)' in content
    
    # Should not contain old implementations
    assert 'def add(self, a, b):' not in content
    assert 'def add(self, a, b, c):' not in content
    
    # Other methods should be untouched
    assert 'def multiply(self, a, b):' in content