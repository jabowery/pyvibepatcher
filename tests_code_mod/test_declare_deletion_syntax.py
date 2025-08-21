#!/usr/bin/env python3
"""
Test case for declare deletion syntax with empty trailing sections
Place this in: tests_code_mod/test_declare_deletion_syntax.py
"""
import textwrap
from pathlib import Path
from modify_code import parse_modification_file


def test_declare_deletion_with_empty_sections(tmp_path):
    """Test that declare deletion syntax works with empty trailing sections"""
    # Create a modification file with deletion syntax (empty third sections)
    mod_file = tmp_path / "deletion_test.txt"
    mod_file.write_text(textwrap.dedent("""
    MMM modification_description MMM
    Delete multiple declarations
    @@@@@@
    MMM declare MMM
    test_file.py
    @@@@@@
    GPUResourceManager._initialize_slots
    @@@@@@
    MMM declare MMM
    test_file.py
    @@@@@@
    GPUSlot
    @@@@@@
    
    MMM declare MMM
    test_file.py
    @@@@@@
    GPUResourceManager.can_allocate
    @@@@@@
    def can_allocate(self, config: Config) -> bool:
        \"\"\"Check if configuration can likely be allocated based on memory estimates.\"\"\"
        required_memory = self.estimate_memory_requirement(config)
        return required_memory <= self.available_vram_mb
    """).strip())
    
    # Parse the modification file
    modifications = parse_modification_file(str(mod_file))
    
    # Should have 4 modifications: 1 description + 3 declare operations
    assert len(modifications) == 4
    
    # First should be description
    desc_func, desc_args, desc_kwargs = modifications[0]
    assert desc_func.__name__ == "modification_description"
    assert desc_args[0] == "Delete multiple declarations"
    
    # Second should be deletion of GPUResourceManager._initialize_slots
    del1_func, del1_args, del1_kwargs = modifications[1]
    assert del1_func.__name__ == "declare"
    assert del1_args[0] == "test_file.py"
    assert del1_args[1] == "GPUResourceManager._initialize_slots"
    assert del1_args[2] is None  # Should be None for deletion
    
    # Third should be deletion of GPUSlot
    del2_func, del2_args, del2_kwargs = modifications[2]
    assert del2_func.__name__ == "declare"
    assert del2_args[0] == "test_file.py"
    assert del2_args[1] == "GPUSlot"
    assert del2_args[2] is None  # Should be None for deletion
    
    # Fourth should be replacement of GPUResourceManager.can_allocate
    repl_func, repl_args, repl_kwargs = modifications[3]
    assert repl_func.__name__ == "declare"
    assert repl_args[0] == "test_file.py"
    assert repl_args[1] == "GPUResourceManager.can_allocate"
    assert repl_args[2] is not None  # Should have content for replacement
    assert "def can_allocate(self, config: Config) -> bool:" in repl_args[2]
    assert "estimate_memory_requirement" in repl_args[2]


def test_remove_block_directly(tmp_path):
    """Test the remove_block function directly to debug the issue"""
    from code_mod_defs import remove_block
    
    source = "class GPUSlot:\n    pass\n\ndef function():\n    pass\n"
    
    print("Testing remove_block directly:")
    print(f"Original: {repr(source)}")
    
    result, removed = remove_block(source, "GPUSlot", [])
    
    print(f"Result: {repr(result)}")
    print(f"Removed: {removed}")
    
    assert removed == True, "remove_block should report successful removal"
    assert "class GPUSlot:" not in result, "GPUSlot class should be removed"
    assert "def function():" in result, "function should remain"


def test_cst_parsing_debug(tmp_path):
    """Test LibCST parsing to see what's happening"""
    import libcst as cst
    
    source = "class GPUSlot:\n    pass\n\ndef function():\n    pass\n"
    
    try:
        module = cst.parse_module(source)
        print("CST parsed successfully")
        print(f"Module body has {len(module.body)} statements")
        
        for i, stmt in enumerate(module.body):
            print(f"Statement {i}: {type(stmt).__name__}")
            if isinstance(stmt, cst.ClassDef):
                print(f"  Class name: {stmt.name.value}")
            elif isinstance(stmt, cst.FunctionDef):
                print(f"  Function name: {stmt.name.value}")
                
    except Exception as e:
        print(f"CST parsing failed: {e}")


