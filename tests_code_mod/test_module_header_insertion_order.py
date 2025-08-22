#!/usr/bin/env python3
"""
Test to verify that declarations are never inserted before the module header.
This ensures that when both module_header and declare operations are used,
the header always comes first and declarations come after it.

Place this in: tests_code_mod/test_module_header_insertion_order.py
"""
import textwrap
from pathlib import Path
import pytest
from code_mod_defs import apply_modification_set, modification_description, module_header, declare


class TestModuleHeaderInsertionOrder:
    """Test that declarations respect module header boundaries"""
    
    def test_declare_after_module_header_replacement(self, tmp_path):
        """Test that declare inserts after module_header when both are used"""
        test_file = tmp_path / "ordering_test.py"
        test_file.write_text(textwrap.dedent("""
        import os
        OLD_CONFIG = "old"
        
        def existing_function():
            return "exists"
        """).strip())
        
        # Apply both module_header and declare operations
        modifications = [
            (modification_description, ("Update header and add new function",), {}),
            (module_header, (str(test_file), textwrap.dedent("""
            #!/usr/bin/env python3
            '''Modern module with enhanced configuration'''
            import sys
            import logging
            from pathlib import Path
            
            # New configuration
            NEW_CONFIG = "modern"
            DEBUG = True
            
            # Initialize logging
            logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)
            logger = logging.getLogger(__name__)
            """).strip()), {}),
            (declare, (str(test_file), "new_function", textwrap.dedent("""
            def new_function():
                '''Newly added function'''
                logger.info("New function called")
                return "new"
            """).strip()), {}),
        ]
        
        # Apply without git to avoid repository issues
        module_header(str(test_file), modifications[1][1][1])

        print("=== DEBUG: After module_header ===")
        content_after_header = test_file.read_text()
        for i, line in enumerate(content_after_header.split('\n')):
            print(f"{i:2}: {line}")
        declare(str(test_file), "new_function", modifications[2][1][2])  # Fixed: [2] not [1]
        
        content = test_file.read_text()
        print("=== DEBUG: After declare ===")
        for i, line in enumerate(content.split('\n')):
            print(f"{i:2}: {line}")
        print("=== END DEBUG ===")

        lines = content.split('\n')
        
        # Find key elements
        shebang_line = next((i for i, line in enumerate(lines) if line.startswith('#!/usr/bin/env python3')), -1)
        import_sys_line = next((i for i, line in enumerate(lines) if 'import sys' in line), -1)
        config_line = next((i for i, line in enumerate(lines) if 'NEW_CONFIG = "modern"' in line), -1)
        logger_line = next((i for i, line in enumerate(lines) if 'logger = logging.getLogger(__name__)' in line), -1)
        new_func_line = next((i for i, line in enumerate(lines) if 'def new_function():' in line), -1)
        existing_func_line = next((i for i, line in enumerate(lines) if 'def existing_function():' in line), -1)
        
        # Verify order: shebang -> imports -> config -> logger -> new function -> existing function
        assert shebang_line < import_sys_line, "Shebang should come before imports"
        assert import_sys_line < config_line, "Imports should come before config"
        assert config_line < logger_line, "Config should come before logger"
        assert logger_line < new_func_line, "Header (logger) should come before new function"
        assert existing_func_line < new_func_line, "Existing function should come before new function"
        
        # Verify old header elements are gone
        assert "import os" not in content
        assert "OLD_CONFIG" not in content
        
        # Verify new header elements are present
        assert "#!/usr/bin/env python3" in content
        assert "import sys" in content
        assert "NEW_CONFIG = \"modern\"" in content
        assert "logger = logging.getLogger(__name__)" in content
        
        # Verify functions are present
        assert "def new_function():" in content
        assert "def existing_function():" in content


    def test_multiple_declares_after_module_header(self, tmp_path):
        """Test multiple declare operations after module_header"""
        test_file = tmp_path / "multi_declare.py"
        test_file.write_text("def old_func():\n    pass\n")
        
        # Apply header first, then multiple declarations
        module_header(str(test_file), textwrap.dedent("""
        #!/usr/bin/env python3
        '''Module with multiple new functions'''
        import json
        import requests
        
        API_BASE = "https://api.example.com"
        TIMEOUT = 30
        """).strip())
        
        declare(str(test_file), "fetch_data", textwrap.dedent("""
        def fetch_data(endpoint):
            '''Fetch data from API'''
            url = f"{API_BASE}/{endpoint}"
            response = requests.get(url, timeout=TIMEOUT)
            return response.json()
        """).strip())
        
        declare(str(test_file), "process_data", textwrap.dedent("""
        def process_data(data):
            '''Process API data'''
            return {k: v for k, v in data.items() if v is not None}
        """).strip())
        
        content = test_file.read_text()
        lines = content.split('\n')
        
        # Find positions
        shebang_pos = next((i for i, line in enumerate(lines) if line.startswith('#!/usr/bin/env python3')), -1)
        api_base_pos = next((i for i, line in enumerate(lines) if 'API_BASE = ' in line), -1)
        fetch_func_pos = next((i for i, line in enumerate(lines) if 'def fetch_data(' in line), -1)
        process_func_pos = next((i for i, line in enumerate(lines) if 'def process_data(' in line), -1)
        old_func_pos = next((i for i, line in enumerate(lines) if 'def old_func():' in line), -1)
        
        # Verify correct ordering
        assert shebang_pos < api_base_pos, "Shebang should come before header constants"
        assert api_base_pos < fetch_func_pos, "Header constants should come before new functions"
        assert fetch_func_pos < process_func_pos, "Functions should be in insertion order"
        assert old_func_pos < process_func_pos, "Existing functions should come before new functions"


    def test_declare_insertion_respects_main_block(self, tmp_path):
        """Test that declare inserts before __main__ block even after module_header"""
        test_file = tmp_path / "with_main.py"
        test_file.write_text(textwrap.dedent("""
        import sys
        
        if __name__ == '__main__':
            print("Original main")
        """).strip())
        
        # Apply header and declaration
        module_header(str(test_file), textwrap.dedent("""
        #!/usr/bin/env python3
        '''Application with main block'''
        import argparse
        import logging
        
        DEFAULT_LOG_LEVEL = "INFO"
        """).strip())
        
        declare(str(test_file), "setup_logging", textwrap.dedent("""
        def setup_logging(level=DEFAULT_LOG_LEVEL):
            '''Setup application logging'''
            logging.basicConfig(level=getattr(logging, level))
            return logging.getLogger(__name__)
        """).strip())
        
        content = test_file.read_text()
        lines = content.split('\n')
        
        # Find positions
        shebang_pos = next((i for i, line in enumerate(lines) if line.startswith('#!/usr/bin/env python3')), -1)
        default_log_pos = next((i for i, line in enumerate(lines) if 'DEFAULT_LOG_LEVEL = ' in line), -1)
        setup_func_pos = next((i for i, line in enumerate(lines) if 'def setup_logging(' in line), -1)
        main_block_pos = next((i for i, line in enumerate(lines) if 'if __name__ == ' in line), -1)
        
        # Verify ordering
        assert shebang_pos < default_log_pos, "Shebang should come first"
        assert default_log_pos < setup_func_pos, "Header constants before functions"
        assert setup_func_pos < main_block_pos, "Functions should come before __main__ block"
        
        # Verify __main__ block is preserved
        assert "if __name__ == '__main__':" in content
        assert "print(\"Original main\")" in content


    def test_declare_never_before_imports(self, tmp_path):
        """Test that declare never inserts before import statements"""
        test_file = tmp_path / "import_order.py"
        test_file.write_text("def existing():\n    pass\n")
        
        # Apply header with imports
        module_header(str(test_file), textwrap.dedent("""
        #!/usr/bin/env python3
        # -*- coding: utf-8 -*-
        '''Module with proper import ordering'''
        
        # Standard library imports
        import os
        import sys
        from pathlib import Path
        
        # Third-party imports
        import requests
        import click
        
        # Configuration
        CONFIG_DIR = Path.home() / '.myapp'
        DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
        """).strip())
        
        declare(str(test_file), "initialize_config", textwrap.dedent("""
        def initialize_config():
            '''Initialize application configuration'''
            CONFIG_DIR.mkdir(exist_ok=True)
            return CONFIG_DIR / 'config.json'
        """).strip())
        
        content = test_file.read_text()
        lines = content.split('\n')
        
        # Find critical positions
        shebang_pos = next((i for i, line in enumerate(lines) if line.startswith('#!/usr/bin/env python3')), -1)
        import_os_pos = next((i for i, line in enumerate(lines) if line.strip() == 'import os'), -1)
        import_requests_pos = next((i for i, line in enumerate(lines) if line.strip() == 'import requests'), -1)
        config_dir_pos = next((i for i, line in enumerate(lines) if 'CONFIG_DIR = ' in line), -1)
        init_func_pos = next((i for i, line in enumerate(lines) if 'def initialize_config(' in line), -1)
        existing_func_pos = next((i for i, line in enumerate(lines) if 'def existing():' in line), -1)
        
        # Verify strict ordering
        assert shebang_pos < import_os_pos, "Shebang before imports"
        assert import_os_pos < import_requests_pos, "Standard imports before third-party"
        assert import_requests_pos < config_dir_pos, "Imports before configuration"
        assert config_dir_pos < init_func_pos, "Configuration before new functions"
        assert existing_func_pos < init_func_pos, "Existing functions before new functions"
        
        # Verify no function appears before any import
        all_import_lines = [i for i, line in enumerate(lines) if line.strip().startswith('import ') or line.strip().startswith('from ')]
        all_function_lines = [i for i, line in enumerate(lines) if 'def ' in line]
        
        if all_import_lines and all_function_lines:
            last_import = max(all_import_lines)
            first_function = min(all_function_lines)
            assert last_import < first_function, "All imports must come before any function definitions"


    def test_complex_interleaved_operations(self, tmp_path):
        """Test complex sequence of module_header and declare operations"""
        test_file = tmp_path / "complex.py"
        test_file.write_text(textwrap.dedent("""
        import old_module
        OLD_SETTING = "deprecated"
        
        def legacy_function():
            return "legacy"
        """).strip())
        
        # Sequence: header -> declare -> declare -> header (should replace) -> declare
        module_header(str(test_file), "import new_module\nNEW_SETTING = 'v1'")
        
        declare(str(test_file), "function_a", "def function_a():\n    return 'a'")
        
        declare(str(test_file), "function_b", "def function_b():\n    return 'b'")
        
        # Replace header again
        module_header(str(test_file), textwrap.dedent("""
        import newest_module
        import another_module
        NEWEST_SETTING = 'v2'
        FINAL_CONFIG = True
        """).strip())
        
        declare(str(test_file), "function_c", "def function_c():\n    return 'c'")
        
        content = test_file.read_text()

        print("=== DEBUG: Final file content ===")
        for i, line in enumerate(content.split('\n')):
            print(f"{i:2}: {line}")
        print("=== END DEBUG ===")

        lines = content.split('\n')
        
        # Find positions
        newest_import_pos = next((i for i, line in enumerate(lines) if 'import newest_module' in line), -1)
        final_config_pos = next((i for i, line in enumerate(lines) if 'FINAL_CONFIG = True' in line), -1)
        func_a_pos = next((i for i, line in enumerate(lines) if 'def function_a():' in line), -1)
        func_b_pos = next((i for i, line in enumerate(lines) if 'def function_b():' in line), -1)
        func_c_pos = next((i for i, line in enumerate(lines) if 'def function_c():' in line), -1)
        legacy_pos = next((i for i, line in enumerate(lines) if 'def legacy_function():' in line), -1)
        
        # Verify final header comes first
        assert newest_import_pos < final_config_pos, "Imports before config in header"
        assert final_config_pos < func_a_pos, "Header before all functions"
        assert final_config_pos < func_b_pos, "Header before all functions"
        assert final_config_pos < func_c_pos, "Header before all functions"
        assert final_config_pos < legacy_pos, "Header before all functions"
        
        # Verify old header elements are gone
        assert "import old_module" not in content
        assert "OLD_SETTING" not in content
        assert "NEW_SETTING" not in content  # From first header replacement
        
        # Verify final header elements are present
        assert "import newest_module" in content
        assert "FINAL_CONFIG = True" in content
        
        # Verify all functions are present and in correct order
        assert legacy_pos < func_a_pos < func_b_pos < func_c_pos, "Legacy function first, then new functions in declaration order"


if __name__ == "__main__":
    print("Run with: pytest test_module_header_insertion_order.py -v")
