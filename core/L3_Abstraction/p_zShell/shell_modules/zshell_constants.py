# zOS/core/L3_Abstraction/p_zShell/shell_modules/zshell_constants.py

"""
Shared Constants for zShell Subsystem

Centralizes display styles, colors, indentation, and other constants used across
multiple zShell modules to eliminate DRY violations.
"""

# ============================================================
# DISPLAY STYLES
# ============================================================
STYLE_SINGLE = "single"
STYLE_FULL = "full"
STYLE_NONE = "none"

# ============================================================
# INDENTATION LEVELS
# ============================================================
INDENT_NORMAL = 0
INDENT_NESTED = 1

# ============================================================
# DISPLAY COLORS
# ============================================================
COLOR_SHELL = "SHELL"
COLOR_INFO = "INFO"
COLOR_ERROR = "ERROR"
COLOR_SUCCESS = "SUCCESS"
COLOR_DATA = "DATA"
COLOR_EXTERNAL = "EXTERNAL"
COLOR_WARNING = "WARNING"

# ============================================================
# PROMPTS
# ============================================================
PROMPT_NORMAL = "zOS> "
PROMPT_WIZARD = "> "

# ============================================================
# MESSAGES
# ============================================================
MSG_READY = "zShell Ready"
MSG_GOODBYE = "Goodbye!"
MSG_ERROR_PREFIX = "Error: {}"
