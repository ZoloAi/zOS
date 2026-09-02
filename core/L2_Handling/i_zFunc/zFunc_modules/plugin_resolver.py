# zOS/core/L2_Handling/i_zFunc/zFunc_modules/plugin_resolver.py

"""
Plugin invocation resolver orchestrator for zFunc subsystem.

Provides main entry point for plugin resolution, coordinating all plugin concerns:
loading, argument parsing, and execution. Syntax parsing is delegated to zParser.
Moved from zParser to zFunc as part of plugin system consolidation.

Public API:
    - resolve_plugin_invocation: Main orchestrator for plugin lifecycle

Dependencies:
    - zParser: Syntax parsing (detection and parsing)
    - plugin_loader: Module loading and caching
    - plugin_executor: Function execution with async support

External Usage:
    - dispatch_launcher.py: Uses this for ALL plugin invocations
    - zParser: Delegates execution after parsing syntax

Created: Phase 2 - Moved from g_zParser to i_zFunc
"""

from zOS import Any, Optional

# Import plugin concerns
from .plugin_loader import resolve_plugin_path
from .func_resolver import resolve_callable
from .plugin_executor import execute_plugin_function

# Characters
CHAR_AMPERSAND: str = '&'

# Once-per-process memo so a content-position call (`&math.square` re-rendered
# on every paint) warns ONCE, not per render.
_WARNED_UNDECORATED: set = set()


def warn_if_undecorated(func: Any, file_path: str, function_name: str, zos: Any) -> None:
    """Say it LOUDLY when an `&` dispatch resolves to an undecorated Python callable.

    zOS#91: @zfunc is what installs DI (user/files/data/params...) and the
    return/error contract — when a refactor drops the decorator (or lands it on
    the helper above), the function still dispatches and "succeeds" while
    writing nothing, with zero log evidence. Not a refusal: a plain function is
    legal in VALUE position (`&math.square(5)`), so this warns instead of
    breaking — once per function per process, in the app's session trace.
    JS plugins never carry the decorator, so only `.py` targets are checked.
    """
    if not (isinstance(file_path, str) and file_path.endswith(".py")):
        return
    if getattr(func, "__zfunc__", False):
        return
    key = (file_path, function_name)
    if key in _WARNED_UNDECORATED:
        return
    _WARNED_UNDECORATED.add(key)
    logger = getattr(zos, "logger", None)
    log = getattr(logger, "session_framework", None) or getattr(logger, "framework", None)
    if log is not None:
        log.warning(
            f"[zFunc] '{function_name}' in {file_path} is NOT @zfunc-decorated — "
            f"it will run, but with NO injection (user/files/data/params) and no "
            f"return contract; a save that 'succeeds' silently may be THIS. "
            f"Decorate it with @zfunc unless it is a pure value function."
        )


