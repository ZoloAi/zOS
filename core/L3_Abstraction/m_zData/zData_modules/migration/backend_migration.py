# zOS/core/L3_Abstraction/m_zData/zData_modules/migration/backend_migration.py
"""
BackendMigration - Handle backend type changes (CSV → PostgreSQL, etc.).

Handles backend migration operations including:
- Data export from old backend
- Data import to new backend
- Schema translation
- Data type mapping

Architecture:
    - Exports data from source adapter
    - Creates new adapter for target backend
    - Imports data with type conversion
    - Validates migration success
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from zOS import Any, Dict, Optional, Tuple

from ..shared.data_keys import SCHEMA_KEY_META

# Module Constants
_LOG_PREFIX = "[BackendMigration]"
_META_KEY = SCHEMA_KEY_META
_META_KEY_DATA_TYPE = "Data_Type"
_META_KEY_DATA_LABEL = "Data_Label"
_MIGRATIONS_DIRNAME = "zmigrations"
_MARKER_FILENAME = "zbackend.json"
# Per-table transfer ledger inside the marker (zOS#1): tables whose csv→target
# transfer is KNOWN complete. The boot gate's row-count inference never re-arms
# for a recorded table — burn-after-use ledgers are legitimately empty forever.
_MARKER_KEY_TRANSFERRED = "transferred_tables"


# ============================================================
# Backend marker — persisted record of which backend the data
# on disk was last migrated to. Lives at
# {data_dir}/zmigrations/zbackend.json, a location both CSV and
# file-DB backends share (Data_Path root), so it survives a
# Data_Type flip in the schema file. Written by `z migrate`,
# never by the boot path.
# ============================================================

def resolve_marker_dir(zos: Any, logger: Any, schema: Dict[str, Any]) -> Optional[Path]:
    """Resolve the on-disk data directory for a schema (marker + legacy-CSV root)."""
    try:
        from ..schema_manager import SchemaManager  # pylint: disable=import-outside-toplevel
        data_path, _ = SchemaManager(zos, logger).resolve_data_path(schema)
    except Exception:  # pylint: disable=broad-except
        return None
    if not data_path:
        return None
    path = Path(str(data_path))
    # File-style Data_Path (…/app.db, …/table.csv) → the containing directory.
    return path.parent if path.suffix else path


def _marker_path(marker_dir: Path) -> Path:
    return Path(marker_dir) / _MIGRATIONS_DIRNAME / _MARKER_FILENAME


def read_backend_marker(marker_dir: Path) -> Optional[Dict[str, Any]]:
    """Read the persisted backend marker, or None if absent/unreadable."""
    try:
        path = _marker_path(marker_dir)
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # pylint: disable=broad-except
        pass
    return None


def write_backend_marker(
    marker_dir: Path,
    data_type: str,
    data_label: Any = None,
    transferred: Any = None,
) -> None:
    """Persist the backend the data was just migrated to (best-effort bookkeeping).

    ``transferred`` (zOS#1): iterable of table names whose csv→target transfer
    completed THIS run. Names accumulate (union with the existing marker) —
    the marker dir is shared by every schema on the data dir, so each schema
    appends its own tables. The boot gate's csv-inference trusts this ledger:
    a recorded table never re-arms the drift gate, no matter what stale rows
    its legacy CSV still holds (burn-after-use tables are legitimately empty
    on the target forever).
    """
    try:
        path = _marker_path(marker_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = read_backend_marker(marker_dir) or {}
        ledger = set(previous.get(_MARKER_KEY_TRANSFERRED) or [])
        ledger.update(transferred or [])
        payload = {
            "data_type": str(data_type).lower(),
            "data_label": data_label,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            _MARKER_KEY_TRANSFERRED: sorted(ledger),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except Exception:  # pylint: disable=broad-except
        pass


# ============================================================
# Backend-switch detection
# ============================================================

def detect_backend_switch(
    zos: Any,
    logger: Any,
    new_schema: Dict[str, Any],
    target_adapter: Any,
) -> Optional[Tuple[str, Any]]:
    """
    Detect that the data on disk still lives on a DIFFERENT backend than the
    schema now declares — the "edit Data_Type in place" workflow, where the
    orchestrator has already been re-wired to the new backend and the naive
    old-vs-new meta comparison sees no change.

    Detection order:
      1. Backend marker ({data_dir}/zmigrations/zbackend.json) that DISAGREES
         with the declared backend — deterministic, written by every
         successful `z migrate`.
      2. csv → SQL inference from disk: a declared table with rows in
         {data_dir}/{table}.csv while the same table is missing or empty on
         the target. This runs even when the marker agrees — multiple schemas
         can share one data dir (one marker), so a sibling schema's success
         must not mask another's unfinished transfer. It self-limits: once a
         table has rows on the target, its CSV is ignored. Delete the legacy
         CSVs to retire the fallback entirely.

    Returns:
        (old_backend, connected source adapter) when a switch is pending,
        else None.
    """
    new_meta = new_schema.get(_META_KEY, {})
    new_backend = str(new_meta.get(_META_KEY_DATA_TYPE) or "").lower()
    if not new_backend:
        return None

    marker_dir = resolve_marker_dir(zos, logger, new_schema)
    if marker_dir is None:
        return None

    marker = read_backend_marker(marker_dir)
    marker_backend = str((marker or {}).get("data_type") or "").lower()
    if marker_backend and marker_backend != new_backend:
        source = _build_source_adapter(
            zos, logger, marker_backend, marker_dir, marker.get("data_label"), new_schema
        )
        if source:
            return (marker_backend, source)

    # csv → SQL inference from disk (see docstring for why it ignores the marker).
    if new_backend == "csv":
        return None
    # zOS#1: the marker's transferred_tables ledger is the gate's memory —
    # a table recorded as transferred never re-arms on row counts (burn-
    # after-use ledgers are legitimately empty on the target while their
    # stale rollback CSVs keep rows forever).
    transferred = set((marker or {}).get(_MARKER_KEY_TRANSFERRED) or [])
    if not _csv_data_pending(marker_dir, new_schema, target_adapter, transferred, logger):
        return None
    source = _build_source_adapter(zos, logger, "csv", marker_dir, None, new_schema)
    return ("csv", source) if source else None


def _csv_data_pending(
    data_dir: Path,
    schema: Dict[str, Any],
    target_adapter: Any,
    transferred: Optional[set] = None,
    logger: Any = None,
) -> bool:
    """True if any declared table has CSV rows on disk but no rows on the target.

    Tables in ``transferred`` (the marker ledger, zOS#1) are excluded from the
    inference — their transfer already completed; leftover CSV rows are stale
    rollback artifacts, worth a warning but never a boot refusal.
    """
    from .backend_transfer import _user_tables  # pylint: disable=import-outside-toplevel

    for table, _columns in _user_tables(schema):
        csv_file = Path(data_dir) / f"{table}.csv"
        if not csv_file.is_file() or not _csv_has_rows(csv_file):
            continue
        if transferred and table in transferred:
            if logger:
                logger.warning(
                    f"{_LOG_PREFIX} {table}.csv still holds rows but the marker "
                    f"records its transfer as complete — ignoring (stale legacy "
                    f"CSV; delete or empty it to silence this warning)."
                )
            continue
        try:
            if (target_adapter is not None
                    and hasattr(target_adapter, "table_exists")
                    and target_adapter.table_exists(table)
                    and (target_adapter.select(table) or [])):
                continue  # this table already has data on the new backend
        except Exception:  # pylint: disable=broad-except
            pass
        return True
    return False


def _csv_has_rows(path: Path) -> bool:
    """True if the CSV has at least one data row beyond the header."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            fh.readline()  # header
            return any(line.strip() for line in fh)
    except OSError:
        return False


def _build_source_adapter(
    zos: Any,
    logger: Any,
    backend: str,
    data_dir: Path,
    data_label: Any,
    new_schema: Dict[str, Any],
) -> Any:
    """Build + connect an adapter for the OLD backend the data still lives on."""
    try:
        from ..shared.backends.adapter_factory import AdapterFactory  # pylint: disable=import-outside-toplevel
        meta = dict(new_schema.get(_META_KEY, {}))
        meta[_META_KEY_DATA_TYPE] = backend
        adapter = AdapterFactory.create_adapter(backend, {
            "path": str(data_dir),
            "label": data_label or meta.get(_META_KEY_DATA_LABEL, "data"),
            "meta": meta,
        })
        adapter.connect()
        return adapter
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(f"{_LOG_PREFIX} Could not open legacy {backend} source: {exc}")
        return None


class BackendMigration:
    """
    Manages backend type migrations.
    
    Responsibilities:
        - Export data from source backend
        - Import data to target backend
        - Handle schema translation
        - Validate migration success
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance
    """

    def __init__(self, zos: Any, logger: Any) -> None:
        """
        Initialize BackendMigration.
        
        Args:
            zos: zOS framework instance
            logger: Logger instance
        """
        self.zos = zos
        self.logger = logger

    def handle_backend_migration(
        self,
        orchestrator: Any,
        old_backend: str,
        new_backend: str,
        new_schema: Dict[str, Any],
        dry_run: bool = False,
        source_adapter: Any = None,
    ) -> Dict[str, Any]:
        """
        Handle a ``Data_Type`` change by moving all data to the new backend.

        Exports every declared user table off the source adapter, builds a fresh
        adapter for the target backend from ``new_schema`` (via the same
        ConnectionManager the runtime uses), replays the rows onto it, and
        validates row counts. The shared row model lives in ``backend_transfer``.

        Source resolution: pass ``source_adapter`` explicitly when the switch was
        detected AFTER the orchestrator was re-wired to the new backend (the
        "edit Data_Type in place" workflow — see ``detect_backend_switch``).
        Without it, ``orchestrator.adapter`` must still be connected to the OLD
        backend.

        The old store is never modified — legacy files (e.g. the CSVs) stay on
        disk as the natural rollback artifact.

        Args:
            orchestrator: DataOrchestrator (schema = declared tables to move).
            old_backend: Source backend type (e.g. "csv").
            new_backend: Target backend type (e.g. "sqlite").
            new_schema: Target schema (carries the new Data_Type + path/env).
            dry_run: If True, report what would move without writing anything.
            source_adapter: Optional adapter connected to the OLD backend.

        Returns:
            Dict with success + moved-table/row counts (or error).
        """
        self.logger.info(f"{_LOG_PREFIX} Backend migration: {old_backend} → {new_backend}")

        from .backend_transfer import preview_transfer, transfer_backend

        source_adapter = source_adapter or getattr(orchestrator, "adapter", None)
        if source_adapter is None:
            return {"success": False, "error": "No source adapter to export from"}

        # zOS#13 guard: a cross-schema-file FK on a db-file backend lands in a
        # different {Data_Label}.db — flag it BEFORE the split becomes silent
        # data-layer breakage (both on dry-run preview and the live move).
        if str(new_backend).lower() != "csv":
            self._warn_cross_file_fks(new_schema or orchestrator.schema or {}, new_backend)

        if dry_run:
            preview = preview_transfer(source_adapter, orchestrator.schema or {})
            return {
                "success": True,
                "message": (f"Dry-run: would move {preview['rows']} row(s) across "
                            f"{preview['tables']} table(s) from {old_backend} → {new_backend}"),
                "preview": preview,
                "operations_executed": 0,
            }

        # Build a live adapter for the target backend from the new schema (reuses the
        # runtime's config/path resolution — env vars, Data_Path, etc.).
        try:
            from ..connection_manager import ConnectionManager
            conn = ConnectionManager(self.zos, self.logger)
            target = conn.initialize_adapter(schema=new_schema, zos=self.zos)
            target_adapter = target["adapter"]
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.error(f"{_LOG_PREFIX} Could not open target backend: {exc}")
            return {
                "success": False,
                "error": f"Could not open target backend {new_backend}: {exc}",
                "hint": "Ensure the new schema declares a valid Data_Path / ZDATA_*_URL.",
            }

        # Suspend FK enforcement for the bulk load: schemas migrate one at a
        # time (alphabetically), so a table can carry an FK to a sibling
        # schema's table that hasn't been created yet. Standard bulk-load
        # practice — the rows come from CSV where FKs were never enforced,
        # and integrity is re-checked once everything has landed.
        _fk_was_suspended = self._suspend_foreign_keys(target_adapter)
        try:
            report = transfer_backend(
                source_adapter, target_adapter, orchestrator.schema or {}, self.logger
            )
        finally:
            if _fk_was_suspended:
                self._restore_foreign_keys(target_adapter)

        # Best-effort: carry migration history across (stub — see below).
        try:
            self._transfer_migration_history(
                source_adapter, target_adapter, old_backend, new_backend
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.warning(f"{_LOG_PREFIX} History transfer skipped: {exc}")

        return {
            "success": report["success"],
            "message": (f"Moved {report['rows']} row(s) across {report['tables']} table(s): "
                        f"{old_backend} → {new_backend}"),
            "operations_executed": report["tables"],
            "report": report,
            **({"error": "Transfer incomplete — "
                         f"errors: {report.get('errors') or 'none'}, "
                         f"row-count mismatches: {report['mismatches'] or 'none'}. "
                         "Re-run `z migrate` — completed tables are skipped, only "
                         "the missing ones are retried."}
               if not report["success"] else {}),
        }

    def _warn_cross_file_fks(self, schema: Dict[str, Any], new_backend: str) -> None:
        """Warn when this schema declares FKs to tables OUTSIDE its own file (zOS#13).

        On db-file backends each schema file lands in its own ``{Data_Label}.db``,
        so an FK whose target table lives in a sibling schema file points across
        database files — sqlite cannot enforce it, and multi-table plugin access
        via the injected ``data`` facade breaks (`no such table`). The one-line
        declarative fix is the SAME ``Data_Label:`` on every related schema file
        (all tables land in one ``{label}.db``); this makes the rule loud at the
        exact moment the split would happen instead of failing silently later.
        """
        from ..shared.data_keys import SCHEMA_TABLE_LEVEL_KEYS  # pylint: disable=import-outside-toplevel

        local_tables = {k for k in schema if k != _META_KEY}
        crossers = []
        for table, block in schema.items():
            if table == _META_KEY or not isinstance(block, dict):
                continue
            for col, cdef in block.items():
                if col in SCHEMA_TABLE_LEVEL_KEYS or not isinstance(cdef, dict):
                    continue
                fk = cdef.get("fk") or cdef.get("foreign_key")
                if not isinstance(fk, str) or "." not in fk:
                    continue
                ref_table = fk.split(".", 1)[0].strip()
                if ref_table and ref_table not in local_tables:
                    crossers.append(f"{table}.{col} → {fk}")
        if not crossers:
            return

        label = schema.get(_META_KEY, {}).get(_META_KEY_DATA_LABEL)
        self.logger.warning(
            f"{_LOG_PREFIX} ⚠ FK target(s) outside this schema file: "
            f"{', '.join(crossers)}. On {new_backend} each schema file maps to "
            f"its own {{Data_Label}}.db — a cross-file FK lands in a DIFFERENT "
            f"database file, where it is unenforceable and invisible to "
            f"multi-table reads. Fix: declare the same Data_Label"
            f"{f' ({label!r})' if label else ''} on every related schema file "
            f"so all FK-linked tables share one database."
        )

    def _suspend_foreign_keys(self, adapter: Any) -> bool:
        """Turn off SQLite FK enforcement for a bulk load. Returns True if done."""
        try:
            if "SQLite" not in type(adapter).__name__:
                return False
            # connect() is lazy — force the physical connection open first.
            connection = getattr(adapter, "connection", None) or adapter._ensure_open()  # pylint: disable=protected-access
            connection.commit()  # PRAGMA foreign_keys is a no-op inside an open txn
            connection.execute("PRAGMA foreign_keys = OFF")
            return True
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.debug(f"{_LOG_PREFIX} Could not suspend FKs: {exc}")
        return False

    def _restore_foreign_keys(self, adapter: Any) -> None:
        """Re-enable SQLite FK enforcement after the bulk load."""
        try:
            adapter.connection.commit()  # see _suspend_foreign_keys
            adapter.connection.execute("PRAGMA foreign_keys = ON")
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.warning(f"{_LOG_PREFIX} Could not restore FKs: {exc}")

    def _transfer_migration_history(
        self,
        _source_adapter: Any,
        _target_adapter: Any,
        source_backend: str,
        target_backend: str,
    ) -> None:
        """
        Transfer migration history when changing backend type.

        Design:
          CSV  → SQL : read zmigrations/{table}.zMigration.csv rows
                       → insert into _zmigrations table in target DB.
          SQL  → CSV : export _zmigrations rows
                       → write zmigrations/{table}.zMigration.csv files.
          SQL  → SQL : SELECT * FROM _zmigrations → INSERT INTO _zmigrations
                       on target (skipping already-applied hashes).

        NOT YET IMPLEMENTED — wired here so the hook location is established
        and the contract is clear before the backend migration feature lands.
        """
        self.logger.info(
            f"{_LOG_PREFIX} [stub] _transfer_migration_history "
            f"{source_backend} → {target_backend} — not yet implemented"
        )
