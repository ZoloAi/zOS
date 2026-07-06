# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/index_naming.py
"""
Index naming — the single source of truth for turning an ``indexes:`` spec into a
deterministic index name (and its field list). Shared so an index gets the SAME
name however it's born: at table-create, via standalone ``create_index``, in the
migration diff (declared-vs-live), and in the plan renderer. Symmetric names are
what make "declared this index" and "this index exists in the DB" comparable, and
what let a dropped declaration map cleanly to a ``DROP INDEX``.

Accepted spec forms (identical to the schema ``indexes:`` key):
  * a bare field string        → ``idx_<table>_<field>``
  * a field list/tuple         → ``idx_<table>_<f1>_<f2>``
  * a dict {fields, unique, name} → custom ``name`` wins, else composite default
"""

from zOS import Any, List, Optional


def resolve_index_fields(spec: Any) -> List[str]:
    """Return the ordered field list an index spec covers (empty if unknown)."""
    if isinstance(spec, str):
        return [spec]
    if isinstance(spec, (list, tuple)):
        return list(spec)
    if isinstance(spec, dict):
        fields = spec.get("fields", [])
        return [fields] if isinstance(fields, str) else list(fields)
    return []


def resolve_index_name(table_name: str, spec: Any) -> Optional[str]:
    """Resolve one index spec to its canonical name (None if unrecognized).

    A dict's explicit ``name`` always wins; otherwise the name is derived from the
    table + covered fields, matching the adapter's build-at-create convention.
    """
    if isinstance(spec, dict) and spec.get("name"):
        return spec["name"]
    fields = resolve_index_fields(spec)
    if not fields:
        return None
    return f"idx_{table_name}_{'_'.join(fields)}"


__all__ = ["resolve_index_name", "resolve_index_fields"]
