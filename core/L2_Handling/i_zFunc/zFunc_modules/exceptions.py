# zOS/core/L2_Handling/i_zFunc/zFunc_modules/exceptions.py

"""
Standardized exceptions for zFunc subsystem.

This module provides a hierarchy of custom exceptions for consistent error
handling across the zFunc subsystem. Replaces inconsistent use of built-in
exceptions (TypeError, ValueError, FileNotFoundError, etc.).

Architecture Position
--------------------
**Tier 1: Foundation** - Error handling infrastructure

Pattern Source:
    - Exception hierarchy best practices
    - Consistent error handling across subsystems

Exception Hierarchy
-------------------
```
zFuncError (base)
├── FunctionNotFoundError
├── ArgumentParsingError
│   ├── InvalidArgumentTypeError
│   └── BracketMismatchError
├── ExecutionError
│   ├── ExecutionTimeoutError
│   └── AsyncExecutionError
├── PluginError
│   ├── PluginNotFoundError
│   └── PluginLoadError
└── JavaScriptError
    ├── NodeNotFoundError
    └── JavaScriptExecutionError
```

Usage Examples
--------------
Example 1: Raise specific exception
    >>> raise FunctionNotFoundError(
    ...     f"Function 'process' not found in module 'utils'",
    ...     function_name="process",
    ...     module_path="/path/to/utils.py"
    ... )

Example 2: Catch exception hierarchy
    >>> try:
    ...     result = executor.execute(func, args)
    ... except ExecutionError as e:
    ...     # Catches ExecutionTimeoutError, AsyncExecutionError
    ...     logger.error(f"Execution failed: {e}")
    ... except zFuncError as e:
    ...     # Catches all zFunc exceptions
    ...     logger.error(f"zFunc error: {e}")

Example 3: Exception with context
    >>> raise ArgumentParsingError(
    ...     "Failed to parse arguments",
    ...     arg_str="zContext, invalid syntax",
    ...     context={"user_id": 123}
    ... )

Version History
---------------
- v1.6.0: Created during refactoring (optional enhancement)
"""

from zOS import Any


class zFuncError(Exception):
    """
    Base exception for all zFunc subsystem errors.
    
    All custom zFunc exceptions inherit from this base class, enabling
    catch-all error handling for zFunc-specific errors.
    
    Attributes:
        message: Human-readable error message
        context: Optional dictionary with additional error context
    """

    def __init__(self, message: str, **context: Any):
        """
        Initialize zFunc error.
        
        Parameters
        ----------
        message : str
            Human-readable error message.
            
        **context : Any
            Additional context information (stored as attributes).
        """
        super().__init__(message)
        self.message = message
        self.context = context

        # Store context items as attributes for easy access
        for key, value in context.items():
            setattr(self, key, value)


# ============================================================================
# Function Resolution Errors
# ============================================================================

class FunctionNotFoundError(zFuncError):
    """
    Function not found in module.
    
    Raised when a requested function doesn't exist in the loaded module.
    
    Context Attributes:
        function_name: Name of the missing function
        module_path: Path to the module
    """
    pass


# ============================================================================
# Argument Parsing Errors
# ============================================================================

class ArgumentParsingError(zFuncError):
    """
    Base class for argument parsing errors.
    
    Context Attributes:
        arg_str: Original argument string
        context: Context dictionary (if available)
    """
    pass


class InvalidArgumentTypeError(ArgumentParsingError):
    """
    Argument has invalid type.
    
    Raised when argument string is not a string or callable is not callable.
    
    Context Attributes:
        arg_type: Actual type of the argument
        expected_type: Expected type
    """
    pass


class BracketMismatchError(ArgumentParsingError):
    """
    Bracket mismatch in argument string.
    
    Raised when brackets are not properly matched (unclosed or unexpected).
    
    Context Attributes:
        bracket_depth: Final bracket depth
        char: Problematic character (if applicable)
    """
    pass


# ============================================================================
# Execution Errors
# ============================================================================

class ExecutionError(zFuncError):
    """
    Base class for function execution errors.
    
    Context Attributes:
        function: Function that failed to execute
        args: Arguments passed to function
        original_error: Original exception (if chained)
    """
    pass


class ExecutionTimeoutError(ExecutionError):
    """
    Function execution exceeded timeout.
    
    Raised when async function execution exceeds the configured timeout.
    
    Context Attributes:
        timeout: Timeout value in seconds
    """
    pass


class AsyncExecutionError(ExecutionError):
    """
    Async function execution failed.
    
    Raised when coroutine execution fails (event loop issues, etc.).
    """
    pass


# ============================================================================
# Plugin Errors
# ============================================================================

class PluginError(zFuncError):
    """
    Base class for plugin-related errors.
    
    Context Attributes:
        plugin_name: Name of the plugin
    """
    pass


class PluginNotFoundError(PluginError):
    """
    Plugin module not found.
    
    Raised when plugin module cannot be found in search paths.
    
    Context Attributes:
        plugin_name: Name of the missing plugin
        search_paths: List of paths searched
    """
    pass


class PluginLoadError(PluginError):
    """
    Plugin module failed to load.
    
    Raised when plugin module exists but cannot be loaded (syntax errors, etc.).
    
    Context Attributes:
        plugin_path: Path to the plugin file
        original_error: Original import/load error
    """
    pass


# ============================================================================
# JavaScript Execution Errors
# ============================================================================

class JavaScriptError(zFuncError):
    """
    Base class for JavaScript execution errors.
    
    Context Attributes:
        file_path: Path to JavaScript file
        function_name: Name of JavaScript function
    """
    pass


class NodeNotFoundError(JavaScriptError):
    """
    Node.js not found on system.
    
    Raised when Node.js is required but not installed or not in PATH.
    """
    pass


class JavaScriptExecutionError(JavaScriptError):
    """
    JavaScript function execution failed.
    
    Raised when JavaScript code fails to execute (syntax errors, runtime errors).
    
    Context Attributes:
        stderr: Error output from Node.js
        exit_code: Exit code from Node.js process
    """
    pass


# ============================================================================
# Module Exports
# ============================================================================

__all__ = [
    # Base
    "zFuncError",

    # Function Resolution
    "FunctionNotFoundError",

    # Argument Parsing
    "ArgumentParsingError",
    "InvalidArgumentTypeError",
    "BracketMismatchError",

    # Execution
    "ExecutionError",
    "ExecutionTimeoutError",
    "AsyncExecutionError",

    # Plugins
    "PluginError",
    "PluginNotFoundError",
    "PluginLoadError",

    # JavaScript
    "JavaScriptError",
    "NodeNotFoundError",
    "JavaScriptExecutionError",
]
