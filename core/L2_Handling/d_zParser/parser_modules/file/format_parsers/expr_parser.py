# zOS/core/L2_Handling/g_zParser/parser_modules/file/format_parsers/expr_parser.py

"""
JSON expression parsing for file package.

Provides specialized parser for JSON-like expression strings with single-quote
normalization for zExpr_eval compatibility.

Public API:
    - parse_json_expr: JSON expression parser

Dependencies:
    - json: Python standard library

Created: Phase 1.1 - Extract Format Parsers from parser_file.py
"""

from zOS import json, Any, Dict, List, Optional, Union

# Import constants from shared
from ...shared.file_constants import (
    CHAR_SINGLE_QUOTE,
    CHAR_DOUBLE_QUOTE,
    LOG_MSG_JSON_EXPR_ERROR
)


def parse_json_expr(
    expr: str,
    logger: Any
) -> Optional[Union[Dict[str, Any], List[Any], str, int, float, bool]]:
    """
    Parse JSON-like expression strings into Python objects.
    
    Specialized parser for expression evaluation (zExpr_eval compatibility).
    Handles single-quote to double-quote normalization for Python expressions.
    
    Args:
        expr: JSON-like expression string (may use single quotes)
        logger: Logger instance for diagnostic output
    
    Returns:
        Optional[Union[Dict, List, str, int, float, bool]]: Parsed expression, or None on error
        - Same types as JSON parsing
        - None: Parse error
    
    Raises:
        No exceptions raised - all errors logged and return None
    
    Examples:
        >>> parse_json_expr('{{"key": "value"}}', logger)
        {"key": "value"}
        
        >>> parse_json_expr("{{'key': 'value'}}", logger)  # Single quotes
        {"key": "value"}
        
        >>> parse_json_expr("[1, 2, 3]", logger)
        [1, 2, 3]
        
        >>> parse_json_expr("invalid", logger)
        None
    
    Normalization:
        - Replaces ' with " (Python → JSON format)
        - Allows Python-style expressions in zOS
    
    Notes:
        - Used by zExpr_eval for expression evaluation
        - Logs debug message on parse error (not error level)
        - Returns None on any parse error (expected for non-JSON strings)
    
    Limitations:
        - Simple quote replacement (doesn't handle escaped quotes)
        - Not suitable for complex Python expressions
        - Best for simple JSON-like structures
    
    Performance:
        O(n) where n = expression length
    
    Thread Safety:
        Thread-safe (no shared state)
    
    See Also:
        - zExpr_eval: Main consumer of this function
    """
    try:
        # Handle single quotes (common in Python expressions)
        normalized = expr.replace(CHAR_SINGLE_QUOTE, CHAR_DOUBLE_QUOTE)
        return json.loads(normalized)
    except Exception as e:  # pylint: disable=broad-except
        logger.debug(LOG_MSG_JSON_EXPR_ERROR, e)
        return None
