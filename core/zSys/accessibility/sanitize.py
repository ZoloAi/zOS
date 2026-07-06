"""
Accessibility HTML-emission sanitizers (trust boundary).

Icon names and CSS class hints can originate from .zolo content authored
outside the open-core trust boundary. When rendered for zBifrost (web),
they are interpolated into raw HTML markup. Without validation, a crafted
name/class can break out of the attribute and inject script (stored XSS).

These helpers are the single source of truth for that validation. They are
allowlist-based and fail closed: anything outside the permitted character
set is dropped, never escaped-and-passed-through.

The zCLI (terminal) path is inert text and does not need these — they guard
only the markup-emitting (web) path.
"""

import re

# Bootstrap-Icons names are lowercase words joined by hyphens (e.g. "arrow-up-circle").
_ICON_NAME_RE = re.compile(r"^[a-z0-9-]+$")

# CSS class tokens: letters, digits, hyphen, underscore. No spaces (handled by split).
_CLASS_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def safe_icon_name(icon_name: str) -> str:
    """
    Validate a Bootstrap-Icons name for safe use in markup.

    Strips an optional 'bi-' prefix, then returns the name only if it
    matches [a-z0-9-]+. Returns "" (fail-closed) for anything else,
    including empty/None input.
    """
    if not icon_name:
        return ""
    clean = icon_name.removeprefix("bi-")
    return clean if _ICON_NAME_RE.match(clean) else ""


def safe_class_attr(value: str) -> str:
    """
    Keep only well-formed CSS class tokens from a space-separated string.

    Drops any token containing characters outside [A-Za-z0-9_-] (quotes,
    angle brackets, whitespace tricks). Returns a space-joined safe string,
    or "" if nothing valid remains.
    """
    if not value:
        return ""
    return " ".join(tok for tok in value.split() if _CLASS_TOKEN_RE.match(tok))
