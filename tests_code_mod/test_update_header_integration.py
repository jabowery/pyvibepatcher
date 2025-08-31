#!/usr/bin/env python3
"""
Integration tests for update_header with the full modification system.
Place this in: tests_code_mod/test_update_header_integration.py
"""

import textwrap
from pathlib import Path
import subprocess
import pytest
from code_mod_defs import apply_modification_set, modification_description, update_header


class TestModuleHeaderIntegrationWithGit:
    """Integration tests with git rollback system"""
    
    def test_update_header_creates_commit(self, tmp_git_repo):
        """Test that update_header modifications create proper git commits"""
        repo, chdir = tmp_git_repo
        with chdir(repo):
            # Create initial Python file
            test_file = Path("app.py")
            test_file.write_text(textwrap.dedent("""
            import os
            OLD_CONFIG = "legacy"
            
            def main():
                print("Hello World")
            """))
            
            # Add and commit initial version
            subprocess.run(["git", "add", "app.py"], check=True)
            subprocess.run(["git", "commit", "-m", "Initial app"], check=True)
            
            initial_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip()
            
            # Apply update_header modification
            modifications = [
                (modification_description, ("Modernize app header",), {}),
                (update_header, (str(test_file), textwrap.dedent("""
                #!/usr/bin/env python3
                '''Modern Python application'''
                import sys
                import logging
                
                NEW_CONFIG = "modern"
                
                # Setup logging
                logging.basicConfig(level=logging.INFO)
                logger = logging.getLogger(__name__)
                """).strip()), {}),
            ]
            
            manager = apply_modification_set(modifications, auto_commit=True)
            
            # Verify new commit was created
            final_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip()
            
            assert final_commit != initial_commit
            
            # Verify file was modified correctly
            content = test_file.read_text()
            assert "#!/usr/bin/env python3" in content
            assert "NEW_CONFIG = \"modern\"" in content
            assert "logger = logging.getLogger(__name__)" in content
            assert "OLD_CONFIG = \"legacy\"" not in content
            assert "def main():" in content  # Function preserved
            
            # Verify commit message
            commit_msg = subprocess.check_output(
                ["git", "log", "-1", "--pretty=format:%s"], text=True
            ).strip()
            assert "Modernize app header" in commit_msg


    def test_update_header_rollback_functionality(self, tmp_git_repo):
        """Test rollback works correctly with update_header modifications"""
        repo, chdir = tmp_git_repo
        with chdir(repo):
            test_file = Path("service.py")
            original_content = textwrap.dedent("""
            '''Original service module'''
            import requests
            import json
            
            API_URL = "https://api.example.com"
            TIMEOUT = 30
            
            def fetch_data():
                response = requests.get(API_URL, timeout=TIMEOUT)
                return response.json()
            
            if __name__ == "__main__":
                data = fetch_data()
                print(json.dumps(data, indent=2))
            """)
            
            test_file.write_text(original_content)
            subprocess.run(["git", "add", "service.py"], check=True)
            subprocess.run(["git", "commit", "-m", "Original service"], check=True)
            
            # Apply modifications
            modifications = [
                (modification_description, ("Upgrade service with async support",), {}),
                (update_header, (str(test_file), textwrap.dedent("""
                '''Async service module with enhanced features'''
                import asyncio
                import aiohttp
                import json
                from pathlib import Path
                import logging
                
                # Enhanced configuration
                API_URL = "https://api-v2.example.com"
                TIMEOUT = aiohttp.ClientTimeout(total=60)
                CACHE_DIR = Path("cache")
                
                # Setup
                logging.basicConfig(level=logging.DEBUG)
                logger = logging.getLogger(__name__)
                CACHE_DIR.mkdir(exist_ok=True)
                """).strip()), {}),
            ]
            
            manager = apply_modification_set(modifications, auto_commit=True)
            
            # Verify changes applied
            content = test_file.read_text()
            assert "import asyncio" in content
            assert "import aiohttp" in content
            assert "API_URL = \"https://api-v2.example.com\"" in content
            assert "import requests" not in content
            assert "def fetch_data():" in content  # Function preserved
            
            # Test rollback
            rollback_success = manager.hard_rollback()
            assert rollback_success
            
            # Verify rollback restored original state
            restored_content = test_file.read_text()
            assert restored_content.strip() == original_content.strip()
            assert "import requests" in restored_content
            assert "import asyncio" not in restored_content


