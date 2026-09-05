"""zOS#23 (half B) — the THIN data door honors schema defaults on insert.

THE BUG (dogfooded in zCloud register.py + dad's MedTrack log, 2026-09-04):
plugins reach zData through TWO doors, and half A only fixed one of them.

    door 1  data.insert("T", {...})                 -> DataFacade  (fixed: 48b8f8d)
    door 2  zos.data.insert(table=, fields=, values=) -> zData -> DataOrchestrator

Door 2 is the raw adapter signature a plugin gets off the `zos` handle. It was a
straight pass-through: `default: now` never fired, so every pre-fix registrar row
landed with NULL created_at/updated_at and the Profile page printed the raw
%data.registrar.created_at token. register.py hand-stamps role/status/created_at/
updated_at to survive exactly this (kept, belt and braces) — but its zCard insert
on the next line does NOT, and silently took the NULLs.

THE FIX: DataOrchestrator.insert / insert_many run the same write_prep.apply_defaults
as the declarative path, against the schema already loaded on the orchestrator.

Layering note: the DECLARATIVE door (handle_insert) applies defaults in its own
pipeline and reaches the adapter via operations.insert — it does NOT pass through
DataOrchestrator.insert, so this is not a double application for that path.
"""
from types import SimpleNamespace

import logging
import pytest

from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends import (  # noqa: F401  (registers builtins)
    adapter_registry,
)
from zOS.L3_Abstraction.m_zData.zData_modules.orchestrator import DataOrchestrator


TABLE = "zTestThinDoorDefaults"

SCHEMA = {
    TABLE: {
        "id": {"type": "int", "pk": True, "auto_increment": True},
        "email": {"type": "str", "required": True},
        "role": {"type": "str", "required": True, "default": "zUser"},
        "created_at": {"type": "datetime", "default": "now"},
        "updated_at": {"type": "datetime", "default": "now"},
        "birth_date": {"type": "date", "default": "now"},
    },
}


class _OperationsSpy:
    """Stands in for DataOperations; captures what would hit the adapter."""

    def __init__(self):
        self.inserts = []
        self.logger = logging.getLogger("ztest.orchestrator.defaults")

    def insert(self, table, fields, values):
        self.inserts.append(dict(zip(fields, values)))
        return 1

    def insert_many(self, table, rows_data):
        self.inserts.extend(rows_data)
        return list(range(len(rows_data)))


@pytest.fixture()
def orch():
    logger = SimpleNamespace(framework=logging.getLogger("ztest.framework"))
    o = DataOrchestrator(zos=SimpleNamespace(), logger=logger, session={})
    o.schema = SCHEMA
    o.operations = _OperationsSpy()
    return o, o.operations


def test_default_now_fires_on_thin_insert(orch):
    o, spy = orch
    o.insert(TABLE, ["email"], ["maya@test.zolo"])
    row = spy.inserts[0]
    assert row["role"] == "zUser"
    # datetime-typed 'now' -> 'YYYY-MM-DD HH:MM:SS'; date-typed -> 'YYYY-MM-DD'
    assert len(row["created_at"]) == 19 and row["created_at"][4] == "-"
    assert len(row["updated_at"]) == 19
    assert len(row["birth_date"]) == 10


def test_supplied_values_never_overridden(orch):
    o, spy = orch
    o.insert(
        TABLE,
        ["email", "role", "created_at"],
        ["x@y.z", "zAdmin", "2020-01-01 00:00:00"],
    )
    row = spy.inserts[0]
    assert row["role"] == "zAdmin"
    assert row["created_at"] == "2020-01-01 00:00:00"


def test_empty_string_counts_as_omitted(orch):
    # apply_defaults' own contract: '' (an empty form field) takes the default.
    o, spy = orch
    o.insert(TABLE, ["email", "role"], ["x@y.z", ""])
    assert spy.inserts[0]["role"] == "zUser"


def test_insert_many_stamps_every_row(orch):
    o, spy = orch
    o.insert_many(TABLE, [{"email": "a@b.c"}, {"email": "d@e.f"}])
    assert len(spy.inserts) == 2
    assert all(r["role"] == "zUser" and r["created_at"] for r in spy.inserts)


def test_unregistered_table_is_untouched(orch):
    # Fail-open: a table outside the loaded schema keeps the pass-through behavior.
    o, spy = orch
    o.insert("zNeverRegistered", ["email"], ["x@y.z"])
    assert spy.inserts[0] == {"email": "x@y.z"}


def test_no_schema_loaded_is_untouched(orch):
    # Cold orchestrator (schema is None) must not raise on the way to the adapter.
    o, spy = orch
    o.schema = None
    o.insert(TABLE, ["email"], ["x@y.z"])
    assert spy.inserts[0] == {"email": "x@y.z"}


def test_mismatched_fields_values_pass_through(orch):
    # A miscounted call is the adapter's error to report — never silently
    # truncated by a zip() we introduced.
    o, spy = orch
    o.insert(TABLE, ["email", "role"], ["x@y.z"])
    assert spy.inserts == [{"email": "x@y.z"}]


def test_register_py_zcard_shape_gets_its_defaults(orch):
    # The live regression: register.py's zCard insert passes ONE column and
    # hand-stamps nothing. Pre-fix it took NULL timestamps.
    o, spy = orch
    o.insert(TABLE, ["email"], ["owner@zolo.media"])
    row = spy.inserts[0]
    assert row["created_at"] and row["updated_at"] and row["role"] == "zUser"


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end — a REAL SQLiteAdapter, so the proof is the persisted row, not a spy
# ─────────────────────────────────────────────────────────────────────────────


class _NullDisplay:
    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture()
def live_orch(tmp_path):
    """A DataOrchestrator wired to a real sqlite file in tmp_path."""
    base = logging.getLogger("ztest.live")
    logger = SimpleNamespace(
        framework=base, debug=base.debug, info=base.info,
        warning=base.warning, error=base.error,
    )
    zos = SimpleNamespace(
        loader=SimpleNamespace(),
        logger=logger,
        display=_NullDisplay(),
        zparser=SimpleNamespace(resolve_data_path=lambda p: p),
    )
    schema = {
        "zMeta": {
            "Schema_Name": "ztest_thin_door",
            "Data_Type": "sqlite",
            "Data_Path": str(tmp_path / "thin_door.db"),
            "Data_Label": "ztest",
        },
        "Widget": {
            "id": {"type": "int", "pk": True, "auto_increment": True},
            "name": {"type": "str", "required": True},
            "role": {"type": "str", "default": "zUser"},
            "created_at": {"type": "datetime", "default": "now"},
        },
    }
    o = DataOrchestrator(zos=zos, logger=logger, session={})
    o.load_schema(schema)
    o.create_table("Widget", schema)
    yield o
    o.disconnect()


def test_thin_insert_persists_defaults_to_sqlite(live_orch):
    live_orch.insert("Widget", ["name"], ["thin-door"])
    row = live_orch.select("Widget", where={"name": "thin-door"})[0]
    assert row["role"] == "zUser"
    assert row["created_at"] and len(row["created_at"]) == 19


def test_pre_fix_pass_through_would_write_nulls(live_orch):
    """Pins the bug itself: with the defaults step disabled, the SAME call lands
    NULL role/created_at — the shape every pre-fix registrar row had."""
    live_orch._with_defaults = lambda table, data: data  # pylint: disable=protected-access
    live_orch.insert("Widget", ["name"], ["pre-fix"])
    row = live_orch.select("Widget", where={"name": "pre-fix"})[0]
    assert row["role"] is None and row["created_at"] is None
