#!/bin/bash
# This creates a file named "output.txt" containing all files relevant to understanding this system 
# in a manner adequate to prompt LLM coding assistants for changes.  
# Caution: Some times the coding assistants will take the prompt.txt to heart and provide modifications
#  as though they are to be applied with the coding system itself.  This may work but since one is
#  developing the code modification system with the code modificaiton system in that case, there
#  are the obviuos hazards of assuming the correctness of code in development.
#  Also, LLM coding assistants sometimes neglect to provide adequate test cases for the
#  tests_code_mod/ directory.  Since this coding assistant interacts with version control,
#  one can get one's self into irrecoverable situations involving destruction of the revision history
#  which is why rigorous testing is more important in this project than usual.
concatdirtofile.sh .gitignore .coveragerc environment.yml pytest.ini prompt.txt modify_code.py tests_code_mod code_mod_defs.py
