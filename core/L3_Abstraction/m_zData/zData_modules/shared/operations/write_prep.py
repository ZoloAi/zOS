# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/write_prep.py
"""
Pre-write payload preparation for zData INSERT / UPSERT.

Extracted from ``operations/helpers.py`` (grab-bag decomposition). These two
functions run over a write payload *before* validation, so the validator and the
DB writer both see the same cleaned, defaulted values:

    apply_transforms(table, data, table_schema, ops) -> Dict
        Apply field-level ``transform:`` directives (lowercase, trim, slug, …).
    apply_defaults(table, data, table_schema, ops) -> Dict
        Fill omitted / empty fields with their declared ``default:`` (``now`` →
        current timestamp shaped to the field's temporal type).

Both return a *new* dict and never mutate the input. ``helpers.py`` re-exports
both names so existing ``from .helpers import apply_transforms`` call sites keep
working unchanged.
"""

from zOS import Any, Dict
from ..validators.constants import SCHEMA_KEY_DEFAULT

__all__ = ["apply_transforms", "apply_defaults"]


def apply_transforms(
    table: str,
    data: Dict[str, Any],
    table_schema: Dict[str, Any],
    ops: Any,
) -> Dict[str, Any]:
    """
    Apply field-level ``transform:`` directives to ``data`` **before** validation.

    Transforms normalise raw user input so both the validator and the DB writer
    see the same cleaned value.  Supported built-in aliases (pipe-chainable):

        lowercase   → value.lower()
        uppercase   → value.upper()
        trim        → value.strip()
        trim_lower  → value.strip().lower()  (convenience shorthand)
        slug        → lower + collapse whitespace/underscores to '-'
        capitalize  → value.capitalize()

    Pipe-chaining applies transforms left-to-right, e.g.::

        transform: trim|lowercase

    Returns a *new* dict with transformed values; ``data`` is not mutated.
    Non-string values are skipped silently (transform only applies to str).
    """
    _BUILT_INS: Dict[str, Any] = {
        "lowercase":  lambda v: v.lower(),
        "uppercase":  lambda v: v.upper(),
        "trim":       lambda v: v.strip(),
        "trim_lower": lambda v: v.strip().lower(),
        "capitalize": lambda v: v.capitalize(),
        "slug": lambda v: (
            __import__("re").sub(r"[-\s_]+", "-", v.strip().lower())
        ),
    }

    result = dict(data)
    for field_name, raw_value in data.items():
        field_def = table_schema.get(field_name)
        if not isinstance(field_def, dict):
            continue
        transform_spec = field_def.get("transform")
        if not transform_spec:
            continue
        if not isinstance(raw_value, str):
            continue

        steps = [s.strip() for s in str(transform_spec).split("|") if s.strip()]
        value = raw_value
        for step in steps:
            fn = _BUILT_INS.get(step)
            if fn:
                value = fn(value)
            else:
                ops.logger.warning(
                    "[zData] Unknown transform '%s' on field '%s' of table '%s' (skipping)",
                    step, field_name, table,
                )
        if value != raw_value:
            ops.logger.info(
                "[zData] transform '%s' on '%s': %r → %r",
                transform_spec, field_name, raw_value, value,
            )
        result[field_name] = value
    return result


def apply_defaults(
    table: str,
    data: Dict[str, Any],
    table_schema: Dict[str, Any],
    ops: Any,
) -> Dict[str, Any]:
    """
    Fill omitted / empty fields with their declared ``default:`` **before**
    validation and insert. This is what makes ``default`` true at the data layer
    (not only as a form pre-fill): a ``required`` column with a ``default`` can be
    left out of the payload and still satisfy NOT NULL.

    The special token ``now`` resolves to the current timestamp, shaped to the
    field's temporal type (``date`` → date, ``time`` → clock, else datetime).
    Only insert uses defaults — update never invents values for omitted fields.

    Returns a *new* dict; ``data`` is not mutated.
    """
    from datetime import datetime as _dt  # pylint: disable=import-outside-toplevel

    result = dict(data)
    for field_name, field_def in table_schema.items():
        if not isinstance(field_def, dict):
            continue
        if SCHEMA_KEY_DEFAULT not in field_def:
            continue
        current = result.get(field_name)
        if current is not None and current != "":
            continue  # caller supplied a value — never override it

        default = field_def.get(SCHEMA_KEY_DEFAULT)
        if default == "now":
            ftype = field_def.get("type")
            if ftype == "date":
                default = _dt.now().strftime("%Y-%m-%d")
            elif ftype == "time":
                default = _dt.now().strftime("%H:%M:%S")
            else:
                default = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        result[field_name] = default
        ops.logger.info(
            "[zData] default applied on '%s.%s': %r", table, field_name, default
        )
    return result
