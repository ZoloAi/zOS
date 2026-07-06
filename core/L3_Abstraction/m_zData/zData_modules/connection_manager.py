# zOS/core/L3_Abstraction/m_zData/zData_modules/connection_manager.py
"""
ConnectionManager - Adapter initialization and connection lifecycle.

Handles all connection-related operations including:
- Adapter initialization via AdapterFactory
- Connection establishment and validation
- Validator initialization
- Operations facade initialization
- Storage quota management

Architecture:
    - Uses AdapterFactory to create backend-specific adapters
    - Integrates with DataValidator for schema validation
    - Integrates with DataOperations for operation routing
    - Manages connection state and lifecycle
"""

from zOS import Any, Dict
from ..zData_modules.shared.backends.adapter_factory import AdapterFactory
from ..zData_modules.shared.validator import DataValidator
from ..zData_modules.shared.data_operations import DataOperations
from .shared.data_keys import SCHEMA_KEY_META

# Module Constants
_LOG_PREFIX = "[ConnectionManager]"
_META_KEY = SCHEMA_KEY_META
_META_KEY_DATA_TYPE = "Data_Type"
_META_KEY_DATA_LABEL = "Data_Label"
_META_DEFAULT_LABEL = "data"
_RESERVED_KEY_META = SCHEMA_KEY_META

# Error messages
_ERROR_NO_SCHEMA = "Cannot initialize adapter without schema"
_ERROR_FAILED_INITIALIZE = "Failed to initialize adapter: {error}"

# Log messages
_LOG_INITIALIZING_ADAPTER = "Initializing %s adapter for: %s (label: %s)"
_LOG_CONNECTED_BACKEND = "[OK] Connected to %s backend: %s"


class ConnectionManager:
    """
    Manages adapter initialization and connection lifecycle.
    
    Responsibilities:
        - Initialize adapters via AdapterFactory
        - Establish database connections
        - Initialize validators with schema
        - Initialize operations facade
        - Manage storage quota
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance
    """

    def __init__(self, zos: Any, logger: Any) -> None:
        """
        Initialize ConnectionManager.
        
        Args:
            zos: zOS framework instance
            logger: Logger instance
        """
        self.zos = zos
        self.logger = logger

    def initialize_adapter(
        self,
        schema: Dict[str, Any],
        zos: Any
    ) -> Dict[str, Any]:
        """
        Initialize adapter, validator, and operations facade.
        
        Args:
            schema: Schema dictionary with Meta section
            zos: zOS framework instance
            
        Returns:
            Dict with:
                - adapter: Backend adapter instance
                - validator: DataValidator instance
                - operations: DataOperations instance
                - connected: Connection state (bool)
                - storage_quota: StorageQuotaManager instance
                
        Raises:
            ValueError: If schema is None or Meta missing required fields
            Exception: If adapter creation or connection fails
        """
        if not schema:
            self.logger.error(_ERROR_NO_SCHEMA)
            raise ValueError(_ERROR_NO_SCHEMA)

        # Extract Meta configuration
        meta = schema.get(_META_KEY, {})
        data_type = meta[_META_KEY_DATA_TYPE]
        data_label = meta.get(_META_KEY_DATA_LABEL, _META_DEFAULT_LABEL)

        # Resolve data path via SchemaManager
        from .schema_manager import SchemaManager
        schema_manager = SchemaManager(zos, self.logger)
        data_path, _ = schema_manager.resolve_data_path(schema)

        self.logger.debug(_LOG_INITIALIZING_ADAPTER, data_type, data_path, data_label)

        # Set logger for factory
        AdapterFactory.set_logger(self.logger)

        # Create adapter
        try:
            adapter = AdapterFactory.create_adapter(data_type, {
                "path": data_path,
                "label": data_label,
                "meta": meta
            })

            # Connect
            adapter.connect()
            connected = True
            self.logger.debug(_LOG_CONNECTED_BACKEND, data_type, data_path)

            # Initialize validator with schema tables (exclude Meta)
            schema_tables = {k: v for k, v in schema.items() if k != _RESERVED_KEY_META}

            # Make the adapter type-aware for EVERY schema table up front. Without
            # this, on-disk tables (never create_table'd) read schema-less and leak
            # nullable int columns as float64 ("2.0"). No-op on SQL backends.
            for table_name, table_schema in schema_tables.items():
                if isinstance(table_schema, dict):
                    adapter.register_schema(table_name, table_schema)
            validator = DataValidator(schema_tables, logger=self.logger, zos=zos)

            # Initialize operations facade (placeholder - will receive orchestrator reference)
            operations = None  # Will be set by orchestrator

            # Initialize storage quota manager
            from ..zData_modules.shared.storage_quota import StorageQuotaManager

            # Create temporary handler object for StorageQuotaManager
            class TempHandler:
                """Temporary handler for StorageQuotaManager initialization."""
                def __init__(self, adapter_inst, schema_inst, logger_inst):
                    self.adapter = adapter_inst
                    self.schema = schema_inst
                    self.logger = logger_inst

            temp_handler = TempHandler(adapter, schema, self.logger)
            storage_quota = StorageQuotaManager(temp_handler)

            return {
                'adapter': adapter,
                'validator': validator,
                'operations': operations,
                'connected': connected,
                'storage_quota': storage_quota
            }

        except Exception as e:
            self.logger.error(_ERROR_FAILED_INITIALIZE.format(error=e))
            raise

    def create_operations_facade(self, orchestrator: Any) -> Any:
        """
        Create DataOperations facade with orchestrator reference.
        
        Args:
            orchestrator: DataOrchestrator instance
            
        Returns:
            DataOperations instance
        """
        return DataOperations(orchestrator)
