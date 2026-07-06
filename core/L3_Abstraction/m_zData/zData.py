# zOS/core/L3_Abstraction/m_zData/zData.py
"""
zData - Unified Data Management Facade (Layer 3)

Lightweight facade orchestrator for all data operations in zOS, following
the zBifrost pattern. Delegates to DataOrchestrator for all heavy lifting.

Architecture:
    zData Facade (this file) - ~300 lines
      ├── Delegates to DataOrchestrator
      ├── Provides public API compatibility
      └── Announces readiness via zDisplay
    
    DataOrchestrator (zData_modules/orchestrator.py)
      ├── SchemaManager: Schema loading and validation
      ├── ConnectionManager: Adapter initialization
      ├── RequestHandler: Request routing
      ├── LifecycleManager: Connection cleanup
      └── MigrationEngine: Schema migrations

Supported Operations:
    CRUD: insert, select, update, delete, upsert, list_tables
    DDL: create_table, drop_table, alter_table, table_exists
    DCL: grant, revoke, list_privileges (PostgreSQL/MySQL only)
    TCL: begin_transaction, commit, rollback
    Migration: migrate, discover_schemas, migrate_app, cli_migrate
    File: open_schema, open_csv

Usage:
    # One-shot mode
    zdata = zData(zos)
    request = {"model": "@.zSchema.users", "action": "read"}
    result = zdata.handle_request(request)
    
    # Wizard mode
    context = {"wizard_mode": True, "schema_cache": cache}
    zdata.handle_request(request, context)
"""

from zOS import Any, Dict, List, Optional

from .zData_modules.shared.data_keys import SCHEMA_KEY_META

# Module Constants
_LOG_PREFIX = "[zData]"
_COLOR_ZDATA = "ZDATA"
_DISPLAY_STYLE_FULL = "full"
_DECLARE_ZDATA_READY = "zData Ready"
_ERROR_NO_ZOS_INSTANCE = "zData requires a zOS framework instance"
_ERROR_NO_SESSION_ATTR = "Invalid zOS instance: missing 'session' attribute"

__all__ = ["zData"]


