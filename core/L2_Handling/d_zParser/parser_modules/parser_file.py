# zOS/core/L2_Core/g_zParser/parser_modules/parser_file.py

"""
BACKWARD COMPATIBILITY WRAPPER for parser_file.py

⚠️ This file is now a thin wrapper for backward compatibility.
The actual implementation has been split into modular files:
    - file/file_parser.py: Main orchestrator
    - file/file_utils.py: Utility functions
    - file/format_parsers/: Format-specific parsers
    - file/transformers/: RBAC transformation

All constants have been moved to shared/file_constants.py

External Usage (6 Files - CRITICAL):
    1. zParser.py (line 150)
    2. zLoader.py (line 63) - CRITICAL for UI loading
    3. authzRBAC.py
    4. auth_session_persistence.py
    5. func_args.py
    6. load_executor.py

All function signatures remain stable for external compatibility.

Refactoring completed: Phase 1 - parser_file.py split
    - 942 LOC → 7 focused modules (< 250 LOC each)
    - Format parsers: yaml_parser, json_parser, format_detector, expr_parser
    - Transformers: rbac_transformer, file_type_detector
    - Main: file_parser, file_utils

Version History:
    - v1.5.4 Week 6.8.6: Added vafile package integration
    - v1.5.4 Week 6.8.7: Industry-grade upgrade (D+ → A+)
    - v1.5.5 Phase 1: Split into modular structure (this wrapper created)

See Also:
    - file/ package: New modular implementation
    - shared/file_constants.py: Centralized constants
"""

# Re-export from new modular structure for backward compatibility
from .file import (
    parse_file_content,
    parse_file_by_path,
    parse_yaml,
    parse_json,
    detect_format,
    parse_json_expr
)

# Re-export constants from shared for backward compatibility
# (External code may import constants directly from this file)
from .shared.file_constants import (
    # File Extensions
    FILE_EXT_JSON,
    FILE_EXT_YAML,
    FILE_EXT_YML,
    FILE_EXT_ZOLO,
    # Log Prefixes
    LOG_PREFIX_PARSE,
    LOG_PREFIX_RBAC,
    # File Markers
    FILE_MARKER_ZUI,
    FILE_MARKER_UI_PATH,
    # Dict Keys
    DICT_KEY_ZBLOCKS,
    DICT_KEY_ITEMS,
    DICT_KEY_DATA,
    DICT_KEY_RBAC,
    DICT_KEY_VALUE,
    # Default Values
    DEFAULT_ENCODING,
    DEFAULT_FORMAT,
    # Special Values
    STR_N_A
)

# Also re-export the zolo availability flag for backward compatibility
try:
    __import__('zlsp')
    ZOLO_AVAILABLE = True
except ImportError:
    ZOLO_AVAILABLE = False
except Exception:
    ZOLO_AVAILABLE = False

__all__ = [
    # Functions
    'parse_file_content',
    'parse_file_by_path',
    'parse_yaml',
    'parse_json',
    'detect_format',
    'parse_json_expr',
    # Constants (for backward compatibility)
    'FILE_EXT_JSON',
    'FILE_EXT_YAML',
    'FILE_EXT_YML',
    'FILE_EXT_ZOLO',
    'LOG_PREFIX_PARSE',
    'LOG_PREFIX_RBAC',
    'FILE_MARKER_ZUI',
    'FILE_MARKER_UI_PATH',
    'DICT_KEY_ZBLOCKS',
    'DICT_KEY_ITEMS',
    'DICT_KEY_DATA',
    'DICT_KEY_RBAC',
    'DICT_KEY_VALUE',
    'DEFAULT_ENCODING',
    'DEFAULT_FORMAT',
    'STR_N_A',
    'ZOLO_AVAILABLE'
]
