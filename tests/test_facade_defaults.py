"""zOS#23 (half A) — the plugin data facade honors schema defaults on insert.

THE BUG (dogfooded in zCloud Media, 2026-07-15): `data.insert("Media", {...})`
through zos_plugin's DataFacade was a plain adapter pass-through — schema
`default: now` (and every other declared default) never fired, landing NULL
`created_at`/`updated_at` while the IDENTICAL declarative zData insert
stamped them. Two write doors, one defaults engine, one door skipped it.

THE FIX: DataFacade.insert / insert_many (and upsert's insert leg, which
funnels through insert) look the table up in SchemaManager._server_registry —
already warm, since plugins call load_schema before writing — and run the
same write_prep.apply_defaults as the declarative path. Contracts preserved:
supplied values are never overridden; unregistered tables behave exactly as
before (no defaults, no errors); update never invents values.

NOT covered here (issue's half B, still open): `on_update: now` auto-touch.
"""
from types import SimpleNamespace

import pytest

from zOS.L3_Abstraction.m_zData.zData_modules.schema_manager import SchemaManager
from zos_plugin.facades import DataFacade


TABLE = "zTestFacadeDefaults"

SCHEMA = {
    TABLE: {
        "id": {"type": "int", "pk": True, "auto_increment": True},
        "email": {"type": "str", "required": True},
        "status": {"type": "str", "required": True, "default": "new"},
        "created_at": {"type": "datetime", "default": "now"},
        "birth_date": {"type": "date", "default": "now"},
    },
}


class _AdapterSpy:
    """Captures what would hit the adapter; no real database involved."""

    def __init__(self):
        self.inserts = []

    def insert(self, table, fields, values):
        self.inserts.append(dict(zip(fields, values)))

    def insert_many(self, table, rows):
        self.inserts.extend(rows)
        return rows

    def select(self, table, fields=None, where=None):
        return []


@pytest.fixture()
def facade():
    SchemaManager._server_registry[TABLE] = SCHEMA
    spy = _AdapterSpy()
    zos = SimpleNamespace(data=spy, logger=None)
    yield DataFacade(zos), spy
    SchemaManager._server_registry.pop(TABLE, None)


def test_default_now_fires_on_facade_insert(facade):
    f, spy = facade
    f.insert(TABLE, {"email": "maya@test.zolo"})
    row = spy.inserts[0]
    assert row["status"] == "new"
    # datetime-typed 'now' → 'YYYY-MM-DD HH:MM:SS'; date-typed → 'YYYY-MM-DD'
    assert len(row["created_at"]) == 19 and row["created_at"][4] == "-"
    assert len(row["birth_date"]) == 10


def test_supplied_values_never_overridden(facade):
    f, spy = facade
    f.insert(TABLE, {"email": "x@y.z", "status": "approved",
                     "created_at": "2020-01-01 00:00:00"})
    row = spy.inserts[0]
    assert row["status"] == "approved"
    assert row["created_at"] == "2020-01-01 00:00:00"


def test_empty_string_counts_as_omitted(facade):
    # apply_defaults' own contract: '' (an empty form field) takes the default.
    f, spy = facade
    f.insert(TABLE, {"email": "x@y.z", "status": ""})
    assert spy.inserts[0]["status"] == "new"


def test_insert_many_stamps_every_row(facade):
    f, spy = facade
    f.insert_many(TABLE, [{"email": "a@b.c"}, {"email": "d@e.f"}])
    assert all(r["status"] == "new" and r["created_at"] for r in spy.inserts)


def test_unregistered_table_is_untouched(facade):
    # The pre-#23 behavior survives for tables outside the registry.
    f, spy = facade
    f.insert("zNeverRegistered", {"email": "x@y.z"})
    assert spy.inserts[0] == {"email": "x@y.z"}
