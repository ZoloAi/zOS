# zSys/logger/config.py
"""
Logger configuration utilities.

Provides helpers for extracting and validating log levels from zSpark configuration.
"""

import os
from typing import Optional, Dict, Any

from .levels import ensure_session_level


# Log Level Constants
LOG_LEVEL_SESSION = "SESSION"  # Session/environment/system information (level 15)
LOG_LEVEL_PROD = "PROD"  # Silent boot + file-only framework logs; zos.log() still prints. Used internally by raven/migrate/config commands.
LOG_LEVEL_KEY_ALIASES = ("zLog", "zScrap", "logger", "log_level", "logLevel", "zLogger")

# ============================================================================
# DEPLOYMENT-MODE VOCABULARY  (SSOT for zSpark deployment parsing)
# ============================================================================
# The keys a zSpark may use to declare its deployment mode, plus the canonical
# mode values. Owned here at Layer 0 (the lowest consumer — the logger gates
# console output on deployment). a_zConfig (L1) imports these DOWN rather than
# re-declaring them, so the "which deployment am I?" vocabulary cannot drift
# across the logger and the zServer/WebSocket network config.
DEPLOYMENT_KEYS = ("zEnv", "zState", "deployment", "Deployment", "DEPLOYMENT")
DEPLOYMENT_PRODUCTION = "production"
DEPLOYMENT_TESTING = "testing"
DEPLOYMENT_INFO = "info"  # deprecated alias for testing
DEPLOYMENT_DEFAULT = "Development"
ENV_VAR_DEPLOYMENT = "DEPLOYMENT"

# z-prefix convention: any level prefixed with "z" (e.g. zDEBUG, zINFO, zWARNING)
# enables zOS framework trace output (ASCII boxes, structured framework logs)
# on top of the standard app-level log output at that level.
# zLog: DEBUG  → app debug only
# zLog: zDEBUG → app debug + full zOS framework trace
_Z_PREFIX = "Z"


def is_zos_log_level(level: str) -> bool:
    """Return True if this is a z-prefixed level (e.g. ZDEBUG, ZINFO)."""
    return bool(level) and level.upper().startswith(_Z_PREFIX) and level.upper() != "ZSESSION"


def get_base_log_level(level: str) -> str:
    """Strip z-prefix and return the underlying Python log level string.
    
    Examples:
        "ZDEBUG"   → "DEBUG"
        "ZINFO"    → "INFO"
        "ZWARNING" → "WARNING"
        "DEBUG"    → "DEBUG"
    """
    upper = level.upper()
    if upper.startswith(_Z_PREFIX) and upper != "ZSESSION":
        return upper[1:]  # strip leading Z
    return upper

# Register SESSION level with Python logging (between INFO:20 and DEBUG:10)
ensure_session_level()


def get_log_level_from_zspark(zspark_obj: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Extract log level from zSpark object using known key aliases.

    Args:
        zspark_obj: zSpark configuration dictionary

    Returns:
        Log level string or None if not found
    """
    if not zspark_obj:
        return None

    for key in LOG_LEVEL_KEY_ALIASES:
        if key in zspark_obj:
            level = zspark_obj[key]
            return str(level).upper() if level else None

    return None


def resolve_deployment_from_zspark(
    zspark_obj: Optional[Dict[str, Any]],
    *,
    env_fallback: bool = True,
) -> str:
    """Resolve the raw deployment-mode string from a zSpark object.

    Single source for the deployment-mode lookup. Checks DEPLOYMENT_KEYS in
    order (first present key wins); when no key is set, falls back to the
    DEPLOYMENT env var (then DEPLOYMENT_DEFAULT) if env_fallback is True.

    Args:
        zspark_obj: zSpark configuration dictionary
        env_fallback: Consult the DEPLOYMENT env var when zSpark is silent

    Returns:
        The raw deployment string (caller lowercases for comparison)
    """
    if zspark_obj and isinstance(zspark_obj, dict):
        for key in DEPLOYMENT_KEYS:
            if key in zspark_obj:
                return str(zspark_obj[key])
    if env_fallback:
        return os.getenv(ENV_VAR_DEPLOYMENT, DEPLOYMENT_DEFAULT)
    return DEPLOYMENT_DEFAULT


def is_production_from_zspark(zspark_obj: Optional[Dict[str, Any]]) -> bool:
    """Check if deployment mode is Production from a zSpark object.

    Args:
        zspark_obj: zSpark configuration dictionary

    Returns:
        True if deployment is "production" (case-insensitive)
    """
    if not zspark_obj or not isinstance(zspark_obj, dict):
        return False
    for key in DEPLOYMENT_KEYS:
        if key in zspark_obj:
            return str(zspark_obj[key]).lower() == DEPLOYMENT_PRODUCTION
    return False


def is_testing_from_zspark(zspark_obj: Optional[Dict[str, Any]]) -> bool:
    """Check if deployment mode is Testing from a zSpark object.

    Includes deprecated "Info" alias for backward compatibility.

    Args:
        zspark_obj: zSpark configuration dictionary

    Returns:
        True if deployment is "testing" or "info" (case-insensitive)
    """
    if not zspark_obj or not isinstance(zspark_obj, dict):
        return False
    for key in DEPLOYMENT_KEYS:
        if key in zspark_obj:
            return str(zspark_obj[key]).lower() in (DEPLOYMENT_TESTING, DEPLOYMENT_INFO)
    return False


def should_suppress_init_prints(log_level: Optional[str]) -> bool:
    """
    Check if initialization prints should be suppressed based on log level.

    In PROD mode, all console output is suppressed (logs go to file only).

    Args:
        log_level: Log level string (e.g., "PROD", "INFO", "DEBUG")

    Returns:
        True if prints should be suppressed, False otherwise

    Note:
        This is an internal helper for backward compatibility.
        New code should use deployment mode checking instead.
    """
    if not log_level:
        return False

    return log_level.upper() == LOG_LEVEL_PROD
