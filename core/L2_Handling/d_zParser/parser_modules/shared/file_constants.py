# zOS/core/L2_Handling/g_zParser/parser_modules/shared/file_constants.py

"""
File-related constants for parser modules.

Consolidates all file extension, format, and path-related constants used across
parser_file, parser_path, and other modules. Eliminates duplication and provides
Single Source of Truth (SSOT) for file-related constants.

Categories:
    - File Extensions: JSON, YAML, Python, etc.
    - Path Symbols: @, ~, path separators
    - zVaFile Prefixes: zUI, zSchema, zConfig
    - File Type Names: Type identifiers
    - Content Detection Markers: Format detection helpers
    - Log Messages: File operation logging
    - Error Messages: File operation errors
    - Display Configuration: Display formatting

Dependencies:
    - None (pure constants module)

Created: Phase 1 - Extract Shared Infrastructure
"""

from zOS import List, Tuple

# Cross-subsystem protocol vocabulary (root SSOT). Imported via the submodule
# path so this module stays import-safe during zOS package initialization.
# Parser's historical names below remain as thin aliases for back-compat.
from zOS.zVocabulary import (
    FILE_EXT_JSON,
    FILE_EXT_YAML,
    FILE_EXT_YML,
    FILE_EXT_ZOLO,
    FILE_EXT_PY,
    FILE_EXT_JS,
    FILE_EXT_SH,
    FILE_EXT_MD,
    FILE_EXT_TXT,
    FILE_EXT_XML,
    FILE_EXT_HTML,
    FILE_EXT_CSS,
    FILE_TYPE_UI,
    FILE_TYPE_SCHEMA,
    FILE_TYPE_CONFIG,
    FILE_TYPE_ZVAFILE,
    FILE_TYPE_ZOTHER,
    PATH_SYMBOL_AT,
    PATH_SYMBOL_TILDE,
    ZMACHINE_PREFIX,
    ZMACHINE_PREFIX_LONG,
    SESSION_KEY_ZSPACE,
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
)

# ============================================================================
# FILE EXTENSIONS  →  atoms single-sourced in zVocabulary (imported above)
# ============================================================================

# Extension Collections
FILE_EXTENSIONS: List[str] = [
    FILE_EXT_PY,
    FILE_EXT_JS,
    FILE_EXT_SH,
    FILE_EXT_MD,
    FILE_EXT_TXT,
    FILE_EXT_JSON,
    FILE_EXT_YAML,
    FILE_EXT_YML,
    FILE_EXT_XML,
    FILE_EXT_HTML,
    FILE_EXT_CSS
]

# zVaFile Extensions (priority order for auto-detection)
ZVAFILE_EXTENSIONS: List[str] = [
    FILE_EXT_ZOLO,    # Try .zolo first (new DRY format)
    FILE_EXT_JSON,
    FILE_EXT_YAML,
    FILE_EXT_YML
]


# ============================================================================
# PATH SYMBOLS AND SEPARATORS
# ============================================================================

# Path Symbols (aliases → root zVocabulary)
SYMBOL_AT: str = PATH_SYMBOL_AT          # Workspace-relative path
SYMBOL_TILDE: str = PATH_SYMBOL_TILDE    # Absolute path

# Path Separators
PATH_SEP_DOT: str = "."
PATH_SEP_SLASH: str = "/"


# ============================================================================
# ZMACHINE CONSTANTS
# ============================================================================

# zMachine Prefixes (aliases → root zVocabulary; ZMACHINE_PREFIX_LONG imported)
ZMACHINE_PREFIX_SHORT: str = ZMACHINE_PREFIX

# zMachine Keywords (for file validation)
ZMACHINE_KEYWORD_ZSCHEMA: str = "zSchema"
ZMACHINE_KEYWORD_ZUI: str = "zUI"
ZMACHINE_KEYWORD_ZCONFIG: str = "zConfig"
ZMACHINE_KEYWORDS: List[str] = [
    ZMACHINE_KEYWORD_ZSCHEMA,
    ZMACHINE_KEYWORD_ZUI,
    ZMACHINE_KEYWORD_ZCONFIG
]


# ============================================================================
# ZVAFILE CONSTANTS
# ============================================================================

# zVaFile Prefixes
ZVAFILE_PREFIX_UI: str = "zUI."
ZVAFILE_PREFIX_SCHEMA: str = "zSchema."
ZVAFILE_PREFIX_CONFIG: str = "zConfig."
ZVAFILE_PREFIXES: Tuple[str, str, str] = (
    ZVAFILE_PREFIX_UI,
    ZVAFILE_PREFIX_SCHEMA,
    ZVAFILE_PREFIX_CONFIG
)

