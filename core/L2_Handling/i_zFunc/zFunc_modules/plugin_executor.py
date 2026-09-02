# zOS/core/L2_Handling/i_zFunc/zFunc_modules/plugin_executor.py

"""
Plugin function execution for zFunc subsystem.

Provides comprehensive function execution with async support, error handling,
and automatic zOS and context auto-injection via inspect.
Moved from zParser to zFunc as part of plugin system consolidation.

Public API:
    - execute_plugin_function: Execute with async support and auto-injection

Dependencies:
    - ExecutionMixin: Shared execution logic (injection + async)
    - func_constants: Centralized constants

Refactored: v1.6.0 - Now uses ExecutionMixin to eliminate code duplication
Created: Phase 2 - Moved from g_zParser to i_zFunc
"""

from zOS import Any, Callable, Dict, List, Optional

# Straight from result.py (typing-only imports) — the zos_plugin facade pulls
# in drivers/swap machinery this Tier-1 module must not depend on.
from zos_plugin.result import ZAbort

from .executors.base_executor import ExecutionMixin
from .func_js_executor import BrowserOnlyFunctionError
from .func_constants import (
    PARAM_NAME_ZOS,
    PARAM_NAME_CONTEXT,
    ERROR_MSG_FUNCTION_CALL_FAILED,
    ERROR_MSG_CHECK_SIGNATURE,
    ERROR_MSG_EXECUTION_FAILED,
)


class _PluginExecutorHelper(ExecutionMixin):
    """
    Helper class to use ExecutionMixin for plugin execution.
    
    Wraps ExecutionMixin functionality for use in the execute_plugin_function
    standalone function. This maintains backward compatibility while leveraging
    shared execution logic.
    """

    def __init__(self, zos: Any):
        self.zos = zos
        self.logger = zos.logger


def execute_plugin_function(
    func: Callable,
    args: List[Any],
    kwargs: Dict[str, Any],
    original_value: str,
    zos: Any,
    context: Optional[Any] = None
) -> Any:
    """
    Execute plugin function with async support, error handling, zOS and context auto-injection.
    
    Comprehensive function execution that handles:
    - zOS auto-injection (inspect-based parameter detection)
    - Context auto-injection (for zWizard/zHat access)
    - Async function detection and execution (event loop handling)
    - Error handling with detailed messages
    
    Refactored in v1.6.0:
        - Now uses ExecutionMixin for shared injection/async logic
        - Eliminated 34 lines of duplicated code
        - Maintains identical functionality and signature
    
    zOS Auto-Injection:
        1. Use ExecutionMixin._inject_dependencies() for parameter detection
        2. If 'zos' parameter exists, inject as keyword argument
        3. Plugin gains access to all zOS subsystems
        4. Transparent to caller (no manual injection needed)
    
    Context Auto-Injection:
        1. If 'context' parameter exists, inject as keyword argument
        2. Plugin gains access to zWizard/zHat context
        3. Used for wizard/hat-specific plugin functions
    
    Async Support:
        - Uses ExecutionMixin._handle_async_result() for coroutine handling
        - Supports both CLI mode and Bifrost mode
        - 300-second timeout for async execution
    
    Args:
        func: Callable function to execute
        args: Positional arguments for function
        kwargs: Keyword arguments for function (merged with auto-injected params)
        original_value: Original invocation string (for error messages)
        zos: zOS instance for auto-injection
        context: Optional context for wizard/hat access
    
    Returns:
        Any: Result of function execution (depends on function return type)
    
    Raises:
        ValueError: If execution fails (TypeError, general Exception)
    
    Examples:
        >>> def greet(name, zos):
        ...     zos.display.handle(f"Greeting {name}")
        ...     return f"Hello, {name}!"
        >>> execute_plugin_function(greet, ["Alice"], {}, "&plugin.greet('Alice')", zos)
        "Hello, Alice!"
        # zos was auto-injected
        
        >>> async def fetch_data(url):
        ...     async with aiohttp.ClientSession() as session:
        ...         async with session.get(url) as resp:
        ...             return await resp.json()
        >>> execute_plugin_function(fetch_data, ["http://api.com"], {}, "&plugin.fetch('http://api.com')", zos)
        {"data": [...]}
        # Coroutine automatically awaited
    
    Notes:
        - Uses ExecutionMixin for shared logic (DRY principle)
        - Maintains backward compatibility (same signature)
        - Proper exception chaining (from e)
    
    See Also:
        - plugin_resolver.resolve_plugin_invocation: Uses this for final execution
        - plugin_loader.get_plugin_function: Retrieves callable before execution
        - ExecutionMixin: Shared injection and async handling logic
    """
    try:
        # Create helper to use ExecutionMixin
        helper = _PluginExecutorHelper(zos)

        # Build available dependencies for auto-injection
        available_deps = {
            PARAM_NAME_ZOS: zos,
        }

        if context:
            available_deps[PARAM_NAME_CONTEXT] = context

        # Auto-inject dependencies and merge with provided kwargs
        injected_kwargs = helper._inject_dependencies(func, available_deps)  # pylint: disable=protected-access
        merged_kwargs = {**kwargs, **injected_kwargs}  # Injected params override

        # Execute function
        result = func(*args, **merged_kwargs)

        # Handle async functions (coroutines)
        return helper._handle_async_result(result)  # pylint: disable=protected-access

    except BrowserOnlyFunctionError:
        # Browser-only JS (DOM in a Node subprocess). Let it propagate untouched
        # so the zFunc facade renders the same clean warning on the & path as on
        # the @. path — locator parity (do NOT wrap into a ValueError traceback).
        raise
    except ZAbort as abort:
        # zOS#91: honor ZAbort REGARDLESS of decoration. The @zfunc wrapper
        # already converts it for decorated plugins; an undecorated function's
        # ZAbort used to fall through the generic wrap below into a ValueError —
        # the structured result (and its 4xx status) silently became a bare 500.
        # Same contract either way now: the abort's ZResult IS the return.
        return abort.result
    except TypeError as e:
        raise ValueError(
            f"{ERROR_MSG_FUNCTION_CALL_FAILED.format(original_value)}\n"
            f"Error: {e}\n"
            f"{ERROR_MSG_CHECK_SIGNATURE}"
        ) from e
    except Exception as e:
        raise ValueError(
            f"{ERROR_MSG_EXECUTION_FAILED.format(original_value)}\n"
            f"Error: {e}"
        ) from e
