# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/dye_ops.py
"""zLoom zDye — the filter half of a thread.

A **thread** (``%token``) resolves to a raw value; a **dye** finishes that value
for display. Dyes chain left→right through the pipe: ``%data.name | trim | title``
reads "take the name, then trim it, then title-case it". Each dye is a plain
function ``fn(value, arg) -> value``; the piped value is always the first
ingredient (``x | f(a)`` == ``f(x, a)``), exactly like a shell pipe.

Scope (SSOT): dyes run ONLY in display interpolation (``resolve_token_string``),
BETWEEN the raw lookup and the scalar-display rule. That ordering is deliberate —
``default`` sees the raw ``None`` of a miss and can rescue it before the
literal-on-miss rule fires, so a dye is the sanctioned way out of the token's
strict miss contract. Decisions (gates / WHERE / zList source) never run dyes.

Unknown dye → fail open: the value passes through untouched (a warning is the
caller's to log), same spirit as an unknown zPattern.
"""

import datetime as _dt

from zOS import re, Any

# One dye step in a chain: ``| name`` or ``| name(arg)``. Arg is bare text
# (string-first — no quotes needed) with no ``|`` or ``)`` inside (MVP).
_STEP = re.compile(r'\|\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(([^)]*)\))?')

# Friendly date tokens → strftime, longest-first so YYYY beats YY.
_DATE_TOKENS = [
    ("YYYY", "%Y"), ("YY", "%y"),
    ("MMMM", "%B"), ("MMM", "%b"), ("MM", "%m"),
    ("DDDD", "%A"), ("DDD", "%a"), ("DD", "%d"),
    ("HH", "%H"), ("mm", "%M"), ("SS", "%S"),
]


def _s(v: Any) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _dye_default(v: Any, arg: Any) -> Any:
    """Fallback when the thread is missing OR blank. Rescues a miss (None) and an
    empty string — but NOT a real 0/False (those are values, not gaps)."""
    return arg if _is_blank(v) else v


def _dye_truncate(v: Any, arg: Any) -> Any:
    if not isinstance(v, str):
        return v
    try:
        n = int(arg) if arg not in (None, "") else 80
    except (TypeError, ValueError):
        n = 80
    return v if len(v) <= n else v[:n].rstrip() + "…"


def _dye_round(v: Any, arg: Any) -> Any:
    try:
        digits = int(arg) if arg not in (None, "") else 0
        num = round(float(v), digits)
        return int(num) if digits <= 0 else num
    except (TypeError, ValueError):
        return v


def _dye_date(v: Any, arg: Any) -> Any:
    """Format an ISO date/datetime with friendly tokens (YYYY-MM-DD, etc).
    Non-dates and unparseable values pass through untouched (fail safe)."""
    if isinstance(v, (_dt.date, _dt.datetime)):
        dtv = v
    elif isinstance(v, str) and v.strip():
        try:
            dtv = _dt.datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
        except ValueError:
            return v
    else:
        return v
    fmt = arg if arg not in (None, "") else "YYYY-MM-DD"
    for token, code in _DATE_TOKENS:
        fmt = fmt.replace(token, code)
    return dtv.strftime(fmt)


# The registry — name → fn(value, arg). MVP set: fallback, case/text, number, date.
DYES = {
    "default":  _dye_default,
    "upper":    lambda v, a: v.upper() if isinstance(v, str) else v,
    "lower":    lambda v, a: v.lower() if isinstance(v, str) else v,
    "title":    lambda v, a: v.title() if isinstance(v, str) else v,
    "trim":     lambda v, a: v.strip() if isinstance(v, str) else v,
    "truncate": _dye_truncate,
    "round":    _dye_round,
    "date":     _dye_date,
}


def apply_dyes(value: Any, chain: Any, warn: Any = None) -> Any:
    """Run a raw ``value`` through a ``| dye | dye(arg)`` chain, left→right.

    ``chain`` is the pipe text captured after a token (may be empty). Returns the
    finished value (still raw — the caller applies the scalar-display rule).
    Unknown dye → value passes through; ``warn(name)`` is called if provided.
    """
    if not chain or "|" not in chain:
        return value
    for step in _STEP.finditer(chain):
        name = step.group(1)
        arg = step.group(2)
        if arg is not None:
            arg = arg.strip()
        fn = DYES.get(name)
        if fn is None:
            if warn:
                warn(name)
            continue  # fail open
        try:
            value = fn(value, arg)
        except Exception:  # pylint: disable=broad-except
            pass  # a broken dye never crashes a render
    return value
