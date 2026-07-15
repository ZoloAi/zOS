# tests/test_issues_13_18.py
"""Unit coverage for the zOS #13–#18 primitive-layer fixes (alpha polish batch).

    #13 — backend move warns when a schema declares FKs to tables OUTSIDE its
          own file (they'd land in a different {Data_Label}.db — unenforceable).
    #14 — backfill treats a cell still at the DDL-pre-filled `default:` as
          fillable for columns added THIS run (sqlite ADD COLUMN pre-fills), and
          warns when a declared backfill finds zero eligible cells.
    #15 — table-level keys (soft_delete, primary_key, zConstraints, …) are never
          diffed as columns; non-dict entries (hook strings) are skipped.
    #16 — action: window strips `fields:` from the inner read (the alias column
          only exists after the compute; projection happens in step 4).
    #17 — `where:` dicts speak the zFilters rule dialect (nested + flat forms),
          and grouped aggregate output honors `order_by`.
    #18 — `zNull` write sentinel → SQL NULL; date/datetime values normalize to
          ISO before storage; `type: datetime` accepts ISO date-only.
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

# noqa: E402 below — imports need the zOS bootstrap above
from zOS.L3_Abstraction.m_zData.zData_modules.shared.data_keys import (  # noqa: E402
    SCHEMA_TABLE_LEVEL_KEYS,
)
from zOS.L3_Abstraction.m_zData.zData_modules.shared.migration_backfill import (  # noqa: E402
    apply_backfills, _is_fillable,
)
from zOS.L3_Abstraction.m_zData.zData_modules.shared.migration_detection import (  # noqa: E402
    detect_schema_changes,
)
from zOS.L3_Abstraction.m_zData.zData_modules.shared.operations.request_extract import (  # noqa: E402
    _normalize_rule_dialect,
)
from zOS.L3_Abstraction.m_zData.zData_modules.shared.operations.agg_aggregate import (  # noqa: E402
    _sort_grouped,
)
from zOS.L3_Abstraction.m_zData.zData_modules.shared.operations.write_prep import (  # noqa: E402
    normalize_write_values,
)
from zOS.L3_Abstraction.m_zData.zData_modules.shared.validators.format_validator import (  # noqa: E402
    validate_datetime, coerce_temporal_iso,
)
from zOS.L3_Abstraction.m_zData.zData_modules.migration.migration_engine import (  # noqa: E402
    MigrationEngine,
)
from zOS.L3_Abstraction.m_zData.zData_modules.migration.backend_migration import (  # noqa: E402
    BackendMigration,
)

_LOGGER = logging.getLogger("test_issues_13_18")


# ── shared stubs ──────────────────────────────────────────────────────────────

class _RecordingLogger:
    def __init__(self):
        self.warnings, self.infos, self.debugs = [], [], []

    def warning(self, msg, *args):
        self.warnings.append(msg % args if args else str(msg))

    def info(self, msg, *args):
        self.infos.append(msg % args if args else str(msg))

    def debug(self, msg, *args):
        self.debugs.append(msg % args if args else str(msg))

    error = warning


class _BackfillAdapter:
    """In-memory rows keyed by pk 'id'; records updates."""

    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def select(self, _table):
        return self.rows

    def update(self, table, fields, values, where):
        self.updates.append((table, fields, values, where))
        target = where["id"]
        for row in self.rows:
            if row["id"] == target:
                row.update(dict(zip(fields, values)))


class _Ops:
    def __init__(self, adapter=None, logger=None, zos=None):
        self.adapter = adapter
        self.logger = logger or _RecordingLogger()
        self.zos = zos


# ── #13: cross-file FK warning on backend move ────────────────────────────────

def _backend_migration(logger):
    bm = object.__new__(BackendMigration)
    bm.zos = None
    bm.logger = logger
    return bm


def test_13_cross_file_fk_warns():
    logger = _RecordingLogger()
    bm = _backend_migration(logger)
    schema = {
        "zMeta": {"Data_Type": "sqlite", "Data_Label": "Checkins"},
        "Checkins": {
            "id": {"type": "int", "pk": True},
            "habit_id": {"type": "int", "fk": "Habits.id", "on_delete": "cascade"},
        },
    }
    bm._warn_cross_file_fks(schema, "sqlite")
    assert len(logger.warnings) == 1
    assert "Checkins.habit_id → Habits.id" in logger.warnings[0]
    assert "Data_Label" in logger.warnings[0]


def test_13_in_file_fk_is_silent():
    logger = _RecordingLogger()
    bm = _backend_migration(logger)
    schema = {
        "zMeta": {"Data_Type": "sqlite"},
        "Habits": {"id": {"type": "int", "pk": True}},
        "Checkins": {
            "id": {"type": "int", "pk": True},
            "habit_id": {"type": "int", "fk": "Habits.id"},
        },
    }
    bm._warn_cross_file_fks(schema, "sqlite")
    assert logger.warnings == []


# ── #14: backfill fills DDL-pre-filled defaults; warns on zero-eligible ───────

def test_14_fillable_matrix():
    cdef = {"type": "int", "default": 0, "backfill": "%current_streak"}
    assert _is_fillable(None, cdef)          # csv empty
    assert _is_fillable("", cdef)            # csv empty string
    assert _is_fillable(0, cdef)             # sqlite DDL pre-fill (typed)
    assert _is_fillable("0", cdef)           # string-coerced match
    assert not _is_fillable(7, cdef)         # real data survives
    assert not _is_fillable(5, {"backfill": "%x"})  # no default declared → only empty fills


def test_14_backfill_fills_ddl_prefilled_rows():
    rows = [
        {"id": 1, "current_streak": 5, "best_streak": 0},
        {"id": 2, "current_streak": 3, "best_streak": 0},
        {"id": 3, "current_streak": 0, "best_streak": 0},
    ]
    adapter = _BackfillAdapter(rows)
    ops = _Ops(adapter=adapter)
    schema = {"Habits": {
        "id": {"type": "int", "pk": True},
        "current_streak": {"type": "int"},
        "best_streak": {"type": "int", "default": 0, "backfill": "%current_streak"},
    }}
    modified = {"Habits": {"columns_added": {
        "best_streak": {"type": "int", "default": 0, "backfill": "%current_streak"},
    }}}
    filled = apply_backfills(ops, modified, schema, _LOGGER)
    assert filled == 3
    assert [r["best_streak"] for r in rows] == [5, 3, 0]


def test_14_zero_eligible_warns():
    rows = [{"id": 1, "src": "x", "col": "real-data"}]
    ops = _Ops(adapter=_BackfillAdapter(rows))
    logger = _RecordingLogger()
    schema = {"T": {"id": {"type": "int", "pk": True}, "src": {"type": "str"},
                    "col": {"type": "str", "backfill": "%src"}}}
    modified = {"T": {"columns_added": {"col": {"type": "str", "backfill": "%src"}}}}
    filled = apply_backfills(ops, modified, schema, logger)
    assert filled == 0
    assert any("0 of 1" in w for w in logger.warnings)


# ── #15: table-level keys never diffed as columns ─────────────────────────────

_T15 = {
    "zMeta": {"Data_Type": "sqlite", "zMigration": True},
    "Habits": {
        "soft_delete": True,
        "primary_key": ["id", "name"],
        "zConstraints": [{"unique": ["name"]}],
        "onBeforeInsert": "&Plugin.hook",
        "id": {"type": "int", "pk": True},
        "deleted_at": {"type": "datetime"},
    },
}


def test_15_converter_excludes_table_level_keys():
    engine = object.__new__(MigrationEngine)
    engine.logger = _RecordingLogger()
    diff_shape = engine._convert_zcli_to_diff_format(_T15)
    cols = diff_shape["Tables"]["Habits"]["Columns"]
    assert set(cols) == {"id", "deleted_at"}
    for reserved in ("soft_delete", "primary_key", "zConstraints", "onBeforeInsert"):
        assert reserved not in cols


def test_15_detection_skips_flags_without_crashing():
    old = {"Habits": {"id": {"type": "int", "pk": True}}}
    changes = detect_schema_changes(old, {k: v for k, v in _T15.items() if k != "zMeta"})
    added = {c["name"] for c in changes["added"]}
    assert added == {"deleted_at"}


def test_15_registry_matches_runtime_consumers():
    assert "soft_delete" in SCHEMA_TABLE_LEVEL_KEYS
    assert "zConstraints" in SCHEMA_TABLE_LEVEL_KEYS
    assert "primary_key" in SCHEMA_TABLE_LEVEL_KEYS


# ── #16: window never forwards `fields:` to the inner read ────────────────────

def test_16_window_strips_fields_from_inner_read(monkeypatch):
    from zOS.L3_Abstraction.m_zData.zData_modules.shared.operations import (
        agg_window, crud_read,
    )
    captured = {}

    def _fake_read(request, _ops):
        captured.update(request)
        return [{"name": "a", "best_streak": 5}, {"name": "b", "best_streak": 3}]

    monkeypatch.setattr(crud_read, "handle_read", _fake_read)
    ops = _Ops()
    ops.display = None
    rows = agg_window.handle_window({
        "action": "window", "table": "Habits", "function": "row_number",
        "order_by": "best_streak DESC", "alias": "rank",
        "fields": ["name", "best_streak", "rank"], "silent": True,
    }, ops)
    assert "fields" not in captured           # the alias never reaches the read
    assert rows[0]["rank"] == 1 and rows[1]["rank"] == 2
    assert set(rows[0]) == {"name", "best_streak", "rank"}  # step-4 projection


# ── #17: where rule dialect + grouped order_by ────────────────────────────────

def test_17_where_rule_dialect_compiles():
    ops = _Ops()
    out = _normalize_rule_dialect({
        "deleted_at": {"zNull": True},          # nested rule dict
        "status": "zNull",                       # flat unary token
        "score": {"zAbove": 80},
        "name": "maya",                          # plain equality untouched
        "country": {"zData": {"action": "read"}},  # subquery untouched
    }, ops)
    assert out["deleted_at"] is None             # IS NULL for the adapter
    assert out["status"] is None
    assert out["score"] == {"$gt": 80}
    assert out["name"] == "maya"
    assert out["country"] == {"zData": {"action": "read"}}


def test_17_grouped_order_by():
    rows = [{"date": "2026-07-01", "total": 2},
            {"date": "2026-07-03", "total": 5},
            {"date": "2026-07-02", "total": 1}]
    by_date = _sort_grouped(rows, "date", True, "date", "total")
    assert [r["date"] for r in by_date] == ["2026-07-03", "2026-07-02", "2026-07-01"]
    by_alias = _sort_grouped(rows, "total", False, "date", "total")
    assert [r["total"] for r in by_alias] == [1, 2, 5]
    flat = _sort_grouped({"b": 2, "a": 9, "c": 1}, "date", False, "date", None)
    assert list(flat) == ["a", "b", "c"]         # group col → sort by key
    flat_val = _sort_grouped({"b": 2, "a": 9, "c": 1}, "total", True, "date", None)
    assert list(flat_val) == ["a", "b", "c"]     # alias → sort by value DESC


# ── #18: zNull write sentinel + temporal ISO normalization ────────────────────

_SCHEMA_18 = {
    "deleted_at": {"type": "datetime"},
    "joined": {"type": "date"},
    "note": {"type": "str"},
}


def test_18_znull_sentinel_writes_null():
    ops = _Ops()
    data = normalize_write_values("Habits", {"deleted_at": "zNull", "note": "keep"},
                                  _SCHEMA_18, ops)
    assert data["deleted_at"] is None
    assert data["note"] == "keep"


def test_18_machine_pref_datetime_normalizes_to_iso():
    class _Cfg:
        machine = {"datetime_format": "ddmmyyyy HH:MM:SS", "date_format": "ddmmyyyy"}

    class _Zos:
        config = _Cfg()

    ops = _Ops(zos=_Zos())
    data = normalize_write_values(
        "Habits", {"deleted_at": "15072026 09:16:51", "joined": "15072026"},
        _SCHEMA_18, ops,
    )
    assert data["deleted_at"] == "2026-07-15 09:16:51"   # sortable ISO
    assert data["joined"] == "2026-07-15"


def test_18_iso_date_only_widens_for_datetime():
    assert coerce_temporal_iso("2026-07-15", "datetime") == "2026-07-15 00:00:00"
    ok, err = validate_datetime("2026-07-15")            # used to fail (zOS#18)
    assert ok and err is None


def test_18_unparseable_value_passes_through_for_validator():
    assert coerce_temporal_iso("not-a-date", "datetime") == "not-a-date"
    ok, _err = validate_datetime("not-a-date")
    assert not ok
