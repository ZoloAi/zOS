# zOS/core/L2_Handling/g_zParser/parser_modules/shared/error_handlers.py

"""
Reusable error handling patterns for parser modules.

Provides standardized error handling templates to eliminate duplication
across parser modules. Handles common error scenarios like file parsing,
file I/O, and validation errors with consistent logging patterns.

Public API:
    - handle_parse_error: Generic parse error handler (try/except/log)
    - handle_file_error: File I/O error handler
    - format_error_message: Consistent error message formatting

Usage:
    >>> logger = get_logger()
    >>> result = handle_parse_error(
    ...     parse_func=yaml.safe_load,
    ...     content=raw_yaml,
    ...     logger=logger,
    ...     error_msg_template="Failed to parse YAML: %s",
    ...     success_msg_template="YAML parsed successfully! Type: %s"
    ... )

Dependencies:
    - zOS: Typing imports
    - logging: Logger instance

Created: Phase 1 - Extract Shared Infrastructure
"""

from zOS import Any, Callable, Optional


def handle_parse_error(
    parse_func: Callable[[str], Any],
    content: str,
    logger: Any,
    error_msg_template: str,
    success_msg_template: Optional[str] = None,
    expected_exceptions: tuple = (Exception,),
    return_on_error: Any = None
) -> Any:
    """
    Generic error handler for parsing operations.
    
    Wraps a parsing function with try/except/log pattern, handling both
    expected parse errors and unexpected exceptions with appropriate logging.
    
    Args:
        parse_func: Parsing function to call (e.g., yaml.safe_load, json.loads)
        content: Content to parse
        logger: Logger instance for error/debug logging
        error_msg_template: Error message template (e.g., "Failed to parse: %s")
        success_msg_template: Optional success message template
        expected_exceptions: Tuple of expected exception types
        return_on_error: Value to return on error (default: None)
    
    Returns:
        Parsed result on success, return_on_error on failure
    
    Example:
        >>> result = handle_parse_error(
        ...     parse_func=yaml.safe_load,
        ...     content=yaml_content,
        ...     logger=logger,
        ...     error_msg_template="YAML parse failed: %s",
        ...     success_msg_template="YAML parsed: %s",
        ...     expected_exceptions=(yaml.YAMLError,)
        ... )
    """
    try:
        parsed = parse_func(content)

        if success_msg_template and logger:
            logger.debug(success_msg_template, type(parsed).__name__)

        return parsed

    except expected_exceptions as e:
        if logger:
            logger.error(error_msg_template, str(e))
        return return_on_error

    except Exception as e:
        if logger:
            logger.error("Unexpected error: %s", str(e))
        return return_on_error


def handle_file_error(
    file_operation: Callable[[], Any],
    logger: Any,
    file_path: str,
    error_msg_template: str = "Failed to access file %s: %s",
    return_on_error: Any = None
) -> Any:
    """
    Generic error handler for file I/O operations.
    
    Wraps a file operation with try/except pattern, handling FileNotFoundError,
    PermissionError, and other I/O errors with appropriate logging.
    
    Args:
        file_operation: File operation function to call
        logger: Logger instance for error logging
        file_path: Path to file (for error messages)
        error_msg_template: Error message template
        return_on_error: Value to return on error (default: None)
    
    Returns:
        Operation result on success, return_on_error on failure
    
    Example:
        >>> def read_file():
        ...     with open(file_path, 'r') as f:
        ...         return f.read()
        >>> content = handle_file_error(
        ...     file_operation=read_file,
        ...     logger=logger,
        ...     file_path="/path/to/file.yaml"
        ... )
    """
    try:
        return file_operation()

    except FileNotFoundError:
        if logger:
            logger.error("File not found: %s", file_path)
        return return_on_error

    except PermissionError:
        if logger:
            logger.error("Permission denied: %s", file_path)
        return return_on_error

    except Exception as e:
        if logger:
            logger.error(error_msg_template, file_path, str(e))
        return return_on_error


def format_error_message(
    error_type: str,
    message: str,
    details: Optional[str] = None,
    hint: Optional[str] = None
) -> str:
    """
    Format consistent error messages across parser modules.
    
    Creates multi-line error messages with optional details and hints,
    following a consistent format across all parser modules.
    
    Args:
        error_type: Type of error (e.g., "Invalid Syntax", "File Not Found")
        message: Primary error message
        details: Optional additional details
        hint: Optional hint for resolution
    
    Returns:
        Formatted error message string
    
    Example:
        >>> error = format_error_message(
        ...     error_type="Invalid Plugin Invocation",
        ...     message="Plugin 'MyPlugin' not found",
        ...     details="Search paths: @, @.plugins, @.utils",
        ...     hint="Check plugin name spelling and location"
        ... )
    """
    lines = [f"[{error_type}] {message}"]

    if details:
        lines.append(f"Details: {details}")

    if hint:
        lines.append(f"Hint: {hint}")

    return "\n".join(lines)
