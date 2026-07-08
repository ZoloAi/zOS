# zOS/core/L2_Handling/g_zParser/parser_modules/plugin/plugin_args.py

"""
Plugin argument parsing for plugin package.

Provides comprehensive argument parsing from string to Python types, supporting
rich types (strings, numbers, booleans, None) and both positional and keyword arguments.

Public API:
    - parse_plugin_arguments: Parse argument string to (args, kwargs)
    - smart_split_arguments: Split by comma respecting quotes
    - is_quoted_string: Check if text has matching quotes
    - parse_argument_value: Convert string to Python type

Dependencies:
    - None (pure parsing logic)

Created: Phase 2.2 - Extract Argument Parsing from parser_plugin.py
"""

from zOS import Any, Dict, List, Optional, Tuple

# Characters
CHAR_COMMA: str = ','
CHAR_EQUALS: str = '='
CHAR_QUOTE_DOUBLE: str = '"'
CHAR_QUOTE_SINGLE: str = "'"

# String Booleans
STR_TRUE: str = 'True'
STR_FALSE: str = 'False'
STR_NONE: str = 'None'


def parse_plugin_arguments(args_str: str) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Parse function arguments from string into Python types.
    
    Converts a string of arguments into Python lists and dicts, supporting
    rich types (strings, numbers, booleans, None) and both positional and
    keyword arguments.
    
    Supported Types:
        - **Strings**: "text" or 'text' (quotes removed)
        - **Integers**: 42, -10, 0
        - **Floats**: 3.14, -2.5, 0.0
        - **Booleans**: True, False
        - **None**: None
        - **Keyword args**: key=value
    
    Parsing Process:
        1. **Empty Check**: Return empty lists if args_str is empty
        2. **Smart Split**: Split by comma, respecting quotes
        3. **Classify**: Determine if each part is positional or keyword
        4. **Parse Values**: Convert strings to appropriate Python types
        5. **Return**: (args list, kwargs dict)
    
    Args:
        args_str: Arguments string from function call (may be empty)
    
    Returns:
        Tuple[List[Any], Dict[str, Any]]: (args, kwargs)
            - args: List of positional arguments
            - kwargs: Dict of keyword arguments
    
    Examples:
        >>> parse_plugin_arguments("")
        ([], {})
        
        >>> parse_plugin_arguments("'Alice', 30")
        (['Alice', 30], {})
        
        >>> parse_plugin_arguments("name='Bob', age=25")
        ([], {'name': 'Bob', 'age': 25})
        
        >>> parse_plugin_arguments("'Alice', age=30, active=True")
        (['Alice'], {'age': 30, 'active': True})
        
        >>> parse_plugin_arguments("42, 3.14, True, None")
        ([42, 3.14, True, None], {})
        
        >>> parse_plugin_arguments('"Hello, World"')  # Comma inside quotes
        (['Hello, World'], {})
    
    Notes:
        - Uses smart_split_arguments() to respect quotes when splitting
        - Keyword args detected by presence of '=' (outside quotes)
        - Value parsing via parse_argument_value() for type conversion
        - Preserves argument order (positional before keyword)
        - Empty/whitespace-only args are filtered out
    
    See Also:
        - plugin_resolver.resolve_plugin_invocation: Uses this to parse arguments
        - smart_split_arguments: Comma splitting with quote respect
        - parse_argument_value: String to Python type conversion
    """
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}

    if not args_str or not args_str.strip():
        return args, kwargs

    # Split by comma, but respect quotes
    parts = smart_split_arguments(args_str)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check for keyword argument (key=value) — the key MUST be a bare
        # identifier. Without this guard, a JSON literal argument (e.g. a
        # Bifrost file-upload envelope) that happens to contain a base64 '='
        # padding character got misread as `<huge JSON blob>=<tail>`.
        eq_index = part.find(CHAR_EQUALS) if not is_quoted_string(part) else -1
        candidate_key = part[:eq_index].strip() if eq_index >= 0 else ""
        if eq_index >= 0 and candidate_key.isidentifier():
            key = candidate_key
            value = part[eq_index + 1:].strip()
            kwargs[key] = parse_argument_value(value)
        else:
            # Positional argument
            args.append(parse_argument_value(part))

    return args, kwargs


_BRACKETS_OPEN = "([{"
_BRACKETS_CLOSE = ")]}"


def smart_split_arguments(text: str) -> List[str]:
    """
    Split text by comma, respecting quotes AND nested brackets/braces.
    
    Splits a string on commas while preserving quoted strings and bracketed/
    braced literals as single tokens. Handles both single (') and double (")
    quotes, plus (), [], {} nesting depth, tracking state to avoid splitting
    on commas that live inside either.
    
    Quote Handling:
        - Tracks in_quotes state (True/False)
        - Tracks quote_char (which quote opened: ' or ")
        - Commas inside quotes are preserved
        - Quote characters are kept in output

    Bracket Handling:
        - Tracks a single nesting-depth counter across (, [, { / ), ], }
        - A comma is only a split point at depth 0 AND outside quotes
        - Lets a JSON object/array argument (e.g. a Bifrost file-upload
          envelope — {"__zFile": true, ...}) survive as ONE token instead
          of shredding at its own internal commas
    
    Args:
        text: Text to split (may contain commas, quotes, and brackets)
    
    Returns:
        List[str]: Split parts (empty parts are included)
    
    Examples:
        >>> smart_split_arguments("arg1, arg2, arg3")
        ['arg1', ' arg2', ' arg3']
        
        >>> smart_split_arguments("'Alice', 'Bob'")
        ["'Alice'", " 'Bob'"]
        
        >>> smart_split_arguments('"Hello, World", 42')
        ['"Hello, World"', ' 42']
        
        >>> smart_split_arguments("name='Alice', age=30")
        ["name='Alice'", " age=30"]

        >>> smart_split_arguments('\\'x\\', {"a": 1, "b": 2}')
        ["'x'", ' {"a": 1, "b": 2}']
        
        >>> smart_split_arguments("")
        []
    
    Notes:
        - Preserves quote characters in output
        - Handles both single (') and double (") quotes
        - Nested quotes of different types work correctly
        - Empty strings between commas are preserved
        - Caller should strip whitespace from parts
    
    See Also:
        - parse_plugin_arguments: Uses this for argument splitting
        - is_quoted_string: Checks if a string is quoted
    """
    parts: List[str] = []
    current: List[str] = []
    in_quotes = False
    quote_char: Optional[str] = None
    depth = 0

    for char in text:
        if char in (CHAR_QUOTE_DOUBLE, CHAR_QUOTE_SINGLE) and (not in_quotes or char == quote_char):
            in_quotes = not in_quotes
            quote_char = char if in_quotes else None
            current.append(char)
        elif in_quotes:
            current.append(char)
        elif char in _BRACKETS_OPEN:
            depth += 1
            current.append(char)
        elif char in _BRACKETS_CLOSE:
            depth = max(0, depth - 1)
            current.append(char)
        elif char == CHAR_COMMA and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(char)

    if current:
        parts.append(''.join(current))

    return parts


def is_quoted_string(text: str) -> bool:
    """
    Check if text is quoted (starts and ends with matching quotes).
    
    Determines if a string is enclosed in quotes by checking if it starts and
    ends with matching quote characters (either single or double quotes).
    
    Detection:
        - Strip whitespace from text
        - Check if starts with " and ends with "
        - OR check if starts with ' and ends with '
    
    Args:
        text: Text to check for quotes
    
    Returns:
        bool: True if text is quoted, False otherwise
    
    Examples:
        >>> is_quoted_string('"Hello"')
        True
        
        >>> is_quoted_string("'World'")
        True
        
        >>> is_quoted_string('Hello')
        False
        
        >>> is_quoted_string('"Mismatched\\'')
        False
        
        >>> is_quoted_string('  "Spaced"  ')
        True  # Whitespace is stripped first
    
    Notes:
        - Strips whitespace before checking
        - Requires matching quotes (both start and end)
        - Only checks outer quotes (doesn't validate escaping)
        - Used to detect keyword arg values that are strings
    
    See Also:
        - parse_plugin_arguments: Uses this to detect keyword args
        - parse_argument_value: Uses this for quote removal
    """
    text = text.strip()
    return ((text.startswith(CHAR_QUOTE_DOUBLE) and text.endswith(CHAR_QUOTE_DOUBLE)) or
            (text.startswith(CHAR_QUOTE_SINGLE) and text.endswith(CHAR_QUOTE_SINGLE)))


def parse_argument_value(value: str) -> Any:
    """
    Parse a single value from string into appropriate Python type.
    
    Converts a string value into the most appropriate Python type based on
    its content. Tries types in order: quoted string, boolean, None, integer,
    float, and finally unquoted string.
    
    Type Detection Order:
        1. **Quoted String**: "text" or 'text' → str (quotes removed)
        2. **Boolean**: 'True' → True, 'False' → False
        3. **None**: 'None' → None
        4. **Integer**: '42' → 42 (via int())
        5. **Float**: '3.14' → 3.14 (via float())
        6. **Unquoted String**: fallback → str as-is
    
    Args:
        value: String value to parse
    
    Returns:
        Any: Parsed value as appropriate Python type
    
    Examples:
        >>> parse_argument_value('"Hello"')
        'Hello'
        
        >>> parse_argument_value("'World'")
        'World'
        
        >>> parse_argument_value('42')
        42
        
        >>> parse_argument_value('3.14')
        3.14
        
        >>> parse_argument_value('True')
        True
        
        >>> parse_argument_value('False')
        False
        
        >>> parse_argument_value('None')
        None
        
        >>> parse_argument_value('unquoted')
        'unquoted'
    
    Notes:
        - Strips whitespace before parsing
        - Quoted strings have quotes removed (value[1:-1])
        - Uses try/except for int and float conversion
        - Unquoted strings are returned as-is (fallback)
        - Boolean detection is case-sensitive ('True', not 'true')
    
    See Also:
        - parse_plugin_arguments: Uses this for each argument value
        - is_quoted_string: Used to detect quoted strings
    """
    value = value.strip()

    # Handle quoted strings
    if is_quoted_string(value):
        return value[1:-1]  # Remove quotes

    # Handle boolean
    if value == STR_TRUE:
        return True
    if value == STR_FALSE:
        return False

    # Handle None
    if value == STR_NONE:
        return None

    # Handle a JSON object/array literal — a non-scalar zConv value (e.g. a
    # Bifrost file-upload envelope, see dialog_context.inject_placeholders)
    # arrives here as embedded JSON text, not a quoted string.
    if value[:1] in ("{", "["):
        try:
            import json
            return json.loads(value)
        except (ValueError, TypeError):
            pass

    # Try integer
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Return as string (unquoted)
    return value
