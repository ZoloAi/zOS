# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/colors.py
"""ANSI color constants for zRaven output.

Re-exports the canonical zOS Colors palette so zRaven never hard-codes
escape sequences. BOLD and DIM are zRaven-local (not in the shared palette).

When stdout is not a tty (piped, redirected) all codes are stripped so that
tools like `grep`, `tail`, `tee`, and CI log collectors receive plain text.
"""

import sys as _sys

_IS_TTY = hasattr(_sys.stdout, "isatty") and _sys.stdout.isatty()


def _c(code: str) -> str:
    return code if _IS_TTY else ""


try:
    from zOS import Colors as _C
    GREEN  = _C.GREEN  if _IS_TTY else ""
    RED    = _C.RED    if _IS_TTY else ""
    YELLOW = _C.YELLOW if _IS_TTY else ""
    CYAN   = _C.CYAN   if _IS_TTY else ""
    RESET  = _C.RESET  if _IS_TTY else ""
except Exception:  # pylint: disable=broad-except
    GREEN  = _c("\033[92m")
    RED    = _c("\033[91m")
    YELLOW = _c("\033[93m")
    CYAN   = _c("\033[96m")
    RESET  = _c("\033[0m")

BOLD = _c("\033[1m")
DIM  = _c("\033[2m")
