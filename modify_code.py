#!/usr/bin/env python3
"""
Script to read and execute code modifications from a formatted file
Usage: python modify_code.py <modification_file>
"""
import sys
import re
from code_mod_defs import *

def parse_modification_file(file_path):
    """Parse modification file and return list of modifications"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    modifications = []
    
    # Split by function markers
    function_blocks = re.split(r'MMM\s+(\w+)\s+MMM', content)[1:]  # Skip empty first element
    # Process pairs: function_name, content
    for i in range(0, len(function_blocks), 2):
        if i + 1 >= len(function_blocks):
            break
            
        function_name = function_blocks[i].strip()
        block_content = function_blocks[i + 1].strip()
        
        # Split arguments by @@@@@@
        #args = re.split(r'@{6}|@{3}\s@{3}', block_content)
        args = re.split(r'@{6}\n', block_content)
        args[0] = args[0].strip()
        #args = [arg for arg in args]
        
        # Get function from globals
        if function_name in globals():
            func = globals()[function_name]
            modifications.append((func, args, {}))
        else:
            raise ValueError(f"Unknown function: {function_name}")
    
    return modifications

def main():
    if len(sys.argv) != 2:
        print("Usage: python modify_code.py <modification_file>")
        sys.exit(1)
    
    modification_file = sys.argv[1]
    
    modifications = parse_modification_file(modification_file)
    
    manager = apply_modification_set(modifications)
    print(f"\nModifications complete. Run 'python {sys.argv[0]} rollback' for rollback options.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        interactive_rollback()
    else:
        main()
