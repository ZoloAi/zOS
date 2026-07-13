# tests/test_backend_switch.py
"""Backend-switch migration (Data_Type flip) — detection, marker, data transfer.

Regression suite for the wiring gap where changing Data_Type in place (csv →
sqlite) ran DDL against the new empty store and never moved the CSV rows:
migrate_app loads the NEW schema into the orchestrator before old-vs-new meta
is compared, so the explicit backend branch could never fire.

These tests exercise the recovery paths directly against real adapters:
  * legacy inference (CSV data on disk, empty target, no marker)
  * the persisted backend marker (zmigrations/zbackend.json)
  * transfer_backend row movement + idempotent re-run (skip non-empty target)
"""

import importlib.util
import logging
import sys
from pathlib import Path

import pytest

_CORE = Path(__file__).resolve().parent.parent / "core"
sys.path.insert(0, str(_CORE))  # zSys

# Alias `zOS` → the working-tree core/ (mirrors the installed package_dir
# mapping zOS -> core) so the modules under test are the LOCAL ones.
if "zOS" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "zOS", _CORE / "__init__.py", submodule_search_locations=[str(_CORE)]
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["zOS"] = _module
    _spec.loader.exec_module(_module)

from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends import adapter_registry  # noqa: E402,F401  (registers builtins)
from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends.adapter_factory import AdapterFactory  # noqa: E402
from zOS.L3_Abstraction.m_zData.zData_modules.migration.backend_migration import (  # noqa: E402
    detect_backend_switch,
    read_backend_marker,
    resolve_marker_dir,
    write_backend_marker,
)
from zOS.L3_Abstraction.m_zData.zData_modules.migration.backend_transfer import (  # noqa: E402
    transfer_backend,
)

_LOGGER = logging.getLogger("test_backend_switch")

_COLUMNS = {
    "id": {"type": "int", "pk": True},
    "name": {"type": "str"},
    "score": {"type": "float"},
}


def _schema(data_dir: Path, data_type: str) -> dict:
    return {
        "zMeta": {
            "Data_Type": data_type,
            "Data_Path": str(data_dir),
            "Data_Label": "app",
        },
        "users": dict(_COLUMNS),
    }


def _zos_stub():
    class _Parser:
        @staticmethod
        def resolve_data_path(path):
            return path

    class _Zos:
        zparser = _Parser()
        loader = None  # SchemaManager.__init__ stores it; unused by resolve_data_path

    return _Zos()


