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

from zOS import Any, Dict

# Module Constants
_LOG_PREFIX = "[BackendMigration]"


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
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Handle a ``Data_Type`` change by moving all data to the new backend.

        Exports every declared user table off the CURRENT (old-backend) adapter,
        builds a fresh adapter for the target backend from ``new_schema`` (via the
        same ConnectionManager the runtime uses), replays the rows onto it, and
        validates row counts. The shared row model lives in ``backend_transfer``.

        The caller must pass an orchestrator still connected to the OLD backend
        (``orchestrator.adapter`` is the source of truth for the data being moved).

        Args:
            orchestrator: DataOrchestrator connected to the source backend.
            old_backend: Source backend type (e.g. "csv").
            new_backend: Target backend type (e.g. "sqlite").
            new_schema: Target schema (carries the new Data_Type + path/env).
            dry_run: If True, report what would move without writing anything.

        Returns:
            Dict with success + moved-table/row counts (or error).
        """
        self.logger.info(f"{_LOG_PREFIX} Backend migration: {old_backend} → {new_backend}")

        from .backend_transfer import preview_transfer, transfer_backend

        source_adapter = getattr(orchestrator, "adapter", None)
        if source_adapter is None:
            return {"success": False, "error": "No source adapter to export from"}

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

        report = transfer_backend(
            source_adapter, target_adapter, orchestrator.schema or {}, self.logger
        )

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
            **({"error": f"Row-count mismatch after transfer: {report['mismatches']}"}
               if not report["success"] else {}),
        }

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
