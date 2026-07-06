# zOS/core/L2_Handling/i_zFunc/zFunc_modules/arg_processing/argument_processor.py

"""
Main argument processor orchestrator (zCLI-specific business logic).

This module provides the main process_arguments() function that orchestrates
argument splitting, zCLI-specific context injection, and value evaluation.

Architecture Position
--------------------
**Tier 2: Orchestrator** - Combines splitting and injection with business logic

Clear Separation from zParser:
    - zParser: Universal parsing primitives (syntax, no semantics)
    - argument_processor: zCLI-specific processing (zContext, zHat, zConv injection)

Extracted From:
    - func_args.py lines 155-381 (227 lines)

Key Functionality
-----------------
1. **Orchestration**: Coordinates splitting and injection
2. **zParser Integration**: Delegates JSON evaluation to zParser (for syntax only)
3. **zCLI Semantics**: Handles zContext, zHat, zConv, this.key (business logic)
4. **Error Handling**: Comprehensive error handling and logging

Integration Points
------------------
**Used By**:
- zFunc._process_args_with_display(): Main entry point for argument processing

**Dependencies**:
- argument_splitter: Delegates to zParser's universal splitting primitive
- context_injector: zCLI-specific special argument type injection
- zParser: Safe JSON expression evaluation (syntax only)
- func_constants: Debug messages and error messages

Usage Examples
--------------
Example 1: Mixed argument types
    >>> context = {"user_id": 42}
    >>> args = process_arguments('this.user_id, "hello", 123', context, split_arguments, logger, zparser)
    [42, "hello", 123]

Example 2: Wizard context
    >>> context = {"zHat": {"step1": "data"}}
    >>> args = process_arguments("zHat", context, split_arguments, logger)
    [{"step1": "data"}]

Version History
---------------
- v1.6.1: Renamed from argument_parser.py to argument_processor.py
- v1.6.0: Extracted from func_args.py during refactoring
"""

from zOS import Any, Callable, List, Optional

from .context_injector import inject_special_argument
from ..func_constants import (
    DEBUG_MSG_NO_ARGS,
    DEBUG_MSG_RAW_ARG,
    DEBUG_MSG_SPLIT_ARGS,
    DEBUG_MSG_EVALUATED_ZPARSER,
    DEBUG_MSG_LITERAL_FALLBACK,
    DEBUG_MSG_FINAL_ARGS,
    ERROR_MSG_PARSE_FAILED,
    ERROR_MSG_INVALID_ARG_STR_TYPE,
    ERROR_MSG_INVALID_SPLIT_FN,
)


