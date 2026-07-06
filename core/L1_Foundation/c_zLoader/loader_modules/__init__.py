# zOS/core/L1_Foundation/c_zLoader/loader_modules/__init__.py

"""
Public API aggregator for zLoader modules.

This module serves as Tier 4 (Package Aggregator) in the zLoader architecture,
exposing the public API from Tiers 0-3 (Constants, Foundation, Cache Implementations,
Cache Orchestrator). It provides a single import location for the zLoader facade to
access all necessary components for file loading and caching operations.

Purpose
-------
The loader_modules package aggregator provides a clean, organized public API for
zLoader's internal components. It exposes four levels of abstraction:
    - Constants API: Centralized constants for all modules
    - Primary API: CacheOrchestrator (unified cache interface)
    - Advanced API: Direct cache implementations (custom cache logic)
    - Foundation API: load_file_raw (bypass cache entirely)

Architecture
------------
**Tier 4 - Package Aggregator (Exposes Public APIs)**
    - Position: Aggregation tier between internal modules and facade
    - Aggregates: Tier 0-3 (Constants, Foundation, Cache Implementations, Orchestrator)
    - Used By: zLoader.py facade (Tier 5)
    - Purpose: Single import location + public API exposure + multi-level access

**7-Tier Architecture** (updated with constants layer):
    - Tier 0: Constants (loader_constants.py - Centralized constants)
    - Tier 1: Foundation (loader_io.py - Raw file I/O)
    - Tier 2: Cache Implementations (SystemCache, PinnedCache, SchemaCache, PythonModuleCache)
    - Tier 3: Cache Orchestrator (CacheOrchestrator - Unified cache router)
    - Tier 4: Package Aggregator ← THIS MODULE
    - Tier 5: Facade (zLoader.py - Public interface to zOS)
    - Tier 6: Package Root (__init__.py - zLoader package entry point)

Integration Points
------------------
**zLoader.py (Tier 5)**:
    - Imports: CacheOrchestrator, load_file_raw, all constants
    - Purpose: Unified file loading + caching + constants access

Public API Exports
------------------
This module exports 70+ components organized by tier:

**Tier 0 - Centralized Constants**:
    - Color constants (COLOR_LOADER, COLOR_SUBLOADER)
    - Cache type constants (CACHE_TYPE_SYSTEM, CACHE_TYPE_PINNED, etc.)
    - File type constants (FILE_TYPE_UI, FILE_TYPE_SCHEMA, etc.)
    - Session key constants (SESSION_KEY_VAFILE, SESSION_KEY_VAFOLDER)
    - Message constants (MSG_READY, MSG_START, MSG_CACHED, etc.)
    - Error templates (ERROR_FILE_NOT_FOUND, ERROR_PERMISSION_DENIED, etc.)
    - Default values (DEFAULT_SYSTEM_MAX_SIZE, DEFAULT_PLUGIN_MAX_SIZE)
    - Stats keys (STAT_KEY_HITS, STAT_KEY_MISSES, etc.)
    
**Tier 3 - Cache Orchestrator**:
    - CacheOrchestrator: Unified cache router for all cache operations. Routes requests
      to appropriate cache tier (system, pinned, schema, plugin) based on cache_type
      parameter. Supports batch operations (clear all, get stats all).

**Tier 2 - Cache Implementations**:
    - SystemCache: UI/config file cache with LRU eviction (max_size=100). For frequently
      accessed YAML files (zUI, zSchema, zConfig).
    - PinnedCache: User alias cache with no eviction. For user-loaded aliases via zLoad
      command. Highest priority, never auto-evicts.
    - SchemaCache: DB connection cache with dual storage (in-memory connections + session
      metadata). For database connections and transaction management.
    - PythonModuleCache: Python module cache with collision detection, session injection, mtime
      invalidation, LRU eviction (max_size=50). For dynamically loaded Python modules.

**Tier 1 - Foundation I/O**:
    - load_file_raw: Raw file I/O function that bypasses all caching. Returns file
      contents as string. Used when cache bypass is needed or as fallback.

**Tier 6 - User Utilities**:
    - cache_utils: User-facing cache inspection and management utilities. Provides
      get_cached_files(), get_cached_files_count(), clear_system_cache(), and
      create_shortcut_from_cache() for interactive and programmatic cache control.

Usage Patterns
--------------
**Primary API (Recommended)**:
    Use CacheOrchestrator for most use cases. It provides a unified interface to all
    cache tiers and handles routing automatically:
        >>> from zOS.L1_Foundation.c_zLoader.loader_modules import CacheOrchestrator
        >>> cache = CacheOrchestrator(session, logger, zos)
        >>> data = cache.get("zUI.users.zolo", cache_type="system")

**Advanced API (Custom Implementations)**:
    Import direct cache implementations for custom cache logic or when you need
    direct access to specific cache tier features:
        >>> from zOS.L1_Foundation.c_zLoader.loader_modules import SystemCache, PinnedCache
        >>> system_cache = SystemCache(session, logger, max_size=50)
        >>> pinned_cache = PinnedCache(session, logger)

**Foundation API (Bypass Cache)**:
    Use load_file_raw to bypass all caching and read files directly from disk:
        >>> from zOS.L1_Foundation.c_zLoader.loader_modules import load_file_raw
        >>> content = load_file_raw("/path/to/file.zolo")

**User Utilities API (Cache Management)**:
    Use cache_utils module for cache inspection and management:
        >>> from zOS.L1_Foundation.c_zLoader.loader_modules import cache_utils
        >>> files = cache_utils.get_cached_files(zos)
        >>> stats = cache_utils.get_cached_files_count(zos)
        >>> cache_utils.clear_system_cache(zos)

External Usage
--------------
**Used By**:
    - zOS/subsystems/zLoader/zLoader.py (Facade - Tier 5)
      Usage: Imports CacheOrchestrator and load_file_raw
      Purpose: Provides file loading and caching to zLoader facade

See Also
--------
- loader_constants.py: Tier 0 centralized constants (new in v1.6.0)
- zLoader.py: Uses CacheOrchestrator, load_file_raw, and constants from this module
- cache_orchestrator.py: Tier 3 orchestrator (primary API)
- loader_cache_*.py: Tier 2 cache implementations (advanced API)
- loader_io.py: Tier 1 foundation I/O (foundation API)
- cache_utils.py: Tier 6 user utilities (user API)

Version History
---------------
- v1.6.0: Added loader_constants.py (Tier 0) with 70+ centralized constants,
          updated architecture to 7-tier model, aligned with a_zConfig/b_zComm patterns
- v1.5.9: Added cache_utils (Tier 6) for user-facing cache management utilities
- v1.5.4: Industry-grade upgrade (comprehensive docs, import organization,
          __all__ inline comments, usage guidance, architecture context)
- v1.5.3: Original implementation (6 exports: orchestrator + 4 caches + load_file_raw)
"""

