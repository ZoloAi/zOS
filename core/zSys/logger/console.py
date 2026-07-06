# zSys/logger/console.py
"""
Minimal logger utilities for standalone contexts (like WSGI workers).

Uses unified logging format from formats.py for consistency.
"""

from datetime import datetime
from .formats import format_log_message


class ConsoleLogger:
    """
    Minimal console logger for contexts where full zCLI logger isn't available.

    Used primarily in WSGI workers where the full zCLI instance isn't accessible.
    Uses the same unified format as Bootstrap, Framework, and App loggers for
    consistency across all logging outputs.

    Features:
        - Uses unified format from formats.py
        - Console output only (no file logging)
        - String formatting support (msg % args)
        - Lightweight (no Python logging module required)

    Usage:
        from zSys.logger import ConsoleLogger

        logger = ConsoleLogger(context="WSGI")
        logger.info("Server started on port %d", 8000)
        logger.error("Connection failed: %s", error)
    """

    def __init__(self, context: str = "Console"):
        """
        Initialize console logger.

        Args:
            context: Logger context name (e.g., "WSGI", "Worker", "Console")
        """
        self.context = context

    def _log(self, level: str, msg: str, *args) -> None:
        """Format and print a log message to stdout."""
        if args:
            msg = msg % args
        formatted = format_log_message(
            timestamp=datetime.now(),
            level=level,
            context=self.context,
            message=msg,
            include_details=False
        )
        print(formatted)

    def debug(self, msg: str, *args):
        """Log debug message using unified format."""
        self._log("DEBUG", msg, *args)

    def info(self, msg: str, *args):
        """Log info message using unified format."""
        self._log("INFO", msg, *args)

    def warning(self, msg: str, *args):
        """Log warning message using unified format."""
        self._log("WARNING", msg, *args)

    def error(self, msg: str, *args):
        """Log error message using unified format."""
        self._log("ERROR", msg, *args)

    def critical(self, msg: str, *args):
        """Log critical message using unified format."""
        self._log("CRITICAL", msg, *args)
