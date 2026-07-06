# zOS/core/L1_Foundation/c_zLoader/loader_modules/loader_constants.py

"""
Centralized constants for zLoader subsystem.

This module provides a single source of truth for all constants used across the
zLoader subsystem, following the established pattern from a_zConfig and b_zComm.

Purpose
-------
Centralizes all constants to prevent magic strings, enable easier refactoring,
and provide a clear overview of all configuration values used throughout zLoader.

Constant Groups
---------------
- COLOR_*: Display color identifiers for zDisplay integration
- CACHE_TYPE_*: Cache tier identifiers for orchestrator routing
- CACHE_KEY_*: Cache key patterns and prefixes
- FILE_TYPE_*: File type identifiers for zVaFile detection
- SESSION_KEY_*: Session dictionary keys for state management
- MSG_*: Display messages for user feedback
- ERROR_*: Error message templates with format placeholders
- DEFAULT_*: Default configuration values
- STAT_KEY_*: Statistics dictionary keys
- KWARGS_KEY_*: Kwargs parameter keys for type safety

Architecture
------------
**Tier 0 - Constants (Foundation)**
    - Position: Lowest-level shared definitions
    - Dependencies: None
    - Used By: All zLoader modules (Tier 1-6)
    - Purpose: Single source of truth for constants

Integration Points
------------------
**zLoader.py (Tier 5)**:
    - Uses: COLOR_*, FILE_TYPE_*, CACHE_KEY_*, SESSION_KEY_*, MSG_*

**cache_orchestrator.py (Tier 3)**:
    - Uses: CACHE_TYPE_*, STAT_KEY_*, KWARGS_KEY_*, DEFAULT_*

**loader_io.py (Tier 1)**:
    - Uses: COLOR_*, MSG_*, ERROR_*, FILE_*

**All cache implementations (Tier 2)**:
    - Uses: CACHE_TYPE_*, STAT_KEY_*, DEFAULT_*

Version History
---------------
- v1.6.0: Created centralized constants module (Phase 1 refactoring)
          Added error exception classes (Phase 3 refactoring)
"""

# Cross-subsystem protocol vocabulary (root SSOT). Imported via the submodule
# path so this module stays import-safe during zOS package initialization.
# zLoader's historical names below remain as thin aliases for back-compat.
from zOS.zVocabulary import (
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZVAFOLDER,
    FILE_TYPE_UI,
    FILE_TYPE_SCHEMA,
    FILE_TYPE_CONFIG,
    PATH_SYMBOL_AT,
    ZMACHINE_PREFIX,
    FILE_EXT_PY,
)

# ============================================================================
# EXCEPTION CLASSES (Standardized Error Hierarchy)
# ============================================================================

class LoaderError(Exception):
    """
    Base exception for all loader errors.
    
    This is the base class for all zLoader subsystem errors, enabling
    catch-all error handling while preserving specific error types.
    
    Usage:
        try:
            loader.handle(path)
        except LoaderError as e:
            # Catches all loader-related errors
            logger.error(f"Loader error: {e}")
    """
    pass


class CacheError(LoaderError):
    """
    Cache operation failed.
    
    Raised when cache get/set/clear operations fail due to cache-specific
    issues (not file I/O or parsing issues).
    
    Examples:
        - Cache full and eviction failed
        - Cache corruption detected
        - Invalid cache key format
    
    Usage:
        try:
            cache.set(key, value)
        except CacheError as e:
            logger.error(f"Cache error: {e}")
    """
    pass


class FileLoadError(LoaderError):
    """
    File loading failed.
    
    Raised when file I/O operations fail (file not found, permission denied,
    read errors). Wraps lower-level OS errors with loader-specific context.
    
    Examples:
        - File not found on disk
        - Permission denied reading file
        - Disk I/O error during read
    
    Usage:
        try:
            content = load_file_raw(path, logger)
        except FileLoadError as e:
            logger.error(f"Failed to load file: {e}")
    """
    pass


class ValidationError(LoaderError):
    """
    Configuration validation failed.
    
    Raised when loader configuration or parameters fail validation checks
    before operations begin. Enables fail-fast error detection.
    
    Examples:
        - Invalid cache max_size (negative or zero)
        - Invalid cache_type parameter
        - Invalid file path format
        - Missing required session keys
    
    Usage:
        try:
            validator.validate_cache_config(config)
        except ValidationError as e:
            logger.error(f"Invalid configuration: {e}")
    """
    pass


class PluginTrustError(LoaderError):
    """
    Plugin failed the trust policy before execution.

    Raised by the plugin-trust gate (see loader_trust.verify_plugin_trust) when a
    plugin path/signature is not permitted by policy. Enforcement is provided by
    the zGuard binary wheel (``zguard.loader.plugin_trust``); in open-core (no
    zGuard) the gate is permissive and this is never raised.

    Note: this exception is part of the public seam so the zGuard wheel can import
    and raise it. It MUST propagate (never be swallowed/re-wrapped) so denials are
    visible to callers.
    """
    pass