# File Type Names (aliases → root zVocabulary; FILE_TYPE_ZVAFILE/ZOTHER imported)
FILE_TYPE_ZUI: str = FILE_TYPE_UI
FILE_TYPE_ZSCHEMA: str = FILE_TYPE_SCHEMA
FILE_TYPE_ZCONFIG: str = FILE_TYPE_CONFIG


# ============================================================================
# FILE MARKERS (for detection)
# ============================================================================

# File Type Markers (for UI file detection)
FILE_MARKER_ZUI: str = "zUI"
FILE_MARKER_UI_PATH: str = "/UI/"

# Content Detection Markers
CONTENT_MARKER_JSON_START_BRACE: str = "{"
CONTENT_MARKER_JSON_START_BRACKET: str = "["
CONTENT_MARKER_YAML_COLON: str = ":"
CONTENT_MARKER_YAML_DASH: str = "-"


# ============================================================================
# DICT KEYS (shared across modules)
# ============================================================================

# Common Dict Keys (from vafile package - for RBAC transformation)
DICT_KEY_ZBLOCKS: str = "zblocks"
DICT_KEY_ITEMS: str = "items"
DICT_KEY_DATA: str = "data"
DICT_KEY_GATE: str = "zGate"   # the one gate verb — hoisted like RBAC on inline items
DICT_KEY_RBAC: str = "zRBAC"   # DEPRECATED — folded into zGate; retained until leaves migrate
DICT_KEY_VALUE: str = "_value"


# ============================================================================
# SESSION KEYS  →  single-sourced in zVocabulary (imported above)
# ============================================================================
# SESSION_KEY_ZSPACE, SESSION_KEY_ZVAFOLDER, SESSION_KEY_ZVAFILE imported from
# the root vocabulary; they remain importable from here for back-compat.


# ============================================================================
# LOG PREFIXES
# ============================================================================

LOG_PREFIX_PARSE: str = "[parse_file_content]"
LOG_PREFIX_RBAC: str = "[RBAC]"


# ============================================================================
# LOG MESSAGES - File Operations
# ============================================================================

# parse_file_content logging
LOG_MSG_PARSE_CALLED: str = "Called with file_extension=%s"
LOG_MSG_EMPTY_CONTENT: str = "Empty content provided for parsing"
LOG_MSG_AUTO_DETECTED: str = "Auto-detected format: %s"
LOG_MSG_IS_UI_FILE: str = "is_ui_file=%s (file_extension=%s, file_path=%s)"
LOG_MSG_DETECTED_UI: str = "Detected UI file, applying RBAC parsing"
LOG_MSG_UNSUPPORTED_EXT: str = "Unsupported file extension: %s"

# YAML parsing logging
LOG_MSG_YAML_PARSED: str = "YAML parsed successfully! Type: %s, Keys: %s"
LOG_MSG_YAML_PARSE_ERROR: str = "Failed to parse YAML: %s"
LOG_MSG_YAML_UNEXPECTED_ERROR: str = "Unexpected error parsing YAML: %s"

# JSON parsing logging
LOG_MSG_JSON_PARSED: str = "JSON parsed successfully! Type: %s, Keys: %s"
LOG_MSG_JSON_PARSE_ERROR: str = "Failed to parse JSON: %s"
LOG_MSG_JSON_UNEXPECTED_ERROR: str = "Unexpected error parsing JSON: %s"

# Format detection logging
LOG_MSG_DETECTED_JSON: str = "Detected JSON format (starts with {{ or [)"
LOG_MSG_DETECTED_YAML: str = "Detected YAML format (contains : or starts with -)"
LOG_MSG_DEFAULT_YAML: str = "Could not detect format, defaulting to YAML"

# File I/O logging
LOG_MSG_FILE_NOT_FOUND: str = "File not found: %s"
LOG_MSG_FILE_READ_ERROR: str = "Failed to read file %s: %s"
LOG_MSG_JSON_EXPR_ERROR: str = "Failed to parse JSON expression: %s"

