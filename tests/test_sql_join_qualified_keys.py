# tests/test_sql_join_qualified_keys.py
"""SQL joins must preserve qualified table.column keys (csv/sql parity).

Contract (data_advanced + Queries): after a join, every column surfaces in the
row dicts as "table.column" — the CSV adapter's pandas join produces these
dotted keys natively. The DB-API cursor.description strips table qualifiers,
so without self-aliasing two joined columns named e.g. "name" collide and
dict(zip) silently keeps only the last one (data loss), and %item.table.column
pattern slots resolve to nothing.

Regression suite for the fix in SQLAdapter._build_select_clause.
"""

import importlib.util
import logging
import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parent.parent / "core"
sys.path.insert(0, str(_CORE))  # zSys

if "zOS" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "zOS", _CORE / "__init__.py", submodule_search_locations=[str(_CORE)]
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["zOS"] = _module
    _spec.loader.exec_module(_module)

from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends import adapter_registry  # noqa: E402,F401
from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends.adapter_factory import AdapterFactory  # noqa: E402

_LOGGER = logging.getLogger("test_sql_join_qualified_keys")


def _adapter_with_join_data(tmp_path):
    """zCloud shape in miniature: zApps.name collides with zRegistrar.name."""
    adapter = AdapterFactory.create_adapter(
        "sqlite", {"path": str(tmp_path), "label": "app", "meta": {}}
    )
    adapter.connect()
    adapter.create_table("zRegistrar", {
        "id": {"type": "int", "pk": True},
        "name": {"type": "str"},
    })
    adapter.create_table("zApps", {
        "id": {"type": "int", "pk": True},
        "name": {"type": "str"},
        "owner": {"type": "int"},
    })
    adapter.insert_many("zRegistrar", [{"id": 1, "name": "gal"}])
    adapter.insert_many("zApps", [{"id": 10, "name": "zHello", "owner": 1}])
    return adapter


_JOIN = [{"table": "zRegistrar", "on": "zApps.owner = zRegistrar.id", "type": "LEFT"}]


def test_explicit_qualified_fields_keep_dotted_keys_and_both_values(tmp_path):
    adapter = _adapter_with_join_data(tmp_path)
    rows = adapter.select(
        ["zApps", "zRegistrar"],
        fields=["zApps.id", "zApps.name", "zRegistrar.name"],
        joins=_JOIN,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["zApps.id"] == 10
    assert row["zApps.name"] == "zHello"      # not lost to the collision
    assert row["zRegistrar.name"] == "gal"    # not lost to the collision
    assert "name" not in row                  # no bare ambiguous key


def test_star_multi_table_expands_to_dotted_keys(tmp_path):
    adapter = _adapter_with_join_data(tmp_path)
    rows = adapter.select(["zApps", "zRegistrar"], joins=_JOIN)
    assert len(rows) == 1
    row = rows[0]
    assert row["zApps.name"] == "zHello"
    assert row["zRegistrar.name"] == "gal"
    assert row["zApps.owner"] == 1
    assert row["zRegistrar.id"] == 1


def test_single_table_select_unchanged(tmp_path):
    adapter = _adapter_with_join_data(tmp_path)
    rows = adapter.select("zApps")
    assert rows[0]["name"] == "zHello"  # bare keys, exactly as before
    assert "zApps.name" not in rows[0]


def test_expressions_pass_through_unaliased(tmp_path):
    adapter = _adapter_with_join_data(tmp_path)
    rows = adapter.select(
        ["zApps", "zRegistrar"], fields=["COUNT(*) AS total"], joins=_JOIN,
    )
    assert rows[0]["total"] == 1