# ============================================================================
# IMPORTS - Organized by Tier
# ============================================================================

# Tier 3: Cache Orchestrator
from .cache import CacheOrchestrator

# Tier 2.5: Validation (ValidationError sourced from loader_constants below)
from .loader_validator import LoaderValidator

# Plugin-trust gate (zGuard seam, permissive fallback in open-core)
from .loader_trust import verify_plugin_trust

# Tier 2: Cache Implementations
from .cache import SystemCache
from .cache import PinnedCache
from .cache import SchemaCache
from .cache import PythonModuleCache

# Tier 1: Foundation I/O
from .loader_io import load_file_raw

# Tier 6: User Utilities
from .cache import cache_utils

# Tier 0: Centralized Constants
from .loader_constants import (
    # Exception classes
    LoaderError,
    CacheError,
    FileLoadError,
    ValidationError,
    PluginTrustError,
    # Color constants
    COLOR_LOADER,
    COLOR_SUBLOADER,
    # Cache type constants
    CACHE_TYPE_SYSTEM,
    CACHE_TYPE_PINNED,
    CACHE_TYPE_SCHEMA,
    CACHE_TYPE_PLUGIN,
    CACHE_TYPE_ALL,
    # Cache key constants
    CACHE_KEY_PREFIX,
    # File type constants
    FILE_TYPE_UI,
    FILE_TYPE_SCHEMA,
    FILE_TYPE_CONFIG,
    # Session key constants
    SESSION_KEY_VAFILE,
    SESSION_KEY_VAFOLDER,
    # Message constants
    MSG_READY,
    MSG_START,
    MSG_CACHED,
    MSG_RETURN,
    MSG_READING,
    # Error message templates
    ERROR_PLUGIN_NOT_FOUND,
    ERROR_PLUGIN_LOAD_FAILED,
    ERROR_NO_PARSER,
    ERROR_FILE_NOT_FOUND,
    ERROR_PERMISSION_DENIED,
    ERROR_GENERIC,
    ERROR_CACHE_MISS,
    ERROR_INVALID_CACHE_TYPE,
    ERROR_INVALID_MAX_SIZE,
    ERROR_INVALID_FILE_PATH,
    ERROR_INVALID_CACHE_CONFIG,
    # Default value constants
    DEFAULT_PATH_SYMBOL,
    DEFAULT_SYSTEM_MAX_SIZE,
    DEFAULT_PLUGIN_MAX_SIZE,
    # File extension constants
    PLUGIN_EXTENSION,
    # File prefix constants
    ZMACHINE_PREFIX,
    # File I/O constants
    FILE_MODE_READ,
    FILE_ENCODING_UTF8,
    # Display style constants
    STYLE_SINGLE,
    STYLE_FULL,
    STYLE_TILDE,
    # Indent constants
    INDENT_ROOT,
    INDENT_PRIMARY,
    INDENT_SECONDARY,
    # Statistics key constants
    STAT_KEY_NAMESPACE,
    STAT_KEY_SIZE,
    STAT_KEY_ALIASES,
    STAT_KEY_ACTIVE_CONNECTIONS,
    STAT_KEY_CONNECTIONS,
    STAT_KEY_HITS,
    STAT_KEY_MISSES,
    STAT_KEY_HIT_RATE,
    # Kwargs key constants
    KWARGS_KEY_ZPATH,
    KWARGS_KEY_FILE_PATH,
    KWARGS_KEY_DEFAULT,
    # Log prefix constants
    LOG_PREFIX_ORCHESTRATOR,
    LOG_PREFIX_SYSTEM_CACHE,
    LOG_PREFIX_PINNED_CACHE,
    LOG_PREFIX_SCHEMA_CACHE,
    LOG_PREFIX_PLUGIN_CACHE,
    LOG_PREFIX_LOADER_IO,
)