class TestModuleHeaderWithOtherModifications:
    """Test update_header combined with other modification types"""
    
    def test_update_header_with_declare_modifications(self, tmp_git_repo):
        """Test update_header combined with declare modifications"""
        repo, chdir = tmp_git_repo
        with chdir(repo):
            from code_mod_defs import declare
            
            test_file = Path("calculator.py")
            test_file.write_text(textwrap.dedent("""
            import math
            PI = 3.14159
            
            def add(a, b):
                return a + b
            
            def multiply(a, b):
                return a * b
            """))
            
            subprocess.run(["git", "add", "calculator.py"], check=True)
            subprocess.run(["git", "commit", "-m", "Initial calculator"], check=True)
            
            # Apply combined modifications
            modifications = [
                (modification_description, ("Enhance calculator with better precision and new functions",), {}),
                (update_header, (str(test_file), textwrap.dedent("""
                '''Enhanced calculator with high precision math'''
                from decimal import Decimal, getcontext
                import math
                
                # High precision configuration
                getcontext().prec = 50
                PI = Decimal('3.1415926535897932384626433832795028841971693993751')
                E = Decimal('2.7182818284590452353602874713526624977572470937000')
                """).strip()), {}),
                (declare, (str(test_file), "subtract", textwrap.dedent("""
                def subtract(a, b):
                    '''Subtract b from a with high precision'''
                    return Decimal(str(a)) - Decimal(str(b))
                """).strip()), {}),
                (declare, (str(test_file), "divide", textwrap.dedent("""
                def divide(a, b):
                    '''Divide a by b with high precision'''
                    if b == 0:
                        raise ValueError("Cannot divide by zero")
                    return Decimal(str(a)) / Decimal(str(b))
                """).strip()), {}),
            ]
            
            manager = apply_modification_set(modifications, auto_commit=True)
            
            content = test_file.read_text()
            
            # Verify header changes
            assert "from decimal import Decimal, getcontext" in content
            assert "getcontext().prec = 50" in content
            assert "PI = Decimal(" in content
            assert "PI = 3.14159" not in content
            
            # Verify original functions preserved
            assert "def add(a, b):" in content
            assert "def multiply(a, b):" in content
            
            # Verify new functions added
            assert "def subtract(a, b):" in content
            assert "def divide(a, b):" in content
            assert "Cannot divide by zero" in content


    def test_update_header_with_file_operations(self, tmp_git_repo):
        """Test update_header with create_file and move_file operations"""
        repo, chdir = tmp_git_repo
        with chdir(repo):
            from code_mod_defs import create_file, move_file
            
            # Create initial structure
            Path("old_utils.py").write_text(textwrap.dedent("""
            import os
            DEBUG = False
            
            def helper():
                return "old helper"
            """))
            
            subprocess.run(["git", "add", "old_utils.py"], check=True)
            subprocess.run(["git", "commit", "-m", "Initial utils"], check=True)
            
            modifications = [
                (modification_description, ("Restructure project with modern utilities",), {}),
                (create_file, ("src/config.py", textwrap.dedent("""
                '''Configuration module'''
                from pathlib import Path
                
                BASE_DIR = Path(__file__).parent.parent
                DEBUG = True
                LOG_LEVEL = "INFO"
                """).strip(),), {"make_executable": False}),
                (move_file, ("old_utils.py", "src/utils.py"), {}),
                (update_header, ("src/utils.py", textwrap.dedent("""
                '''Modern utility functions'''
                import logging
                from pathlib import Path
                from .config import DEBUG, LOG_LEVEL
                
                # Setup logging
                logging.basicConfig(level=getattr(logging, LOG_LEVEL))
                logger = logging.getLogger(__name__)
                """).strip()), {}),
            ]
            
            manager = apply_modification_set(modifications, auto_commit=True)
            
            # Verify file structure
            assert Path("src/config.py").exists()
            assert Path("src/utils.py").exists()
            assert not Path("old_utils.py").exists()
            
            # Verify config file
            config_content = Path("src/config.py").read_text()
            assert "BASE_DIR = Path(__file__).parent.parent" in config_content
            
            # Verify utils file with new header
            utils_content = Path("src/utils.py").read_text()
            assert "from .config import DEBUG, LOG_LEVEL" in utils_content
            assert "logger = logging.getLogger(__name__)" in utils_content
            assert "import os" not in utils_content  # Old header gone
            assert "def helper():" in utils_content  # Function preserved