# ============================================================================
# COLOR CONSTANTS (Display Integration)
# ============================================================================

COLOR_LOADER: str = "LOADER"
COLOR_SUBLOADER: str = "SUBLOADER"

# ============================================================================
# CACHE TYPE CONSTANTS (Orchestrator Routing)
# ============================================================================

CACHE_TYPE_SYSTEM: str = "system"
CACHE_TYPE_PINNED: str = "pinned"
CACHE_TYPE_SCHEMA: str = "schema"
CACHE_TYPE_PLUGIN: str = "plugin"
CACHE_TYPE_ALL: str = "all"

# ============================================================================
# CACHE KEY CONSTANTS (Key Construction)
# ============================================================================

CACHE_KEY_PREFIX: str = "parsed:"

# ============================================================================
# FILE TYPE CONSTANTS (File Identification)
# ============================================================================
# Canonical ids single-sourced in zVocabulary; imported at top of module.
# (FILE_TYPE_UI, FILE_TYPE_SCHEMA, FILE_TYPE_CONFIG)

# ============================================================================
# SESSION KEY CONSTANTS (Session Dictionary)
# ============================================================================
# zLoader's historical names alias the canonical root session keys.
SESSION_KEY_VAFILE: str = SESSION_KEY_ZVAFILE
SESSION_KEY_VAFOLDER: str = SESSION_KEY_ZVAFOLDER

# ============================================================================
# MESSAGE CONSTANTS (User Feedback)
# ============================================================================

# Loader Messages
MSG_READY: str = "zLoader Ready"
MSG_START: str = "zLoader"
MSG_CACHED: str = "zLoader return (cached)"
MSG_RETURN: str = "zLoader return"

# I/O Messages
MSG_READING: str = "Reading"

# ============================================================================
# ERROR MESSAGE TEMPLATES (Exception Messages)
# ============================================================================

# Plugin Errors
ERROR_PLUGIN_NOT_FOUND: str = "Plugin file not found: {filepath}"
ERROR_PLUGIN_LOAD_FAILED: str = "Failed to load plugin: {error}"
ERROR_NO_PARSER: str = "zParser subsystem not available"

# File I/O Errors
ERROR_FILE_NOT_FOUND: str = "Unable to load zFile (not found): {path}"
ERROR_PERMISSION_DENIED: str = "Unable to load zFile (permission denied): {path}"
ERROR_GENERIC: str = "Unable to load zFile: {path}"

# Cache Errors
ERROR_CACHE_MISS: str = "Cache miss for key: {key}"
ERROR_INVALID_CACHE_TYPE: str = "Invalid cache type: {type}"

# Validation Errors
ERROR_INVALID_MAX_SIZE: str = "Invalid max_size: {value} (must be positive integer)"
ERROR_INVALID_FILE_PATH: str = "Invalid file path: {path}"
ERROR_INVALID_CACHE_CONFIG: str = "Invalid cache configuration: {reason}"

# ============================================================================
# DEFAULT VALUE CONSTANTS (Configuration Defaults)
# ============================================================================

DEFAULT_PATH_SYMBOL: str = PATH_SYMBOL_AT  # alias → root path symbol
DEFAULT_SYSTEM_MAX_SIZE: int = 100  # System cache max size (UI/config files)
DEFAULT_PLUGIN_MAX_SIZE: int = 50   # Plugin cache max size (module instances)

# ============================================================================
# FILE EXTENSION CONSTANTS (File Format Detection)
# ============================================================================

# Schema files are detected by the zSchema filename prefix (format-agnostic:
# .zolo/.json/.yaml/.yml all supported), NOT by extension. See zLoader._is_schema.
PLUGIN_EXTENSION: str = FILE_EXT_PY  # alias → root extension atom

# ============================================================================
# FILE PREFIX CONSTANTS (File Naming Patterns)
# ============================================================================
# ZMACHINE_PREFIX single-sourced in zVocabulary; imported at top of module.

# ============================================================================
# FILE I/O CONSTANTS (File Reading Configuration)
# ============================================================================

FILE_MODE_READ: str = "r"
FILE_ENCODING_UTF8: str = "utf-8"

# ============================================================================
# DISPLAY STYLE CONSTANTS (zDisplay Integration)
# ============================================================================

STYLE_SINGLE: str = "single"
STYLE_FULL: str = "full"
STYLE_TILDE: str = "~"

# ============================================================================
# INDENT CONSTANTS (Display Formatting)
# ============================================================================

INDENT_ROOT: int = 0
INDENT_PRIMARY: int = 1
INDENT_SECONDARY: int = 2

