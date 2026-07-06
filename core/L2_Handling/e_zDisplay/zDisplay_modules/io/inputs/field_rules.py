# zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/io/inputs/field_rules.py

"""
Field validation rules — the cross-surface SSOT.

ONE definition of every input rule, consumed by:
  - the zCLI input hub (input_string._terminal_single_line) — runs them directly
  - the Bifrost form (raw constraint attrs forwarded; the browser enforces)

Two layers, one registry:
  - TYPE_PRESETS — a `type` IS a constraint bundle (``email`` == ``pattern``
    EMAIL_RE, ``number`` == numeric). Types are not special-cased validators;
    they resolve to the same primitives a raw constraint uses.
  - raw CONSTRAINTS — ``min`` / ``max`` / ``step`` / ``minlength`` /
    ``maxlength`` / ``pattern`` apply WITH or WITHOUT a type. This is the
    developer escape hatch: the raw primitive most forms never need.

``resolve()`` merges the preset with the author's raw constraints (author
wins); ``validate_value()`` runs the merged set and returns the first human
message. No regex lives anywhere else — both surfaces trace back here.
"""

import re as _re

# ── Canonical regexes (single source — presets reference these) ──────────────
EMAIL_RE = r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$'
NUMBER_RE = r'^-?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$'
# NOTE: parens are escaped inside the char classes (\( \)) — required so the
# browser's `pattern` attr compiles under the regex `v` flag (which forbids
# unescaped ( ) in a class). Harmless in Python re; keeps both surfaces in sync.
TEL_RE = r'^[+\d\(*#][0-9\s\-\(\)+*#xX.]*$'
URL_RE = r'^[a-zA-Z][a-zA-Z0-9+\-.]*:(?://[^\s]+|(?!//)[^\s]+)$'
HEX_RE = r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$'

# type → preset rule. Either a ``pattern`` (with message) or ``numeric`` (range
# semantics). These are the OLD per-type validators, now expressed as the same
# constraint primitives a raw ``pattern:`` would use (DRY).
TYPE_PRESETS: dict = {
    'email': {'pattern': EMAIL_RE,
              'message': "Invalid email address — expected format: user@domain.com"},
    'url': {'pattern': URL_RE,
            'message': "Invalid URL — include the scheme (e.g. https://example.com)"},
    'tel': {'pattern': TEL_RE,
            'message': "Invalid phone number — use digits and separators only (e.g. +1 555 000 0000)"},
    'color': {'pattern': HEX_RE,
              'message': "Invalid color — use a hex value (e.g. #5CA9FF or #FFF)"},
    'number': {'numeric': True,
               'message': "Invalid number — enter a numeric value (e.g. 42, 3.14, -7)"},
}

# Raw constraint keys an author may declare on a field (type optional). These
# are the keys forwarded to read_string (zCLI) and emitted as native HTML attrs
# (Bifrost) — keep this list in sync with both passthrough lists.
CONSTRAINT_KEYS = ('pattern', 'min', 'max', 'step', 'minlength', 'maxlength')

# The subset of resolved rules that map to real HTML input attributes (used to
# emit the SAME rule to the browser that zCLI runs). ``numeric``/``*_msg`` are
# zCLI-internal and never go on the wire.
_HTML_ATTR_KEYS = ('pattern', 'min', 'max', 'step', 'minlength', 'maxlength')

_NUMBER = _re.compile(NUMBER_RE)


def detect_type(field_name: str):
    """Name-based type auto-detection — the SSOT for the bare-field convention.

    A bare ``email`` / ``phone`` / ``password`` field resolves to that type on
    every surface. Mirrors the zCLI parser and the Bifrost FormRenderer so the
    three never drift. Returns the detected type or ``None``.
    """
    lower = (field_name or '').lower()
    if 'password' in lower:
        return 'password'
    if 'email' in lower:
        return 'email'
    if lower in ('tel', 'phone') or 'phone' in lower:
        return 'tel'
    return None


