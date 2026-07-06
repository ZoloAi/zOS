# zOS/core/L2_Handling/i_zFunc/zFunc_modules/arg_processing/context_injector.py

"""
Context injection utilities for special argument types (zCLI-specific business logic).

This module handles injection of zCLI-specific argument types like zContext,
zHat, zConv, and context key notation (this.key, zConv.field).

Architecture Position
--------------------
**Tier 1: Foundation** - zCLI-specific special argument processing

Clear Separation from zParser:
    - zParser: Universal parsing primitives (syntax, no business logic)
    - context_injector: zCLI-specific semantics (zContext, zHat, zConv injection)

Extracted From:
    - func_args.py lines 296-365 (70 lines of injection logic)

Key Functionality
-----------------
1. **zContext**: Full context dictionary injection
2. **zHat**: Wizard step context (from zWizard)
3. **zHat[index]**: Wizard result array access
4. **zConv**: Dialog conversation data (from zDialog)
5. **zConv.field**: Dialog field notation
6. **this.key**: Context key notation

Integration Points
------------------
**Used By**:
- argument_processor.process_arguments(): Uses this to handle special argument types

**Dependencies**:
- func_constants: Special argument identifiers

Version History
---------------
- v1.6.1: Moved to arg_processing/ (renamed from parsers/)
- v1.6.0: Extracted from func_args.py during refactoring
"""

from zOS import Any

from ..func_constants import (
    ARG_ZCONTEXT,
    ARG_ZHAT,
    ARG_ZCONV,
    ARG_ZCONV_PREFIX,
    ARG_THIS_PREFIX,
    DEBUG_MSG_INJECTED_ZCONTEXT,
    DEBUG_MSG_INJECTED_ZHAT,
    DEBUG_MSG_INJECTED_ZCONV,
    DEBUG_MSG_RESOLVED_ZCONV_FIELD,
    DEBUG_MSG_RESOLVED_THIS_KEY,
)


def inject_special_argument(arg: str, zContext: Any, logger_instance: Any) -> tuple[bool, Any]:
    """
    Process special argument types with zCLI-specific context injection.
    
    Checks if the argument is a special type (zContext, zHat, zConv, etc.)
    and returns the appropriate value from the context.
    
    This is zCLI business logic, NOT universal parsing. zParser handles syntax;
    this module handles semantics (what zContext, zHat, zConv mean in your app).
    
    Parameters
    ----------
    arg : str
        Argument string to check and process.
        
    zContext : Any
        Context dictionary containing contextual data.
        
    logger_instance : Any
        Logger instance for debug messages.
        
    Returns
    -------
    tuple[bool, Any]
        Tuple of (is_special, value):
        - is_special: True if argument was a special type, False otherwise
        - value: Resolved value (or None if not special)
        
    Examples
    --------
    Example 1: zContext injection
        >>> is_special, value = inject_special_argument("zContext", context, logger)
        >>> # Returns: (True, entire_context_dict)
    
    Example 2: zHat injection
        >>> is_special, value = inject_special_argument("zHat", context, logger)
        >>> # Returns: (True, context["zHat"])
    
    Example 3: zConv field notation
        >>> is_special, value = inject_special_argument("zConv.username", context, logger)
        >>> # Returns: (True, context["zConv"]["username"])
    
    Example 4: Regular argument
        >>> is_special, value = inject_special_argument("'hello'", context, logger)
        >>> # Returns: (False, None)
    """
    is_dict_context = isinstance(zContext, dict)

    # Special argument type 1: zContext (full context injection)
    if arg == ARG_ZCONTEXT:
        logger_instance.debug(DEBUG_MSG_INJECTED_ZCONTEXT)
        return (True, zContext)

    # Special argument type 2: zHat (wizard context from zWizard)
    elif arg == ARG_ZHAT:
        zhat_value = zContext.get(ARG_ZHAT) if is_dict_context else None
        logger_instance.debug(DEBUG_MSG_INJECTED_ZHAT, zhat_value)
        return (True, zhat_value)

    # Special argument type 2b: zHat[index] or zHat[key] (wizard result access)
    elif is_dict_context and arg.startswith("zHat[") and arg.endswith("]"):
        # Extract index/key from brackets: "zHat[0]" -> "0", "zHat[step1]" -> "step1"
        index_or_key = arg[5:-1]  # Remove "zHat[" and "]"
        zhat_obj = zContext.get(ARG_ZHAT)

        if zhat_obj is not None:
            try:
                # Try as integer index first
                idx = int(index_or_key)
                value = zhat_obj[idx]
                logger_instance.debug("Resolved zHat[%s] => %s", index_or_key, value)
            except (ValueError, KeyError, IndexError, TypeError):
                # Try as string key (remove quotes if present)
                key = index_or_key.strip("\"'")
                try:
                    value = zhat_obj[key]
                    logger_instance.debug("Resolved zHat['%s'] => %s", key, value)
                except (KeyError, TypeError):
                    value = None
                    logger_instance.warning("zHat[%s] not found in context", index_or_key)
            return (True, value)
        else:
            logger_instance.warning("zHat not found in context for %s", arg)
            return (True, None)

    # Special argument type 3: zConv (dialog data from zDialog)
    elif arg == ARG_ZCONV:
        zconv_value = zContext.get(ARG_ZCONV) if is_dict_context else None
        logger_instance.debug(DEBUG_MSG_INJECTED_ZCONV, zconv_value)
        return (True, zconv_value)

    # Special argument type 4: zConv.field (dialog field notation)
    elif is_dict_context and arg.startswith(ARG_ZCONV_PREFIX):
        field = arg.replace(ARG_ZCONV_PREFIX, "")
        zconv_data = zContext.get(ARG_ZCONV, {})
        value = zconv_data.get(field) if isinstance(zconv_data, dict) else None
        logger_instance.debug(DEBUG_MSG_RESOLVED_ZCONV_FIELD, field, value)
        return (True, value)

    # Special argument type 5: this.key (context key notation)
    elif is_dict_context and arg.startswith(ARG_THIS_PREFIX):
        key = arg.replace(ARG_THIS_PREFIX, "")
        value = zContext.get(key)
        logger_instance.debug(DEBUG_MSG_RESOLVED_THIS_KEY, key, value)
        return (True, value)

    # Not a special argument
    return (False, None)


__all__ = ["inject_special_argument"]