# ============================================================================
# PUBLIC API EXPORTS
# ============================================================================

__all__ = [
    # Tier 3: Cache Orchestrator
    "CacheOrchestrator",  # Unified cache router (PRIMARY API)
    # Tier 2.5: Validation
    "LoaderValidator",    # Validation layer for configs and paths (VALIDATION API)
    # Tier 2: Cache Implementations
    "SystemCache",        # UI/config file cache (ADVANCED API)
    "PinnedCache",        # User alias cache (ADVANCED API)
    "SchemaCache",        # DB connection cache (ADVANCED API)
    "PythonModuleCache",  # Python module cache (ADVANCED API)
    # Tier 1: Foundation I/O
    "load_file_raw",      # Raw file I/O (FOUNDATION API)
    # Tier 6: User Utilities
    "cache_utils",        # User-facing cache utilities (USER API)
    # Plugin-trust gate
    "verify_plugin_trust",
    # Tier 0: Exception Classes
    "LoaderError", "CacheError", "FileLoadError", "ValidationError", "PluginTrustError",
    # Tier 0: Constants (ALL CONSTANTS)
    "COLOR_LOADER", "COLOR_SUBLOADER",
    "CACHE_TYPE_SYSTEM", "CACHE_TYPE_PINNED", "CACHE_TYPE_SCHEMA", "CACHE_TYPE_PLUGIN", "CACHE_TYPE_ALL",
    "CACHE_KEY_PREFIX",
    "FILE_TYPE_UI", "FILE_TYPE_SCHEMA", "FILE_TYPE_CONFIG",
    "SESSION_KEY_VAFILE", "SESSION_KEY_VAFOLDER",
    "MSG_READY", "MSG_START", "MSG_CACHED", "MSG_RETURN", "MSG_READING",
    "ERROR_PLUGIN_NOT_FOUND", "ERROR_PLUGIN_LOAD_FAILED", "ERROR_NO_PARSER",
    "ERROR_FILE_NOT_FOUND", "ERROR_PERMISSION_DENIED", "ERROR_GENERIC",
    "ERROR_CACHE_MISS", "ERROR_INVALID_CACHE_TYPE",
    "ERROR_INVALID_MAX_SIZE", "ERROR_INVALID_FILE_PATH", "ERROR_INVALID_CACHE_CONFIG",
    "DEFAULT_PATH_SYMBOL", "DEFAULT_SYSTEM_MAX_SIZE", "DEFAULT_PLUGIN_MAX_SIZE",
    "PLUGIN_EXTENSION",
    "ZMACHINE_PREFIX",
    "FILE_MODE_READ", "FILE_ENCODING_UTF8",
    "STYLE_SINGLE", "STYLE_FULL", "STYLE_TILDE",
    "INDENT_ROOT", "INDENT_PRIMARY", "INDENT_SECONDARY",
    "STAT_KEY_NAMESPACE", "STAT_KEY_SIZE", "STAT_KEY_ALIASES",
    "STAT_KEY_ACTIVE_CONNECTIONS", "STAT_KEY_CONNECTIONS",
    "STAT_KEY_HITS", "STAT_KEY_MISSES", "STAT_KEY_HIT_RATE",
    "KWARGS_KEY_ZPATH", "KWARGS_KEY_FILE_PATH", "KWARGS_KEY_DEFAULT",
    "LOG_PREFIX_ORCHESTRATOR", "LOG_PREFIX_SYSTEM_CACHE", "LOG_PREFIX_PINNED_CACHE",
    "LOG_PREFIX_SCHEMA_CACHE", "LOG_PREFIX_PLUGIN_CACHE", "LOG_PREFIX_LOADER_IO",
]
