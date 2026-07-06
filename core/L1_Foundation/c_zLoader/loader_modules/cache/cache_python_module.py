# zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_python_module.py

"""
Python module cache for dynamically loaded code with collision detection and session injection.

This module provides a specialized caching layer for Python modules within the zLoader
subsystem. Unlike other caches, the PythonModuleCache uses filename-based keys (not full paths)
with collision detection, automatic mtime invalidation, and zOS framework session injection for
every loaded module. It's the largest and most feature-rich cache implementation.

Purpose
-------
The PythonModuleCache serves as Tier 2 (Cache Implementations) in the zLoader architecture,
providing Python module caching with collision detection, LRU eviction, mtime-based
freshness checking, and automatic zOS framework session injection. It sits alongside other cache
implementations but is the only one that caches executable code (modules).

Architecture
------------
**Tier 2 - Cache Implementations (Plugin Cache)**
    - Position: Cache tier for plugin modules
    - Dependencies: OrderedDict, time, os (from zCLI), Path, importlib.util, zConfig constants
    - Used By: CacheOrchestrator (line 23), zParser (plugin invocation via &PluginName.function)
    - Purpose: Plugin module caching + collision detection + session injection + LRU eviction

Key Features
------------
1. **Collision Detection**: Prevents loading plugins with duplicate filenames from different
   paths. If "test_plugin.py" exists in two directories, raises ValueError with hints.

2. **Filename-Based Keys**: Caches plugins by filename (stem), not full path. Ensures
   consistent access: &test_plugin.function works regardless of plugin location.

3. **Session Injection**: Injects `zos` instance into module BEFORE executing it, enabling
   plugins to access zos.logger, zos.session, zos.data in top-level code.

4. **Mtime Invalidation**: Automatic freshness checking on every get(). Compares file mtime
   vs cached mtime. Invalidates and reloads if file changed.

5. **LRU Eviction**: Uses OrderedDict with move_to_end() for proper LRU behavior. Evicts
   oldest plugins when max_size exceeded.

6. **Comprehensive Stats**: Tracks 6 metrics (hits, misses, loads, evictions, invalidations,
   collisions) for cache performance monitoring.

Design Decisions
----------------
1. **Filename-Based Keys**: Using Path.stem (filename without .py) as cache key ensures
   consistent plugin access. &test_plugin.function always works, regardless of where
   test_plugin.py is located.

2. **Collision Detection**: Critical safety feature. Two plugins with same filename from
   different paths would overwrite each other. Collision detection prevents this with
   clear error messages.

3. **Session Injection Timing**: Injecting zos instance BEFORE exec_module() is critical.
   Allows plugins to use zos in top-level code (imports, constants, decorators).

4. **OrderedDict for LRU**: Provides O(1) move_to_end() for efficient LRU tracking. Standard
   dict maintains insertion order but lacks move_to_end().

5. **Mtime Invalidation**: Ensures plugins reflect latest code changes during development.
   Without this, cached plugins would persist even after file modifications.

Cache Strategy
--------------
**When to Cache**:
    - User invokes plugin via &PluginName.function syntax
    - zParser calls load_and_cache() to load plugin module
    - Module stored with filename as key

**When to Invalidate**:
    - File mtime changed (developer modified plugin code)
    - User explicitly calls invalidate(plugin_name)
    - LRU eviction when max_size exceeded (default: 50 plugins)

**When to Hit**:
    - Same plugin invoked again (same filename)
    - File mtime unchanged (plugin code not modified)
    - Plugin moved to end of OrderedDict (most recently used)

External Usage
--------------
**Used By**:
    - zOS/subsystems/zLoader/loader_modules/cache_orchestrator.py (Line 23)
      Usage: self.plugin_cache = PythonModuleCache(session, logger, zos)
      Purpose: Routes Python module cache requests (type="plugin")

    - zParser: Plugin invocation via &PluginName.function(args) syntax
      Usage: Calls load_and_cache() to load and cache plugin module
      Purpose: Provides fast plugin execution with caching

Usage Examples
--------------
**Load and Cache Module**:
    >>> session = {}
    >>> logger = get_logger()
    >>> zos = get_zos_instance()
    >>> cache = PythonModuleCache(session, logger, zos, max_size=50)
    >>> module = cache.load_and_cache("/path/to/test_module.py")
    >>> # Module cached as "test_module", zos injected

**Get Cached Module**:
    >>> module = cache.get("test_module")
    >>> if module:
    ...     result = module.some_function(args)

**Collision Detection**:
    >>> cache.load_and_cache("/dir1/test_module.py")  # OK
    >>> cache.load_and_cache("/dir2/test_module.py")  # Raises ValueError with hints

**Invalidate Module**:
    >>> cache.invalidate("test_module")
    >>> # Module removed, will be reloaded on next access

**Clear Modules by Pattern**:
    >>> cache.clear("test*")
    >>> # Removes all modules starting with "test"

**Get Stats**:
    >>> stats = cache.get_stats()
    >>> print(f"Hit rate: {stats['hit_rate']}, Collisions: {stats['collisions']}")

Layer Position
--------------
Layer 1, Position 6 (zLoader - Tier 2 Cache Implementations)
    - Tier 1: Foundation (loader_io.py - File I/O)
    - Tier 2: Cache Implementations ← THIS MODULE
        - SystemCache (UI/config files with LRU)
        - PinnedCache (User aliases, no eviction)
        - SchemaCache (DB connections + transactions)
        - PythonModuleCache (Python modules + collision detection) ← THIS (LARGEST)
    - Tier 3: Cache Orchestrator (Routes cache requests)
    - Tier 4: Package Aggregator (loader_modules/__init__.py)
    - Tier 5: Facade (zLoader.py)
    - Tier 6: Package Root (__init__.py)

Dependencies
------------
Internal:
    - None (standalone cache implementation)

External:
    - zCLI imports: os, time, OrderedDict, Any, Dict, List, Optional
    - pathlib: Path (for filename extraction)
    - importlib.util: spec_from_file_location, module_from_spec (for dynamic loading)
    - zConfig constants: SESSION_KEY_ZCACHE, ZCACHE_KEY_PLUGIN

Performance Considerations
--------------------------
- **Memory**: Stores plugin modules in-memory. Typical usage: 5-20 plugins per session.
  Module objects vary by complexity (~10-100KB each).
- **LRU Overhead**: OrderedDict move_to_end() is O(1), minimal overhead.
- **Mtime Checking**: os.path.getmtime() on every get(), typically <1ms overhead.
- **Collision Detection**: Dict lookup is O(1), negligible overhead.
- **Eviction**: Evicts oldest plugin when max_size exceeded (default: 50).

Thread Safety
-------------
This class is NOT thread-safe. Both in-memory OrderedDict and session dict access are not
synchronized. If using zCLI in a multi-threaded environment, ensure proper locking around
plugin cache access.

See Also
--------
- cache_orchestrator.py: Routes cache requests to this class
- loader_cache_system.py: System cache with LRU eviction
- loader_cache_pinned.py: Pinned aliases cache (no eviction)
- loader_cache_schema.py: Schema cache (DB connections + transactions)
- zParser/parser_modules/parser_plugin.py: Plugin invocation logic

Version History
---------------
- v1.5.4: Industry-grade upgrade (type hints, constants, comprehensive docs,
          zConfig modernization, DRY refactoring, robust pattern matching)
- v1.5.3: Original implementation (344 lines, collision detection, session injection,
          mtime invalidation, LRU eviction)
"""

