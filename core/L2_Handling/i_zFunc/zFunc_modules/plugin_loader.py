# zOS/core/L2_Handling/i_zFunc/zFunc_modules/plugin_loader.py

"""
Plugin module loading for zFunc subsystem.

Provides module loading with caching and function retrieval from loaded plugins.
Moved from zParser to zFunc as part of plugin system consolidation.

Public API:
    - load_plugin_module: Load and cache plugin module
    - get_plugin_function: Get callable from module

Dependencies:
    - pathlib: Path handling
    - zFunc.module_cache: Module caching

Created: Phase 2 - Moved from g_zParser to i_zFunc
"""

from zOS import Path, Any, Callable

# Import constants from centralized SSOT
from .func_constants import (
    FILE_EXT_PY,
    FILE_EXT_JS,
    CHAR_DOT,
    STR_COLLISION,
    PLUGIN_SEARCH_PATHS,
    ERROR_MSG_PLUGIN_NOT_FOUND,
    ERROR_MSG_SEARCHED_IN,
    ERROR_MSG_PLUGIN_HINT,
    ERROR_MSG_FUNCTION_NOT_FOUND,
    ERROR_MSG_AVAILABLE_FUNCTIONS,
    ERROR_MSG_NOT_CALLABLE,
    LOG_MSG_CACHE_HIT,
    LOG_MSG_CACHE_MISS,
    LOG_MSG_LOADING_PLUGIN,
    LOG_MSG_FAILED_LOAD,
)


def resolve_plugin_path(plugin_name: str, zos: Any, extensions=(FILE_EXT_PY, FILE_EXT_JS)) -> str:
    """
    Resolve a bare plugin name to an absolute file path, language-agnostic.

    This is the SSOT for the ``&Plugin`` auto-folder lookup. It reuses the zPath
    decoder (``zparser.resolve_symbol_path``) — never raw filesystem path math —
    to turn each ``PLUGIN_SEARCH_PATHS`` entry + ``plugin_name`` into a base path,
    then probes the requested ``extensions`` in order. The first existing file
    wins. By defaulting to ``(.py, .js)`` the ``&`` syntax becomes extension
    agnostic: Python and JavaScript plugins enter the system the same way.

    Args:
        plugin_name: Plugin file stem (no extension), e.g. ``"zOS_Demos"``.
        zos: zOS instance (provides ``zparser`` and ``logger``).
        extensions: Ordered extensions to probe. Callers that need a specific
            language (e.g. the Python-module API) pass a narrowed tuple.

    Returns:
        Absolute path to the resolved plugin file.

    Raises:
        ValueError: If no matching file exists under any search path.
    """
    for search_path in PLUGIN_SEARCH_PATHS:
        try:
            # Build + decode the zPath (SSOT) — do NOT hand-roll path joins.
            zpath = f"{search_path}{CHAR_DOT}{plugin_name}"
            parts = zpath.split(CHAR_DOT)
            symbol = parts[0]
            path_parts = parts[1:]
            base_path = zos.zparser.resolve_symbol_path(symbol, [symbol] + path_parts)
        except FileNotFoundError:
            continue
        except Exception as e:
            if STR_COLLISION in str(e).lower():
                raise  # Re-raise collision errors
            zos.logger.debug(LOG_MSG_FAILED_LOAD, search_path, e)
            continue

        for ext in extensions:
            candidate = base_path if base_path.endswith(ext) else f"{base_path}{ext}"
            if Path(candidate).is_file():
                return candidate

    # Not found anywhere
    search_paths_str = ", ".join(PLUGIN_SEARCH_PATHS)
    raise ValueError(
        f"{ERROR_MSG_PLUGIN_NOT_FOUND.format(plugin_name)}\n"
        f"{ERROR_MSG_SEARCHED_IN.format(search_paths_str)}\n"
        f"{ERROR_MSG_PLUGIN_HINT}"
    )


