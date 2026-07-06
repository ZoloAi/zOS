# zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_orchestrator.py

"""
Cache orchestrator for unified routing to all cache tiers.

This module provides the central orchestration layer for zLoader's caching system,
routing cache requests to the appropriate Tier 2 cache implementation based on
cache_type parameter. It acts as a unified interface between the zLoader facade
(Tier 5) and the four specialized cache implementations (Tier 2).

Purpose
-------
The CacheOrchestrator serves as Tier 3 (Cache Orchestrator) in the zLoader architecture,
providing a unified interface for all cache operations. It routes requests to System,
Pinned, Schema, or Plugin caches based on cache_type, handles conditional plugin cache
availability, and supports batch operations across all cache tiers.

Architecture
------------
**Tier 3 - Cache Orchestrator (Routes Requests to Tier 2)**
    - Position: Orchestration tier between facade and cache implementations
    - Dependencies: All 4 Tier 2 caches (System, Pinned, Schema, Plugin)
    - Used By: zLoader.py facade (Tier 5)
    - Purpose: Unified cache interface + 4-tier routing + batch operations

Key Features
------------
1. **Unified Interface**: Single entry point for all cache operations (get, set, has,
   clear, get_stats). zLoader facade delegates all cache requests here.

2. **4-Tier Routing**: Routes requests to appropriate cache based on cache_type:
   - "system": SystemCache (UI/config files with LRU eviction)
   - "pinned": PinnedCache (User aliases with no eviction)
   - "schema": SchemaCache (DB connections + transactions)
   - "plugin": PluginCache (Module instances + session injection)

3. **Batch Operations**: Supports cache_type="all" for operations across all tiers:
   - clear("all") - Clears all 4 cache tiers
   - get_stats("all") - Aggregates stats from all tiers

4. **Conditional Plugin Cache**: Gracefully handles zos=None scenario. Plugin cache
   requires zos instance for session injection, so it's optional and created only
   when zos is provided.

5. **Tier-Specific Method Calls**: Uses correct method names per cache tier:
   - System: get/set
   - Pinned: get_alias/load_alias
   - Schema: get_connection/set_connection
   - Plugin: get/set

Design Decisions
----------------
1. **Orchestrator Pattern**: Using orchestrator pattern instead of direct cache access
   provides single point of control, simplifies facade logic, enables batch operations.

2. **Cache Type Routing**: cache_type parameter determines routing. Simple string
   comparison enables clear, predictable routing logic.

3. **Conditional Plugin Cache**: Plugin cache is optional because it requires zos
   instance for session injection. Other caches don't need zos, so they're always
   initialized.

4. **Kwargs Passthrough**: Methods accept **kwargs to support tier-specific parameters
   (e.g., zpath for pinned, file_path for plugin) without coupling orchestrator to
   tier-specific details.

Cache Type Routing
------------------
**system**: SystemCache
    - For: UI files, config files, YAML schemas
    - Features: LRU eviction (max_size=100), pattern matching

**pinned**: PinnedCache
    - For: User-loaded aliases (zLoad command)
    - Features: No eviction, highest priority, user control

**schema**: SchemaCache
    - For: Database connections, transaction management
    - Features: Dual storage (in-memory connections + session metadata)

**plugin**: PluginCache
    - For: Dynamically loaded plugin modules
    - Features: Collision detection, session injection, mtime invalidation, LRU

**all**: Batch Operations
    - For: clear() and get_stats() across all tiers
    - Features: Aggregates results from all 4 caches

External Usage
--------------
**Used By**:
    - zOS/subsystems/zLoader/zLoader.py (Facade - Tier 5)
      Usage: self.cache = CacheOrchestrator(session, logger, zos)
      Purpose: Provides unified cache interface to zLoader facade

Usage Examples
--------------
**Get from Cache**:
    >>> orchestrator = CacheOrchestrator(session, logger, zos)
    >>> data = orchestrator.get("zUI.users.zolo", cache_type="system")
    >>> alias_data = orchestrator.get("my_alias", cache_type="pinned")
    >>> connection = orchestrator.get("db_alias", cache_type="schema")
    >>> module = orchestrator.get("test_plugin", cache_type="plugin")

**Set to Cache**:
    >>> orchestrator.set("zUI.users.zolo", data, cache_type="system")
    >>> orchestrator.set("my_alias", data, cache_type="pinned", zpath="path/to/file")
    >>> orchestrator.set("db_alias", handler, cache_type="schema")
    >>> orchestrator.set("test_plugin", module, cache_type="plugin", file_path="/path/to/test_plugin.py")

**Clear Cache**:
    >>> orchestrator.clear(cache_type="system", pattern="zUI*")
    >>> orchestrator.clear(cache_type="all")  # Clears all 4 tiers

**Get Stats**:
    >>> stats = orchestrator.get_stats(cache_type="all")
    >>> # {'system_cache': {...}, 'pinned_cache': {...}, 'schema_cache': {...}, 'plugin_cache': {...}}

Layer Position
--------------
Layer 1, Position 6 (zLoader - Tier 3 Cache Orchestrator)
    - Tier 1: Foundation (loader_io.py - File I/O)
    - Tier 2: Cache Implementations (System, Pinned, Schema, Plugin)
    - Tier 3: Cache Orchestrator ← THIS MODULE
    - Tier 4: Package Aggregator (loader_modules/__init__.py)
    - Tier 5: Facade (zLoader.py)
    - Tier 6: Package Root (__init__.py)

Dependencies
------------
Internal:
    - loader_cache_system.SystemCache (Tier 2)
    - loader_cache_pinned.PinnedCache (Tier 2)
    - loader_cache_schema.SchemaCache (Tier 2)
    - loader_cache_plugin.PluginCache (Tier 2)

External:
    - zOS imports: Any, Dict, Optional (for type hints)

See Also
--------
- zLoader.py: Uses this orchestrator as unified cache interface
- loader_cache_system.py: System cache for UI/config files
- loader_cache_pinned.py: Pinned cache for user aliases
- loader_cache_schema.py: Schema cache for DB connections
- loader_cache_plugin.py: Plugin cache for dynamic modules

Version History
---------------
- v1.5.4: Industry-grade upgrade (type hints, constants, comprehensive docs,
          DRY refactoring, consistent error handling)
- v1.5.3: Original implementation (129 lines, 4-tier routing, batch operations)
"""