class TestModuleHeaderParsingIntegration:
    """Test update_header parsing within the modification file system"""
    
    def test_parse_update_header_from_file(self, tmp_path):
        """Test parsing update_header directive from modification file"""
        from modify_code import parse_modification_file
        
        mod_file = tmp_path / "header_mods.txt"
        mod_file.write_text(textwrap.dedent("""
        MMM modification_description MMM
        Update application header for production deployment
        @@@@@@
        MMM update_header MMM
        app/main.py
        @@@@@@
        #!/usr/bin/env python3
        '''Production-ready Flask application'''
        
        from flask import Flask, request, jsonify, g
        from flask_cors import CORS
        import logging
        import os
        import sys
        from pathlib import Path
        
        # Production configuration
        BASE_DIR = Path(__file__).parent
        DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
        SECRET_KEY = os.getenv('SECRET_KEY') or 'fallback-secret-key'
        
        # Database configuration
        DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{BASE_DIR}/app.db')
        
        # Initialize Flask with production settings
        app = Flask(__name__)
        CORS(app, origins=os.getenv('ALLOWED_ORIGINS', '*').split(','))
        
        app.config.update({
            'DEBUG': DEBUG,
            'SECRET_KEY': SECRET_KEY,
            'DATABASE_URL': DATABASE_URL,
            'JSON_SORT_KEYS': False
        })
        
        # Production logging
        if not DEBUG:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
                handlers=[
                    logging.FileHandler('app.log'),
                    logging.StreamHandler(sys.stdout)
                ]
            )
        
        logger = logging.getLogger(__name__)
        logger.info('Application starting in %s mode', 'DEBUG' if DEBUG else 'PRODUCTION')
        """).strip())
        
        modifications = parse_modification_file(str(mod_file))
        
        assert len(modifications) == 2
        
        # First modification should be description
        desc_func, desc_args, desc_kwargs = modifications[0]
        assert desc_func.__name__ == "modification_description"
        assert desc_args[0] == "Update application header for production deployment"
        
        # Second modification should be update_header
        header_func, header_args, header_kwargs = modifications[1]
        assert header_func.__name__ == "update_header"
        assert header_args[0] == "app/main.py"
        
        header_content = header_args[1]
        assert "#!/usr/bin/env python3" in header_content
        assert "'''Production-ready Flask application'''" in header_content
        assert "from flask_cors import CORS" in header_content
        assert "DATABASE_URL = os.getenv('DATABASE_URL'" in header_content
        assert "logger.info('Application starting" in header_content


    def test_end_to_end_modification_workflow(self, tmp_git_repo, tmp_path):
        """Complete end-to-end test using the main script workflow"""
        repo, chdir = tmp_git_repo
        with chdir(repo):
            # Create initial application structure
            app_file = Path("web_app.py")
            app_file.write_text(textwrap.dedent("""
            from flask import Flask
            import os
            
            DEBUG = True
            app = Flask(__name__)
            
            @app.route('/')
            def home():
                return 'Hello World'
            
            if __name__ == '__main__':
                app.run(debug=DEBUG)
            """))
            
            subprocess.run(["git", "add", "web_app.py"], check=True)
            subprocess.run(["git", "commit", "-m", "Initial web app"], check=True)
            
            # Create modification file
            mod_file = tmp_path / "production_upgrade.txt"
            mod_file.write_text(textwrap.dedent("""
            MMM modification_description MMM
            Upgrade web application for production deployment with proper configuration
            @@@@@@
            MMM update_header MMM
            web_app.py
            @@@@@@
            #!/usr/bin/env python3
            '''Production Flask Web Application'''
            
            from flask import Flask, request, jsonify
            import logging
            import os
            import sys
            from pathlib import Path
            
            # Production configuration
            BASE_DIR = Path(__file__).parent
            DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
            SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
            HOST = os.getenv('HOST', '0.0.0.0')
            PORT = int(os.getenv('PORT', 5000))
            
            # Initialize Flask application
            app = Flask(__name__)
            app.config.update({
                'DEBUG': DEBUG,
                'SECRET_KEY': SECRET_KEY,
                'TESTING': False
            })
            
            # Configure logging for production
            if not DEBUG:
                logging.basicConfig(
                    level=logging.INFO,
                    format='%(asctime)s %(name)s %(levelname)s: %(message)s'
                )
            
            logger = logging.getLogger(__name__)
            logger.info('Starting application in %s mode', 'DEBUG' if DEBUG else 'PRODUCTION')
            """).strip())
            
            # Parse and apply modifications (simulating main script behavior)
            from modify_code import parse_modification_file
            
            modifications = parse_modification_file(str(mod_file))
            manager = apply_modification_set(modifications, auto_commit=True)
            
            # Verify the complete transformation
            final_content = app_file.read_text()
            
            # New header elements
            assert "#!/usr/bin/env python3" in final_content
            assert "'''Production Flask Web Application'''" in final_content
            assert "from flask import Flask, request, jsonify" in final_content
            assert "BASE_DIR = Path(__file__).parent" in final_content
            assert "SECRET_KEY = os.getenv('SECRET_KEY'," in final_content
            assert "logger.info('Starting application" in final_content
            
            # Old header elements should be gone
            assert "from flask import Flask" not in final_content or "from flask import Flask, request, jsonify" in final_content
            assert "DEBUG = True" not in final_content
            
            # Original application logic preserved
            assert "@app.route('/')" in final_content
            assert "def home():" in final_content
            assert "return 'Hello World'" in final_content
            assert "if __name__ == '__main__':" in final_content
            
            # Verify git commit was created
            commit_msg = subprocess.check_output(
                ["git", "log", "-1", "--pretty=format:%s"], text=True
            ).strip()
            assert "Upgrade web application for production deployment" in commit_msg
            
            print("✓ End-to-end update_header workflow test completed successfully")


if __name__ == "__main__":
    print("Module Header Integration Test Suite")
    print("Run with: pytest test_update_header_integration.py -v")
