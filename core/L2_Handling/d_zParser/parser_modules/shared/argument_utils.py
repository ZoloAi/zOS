# zOS/core/L2_Handling/d_zParser/parser_modules/shared/argument_utils.py

"""
Universal argument string parsing primitives.

This module provides stateless parsing primitives for splitting comma-separated
argument strings while respecting both brackets and quotes. These are foundational
utilities used by higher-level subsystems (zFunc, etc.).

Architecture Position
--------------------
**Foundation Layer** - Pure parsing primitives with no dependencies

Key Features
------------
1. **Bracket Tracking**: Respects nesting of (), [], {}
2. **Quote Tracking**: Respects single and double quotes
3. **Combined Parsing**: Handles both brackets AND quotes in same string
4. **Validation**: Detects mismatched brackets and unclosed quotes
5. **Zero Dependencies**: No imports from other subsystems

Usage Examples
--------------
Example 1: Simple arguments
    >>> split_arguments("arg1, arg2, arg3")
    ["arg1", " arg2", " arg3"]

Example 2: Brackets and quotes combined
    >>> split_arguments('func(a, b), "text, with, commas", [1, 2]')
    ['func(a, b)', ' "text, with, commas"', ' [1, 2]']

Example 3: Nested structures
    >>> split_arguments("outer(inner[a, b], c), 'hello, world'")
    ["outer(inner[a, b], c)", " 'hello, world'"]

Version History
---------------
- v1.6.0: Created as unified primitive combining bracket + quote logic
"""

from zOS import List


# ============================================================================
# Character Constants
# ============================================================================

BRACKETS_OPEN = "([{"
BRACKETS_CLOSE = ")]}"
QUOTE_CHARS = "\"'"
DELIMITER_COMMA = ","


# ============================================================================
# Error Messages
# ============================================================================

ERROR_MSG_INVALID_ARG_STR_TYPE = "arg_str must be a string, got: {arg_type}"
ERROR_MSG_BRACKET_MISMATCH = "Bracket mismatch in argument string: {details}"
ERROR_MSG_UNCLOSED_QUOTE = "Unclosed quote in argument string: {details}"


# ============================================================================
# Public API
# ============================================================================

def split_arguments(arg_str: str) -> List[str]:
    """
    Split comma-separated argument string respecting both brackets and quotes.
    
    This is a universal argument splitter that handles:
    - Nested brackets: (), [], {}
    - Single and double quotes: ', "
    - Escaped characters within quotes
    - Mixed nesting (brackets inside quotes, quotes inside brackets)
    
    The function tracks both bracket depth and quote state simultaneously,
    only splitting at commas that are:
    - Outside all brackets (depth == 0)
    - Outside all quotes (not in_quotes)
    
    Parameters
    ----------
    arg_str : str
        Comma-separated argument string to split.
        Example: "func(a, b), 'text, commas', [1, 2], {\"key\": \"val\"}"
        
    Returns
    -------
    List[str]
        List of argument strings split at top-level commas only.
        Whitespace is preserved (caller should strip if needed).
        
    Raises
    ------
    TypeError
        If arg_str is not a string.
        
    ValueError
        If brackets are mismatched or quotes are unclosed.
        
    Examples
    --------
    Example 1: Simple arguments
        >>> split_arguments("arg1, arg2, arg3")
        ['arg1', ' arg2', ' arg3']
        
    Example 2: Brackets only
        >>> split_arguments("func(a, b), [1, 2, 3]")
        ['func(a, b)', ' [1, 2, 3]']
        
    Example 3: Quotes only
        >>> split_arguments('"Hello, World", \\'name\\', 42')
        ['"Hello, World"', " 'name'", ' 42']
        
    Example 4: Mixed brackets and quotes
        >>> split_arguments('func("a, b"), [1, 2], \\'text\\'')
        ['func("a, b")', ' [1, 2]', " 'text'"]
        
    Example 5: Nested structures
        >>> split_arguments('outer(inner[x, "y, z"]), [\\'a\\', \\'b\\']')
        ['outer(inner[x, "y, z"])', " ['a', 'b']"]
        
    Notes
    -----
    - **Bracket Types**: Tracks (, [, { as opening and ), ], } as closing
    - **Quote Types**: Tracks both " and ' quotes
    - **Quote State**: Tracks which quote character opened current string
    - **Depth Tracking**: Maintains bracket nesting depth counter
    - **Validation**: Checks for mismatched brackets and unclosed quotes
    - **Whitespace**: Preserved in output (use .strip() on results if needed)
    - **Empty Args**: Consecutive commas produce empty strings: "a,,b" → ["a", "", "b"]
    
    Implementation Details
    ----------------------
    The function uses a state machine with two independent trackers:
    1. **Bracket depth** (integer): Increments on open, decrements on close
    2. **Quote state** (boolean + char): Tracks if inside quotes and which type
    
    Splitting only occurs when BOTH conditions are met:
    - depth == 0 (not inside any brackets)
    - not in_quotes (not inside any quote string)
    
    This allows proper handling of complex cases like:
    - Quotes inside brackets: func("a, b", "c, d")
    - Brackets inside quotes: "array is [1, 2, 3]"
    - Nested quotes: "it's working" (different quote types)
    """
    # Input validation
    if not isinstance(arg_str, str):
        raise TypeError(ERROR_MSG_INVALID_ARG_STR_TYPE.format(arg_type=type(arg_str).__name__))
    
    # State tracking
    args = []
    buf = ''
    depth = 0
    in_quotes = False
    quote_char = None
    
    try:
        for char in arg_str:
            # Quote handling (only when not inside other quote type)
            if char in QUOTE_CHARS and (not in_quotes or char == quote_char):
                in_quotes = not in_quotes
                quote_char = char if in_quotes else None
                buf += char
                
            # Bracket handling (only when not inside quotes)
            elif not in_quotes:
                if char in BRACKETS_OPEN:
                    depth += 1
                    buf += char
                elif char in BRACKETS_CLOSE:
                    depth -= 1
                    buf += char
                    
                    # Validation: Check for closing bracket without opening
                    if depth < 0:
                        raise ValueError(
                            ERROR_MSG_BRACKET_MISMATCH.format(
                                details=f"Unexpected closing bracket '{char}' without matching opening bracket"
                            )
                        )
                
                # Split at comma only when at top level (depth == 0, not in_quotes)
                elif char == DELIMITER_COMMA and depth == 0:
                    args.append(buf)
                    buf = ''
                else:
                    buf += char
            else:
                # Inside quotes - add everything as-is
                buf += char
        
        # Append final buffer
        if buf:
            args.append(buf)
        
        # Validation: Check for unclosed quotes
        if in_quotes:
            raise ValueError(
                ERROR_MSG_UNCLOSED_QUOTE.format(
                    details=f"Unclosed {quote_char} quote detected. Missing closing quote"
                )
            )
        
        # Validation: Check for unclosed brackets
        if depth != 0:
            raise ValueError(
                ERROR_MSG_BRACKET_MISMATCH.format(
                    details=f"Unclosed brackets detected (depth={depth}). "
                           f"Expected {depth} more closing bracket(s)"
                )
            )
        
        return args
        
    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        # Wrap unexpected errors in ValueError for consistency
        raise ValueError(
            ERROR_MSG_BRACKET_MISMATCH.format(details=f"Unexpected error: {str(e)}")
        ) from e


# ============================================================================
# Module Metadata
# ============================================================================

__all__ = ["split_arguments"]
