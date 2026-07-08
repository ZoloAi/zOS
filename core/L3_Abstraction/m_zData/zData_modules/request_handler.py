# zOS/core/L3_Abstraction/m_zData/zData_modules/request_handler.py
"""
RequestHandler - Request routing and operation execution.

Handles all request processing including:
- Request validation and preprocessing
- Schema initialization (wizard mode vs one-shot mode)
- Connection validation
- Operation routing via DataOperations
- Connection lifecycle management

Architecture:
    - Coordinates SchemaManager for schema loading
    - Coordinates ConnectionManager for adapter initialization
    - Integrates with DataOperations for operation execution
    - Manages wizard mode vs one-shot mode connection strategies
"""

from zOS import Any, Dict, Optional

from .shared.data_keys import (
    KEY_ACTION as _REQUEST_KEY_ACTION,
    KEY_MODEL as _REQUEST_KEY_MODEL,
    KEY_OPTIONS as _REQUEST_KEY_OPTIONS,
    KEY_TABLES as _REQUEST_KEY_TABLES,
    SCHEMA_KEY_META as _RESERVED_KEY_META,
    SCHEMA_KEY_DB_PATH as _RESERVED_KEY_DB_PATH,
)

# Module Constants
_LOG_PREFIX = "[RequestHandler]"

# Option keys (zData-specific request-shape options)
_OPTION_KEY_SCHEMA_CACHED = "_schema_cached"
_OPTION_KEY_ALIAS_NAME = "_alias_name"
_OPTION_KEY_TABLES = _REQUEST_KEY_TABLES
_OPTION_VALUE_ALL_TABLES = "all"

# Context keys
_CONTEXT_KEY_WIZARD_MODE = "wizard_mode"
_CONTEXT_KEY_SCHEMA_CACHE = "schema_cache"

# Return values
_RESULT_ERROR = "error"

# Display constants
_COLOR_ZCRUD = "ZCRUD"
_DECLARE_ZDATA_REQUEST = "zData Request"
_DISPLAY_STYLE_FULL = "full"

# Error messages
_ERROR_FAILED_CONNECT = "Failed to connect to backend"
_ERROR_NO_SCHEMA_PROVIDED = "No schema provided (model path or cached schema required)"

# Log messages
_LOG_ERROR_EXECUTING_REQUEST = "Error executing request: %s"
_LOG_DISCONNECTED_ONE_SHOT = "Disconnected (one-shot mode)"
_LOG_CONNECTION_KEPT_ALIVE = "Connection kept alive (wizard mode)"
_LOG_CREATED_PERSISTENT = "[CONNECT] Created persistent connection for $%s"