from zOS import os, time, OrderedDict, Any, Dict, List, Optional, Path, importlib
from zOS.L1_Foundation.a_zConfig.zConfig_modules import SESSION_KEY_ZCACHE
from .cache_pattern import matches_pattern
from ..loader_trust import verify_plugin_trust
from ..loader_constants import PluginTrustError

# ============================================================================
# MODULE CONSTANTS
# ============================================================================

# Session Keys
ZCACHE_KEY_PLUGIN: str = "plugin_cache"  # Plugin cache namespace key

# Default Values
DEFAULT_MAX_SIZE: int = 50  # Default maximum number of cached plugins
MODULE_NAME_UNKNOWN: str = "unknown"  # Default module name if __name__ not set

# Log Prefixes
LOG_PREFIX_MISS: str = "[PythonModuleCache MISS]"
LOG_PREFIX_STALE: str = "[PythonModuleCache STALE]"
LOG_PREFIX_INVALID: str = "[PythonModuleCache INVALID]"
LOG_PREFIX_HIT: str = "[PythonModuleCache HIT]"
LOG_PREFIX_LOAD: str = "[PythonModuleCache LOAD]"
LOG_PREFIX_SET: str = "[PythonModuleCache SET]"
LOG_PREFIX_EVICT: str = "[PythonModuleCache EVICT]"
LOG_PREFIX_INVALIDATE: str = "[PythonModuleCache INVALIDATE]"
LOG_PREFIX_CLEAR: str = "[PythonModuleCache CLEAR]"
LOG_PREFIX_ERROR: str = "[PythonModuleCache ERROR]"

# Stats Keys (internal tracking)
STAT_KEY_HITS: str = "hits"
STAT_KEY_MISSES: str = "misses"
STAT_KEY_EVICTIONS: str = "evictions"
STAT_KEY_INVALIDATIONS: str = "invalidations"
STAT_KEY_LOADS: str = "loads"
STAT_KEY_COLLISIONS: str = "collisions"

# Entry Keys (cache entry structure)
ENTRY_KEY_MODULE: str = "module"
ENTRY_KEY_FILEPATH: str = "filepath"
ENTRY_KEY_CACHED_AT: str = "cached_at"
ENTRY_KEY_ACCESSED_AT: str = "accessed_at"
ENTRY_KEY_HITS: str = "hits"
ENTRY_KEY_MTIME: str = "mtime"
ENTRY_KEY_MODULE_NAME: str = "module_name"

