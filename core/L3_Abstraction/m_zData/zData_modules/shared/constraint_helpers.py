# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/constraint_helpers.py
"""
Constraint helpers — split a table's declared ``constraints:`` into the two kinds
that migrate very differently:

  * UNIQUE  → folded into the INDEX pipeline as a unique index spec. A unique
    constraint IS a unique index at the storage layer, so routing it through the
    already-idempotent, introspected, cross-backend index machinery gives add +
    drop-detection + apply for free (works everywhere, including a clean CSV no-op).
  * FK / CHECK → kept as constraints. These need real ``ALTER TABLE … ADD/DROP
    CONSTRAINT`` DDL — native on Postgres, guarded on SQLite (which needs a table
    rebuild) and a no-op on CSV. Each def is stamped with its own ``name`` so the
    diff/executor can DROP it by name.

Pure + SSOT: one place decides what "unique-as-index" means, consumed by the schema
converter (new side) and any caller normalizing a ``constraints:`` block.
"""

from zOS import Any, Dict, List, Tuple

_UNIQUE_TYPES = ("unique", "uq")


def split_constraints(constraints: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Split a ``{name: def}`` constraint map into (unique_index_specs, others).

    - unique_index_specs: ``[{fields, unique: True, name}]`` for the index pipeline.
    - others: ``{name: def}`` for fk/check, each def stamped with its ``name``.
    """
    unique_index_specs: List[Dict[str, Any]] = []
    others: Dict[str, Any] = {}
    for name, cdef in (constraints or {}).items():
        ctype = (cdef.get("type") if isinstance(cdef, dict) else "") or ""
        if str(ctype).lower() in _UNIQUE_TYPES:
            fields = cdef.get("fields", []) if isinstance(cdef, dict) else []
            if isinstance(fields, str):
                fields = [fields]
            unique_index_specs.append({"fields": list(fields), "unique": True, "name": name})
        else:
            # Stamp the name onto the def so a later DROP can name it.
            others[name] = {**cdef, "name": name} if isinstance(cdef, dict) else {"name": name}
    return unique_index_specs, others


__all__ = ["split_constraints"]
