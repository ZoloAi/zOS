# zOS/core/L2_Core/g_zParser/parser_modules/parser_path.py

"""
BACKWARD COMPATIBILITY WRAPPER for parser_path.py

⚠️ This file is now a thin wrapper for backward compatibility.
The actual implementation has been split into modular files:
    - path/path_decoder.py: Main path decoder (~120 LOC)
    - path/file_identifier.py: File identification (~120 LOC)
    - path/resolvers/: zmachine_resolver, symbol_resolver, path_builder
    - path/detection/: zvafile_detector, extension_finder, file_validator
    - path/extraction/: ui_mode_handler, filename_extractor

All constants have been moved to shared/file_constants.py

External Usage (CRITICAL):
    - zLoader.py (Week 6.9 - CRITICAL)
    - zShell/load_executor.py

All function signatures remain stable for external compatibility.

Refactoring completed: Phase 3 - parser_path.py split
    - 1003 LOC → 13 focused modules (< 200 LOC each)
    - Resolvers: zmachine_resolver, symbol_resolver, path_builder
    - Detection: zvafile_detector, extension_finder, file_validator
    - Extraction: ui_mode_handler, filename_extractor
    - Main: path_decoder, file_identifier

Version History:
    - v1.5.4 Week 6.8.7: Industry-grade upgrade
    - v1.5.5 Phase 3: Split into modular structure (this wrapper created)

See Also:
    - path/ package: New modular implementation
    - shared/file_constants.py: Centralized constants
"""

# Re-export from new modular structure for backward compatibility
from .path import (
    zPath_decoder,
    identify_zFile,
    resolve_zmachine_path,
    resolve_symbol_path,
    is_zvafile_type
)

# Re-export constants from shared for backward compatibility
from .shared.file_constants import (
    # Path Symbols
    SYMBOL_AT,
    SYMBOL_TILDE,
    # Path Separators
    PATH_SEP_DOT,
    PATH_SEP_SLASH,
    # zMachine Prefixes
    ZMACHINE_PREFIX_SHORT,
    ZMACHINE_PREFIX_LONG,
    # zVaFile Prefixes
    ZVAFILE_PREFIX_UI,
    ZVAFILE_PREFIX_SCHEMA,
    ZVAFILE_PREFIX_CONFIG,
    ZVAFILE_PREFIXES,
    # File Types
    FILE_TYPE_ZUI,
    FILE_TYPE_ZSCHEMA,
    FILE_TYPE_ZCONFIG,
    FILE_TYPE_ZVAFILE,
    FILE_TYPE_ZOTHER,
    # Extensions
    ZVAFILE_EXTENSIONS,
    FILE_EXTENSIONS,
    # Keywords
    ZMACHINE_KEYWORDS
)

__all__ = [
    # Functions
    'zPath_decoder',
    'identify_zFile',
    'resolve_zmachine_path',
    'resolve_symbol_path',
    'is_zvafile_type',
    # Constants (for backward compatibility)
    'SYMBOL_AT',
    'SYMBOL_TILDE',
    'PATH_SEP_DOT',
    'PATH_SEP_SLASH',
    'ZMACHINE_PREFIX_SHORT',
    'ZMACHINE_PREFIX_LONG',
    'ZVAFILE_PREFIX_UI',
    'ZVAFILE_PREFIX_SCHEMA',
    'ZVAFILE_PREFIX_CONFIG',
    'ZVAFILE_PREFIXES',
    'FILE_TYPE_ZUI',
    'FILE_TYPE_ZSCHEMA',
    'FILE_TYPE_ZCONFIG',
    'FILE_TYPE_ZVAFILE',
    'FILE_TYPE_ZOTHER',
    'ZVAFILE_EXTENSIONS',
    'FILE_EXTENSIONS',
    'ZMACHINE_KEYWORDS'
]