from zOS import Any, Dict, Optional
from .cache_system import SystemCache
from .cache_pinned import PinnedCache
from .cache_schema import SchemaCache
from .cache_python_module import PythonModuleCache

# Import constants from centralized module
from ..loader_constants import (
    CACHE_TYPE_SYSTEM,
    CACHE_TYPE_PINNED,
    CACHE_TYPE_SCHEMA,
    CACHE_TYPE_PLUGIN,
    CACHE_TYPE_ALL,
    LOG_PREFIX_ORCHESTRATOR,
    STAT_KEY_NAMESPACE,
    STAT_KEY_SIZE,
    STAT_KEY_ALIASES,
    STAT_KEY_ACTIVE_CONNECTIONS,
    STAT_KEY_CONNECTIONS,
    KWARGS_KEY_ZPATH,
    KWARGS_KEY_FILE_PATH,
    DEFAULT_SYSTEM_MAX_SIZE,
    DEFAULT_PLUGIN_MAX_SIZE,
)

# ============================================================================
# CACHEORCHESTRATOR CLASS
# ============================================================================


class CacheOrchestrator:
    """
    Routes cache requests to appropriate tier based on cache_type.

    This class provides a unified interface for all cache operations, routing requests
    to the appropriate Tier 2 cache implementation (System, Pinned, Schema, Plugin) based
    on the cache_type parameter. It handles conditional plugin cache initialization and
    supports batch operations across all cache tiers.

    Attributes
    ----------
    session : Dict[str, Any]
        Session dictionary shared across all cache tiers.
    logger : Any
        Logger instance for orchestrator logging.
    zos : Optional[Any]
        zOS framework instance for plugin cache session injection (optional).
    system_cache : SystemCache
        System cache for UI/config files (Tier 2).
    pinned_cache : PinnedCache
        Pinned cache for user aliases (Tier 2).
    schema_cache : SchemaCache
        Schema cache for DB connections (Tier 2).
    plugin_cache : Optional[PluginCache]
        Plugin cache for module instances (Tier 2), None if zos not provided.

    Notes
    -----
    **Tier Initialization**:
        All 4 cache tiers (System, Pinned, Schema, Plugin) are initialized in __init__.
        Plugin cache is conditional: only created if zos instance provided.

    **Cache Type Routing**:
        Methods accept cache_type parameter to determine which cache tier to use:
        - "system" → system_cache
        - "pinned" → pinned_cache
        - "schema" → schema_cache
        - "plugin" → plugin_cache
        - "all" → batch operation across all tiers (clear, get_stats)
    """

    def __init__(self, session: Dict[str, Any], logger: Any, zos: Optional[Any] = None) -> None:
        """
        Initialize cache orchestrator with all cache tiers and routing registry.

        Parameters
        ----------
        session : Dict[str, Any]
            Session dictionary shared across all cache tiers.
        logger : Any
            Logger instance for orchestrator logging.
        zos : Optional[Any], optional
            zOS framework instance for plugin cache session injection (default: None).

        Notes
        -----
        **Tier Initialization Order**:
            1. System cache (always initialized, max_size=100)
            2. Pinned cache (always initialized, no max_size)
            3. Schema cache (always initialized, no max_size)
            4. Plugin cache (conditional, max_size=50, requires zos for session injection)

        **Registry Pattern** (NEW in v1.6.0):
            Instead of if/elif chains, we use a registry dict that maps cache_type
            to (cache_instance, method_name) tuples. This makes routing declarative,
            easier to extend, and self-documenting.

        **Plugin Cache Conditional**:
            Plugin cache is only initialized if zos is provided. This is because plugin
            cache requires zos instance to inject into loaded modules, enabling plugins
            to access zos.logger, zos.session, zos.data, etc.

        **Default Max Sizes**:
            - System cache: 100 (frequent UI/config file access)
            - Plugin cache: 50 (less frequent plugin loading)
            - Pinned cache: No limit (user aliases, no eviction)
            - Schema cache: No limit (DB connections managed separately)
        """
        self.session = session
        self.logger = logger
        self.zos = zos

        # Initialize all cache tiers
        self.system_cache = SystemCache(session, logger, max_size=DEFAULT_SYSTEM_MAX_SIZE)
        self.pinned_cache = PinnedCache(session, logger)
        self.schema_cache = SchemaCache(session, logger)

        # Re-enable PythonModuleCache for unified module loading (Phase 3 refactoring)
        # This cache handles ALL Python module loading (plugins, functions, etc.)
        self.python_module_cache = PythonModuleCache(session, logger, zos, max_size=DEFAULT_PLUGIN_MAX_SIZE)
        
        # Legacy attribute for backward compatibility
        self.plugin_cache = self.python_module_cache

        # ====================================================================
        # Registry Pattern: Maps cache_type -> (cache_instance, method_names)
        # ====================================================================
        # This replaces if/elif chains with declarative routing configuration.
        # Each cache type maps to a dict of method names for different operations.
        self._cache_registry = {
            CACHE_TYPE_SYSTEM: {
                'cache': self.system_cache,
                'get': 'get',
                'set': 'set',
                'has': 'get',  # SystemCache has no has(), use get() + None check
                'clear': 'clear',
                'stats': 'get_stats',
            },
            CACHE_TYPE_PINNED: {
                'cache': self.pinned_cache,
                'get': 'get_alias',
                'set': 'load_alias',
                'has': 'has_alias',
                'clear': 'clear',
                'stats': 'list_aliases',  # Special case: needs wrapper
            },
            CACHE_TYPE_SCHEMA: {
                'cache': self.schema_cache,
                'get': 'get_connection',
                'set': 'set_connection',
                'has': 'has_connection',
                'clear': 'clear',
                'stats': 'list_connections',  # Special case: needs wrapper
            },
            CACHE_TYPE_PLUGIN: {
                'cache': self.python_module_cache,
                'get': 'get',
                'set': 'set',
                'has': 'get',  # PythonModuleCache has no has(), use get() + None check
                'clear': 'clear',
                'stats': 'get_stats',
                'load': 'load_and_cache',
                'invalidate': 'invalidate',
            },
        }

    def _should_use_cache(self, cache_type: str, target_type: str) -> bool:
        """
        Check if cache_type matches target_type or "all".

        Parameters
        ----------
        cache_type : str
            Requested cache type ("system", "pinned", "schema", "plugin", "all").
        target_type : str
            Target cache type to check against ("system", "pinned", "schema", "plugin").

        Returns
        -------
        bool
            True if cache_type matches target_type or cache_type is "all", False otherwise.

        Examples
        --------
        >>> self._should_use_cache("system", "system")
        True
        >>> self._should_use_cache("all", "system")
        True
        >>> self._should_use_cache("pinned", "system")
        False

        Notes
        -----
        **DRY Helper**:
            This method eliminates repeated `if cache_type in ("...", "all")` patterns
            across clear() and get_stats() methods. Used 16 times total.
        """
        return cache_type == target_type or cache_type == CACHE_TYPE_ALL

    def get(self, key: str, cache_type: str = CACHE_TYPE_SYSTEM, **kwargs) -> Any:
        """
        Route get request to appropriate cache tier using registry pattern.

        Parameters
        ----------
        key : str
            Cache key to retrieve (filename, alias name, connection alias, plugin name).
        cache_type : str, optional
            Cache tier to use: "system", "pinned", "schema", "plugin" (default: "system").
        **kwargs : Any
            Additional tier-specific parameters (e.g., default for system cache).

        Returns
        -------
        Any
            Cached value if found, None otherwise.

        Examples
        --------
        >>> data = orchestrator.get("zUI.users.zolo", cache_type="system")
        >>> alias_data = orchestrator.get("my_alias", cache_type="pinned")
        >>> connection = orchestrator.get("db_alias", cache_type="schema")

        Notes
        -----
        **Registry Pattern** (NEW in v1.6.0):
            Uses self._cache_registry to lookup cache instance and method name.
            This replaces if/elif chains with declarative routing configuration.

        **Routing Logic**:
            - Registry lookup: cache_config = self._cache_registry[cache_type]
            - Method call: getattr(cache_config['cache'], cache_config['get'])(key, **kwargs)
            - Falls through to plugin deprecation warning if not in registry

        **Plugin Cache Handling**:
            If cache_type is "plugin" (not in registry), logs warning and returns None.

        **Unknown Cache Type**:
            If cache_type doesn't match known types, logs warning and returns None.
        """
        # Registry-based routing (NEW in v1.6.0)
        if cache_type in self._cache_registry:
            cache_config = self._cache_registry[cache_type]
            cache_instance = cache_config['cache']
            method_name = cache_config['get']

            # System and Plugin caches accept **kwargs (e.g. default); Pinned/Schema do not
            if cache_type in (CACHE_TYPE_SYSTEM, CACHE_TYPE_PLUGIN):
                return getattr(cache_instance, method_name)(key, **kwargs)
            else:
                # Pinned and Schema don't need **kwargs
                return getattr(cache_instance, method_name)(key)

        # Unknown cache type
        self.logger.warning(f"{LOG_PREFIX_ORCHESTRATOR} Unknown cache_type: {cache_type}")
        return None

    def set(self, key: str, value: Any, cache_type: str = CACHE_TYPE_SYSTEM, **kwargs) -> Any:
        """
        Route set request to appropriate cache tier using registry pattern.

        Parameters
        ----------
        key : str
            Cache key to store (filename, alias name, connection alias, plugin name).
        value : Any
            Value to cache (data, handler, module).
        cache_type : str, optional
            Cache tier to use: "system", "pinned", "schema", "plugin" (default: "system").
        **kwargs : Any
            Tier-specific parameters:
                - pinned: zpath (str) - Path to file for alias
                - plugin: file_path (str) - Path to plugin file

        Returns
        -------
        Any
            Cached value (same as input value parameter).

        Examples
        --------
        >>> orchestrator.set("zUI.users.zolo", data, cache_type="system")
        >>> orchestrator.set("my_alias", data, cache_type="pinned", zpath="path/to/file")
        >>> orchestrator.set("db_alias", handler, cache_type="schema")

        Notes
        -----
        **Registry Pattern** (NEW in v1.6.0):
            Uses self._cache_registry to lookup cache instance and method name.
            This replaces if/elif chains with declarative routing configuration.

        **Routing Logic**:
            - Registry lookup: cache_config = self._cache_registry[cache_type]
            - Method call: getattr(cache_config['cache'], cache_config['set'])(key, value, ...)
            - Falls through to plugin deprecation warning if not in registry

        **Plugin Cache Handling**:
            If cache_type is "plugin" (not in registry), logs warning and returns value.

        **Unknown Cache Type**:
            If cache_type doesn't match known types, logs warning and returns value without caching.
        """
        # Registry-based routing (NEW in v1.6.0)
        if cache_type in self._cache_registry:
            cache_config = self._cache_registry[cache_type]
            cache_instance = cache_config['cache']
            method_name = cache_config['set']

            # Different caches have different method signatures
            if cache_type == CACHE_TYPE_SYSTEM:
                return getattr(cache_instance, method_name)(key, value, **kwargs)
            elif cache_type == CACHE_TYPE_PINNED:
                # Pinned needs: load_alias(alias_name, value, zpath)
                zpath = kwargs.get(KWARGS_KEY_ZPATH, "")
                return getattr(cache_instance, method_name)(key, value, zpath)
            elif cache_type == CACHE_TYPE_SCHEMA:
                # Schema needs: set_connection(alias_name, handler)
                getattr(cache_instance, method_name)(key, value)
                return value
            elif cache_type == CACHE_TYPE_PLUGIN:
                # Plugin needs: set(plugin_name, module, file_path)
                file_path = kwargs.get(KWARGS_KEY_FILE_PATH, "")
                return getattr(cache_instance, method_name)(key, value, file_path)

        # Unknown cache type
        self.logger.warning(f"{LOG_PREFIX_ORCHESTRATOR} Unknown cache_type: {cache_type}")
        return value

    def has(self, key: str, cache_type: str = CACHE_TYPE_SYSTEM) -> bool:
        """
        Check if key exists in specified cache tier using registry pattern.

        Parameters
        ----------
        key : str
            Cache key to check (filename, alias name, connection alias).
        cache_type : str, optional
            Cache tier to check: "system", "pinned", "schema" (default: "system").

        Returns
        -------
        bool
            True if key exists in cache, False otherwise.

        Examples
        --------
        >>> if orchestrator.has("zUI.users.zolo", cache_type="system"):
        ...     data = orchestrator.get("zUI.users.zolo", cache_type="system")

        Notes
        -----
        **Registry Pattern** (NEW in v1.6.0):
            Uses self._cache_registry to lookup cache instance and method name.
            
        **Routing Logic**:
            - Registry lookup: cache_config = self._cache_registry[cache_type]
            - Method call: getattr(cache_config['cache'], cache_config['has'])(key)
            - For system: Special case using get() + None check

        **System Cache Special Case**:
            SystemCache doesn't have a dedicated has() method, so we use get(key) and
            check if result is not None.
        """
        # Registry-based routing (NEW in v1.6.0)
        if cache_type in self._cache_registry:
            cache_config = self._cache_registry[cache_type]
            cache_instance = cache_config['cache']
            method_name = cache_config['has']

            # System/Plugin have no has(); 'has' maps to 'get' → None-check for bool
            if cache_type in (CACHE_TYPE_SYSTEM, CACHE_TYPE_PLUGIN):
                return getattr(cache_instance, method_name)(key) is not None
            else:
                # Pinned and Schema have dedicated has_*() methods
                return getattr(cache_instance, method_name)(key)

        # Unknown cache type
        return False

    def clear(self, cache_type: str = CACHE_TYPE_ALL, pattern: Optional[str] = None) -> None:
        """
        Clear cache entries in specified tier(s).

        Parameters
        ----------
        cache_type : str, optional
            Cache tier(s) to clear: "system", "pinned", "schema", "plugin", "all" (default: "all").
        pattern : Optional[str], optional
            Pattern to match for selective clearing (default: None clears all).
            Supports wildcards: "zUI*", "*_plugin", "*test*" (system, pinned, plugin only).

        Examples
        --------
        >>> orchestrator.clear(cache_type="system", pattern="zUI*")
        >>> orchestrator.clear(cache_type="all")  # Clears all 4 tiers

        Notes
        -----
        **Batch Operation**:
            If cache_type is "all", clears all 4 cache tiers (system, pinned, schema, plugin).

        **Pattern Support**:
            - System cache: Supports pattern (prefix/suffix/substring)
            - Pinned cache: Supports pattern (prefix/suffix/substring)
            - Schema cache: No pattern support (clears all connections)
            - Plugin cache: Supports pattern (prefix/suffix/substring)

        **Plugin Cache Handling**:
            If cache_type is "plugin" or "all" but plugin_cache is None (zos not provided),
            logs warning and skips plugin cache clearing.
        """
        if self._should_use_cache(cache_type, CACHE_TYPE_SYSTEM):
            self.system_cache.clear(pattern)

        if self._should_use_cache(cache_type, CACHE_TYPE_PINNED):
            self.pinned_cache.clear(pattern)

        if self._should_use_cache(cache_type, CACHE_TYPE_SCHEMA):
            self.schema_cache.clear()

        if self._should_use_cache(cache_type, CACHE_TYPE_PLUGIN):
            self.python_module_cache.clear(pattern)

    def get_stats(self, cache_type: str = CACHE_TYPE_ALL) -> Dict[str, Any]:
        """
        Get cache statistics for specified tier(s).

        Parameters
        ----------
        cache_type : str, optional
            Cache tier(s) to get stats from: "system", "pinned", "schema", "plugin", "all" (default: "all").

        Returns
        -------
        Dict[str, Any]
            Dictionary with cache stats, keyed by cache tier name:
                - "system_cache": System cache stats (hits, misses, hit_rate, size, etc.)
                - "pinned_cache": Pinned cache stats (namespace, size, aliases)
                - "schema_cache": Schema cache stats (namespace, active_connections, connections list)
                - "plugin_cache": Plugin cache stats (hits, misses, hit_rate, loads, collisions, etc.)

        Examples
        --------
        >>> stats = orchestrator.get_stats(cache_type="all")
        >>> print(f"System hit rate: {stats['system_cache']['hit_rate']}")
        >>> print(f"Plugin collisions: {stats['plugin_cache']['collisions']}")

        >>> system_stats = orchestrator.get_stats(cache_type="system")
        >>> # {'system_cache': {'hits': 10, 'misses': 2, 'hit_rate': '83.3%', ...}}

        Notes
        -----
        **Batch Operation**:
            If cache_type is "all", aggregates stats from all 4 cache tiers.

        **Tier-Specific Stats Structures**:
            - System: From system_cache.get_stats() (comprehensive stats)
            - Pinned: Custom dict with namespace, size, aliases count
            - Schema: Custom dict with namespace, active_connections, connections list
            - Plugin: From plugin_cache.get_stats() (comprehensive stats including collisions)

        **Plugin Cache Handling**:
            If cache_type is "plugin" or "all" but plugin_cache is None (zos not provided),
            logs warning and excludes plugin_cache from returned stats.
        """
        stats = {}

        if self._should_use_cache(cache_type, CACHE_TYPE_SYSTEM):
            stats[CACHE_TYPE_SYSTEM + "_cache"] = self.system_cache.get_stats()

        if self._should_use_cache(cache_type, CACHE_TYPE_PINNED):
            aliases = self.pinned_cache.list_aliases()
            stats[CACHE_TYPE_PINNED + "_cache"] = {
                STAT_KEY_NAMESPACE: CACHE_TYPE_PINNED + "_cache",
                STAT_KEY_SIZE: len(aliases),
                STAT_KEY_ALIASES: len(aliases)
            }

        if self._should_use_cache(cache_type, CACHE_TYPE_SCHEMA):
            connections = self.schema_cache.list_connections()
            stats[CACHE_TYPE_SCHEMA + "_cache"] = {
                STAT_KEY_NAMESPACE: CACHE_TYPE_SCHEMA + "_cache",
                STAT_KEY_ACTIVE_CONNECTIONS: len(connections),
                STAT_KEY_CONNECTIONS: connections
            }

        if self._should_use_cache(cache_type, CACHE_TYPE_PLUGIN):
            stats[CACHE_TYPE_PLUGIN + "_cache"] = self.python_module_cache.get_stats()

        return stats


# ============================================================================
# MODULE METADATA
# ============================================================================

__all__ = ["CacheOrchestrator"]
