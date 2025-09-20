#!/usr/bin/env python3
"""
Test case for declare function handling of decorators
Place this in: tests_code_mod/test_declare_decorators.py
"""
import textwrap
from pathlib import Path
import pytest
from code_mod_defs import declare


class TestDeclareWithDecorators:
    """Test that declare function properly handles decorated functions"""
    
    def test_single_decorator_function_replacement(self, tmp_path):
        """Test replacing a function with a single decorator"""
        test_file = tmp_path / "single_decorator.py"
        test_file.write_text(textwrap.dedent("""
        class MyClass:
            @property
            def value(self):
                return "old value"
        """))
        
        # Replace the decorated method
        declare(str(test_file), "MyClass.value", textwrap.dedent("""
        @property
        def value(self):
            return "new value"
        """))
        
        content = test_file.read_text()
        assert 'return "new value"' in content
        assert 'return "old value"' not in content
        assert '@property' in content
    
    def test_multiple_decorators_function_replacement(self, tmp_path):
        """Test replacing a function with multiple decorators"""
        test_file = tmp_path / "multi_decorator.py"
        test_file.write_text(textwrap.dedent("""
        import functools
        
        @functools.lru_cache(maxsize=128)
        @staticmethod
        def compute_value(x):
            return x * 2
        """))
        
        # Replace the multi-decorated function
        declare(str(test_file), "compute_value", textwrap.dedent("""
        @functools.lru_cache(maxsize=256)
        @staticmethod  
        def compute_value(x):
            return x * 3
        """))
        
        content = test_file.read_text()
        assert 'return x * 3' in content
        assert 'return x * 2' not in content
        assert '@functools.lru_cache(maxsize=256)' in content
        assert '@staticmethod' in content
    
    def test_multi_declaration_with_decorators(self, tmp_path):
        """Test multi-declaration parsing with decorated functions"""
        test_file = tmp_path / "multi_with_decorators.py"
        test_file.write_text(textwrap.dedent("""
        class Calculator:
            pass
        """))
        
        # Declare multiple functions, some with decorators
        declare(str(test_file), "Calculator.add", textwrap.dedent("""
        def add(self, a, b):
            return a + b

        @property
        def precision(self):
            return 2
            
        @staticmethod
        @functools.lru_cache(maxsize=100)
        def multiply(a, b):
            return a * b
        """))
        
        content = test_file.read_text()
        
        # All three functions should be present
        assert 'def add(self, a, b):' in content
        assert 'def precision(self):' in content  
        assert 'def multiply(a, b):' in content
        
        # Decorators should be preserved
        assert '@property' in content
        assert '@staticmethod' in content
        assert '@functools.lru_cache(maxsize=100)' in content
        
        # All should be inside the Calculator class
        lines = content.split('\n')
        calc_line = next(i for i, line in enumerate(lines) if 'class Calculator:' in line)
        add_line = next(i for i, line in enumerate(lines) if 'def add(self, a, b):' in line)
        precision_line = next(i for i, line in enumerate(lines) if 'def precision(self):' in line)
        multiply_line = next(i for i, line in enumerate(lines) if 'def multiply(a, b):' in line)
        
        assert calc_line < add_line < precision_line < multiply_line
    
    def test_decorated_async_function(self, tmp_path):
        """Test handling of decorated async functions"""
        test_file = tmp_path / "async_decorator.py"
        test_file.write_text(textwrap.dedent("""
        import asyncio
        
        async def old_async_func():
            return "old"
        """))
        
        # Replace with decorated async function
        declare(str(test_file), "old_async_func", textwrap.dedent("""
        @asyncio.coroutine
        async def old_async_func():
            await asyncio.sleep(0.1)
            return "new async"
        """))
        
        content = test_file.read_text()
        assert '@asyncio.coroutine' in content
        assert 'async def old_async_func():' in content
        assert 'return "new async"' in content
        assert 'return "old"' not in content
    
    def test_decorator_with_complex_arguments(self, tmp_path):
        """Test decorators with complex arguments and multiple lines"""
        test_file = tmp_path / "complex_decorator.py"
        test_file.write_text(textwrap.dedent("""
        def simple_func():
            return "simple"
        """))
        
        # Replace with function having complex decorator
        declare(str(test_file), "simple_func", textwrap.dedent("""
        @app.route('/api/users/<int:user_id>', 
                   methods=['GET', 'POST'],
                   defaults={'format': 'json'})
        @login_required
        @cache.memoize(timeout=300)
        def simple_func():
            return "complex decorated"
        """))
        
        content = test_file.read_text()
        assert "@app.route('/api/users/<int:user_id>'" in content
        assert "methods=['GET', 'POST']" in content
        assert "@login_required" in content
        assert "@cache.memoize(timeout=300)" in content
        assert 'return "complex decorated"' in content
        assert 'return "simple"' not in content
    
    def test_mixed_decorated_and_non_decorated_multi_declaration(self, tmp_path):
        """Test mixing decorated and non-decorated functions in multi-declaration"""
        test_file = tmp_path / "mixed_decorators.py"
        test_file.write_text("")
        
        # Declare multiple functions, mixing decorated and plain
        declare(str(test_file), "plain_func", textwrap.dedent("""
        def plain_func():
            return "plain"

        @property  
        def decorated_func(self):
            return "decorated"
            
        def another_plain():
            return "also plain"
            
        @staticmethod
        @functools.wraps(lambda x: x)
        def complex_decorated():
            return "complex"
        """))
        
        content = test_file.read_text()
        
        # All functions should be present
        assert 'def plain_func():' in content
        assert 'def decorated_func(self):' in content
        assert 'def another_plain():' in content  
        assert 'def complex_decorated():' in content
        
        # Decorators should be preserved where expected
        assert '@property' in content
        assert '@staticmethod' in content
        assert '@functools.wraps' in content
        
        # Count function definitions to ensure no duplicates
        assert content.count('def plain_func():') == 1
        assert content.count('def decorated_func(self):') == 1
        assert content.count('def another_plain():') == 1
        assert content.count('def complex_decorated():') == 1
    
    def test_decorator_parsing_edge_cases(self, tmp_path):
        """Test edge cases in decorator parsing"""
        test_file = tmp_path / "edge_cases.py"
        test_file.write_text("")
        
        # Test various decorator formats that might cause issues
        declare(str(test_file), "edge_func", textwrap.dedent("""
        # Comment before decorator
        @decorator_with_underscores_123
        def edge_func():
            return "edge case 1"

        @module.submodule.decorator(
            arg1="value1",
            arg2="value2"
        )
        def another_edge():
            return "edge case 2"
            
        @lambda_decorator(lambda x: x.upper())
        def lambda_decorated():
            return "lambda case"
        """))
        
        content = test_file.read_text()
        
        # All functions should be detected and present
        assert 'def edge_func():' in content
        assert 'def another_edge():' in content
        assert 'def lambda_decorated():' in content
        
        # Decorators should be preserved
        assert '@decorator_with_underscores_123' in content
        assert '@module.submodule.decorator(' in content
        assert '@lambda_decorator(lambda x: x.upper())' in content
    
    def test_pytest_parametrize_decorator(self, tmp_path):
        """Test the specific pytest.mark.parametrize decorator that was failing"""
        test_file = tmp_path / "pytest_test.py"
        test_file.write_text("import pytest\n")
        
        # Test the exact decorator format that was failing
        declare(str(test_file), "test_mdl_ordering_and_sign", textwrap.dedent("""
        @pytest.mark.parametrize("delta", [1e-3, 1e-2, 0.1])
        def test_mdl_ordering_and_sign(delta):
            assert delta > 0
            return delta * 2
        """))
        
        content = test_file.read_text()
        
        # Function should be correctly identified and added
        assert 'def test_mdl_ordering_and_sign(delta):' in content
        assert '@pytest.mark.parametrize("delta", [1e-3, 1e-2, 0.1])' in content
        assert 'assert delta > 0' in content
    
    def test_multiline_decorator_with_complex_args(self, tmp_path):
        """Test decorators with complex multiline arguments"""
        test_file = tmp_path / "multiline_decorator.py"
        test_file.write_text("")
        
        # Test decorator that spans multiple lines with complex arguments
        declare(str(test_file), "complex_test", textwrap.dedent("""
        @pytest.mark.parametrize(
            "input_val,expected",
            [
                (1, 2),
                (2, 4),
                (3, 6)
            ]
        )
        def complex_test(input_val, expected):
            assert input_val * 2 == expected

        @app.route(
            '/api/v1/users/<int:user_id>/profile',
            methods=['GET', 'POST', 'PUT'],
            defaults={'format': 'json', 'version': 'v1'}
        )
        @login_required
        def user_profile_handler(user_id):
            return {"user_id": user_id}
        """))
        
        content = test_file.read_text()
        
        # Both functions should be correctly identified despite complex multiline decorators
        assert 'def complex_test(input_val, expected):' in content
        assert 'def user_profile_handler(user_id):' in content
        assert '@pytest.mark.parametrize(' in content
        assert '@app.route(' in content
        assert '@login_required' in content
        
        # Verify no duplicates created
        assert content.count('def complex_test(') == 1
        assert content.count('def user_profile_handler(') == 1
    
    def test_decorator_name_inference_debugging(self, tmp_path):
        """Test to debug the specific name inference logic with decorators"""
        from code_mod_defs import declare
        
        # Test the internal parsing logic directly
        test_code = textwrap.dedent("""
        @property
        def decorated_method(self):
            return "test"

        def plain_method(self):
            return "plain"
        """)
        
        # This should not fail when declare tries to parse multiple declarations
        test_file = tmp_path / "debug_test.py"
        test_file.write_text("class TestClass:\n    pass\n")
        
        # This call should work without errors and correctly identify both methods
        declare(str(test_file), "TestClass.decorated_method", test_code)
        
        content = test_file.read_text()
        
        # Both methods should be added to the class
        assert 'def decorated_method(self):' in content
        assert 'def plain_method(self):' in content
        assert '@property' in content


if __name__ == "__main__":
    print("Run with: pytest test_declare_decorators.py -v")
