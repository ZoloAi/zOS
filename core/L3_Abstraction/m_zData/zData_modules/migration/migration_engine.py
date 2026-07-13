# zOS/core/L3_Abstraction/m_zData/zData_modules/migration/migration_engine.py
"""
MigrationEngine - Declarative schema migration execution.

Handles schema migration operations including:
- Schema diff computation
- Migration preview and confirmation
- DDL operation execution
- Migration history tracking
- Rollback on failure

Architecture:
    - Uses schema_diff for computing changes
    - Uses migration_history for tracking
    - Integrates with adapter for DDL execution
    - Provides transaction safety
"""

from zOS import Any, Dict, List, Optional

from ..shared.data_keys import SCHEMA_KEY_META

# Module Constants
_LOG_PREFIX = "[MigrationEngine]"
_META_KEY = SCHEMA_KEY_META
_META_KEY_DATA_TYPE = "Data_Type"
_META_KEY_DATA_LABEL = "Data_Label"
_META_KEY_ZMIGRATION = "zMigration"
_META_KEY_ZMIGRATION_VERSION = "zMigrationVersion"
_ERROR_NO_ADAPTER = "No adapter initialized"


class MigrationEngine:
    """
    Manages declarative schema migrations.
    
    Responsibilities:
        - Execute schema migrations
        - Track migration history
        - Provide dry-run mode
        - Handle migration rollback
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance
    """

    def __init__(self, zos: Any, logger: Any) -> None:
        """
        Initialize MigrationEngine.
        
        Args:
            zos: zOS framework instance
            logger: Logger instance
        """
        self.zos = zos
        self.logger = logger

    def migrate(
        self,
        orchestrator: Any,
        new_schema_path: str,
        dry_run: bool = False,
        auto_approve: bool = False,
        schema_version: Optional[str] = None,
        plan: bool = False
    ) -> Dict[str, Any]:
        """
        Execute declarative schema migration.
        
        Args:
            orchestrator: DataOrchestrator instance
            new_schema_path: Path to new schema YAML file
            dry_run: If True, preview changes without executing
            auto_approve: If True, skip confirmation prompt
            schema_version: Optional version string
            
        Returns:
            Dict with success, diff, operations_executed, error
        """
        if not orchestrator.adapter:
            raise RuntimeError(_ERROR_NO_ADAPTER)
        if not orchestrator.schema:
            raise RuntimeError("No schema loaded. Call load_schema() first.")

        # Load new schema
        from zOS.L3_Abstraction.m_zData.zData_modules.shared.migration_history import (
            get_current_schema_hash,
            is_migration_applied,
        )

        new_schema = self.zos.loader.handle(new_schema_path)

        if not new_schema:
            error_msg = f"❌ Failed to load schema: {new_schema_path}"
            self.logger.error(error_msg)
            return {"success": False, "error": "Schema load failed"}

        # Check if migrations are enabled
        new_meta = new_schema.get(_META_KEY, {})
        migration_enabled = new_meta.get(_META_KEY_ZMIGRATION, False)

        if not migration_enabled:
            return self._migration_not_enabled_error(new_schema_path)

        # Log migration version
        new_version = new_meta.get(_META_KEY_ZMIGRATION_VERSION, "unknown")
        self.logger.info(f"[zMigrate] Schema version: {new_version}")

        # ── Backend change (Data_Type) ─────────────────────────────────────
        # Two ways a switch surfaces:
        #   explicit — orchestrator still holds the OLD schema/adapter and the
        #              new file declares a different backend;
        #   implicit — the usual `z migrate` / boot flow, where load_schema()
        #              already re-wired the orchestrator to the NEW backend so
        #              old-vs-new meta looks identical. detect_backend_switch()
        #              recovers the truth from the persisted backend marker (or,
        #              pre-marker, from legacy CSV data still on disk).
        from .backend_migration import (
            BackendMigration,
            detect_backend_switch,
            resolve_marker_dir,
            write_backend_marker,
        )

        old_meta = orchestrator.schema.get(_META_KEY, {})
        old_backend = old_meta.get(_META_KEY_DATA_TYPE)
        new_backend = new_meta.get(_META_KEY_DATA_TYPE)

        marker_dir = resolve_marker_dir(self.zos, self.logger, new_schema)
        transfer_result: Optional[Dict[str, Any]] = None

        explicit_switch = bool(
            old_backend and new_backend
            and str(old_backend).lower() != str(new_backend).lower()
        )
        if explicit_switch:
            switch_old_backend: Optional[str] = old_backend
            switch_source = orchestrator.adapter  # still connected to the old backend
        else:
            detected = detect_backend_switch(
                self.zos, self.logger, new_schema, orchestrator.adapter
            )
            switch_old_backend, switch_source = detected if detected else (None, None)

        if switch_source is not None:
            self.logger.info(
                f"[zMigrate] Backend change detected: {switch_old_backend} → {new_backend}"
            )
            backend_migration = BackendMigration(self.zos, self.logger)

            if dry_run:
                result = backend_migration.handle_backend_migration(
                    orchestrator, switch_old_backend, new_backend, new_schema,
                    dry_run=True, source_adapter=switch_source,
                )
                # The boot gate keys off diff.has_changes — a pending backend
                # switch with unmoved data IS drift and must refuse launch.
                result["diff"] = {
                    "has_changes": True,
                    "backend_switch": f"{switch_old_backend} → {new_backend}",
                }
                return result

            transfer_result = backend_migration.handle_backend_migration(
                orchestrator, switch_old_backend, new_backend, new_schema,
                dry_run=False, source_adapter=switch_source,
            )
            if not transfer_result.get("success"):
                return transfer_result
            self.zos.display.text(
                f"📦 {transfer_result.get('message', 'Backend data transfer complete')}"
            )
            if explicit_switch:
                # The orchestrator is still wired to the OLD backend — running the
                # DDL path against it would target the wrong store. Record the
                # marker and stop; a re-run on the new backend finishes DDL extras.
                if marker_dir:
                    write_backend_marker(
                        marker_dir, new_backend, new_meta.get(_META_KEY_DATA_LABEL)
                    )
                return transfer_result
            # Implicit switch: orchestrator.adapter IS the new backend — fall
            # through to the normal DDL path so indexes/constraints/history land
            # on the target, then the marker is written below on success.

        # Compute schema hash
        schema_hash = get_current_schema_hash(new_schema)

        # Short-circuit: schema hash already recorded as successful — nothing to do
        if is_migration_applied(orchestrator.adapter, schema_hash):
            self.logger.info("[zMigrate] Schema hash matches last applied migration — up to date")
            self.zos.display.text("✅ Migration completed successfully!")
            if not dry_run and marker_dir:
                write_backend_marker(marker_dir, new_backend, new_meta.get(_META_KEY_DATA_LABEL))
            return {"success": True, "diff": {}, "operations_executed": 0}

        # Resolve from_version from last migration record (first user-defined table)
        from_version = self._get_last_applied_version(orchestrator, new_schema)

        # Introspect database state
        self.logger.info("[zMigrate] Introspecting current database state...")
        old_schema_zcli = self._introspect_database_schema(orchestrator)

        # Convert schemas to diff format
        self.logger.debug("[zMigrate] Converting schemas to diff engine format...")
        old_schema_diff = self._convert_zcli_to_diff_format(old_schema_zcli)
        new_schema_diff = self._convert_zcli_to_diff_format(new_schema)

        # Build migration request
        request = {
            "old_schema": old_schema_diff,
            "new_schema": new_schema_diff,
            "dry_run": dry_run,
            "auto_approve": auto_approve,
            "schema_version": schema_version or new_version,
            "schema_hash": schema_hash,
            "from_version": from_version,
            "plan": plan,
        }

        # Execute migration via operations facade
        result = orchestrator.operations.route_action("migrate", request)

        if isinstance(result, dict) and result.get("success") and not dry_run and not plan:
            if marker_dir:
                write_backend_marker(marker_dir, new_backend, new_meta.get(_META_KEY_DATA_LABEL))
            if transfer_result is not None:
                result["backend_transfer"] = transfer_result.get("report")
        return result

    def rollback(self, orchestrator: Any, specific_table: Optional[str] = None) -> Dict[str, Any]:
        """
        Roll a CSV app back to its last pre-migration snapshot.

        Every CSV migration snapshots each affected table to
        ``zmigrations/<table>.csv.backup`` and records that path in the table's
        ``__zmigration_<table>`` history. Rollback reads the most recent successful
        record per table and restores its backup — undoing the last migration's
        data/shape change. SQL down-migrations (inverse DDL) are not yet built;
        those return a clear, non-destructive error.

        Args:
            orchestrator: DataOperations/orchestrator (adapter, schema).
            specific_table: Restore only this table; default = all user tables.

        Returns:
            Dict with success + restored (count) or error.
        """
        import shutil
        from pathlib import Path

        adapter = orchestrator.adapter
        if not adapter:
            raise RuntimeError(_ERROR_NO_ADAPTER)

        if "CSV" not in type(adapter).__name__:
            return {
                "success": False,
                "error": "Rollback is currently CSV-only — SQL down-migrations are not yet built.",
                "hint": "Restore from a database backup, or re-declare the prior schema and migrate forward.",
            }

        schema = orchestrator.schema or {}
        tables = ([specific_table] if specific_table
                  else [t for t in schema if t != _META_KEY])
        restored = 0

        try:
            from ..shared.backends.csv_helpers.file_operations import get_csv_path
        except ImportError:  # pragma: no cover
            from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends.csv_helpers.file_operations import get_csv_path  # type: ignore

        base_path = getattr(adapter, "base_path", None)
        for table in tables:
            migration_table = f"__zmigration_{table}"
            try:
                if not adapter.table_exists(migration_table):
                    continue
                rows = adapter.select(
                    migration_table,
                    where={"status": "success"},
                    order_by="applied_at DESC",
                    limit=1,
                )
                if not rows:
                    continue
                backup = rows[0].get("backup_location")
                if not backup or not Path(backup).exists():
                    self.logger.info(
                        f"[zRollback] No restorable backup for {table} — skipping"
                    )
                    continue
                shutil.copy2(backup, get_csv_path(base_path, table))
                # Force a reload from the restored file on next access.
                cache = getattr(adapter, "tables", {})
                cache.pop(table, None)
                restored += 1
                self.logger.info(f"[zRollback] Restored {table} from {backup}")
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning(f"[zRollback] Failed to restore {table}: {exc}")

        if getattr(self.zos, "display", None):
            self.zos.display.text(
                f"↩️  Rollback complete — restored {restored} table(s) from backup."
            )
        return {"success": True, "restored": restored}

    def get_migration_history(self, adapter: Any, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve migration execution history.
        
        Args:
            adapter: Backend adapter instance
            limit: Maximum number of records to return
            
        Returns:
            List of migration record dicts
        """
        if not adapter:
            raise RuntimeError(_ERROR_NO_ADAPTER)

        from zOS.L3_Abstraction.m_zData.zData_modules.shared.migration_history import (
            get_migration_history as _get_history
        )

        return _get_history(adapter, limit=limit)

    def _migration_not_enabled_error(self, schema_path: str) -> Dict[str, Any]:
        """Generate migration not enabled error response."""
        error_msg = (
            f"\n❌ Schema Migration Not Enabled!\n"
            f"   Schema: {schema_path}\n"
            f"   \n"
            f"   To enable migrations, add to Meta section:\n"
            f"   \n"
            f"   Meta:\n"
            f"     zMigration: true\n"
            f"     zMigrationVersion: \"v1.0.0\"\n"
            f"   \n"
            f"   This opt-in flag prevents accidental schema changes.\n"
        )
        self.logger.error(error_msg)

        # Display user-friendly error
        self.zos.display.text("", indent=0)
        self.zos.display.text("❌ Migration Blocked: zMigration not enabled", indent=0)
        self.zos.display.text("", indent=0)
        self.zos.display.text(f"Schema file: {schema_path}", indent=1)
        self.zos.display.text("", indent=0)
        self.zos.display.text("To enable migrations, add to Meta section:", indent=1)
        self.zos.display.text("", indent=0)
        self.zos.display.text("  Meta:", indent=1)
        self.zos.display.text("    zMigration: true", indent=1)
        self.zos.display.text("    zMigrationVersion: \"v1.0.0\"", indent=1)
        self.zos.display.text("", indent=0)
        self.zos.display.text("This opt-in flag prevents accidental schema changes.", indent=1)
        self.zos.display.text("", indent=0)

        return {
            "success": False,
            "error": "zMigration not enabled in schema",
            "hint": "Add 'zMigration: true' to Meta section"
        }

    def _get_last_applied_version(self, orchestrator: Any, new_schema: Dict[str, Any]) -> str:
        """
        Return the to_version of the last successful migration for the first
        user-defined table in the schema, so it can be stored as from_version
        in the new migration record.
        """
        try:
            first_table = next(
                (k for k in new_schema if k != _META_KEY), None
            )
            if not first_table:
                return ''
            migration_table = f"__zmigration_{first_table}"
            if not orchestrator.adapter.table_exists(migration_table):
                return ''
            rows = orchestrator.adapter.select(
                migration_table,
                where={'status': 'success'},
                order_by='applied_at DESC',
                limit=1,
            )
            if rows:
                return rows[0].get('to_version', '') or ''
        except Exception:  # pylint: disable=broad-except
            pass
        return ''

    def _introspect_database_schema(self, orchestrator: Any) -> Dict[str, Any]:
        """
        Introspect the ACTUAL current state of the data source.

        For CSV: reads column headers from the live .csv files so the diff
        engine sees what really exists on disk — not what the schema file says.
        For SQL/other: falls back to the loaded schema (placeholder until
        SQL introspection is implemented).
        """
        schema = orchestrator.schema or {}
        meta   = schema.get(_META_KEY, {})
        data_type = meta.get(_META_KEY_DATA_TYPE, "").upper()

        adapter = orchestrator.adapter

        if data_type == "CSV":
            introspected: Dict[str, Any] = {_META_KEY: meta}
            for table_name in schema:
                if table_name == _META_KEY:
                    continue
                try:
                    # A table whose data file doesn't exist yet is genuinely absent —
                    # omit it so the diff classifies it as a NEW table (tables_added →
                    # CREATE) rather than an existing table with 0 columns (which would
                    # try to ALTER a file that isn't there).
                    if hasattr(adapter, "table_exists") and not adapter.table_exists(table_name):
                        continue
                    live_cols = adapter.introspect_schema(table_name)
                    # introspect_schema returns {col: {type, ...}, ...} or similar
                    introspected[table_name] = live_cols if isinstance(live_cols, dict) else {}
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.debug(
                        f"[zMigrate] Could not introspect {table_name}: {exc} — treating as empty"
                    )
                    introspected[table_name] = {}
            return introspected

        # SQL backends: introspect the LIVE database (PRAGMA / information_schema),
        # then reconcile each column's type against the declared schema so lossy
        # affinities (bool↦INTEGER, datetime↦TEXT) never look like changes. This is
        # what makes SQL migrations diff against DB truth — drops and real type
        # changes on existing tables are now detected, not just brand-new tables.
        if hasattr(adapter, "introspect_schema"):
            from ..shared.backends.type_mapping import reconcile_live_types
            introspected = {_META_KEY: meta}
            for table_name in schema:
                if table_name == _META_KEY:
                    continue
                try:
                    if hasattr(adapter, "table_exists") and not adapter.table_exists(table_name):
                        continue
                    live_cols = adapter.introspect_schema(table_name) or {}
                    declared = schema.get(table_name, {})
                    declared_cols = declared if isinstance(declared, dict) else {}
                    reconciled = reconcile_live_types(
                        live_cols, declared_cols, adapter.map_type
                    )
                    # Attach the LIVE index names so the diff sees which declared
                    # indexes already exist (idempotent) and which live ones are no
                    # longer declared (DROP). Stored under the same key the converter
                    # lifts into Indexes.
                    if hasattr(adapter, "introspect_indexes"):
                        from ..shared.validators.constants import SCHEMA_KEY_INDEXES
                        live_idx = adapter.introspect_indexes(table_name) or []
                        if live_idx:
                            reconciled[SCHEMA_KEY_INDEXES] = live_idx
                    introspected[table_name] = reconciled
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.debug(
                        f"[zMigrate] Could not introspect {table_name}: {exc} — treating as empty"
                    )
                    introspected[table_name] = {}
            return introspected

        # Adapter without introspection: fall back to the loaded schema.
        return schema

    def _convert_zcli_to_diff_format(self, zcli_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert zCLI schema format to the diff engine format.

        zCLI format  (input):  {'zMeta': {...}, 'contacts': {'id': {...}, ..., 'indexes': [...]}}
        Diff format  (output): {'Tables': {'contacts': {'Columns': {'id': {...}, ...}, 'Indexes': [...]}}}

        Table-level ``indexes`` (declared specs on the new side, live names on the
        old/introspected side) is lifted OUT of the column map into its own ``Indexes``
        slot so the diff engine can compare it as indexes — not mistake it for a column.
        """
        from ..shared.validators.constants import SCHEMA_KEY_INDEXES, SCHEMA_KEY_CONSTRAINTS
        from ..shared.constraint_helpers import split_constraints
        tables: Dict[str, Any] = {}
        for key, value in zcli_schema.items():
            if key == _META_KEY:
                continue
            if isinstance(value, dict):
                columns = {k: v for k, v in value.items()
                           if k not in (SCHEMA_KEY_INDEXES, SCHEMA_KEY_CONSTRAINTS)}
                table_def: Dict[str, Any] = {"Columns": columns}
                indexes = list(value.get(SCHEMA_KEY_INDEXES, []) or [])
                # UNIQUE constraints ride the index pipeline; fk/check stay constraints.
                if SCHEMA_KEY_CONSTRAINTS in value:
                    unique_specs, others = split_constraints(value[SCHEMA_KEY_CONSTRAINTS])
                    indexes += unique_specs
                    if others:
                        table_def["Constraints"] = others
                if indexes:
                    table_def["Indexes"] = indexes
                tables[key] = table_def
        return {"Tables": tables}
