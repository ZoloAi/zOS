# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/crud_join_refs.py
"""
Shared join helpers for cross-table writes — DELETE … USING and UPDATE … FROM.

Both features link a target table A to a second table B and either delete A rows
that join to B, or copy B values into A. Two tiny, adapter-agnostic primitives:

  parse_on   — read the join key pair from an ``on:`` spec (string or dict)
  resolve_ref — resolve a ``%table.field`` reference against the A / B rows

Kept out of the adapters entirely: cross-table writes are executed as plain reads
plus a normal write (see crud_delete / crud_update_join), so CSV, SQLite and
Postgres share one code path with no join-projection quirks.
"""

from typing import Any, Dict, Optional, Tuple


def _split_side(token: str) -> Tuple[Optional[str], str]:
    """'members.team_id' → ('members', 'team_id');  'team_id' → (None, 'team_id')."""
    token = token.strip()
    if "." in token:
        tbl, _, col = token.partition(".")
        return tbl.strip(), col.strip()
    return None, token


def parse_on(on: Any, a_table: str, b_table: str) -> Tuple[str, str]:
    """
    Resolve the (A-column, B-column) join key pair from an ``on:`` spec.

    Accepts either:
        on: "members.team_id = teams.id"        (string, SQL-style)
        on: {members: team_id, teams: id}        (dict keyed by table name)
    """
    if isinstance(on, dict):
        return str(on.get(a_table)), str(on.get(b_table))

    if isinstance(on, str) and "=" in on:
        left, _, right = on.partition("=")
        lt, lc = _split_side(left)
        rt, rc = _split_side(right)
        # Assign each side to A or B by its table qualifier; fall back to order.
        if lt == a_table or rt == b_table:
            return lc, rc
        if lt == b_table or rt == a_table:
            return rc, lc
        return lc, rc

    raise ValueError(f"Unparseable join 'on' spec: {on!r}")


def resolve_ref(spec: Any, a_row: Dict[str, Any], b_row: Optional[Dict[str, Any]],
                a_table: str, b_table: str) -> Any:
    """
    Resolve a SET value that may reference a row column.

        %teams.name   → b_row['name']       (value pulled from the FROM table)
        %members.name → a_row['name']       (value from the target row)
        %row.name     → a_row['name']       (alias for the target row)
        "literal"     → returned unchanged
    """
    if not (isinstance(spec, str) and spec.startswith("%")):
        return spec
    table_part, _, col = spec[1:].partition(".")
    if table_part in (a_table, "row", "self"):
        return a_row.get(col)
    if table_part == b_table:
        return b_row.get(col) if b_row else None
    return spec
