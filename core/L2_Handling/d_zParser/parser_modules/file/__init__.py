# zOS/core/L2_Handling/g_zParser/parser_modules/file/__init__.py

"""
File parsing package for zParser subsystem.

Provides comprehensive file content parsing for YAML, JSON, and expression parsing
with automatic format detection and UI file RBAC transformation. Refactored from
monolithic parser_file.py into modular structure with format parsers and transformers.

Public API:
    - parse_file_content: Main file parser (CRITICAL - 6 external usages)
    - parse_yaml: YAML-specific parsing
    - parse_json: JSON-specific parsing
    - detect_format: Auto-detect file format
    - parse_file_by_path: Convenience method (load + parse)
    - parse_json_expr: JSON expression parsing

Architecture:
    - file_parser.py: Main parse_file_content dispatcher
    - file_utils.py: Utility functions
    - format_parsers/: YAML, JSON, format detection
    - transformers/: RBAC transformation, file type detection

External Usage (CRITICAL - 6 files):
    - zParser.py: Facade delegates all file parsing
    - zLoader.py: Loads UI files for zWalker (CRITICAL)
    - authzRBAC.py: Loads RBAC policy files
    - auth_session_persistence.py: Loads session data
    - func_args.py: Loads function argument definitions
    - load_executor.py: Loads executable files

Signature Stability:
    All function signatures must remain stable for external compatibility.

Created: Phase 5 - Refactor parser_file.py
"""

# Import from new modular structure (Phase 1 refactoring complete)
from .file_parser import parse_file_content
from .file_utils import parse_file_by_path
from .format_parsers import parse_yaml, parse_json, detect_format, parse_json_expr

__all__ = [
    'parse_file_content',
    'parse_yaml',
    'parse_json',
    'detect_format',
    'parse_file_by_path',
    'parse_json_expr'
]
