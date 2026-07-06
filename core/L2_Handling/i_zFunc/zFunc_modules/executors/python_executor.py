# zOS/core/L2_Handling/i_zFunc/zFunc_modules/executors/python_executor.py

"""
Python function executor with dependency injection and async support.

This module provides execution logic for Python functions, extracted from
zFunc._execute_function(). It uses the ExecutionMixin for shared logic.

Architecture Position
--------------------
**Tier 2: Manager** - Specialized executor for Python functions

Pattern Source:
    - b_zComm/zComm_modules/comm_http.py (manager pattern)
    - ExecutionMixin (shared logic via mixin composition)

Key Functionality
-----------------
1. **Execute Python Functions**: Run Python callables with args/kwargs
2. **Auto-Injection**: Inject zos, session, context based on signature
3. **Async Support**: Handle coroutines transparently
4. **Error Handling**: Graceful fallback if injection fails

Extracted From
--------------
- zFunc._execute_function() lines 199-254 (56 lines)

Integration Points
------------------
**Used By**:
- zFunc.handle(): Main function execution entry point

**Dependencies**:
- ExecutionMixin: Shared injection and async logic
- func_constants: Parameter names and log messages

Usage Examples
--------------
Example 1: Basic usage
    >>> executor = PythonExecutor(zos)
    >>> def my_func(arg1, zos):
    ...     return zos.config.get(arg1)
    >>> result = executor.execute(my_func, ["setting"], context=None)

Example 2: Async function
    >>> async def fetch_data(url, zos):
    ...     return await zos.http.get(url)
    >>> result = executor.execute(fetch_data, ["http://api.com"], context=None)
    >>> # Coroutine automatically awaited

Version History
---------------
- v1.6.0: Extracted from zFunc._execute_function() during refactoring
"""

from zOS import Any, Callable, List, Optional

from .base_executor import ExecutionMixin
from ..func_constants import (
    PARAM_NAME_ZOS,
    PARAM_NAME_SESSION,
    PARAM_NAME_CONTEXT,
)


class PythonExecutor(ExecutionMixin):
    """
    Python function executor with auto-injection and async support.
    
    Executes Python callables with automatic dependency injection for zos,
    session, and context parameters. Inherits async handling from ExecutionMixin.
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance for debug messages
        session: Session instance for auto-injection
    
    Methods:
        execute: Execute Python function with auto-injection
    """

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any):
        """
        Initialize Python executor.
        
        Parameters
        ----------
        zos : Any
            zOS framework instance providing access to session, logger, etc.
        """
        self.zos = zos
        self.logger = zos.logger
    def execute(
        self,
        func: Callable,
        args: List[Any],
        context: Optional[Any] = None
    ) -> Any:
        """
        Execute Python function with optional zos/session/context injection.
        
        Automatically injects zos, session, and context parameters if the function
        accepts them. Handles both sync and async functions transparently.
        
        Injection Logic:
            1. **zos**: Always injected if function accepts it
            2. **session**: Injected if function accepts it AND not in args[0]
            3. **context**: Injected if function accepts it AND context provided
        
        Parameters
        ----------
        func : Callable
            Python function to execute.
            
        args : List[Any]
            Positional arguments to pass to function.
            
        context : Optional[Any], default=None
            Context dictionary for wizard/dialog integration.
            Only injected if function accepts 'context' parameter.
            
        Returns
        -------
        Any
            Function execution result (awaited if async).
            
        Raises
        ------
        TypeError
            If injection fails and fallback execution also fails.
            
        Examples
        --------
        Example 1: Function with zos parameter
            >>> def get_setting(key, zos):
            ...     return zos.config.get(key)
            >>> result = executor.execute(get_setting, ["my_setting"])
            >>> # zos auto-injected
        
        Example 2: Function with session parameter
            >>> def get_user_data(zos, session):
            ...     return session.get("user_data")
            >>> result = executor.execute(get_user_data, [])
            >>> # Both zos and session auto-injected
        
        Example 3: Async function
            >>> async def fetch_remote(url, zos):
            ...     return await zos.http.get(url)
            >>> result = executor.execute(fetch_remote, ["http://api.com"])
            >>> # Coroutine automatically awaited
        
        Example 4: Function with context (wizard)
            >>> def process_wizard_step(data, context):
            ...     return context.get("zHat", {})
            >>> result = executor.execute(process_wizard_step, [data], context=ctx)
            >>> # context auto-injected
        
        Notes
        -----
        - Uses ExecutionMixin._inject_dependencies() for injection logic
        - Uses ExecutionMixin._handle_async_result() for async handling
        - Graceful fallback: If injection fails (TypeError), retries without kwargs
        - Session injection skipped if args[0] is dict containing 'session' key
        - Context only injected if explicitly provided to execute()
        """
        # Build available dependencies
        available_deps = {
            PARAM_NAME_ZOS: self.zos,
        }

        # Add session if not already in args
        inject_session = True
        if args and isinstance(args[0], dict) and PARAM_NAME_SESSION in args[0]:
            inject_session = False

        if inject_session:
            available_deps[PARAM_NAME_SESSION] = self.session

        # Add context if provided
        if context:
            available_deps[PARAM_NAME_CONTEXT] = context

        # Inject dependencies based on function signature
        kwargs = self._inject_dependencies(func, available_deps)

        # Execute with injected kwargs
        if kwargs:
            try:
                result = func(*args, **kwargs)
            except TypeError as e:
                # Fallback: Execute without kwargs if injection fails
                self.logger.warning("Failed to inject parameters: %s", e)
                result = func(*args)
        else:
            result = func(*args)

        # Handle async results
        return self._handle_async_result(result)
