# zOS/core/L2_Handling/g_zParser/parser_modules/shared/__init__.py

"""
Shared infrastructure for parser modules.

This package provides reusable utilities, constants, and helpers used across
all parser modules to eliminate duplication and maintain SSOT (Single Source of Truth).

Public API:
    Constants:
        - File extensions (FILE_EXT_*)
        - Path symbols (SYMBOL_*)
        - zVaFile prefixes (ZVAFILE_PREFIX_*)
        - Log message templates
        - Error message templates
    
    Utilities:
        - Error handling helpers
        - Display integration helpers
        - Argument parsing primitives

Architecture:
    - parser_constants.py: Command types and internal constants
    - file_constants.py: File extensions, formats, and file-related constants
    - error_handlers.py: Reusable error handling patterns
    - display_utils.py: Standardized display integration
    - argument_utils.py: Universal argument splitting (brackets + quotes)

Created: Phase 1 - Extract Shared Infrastructure
Updated: v1.6.0 - Added argument_utils for unified argument parsing
"""

# Import from submodules
from .parser_constants import *
from .file_constants import *
from .error_handlers import *
from .display_utils import *
from .argument_utils import *

__all__ = [
    # From parser_constants
    'RESERVED_SCHEMA_KEYS',
    
    # From file_constants (most commonly used)
    'FILE_EXT_JSON',
    'FILE_EXT_YAML',
    'FILE_EXT_YML',
    'FILE_EXT_ZOLO',
    'SYMBOL_AT',
    'SYMBOL_TILDE',
    'ZVAFILE_PREFIX_UI',
    'ZVAFILE_PREFIX_SCHEMA',
    'ZVAFILE_PREFIX_CONFIG',
    'ZVAFILE_PREFIXES',
    'ZVAFILE_EXTENSIONS',
    'PATH_SEP_DOT',
    'PATH_SEP_SLASH',
    
    # From error_handlers
    'handle_parse_error',
    'handle_file_error',
    'format_error_message',
    
    # From display_utils
    'display_path_info',
    'display_file_type',
    
    # From argument_utils
    'split_arguments',
]
