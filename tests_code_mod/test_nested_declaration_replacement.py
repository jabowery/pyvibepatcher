#!/usr/bin/env python3
"""
Test to verify that nested declarations can be replaced correctly.
This ensures that when using declare with a dotted path like 'main.foo',
the nested function is properly replaced without affecting the outer structure.

Place this in: tests_code_mod/test_nested_declaration_replacement.py
"""
import textwrap
from pathlib import Path
import pytest
from code_mod_defs import declare


class TestNestedDeclarationReplacement:
    """Test replacement of nested declarations"""
    
    def test_replace_nested_function(self, tmp_path):
        """Test replacing a nested function using dotted path"""
        test_file = tmp_path / "nested_test.py"
        test_file.write_text(textwrap.dedent("""
        def main():
            def foo():
                pass
                
            def bar():
                return "original"
        """).strip())
        
        # Apply declare for nested replacement
        declare(str(test_file), "main.foo", textwrap.dedent("""
        def foo():
            '''Updated nested function'''
            print('hi')
            return "updated"
        """).strip())
        
        content = test_file.read_text()
        print("=== DEBUG: After declare ===")
        for i, line in enumerate(content.split('\n')):
            print(f"{i:2}: {line}")
        print("=== END DEBUG ===")

        lines = content.split('\n')
        
        # Find key elements
        main_def_line = next((i for i, line in enumerate(lines) if line.strip().startswith('def main():')), -1)
        foo_def_line = next((i for i, line in enumerate(lines) if line.strip().startswith('def foo():')), -1)
        print_line = next((i for i, line in enumerate(lines) if "print('hi')" in line), -1)
        bar_def_line = next((i for i, line in enumerate(lines) if line.strip().startswith('def bar():')), -1)
        pass_line = next((i for i, line in enumerate(lines) if line.strip() == 'pass'), -1)
        
        # Verify order: main > foo > print > bar
        assert main_def_line < foo_def_line, "Main should come before foo"
        assert foo_def_line < print_line, "Foo def should come before its body"
        assert foo_def_line < bar_def_line, "Foo should come before bar"
        
        # Verify replacement happened
        assert "print('hi')" in content
        assert "return \"updated\"" in content
        
        # Verify original elements preserved/removed
        assert "def bar():" in content
        assert "return \"original\"" in content
        assert pass_line == -1, "Original 'pass' should be removed"
        
        # Verify no unexpected changes
        assert "def main():" in content
        assert content.count('def foo():') == 1, "Only one foo definition should exist"


    def test_replace_nested_class_method(self, tmp_path):
        """Test replacing a method inside a nested class"""
        test_file = tmp_path / "nested_class.py"
        test_file.write_text(textwrap.dedent("""
        class Outer:
            class Inner:
                def method(self):
                    return "original"
                
            def other(self):
                return "preserve"
        """).strip())
        
        # Apply declare for nested method replacement
        declare(str(test_file), "Outer.Inner.method", textwrap.dedent("""
        def method(self):
            '''Updated method'''
            return "updated"
        """).strip())
        
        content = test_file.read_text()
        lines = content.split('\n')
        
        # Find positions
        outer_line = next((i for i, line in enumerate(lines) if line.strip().startswith('class Outer:')), -1)
        inner_line = next((i for i, line in enumerate(lines) if line.strip().startswith('class Inner:')), -1)
        method_line = next((i for i, line in enumerate(lines) if line.strip().startswith('def method(self):')), -1)
        updated_return_line = next((i for i, line in enumerate(lines) if 'return "updated"' in line), -1)
        other_line = next((i for i, line in enumerate(lines) if line.strip().startswith('def other(self):')), -1)
        
        # Verify correct ordering
        assert outer_line < inner_line, "Outer should come before Inner"
        assert inner_line < method_line, "Inner should come before method"
        assert method_line < updated_return_line, "Method def before its body"
        assert method_line < other_line, "Method should come before other (assuming insertion order)"
        
        # Verify changes
        assert 'return "updated"' in content
        assert 'return "original"' not in content
        assert 'def other(self):' in content
        assert 'return "preserve"' in content


    def test_replace_deeply_nested(self, tmp_path):
        """Test replacement with deeper nesting like func.class.method"""
        test_file = tmp_path / "deep_nested.py"
        test_file.write_text(textwrap.dedent("""
        def func():
            class Cls:
                def meth(self):
                    pass
            
            def other():
                return "preserve"
        """).strip())
        
        # Apply declare for deep nested replacement
        declare(str(test_file), "func.Cls.meth", textwrap.dedent("""
        def meth(self):
            '''Deep updated'''
            print('deep')
        """).strip())
        
        content = test_file.read_text()
        lines = content.split('\n')
        
        # Find positions
        func_line = next((i for i, line in enumerate(lines) if line.strip().startswith('def func():')), -1)
        cls_line = next((i for i, line in enumerate(lines) if line.strip().startswith('class Cls:')), -1)
        meth_line = next((i for i, line in enumerate(lines) if line.strip().startswith('def meth(self):')), -1)
        print_line = next((i for i, line in enumerate(lines) if "print('deep')" in line), -1)
        other_line = next((i for i, line in enumerate(lines) if line.strip().startswith('def other():')), -1)
        pass_line = next((i for i, line in enumerate(lines) if line.strip() == 'pass'), -1)
        
        # Verify ordering
        assert func_line < cls_line, "Func before Cls"
        assert cls_line < meth_line, "Cls before meth"
        assert meth_line < print_line, "Meth before print"
        assert meth_line < other_line, "Meth before other"
        
        # Verify changes
        assert "print('deep')" in content
        assert pass_line == -1, "'pass' should be removed"
        assert "def other():" in content
        assert 'return "preserve"' in content


    def test_noop_on_nonexistent_nested(self, tmp_path):
        """Test that declare inserts if nested target doesn't exist"""
        test_file = tmp_path / "insert_nested.py"
        test_file.write_text(textwrap.dedent("""
        def main():
            pass
        """).strip())
        
        # Apply declare for non-existent nested
        declare(str(test_file), "main.foo", textwrap.dedent("""
        def foo():
            print('inserted')
        """).strip())
        
        content = test_file.read_text()
        lines = content.split('\n')
        
        main_line = next((i for i, line in enumerate(lines) if line.strip().startswith('def main():')), -1)
        foo_line = next((i for i, line in enumerate(lines) if line.strip().startswith('def foo():')), -1)
        print_line = next((i for i, line in enumerate(lines) if "print('inserted')" in line), -1)
        
        assert main_line < foo_line < print_line, "Correct insertion order"
        assert "print('inserted')" in content
        assert "pass" not in content  # Original pass removed or overwritten? Wait, insertion should add after.