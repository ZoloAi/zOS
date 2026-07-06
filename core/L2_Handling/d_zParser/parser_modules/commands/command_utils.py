# zOS/core/L2_Handling/g_zParser/parser_modules/commands/command_utils.py

"""
Command parsing utilities for commands package.

Provides shared utilities for command string splitting and argument extraction.

Public API:
    - split_command: Quote-aware command string splitting
    - extract_args_and_options: Extract positional args and named options

Created: Phase 4.1 - Extract Shared Utilities from parser_commands.py
"""

from zOS import Any, Dict, List, Tuple

# Import constants from shared
from ..shared.parser_constants import (
    CHAR_SPACE,
    CHAR_QUOTE_DOUBLE,
    CHAR_QUOTE_SINGLE,
    CHAR_DASH_DOUBLE
)


def split_command(command: str) -> List[str]:
    """
    Split command into parts, handling quotes and special characters.
    
    Splits command string on spaces while preserving quoted strings as single tokens.
    Handles both single and double quotes properly, allowing spaces within quotes.
    
    Quote Handling Logic:
        1. Iterate through each character
        2. Track quote state (in_quotes, quote_char)
        3. Build current token character by character
        4. When space found outside quotes: finalize current token
        5. When quote found: toggle quote state and track quote character
        6. Strip whitespace from tokens before adding to results
    
    Args:
        command: Command string to split (may contain quotes)
    
    Returns:
        List[str]: List of command parts with quotes preserved in content
    
    Examples:
        >>> split_command("data read users")
        ['data', 'read', 'users']
        
        >>> split_command('echo "Hello World"')
        ['echo', '"Hello World"']
        
        >>> split_command("data insert --name 'John Doe' --age 30")
        ['data', 'insert', '--name', "'John Doe'", '--age', '30']
        
        >>> split_command("load '@.ui.file with spaces.yaml'")
        ['load', "'@.ui.file with spaces.yaml'"]
    
    Notes:
        - Handles both single (') and double (") quotes
        - Preserves spaces within quoted strings
        - Quotes are kept in the token (not stripped)
        - Empty tokens are filtered out
        - Whitespace trimmed from non-quoted tokens
    
    See Also:
        - parse_command: Uses this helper for initial command splitting
    """
    parts = []
    current = ""
    in_quotes = False
    quote_char = None

    for char in command:
        # Check if this is a quote character and we're not already in quotes
        if char in [CHAR_QUOTE_DOUBLE, CHAR_QUOTE_SINGLE] and not in_quotes:
            in_quotes = True
            quote_char = char
            current += char
        # Check if this is the closing quote
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = None
            current += char
        # Check if this is a space outside of quotes (token separator)
        elif char == CHAR_SPACE and not in_quotes:
            if current.strip():
                parts.append(current.strip())
            current = ""
        # Regular character: add to current token
        else:
            current += char

    # Add final token if exists
    if current.strip():
        parts.append(current.strip())

    return parts


def extract_args_and_options(parts: List[str], start_idx: int) -> Tuple[List[str], Dict[str, Any]]:
    """
    DRY helper: Extract arguments and options from command parts.
    
    Extracts positional arguments and named options (--key value or --flag) from
    command parts starting at specified index. Used by multiple parsers to avoid
    code duplication.
    
    Args:
        parts: Full command parts list
        start_idx: Index to start extraction (typically 1 or 2)
    
    Returns:
        Tuple[List[str], Dict[str, Any]]: (args, options)
            - args: Positional arguments
            - options: Named options (--key value) or flags (--flag)
    
    Examples:
        >>> extract_args_and_options(['cmd', 'action', 'arg1', '--key', 'val', '--flag'], 2)
        (['arg1'], {{'key': 'val', 'flag': True}})
    """
    args = []
    options = {}

    i = start_idx
    while i < len(parts):
        part = parts[i]

        if part.startswith(CHAR_DASH_DOUBLE):
            # Option
            opt_name = part[2:]
            if i + 1 < len(parts) and not parts[i + 1].startswith(CHAR_DASH_DOUBLE):
                options[opt_name] = parts[i + 1]
                i += 2
            else:
                options[opt_name] = True
                i += 1
        else:
            # Argument
            args.append(part)
            i += 1

    return args, options
