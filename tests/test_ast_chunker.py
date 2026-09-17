import pytest
from app.services.ast_chunker import chunk_code_by_ast, extract_added_code_from_diff

SAMPLE_PYTHON_CODE = """import os
import sys

class UserService:
    def __init__(self, db_url):
        self.db_url = db_url

    def get_user(self, user_id):
        return f"User {user_id}"

def standalone_function(x, y):
    return x + y
"""

SAMPLE_DIFF = """@@ -1,4 +1,8 @@
 import os
+import sys
+
+def new_feature(data):
+    eval(data)
"""

def test_ast_chunker_extracts_functions_and_classes():
    chunks = chunk_code_by_ast(SAMPLE_PYTHON_CODE, filename="user_service.py")
    
    # Should identify module_globals, UserService class, and standalone_function
    types = [c.chunk_type for c in chunks]
    names = [c.name for c in chunks]
    
    assert "class" in types
    assert "function" in types
    assert "UserService" in names
    assert "standalone_function" in names

def test_ast_chunker_handles_diff_patch():
    code, mappings = extract_added_code_from_diff(SAMPLE_DIFF)
    assert "eval(data)" in code
    
    chunks = chunk_code_by_ast(SAMPLE_DIFF, filename="patch.py")
    assert len(chunks) > 0

def test_ast_chunker_fallback_on_invalid_syntax():
    invalid_code = "def broken_function(: invalid python syntax $$$"
    chunks = chunk_code_by_ast(invalid_code, filename="broken.py")
    assert len(chunks) > 0
    assert chunks[0].chunk_type == "structural_block"
