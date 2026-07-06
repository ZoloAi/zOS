# zOS/core/L2_Handling/i_zFunc/zFunc_modules/protocols.py
# pylint: disable=unnecessary-ellipsis

"""
Type protocols for zFunc subsystem.

This module defines Protocol classes for type hinting and interface contracts
across the zFunc subsystem. Protocols enable static type checking without
requiring inheritance.

Architecture Position
--------------------
**Tier 1: Foundation** - Type definitions and interfaces

Pattern Source:
    - Python typing.Protocol (PEP 544)
    - Duck typing with type safety

Key Protocols
-------------
1. **ExecutorProtocol**: Common interface for all executors
2. **LoaderProtocol**: Common interface for module loaders

Usage Examples
--------------
Example 1: Type hinting with protocol
    >>> def execute_with_timeout(executor: ExecutorProtocol, func, args):
    ...     return executor.execute(func, args)
    >>> # Works with any executor implementing the protocol

Example 2: Type checking
    >>> from typing import TYPE_CHECKING
    >>> if TYPE_CHECKING:
    ...     from .protocols import ExecutorProtocol

Version History
---------------
- v1.6.0: Created during refactoring (optional enhancement)
"""

from zOS import Protocol, Any, List, Optional


class ExecutorProtocol(Protocol):
    """
    Common interface for all executor types.
    
    Defines the contract that all executors (Python, plugin, JavaScript)
    should follow. Enables type checking without requiring inheritance.
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance for debug/error messages
    
    Methods:
        execute: Execute a function with arguments
    """

    zos: Any
    logger: Any

    def execute(
        self,
        func: Any,
        args: List[Any],
        context: Optional[Any] = None
    ) -> Any:
        """
        Execute a function with arguments and optional context.
        
        Parameters
        ----------
        func : Any
            Callable function to execute.
            
        args : List[Any]
            Positional arguments for the function.
            
        context : Optional[Any], default=None
            Context dictionary for wizard/dialog integration.
            
        Returns
        -------
        Any
            Result of function execution.
        """
        ...


class LoaderProtocol(Protocol):
    """
    Common interface for module loaders.
    
    Defines the contract for loading and caching Python modules.
    Enables type checking for loader implementations.
    
    Methods:
        load: Load a module from file path
        get_cached: Retrieve a cached module
    """

    def load(self, path: str, cache_key: Optional[str] = None) -> Any:
        """
        Load a Python module from file path.
        
        Parameters
        ----------
        path : str
            Absolute path to the Python file.
            
        cache_key : Optional[str], default=None
            Key to use for caching. If None, uses filename.
            
        Returns
        -------
        Any
            Loaded Python module object.
        """
        ...

    def get_cached(self, cache_key: str) -> Optional[Any]:
        """
        Retrieve a cached module by key.
        
        Parameters
        ----------
        cache_key : str
            Cache key (typically filename or module name).
            
        Returns
        -------
        Optional[Any]
            Cached module if found, None otherwise.
        """
        ...


class ParserProtocol(Protocol):
    """
    Common interface for argument parsers.
    
    Defines the contract for parsing function arguments with context injection.
    """

    def parse_arguments(
        self,
        arg_str: Optional[str],
        context: Any,
        logger: Any
    ) -> List[Any]:
        """
        Parse argument string into list of values.
        
        Parameters
        ----------
        arg_str : Optional[str]
            Comma-separated argument string.
            
        context : Any
            Context dictionary for special argument injection.
            
        logger : Any
            Logger instance for debug messages.
            
        Returns
        -------
        List[Any]
            Parsed argument values.
        """
        ...


class CacheProtocol(Protocol):
    """
    Common interface for module caches.
    
    Defines the contract for caching loaded modules.
    """

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached module by key.
        
        Parameters
        ----------
        key : str
            Cache key.
            
        Returns
        -------
        Optional[Any]
            Cached module if found, None otherwise.
        """
        ...

    def set(self, key: str, value: Any) -> None:
        """
        Set cached module.
        
        Parameters
        ----------
        key : str
            Cache key.
            
        value : Any
            Module to cache.
        """
        ...

    def clear(self) -> None:
        """Clear all cached modules."""
        ...


__all__ = [
    "ExecutorProtocol",
    "LoaderProtocol",
    "ParserProtocol",
    "CacheProtocol",
]
