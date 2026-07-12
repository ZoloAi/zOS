# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/detectors/shared.py
"""Shared utilities and constants for machine detection."""

from zOS import os, Path
from zSys.logger import ConsoleLogger

# Module-level logger
logger = ConsoleLogger("MachineDetector")

# Logging
LOG_PREFIX = "[MachineDetector]"

# Subprocess timeouts
SUBPROCESS_TIMEOUT_SEC = 5

# Memory conversion constants
BYTES_PER_KB = 1024
KB_PER_MB = 1024
MB_PER_GB = 1024
BYTES_PER_GB = 1024 ** 3

# Sentinel launch command meaning "hand the file to the OS default handler".
# Windows-only today: `start` is a cmd.exe builtin (unlaunchable via Popen
# without shell=True), so launchers must translate this to os.startfile().
OS_DEFAULT_HANDLER = "__os_default__"

# Default values
# When $SHELL is unset: cmd.exe on Windows (via %COMSPEC%), /bin/sh elsewhere.
DEFAULT_SHELL = (
    os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
    if os.name == "nt" else "/bin/sh"
)
DEFAULT_TIMEZONE = "system"
DEFAULT_TIME_FORMAT = "HH:MM:SS"
DEFAULT_DATE_FORMAT = "ddmmyyyy"
DEFAULT_DATETIME_FORMAT = "ddmmyyyy HH:MM:SS"

# Logging Helpers

def _log_info(message: str, log_level=None, is_production: bool = False) -> None:  # pylint: disable=unused-argument
    """Log info message (suppressed in Production deployment).

    log_level is accepted (and ignored) because most detector call sites pass
    (message, log_level, is_production) — the old 2-arg signature made every
    such call a TypeError that only surfaced on code paths outside try/except
    (e.g. headless Linux boot).
    """
    if not is_production:
        logger.debug("%s %s", LOG_PREFIX, message)

def _log_warning(message: str, log_level=None, is_production: bool = False) -> None:  # pylint: disable=unused-argument
    """Log warning message (suppressed in Production deployment). See _log_info."""
    if not is_production:
        logger.warning("%s %s", LOG_PREFIX, message)

def _log_error(message: str) -> None:
    """Log error message (always shown, even in Production)."""
    logger.error("%s %s", LOG_PREFIX, message)

def _log_config(message: str, verbose: bool = False) -> None:
    """Log config message (suppressed unless verbose mode).
    
    Args:
        message: Message to log
        verbose: If True, show the message (default: False)
    """
    if verbose:
        logger.debug("%s %s", LOG_PREFIX, message)

def linux_gui_available() -> bool:
    """True when a graphical session is reachable (X11 or Wayland)."""
    return bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))


def _safe_getcwd() -> str:
    """Get current directory, falling back to home if deleted."""
    try:
        return os.getcwd()
    except (FileNotFoundError, OSError):
        # Directory was deleted (common in tests with temp directories)
        # Fall back to home directory
        return str(Path.home())
