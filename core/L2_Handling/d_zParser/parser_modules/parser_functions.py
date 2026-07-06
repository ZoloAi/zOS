# zOS/core/L2_Core/g_zParser/parser_modules/parser_functions.py
"""
Function call resolution for zParser.

Handles parsing and resolution of &function calls and %variable references in zUI content.
This enables calling built-in functions like &zNow and accessing variables like %session.username
directly from YAML configuration.
"""

from zOS import re, Any


def resolve_variables(value: str, zos: Any, context: Any = None) -> str:
    """
    Resolve %variable references in zUI content.

    Thin delegate to the zLoom token SSOT (``zos.zloom.resolve_token_string``).
    zLoom owns the binding grammar; the whole ``%token`` vocabulary — %session,
    %zloom, %auth, %data, %<var>, %<var>.<field> — is resolved there through ONE
    navigator, so render strings, WHERE clauses, and gate values can never drift.

    Syntax (resolved by zLoom):
        %session.<a.b.c>   deep-nav the live zSession root
        %zloom.<a.b.c>     deep-nav the live zSession root (attribute-agnostic)
        %auth.<field>      zSession["zVisitor"][field], gated by authenticated
        %data.<a.b.c>      resolved query data (context["_resolved_data"] / stash)
        %<var>[.<field>]   zSession["zVars"][var] (+ optional deep-nav)

    Args:
        value: String potentially containing %variable references
        zos: zOS instance for session access
        context: Optional execution context (contains _resolved_data from queries)

    Returns:
        String with variable references resolved to their values

    Layering: calls UP into the L3 zLoom subsystem via the runtime ``zos`` handle
    (NOT an import). Before the facade is attached at boot, falls back to the SAME
    SSOT function via a late import, so semantics are identical either way.
    """
    if not zos or not hasattr(zos, 'session'):
        return value

    zloom = getattr(zos, "zloom", None)
    if zloom is not None and hasattr(zloom, "resolve_token_string"):
        return zloom.resolve_token_string(value, context)

    # Boot-before-attach fallback — same implementation, no module-level cross-layer import.
    from zOS.L3_Abstraction.n_zLoom.zLoom_modules.token_resolver import resolve_token_string
    return resolve_token_string(value, zos, context)


def resolve_function_call(value: str, zos: Any) -> str:
    """
    Resolve &function calls in zUI content.
    
    Syntax:
        &zNow → zNow()
        &zNow('date') → zNow('date')
        &zNow(custom_format='yyyy-mm-dd') → zNow(custom_format='yyyy-mm-dd')
    
    Args:
        value: String potentially containing &function calls
        zos: zOS instance for function execution
        
    Returns:
        String with function calls resolved to their values
        
    Examples:
        >>> resolve_function_call("Today is &zNow('date')", zos)
        "Today is 19122025"
        
        >>> resolve_function_call("Report: &zNow", zos)
        "Report: 19122025 14:30:00"
    """
    # Pattern: &functionName or &functionName(...args...)
    pattern = r'&(\w+)(?:\((.*?)\))?'

    def replace_function(match):
        func_name = match.group(1)
        args_str = match.group(2) if match.group(2) else ""

        # Handle zNow
        if func_name == "zNow":
            if not args_str:
                return zos.zfunc.zNow()
            else:
                # Parse simple arg: 'date', 'time', or custom_format='...'
                args_str = args_str.strip().strip("'\"")
                if args_str in ["date", "time", "datetime"]:
                    return zos.zfunc.zNow(format_type=args_str)
                elif args_str.startswith("custom_format="):
                    custom_fmt = args_str.split("=", 1)[1].strip("'\"")
                    return zos.zfunc.zNow(custom_format=custom_fmt)
                else:
                    # Default: treat as format_type
                    return zos.zfunc.zNow(format_type=args_str)

        # Handle zUUID (no args)
        if func_name == "zUUID":
            return zos.zfunc.zUUID()

        # Unknown function - return as-is (no modification)
        return match.group(0)

    return re.sub(pattern, replace_function, value)
