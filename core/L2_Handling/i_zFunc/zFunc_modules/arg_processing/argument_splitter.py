# zOS/core/L2_Handling/i_zFunc/zFunc_modules/arg_processing/argument_splitter.py

"""
Argument string splitter (delegates to zParser).

This module provides functionality to split comma-separated argument strings
while respecting nested brackets (parentheses, square brackets, curly braces)
and quotes (single and double).

Architecture Position
--------------------
**Tier 1: Foundation** - Wrapper to zParser's universal primitive

**IMPORTANT**: This module now delegates to zParser's universal argument splitter
which handles both brackets AND quotes. This eliminates duplication and provides
a single source of truth for argument splitting.

Key Functionality
-----------------
1. **Delegation**: Forwards to zParser's shared.argument_utils.split_arguments()
2. **Backward Compatibility**: Maintains stable API for zFunc consumers
3. **Validation**: Inherits bracket/quote validation from zParser

Integration Points
------------------
**Used By**:
- argument_processor.process_arguments(): Uses this for initial string splitting

**Dependencies**:
- zParser.shared.argument_utils: Universal splitting primitive (SSOT)

Usage Examples
--------------
Example 1: Simple arguments
    >>> result = split_arguments("arg1, arg2, arg3")
    ["arg1", " arg2", " arg3"]

Example 2: Nested structures
    >>> result = split_arguments("func(a, b), [1, 2], arg3")
    ["func(a, b)", " [1, 2]", " arg3"]

Example 3: Quotes and brackets
    >>> result = split_arguments('func("a, b"), \\'text\\', [1, 2]')
    ['func("a, b")', " 'text'", ' [1, 2]']

Version History
---------------
- v1.6.1: Moved to arg_processing/ (renamed from parsers/)
- v1.6.0: Refactored to delegate to zParser's universal splitter (SSOT)
- v1.5.x: Original implementation with bracket-only support
"""

# Delegate to zParser's universal argument splitter (SSOT)
from zOS.L2_Handling.d_zParser.parser_modules.shared import split_arguments


# Re-export constants for backward compatibility
from zOS.L2_Handling.d_zParser.parser_modules.shared.argument_utils import (
    BRACKETS_OPEN,
    BRACKETS_CLOSE,
    DELIMITER_COMMA,
    ERROR_MSG_BRACKET_MISMATCH,
    ERROR_MSG_INVALID_ARG_STR_TYPE,
)


__all__ = [
    "split_arguments",
    # Constants for backward compatibility
    "BRACKETS_OPEN",
    "BRACKETS_CLOSE",
    "DELIMITER_COMMA",
    "ERROR_MSG_BRACKET_MISMATCH",
    "ERROR_MSG_INVALID_ARG_STR_TYPE",
]
