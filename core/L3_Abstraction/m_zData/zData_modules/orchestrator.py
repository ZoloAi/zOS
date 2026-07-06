# zOS/core/L3_Abstraction/m_zData/zData_modules/orchestrator.py
"""
DataOrchestrator - Core orchestration logic for zData subsystem.

Coordinates schema loading, connection management, request handling, and lifecycle
management for all data operations. Follows the facade orchestrator pattern used
by zBifrost.

Architecture:
    - Uses SchemaManager for schema loading and validation
    - Uses ConnectionManager for adapter initialization and connection lifecycle
    - Uses RequestHandler for operation routing and execution
    - Uses LifecycleManager for connection state management
    - Integrates with existing shared modules (adapters, validators, operations)

Responsibilities:
    - Initialize and coordinate all data subsystem components
    - Manage wizard mode vs one-shot mode connection strategies
    - Provide unified interface for zData facade
    - Handle errors gracefully with logging
"""

from zOS import Any, Dict, List, Optional

from .shared.data_keys import SCHEMA_KEY_META

# Module Constants
_LOG_PREFIX = "[DataOrchestrator]"
_LOG_INIT = "DataOrchestrator initialized"
_LOG_READY = "DataOrchestrator ready"
_ERROR_ZOS_NONE = "zos parameter cannot be None"
_ERROR_LOGGER_NONE = "logger parameter cannot be None"
_ERROR_SESSION_NONE = "session parameter cannot be None"