def _write_csv(data_dir: Path, rows=(("1", "ada", "9.5"), ("2", "bob", "7.0"))):
    lines = ["id,name,score"] + [",".join(r) for r in rows]
    (data_dir / "users.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sqlite_target(data_dir: Path):
    adapter = AdapterFactory.create_adapter(
        "sqlite", {"path": str(data_dir), "label": "app", "meta": {}}
    )
    adapter.connect()
    return adapter


# ── marker round-trip ─────────────────────────────────────────────────────────

def test_marker_roundtrip(tmp_path):
    assert read_backend_marker(tmp_path) is None
    write_backend_marker(tmp_path, "SQLite", "app")
    marker = read_backend_marker(tmp_path)
    assert marker["data_type"] == "sqlite"  # normalized to lowercase
    assert marker["data_label"] == "app"
    assert (tmp_path / "zmigrations" / "zbackend.json").is_file()


def test_resolve_marker_dir_file_style_path(tmp_path):
    schema = {
        "zMeta": {"Data_Type": "sqlite", "Data_Path": str(tmp_path / "app.db")}
    }
    assert resolve_marker_dir(_zos_stub(), _LOGGER, schema) == tmp_path


# ── legacy inference (no marker) ──────────────────────────────────────────────

def test_detect_infers_csv_to_sqlite_without_marker(tmp_path):
    _write_csv(tmp_path)
    target = _sqlite_target(tmp_path)
    detected = detect_backend_switch(
        _zos_stub(), _LOGGER, _schema(tmp_path, "sqlite"), target
    )
    assert detected is not None
    old_backend, source = detected
    assert old_backend == "csv"
    rows = source.select("users")
    assert len(rows) == 2


def test_no_detection_when_target_already_has_data(tmp_path):
    _write_csv(tmp_path)
    target = _sqlite_target(tmp_path)
    target.create_table("users", _COLUMNS)
    target.insert_many("users", [{"id": 1, "name": "ada", "score": 9.5}])
    assert detect_backend_switch(
        _zos_stub(), _LOGGER, _schema(tmp_path, "sqlite"), target
    ) is None


def test_no_detection_without_csv_data(tmp_path):
    (tmp_path / "users.csv").write_text("id,name,score\n", encoding="utf-8")  # header only
    target = _sqlite_target(tmp_path)
    assert detect_backend_switch(
        _zos_stub(), _LOGGER, _schema(tmp_path, "sqlite"), target
    ) is None


def test_no_detection_when_declared_backend_is_csv(tmp_path):
    _write_csv(tmp_path)
    assert detect_backend_switch(
        _zos_stub(), _LOGGER, _schema(tmp_path, "csv"), None
    ) is None


# ── marker-driven detection ───────────────────────────────────────────────────

def test_marker_match_with_transferred_data_means_no_switch(tmp_path):
    """Legacy CSVs on disk must not retrigger once the target holds the data."""
    _write_csv(tmp_path)
    write_backend_marker(tmp_path, "sqlite", "app")
    target = _sqlite_target(tmp_path)
    target.create_table("users", _COLUMNS)
    target.insert_many("users", [{"id": 1, "name": "ada", "score": 9.5},
                                 {"id": 2, "name": "bob", "score": 7.0}])
    assert detect_backend_switch(
        _zos_stub(), _LOGGER, _schema(tmp_path, "sqlite"), target
    ) is None


def test_marker_match_does_not_mask_unfinished_sibling(tmp_path):
    """Multiple schemas share one data dir/marker: a sibling's success (marker
    already flipped to sqlite) must not hide THIS schema's unmoved CSV data."""
    _write_csv(tmp_path)
    write_backend_marker(tmp_path, "sqlite", "app")  # sibling schema finished
    target = _sqlite_target(tmp_path)  # but users table has no rows yet
    detected = detect_backend_switch(
        _zos_stub(), _LOGGER, _schema(tmp_path, "sqlite"), target
    )
    assert detected is not None and detected[0] == "csv"


def test_marker_mismatch_detects_switch(tmp_path):
    _write_csv(tmp_path)
    write_backend_marker(tmp_path, "csv", "app")
    target = _sqlite_target(tmp_path)
    detected = detect_backend_switch(
        _zos_stub(), _LOGGER, _schema(tmp_path, "sqlite"), target
    )
    assert detected is not None and detected[0] == "csv"


# ── data transfer ─────────────────────────────────────────────────────────────

def test_transfer_moves_rows_and_coerces_types(tmp_path):
    _write_csv(tmp_path)
    schema = _schema(tmp_path, "sqlite")
    detected = detect_backend_switch(_zos_stub(), _LOGGER, schema, None)
    assert detected is not None
    _, source = detected
    target = _sqlite_target(tmp_path)

    report = transfer_backend(source, target, schema, _LOGGER)
    assert report["success"] is True
    assert report["tables"] == 1
    assert report["rows"] == 2
    assert report["mismatches"] == {}

    rows = sorted(target.select("users"), key=lambda r: r["id"])
    assert rows[0]["id"] == 1 and rows[0]["name"] == "ada"
    assert rows[1]["score"] == pytest.approx(7.0)


def test_transfer_rerun_skips_nonempty_target(tmp_path):
    _write_csv(tmp_path)
    schema = _schema(tmp_path, "sqlite")
    _, source = detect_backend_switch(_zos_stub(), _LOGGER, schema, None)
    target = _sqlite_target(tmp_path)

    first = transfer_backend(source, target, schema, _LOGGER)
    assert first["rows"] == 2

    second = transfer_backend(source, target, schema, _LOGGER)
    assert second["rows"] == 0
    assert second["skipped"] == {"users": 2}
    assert len(target.select("users")) == 2  # no duplicates


def test_target_table_created_empty_by_prior_ddl_still_gets_rows(tmp_path):
    """The zCloud shape: an earlier DDL-only migrate created empty tables."""
    _write_csv(tmp_path)
    schema = _schema(tmp_path, "sqlite")
    target = _sqlite_target(tmp_path)
    target.create_table("users", _COLUMNS)  # empty — prior DDL-only run

    detected = detect_backend_switch(_zos_stub(), _LOGGER, schema, target)
    assert detected is not None
    _, source = detected

    report = transfer_backend(source, target, schema, _LOGGER)
    assert report["success"] is True and report["rows"] == 2
    assert len(target.select("users")) == 2
