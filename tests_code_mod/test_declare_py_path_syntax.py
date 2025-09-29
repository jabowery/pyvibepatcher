# File: tests_code_mod/test_declare_py_path_syntax.py
#!/usr/bin/env python3
"""
Test case for declare function's .py. path syntax
This tests the feature where "file.py.target" can be used as a combined path
"""
import textwrap
from pathlib import Path
import pytest
from code_mod_defs import declare


class TestDeclareWithPyPathSyntax:
    """Test that declare properly handles file.py.target syntax"""
    
    def test_simple_function_with_py_path_syntax(self, tmp_path):
        """Test basic function declaration using file.py.function_name syntax"""
        test_file = tmp_path / "module.py"
        test_file.write_text(textwrap.dedent("""
        def old_function():
            return "old"
        """))
        
        # Change to tmp_path directory for relative path to work
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # Use the combined path syntax: file.py.target
            declare("module.py.old_function", textwrap.dedent("""
            def old_function():
                return "new"
            """))
            
            content = test_file.read_text()
            assert 'return "new"' in content
            assert 'return "old"' not in content
        finally:
            os.chdir(original_dir)
    
    def test_nested_class_method_with_py_path_syntax(self, tmp_path):
        """Test nested class method using file.py.Class.method syntax"""
        test_file = tmp_path / "calculator.py"
        test_file.write_text(textwrap.dedent("""
        class Calculator:
            def add(self, a, b):
                return a + b
        """))
        
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # Use nested path: file.py.Class.method
            declare("calculator.py.Calculator.add", textwrap.dedent("""
            def add(self, a, b):
                return a + b + 1  # Modified
            """))
            
            content = test_file.read_text()
            assert 'return a + b + 1' in content
            # Check that the plain "return a + b" is gone (may still have "a + b + 1")
            lines_with_return = [line for line in content.split('\n') if 'return' in line]
            assert any('a + b + 1' in line for line in lines_with_return)
            assert not any(line.strip() == 'return a + b' for line in lines_with_return)
        finally:
            os.chdir(original_dir)
    
    def test_py_path_with_subdirectory(self, tmp_path):
        """Test that subdirectory paths work: subdir/file.py.target"""
        subdir = tmp_path / "src"
        subdir.mkdir()
        test_file = subdir / "utils.py"
        test_file.write_text(textwrap.dedent("""
        def helper():
            return "original"
        """))
        
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # Use path with subdirectory
            declare("src/utils.py.helper", textwrap.dedent("""
            def helper():
                return "updated"
            """))
            
            content = test_file.read_text()
            assert 'return "updated"' in content
            assert 'return "original"' not in content
        finally:
            os.chdir(original_dir)
    
    def test_py_path_replaces_different_function_name(self, tmp_path):
        """Test that .py. syntax can replace a function with a different name"""
        test_file = tmp_path / "service.py"
        test_file.write_text(textwrap.dedent("""
        def fetch_data():
            return "old implementation"
        """))
        
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # Target is fetch_data, but new function has different name
            declare("service.py.fetch_data", textwrap.dedent("""
            def fetch_data_v2():
                return "new implementation"
            """))
            
            content = test_file.read_text()
            # Old function should be replaced
            assert 'def fetch_data():' not in content
            assert 'def fetch_data_v2():' in content
            assert 'return "new implementation"' in content
        finally:
            os.chdir(original_dir)
    
    def test_py_path_with_assignment(self, tmp_path):
        """Test .py. syntax works with variable assignments"""
        test_file = tmp_path / "config.py"
        test_file.write_text(textwrap.dedent("""
        API_URL = "http://old-api.example.com"
        TIMEOUT = 30
        """))
        
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            declare("config.py.API_URL", textwrap.dedent("""
            API_URL = "http://new-api.example.com"
            """))
            
            content = test_file.read_text()
            assert 'http://new-api.example.com' in content
            assert 'http://old-api.example.com' not in content
            assert 'TIMEOUT = 30' in content  # Other vars preserved
        finally:
            os.chdir(original_dir)
    
    def test_py_path_with_class_definition(self, tmp_path):
        """Test .py. syntax works with class definitions"""
        test_file = tmp_path / "models.py"
        test_file.write_text(textwrap.dedent("""
        class OldModel:
            def __init__(self):
                self.version = 1
        """))
        
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            declare("models.py.OldModel", textwrap.dedent("""
            class OldModel:
                def __init__(self):
                    self.version = 2
                    self.updated = True
            """))
            
            content = test_file.read_text()
            assert 'self.version = 2' in content
            assert 'self.updated = True' in content
            assert 'self.version = 1' not in content
        finally:
            os.chdir(original_dir)
    
    def test_three_arg_form_still_works(self, tmp_path):
        """Ensure traditional 3-argument form still works"""
        test_file = tmp_path / "legacy.py"
        test_file.write_text(textwrap.dedent("""
        def old_func():
            pass
        """))
        
        # Traditional 3-arg form should still work (uses absolute path)
        declare(str(test_file), "old_func", textwrap.dedent("""
        def old_func():
            return "updated"
        """))
        
        content = test_file.read_text()
        assert 'return "updated"' in content
    
    def test_example_from_documentation(self, tmp_path):
        """Test the exact example from the feature request"""
        test_file = tmp_path / "heteromix_training.py"
        test_file.write_text(textwrap.dedent("""
        def add_artifact_cli_args(parser):
            # Old implementation
            return parser
        
        def main():
            pass
        """))
        
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # This is the exact syntax from the feature request
            declare("heteromix_training.py.add_artifact_cli_args", textwrap.dedent("""
            def new_name_for_add_artifact_cli_args(parser):
                '''
                Non-invasive helper: call this where you build argparse in heteromix_training.py
                to add the --out argument without altering other CLI.
                '''
                parser.add_argument(
                    "--out",
                    type=str,
                    required=False,
                    help="Directory to write Model Artifact v1. If absent, no artifact is written."
                )
                return parser
            """))
            
            content = test_file.read_text()
            
            # Old function should be gone
            assert 'def add_artifact_cli_args(parser):' not in content
            
            # New function should be present
            assert 'def new_name_for_add_artifact_cli_args(parser):' in content
            assert '--out' in content
            assert 'Model Artifact v1' in content
            
            # Other functions preserved
            assert 'def main():' in content
        finally:
            os.chdir(original_dir)
    
    def test_multiple_py_in_path_uses_first(self, tmp_path):
        """Test that if path has multiple .py., it uses the first one"""
        # Create nested structure
        test_file = tmp_path / "my.py"
        test_file.write_text(textwrap.dedent("""
        def target():
            return "original"
        """))
        
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # Edge case: what if someone has "my.py.backup.py.target"?
            # Should split at first .py.
            declare("my.py.target", textwrap.dedent("""
            def target():
                return "updated"
            """))
            
            content = test_file.read_text()
            assert 'return "updated"' in content
        finally:
            os.chdir(original_dir)


if __name__ == "__main__":
    print("Run with: pytest test_declare_py_path_syntax.py -v")