class DataOrchestrator:
    """
    Core orchestrator for zData subsystem.
    
    Coordinates all data operations by delegating to specialized managers:
    - SchemaManager: Schema loading and validation
    - ConnectionManager: Adapter initialization and connection lifecycle
    - RequestHandler: Request routing and operation execution
    - LifecycleManager: Connection state and cleanup
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance
        session: Session dict from zOS framework
        schema_manager: SchemaManager instance
        connection_manager: ConnectionManager instance
        request_handler: RequestHandler instance
        lifecycle_manager: LifecycleManager instance
    """

    def __init__(self, zos: Any, logger: Any, session: dict) -> None:
        """
        Initialize DataOrchestrator.
        
        Args:
            zos: zOS framework instance (required)
            logger: Logger instance (required)
            session: Session dict from zOS (required)
            
        Raises:
            ValueError: If zos, logger, or session is None
        """
        if zos is None:
            raise ValueError(_ERROR_ZOS_NONE)
        if logger is None:
            raise ValueError(_ERROR_LOGGER_NONE)
        if session is None:
            raise ValueError(_ERROR_SESSION_NONE)

        self.zos = zos
        self.logger = logger
        self.session = session

        self.logger.framework.debug(f"{_LOG_PREFIX} {_LOG_INIT}")

        # Initialize managers (lazy loading - will be created when needed)
        self.schema_manager: Optional[Any] = None
        self.connection_manager: Optional[Any] = None
        self.request_handler: Optional[Any] = None
        self.lifecycle_manager: Optional[Any] = None

        # State tracking
        self.schema: Optional[Dict[str, Any]] = None
        self.adapter: Optional[Any] = None
        self.validator: Optional[Any] = None
        self.operations: Optional[Any] = None
        self._connected: bool = False

        self.logger.framework.debug(f"{_LOG_PREFIX} {_LOG_READY}")

    def _ensure_managers(self) -> None:
        """
        Lazy initialization of manager instances.
        
        Creates manager instances on first use to avoid circular dependencies
        and improve startup performance.
        """
        if self.schema_manager is None:
            from .schema_manager import SchemaManager
            self.schema_manager = SchemaManager(self.zos, self.logger)

        if self.connection_manager is None:
            from .connection_manager import ConnectionManager
            self.connection_manager = ConnectionManager(self.zos, self.logger)

        if self.request_handler is None:
            from .request_handler import RequestHandler
            self.request_handler = RequestHandler(self.zos, self.logger)

        if self.lifecycle_manager is None:
            from .lifecycle_manager import LifecycleManager
            self.lifecycle_manager = LifecycleManager(self.logger)

    def handle_request(self, request: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Main entry point for all data operations.
        
        Delegates to RequestHandler after ensuring managers are initialized.
        
        Args:
            request: Request dictionary with model, action, options
            context: Optional context dictionary with wizard_mode, schema_cache
            
        Returns:
            Operation result from adapter or "error" string on failure
        """
        self._ensure_managers()
        return self.request_handler.handle_request(
            request=request,
            context=context,
            orchestrator=self
        )

    def load_schema(self, schema: Dict[str, Any]) -> None:
        """
        Load schema and initialize adapter/validator/operations.
        
        Delegates to SchemaManager and ConnectionManager.
        
        Args:
            schema: Schema dictionary with Meta section and table definitions
        """
        self._ensure_managers()

        # Store schema via SchemaManager
        self.schema = self.schema_manager.load_schema(schema)

        # Initialize adapter via ConnectionManager
        adapter_result = self.connection_manager.initialize_adapter(
            schema=self.schema,
            zos=self.zos
        )

        self.adapter = adapter_result['adapter']
        self.validator = adapter_result['validator']
        self._connected = adapter_result['connected']

        # Initialize operations facade with orchestrator reference
        self.operations = self.connection_manager.create_operations_facade(self)

    def is_connected(self) -> bool:
        """
        Check if adapter is connected.
        
        Returns:
            True if adapter is connected, False otherwise
        """
        return self._connected and self.adapter is not None

    def disconnect(self) -> None:
        """
        Disconnect from backend.
        
        Delegates to LifecycleManager for cleanup.
        """
        self._ensure_managers()
        self.lifecycle_manager.disconnect(self.adapter)
        self._connected = False

    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get connection information.
        
        Returns:
            Dict with connection details (backend, path, label, connected)
        """
        if not self.schema or not self.adapter:
            return {
                "backend": "none",
                "path": "N/A",
                "label": "N/A",
                "connected": False
            }

        meta = self.schema.get(SCHEMA_KEY_META, {})
        return {
            "backend": meta.get("Data_Type", "unknown"),
            "path": meta.get("Data_Path", "N/A"),
            "label": meta.get("Data_Label", "data"),
            "connected": self._connected
        }

    # ═══════════════════════════════════════════════════════════════════════════════
    # CRUD OPERATIONS (Delegate to operations facade)
    # ═══════════════════════════════════════════════════════════════════════════════

    def insert(self, table: str, fields: List[str], values: List[Any]) -> Any:
        """Insert rows into table. Delegates to operations facade."""
        if not self.operations:
            raise RuntimeError("No operations handler initialized")
        return self.operations.insert(table, fields, values)

    def select(self, table: str, fields: Optional[List[str]] = None, **kwargs: Any) -> List[Dict[str, Any]]:
        """Select rows from table. Delegates to operations facade."""
        if not self.operations:
            raise RuntimeError("No operations handler initialized")
        return self.operations.select(table, fields, **kwargs)

    def update(self, table: str, fields: List[str], values: List[Any], where: Any) -> Any:
        """Update rows in table. Delegates to operations facade."""
        if not self.operations:
            raise RuntimeError("No operations handler initialized")
        return self.operations.update(table, fields, values, where)

    def delete(self, table: str, where: Any) -> Any:
        """Delete rows from table. Delegates to operations facade."""
        if not self.operations:
            raise RuntimeError("No operations handler initialized")
        return self.operations.delete(table, where)

    def upsert(self, table: str, fields: List[str], values: List[Any], conflict_fields: List[str]) -> Any:
        """Upsert rows into table. Delegates to operations facade."""
        if not self.operations:
            raise RuntimeError("No operations handler initialized")
        return self.operations.upsert(table, fields, values, conflict_fields)

    def list_tables(self) -> List[str]:
        """List all tables. Delegates to operations facade."""
        if not self.operations:
            raise RuntimeError("No operations handler initialized")
        return self.operations.list_tables()

    # ═══════════════════════════════════════════════════════════════════════════════
    # DDL OPERATIONS (Delegate to adapter)
    # ═══════════════════════════════════════════════════════════════════════════════

    def create_table(self, table_name: str, schema: Optional[Dict[str, Any]] = None) -> Any:
        """Create table. Delegates to adapter."""
        if not self.adapter:
            raise RuntimeError("No adapter initialized")
        full_schema = schema or self.schema or {}
        # Extract table-level schema — callers may pass the full top-level schema
        table_schema = full_schema.get(table_name, full_schema)
        return self.adapter.create_table(table_name, table_schema)

    def drop_table(self, table_name: str) -> Any:
        """Drop table. Delegates to adapter."""
        if not self.adapter:
            raise RuntimeError("No adapter initialized")
        return self.adapter.drop_table(table_name)

    def alter_table(self, table_name: str, changes: Dict[str, Any]) -> Any:
        """Alter table. Delegates to adapter."""
        if not self.adapter:
            raise RuntimeError("No adapter initialized")
        return self.adapter.alter_table(table_name, changes)

    def table_exists(self, table_name: str) -> bool:
        """Check if table exists. Delegates to adapter."""
        if not self.adapter:
            raise RuntimeError("No adapter initialized")
        return self.adapter.table_exists(table_name)

    # ═══════════════════════════════════════════════════════════════════════════════
    # DCL OPERATIONS (Delegate to adapter)
    # ═══════════════════════════════════════════════════════════════════════════════

    def grant(self, privileges: str, table_name: str, user: str) -> Any:
        """Grant privileges. Delegates to adapter."""
        if not self.adapter:
            raise RuntimeError("No adapter initialized")
        return self.adapter.grant(privileges, table_name, user)

    def revoke(self, privileges: str, table_name: str, user: str) -> Any:
        """Revoke privileges. Delegates to adapter."""
        if not self.adapter:
            raise RuntimeError("No adapter initialized")
        return self.adapter.revoke(privileges, table_name, user)

    def list_privileges(self, table_name: Optional[str] = None, user: Optional[str] = None) -> List[Dict[str, Any]]:
        """List privileges. Delegates to adapter."""
        if not self.adapter:
            raise RuntimeError("No adapter initialized")
        return self.adapter.list_privileges(table_name, user)

    # ═══════════════════════════════════════════════════════════════════════════════
    # TCL OPERATIONS (Delegate to adapter)
    # ═══════════════════════════════════════════════════════════════════════════════

    def begin_transaction(self) -> Any:
        """Begin transaction. Delegates to adapter."""
        if not self.adapter:
            raise RuntimeError("No adapter initialized")
        return self.adapter.begin_transaction()

    def commit(self) -> Any:
        """Commit transaction. Delegates to adapter."""
        if not self.adapter:
            raise RuntimeError("No adapter initialized")
        return self.adapter.commit()

    def rollback(self) -> Any:
        """Rollback transaction. Delegates to adapter."""
        if not self.adapter:
            raise RuntimeError("No adapter initialized")
        return self.adapter.rollback()
