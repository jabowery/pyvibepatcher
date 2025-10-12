#!/usr/bin/env python3
"""
Test case for declare function handling of pre-indented code.
Place this in: tests_code_mod/test_declare_indented_code.py
"""
import textwrap
from pathlib import Path
import pytest
from code_mod_defs import declare


class TestDeclareWithIndentedCode:
    """Test that declare properly handles pre-indented code"""
    
    def test_method_with_leading_indentation(self, tmp_path):
        """Test that method code with leading indentation is handled correctly"""
        test_file = tmp_path / "test_class.py"
        test_file.write_text(textwrap.dedent("""
        class MyClass:
            def old_method(self):
                return "old"
        """))
        
        # Provide code WITH indentation (as if user tried to be helpful)
        indented_code = """    def old_method(self):
        return "new"
    """
        
        # This should work despite the indentation
        declare(str(test_file), "MyClass.old_method", indented_code)
        
        content = test_file.read_text()
        assert 'return "new"' in content
        assert 'return "old"' not in content
        assert 'def old_method(self):' in content
    
    def test_method_with_decorator_and_indentation(self, tmp_path):
        """Test decorated method with leading indentation"""
        test_file = tmp_path / "decorated_class.py"
        test_file.write_text(textwrap.dedent("""
        class Calculator:
            def compute(self, x):
                return x * 2
        """))
        
        # Indented code with decorator (like the original bug report)
        indented_code = """    @torch.no_grad()
    def compute(self, x):
        return x * 3
    """
        
        declare(str(test_file), "Calculator.compute", indented_code)
        
        content = test_file.read_text()
        assert '@torch.no_grad()' in content
        assert 'return x * 3' in content
        assert 'return x * 2' not in content
    
    def test_deeply_indented_method(self, tmp_path):
        """Test method with excessive indentation (e.g., copied from nested context)"""
        test_file = tmp_path / "nested_class.py"
        test_file.write_text(textwrap.dedent("""
        class Outer:
            class Inner:
                def method(self):
                    return "old"
        """))
        
        # Very indented code (8 spaces)
        deeply_indented = """        def method(self):
            return "new"
        """
        
        declare(str(test_file), "Outer.Inner.method", deeply_indented)
        
        content = test_file.read_text()
        assert 'return "new"' in content
        assert 'return "old"' not in content
    
    def test_mixed_indentation_multi_declaration(self, tmp_path):
        """Test multiple declarations with indentation"""
        test_file = tmp_path / "multi_methods.py"
        test_file.write_text(textwrap.dedent("""
        class DataProcessor:
            pass
        """))
        
        # Multiple methods with indentation
        indented_multi = """    def process(self, data):
        return data.upper()

    @property
    def name(self):
        return "processor"
    
    def validate(self, data):
        return len(data) > 0
    """
        
        declare(str(test_file), "DataProcessor.process", indented_multi)
        
        content = test_file.read_text()
        
        # All methods should be present
        assert 'def process(self, data):' in content
        assert 'def name(self):' in content
        assert 'def validate(self, data):' in content
        assert '@property' in content
        assert 'return data.upper()' in content
        assert 'return "processor"' in content
        assert 'return len(data) > 0' in content
    
    def test_top_level_function_with_indentation(self, tmp_path):
        """Test top-level function with unnecessary indentation"""
        test_file = tmp_path / "module.py"
        test_file.write_text(textwrap.dedent("""
        def old_function():
            return "old"
        """))
        
        # Indented top-level function (should still work)
        indented_func = """    def old_function():
        return "new"
    """
        
        declare(str(test_file), "old_function", indented_func)
        
        content = test_file.read_text()
        assert 'return "new"' in content
        assert 'return "old"' not in content
    
    def test_assignment_with_indentation(self, tmp_path):
        """Test assignment with leading indentation"""
        test_file = tmp_path / "config.py"
        test_file.write_text(textwrap.dedent("""
        class Config:
            DEBUG = False
        """))
        
        # Indented assignment
        indented_assign = """    DEBUG = True
    """
        
        declare(str(test_file), "Config.DEBUG", indented_assign)
        
        content = test_file.read_text()
        assert 'DEBUG = True' in content
        assert 'DEBUG = False' not in content
    
    def test_real_world_torch_example(self, tmp_path):
        """Test the exact scenario from the bug report"""
        test_file = tmp_path / "mdlloss_flow.py"
        test_file.write_text(textwrap.dedent("""
        import torch
        
        class MDLLossFlow:
            def compute_gaussian_nll_bits(self, residuals):
                # Old implementation
                return residuals.sum()
        """))
        
        # Exact code from bug report with indentation
        indented_method = """    @torch.no_grad()
    def compute_gaussian_nll_bits(self, residuals: torch.Tensor) -> torch.Tensor:
        \"\"\"
        Compute Gaussian NLL in bits for residuals.
        Uses robust MAD-based scale estimation.
        
        Args:
            residuals: [n, d] residuals in log1p space
            
        Returns:
            Scalar tensor: total NLL in bits
        \"\"\"
        r64 = residuals.to(torch.float64)
        
        # Robust scale estimation per feature
        mad = torch.median(torch.abs(r64 - torch.median(r64, dim=0).values), dim=0).values.clamp_min(1e-12)
        sigma = 1.4826 * mad
        sigma = torch.maximum(sigma, torch.full_like(sigma, 1e-3))
        
        # Gaussian NLL in bits
        n = r64.shape[0]
        nll_bits = 0.5 * torch.sum((r64 / sigma.unsqueeze(0))**2) / torch.log(torch.tensor(2.0, dtype=torch.float64))
        
        # Add normalization constant: -log2(sqrt(2π)σ) per sample per feature
        norm_bits = n * torch.sum(0.5 * torch.log2(2.0 * torch.pi * sigma**2))
        
        return nll_bits + norm_bits
    """
        
        # This should work now with the fix
        declare(str(test_file), "MDLLossFlow.compute_gaussian_nll_bits", indented_method)
        
        content = test_file.read_text()
        
        # Verify the new implementation is present
        assert '@torch.no_grad()' in content
        assert 'def compute_gaussian_nll_bits(self, residuals: torch.Tensor) -> torch.Tensor:' in content
        assert 'Compute Gaussian NLL in bits for residuals.' in content
        assert 'r64 = residuals.to(torch.float64)' in content
        assert 'mad = torch.median' in content
        assert 'nll_bits + norm_bits' in content
        
        # Old implementation should be gone
        assert 'return residuals.sum()' not in content
        
        # Verify it's properly indented inside the class
        lines = content.split('\n')
        decorator_line = next(i for i, line in enumerate(lines) if '@torch.no_grad()' in line)
        def_line = next(i for i, line in enumerate(lines) if 'def compute_gaussian_nll_bits' in line)
        
        # Both should be indented (not at column 0)
        assert lines[decorator_line].startswith('    ')
        assert lines[def_line].startswith('    ')
    
    def test_tabs_and_spaces_mix(self, tmp_path):
        """Test handling of mixed tabs and spaces (dedent handles this)"""
        test_file = tmp_path / "mixed_indent.py"
        test_file.write_text(textwrap.dedent("""
        class MixedClass:
            def method(self):
                return "old"
        """))
        
        # Code with tab indentation
        tab_indented = "\tdef method(self):\n\t\treturn 'new'\n"
        
        declare(str(test_file), "MixedClass.method", tab_indented)
        
        content = test_file.read_text()
        assert 'return \'new\'' in content or 'return "new"' in content
        assert 'return "old"' not in content
    
    def test_no_indentation_still_works(self, tmp_path):
        """Verify that code without indentation still works (regression test)"""
        test_file = tmp_path / "normal.py"
        test_file.write_text(textwrap.dedent("""
        class NormalClass:
            def method(self):
                return "old"
        """))
        
        # Code without any leading indentation (original expected format)
        normal_code = """def method(self):
    return "new"
"""
        
        declare(str(test_file), "NormalClass.method", normal_code)
        
        content = test_file.read_text()
        assert 'return "new"' in content
        assert 'return "old"' not in content


if __name__ == "__main__":
    print("Run with: pytest test_declare_indented_code.py -v")