class RequestHandler:
    """
    Handles request routing and operation execution.
    
    Responsibilities:
        - Validate and preprocess requests
        - Initialize schema and adapter (wizard mode vs one-shot mode)
        - Route operations to DataOperations facade
        - Manage connection lifecycle
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance
        display: zDisplay instance (from zos)
    """

    def __init__(self, zos: Any, logger: Any) -> None:
        """
        Initialize RequestHandler.
        
        Args:
            zos: zOS framework instance
            logger: Logger instance
        """
        self.zos = zos
        self.logger = logger
        self.display = zos.display

    def handle_request(
        self,
        request: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        orchestrator: Any
    ) -> Any:
        """
        Main entry point for all data operations.
        
        Args:
            request: Request dictionary with model, action, options
            context: Optional context dictionary with wizard_mode, schema_cache
            orchestrator: DataOrchestrator instance
            
        Returns:
            Operation result from adapter or "error" string on failure
        """
        # PHASE 1: Announce request (skip if silent mode)
        silent = request.get("silent", False)
        if not silent:
            self.display.zDeclare(
                _DECLARE_ZDATA_REQUEST,
                color=_COLOR_ZCRUD,
                indent=1,
                style=_DISPLAY_STYLE_FULL
            )

        # PHASE 2: Extract wizard mode flag
        wizard_mode = context.get(_CONTEXT_KEY_WIZARD_MODE, False) if context else False

        # PHASE 3: Initialize schema and adapter
        if not self._initialize_handler(request, context, orchestrator):
            return _RESULT_ERROR

        # PHASE 4: Validate connection
        if not orchestrator.is_connected():
            self.logger.error(_ERROR_FAILED_CONNECT)
            return _RESULT_ERROR

        # PHASE 5: Preprocess request (parse tables option)
        self._preprocess_request(request, orchestrator)

        action = request.get(_REQUEST_KEY_ACTION)

        # PHASE 5.5: Authoritative access control (zRBAC) — fail-closed.
        # The wizard/dispatch RBAC gates are presentational; this is the data
        # layer's own re-check before any declarative request reads or mutates,
        # closing the Bifrost gate-continuation gap. Schemas without a zRBAC
        # block are unaffected (public, zero auth calls).
        from .shared.access_guard import enforce_access  # pylint: disable=import-outside-toplevel
        if not enforce_access(request, action, orchestrator, self.zos, self.logger):
            return _RESULT_ERROR

        # PHASE 6: Ensure tables exist (for operations that require tables)
        tables = request.get(_REQUEST_KEY_TABLES, [])
        if not orchestrator.operations.ensure_tables_for_action(action, tables):
            return _RESULT_ERROR

        # PHASE 7: Delegate to operation handlers
        try:
            result = orchestrator.operations.route_action(action, request)
        except Exception as e:  # pylint: disable=broad-except
            self.logger.error(_LOG_ERROR_EXECUTING_REQUEST, e, exc_info=True)
            result = _RESULT_ERROR
        finally:
            # PHASE 8: Manage connection lifecycle
            if not wizard_mode:
                orchestrator.disconnect()
                self.logger.debug(_LOG_DISCONNECTED_ONE_SHOT)
            else:
                self.logger.debug(_LOG_CONNECTION_KEPT_ALIVE)

        return result

    def _initialize_handler(
        self,
        request: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        orchestrator: Any
    ) -> bool:
        """
        Initialize schema and adapter with connection reuse support.
        
        Args:
            request: Request dictionary with model/options
            context: Context dictionary with wizard_mode/schema_cache
            orchestrator: DataOrchestrator instance
            
        Returns:
            True if initialization succeeded, False otherwise
        """
        # Extract context parameters
        schema_cache = context.get(_CONTEXT_KEY_SCHEMA_CACHE) if context else None
        wizard_mode = context.get(_CONTEXT_KEY_WIZARD_MODE, False) if context else False

        # Extract request options
        options = request.get(_REQUEST_KEY_OPTIONS, {})
        cached_schema = options.get(_OPTION_KEY_SCHEMA_CACHED)
        alias_name = options.get(_OPTION_KEY_ALIAS_NAME)

        # Auto-detect $alias from model field when not explicitly set in options.
        # Handles the walker/dispatch path (e.g. _handle_data_dict) which passes the
        # raw zData dict without pre-processing the $prefix into _alias_name.
        if not alias_name:
            raw_model = request.get(_REQUEST_KEY_MODEL, "")
            if isinstance(raw_model, str) and raw_model.startswith("$"):
                alias_name = raw_model[1:]  # strip $ prefix
                request[_REQUEST_KEY_MODEL] = None  # clear model so it doesn't fall through

        # Import managers
        from .schema_manager import SchemaManager
        schema_manager = SchemaManager(self.zos, self.logger)

        # Wizard mode with connection reuse
        if wizard_mode and schema_cache and alias_name:
            return self._init_wizard_handler(
                schema_cache,
                alias_name,
                cached_schema,
                orchestrator,
                schema_manager
            )

        # One-shot mode with cached schema
        if cached_schema and alias_name:
            schema = schema_manager.load_schema(cached_schema)
            orchestrator.load_schema(schema)
            return True

        # Load schema from model path
        model_path = request.get(_REQUEST_KEY_MODEL)

        # CTE fallback: outer request uses `from: <cte_name>` with no top-level model.
        # Infer the schema from the first with-block sub-request that has a model key.
        if not model_path:
            with_block = request.get('with')
            if isinstance(with_block, dict):
                for sub_req in with_block.values():
                    if isinstance(sub_req, dict) and sub_req.get(_REQUEST_KEY_MODEL):
                        model_path = sub_req[_REQUEST_KEY_MODEL]
                        break

        # SET fallback: action: set uses `queries: {q1: {model: ...}, ...}` (or list).
        # Infer the schema from the first query entry that has a model key.
        if not model_path:
            queries_raw = request.get('queries')
            if isinstance(queries_raw, dict):
                queries_iter = queries_raw.values()
            elif isinstance(queries_raw, list):
                queries_iter = queries_raw
            else:
                queries_iter = []
            for q in queries_iter:
                if isinstance(q, dict) and q.get(_REQUEST_KEY_MODEL):
                    model_path = q[_REQUEST_KEY_MODEL]
                    break

        if not model_path:
            self.logger.error(_ERROR_NO_SCHEMA_PROVIDED)
            return False

        schema = schema_manager.load_schema_from_path(model_path)

        # Cross-file multi-table request (tables: [...] + auto_join, etc.) — the
        # `model:` file only carries ITS OWN table(s); backfill any others named
        # in `tables:` from the server-wide registry (see enrich_with_tables).
        schema = schema_manager.enrich_with_tables(schema, request.get(_REQUEST_KEY_TABLES))

        orchestrator.load_schema(schema)
        return bool(orchestrator.adapter)

    def _init_wizard_handler(
        self,
        schema_cache: Any,
        alias_name: str,
        cached_schema: Optional[Dict[str, Any]],
        orchestrator: Any,
        schema_manager: Any
    ) -> bool:
        """
        Initialize handler for wizard mode with connection reuse.
        
        Args:
            schema_cache: SchemaCache instance
            alias_name: Alias name for connection
            cached_schema: Optional cached schema dictionary
            orchestrator: DataOrchestrator instance
            schema_manager: SchemaManager instance
            
        Returns:
            True if initialization succeeded, False otherwise
        """
        # Check if connection already exists (reuse)
        existing_handler = schema_cache.get_connection(alias_name)
        if existing_handler:
            # Reuse existing adapter/validator/operations
            orchestrator.adapter = existing_handler.adapter
            orchestrator.validator = existing_handler.validator
            orchestrator.operations = existing_handler.operations
            orchestrator.schema = existing_handler.schema
            orchestrator._connected = existing_handler._connected  # pylint: disable=protected-access
            return True

        # First use in wizard - load schema and store connection
        schema, _ = schema_manager.load_wizard_schema(
            schema_cache,
            alias_name,
            cached_schema
        )

        orchestrator.load_schema(schema)
        schema_cache.set_connection(alias_name, orchestrator)
        self.logger.info(_LOG_CREATED_PERSISTENT, alias_name)
        return True

    def _preprocess_request(self, request: Dict[str, Any], orchestrator: Any) -> None:
        """
        Preprocess request - parse tables option.
        
        Args:
            request: Request dictionary (modified in-place)
            orchestrator: DataOrchestrator instance
        """
        options = request.get(_REQUEST_KEY_OPTIONS, {})
        tables_option = options.get(_OPTION_KEY_TABLES)

        if not tables_option:
            return

        # Parse "all" or comma-separated list
        if tables_option == _OPTION_VALUE_ALL_TABLES:
            # Get all tables from schema (exclude Meta and reserved keys)
            if orchestrator.schema:
                tables = [
                    k for k in orchestrator.schema.keys()
                    if k not in (_RESERVED_KEY_META, _RESERVED_KEY_DB_PATH)
                ]
                request[_REQUEST_KEY_TABLES] = tables
        elif isinstance(tables_option, str):
            # Split comma-separated list
            tables = [t.strip() for t in tables_option.split(",")]
            request[_REQUEST_KEY_TABLES] = tables
