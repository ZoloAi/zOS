"""
Single source of truth for ALL zCLI logging formats.

Inspired by mkma simple, consistent logging pattern:
https://github.com/israellevin/mkma/blob/master/initramfs_init.sh

This module provides:
- format_log_message(): Single format function used by ALL loggers
- UnifiedFormatter: Python logging.Formatter that uses our format
- format_bootstrap_verbose(): Special colored format for --verbose flag

Philosophy:
- ONE format function that defines the canonical log format
- Bootstrap, Framework, and App loggers ALL use this same format
- Consistent, machine-parsable output across all systems
- Context ([Bootstrap], [Framework], [App]) makes source clear
"""

from datetime import datetime
from typing import Optional
import logging
from zSys.formatting.colors import Colors
from .constants import TS_FORMAT_FULL, TS_FORMAT_TIME


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE COLOR TRUTH - level → color map shared by BOTH formatters
# ═══════════════════════════════════════════════════════════════════════════════
# One mapping consumed by format_log_message AND format_bootstrap_verbose so the
# level colors cannot drift. All escapes come from the Colors SSOT (no raw ANSI).
LEVEL_COLORS = {
    "DEBUG": Colors.PEACH,        # Peach for debug (subtle)
    "SESSION": Colors.PRIMARY,    # Primary green for session info
    "INFO": Colors.CYAN,          # Cyan for general info
    "WARNING": Colors.YELLOW,     # Yellow for warnings
    "ERROR": Colors.RED,          # Red for errors
    "CRITICAL": Colors.ERROR,     # Red background for critical
}


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE FORMAT TRUTH - All loggers use this
# ═══════════════════════════════════════════════════════════════════════════════

def format_log_message(
    timestamp: datetime,
    level: str,
    context: str,
    message: str,
    include_details: bool = False,
    filename: Optional[str] = None,
    lineno: Optional[int] = None,
    console_colors: bool = True
) -> str:
    """
    Single format function for ALL zCLI logging.

    This is the ONLY place where log format is defined.
    Bootstrap, Framework, and App loggers ALL call this.

    Args:
        timestamp: When the log occurred
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        context: Logger context (Bootstrap, Framework, App, etc.)
        message: The actual log message
        include_details: If True, include filename and line number
        filename: Source file name (optional)
        lineno: Line number (optional)

    Returns:
        Formatted log string

    Examples:
        >>> now = datetime.now()
        >>> format_log_message(now, "INFO", "Bootstrap", "Starting...")
        '2025-12-27 18:00:00 [Bootstrap] INFO: Starting...'

        >>> format_log_message(now, "ERROR", "Framework", "Failed", True, "zCLI.py", 123)
        '2025-12-27 18:00:00 [Framework] ERROR [zCLI.py:123]: Failed'

    Inspired by mkma format:
        <priority>$(date) [context]: message

    Our format:
        TIMESTAMP [CONTEXT] LEVEL: MESSAGE
        TIMESTAMP [CONTEXT] LEVEL [FILE:LINE]: MESSAGE  (with details)
    """
    # Base format: TIMESTAMP [CONTEXT] LEVEL: MESSAGE
    time_str = timestamp.strftime(TS_FORMAT_FULL)

    # Context colors for visual grouping
    context_colors = {
        'Bootstrap': Colors.ZINFO,       # Blue for bootstrap
        'SessionFramework': Colors.PRIMARY,  # Green for session framework
        'Framework': Colors.PEACH,       # Peach for framework (subtle)
        'App': Colors.CYAN,              # Cyan for app logs
    }

    level_color = LEVEL_COLORS.get(level, '')
    context_color = context_colors.get(context, '')

    if include_details and filename and lineno:
        # Detailed format for file logging (NO COLORS - file logs are plain text)
        return f"{time_str} [{context}] {level} [{filename}:{lineno}]: {message}"
    else:
        # Console format - apply colors only if enabled
        if console_colors:
            return f"{time_str} {context_color}[{context}]{Colors.RESET} {level_color}{level}{Colors.RESET}: {message}"
        else:
            return f"{time_str} [{context}] {level}: {message}"


# ═══════════════════════════════════════════════════════════════════════════════
# BOOTSTRAP-SPECIFIC (for --verbose colored output)
# ═══════════════════════════════════════════════════════════════════════════════

def format_bootstrap_verbose(timestamp: datetime, level: str, message: str) -> str:
    """
    Format bootstrap message for --verbose colored output.

    This is the ONLY exception to the single format rule, used ONLY for
    --verbose flag colored terminal output. File logs still use format_log_message().

    Args:
        timestamp: When the log occurred
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: The message

    Returns:
        Colored string for terminal display

    Examples:
        >>> now = datetime.now()
        >>> format_bootstrap_verbose(now, "INFO", "Starting...")
        '<info>[18:00:00] [Bootstrap] Starting...<reset>'
    """
    time_str = timestamp.strftime(TS_FORMAT_TIME)

    # Same level→color SSOT as format_log_message (Colors, no raw ANSI).
    color = LEVEL_COLORS.get(level, '')
    return f"{color}[{time_str}] [Bootstrap] {message}{Colors.RESET}"


# ═══════════════════════════════════════════════════════════════════════════════
# PYTHON LOGGING FORMATTER (uses our format function)
# ═══════════════════════════════════════════════════════════════════════════════

class UnifiedFormatter(logging.Formatter):
    """
    Python logging.Formatter that uses our single format function.

    This ensures Framework and App loggers use the SAME format as Bootstrap.
    All zCLI loggers should use this formatter to maintain consistency.

    Usage:
        # Framework logger (detailed, includes file/line)
        formatter = UnifiedFormatter("Framework", include_details=True)
        handler.setFormatter(formatter)

        # App logger (simple, no file/line)
        formatter = UnifiedFormatter("App", include_details=False)
        handler.setFormatter(formatter)
    """

    def __init__(self, context: str, include_details: bool = False, console_colors: bool = True):
        """
        Initialize formatter.

        Args:
            context: Logger context (Bootstrap, Framework, App, ConsoleLogger, etc.)
            include_details: If True, include filename and line numbers in output
            console_colors: If True, use colors for console output (default: True)
        """
        super().__init__()
        self.context = context
        self.include_details = include_details
        self.console_colors = console_colors

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record using our single format function.

        Args:
            record: Python logging.LogRecord

        Returns:
            Formatted log string
        """
        return format_log_message(
            timestamp=datetime.fromtimestamp(record.created),
            level=record.levelname,
            context=self.context,
            message=record.getMessage(),
            include_details=self.include_details,
            filename=record.filename if self.include_details else None,
            lineno=record.lineno if self.include_details else None,
            console_colors=self.console_colors,
        )