def _to_number(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _fmt(n) -> str:
    """Render a number without a trailing .0 for whole values (clean messages)."""
    f = float(n)
    return str(int(f)) if f.is_integer() else str(n)


def _anchor(pattern: str) -> str:
    """Anchor a raw author pattern to a full-string match, like HTML does."""
    p = pattern
    if not p.startswith('^'):
        p = '^' + p
    if not p.endswith('$'):
        p = p + '$'
    return p


def resolve(field) -> dict:
    """Merge a field's type preset with its raw constraints → normalized dict.

    ``field`` is the read_string kwargs / field dict (carries ``type`` plus any
    constraint keys). Author-declared constraints win over preset-derived ones.

    Returns a dict holding any of: ``pattern`` / ``pattern_msg`` / ``numeric`` /
    ``numeric_msg`` / ``min`` / ``max`` / ``step`` / ``minlength`` /
    ``maxlength``. Empty dict when there is nothing to enforce.
    """
    if not isinstance(field, dict):
        return {}

    out: dict = {}

    preset = TYPE_PRESETS.get(field.get('type'))
    if preset:
        if 'pattern' in preset:
            out['pattern'] = preset['pattern']
            out['pattern_msg'] = preset['message']
        if preset.get('numeric'):
            out['numeric'] = True
            out['numeric_msg'] = preset['message']

    # Raw author pattern wins over a preset pattern.
    if field.get('pattern') is not None:
        out['pattern'] = _anchor(str(field['pattern']))
        out['pattern_msg'] = f"Must match the required format: {field['pattern']}"

    for k in ('minlength', 'maxlength'):
        iv = _to_int(field.get(k))
        if iv is not None:
            out[k] = iv

    for k in ('min', 'max', 'step'):
        nv = _to_number(field.get(k))
        if nv is not None:
            out[k] = nv
            out['numeric'] = True  # a range/step implies the value is numeric

    return out


def html_attrs(field) -> dict:
    """Resolve a field's rules to the native HTML attrs that enforce them.

    Used to emit the SAME rule to the Bifrost form that the zCLI input hub runs
    — closing the gap where a type preset (e.g. ``email``) validated via the
    browser builtin in the GUI but via our regex at the prompt. Auto-detects the
    type for bare fields so ``email`` carries our ``pattern`` on both surfaces.

    Returns only real HTML attribute keys (pattern/min/max/step/min/maxlength).
    """
    if isinstance(field, dict):
        f = dict(field)
        identity = f.get('zConv') or f.get('name') or f.get('field') or ''
    else:
        f = {}
        identity = str(field)
    if not f.get('type'):
        detected = detect_type(identity)
        if detected:
            f['type'] = detected
    resolved = resolve(f)
    return {k: resolved[k] for k in _HTML_ATTR_KEYS if k in resolved}


def validate_value(value, constraints: dict):
    """Run all resolved constraints against a (string) value.

    Returns ``(ok: bool, message: str | None)`` — first failure wins. An empty
    value is the caller's concern (the required gate / default fallback), so we
    only enforce on non-empty input.
    """
    if value is None or value == '':
        return True, None
    if not constraints:
        return True, None

    s = str(value)

    # Length (cheap, type-agnostic) first.
    if 'minlength' in constraints and len(s) < constraints['minlength']:
        return False, f"Must be at least {constraints['minlength']} characters"
    if 'maxlength' in constraints and len(s) > constraints['maxlength']:
        return False, f"Must be at most {constraints['maxlength']} characters"

    # Pattern (type preset OR raw author pattern — already anchored in resolve).
    pat = constraints.get('pattern')
    if pat and not _re.match(pat, s):
        return False, constraints.get('pattern_msg') or f"Must match {pat}"

    # Numeric value + range/step.
    if constraints.get('numeric'):
        if not _NUMBER.match(s):
            return False, constraints.get('numeric_msg') or "Enter a numeric value"
        n = float(s)
        if 'min' in constraints and n < constraints['min']:
            return False, f"Must be ≥ {_fmt(constraints['min'])}"
        if 'max' in constraints and n > constraints['max']:
            return False, f"Must be ≤ {_fmt(constraints['max'])}"
        step = constraints.get('step')
        if step and step > 0:
            base = constraints.get('min', 0) or 0
            q = (n - base) / step
            if abs(q - round(q)) > 1e-9:
                return False, f"Must be in steps of {_fmt(step)}"

    return True, None