# RBAC transformation logging
LOG_MSG_RAW_DATA_KEYS: str = "Raw data keys: %s"
LOG_MSG_PARSED_UI_TYPE: str = "Parsed UI structure: %s"
LOG_MSG_PARSED_UI_KEYS: str = "Parsed UI keys: %s"
LOG_MSG_TRANSFORMING_ZBLOCKS: str = "Transforming zblocks: %s"
LOG_MSG_PROCESSING_ZBLOCK: str = "Processing zblock: %s"
LOG_MSG_FOUND_ITEMS: str = "Found %d items in %s"
LOG_MSG_ATTACHED_RBAC: str = "Attached zRBAC to %s"
LOG_MSG_WRAPPED_RBAC: str = "Wrapped %s with zRBAC"
LOG_MSG_TRANSFORM_COMPLETE: str = "Transformation complete, returning %d zblocks"
LOG_MSG_FINAL_RESULT_KEYS: str = "Final result keys: %s"
LOG_MSG_NO_ZBLOCKS_STRUCTURE: str = "Parsed UI doesn't have expected 'zblocks' structure!"


# ============================================================================
# LOG MESSAGES - Path Operations
# ============================================================================

LOG_MSG_ZMACHINE_PATH: str = "[zMachine Path] %s => %s"
LOG_MSG_ZSPACE: str = "\nzSpace: %s"
LOG_MSG_ZRELPATH: str = "\nzRelPath: %s"
LOG_MSG_ZFILENAME: str = "\nzFileName: %s"
LOG_MSG_OS_RELPATH: str = "\nos_RelPath: %s"
LOG_MSG_ZVAFOLDER_PATH: str = "\nzVaFolder path: %s"
LOG_MSG_ZBLOCK: str = "\nzBlock: %s"
LOG_MSG_ZPATH_2_ZFILE: str = "\nzPath_2_zFile: %s"
LOG_MSG_ZFILENAME_SHORT: str = "zFileName: %s"
LOG_MSG_ZRELPATH_PARTS: str = "zRelPath_parts: %s"
LOG_MSG_NO_ZBLOCK: str = "\nNo zBlock (not a zVaFile)"
LOG_MSG_PARTS: str = "\nparts: %s"
LOG_MSG_IS_ZVAFILE: str = "is_zvafile: %s"
LOG_MSG_SYMBOL: str = "symbol: %s"
LOG_MSG_ZVAFILE_FULLPATH: str = "zVaFile path + zVaFile:\n%s"
LOG_MSG_SYMBOL_AT: str = "↪ '@' → workspace-relative path"
LOG_MSG_SYMBOL_TILDE: str = "↪ '~' → absolute path"
LOG_MSG_SYMBOL_NONE: str = "↪ no symbol → treat whole as relative"
LOG_MSG_NO_WORKSPACE: str = "⚠️ '@' path requested but no workspace configured in zSession"
LOG_MSG_NO_WORKSPACE_HELP: str = "   Use 'session set zSpace <path>' to configure workspace"
LOG_MSG_NO_WORKSPACE_FALLBACK: str = "   Falling back to current working directory: %s"
LOG_MSG_FILE_TYPE: str = "File Type: %s"
LOG_MSG_FILE_TYPE_UNKNOWN: str = "File Type: zVaFile (unknown subtype)"
LOG_MSG_FILE_TYPE_OTHER: str = "File Type: zOther (extension provided)"
LOG_MSG_ZFILE_EXTENSION: str = "zFile extension: %s"


# ============================================================================
# ERROR MESSAGES
# ============================================================================

# File operation errors
ERROR_MSG_UNSUPPORTED_EXTENSION: str = "Unsupported file extension"
ERROR_MSG_FILE_NOT_FOUND: str = "File not found"
ERROR_MSG_FILE_READ_FAILED: str = "Failed to read file"
ERROR_MSG_NO_ZVAFILE_FOUND: str = "No zVaFile found for base path: {} (tried .zolo/.json/.yaml/.yml)"


# ============================================================================
# DISPLAY CONFIGURATION
# ============================================================================

COLOR_SUBLOADER: str = "SUBLOADER"
INDENT_PATH: int = 2
STYLE_SINGLE: str = "single"

# Display Messages
DISPLAY_MSG_PATH_DECODER: str = "zPath decoder"
DISPLAY_MSG_FILE_TYPE_TEMPLATE: str = "Type: {}|{}"


# ============================================================================
# DEFAULT VALUES
# ============================================================================

DEFAULT_ENCODING: str = "utf-8"
DEFAULT_FORMAT: str = FILE_EXT_YAML


# ============================================================================
# SPECIAL VALUES
# ============================================================================

STR_N_A: str = "N/A"
CHAR_SINGLE_QUOTE: str = "'"
CHAR_DOUBLE_QUOTE: str = '"'


# ============================================================================
# THRESHOLDS AND LIMITS
# ============================================================================

MIN_PARTS_FOR_ZVAFILE: int = 2
FILENAME_PARTS_FOR_SHORT: int = 2
FALLBACK_FILENAME_START: int = 2
