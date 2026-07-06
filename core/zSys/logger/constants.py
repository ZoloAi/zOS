# zSys/logger/constants.py
"""
Single-sourced literals for the zSys logger.

Timestamp format strings shared by ``formats.py`` (console/file lines) and
``bootstrap.py`` (pre-boot verbose + emergency dump). Kept here so the format
literals cannot drift across the logger's own modules.
"""

# Full datetime — console + file log lines (format_log_message).
TS_FORMAT_FULL = "%Y-%m-%d %H:%M:%S"

# Time only — bootstrap --verbose terminal output.
TS_FORMAT_TIME = "%H:%M:%S"

# Time + microseconds — bootstrap injection/emergency dump.
# Callers slice ``[:-3]`` to render milliseconds.
TS_FORMAT_TIME_MS = "%H:%M:%S.%f"

__all__ = ["TS_FORMAT_FULL", "TS_FORMAT_TIME", "TS_FORMAT_TIME_MS"]