class zData:
    """
    zData Facade - Lightweight orchestrator for data operations.
    
    Delegates all operations to DataOrchestrator while maintaining
    backward compatibility with existing API.
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance
        display: zDisplay instance
        orchestrator: DataOrchestrator instance
    """

    def __init__(self, zos: Any) -> None:
        """
        Initialize zData facade.
        
        Args:
            zos: zOS framework instance
            
        Raises:
            ValueError: If zos is None or missing 'session' attribute
        """
        if zos is None:
            raise ValueError(_ERROR_NO_ZOS_INSTANCE)
        if not hasattr(zos, 'session'):
            raise ValueError(_ERROR_NO_SESSION_ATTR)

        self.zos = zos
        self.logger = zos.logger
        self.display = zos.display

        # Initialize orchestrator (pandas is optional — CSV backend only)
        try:
            from .zData_modules.orchestrator import DataOrchestrator  # pylint: disable=import-outside-toplevel
            self.orchestrator = DataOrchestrator(
                zos=zos,
                logger=self.logger,
                session=zos.session
            )
        except ImportError as exc:
            if "pandas" in str(exc):
                self.orchestrator = None
                self.logger.warning(
                    "zData CSV backend unavailable (pandas not installed). "
                    "Install with: pip install zos[csv]"
                )
            else:
                raise

        # Announce readiness
        self.display.zDeclare(
            _DECLARE_ZDATA_READY,
            color=_COLOR_ZDATA,
            indent=0,
            style=_DISPLAY_STYLE_FULL
        )

    # ═══════════════════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ═══════════════════════════════════════════════════════════════════════════════

    def handle_request(self, request: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """Main entry point for all data operations. Delegates to orchestrator."""
        return self.orchestrator.handle_request(request, context)

    # ═══════════════════════════════════════════════════════════════════════════════
    # SCHEMA & CONNECTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════════

    def load_schema(self, schema: Dict[str, Any]) -> None:
        """Load schema and initialize adapter. Delegates to orchestrator."""
        self.orchestrator.load_schema(schema)

    def is_connected(self) -> bool:
        """Check if adapter is connected. Delegates to orchestrator."""
        return self.orchestrator.is_connected()

    def disconnect(self) -> None:
        """Disconnect from backend. Delegates to orchestrator."""
        self.orchestrator.disconnect()

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information. Delegates to orchestrator."""
        return self.orchestrator.get_connection_info()

    # ═══════════════════════════════════════════════════════════════════════════════
    # PROPERTY ACCESSORS (for backward compatibility)
    # ═══════════════════════════════════════════════════════════════════════════════

    @property
    def schema(self) -> Optional[Dict[str, Any]]:
        """Get current schema."""
        return self.orchestrator.schema

    @property
    def adapter(self) -> Optional[Any]:
        """Get current adapter."""
        return self.orchestrator.adapter

    @property
    def validator(self) -> Optional[Any]:
        """Get current validator."""
        return self.orchestrator.validator

    @property
    def operations(self) -> Optional[Any]:
        """Get current operations facade."""
        return self.orchestrator.operations

    @property
    def loader(self) -> Any:
        """Get zLoader instance."""
        return self.zos.loader

    @property
    def open(self) -> Any:
        """Get zOpen instance."""
        return self.zos.open

    @property
    def mycolor(self) -> str:
        """Get zDisplay color code."""
        return _COLOR_ZDATA

    # ═══════════════════════════════════════════════════════════════════════════════
    # CRUD OPERATIONS (Delegate to orchestrator)
    # ═══════════════════════════════════════════════════════════════════════════════

    def insert(self, table: str, fields: List[str], values: List[Any]) -> Any:
        """Insert rows into table."""
        return self.orchestrator.insert(table, fields, values)

    def select(self, table: str, fields: Optional[List[str]] = None, **kwargs: Any) -> List[Dict[str, Any]]:
        """Select rows from table."""
        return self.orchestrator.select(table, fields, **kwargs)

    def update(self, table: str, fields: List[str], values: List[Any], where: Any) -> Any:
        """Update rows in table."""
        return self.orchestrator.update(table, fields, values, where)

    def delete(self, table: str, where: Any) -> Any:
        """Delete rows from table."""
        return self.orchestrator.delete(table, where)

    def upsert(self, table: str, fields: List[str], values: List[Any], conflict_fields: List[str]) -> Any:
        """Upsert rows into table."""
        return self.orchestrator.upsert(table, fields, values, conflict_fields)

    def list_tables(self) -> List[str]:
        """List all tables."""
        return self.orchestrator.list_tables()

    # ═══════════════════════════════════════════════════════════════════════════════
    # DDL OPERATIONS (Delegate to orchestrator)
    # ═══════════════════════════════════════════════════════════════════════════════

    def create_table(self, table_name: str, schema: Optional[Dict[str, Any]] = None) -> Any:
        """Create table."""
        return self.orchestrator.create_table(table_name, schema)

    def drop_table(self, table_name: str) -> Any:
        """Drop table."""
        return self.orchestrator.drop_table(table_name)

    def alter_table(self, table_name: str, changes: Dict[str, Any]) -> Any:
        """Alter table."""
        return self.orchestrator.alter_table(table_name, changes)

    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        return self.orchestrator.table_exists(table_name)

    # ═══════════════════════════════════════════════════════════════════════════════
    # DCL OPERATIONS (Delegate to orchestrator)
    # ═══════════════════════════════════════════════════════════════════════════════

    def grant(self, privileges: str, table_name: str, user: str) -> Any:
        """Grant privileges."""
        return self.orchestrator.grant(privileges, table_name, user)

    def revoke(self, privileges: str, table_name: str, user: str) -> Any:
        """Revoke privileges."""
        return self.orchestrator.revoke(privileges, table_name, user)

    def list_privileges(self, table_name: Optional[str] = None, user: Optional[str] = None) -> List[Dict[str, Any]]:
        """List privileges."""
        return self.orchestrator.list_privileges(table_name, user)

    # ═══════════════════════════════════════════════════════════════════════════════
    # TCL OPERATIONS (Delegate to orchestrator)
    # ═══════════════════════════════════════════════════════════════════════════════

    def begin_transaction(self) -> Any:
        """Begin transaction."""
        return self.orchestrator.begin_transaction()

    def commit(self) -> Any:
        """Commit transaction."""
        return self.orchestrator.commit()

    def rollback(self) -> Any:
        """Rollback transaction."""
        return self.orchestrator.rollback()

    # ═══════════════════════════════════════════════════════════════════════════════
    # MIGRATION OPERATIONS (Delegate to migration modules)
    # ═══════════════════════════════════════════════════════════════════════════════

    def migrate(
        self,
        new_schema_path: str,
        dry_run: bool = False,
        auto_approve: bool = False,
        schema_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute declarative schema migration."""
        from .zData_modules.migration import MigrationEngine
        migration_engine = MigrationEngine(self.zos, self.logger)
        return migration_engine.migrate(
            orchestrator=self.orchestrator,
            new_schema_path=new_schema_path,
            dry_run=dry_run,
            auto_approve=auto_approve,
            schema_version=schema_version
        )

    def get_migration_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve migration execution history."""
        from .zData_modules.migration import MigrationEngine
        migration_engine = MigrationEngine(self.zos, self.logger)
        return migration_engine.get_migration_history(self.orchestrator.adapter, limit)

    def discover_schemas(self) -> List[Dict[str, Any]]:
        """Discover all schemas with zMigration enabled."""
        from .zData_modules.migration import SchemaDiscovery
        schema_discovery = SchemaDiscovery(self.zos, self.logger)
        return schema_discovery.discover_schemas()

    def migrate_app(
        self,
        app_file: Optional[str] = None,
        auto_approve: bool = False,
        dry_run: bool = False,
        specific_schema: Optional[str] = None,
        force_version: Optional[str] = None,
        plan: bool = False,
        rollback: bool = False
    ) -> Dict[str, Any]:
        """Execute migrations for all schemas in an application."""
        from .zData_modules.migration import SchemaDiscovery
        schema_discovery = SchemaDiscovery(self.zos, self.logger)
        return schema_discovery.migrate_app(
            orchestrator=self.orchestrator,
            _app_file=app_file,
            auto_approve=auto_approve,
            dry_run=dry_run,
            specific_schema=specific_schema,
            force_version=force_version,
            plan=plan,
            rollback=rollback
        )

    def cli_migrate(
        self,
        app_file: Optional[str] = None,
        auto_approve: bool = False,
        dry_run: bool = False,
        specific_schema: Optional[str] = None,
        force_version: Optional[str] = None,
        plan: bool = False,
        rollback: bool = False
    ) -> int:
        """CLI entry point for migrations with full user experience."""
        # Import CLI migration handler
        # This is a placeholder - full implementation would include display formatting
        result = self.migrate_app(
            app_file=app_file,
            auto_approve=auto_approve,
            dry_run=dry_run,
            specific_schema=specific_schema,
            force_version=force_version,
            plan=plan,
            rollback=rollback
        )

        # Return exit code (0 = success, 1 = failure)
        return 0 if result.get('failed', 0) == 0 else 1

    # ═══════════════════════════════════════════════════════════════════════════════
    # FILE OPERATIONS (zOpen integration)
    # ═══════════════════════════════════════════════════════════════════════════════

    def open_schema(self, schema_path: Optional[str] = None) -> Any:
        """Open schema YAML file in editor."""
        if not hasattr(self.zos, 'open'):
            self.logger.error("zOpen not available")
            return "error"

        # Use schema path from current schema if not provided
        if not schema_path and self.orchestrator.schema:
            meta = self.orchestrator.schema.get(SCHEMA_KEY_META, {})
            schema_path = meta.get("zVaFiles")

        if not schema_path:
            self.logger.error("No schema path available")
            return "error"

        self.logger.info(f"Opening schema file: {schema_path}")
        return self.zos.open.handle(schema_path)

    def open_csv(self, table_name: Optional[str] = None) -> Any:
        """Open CSV data file in editor."""
        if not hasattr(self.zos, 'open'):
            self.logger.error("zOpen not available")
            return "error"

        if not self.orchestrator.adapter:
            self.logger.error("No adapter initialized")
            return "error"

        # Check if adapter supports CSV operations
        if not hasattr(self.orchestrator.adapter, 'get_csv_path'):
            self.logger.error("CSV operations not supported for this adapter")
            return "error"

        # Get CSV file path from adapter
        csv_path = self.orchestrator.adapter.get_csv_path(table_name)
        if not csv_path:
            self.logger.error("No CSV file path available")
            return "error"

        self.logger.info(f"Opening CSV file: {csv_path}")
        return self.zos.open.handle(csv_path)
