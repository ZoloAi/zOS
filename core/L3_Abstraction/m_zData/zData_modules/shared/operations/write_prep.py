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
    normalize_write_values(table, data, table_schema, ops) -> Dict
        ``zNull`` sentinel → SQL NULL, and date/datetime values → ISO canonical
        form (zOS#18) — runs before validation so validators see final values.
    apply_zhash_fields(table, data, table_schema, ops) -> (Dict, Optional[str])
        Hash ``zHash: bcrypt`` fields — the ONE hashing step shared by INSERT
        and UPDATE (zOS#41), so a change-password ``update()`` can never store
        plaintext while the signup ``insert()`` hashes.

All return a *new* dict and never mutate the input. ``helpers.py`` re-exports
the names so existing ``from .helpers import apply_transforms`` call sites keep
working unchanged.
"""

import re as _re

from zOS import Any, Dict, Optional, Tuple
from ..validators.constants import SCHEMA_KEY_DEFAULT

__all__ = ["apply_transforms", "apply_defaults", "normalize_write_values",
           "apply_zhash_fields"]

# A modular-crypt bcrypt digest: $2a$/$2b$/$2x$/$2y$ + 2-digit cost + 53 chars
# of salt+hash. Used to recognise an ALREADY-hashed value so re-writing a row
# (or a caller that hashed by hand, the pre-#41 survival pattern) can never
# double-hash — a double-hashed digest verifies against nothing, silently
# locking the account.
_BCRYPT_DIGEST_RE = _re.compile(r"^\$2[abxy]\$\d{2}\$[./A-Za-z0-9]{53}$")

# Write-side NULL sentinel (zOS#18): .zolo is string-first, so there was no way
# to WRITE a NULL declaratively (un-archiving a soft-deleted row needed a
# plugin). `zNull` mirrors its zFilters read-side meaning — in values:/data:/set:
# it resolves to SQL NULL. A literal string "zNull" as data is forfeited, same
# reserved-token tradeoff the read side already made.
_ZNULL_SENTINEL = "zNull"

# Temporal types whose accepted values are normalized to ISO before storage.
_TEMPORAL_ISO_TYPES = ("date", "datetime")


def normalize_write_values(
    table: str,
    data: Dict[str, Any],
    table_schema: Dict[str, Any],
    ops: Any,
) -> Dict[str, Any]:
    """
    Normalize a write payload's VALUES **before** validation (zOS#18):

    1. ``zNull`` sentinel → ``None`` on any field — the declarative NULL literal
       (e.g. restore = ``set: {deleted_at: zNull}``), mirroring the token's
       zFilters read-side meaning.
    2. ``date`` / ``datetime`` typed fields → ISO canonical form via
       ``coerce_temporal_iso``: machine-pref-formatted values (``&zNow``'s
       default shape) become sortable ISO, and an ISO date-only value widens to
       midnight for a datetime column. Unparseable values pass through
       unchanged so the validator still owns the reject.

    Returns a *new* dict; ``data`` is not mutated.
    """
    from ..validators.format_validator import coerce_temporal_iso  # pylint: disable=import-outside-toplevel

    result = dict(data)
    for field_name, raw_value in data.items():
        if isinstance(raw_value, str) and raw_value.strip() == _ZNULL_SENTINEL:
            result[field_name] = None
            ops.logger.info(
                "[zData] zNull sentinel on '%s.%s' → NULL", table, field_name
            )
            continue

        field_def = table_schema.get(field_name)
        if not isinstance(field_def, dict):
            continue
        ftype = field_def.get("type")
        if ftype in _TEMPORAL_ISO_TYPES and isinstance(raw_value, str) and raw_value.strip():
            iso_value = coerce_temporal_iso(
                raw_value.strip(), ftype, getattr(ops, "zos", None)
            )
            if iso_value != raw_value:
                result[field_name] = iso_value
                ops.logger.info(
                    "[zData] %s '%s.%s' normalized to ISO: %r → %r",
                    ftype, table, field_name, raw_value, iso_value,
                )
    return result


def apply_zhash_fields(
    table: str,
    data: Dict[str, Any],
    table_schema: Dict[str, Any],
    ops: Any,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Hash every ``zHash: bcrypt`` field in a write payload (zOS#41).

    The SINGLE hashing step for insert AND update: before this, only insert
    hashed — so the natural change-password call,
    ``data.update("Users", {"password": new_password}, …)``, silently wrote
    PLAINTEXT to the store. One `zData` call hashed, its sibling didn't, and
    nothing said so.

    Values already shaped like a bcrypt digest pass through untouched (with a
    log line): re-writing a fetched row, seeding pre-hashed users, or a caller
    that hashed by hand must never be double-hashed — that verifies against
    nothing and locks the account. A user genuinely choosing a bcrypt-digest
    string AS their password is the forfeited corner, same reserved-token
    tradeoff as ``zNull``.

    Returns ``(new_dict, None)`` on success or ``(data, error_msg)`` when
    hashing is impossible (zAuth missing / hash failure) — the write must NOT
    proceed on error, or the plaintext lands exactly as before.
    """
    result = dict(data)
    for field_name, raw_value in data.items():
        field_def = table_schema.get(field_name)
        if not (isinstance(field_def, dict) and field_def.get("zHash") == "bcrypt"):
            continue
        if raw_value is None or raw_value == "":
            continue  # empty stays empty — required/min_length owns the reject
        if isinstance(raw_value, str) and _BCRYPT_DIGEST_RE.match(raw_value):
            ops.logger.info(
                "[zData] '%s.%s' already a bcrypt digest — stored as-is (no re-hash)",
                table, field_name,
            )
            continue
        if not (getattr(ops, "zos", None) and hasattr(ops.zos, "auth")):
            return data, f"zHash: bcrypt on '{field_name}' but zAuth not available"
        try:
            result[field_name] = ops.zos.auth.hash_password(str(raw_value))
        except Exception as e:  # pylint: disable=broad-except
            return data, f"Failed to hash '{field_name}': {e}"
    return result, None


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