def process_arguments(
    arg_str: Optional[str],
    zContext: Any,
    split_fn: Callable[[str], List[str]],
    logger_instance: Any,
    zparser: Any = None
) -> List[Any]:
    """
    Process function arguments from string with zCLI-specific context injection.
    
    This function processes a comma-separated argument string and returns a list
    of processed values. It supports 5 special zCLI argument types for context
    injection, plus safe evaluation via zParser for regular arguments.
    
    Clear Separation:
        - zParser handles syntax: split_arguments(), parse_json_expr()
        - This function handles semantics: zContext, zHat, zConv injection
    
    Special Argument Types (zCLI-Specific):
    1. **zContext**: Injects the full context dictionary
    2. **zHat**: Extracts zHat value from context (zWizard integration)
    3. **zConv**: Extracts zConv value from context (zDialog integration)
    4. **zConv.field**: Extracts specific field from zConv dictionary
    5. **this.key**: Extracts specific key from context dictionary
    
    Regular arguments are evaluated using zParser.parse_json_expr() if available,
    otherwise treated as string literals for safety.
    
    Parameters
    ----------
    arg_str : Optional[str]
        Comma-separated argument string to process. Can be None or empty string
        for functions with no arguments. Example: "zContext, 123, \"hello\""
        
    zContext : Any
        Context dictionary containing all contextual data (wizard state, dialog
        data, session info). Typically a dict, but can be any type. Used for
        special argument injection (zContext, zHat, zConv, this.key).
        
    split_fn : Callable[[str], List[str]]
        Function to split arg_str into individual arguments while respecting
        nested brackets. Typically split_arguments() from argument_splitter.
        
    logger_instance : Any
        Logger instance for debug and error messages. Typically a logging.Logger
        object from Python's logging module.
        
    zparser : Any, optional
        zParser instance for safe JSON expression evaluation. If None, regular
        arguments are treated as string literals. Typically zos.zparser.
        
    Returns
    -------
    List[Any]
        List of processed argument values, ready to pass to target function.
        Order matches the input arg_str. Special arguments are replaced with
        their resolved values.
        
    Raises
    ------
    TypeError
        If arg_str is not a string (when not None/empty) or split_fn not callable.
        
    AttributeError
        If zContext doesn't support dict operations when required (e.g., for
        zConv.field notation when zContext is not a dict).
        
    KeyError
        If a required key is missing from zContext or zConv dictionary.
        
    Exception
        Generic catch-all for unexpected errors during processing. Original error
        is logged and re-raised.
        
    Examples
    --------
    Example 1: Full zContext injection
        >>> context = {"user_id": 123, "session": {...}}
        >>> args = process_arguments("zContext", context, split_arguments, logger)
        >>> print(args)
        [{"user_id": 123, "session": {...}}]
        
    Example 2: zWizard integration (zHat)
        >>> context = {"zHat": {"step1": "data", "step2": "more"}}
        >>> args = process_arguments("zHat", context, split_arguments, logger)
        >>> print(args)
        [{"step1": "data", "step2": "more"}]
        
    Example 3: zDialog integration (zConv)
        >>> context = {"zConv": {"username": "alice", "email": "alice@example.com"}}
        >>> args = process_arguments("zConv", context, split_arguments, logger)
        >>> print(args)
        [{"username": "alice", "email": "alice@example.com"}]
        
    Example 4: Dialog field notation (zConv.field)
        >>> context = {"zConv": {"username": "alice", "age": 30}}
        >>> args = process_arguments("zConv.username, zConv.age", context, split_arguments, logger)
        >>> print(args)
        ["alice", 30]
        
    Example 5: Context key notation (this.key) with mixed types
        >>> context = {"user_id": 42, "name": "Bob"}
        >>> args = process_arguments('this.user_id, this.name, 123, "hello"', 
        ...                          context, split_arguments, logger, zparser)
        >>> print(args)
        [42, "Bob", 123, "hello"]
        
    Notes
    -----
    - **Empty Arguments**: If arg_str is None or empty, returns empty list []
    
    - **zParser Delegation**: Regular arguments (not special types) are evaluated
      via zparser.parse_json_expr() for safe JSON parsing. Falls back to string
      literal if zParser unavailable.
      
    - **Context Type**: zContext is typically a dict, but can be any type. Dict
      operations (.get(), .startswith()) only used when isinstance(zContext, dict)
      check passes.
      
    - **Error Handling**: All errors are logged at error level with full traceback
      before re-raising. Debug logging tracks each processing step.
      
    - **Order Preservation**: Output list maintains same order as input arg_str.
    
    - **Terminology**: We use "process" not "parse" to distinguish from zParser's
      universal parsing primitives. Processing includes zCLI-specific business logic.
    """
    # Input validation
    if arg_str is not None and not isinstance(arg_str, str):
        raise TypeError(ERROR_MSG_INVALID_ARG_STR_TYPE.format(arg_type=type(arg_str).__name__))

    if not callable(split_fn):
        raise TypeError(ERROR_MSG_INVALID_SPLIT_FN.format(split_fn_type=type(split_fn).__name__))

    # Handle empty argument string
    if not arg_str:
        logger_instance.debug(DEBUG_MSG_NO_ARGS)
        return []

    try:
        logger_instance.debug(DEBUG_MSG_RAW_ARG, arg_str)
        args_raw = [arg.strip() for arg in split_fn(arg_str)]
        logger_instance.debug(DEBUG_MSG_SPLIT_ARGS, args_raw)

        processed_args = []

        for arg in args_raw:
            # Check for special argument types (zContext, zHat, zConv, etc.)
            is_special, value = inject_special_argument(arg, zContext, logger_instance)

            if is_special:
                processed_args.append(value)
            else:
                # Regular argument: Use zParser for safe evaluation
                if zparser:
                    evaluated = zparser.parse_json_expr(arg)
                    logger_instance.debug(DEBUG_MSG_EVALUATED_ZPARSER, arg, evaluated)
                else:
                    # No zParser available - treat as string literal for safety
                    evaluated = arg
                    logger_instance.debug(DEBUG_MSG_LITERAL_FALLBACK, arg)
                processed_args.append(evaluated)

        logger_instance.debug(DEBUG_MSG_FINAL_ARGS, processed_args)
        return processed_args

    except TypeError as e:
        logger_instance.error(ERROR_MSG_PARSE_FAILED, e, exc_info=True)
        raise
    except AttributeError as e:
        logger_instance.error(ERROR_MSG_PARSE_FAILED, e, exc_info=True)
        raise
    except KeyError as e:
        logger_instance.error(ERROR_MSG_PARSE_FAILED, e, exc_info=True)
        raise
    except Exception as e:
        logger_instance.error(ERROR_MSG_PARSE_FAILED, e, exc_info=True)
        raise


__all__ = ["process_arguments"]
