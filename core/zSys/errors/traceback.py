# zSys/errors/traceback.py
"""Centralized traceback utilities — the error SHAPING CORE.

This is the engine room behind the `!` modifier's error policy: it turns any
exception into a clean, structured signal (type, message, file:line, context) and
logs it consistently. `!` decides *what to do* on a failure (retry / quit);
zTraceback decides *how the error reads*.

The old interactive global `sys.excepthook` UI — auto-catch every uncaught
exception and launch a Walker "View Details / Full Traceback" menu — was retired.
It was a relic of the imperative scaffolding era: gated off by default, undocumented,
and reachable only through itself. `!` is now the single declarative front door to
failure handling, so the hook, its interactive handler, and the render functions
are gone. Only the shaping core (and ExceptionContext) remain.
"""

import sys
import traceback
import logging
from typing import Optional

from .errors_constants import (
    DEFAULT_LOG_MESSAGE,
    OPERATION_PREFIX,
)

__all__ = [
    "zTraceback",
    "ExceptionContext",
]


class zTraceback:
    """Error shaping: structured formatting + consistent logging for exceptions."""

    def __init__(self, logger=None, zos=None, zcli=None):
        """Initialize with an optional logger and zOS instance.

        Args:
            logger: Logger instance for error logging
            zos: zOS framework instance (preferred)
            zcli: Deprecated alias for zos (backward compatibility)
        """
        self.logger = logger
        self.zos = zos or zcli
        self.zcli = self.zos  # Backward-compat alias

    def _emergency_print(self, exc: Exception, prefix: str):
        """Last-resort stderr dump when no logger is available."""
        print(f"{prefix}: {exc}", file=sys.stderr)
        traceback.print_exc()

    def format_exception(self, exc: Exception, include_locals: bool = False) -> str:
        """Format an exception (include_locals adds the full frame stack)."""
        if include_locals:
            return ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return ''.join(traceback.format_exception_only(type(exc), exc))

    def get_traceback_info(self, exc: Exception) -> dict:
        """Extract structured info (file, line, function, type, message)."""
        tb = exc.__traceback__
        if not tb:
            return {
                'exception_type': type(exc).__name__,
                'exception_message': str(exc),
            }

        # Walk to the last frame (where the error actually occurred).
        while tb.tb_next:
            tb = tb.tb_next

        frame = tb.tb_frame
        return {
            'file': frame.f_code.co_filename,
            'line': tb.tb_lineno,
            'function': frame.f_code.co_name,
            'exception_type': type(exc).__name__,
            'exception_message': str(exc),
        }

    def log_exception(self,
                      exc: Exception,
                      message: str = DEFAULT_LOG_MESSAGE,
                      context: Optional[dict] = None,
                      include_locals: bool = False):
        """Log an exception with consistent formatting and optional structured context."""
        if not self.logger:
            self._emergency_print(exc, message)
            return

        self.logger.error(message + ": %s", exc, exc_info=True)

        if context:
            self.logger.debug("Error context: %s", context)

        if include_locals and self.logger.isEnabledFor(logging.DEBUG):
            info = self.get_traceback_info(exc)
            self.logger.debug("Error location: %s:%s in %s()",
                              info.get('file', 'unknown'),
                              info.get('line', '?'),
                              info.get('function', 'unknown'))


class ExceptionContext:
    """Context manager for consistent exception handling with logging."""

    def __init__(
        self,
        ztraceback: "zTraceback",
        operation: str,
        context: Optional[dict] = None,
        reraise: bool = False,
        default_return=None,
    ):
        """Initialize (operation desc, context dict, reraise flag, default_return)."""
        self.ztraceback = ztraceback
        self.operation = operation
        self.context = context or {}
        self.reraise = reraise
        self.default_return = default_return
        self.exception = None
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.exception = exc_val
            self.ztraceback.log_exception(
                exc_val,
                message=OPERATION_PREFIX % self.operation,
                context=self.context,
            )
            if self.reraise:
                return False
            self.result = self.default_return
            return True  # suppress
        return False
