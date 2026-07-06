# zSys/logger/levels.py
"""
Custom logging levels used across zSys logger utilities.
"""

import logging

SESSION_LEVEL = 15
SESSION_LEVEL_NAME = "SESSION"


def ensure_session_level() -> int:
    """Register the SESSION level with logging if missing and return its value."""
    if not hasattr(logging, SESSION_LEVEL_NAME):
        logging.addLevelName(SESSION_LEVEL, SESSION_LEVEL_NAME)
        logging.SESSION = SESSION_LEVEL
    return logging.SESSION


__all__ = ["ensure_session_level", "SESSION_LEVEL", "SESSION_LEVEL_NAME"]