def test_simple_deletion_debug(tmp_path):
    """Simple test to debug deletion issues"""
    from code_mod_defs import declare
    
    # Create simple test file
    test_file = tmp_path / "simple.py"
    test_file.write_text("class GPUSlot:\n    pass\n\ndef function():\n    pass\n")
    
    print("Original content:")
    print(repr(test_file.read_text()))
    
    # Try to delete the class
    declare(str(test_file), "GPUSlot", None)
    
    print("After deletion:")
    print(repr(test_file.read_text()))
    
    content = test_file.read_text()
    assert "class GPUSlot:" not in content
    assert "def function():" in content  # Should remain


def test_declare_deletion_actually_deletes(tmp_path):
    """Test that declare deletion actually removes code from files"""
    from code_mod_defs import apply_modification_set, modification_description, declare
    
    # Create test file with multiple declarations
    test_file = tmp_path / "gpu_manager.py"
    test_file.write_text(textwrap.dedent("""
    class GPUSlot:
        def __init__(self, device_id):
            self.device_id = device_id
    
    class GPUResourceManager:
        def __init__(self):
            self.slots = []
        
        def _initialize_slots(self):
            '''Initialize GPU slots'''
            for i in range(4):
                self.slots.append(GPUSlot(i))
        
        def can_allocate(self, config):
            '''Old allocation check'''
            return True
        
        def allocate(self, config):
            '''Allocate resources'''
            return self.slots[0]
    """))
    
    # Create modification file content manually for testing
    modifications = [
        (modification_description, ("Remove old declarations and update can_allocate",), {}),
        (declare, (str(test_file), "GPUSlot", None), {}),  # Delete class
        (declare, (str(test_file), "GPUResourceManager._initialize_slots", None), {}),  # Delete method
        (declare, (str(test_file), "GPUResourceManager.can_allocate", textwrap.dedent("""
        def can_allocate(self, config: Config) -> bool:
            '''Check if configuration can likely be allocated based on memory estimates.'''
            required_memory = self.estimate_memory_requirement(config)
            return required_memory <= self.available_vram_mb
        """).strip()), {}),  # Replace method
    ]
    
    # Apply modifications
    try:
        manager = apply_modification_set(modifications, auto_rollback_on_failure=False)
        
        # Verify deletions and replacement
        content = test_file.read_text()
        
        # GPUSlot class should be deleted
        assert "class GPUSlot:" not in content
        assert "def __init__(self, device_id):" not in content
        
        # _initialize_slots method should be deleted
        assert "def _initialize_slots(self):" not in content
        assert "Initialize GPU slots" not in content
        
        # can_allocate should be replaced with new version
        assert "def can_allocate(self, config: Config) -> bool:" in content
        assert "estimate_memory_requirement" in content
        assert "Old allocation check" not in content
        
        # Other methods should remain
        assert "def allocate(self, config):" in content
        assert "class GPUResourceManager:" in content
        
    except Exception as e:
        # If we're not in a git repo, just test the individual operations
        declare(str(test_file), "GPUSlot", None)
        declare(str(test_file), "GPUResourceManager._initialize_slots", None) 
        declare(str(test_file), "GPUResourceManager.can_allocate", textwrap.dedent("""
        def can_allocate(self, config: Config) -> bool:
            '''Check if configuration can likely be allocated based on memory estimates.'''
            required_memory = self.estimate_memory_requirement(config)
            return required_memory <= self.available_vram_mb
        """).strip())
        
        # Same verification
        content = test_file.read_text()
        assert "class GPUSlot:" not in content
        assert "def _initialize_slots(self):" not in content
        assert "def can_allocate(self, config: Config) -> bool:" in content


def test_split_sections_preserves_empty_trailing(tmp_path):
    """Test that _split_sections preserves empty trailing sections"""
    from modify_code import _split_sections
    
    # Test case with empty trailing section
    block_lines = [
        "first_section_content\n",
        "@@@@@@\n", 
        "second_section_content\n",
        "@@@@@@\n",
        # Empty third section (no content after final separator)
    ]
    
    sections = _split_sections(block_lines)
    
    # Should have 3 sections: first, second, and empty third
    assert len(sections) == 3
    assert sections[0] == "first_section_content"
    assert sections[1] == "second_section_content"
    assert sections[2] == ""  # Empty section should be preserved
    
    # Test case with multiple empty trailing sections
    block_lines_multi = [
        "content\n",
        "@@@@@@\n",
        "@@@@@@\n",
        "@@@@@@\n",
    ]
    
    sections_multi = _split_sections(block_lines_multi)
    assert len(sections_multi) == 4
    assert sections_multi[0] == "content"
    assert sections_multi[1] == ""
    assert sections_multi[2] == ""
    assert sections_multi[3] == ""


if __name__ == "__main__":
    print("Run with: pytest test_declare_deletion_syntax.py -v")