def load_plugin_module(plugin_name: str, zos: Any) -> Any:
    """
    Load and cache plugin module with search path resolution.
    
    Searches standard plugin paths in priority order, resolves zPaths to absolute
    file paths, and loads modules with filename-based caching for fast lookups.
    
    Search Paths (Priority Order):
        1. @ (Workspace root - for demo/test plugins)
        2. @.zTestSuite.demos (Test/demo plugins)
        3. @.utils (Workspace utilities)
        4. @.plugins (Workspace plugins directory)
    
    Cache Strategy:
        - Filename-based caching for O(1) lookups
        - Cache hit: Return immediately
        - Cache miss: Search → Load → Cache → Return
        - Collision detection prevents duplicate filenames
    
    Args:
        plugin_name: Name of plugin file (without .py extension)
        zos: zOS instance with zfunc.module_cache, parser, logger
    
    Returns:
        Any: Loaded Python module
    
    Raises:
        ValueError: If plugin not found in any search path
    
    Examples:
        >>> module = load_plugin_module("test_plugin", zos)
        >>> # Module loaded from @/test_plugin.py or @.utils/test_plugin.py
        
        >>> module = load_plugin_module("IDGenerator", zos)
        >>> # Module loaded from standard search paths
    
    Notes:
        - Uses zOS.zfunc.module_cache for caching
        - Uses zParser.resolve_symbol_path for zPath resolution
        - Collision errors are re-raised (not suppressed)
        - Search order is critical for plugin priority
        - First match wins (stops searching after first load)
    
    See Also:
        - plugin_resolver.resolve_plugin_invocation: Uses this for loading
        - get_plugin_function: Get callable after loading
    """
    # Check cache first (delegate to zLoader - single source of truth)
    cached_module = zos.loader.get_python_module(plugin_name)

    if cached_module:
        zos.logger.debug(LOG_MSG_CACHE_HIT, plugin_name)
        return cached_module

    # Cache miss - resolve (Python-only) via the shared zPath resolver, then load.
    zos.logger.debug(LOG_MSG_CACHE_MISS, plugin_name)
    file_path = resolve_plugin_path(plugin_name, zos, extensions=(FILE_EXT_PY,))

    # Load and cache (by filename) - delegate to zLoader
    zos.logger.debug(LOG_MSG_LOADING_PLUGIN, plugin_name, file_path)
    return zos.loader.load_python_module(file_path, plugin_name)


def get_plugin_function(module: Any, function_name: str, plugin_name: str) -> Callable:
    """
    Get callable function from loaded plugin module with validation.
    
    Retrieves a function from a Python module, validates that it exists and is
    callable, and provides helpful error messages with available functions if
    the requested function is not found.
    
    Validation:
        1. Check if module has attribute with function_name
        2. If not found, list all available public functions
        3. Retrieve function via getattr()
        4. Validate that retrieved object is callable
    
    Args:
        module: Loaded Python module (plugin)
        function_name: Name of function to retrieve
        plugin_name: Plugin name for error messages
    
    Returns:
        Callable: Function object from module
    
    Raises:
        ValueError: If function not found or not callable
    
    Examples:
        >>> module = load_plugin_module("test_plugin", zos)
        >>> func = get_plugin_function(module, "hello", "test_plugin")
        >>> func("Alice")
        "Hello, Alice!"
        
        >>> get_plugin_function(module, "invalid", "test_plugin")
        ValueError: Function not found in plugin 'test_plugin': invalid
        Available functions: hello, goodbye, get_data
    
    Notes:
        - Only lists public functions (not starting with _)
        - Uses hasattr() for existence check
        - Uses callable() for callable validation
        - Provides list of available functions in error message
        - Function names must be valid Python identifiers
    
    See Also:
        - plugin_resolver.resolve_plugin_invocation: Uses this to get function after loading
        - plugin_executor.execute_plugin_function: Executes the returned callable
    """
    if not hasattr(module, function_name):
        available_funcs = [name for name in dir(module)
                          if not name.startswith('_') and callable(getattr(module, name))]
        raise ValueError(
            f"{ERROR_MSG_FUNCTION_NOT_FOUND.format(plugin_name, function_name)}\n"
            f"{ERROR_MSG_AVAILABLE_FUNCTIONS.format(', '.join(available_funcs) if available_funcs else 'none')}"
        )

    func = getattr(module, function_name)

    if not callable(func):
        raise ValueError(
            ERROR_MSG_NOT_CALLABLE.format(function_name, plugin_name)
        )

    return func