# Stats Return Keys (for get_stats() return dict)
STATS_KEY_NAMESPACE: str = "namespace"
STATS_KEY_SIZE: str = "size"
STATS_KEY_MAX_SIZE: str = "max_size"
STATS_KEY_HITS: str = "hits"
STATS_KEY_MISSES: str = "misses"
STATS_KEY_HIT_RATE: str = "hit_rate"
STATS_KEY_LOADS: str = "loads"
STATS_KEY_EVICTIONS: str = "evictions"
STATS_KEY_INVALIDATIONS: str = "invalidations"
STATS_KEY_COLLISIONS: str = "collisions"

# List Return Keys (for list_plugins() return dict)
LIST_KEY_NAME: str = "name"
LIST_KEY_FILEPATH: str = "filepath"
LIST_KEY_HITS: str = "hits"
LIST_KEY_CACHED_AT: str = "cached_at"

# Wildcard Character
WILDCARD_CHAR: str = "*"

# ============================================================================
# PYTHONMODULECACHE CLASS
# ============================================================================


class PythonModuleCache:
    """
    Cache for dynamically loaded Python modules with collision detection and session injection.

    This class implements a specialized caching layer for Python modules using filename-based
    keys (not full paths) with collision detection, automatic mtime invalidation, zOS framework session
    injection, and LRU eviction.

    The PythonModuleCache is the largest and most feature-rich cache implementation, providing:
    - Collision detection (prevents duplicate filenames from different paths)
    - Session injection (injects zos instance before executing plugin)
    - Mtime invalidation (auto-reloads when plugin file changes)
    - LRU eviction (OrderedDict with move_to_end for proper LRU)
    - Comprehensive stats (6 metrics for performance monitoring)

    Attributes
    ----------
    session : Dict[str, Any]
        Session dictionary for storing cache (OrderedDict).
    logger : Any
        Logger instance for cache operation logging.
    zos : Any
        zOS framework instance for session injection into plugins.
    max_size : int
        Maximum number of cached plugins (default: 50).
    stats : Dict[str, int]
        Statistics dict tracking hits, misses, loads, evictions, invalidations, collisions.

    Notes
    -----
    **Collision Detection**:
        If two plugins with the same filename exist in different paths, raises ValueError
        with detailed error message and hints. This prevents silent overwrites.

    **Session Injection Timing**:
        zos instance is injected AFTER exec_module() to overwrite any zos = None
        placeholder in the plugin. This ensures the zos instance is available in functions.

    **LRU Eviction**:
        Uses OrderedDict with move_to_end() for O(1) LRU tracking. When max_size exceeded,
        evicts oldest (least recently used) plugin.
    """

    def __init__(self, session: Dict[str, Any], logger: Any, zos: Any, max_size: int = DEFAULT_MAX_SIZE) -> None:
        """
        Initialize plugin cache with collision detection and session injection.

        Parameters
        ----------
        session : Dict[str, Any]
            Session dictionary for storing cached plugins (OrderedDict).
        logger : Any
            Logger instance for cache operation logging.
        zos : Any
            zOS framework instance for session injection into plugins.
        max_size : int, optional
            Maximum number of cached plugins (default: DEFAULT_MAX_SIZE = 50).

        Notes
        -----
        **Initialization Process**:
            1. Store session, logger, zos, max_size references
            2. Initialize stats dict (6 metrics: hits, misses, loads, evictions, invalidations, collisions)
            3. Ensure session namespace exists (creates OrderedDict if needed)

        **Stats Tracking**:
            - hits: Successful cache lookups
            - misses: Cache misses (plugin not found)
            - loads: Plugins loaded from disk
            - evictions: Plugins evicted due to LRU
            - invalidations: Plugins invalidated due to mtime or explicit invalidate()
            - collisions: Duplicate filename attempts from different paths

        **OrderedDict**:
            Cache is stored as OrderedDict for LRU tracking. If existing cache is regular dict,
            _ensure_namespace() converts it to OrderedDict.
        """
        self.session = session
        self.max_size = max_size
        self.logger = logger
        self.zos = zos

        # Statistics tracking
        self.stats: Dict[str, int] = {
            STAT_KEY_HITS: 0,
            STAT_KEY_MISSES: 0,
            STAT_KEY_EVICTIONS: 0,
            STAT_KEY_INVALIDATIONS: 0,
            STAT_KEY_LOADS: 0,
            STAT_KEY_COLLISIONS: 0
        }

        # Ensure namespace exists
        self._ensure_namespace()

    @property
    def _cache(self) -> OrderedDict:
        """
        Get session cache dict for plugin cache.

        Returns
        -------
        OrderedDict
            Session cache OrderedDict containing plugin entries.

        Notes
        -----
        This property encapsulates the session path for cache storage,
        reducing code duplication across methods (9 uses).
        """
        return self.session[SESSION_KEY_ZCACHE][ZCACHE_KEY_PLUGIN]

    def _ensure_namespace(self) -> None:
        """
        Ensure plugin_cache namespace exists in session (OrderedDict).

        Notes
        -----
        **Creates Two-Level Namespace**:
            1. `session[SESSION_KEY_ZCACHE]` - Top-level cache namespace
            2. `session[SESSION_KEY_ZCACHE][ZCACHE_KEY_PLUGIN]` - Plugin cache namespace

        **OrderedDict Conversion**:
            If existing cache is regular dict (from deserialization or legacy code),
            converts it to OrderedDict for LRU tracking. This ensures move_to_end()
            always works.

        **When Called**:
            - During __init__ to ensure namespace exists
            - Before any cache operations
        """
        try:
            if SESSION_KEY_ZCACHE not in self.session:
                self.session[SESSION_KEY_ZCACHE] = {}

            if ZCACHE_KEY_PLUGIN not in self.session[SESSION_KEY_ZCACHE]:
                self.session[SESSION_KEY_ZCACHE][ZCACHE_KEY_PLUGIN] = OrderedDict()
            elif not isinstance(self.session[SESSION_KEY_ZCACHE][ZCACHE_KEY_PLUGIN], OrderedDict):
                # Convert existing dict to OrderedDict for LRU support
                self.session[SESSION_KEY_ZCACHE][ZCACHE_KEY_PLUGIN] = OrderedDict(
                    self.session[SESSION_KEY_ZCACHE][ZCACHE_KEY_PLUGIN]
                )
        except Exception as e:
            self.logger.debug(f"{LOG_PREFIX_ERROR} _ensure_namespace - {e}")

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """
        Check if key matches wildcard pattern (robust pattern matching).

        Parameters
        ----------
        key : str
            Plugin name to check (e.g., "test_plugin").
        pattern : str
            Pattern with optional wildcards (e.g., "test*", "*_plugin", "*test*").

        Returns
        -------
        bool
            True if key matches pattern, False otherwise.

        Notes
        -----
        **Pattern Types**:
            - Prefix: "test*" matches "test_plugin", "test_utils", "test123"
            - Suffix: "*_plugin" matches "test_plugin", "db_plugin", "auth_plugin"
            - Substring: "*test*" matches "test_plugin", "my_test", "unittest"
            - Exact: "test_plugin" matches only "test_plugin"

        **Wildcard Handling**:
            - Leading wildcard: startswith check
            - Trailing wildcard: endswith check
            - Both wildcards: substring check
            - No wildcards: exact match

        Examples
        --------
        >>> cache._matches_pattern("test_plugin", "test*")
        True
        >>> cache._matches_pattern("test_plugin", "*_plugin")
        True
        >>> cache._matches_pattern("test_plugin", "*test*")
        True
        >>> cache._matches_pattern("test_plugin", "db*")
        False
        """
        return matches_pattern(key, pattern)

    def get(self, plugin_name: str, default: Any = None) -> Optional[Any]:
        """
        Get plugin module from cache by filename with automatic freshness checking.

        Parameters
        ----------
        plugin_name : str
            Plugin filename (without .py extension), e.g., "test_plugin".
        default : Any, optional
            Default value if plugin not found or invalidated (default: None).

        Returns
        -------
        Optional[Any]
            Cached module if found and fresh, default value otherwise.

        Examples
        --------
        >>> module = cache.get("test_plugin")
        >>> if module:
        ...     result = module.some_function(args)

        Notes
        -----
        **Freshness Checking**:
            On every get(), compares current file mtime vs cached mtime. If different,
            invalidates cache entry and returns default. This ensures plugins reflect
            latest code changes during development.

        **LRU Tracking**:
            On cache hit, moves plugin to end of OrderedDict (most recently used).
            This ensures proper LRU eviction when max_size exceeded.

        **Stats Tracking**:
            - Increments hits on cache hit
            - Increments misses on cache miss
            - Increments invalidations on stale or missing file

        **OSError Handling**:
            If file no longer exists, invalidates cache entry gracefully and returns default.
        """
        try:
            cache = self._cache

            if plugin_name not in cache:
                self.stats[STAT_KEY_MISSES] += 1
                self.logger.debug(f"{LOG_PREFIX_MISS} {plugin_name}")
                return default

            entry = cache[plugin_name]
            file_path = entry.get(ENTRY_KEY_FILEPATH)

            # Check freshness (mtime)
            if file_path:
                try:
                    current_mtime = os.path.getmtime(file_path)
                    cached_mtime = entry.get(ENTRY_KEY_MTIME, 0)

                    if current_mtime != cached_mtime:
                        # File changed - invalidate
                        self.stats[STAT_KEY_INVALIDATIONS] += 1
                        self.logger.debug(
                            f"{LOG_PREFIX_STALE} {plugin_name} (mtime: {cached_mtime} => {current_mtime})"
                        )
                        del cache[plugin_name]
                        return default
                except OSError:
                    # File doesn't exist anymore - invalidate
                    self.stats[STAT_KEY_INVALIDATIONS] += 1
                    self.logger.debug(f"{LOG_PREFIX_INVALID} {plugin_name} (file not found)")
                    del cache[plugin_name]
                    return default

            # Cache hit - move to end (most recent)
            cache.move_to_end(plugin_name)
            entry[ENTRY_KEY_ACCESSED_AT] = time.time()
            entry[ENTRY_KEY_HITS] = entry.get(ENTRY_KEY_HITS, 0) + 1

            self.stats[STAT_KEY_HITS] += 1
            self.logger.debug(f"{LOG_PREFIX_HIT} {plugin_name} (hits: {entry[ENTRY_KEY_HITS]})")

            return entry.get(ENTRY_KEY_MODULE)

        except Exception as e:
            self.logger.debug(f"{LOG_PREFIX_ERROR} {plugin_name} - {e}")
            return default

    def load_and_cache(self, file_path: str, plugin_name: Optional[str] = None) -> Any:
        """
        Load plugin module and cache it by filename with collision detection and session injection.

        Parameters
        ----------
        file_path : str
            Absolute path to plugin file (e.g., "/path/to/test_plugin.py").
        plugin_name : Optional[str], optional
            Plugin name override. If None, uses filename stem (default: None).

        Returns
        -------
        Any
            Loaded and cached module object with zos instance injected.

        Raises
        ------
        ValueError
            If module cannot be loaded or filename collision detected.

        Examples
        --------
        >>> module = cache.load_and_cache("/path/to/test_plugin.py")
        >>> # Module cached as "test_plugin", accessible via zos

        >>> module = cache.load_and_cache("/dir1/test_plugin.py")
        >>> module = cache.load_and_cache("/dir2/test_plugin.py")  # Raises ValueError

        Notes
        -----
        **Collision Detection**:
            If plugin with same filename already cached from different path, raises ValueError
            with detailed error message and hints. This prevents silent overwrites.

        **Collision Handling**:
            - Same filename, same path: Returns cached version (no reload)
            - Same filename, different path: Raises ValueError with collision details
            - New filename: Loads and caches normally

        **Session Injection Timing**:
            Critical: Injects zos instance AFTER exec_module(). This overwrites any
            zos = None placeholder and ensures functions have access to the instance.

            ```python
            spec.loader.exec_module(module)  # Execute first
            module.zos = self.zos  # Inject after (overwrites None)
            ```

        **Module Name**:
            Uses Path.stem to extract filename without extension:
            - "/path/to/test_plugin.py" → "test_plugin"
            - "/dir/IDGenerator.py" → "IDGenerator"

        **Stats Tracking**:
            - Increments loads on successful load
            - Increments collisions on collision detection
        """
        try:
            # Extract filename as plugin name
            if not plugin_name:
                plugin_name = Path(file_path).stem

            # Check for collision
            cache = self._cache
            if plugin_name in cache:
                existing_path = cache[plugin_name].get(ENTRY_KEY_FILEPATH)
                if existing_path != file_path:
                    self.stats[STAT_KEY_COLLISIONS] += 1
                    raise ValueError(
                        f"[ERROR] Plugin name collision: '{plugin_name}'\n"
                        f"   Already loaded from: {existing_path}\n"
                        f"   Attempted to load:   {file_path}\n"
                        f"   Hint: Rename one of the plugin files to avoid collision"
                    )
                # Same file - just return cached version
                return cache[plugin_name][ENTRY_KEY_MODULE]

            # Trust gate: zGuard policy decides whether this path may execute.
            # Permissive no-op in open-core; raises PluginTrustError when denied.
            verify_plugin_trust(file_path, self.zos, self.logger)

            # Load the module
            spec = importlib.util.spec_from_file_location(plugin_name, file_path)
            if not spec or not spec.loader:
                raise ValueError(f"Failed to create module spec for: {file_path}")

            module = importlib.util.module_from_spec(spec)

            # Execute module first (which may define zos = None)
            spec.loader.exec_module(module)

            # Inject framework session AFTER executing module
            # This overwrites any zos = None placeholder in the plugin
            # and gives plugins access to zos.logger, zos.session, zos.data, etc.
            module.zos = self.zos

            self.stats[STAT_KEY_LOADS] += 1
            self.logger.debug(f"{LOG_PREFIX_LOAD} {plugin_name} => {file_path} (session injected)")

            # Cache it by filename
            self.set(plugin_name, module, file_path)

            return module

        except PluginTrustError:
            raise  # Trust denials must propagate unwrapped (security-visible)
        except Exception as e:
            if "collision" in str(e):
                raise  # Re-raise collision errors as-is
            raise ValueError(
                f"Failed to load plugin module: {file_path}\n"
                f"Error: {e}\n"
                f"Hint: Ensure the file is valid Python code"
            ) from e

    def set(self, plugin_name: str, module: Any, file_path: str) -> Any:
        """
        Set plugin module in cache by filename with mtime tracking and LRU eviction.

        Parameters
        ----------
        plugin_name : str
            Plugin filename (cache key), e.g., "test_plugin".
        module : Any
            Loaded module object to cache.
        file_path : str
            Absolute path to plugin file for mtime tracking.

        Returns
        -------
        Any
            The cached module (same as input module parameter).

        Notes
        -----
        **Cache Entry Structure**:
            - module: Module object
            - filepath: Absolute path to plugin file
            - cached_at: Unix timestamp when cached
            - accessed_at: Unix timestamp of last access
            - hits: Number of cache hits (starts at 0)
            - mtime: File modification time for freshness checking
            - module_name: Module __name__ attribute (or "unknown")

        **LRU Eviction**:
            After storing entry, checks if cache size > max_size. If yes, evicts oldest
            (least recently used) plugin via OrderedDict.popitem(last=False).

        **Eviction Logging**:
            Logs evicted plugin details (name, age, hits) for debugging.

        **Mtime Handling**:
            Uses os.path.getmtime() to capture file modification time. If OSError (file
            doesn't exist), skips mtime (entry still cached but won't have freshness checking).
        """
        try:
            cache = self._cache

            # Create cache entry
            entry = {
                ENTRY_KEY_MODULE: module,
                ENTRY_KEY_FILEPATH: file_path,
                ENTRY_KEY_CACHED_AT: time.time(),
                ENTRY_KEY_ACCESSED_AT: time.time(),
                ENTRY_KEY_HITS: 0,
                ENTRY_KEY_MODULE_NAME: module.__name__ if hasattr(module, '__name__') else MODULE_NAME_UNKNOWN
            }

            # Add mtime
            try:
                entry[ENTRY_KEY_MTIME] = os.path.getmtime(file_path)
            except OSError:
                pass  # File doesn't exist, skip mtime

            # Store entry by plugin name
            cache[plugin_name] = entry
            cache.move_to_end(plugin_name)

            self.logger.debug(f"{LOG_PREFIX_SET} {plugin_name} <= {file_path}")

            # Evict oldest if over limit
            while len(cache) > self.max_size:
                evicted_key, evicted_entry = cache.popitem(last=False)
                self.stats[STAT_KEY_EVICTIONS] += 1
                age = time.time() - evicted_entry[ENTRY_KEY_CACHED_AT]
                hits = evicted_entry.get(ENTRY_KEY_HITS, 0)
                self.logger.debug(
                    f"{LOG_PREFIX_EVICT} {evicted_key} (age: {age:.1f}s, hits: {hits})"
                )

        except Exception as e:
            self.logger.debug(f"{LOG_PREFIX_ERROR} {plugin_name} - {e}")

        return module

    def invalidate(self, plugin_name: str) -> None:
        """
        Remove specific plugin from cache by name.

        Parameters
        ----------
        plugin_name : str
            Plugin filename (without .py extension), e.g., "test_plugin".

        Examples
        --------
        >>> cache.invalidate("test_plugin")
        >>> # Plugin removed, will be reloaded on next access

        Notes
        -----
        **When to Use**:
            - User explicitly requests plugin reload
            - Developer modified plugin and wants fresh load
            - Plugin cache entry corrupted

        **Stats Tracking**:
            Increments invalidations counter.
        """
        try:
            cache = self._cache
            if plugin_name in cache:
                del cache[plugin_name]
                self.stats[STAT_KEY_INVALIDATIONS] += 1
                self.logger.debug(f"{LOG_PREFIX_INVALIDATE} {plugin_name}")
        except Exception as e:
            self.logger.debug(f"{LOG_PREFIX_ERROR} {plugin_name} - {e}")

    def clear(self, pattern: Optional[str] = None) -> None:
        """
        Clear cache entries (optionally by pattern with wildcard support).

        Parameters
        ----------
        pattern : Optional[str], optional
            Pattern with optional wildcards (e.g., "test*", "*_plugin", "*test*").
            If None, clears entire cache (default: None).

        Examples
        --------
        >>> cache.clear("test*")
        >>> # Removes test_plugin, test_utils, test123, etc.

        >>> cache.clear("*_plugin")
        >>> # Removes test_plugin, db_plugin, auth_plugin, etc.

        >>> cache.clear()
        >>> # Removes all plugins

        Notes
        -----
        **Pattern Matching**:
            Uses _matches_pattern() for robust wildcard support:
            - Prefix: "test*" matches plugins starting with "test"
            - Suffix: "*_plugin" matches plugins ending with "_plugin"
            - Substring: "*test*" matches plugins containing "test"
            - Exact: "test_plugin" matches only "test_plugin"

        **Performance**:
            Pattern matching iterates over all keys. For large caches, use specific
            patterns rather than "*everything*" wildcards.
        """
        try:
            cache = self._cache

            if pattern:
                # Clear matching keys using robust pattern matching
                keys_to_delete = [k for k in cache.keys() if self._matches_pattern(k, pattern)]
                for key in keys_to_delete:
                    del cache[key]
                self.logger.debug(f"{LOG_PREFIX_CLEAR} {len(keys_to_delete)} entries matching '{pattern}'")
            else:
                # Clear entire cache
                count = len(cache)
                cache.clear()
                self.logger.debug(f"{LOG_PREFIX_CLEAR} {count} entries")

        except Exception as e:
            self.logger.debug(f"{LOG_PREFIX_ERROR} clear - {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Return cache statistics with performance metrics.

        Returns
        -------
        Dict[str, Any]
            Cache statistics dictionary with keys:
                - namespace (str): Cache namespace ("plugin_cache")
                - size (int): Current number of cached plugins
                - max_size (int): Maximum cache size
                - hits (int): Number of cache hits
                - misses (int): Number of cache misses
                - hit_rate (str): Hit rate percentage (e.g., "85.5%")
                - loads (int): Number of plugins loaded from disk
                - evictions (int): Number of LRU evictions
                - invalidations (int): Number of cache invalidations
                - collisions (int): Number of filename collisions detected

        Examples
        --------
        >>> stats = cache.get_stats()
        >>> print(f"Hit rate: {stats['hit_rate']}")
        Hit rate: 85.5%
        >>> print(f"Collisions: {stats['collisions']}")
        Collisions: 2

        Notes
        -----
        **Hit Rate Calculation**:
            hit_rate = (hits / (hits + misses)) * 100
            Returns "0.0%" if no requests yet (avoid division by zero).

        **Error Handling**:
            Returns empty dict {} on any exception.
        """
        try:
            cache = self._cache
            total_requests = self.stats[STAT_KEY_HITS] + self.stats[STAT_KEY_MISSES]
            hit_rate = (self.stats[STAT_KEY_HITS] / total_requests * 100) if total_requests > 0 else 0

            return {
                STATS_KEY_NAMESPACE: ZCACHE_KEY_PLUGIN,
                STATS_KEY_SIZE: len(cache),
                STATS_KEY_MAX_SIZE: self.max_size,
                STATS_KEY_HITS: self.stats[STAT_KEY_HITS],
                STATS_KEY_MISSES: self.stats[STAT_KEY_MISSES],
                STATS_KEY_HIT_RATE: f"{hit_rate:.1f}%",
                STATS_KEY_LOADS: self.stats[STAT_KEY_LOADS],
                STATS_KEY_EVICTIONS: self.stats[STAT_KEY_EVICTIONS],
                STATS_KEY_INVALIDATIONS: self.stats[STAT_KEY_INVALIDATIONS],
                STATS_KEY_COLLISIONS: self.stats[STAT_KEY_COLLISIONS]
            }
        except Exception:
            return {}

    def list_modules(self) -> List[Dict[str, Any]]:
        """
        List all cached Python modules with metadata.

        Returns
        -------
        List[Dict[str, Any]]
            List of module dictionaries, each containing:
                - name (str): Module filename (e.g., "test_module")
                - filepath (str): Absolute path to module file
                - hits (int): Number of cache hits for this module
                - cached_at (float): Unix timestamp when cached

        Examples
        --------
        >>> modules = cache.list_modules()
        >>> for module in modules:
        ...     print(f"{module['name']}: {module['hits']} hits")
        test_module: 5 hits
        calculator: 12 hits

        >>> modules = cache.list_modules()
        >>> # [
        >>> #     {"name": "test_module", "filepath": "/path/to/test_module.py", "hits": 5, "cached_at": 1234567890.0},
        >>> #     {"name": "calculator", "filepath": "/path/to/calculator.py", "hits": 12, "cached_at": 1234567891.0}
        >>> # ]

        Notes
        -----
        **Module Order**:
            Modules listed in OrderedDict iteration order (most recently used last).

        **Error Handling**:
            Returns empty list [] on any exception.

        **Missing Fields**:
            Uses "unknown" for filepath if entry missing ENTRY_KEY_FILEPATH.
            Uses 0 for hits/cached_at if entry missing those keys.
        """
        try:
            cache = self._cache
            return [
                {
                    LIST_KEY_NAME: name,
                    LIST_KEY_FILEPATH: entry.get(ENTRY_KEY_FILEPATH, MODULE_NAME_UNKNOWN),
                    LIST_KEY_HITS: entry.get(ENTRY_KEY_HITS, 0),
                    LIST_KEY_CACHED_AT: entry.get(ENTRY_KEY_CACHED_AT, 0)
                }
                for name, entry in cache.items()
            ]
        except Exception:
            return []
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        Backward compatibility alias for list_modules().
        
        Deprecated: Use list_modules() instead.
        """
        return self.list_modules()
    
    def register_js_plugin(self, file_path: str, plugin_name: Optional[str] = None) -> Any:
        """
        Register a JavaScript plugin as a proxy module.
        
        JavaScript plugins can't be imported into Python like Python plugins.
        Instead, this method creates a proxy module that stores the file path
        and allows functions to be called via zFunc's JavaScript executor.
        
        Parameters
        ----------
        file_path : str
            Absolute path to .js plugin file
        plugin_name : Optional[str], optional
            Plugin name override. If None, uses filename stem (default: None)
        
        Returns
        -------
        Any
            Proxy module object with __js_plugin_path__ attribute
        
        Examples
        --------
        >>> cache = PythonModuleCache(session, logger, zos)
        >>> proxy = cache.register_js_plugin("/path/to/calculator.js")
        >>> # Use via zFunc: z.zfunc.handle("&calculator.add(5, 3)")
        
        Notes
        -----
        **JavaScript Plugin Support**:
            - Creates a SimpleNamespace proxy module
            - Stores file path in __js_plugin_path__ attribute
            - Injects zos instance for consistency with Python plugins
            - Functions are executed via Node.js subprocess through zFunc
        
        **Cache Entry Structure**:
            - Same as Python modules for consistency
            - Marked with is_js_plugin: True
            - Mtime tracked for auto-reload support
        """
        from types import SimpleNamespace
        
        # Extract module name if not provided
        if not plugin_name:
            plugin_name = Path(file_path).stem

        # Trust gate: JS plugins run via Node subprocess (arbitrary code), so the
        # same zGuard policy applies. Permissive no-op in open-core.
        verify_plugin_trust(file_path, self.zos, self.logger)
        
        # Create proxy module namespace
        proxy_module = SimpleNamespace()
        proxy_module.__name__ = plugin_name
        proxy_module.__file__ = file_path
        proxy_module.__js_plugin_path__ = file_path
        proxy_module.zos = self.zos
        
        # Get mtime for freshness tracking
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            mtime = 0
        
        # Store in cache with same structure as Python modules
        self._cache[plugin_name] = {
            ENTRY_KEY_MODULE: proxy_module,
            ENTRY_KEY_FILEPATH: file_path,
            ENTRY_KEY_MTIME: mtime,
            ENTRY_KEY_CACHED_AT: time.time(),
            ENTRY_KEY_ACCESSED_AT: time.time(),
            ENTRY_KEY_HITS: 0,
            ENTRY_KEY_MODULE_NAME: plugin_name,
            'is_js_plugin': True
        }
        
        self.logger.debug(f"[PythonModuleCache] Registered JavaScript plugin: {plugin_name} -> {file_path}")
        return proxy_module
    
    def register_import_module(self, module: Any, module_name: str, import_path: str) -> Any:
        """
        Register an already-imported module (loaded via importlib.import_module).

        For dotted import paths (e.g. "package.module.plugin") there is no source
        file to mtime-track, so this stores the module without freshness checking.
        Centralizes cache-entry construction (SSOT) instead of callers poking _cache.

        Parameters
        ----------
        module : Any
            The imported module object (zos should already be injected by caller).
        module_name : str
            Cache key (filename/leaf name).
        import_path : str
            The dotted import path used to load the module.

        Returns
        -------
        Any
            The registered module.
        """
        self._cache[module_name] = {
            ENTRY_KEY_MODULE: module,
            ENTRY_KEY_FILEPATH: import_path,
            ENTRY_KEY_CACHED_AT: time.time(),
            ENTRY_KEY_ACCESSED_AT: time.time(),
            ENTRY_KEY_HITS: 0,
            ENTRY_KEY_MODULE_NAME: module_name,
            'is_import_path': True,
        }
        self.logger.debug(f"{LOG_PREFIX_SET} {module_name} <= {import_path} (import path)")
        return module

    def check_and_reload_all(self) -> List[str]:
        """
        Check all cached modules for changes and reload if stale.
        
        This method iterates through all cached modules, checks their file
        modification times, and reloads any that have changed on disk. This
        provides active auto-reload functionality for plugin systems.
        
        Returns
        -------
        List[str]
            List of module names that were reloaded due to file changes.
        
        Examples
        --------
        >>> cache = PythonModuleCache(session, logger, zos)
        >>> cache.load_and_cache("/path/to/plugin.py")
        >>> # ... modify plugin.py on disk ...
        >>> reloaded = cache.check_and_reload_all()
        >>> print(f"Reloaded modules: {reloaded}")
        ['plugin']
        
        Notes
        -----
        **Active vs Passive Reload**:
            - Passive (get()): Checks mtime only when module is accessed
            - Active (this method): Proactively checks all cached modules
        
        **Use Cases**:
            - Plugin systems that need to periodically check for updates
            - Development environments with hot-reload requirements
            - Systems that expose a "reload all plugins" command
        
        **Performance**:
            - Calls os.path.getmtime() for each cached module
            - Only reloads modules with changed mtimes
            - Returns quickly if no files changed
        """
        reloaded = []
        
        try:
            cache = self._cache
            
            for module_name in list(cache.keys()):
                entry = cache.get(module_name)
                if not entry:
                    continue
                
                file_path = entry.get(ENTRY_KEY_FILEPATH)
                cached_mtime = entry.get(ENTRY_KEY_MTIME, 0)
                is_js = entry.get('is_js_plugin', False)
                
                # Check if file exists and has changed
                if file_path:
                    try:
                        if not os.path.exists(file_path):
                            # File deleted - invalidate
                            self.invalidate(module_name)
                            self.logger.debug(f"{LOG_PREFIX_INVALID} {module_name} (file deleted)")
                            continue
                        
                        current_mtime = os.path.getmtime(file_path)
                        
                        if current_mtime > cached_mtime:
                            # File changed - reload
                            self.logger.info(f"[PythonModuleCache] Module changed, reloading: {module_name}")
                            
                            # Invalidate old entry
                            self.invalidate(module_name)
                            
                            # Reload from disk (handle JS vs Python)
                            if is_js:
                                self.register_js_plugin(file_path, module_name)
                            else:
                                self.load_and_cache(file_path, module_name)
                            reloaded.append(module_name)
                            
                    except OSError as e:
                        self.logger.debug(f"{LOG_PREFIX_ERROR} {module_name} - {e}")
                        
        except Exception as e:
            self.logger.debug(f"{LOG_PREFIX_ERROR} check_and_reload_all - {e}")
        
        return reloaded


# ============================================================================
# MODULE METADATA
# ============================================================================

__all__ = ["PythonModuleCache"]
