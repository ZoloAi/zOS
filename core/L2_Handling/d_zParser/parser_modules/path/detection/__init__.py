# zOS/core/L2_Handling/g_zParser/parser_modules/path/detection/__init__.py

"""
Path detection modules for path package.

Provides detection utilities for zVaFiles, extension finding, and file validation.

Public API:
    - is_zvafile_type: Detect zVaFile prefixes
    - find_file_with_extension: Find file with supported extensions
    - validate_file_exists: Check file existence
    - validate_zvafile_found: Validate zVaFile found with extensions

Created: Phase 3.2 - Extract Detection from parser_path.py
"""

from .zvafile_detector import is_zvafile_type
from .extension_finder import find_file_with_extension
from .file_validator import validate_file_exists, validate_zvafile_found

__all__ = [
    'is_zvafile_type',
    'find_file_with_extension',
    'validate_file_exists',
    'validate_zvafile_found'
]