# ============================================================================
# STATISTICS KEY CONSTANTS (Cache Stats Dictionaries)
# ============================================================================

STAT_KEY_NAMESPACE: str = "namespace"
STAT_KEY_SIZE: str = "size"
STAT_KEY_ALIASES: str = "aliases"
STAT_KEY_ACTIVE_CONNECTIONS: str = "active_connections"
STAT_KEY_CONNECTIONS: str = "connections"
STAT_KEY_HITS: str = "hits"
STAT_KEY_MISSES: str = "misses"
STAT_KEY_HIT_RATE: str = "hit_rate"

# ============================================================================
# KWARGS KEY CONSTANTS (Method Parameter Keys)
# ============================================================================

KWARGS_KEY_ZPATH: str = "zpath"
KWARGS_KEY_FILE_PATH: str = "file_path"
KWARGS_KEY_DEFAULT: str = "default"

# ============================================================================
# LOG PREFIX CONSTANTS (Logging Prefixes)
# ============================================================================

LOG_PREFIX_ORCHESTRATOR: str = "[CacheOrchestrator]"
LOG_PREFIX_SYSTEM_CACHE: str = "[SystemCache]"
LOG_PREFIX_PINNED_CACHE: str = "[PinnedCache]"
LOG_PREFIX_SCHEMA_CACHE: str = "[SchemaCache]"
LOG_PREFIX_PLUGIN_CACHE: str = "[PythonModuleCache]"
LOG_PREFIX_LOADER_IO: str = "[LoaderIO]"

# ============================================================================
# MODULE METADATA
# ============================================================================

__all__ = [
    # Exception classes
    "LoaderError",
    "CacheError",
    "FileLoadError",
    "ValidationError",
    "PluginTrustError",
    # Color constants
    "COLOR_LOADER",
    "COLOR_SUBLOADER",
    # Cache type constants
    "CACHE_TYPE_SYSTEM",
    "CACHE_TYPE_PINNED",
    "CACHE_TYPE_SCHEMA",
    "CACHE_TYPE_PLUGIN",
    "CACHE_TYPE_ALL",
    # Cache key constants
    "CACHE_KEY_PREFIX",
    # File type constants
    "FILE_TYPE_UI",
    "FILE_TYPE_SCHEMA",
    "FILE_TYPE_CONFIG",
    # Session key constants
    "SESSION_KEY_VAFILE",
    "SESSION_KEY_VAFOLDER",
    # Message constants
    "MSG_READY",
    "MSG_START",
    "MSG_CACHED",
    "MSG_RETURN",
    "MSG_READING",
    # Error message templates
    "ERROR_PLUGIN_NOT_FOUND",
    "ERROR_PLUGIN_LOAD_FAILED",
    "ERROR_NO_PARSER",
    "ERROR_FILE_NOT_FOUND",
    "ERROR_PERMISSION_DENIED",
    "ERROR_GENERIC",
    "ERROR_CACHE_MISS",
    "ERROR_INVALID_CACHE_TYPE",
    "ERROR_INVALID_MAX_SIZE",
    "ERROR_INVALID_FILE_PATH",
    "ERROR_INVALID_CACHE_CONFIG",
    # Default value constants
    "DEFAULT_PATH_SYMBOL",
    "DEFAULT_SYSTEM_MAX_SIZE",
    "DEFAULT_PLUGIN_MAX_SIZE",
    # File extension constants
    "PLUGIN_EXTENSION",
    # File prefix constants
    "ZMACHINE_PREFIX",
    # File I/O constants
    "FILE_MODE_READ",
    "FILE_ENCODING_UTF8",
    # Display style constants
    "STYLE_SINGLE",
    "STYLE_FULL",
    "STYLE_TILDE",
    # Indent constants
    "INDENT_ROOT",
    "INDENT_PRIMARY",
    "INDENT_SECONDARY",
    # Statistics key constants
    "STAT_KEY_NAMESPACE",
    "STAT_KEY_SIZE",
    "STAT_KEY_ALIASES",
    "STAT_KEY_ACTIVE_CONNECTIONS",
    "STAT_KEY_CONNECTIONS",
    "STAT_KEY_HITS",
    "STAT_KEY_MISSES",
    "STAT_KEY_HIT_RATE",
    # Kwargs key constants
    "KWARGS_KEY_ZPATH",
    "KWARGS_KEY_FILE_PATH",
    "KWARGS_KEY_DEFAULT",
    # Log prefix constants
    "LOG_PREFIX_ORCHESTRATOR",
    "LOG_PREFIX_SYSTEM_CACHE",
    "LOG_PREFIX_PINNED_CACHE",
    "LOG_PREFIX_SCHEMA_CACHE",
    "LOG_PREFIX_PLUGIN_CACHE",
    "LOG_PREFIX_LOADER_IO",
]
