# zSys/errors/errors_constants.py
"""
Constants for the errors subsystem.

Single-sources the interactive-traceback UI literals (header labels, colors,
styles, prompts) and the fallback/emergency messages that were previously
inline across `traceback.py`. Per-exception hint text stays with its exception
class (cohesive with the error it describes); only the shared/reused literals
live here.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Interactive traceback UI — header labels
# ─────────────────────────────────────────────────────────────────────────────
HEADER_ERROR_DETAILS: str = "Error Details"
HEADER_CONTEXT: str = "Context"
HEADER_HINT: str = "Hint"
HEADER_FULL_TRACEBACK: str = "Full Traceback"

# ─────────────────────────────────────────────────────────────────────────────
# Header colors + styles (zDisplay header tokens)
# ─────────────────────────────────────────────────────────────────────────────
COLOR_ERROR: str = "RED"
COLOR_CONTEXT: str = "CYAN"
COLOR_HINT: str = "GREEN"
COLOR_RESET: str = "RESET"
STYLE_FULL: str = "full"
STYLE_SINGLE: str = "single"

# ─────────────────────────────────────────────────────────────────────────────
# UI prompts / labels
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_RETURN_TO_MENU: str = "Press Enter to return to menu..."
MSG_NO_EXCEPTION: str = "No exception to display"
LABEL_LOCATION: str = "\nLocation:"

# ─────────────────────────────────────────────────────────────────────────────
# Fallback / emergency messages (stderr + logger)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_LOG_MESSAGE: str = "Exception occurred"
PREFIX_ERROR: str = "Error"
PREFIX_ORIGINAL_ERROR: str = "Original Error"
MSG_INTERACTIVE_HANDLER_FAILED: str = "Interactive handler failed: %s"
MSG_INTERACTIVE_UNAVAILABLE: str = "Interactive traceback unavailable (no zos instance)"
MSG_UI_LAUNCH_FAILED: str = "Failed to launch interactive traceback UI: %s"
OPERATION_PREFIX: str = "Error during %s"

# ─────────────────────────────────────────────────────────────────────────────
# Redaction (E5 — keep sensitive raw values out of context/logs)
# ─────────────────────────────────────────────────────────────────────────────
REDACTED: str = "<redacted>"

__all__ = [
    "HEADER_ERROR_DETAILS",
    "HEADER_CONTEXT",
    "HEADER_HINT",
    "HEADER_FULL_TRACEBACK",
    "COLOR_ERROR",
    "COLOR_CONTEXT",
    "COLOR_HINT",
    "COLOR_RESET",
    "STYLE_FULL",
    "STYLE_SINGLE",
    "PROMPT_RETURN_TO_MENU",
    "MSG_NO_EXCEPTION",
    "LABEL_LOCATION",
    "DEFAULT_LOG_MESSAGE",
    "PREFIX_ERROR",
    "PREFIX_ORIGINAL_ERROR",
    "MSG_INTERACTIVE_HANDLER_FAILED",
    "MSG_INTERACTIVE_UNAVAILABLE",
    "MSG_UI_LAUNCH_FAILED",
    "OPERATION_PREFIX",
    "REDACTED",
]