def resolve_plugin_invocation(value: str, zos: Any, context: Optional[Any] = None) -> Any:
    """
    Resolve plugin function invocation with unified filename-based syntax.
    
    ⚠️ CRITICAL: This function is used externally by dispatch_launcher.py for
    ALL plugin invocations. Signature must remain stable.
    
    Main entry point for plugin resolution. Handles the full lifecycle from
    parsing to execution, with support for caching, async functions, and
    automatic zOS dependency injection and context (zHat) support.
    
    Process Flow:
        1. **Parse**: Delegate to zParser for syntax parsing
        2. **Load**: Load plugin module (with caching in zFunc)
        3. **Get Function**: Retrieve callable from loaded module
        4. **Parse Arguments**: Import and parse arguments
        5. **Execute**: Call function (handles sync/async)
        6. **Return**: Return function result
    
    Cache Strategy:
        - Filename-based caching for O(1) lookups via zFunc.module_cache
        - Cache hit: Immediate function retrieval
        - Cache miss: Search → Load → Cache → Execute
        - Collision detection prevents duplicate filenames
    
    Async Support:
        - Automatically detects async functions (coroutines)
        - CLI mode: Uses asyncio.run()
        - Bifrost mode: Uses run_coroutine_threadsafe()
        - 300-second timeout for async execution
    
    zOS Auto-Injection:
        - Inspects function signature for 'zos' parameter
        - Automatically injects zos instance as kwarg
        - Transparent to caller (no manual injection needed)
        - Enables plugins to access all zOS subsystems
    
    Context Auto-Injection:
        - Inspects function signature for 'context' parameter
        - Automatically injects context as kwarg
        - Used for zWizard/zHat-specific plugins
    
    Syntax:
        &PluginName.function_name(args)
    
    Args:
        value: Plugin invocation string (e.g., "&test_plugin.hello('Alice')")
        zos: zOS instance with zfunc.module_cache, parser, logger
        context: Optional context for wizard/hat access
    
    Returns:
        Any: Result of plugin function execution (depends on function return type)
    
    Raises:
        ValueError: If syntax invalid, plugin not found, or execution fails
    
    Examples:
        >>> zos = zOS()
        
        # Simple function call
        >>> resolve_plugin_invocation("&test_plugin.hello_world('Alice')", zos)
        "Hello, Alice!"
        
        # Function with integer argument
        >>> resolve_plugin_invocation("&math_utils.square(5)", zos)
        25
        
        # Function with multiple arguments
        >>> resolve_plugin_invocation("&math_utils.add(10, 20)", zos)
        30
        
        # Function with keyword arguments
        >>> resolve_plugin_invocation("&greeter.hello(name='Bob', formal=True)", zos)
        "Good day, Bob!"
        
        # Async function (automatically awaited)
        >>> resolve_plugin_invocation("&api_client.fetch_data()", zos)
        {"data": [...]}  # Coroutine automatically awaited
        
        # Function with zOS access (auto-injected)
        >>> resolve_plugin_invocation("&data_processor.analyze()", zos)
        # Plugin internally uses zos.display, zos.zdata, etc.
        {"result": "complete"}
    
    External Usage:
        dispatch_launcher.py:
            return self.zos.zparser.resolve_plugin_invocation(func_spec)
        Purpose: Execute plugin invocations in zFunc commands
    
    Notes:
        - Signature must remain stable for backward compatibility
        - Returns original value if not a plugin invocation string
        - Delegates syntax parsing to zParser
        - All loading/execution in zFunc
        - All errors from modules are propagated upward
    
    See Also:
        - zParser.is_plugin_invocation: Quick detection before resolution
        - zParser.parse_plugin_invocation: Regex-based syntax parsing
        - plugin_loader.load_plugin_module: Module loading with caching
        - plugin_executor.execute_plugin_function: Async handling and zOS injection
        - dispatch_launcher.py: External usage
    """
    if not isinstance(value, str) or not value.startswith(CHAR_AMPERSAND):
        return value

    # Step 1: Parse invocation syntax (delegate to zParser)
    from zOS.L2_Handling.d_zParser.parser_modules.plugin import parse_plugin_invocation
    plugin_name, function_name, args_str = parse_plugin_invocation(value)

    # Step 2: Resolve the plugin to a file via the zPath decoder — language
    # agnostic (.py or .js). The `&` auto-folder lookup and the `@.`/`~` explicit
    # zPath now share the SAME resolver, so language never changes the syntax.
    file_path = resolve_plugin_path(plugin_name, zos)

    # Step 3: Resolve the callable through the SSOT resolver — Python via importlib
    # (gated), JavaScript via the Node executor. Identical for both languages.
    func = resolve_callable(file_path, function_name, zos.logger, zos)

    # zOS#91: an undecorated Python target dispatches fine but silently loses
    # DI + the return contract — warn loudly (once) instead of failing silent.
    warn_if_undecorated(func, file_path, function_name, zos)

    # Step 4: Parse arguments
    from zOS.L2_Handling.d_zParser.parser_modules.plugin import parse_plugin_arguments
    args, kwargs = parse_plugin_arguments(args_str)

    # Step 5: Execute function (with async support and auto-injection)
    return execute_plugin_function(func, args, kwargs, value, zos, context)
