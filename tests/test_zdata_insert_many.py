"""zPlanner#15 — zData exposes the insert_many delegate the plugin facade calls.

THE BUG: DataFacade.insert_many (zos_plugin/facades.py) has called
``self._d.insert_many(table, rows)`` since 33b81b8 ("bulk insert facade"), but
zData — the ``_d`` behind every real plugin handle — never declared the
delegate. Every plugin bulk insert died with AttributeError, so the bulk path
NEVER worked outside tests: test_facade_defaults' _AdapterSpy happens to
implement insert_many itself, which is exactly how the gap stayed invisible.
Hit for real seeding zPlanner's board (2026-09-05); worked around with a loop.

THE FIX: a one-delegate addition to zData, mirroring insert/select/update —
straight to DataOrchestrator.insert_many (which, since zOS#23B, also applies
schema defaults, so both bulk doors behave like their single-row siblings).

The e2e below goes through the REAL chain that was broken — DataFacade →
zData → DataOrchestrator → SQLiteAdapter — not a spy.
"""
import logging
from types import SimpleNamespace

import pytest

from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends import (  # noqa: F401  (registers builtins)
    adapter_registry,
)
from zOS.L3_Abstraction.m_zData.zData import zData
from zos_plugin.facades import DataFacade


class _NullDisplay:
    def __getattr__(self, name):
        return lambda *a, **k: None


def _stub_zos():
    base = logging.getLogger("ztest.zdata.insert_many")
    logger = SimpleNamespace(
        framework=base, debug=base.debug, info=base.info,
        warning=base.warning, error=base.error,
    )
    return SimpleNamespace(
        session={},
        logger=logger,
        display=_NullDisplay(),
        loader=SimpleNamespace(),
        zparser=SimpleNamespace(resolve_data_path=lambda p: p),
    )


def test_zdata_declares_every_crud_verb_the_plugin_facade_calls():
    """The parity check that would have caught 33b81b8: every ``self._d.<verb>``
    in the plugin facade must exist on zData."""
    for verb in ("insert", "insert_many", "select", "update", "delete", "upsert"):
        assert callable(getattr(zData, verb, None)), f"zData is missing .{verb}"


def test_insert_many_delegates_to_orchestrator():
    d = zData(_stub_zos())
    calls = []
    d.orchestrator = SimpleNamespace(
        insert_many=lambda table, rows: calls.append((table, rows)) or [1, 2]
    )
    result = d.insert_many("T", [{"a": 1}, {"a": 2}])
    assert calls == [("T", [{"a": 1}, {"a": 2}])]
    assert result == [1, 2]


@pytest.fixture()
def live_facade(tmp_path):
    """The real broken chain, end to end: DataFacade → zData → orchestrator →
    a real sqlite file."""
    zos = _stub_zos()
    schema = {
        "zMeta": {
            "Schema_Name": "ztest_bulk",
            "Data_Type": "sqlite",
            "Data_Path": str(tmp_path / "bulk.db"),
            "Data_Label": "ztest",
        },
        "Widget": {
            "id": {"type": "int", "pk": True, "auto_increment": True},
            "name": {"type": "str", "required": True},
            "status": {"type": "str", "default": "new"},
            "created_at": {"type": "datetime", "default": "now"},
        },
    }
    d = zData(zos)
    d.load_schema(schema)
    d.orchestrator.create_table("Widget", schema)
    zos.data = d
    facade = DataFacade(zos)
    yield facade, d
    d.disconnect()


def test_bulk_path_works_end_to_end(live_facade):
    facade, d = live_facade
    count = facade.insert_many("Widget", [{"name": "a"}, {"name": "b"}, {"name": "c"}])
    assert count == 3
    rows = d.select("Widget")
    assert len(rows) == 3
    # Defaults fired on the bulk path too (zOS#23B on the orchestrator side).
    assert all(r["status"] == "new" and r["created_at"] for r in rows)
