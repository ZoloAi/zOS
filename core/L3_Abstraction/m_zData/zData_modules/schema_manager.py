# zOS/core/L3_Abstraction/m_zData/zData_modules/schema_manager.py
"""
SchemaManager - Schema loading, validation, and caching.

Handles all schema-related operations including:
- Loading schemas from zPath via zLoader
- Schema validation and Meta section parsing
- Wizard mode schema caching
- Schema name extraction and error context
- Environment variable resolution for Data_Path (security)

Architecture:
    - Integrates with zLoader for schema file loading
    - Validates Meta section for required fields
    - Manages schema cache for wizard mode
    - Provides schema context for error messages
"""

from zSys.errors import SchemaNotFoundError  # pylint: disable=import-error

from zOS import Any, Dict, Optional, Tuple, os

from zOS.zVocabulary import FILE_TYPE_SCHEMA, PATH_SYMBOL_AT, PATH_SYMBOL_TILDE

from .shared.data_keys import SCHEMA_KEY_META, SCHEMA_KEY_DB_PATH

# Module Constants
_LOG_PREFIX = "[SchemaManager]"
_META_KEY = SCHEMA_KEY_META
_META_KEY_DATA_TYPE = "Data_Type"
_META_KEY_DATA_PATH = "Data_Path"
_META_KEY_DATA_SOURCE = "Data_Source"
_META_KEY_DATA_LABEL = "Data_Label"
_META_KEY_SCHEMA_NAME = "Schema_Name"
_META_KEY_ZVAFILES = "zVaFiles"
_META_DEFAULT_LABEL = "data"

# Environment variable naming convention
_ENV_VAR_PREFIX = "ZDATA_"
_ENV_VAR_SUFFIX = "_URL"

# Reserved keys (SSOT: shared/data_keys)
_RESERVED_KEY_META = SCHEMA_KEY_META
_RESERVED_KEY_DB_PATH = SCHEMA_KEY_DB_PATH

# Field-key aliases: readable long-form a user may write → the canonical key the
# engine actually reads. Normalized once here at load so every downstream consumer
# (DDL FK clause, on_delete scan, schema_diff, validator) sees the canonical form.
_FIELD_KEY_ALIASES = {"foreign_key": "fk"}

# Error messages
_ERROR_NO_SCHEMA_PROVIDED = "No schema provided (model path or cached schema required)"
_ERROR_SCHEMA_LOAD_FAILED = "Failed to load schema from: {path}"
_ERROR_NO_CACHED_SCHEMA = "No cached schema for first-time connection: ${alias}"

# Log messages (registry bootstrap)
_LOG_REGISTRY_REGISTERED = "[Registry] Registered table '%s' from schema '%s'"
_LOG_REGISTRY_FALLBACK = "[Registry] Bootstrap fallback: resolved $%s from server schema registry"
_LOG_REGISTRY_MISS = "[Registry] No server-registered schema found for alias: $%s"
_ERROR_MISSING_META_FIELD = "Schema Meta missing required field: '{field}'"
_ERROR_NO_DATA_CONNECTION = "No database connection info found. Use Data_Source (env var) or Data_Path in schema Meta."

# Security messages
_SECURITY_WARNING_DATA_PATH_IN_SCHEMA = (
    "[SECURITY] Data_Path found in schema file. "
    "Move credentials to .zEnv using Data_Source pattern!"
)
_SECURITY_INFO_LOADED_FROM_ENV = "[SECURITY] Loaded Data_Path from environment: {env_var}"
_SECURITY_INFO_AUTO_CONVENTION = "[SECURITY] Auto-loaded connection from .zEnv using convention: {env_var}"

# Log messages
_LOG_LOADING_SCHEMA = "Loading schema from: %s"
_LOG_USING_CACHED_SCHEMA = "Using cached schema from alias: $%s"
_LOG_LOADING_FROM_PINNED = "[LOAD] Loading schema from pinned_cache: $%s"
_LOG_REUSING_CONNECTION = "[REUSE] Reusing connection for $%s"
_LOG_CREATED_PERSISTENT = "[CONNECT] Created persistent connection for $%s"

# Hints
_HINT_USE_LOAD_COMMAND = "Hint: Use 'load @data.%s' or provide model path directly"

# Misc
_SCHEMA_PATH_SEPARATOR = "."
# zPath prefixes (SSOT: zVocabulary path symbols + the path separator)
_PREFIX_AT = PATH_SYMBOL_AT + _SCHEMA_PATH_SEPARATOR        # "@."
_PREFIX_TILDE = PATH_SYMBOL_TILDE + _SCHEMA_PATH_SEPARATOR  # "~."
_SCHEMA_NAME_FALLBACK = "unknown"
_RESULT_ERROR = "error"


def parse_schema_model_path(model_path: str) -> Tuple[str, Optional[str]]:
    """
    Parse a schema model zPath, extracting the block/table name when present.

    Follows the same convention as zUI paths where the last segment is the block:
        @.models.Demos.zSchema.basic.demo_basic  →  ('@.models.Demos.zSchema.basic', 'demo_basic')
        @.models.Demos.zSchema.basic             →  ('@.models.Demos.zSchema.basic', None)

    The file boundary is detected by the 'zSchema' keyword: everything up to and
    including 'zSchema.<name>' is the file path; any additional segment is the block.

    Returns:
        (schema_path, block_name_or_None)
    """
    if not model_path:
        return model_path, None

    # Preserve the original prefix symbol (@. or ~.)
    prefix = ''
    path_body = model_path
    if model_path.startswith(_PREFIX_AT):
        prefix = _PREFIX_AT
        path_body = model_path[len(_PREFIX_AT):]
    elif model_path.startswith(_PREFIX_TILDE):
        prefix = _PREFIX_TILDE
        path_body = model_path[len(_PREFIX_TILDE):]

    parts = path_body.split(_SCHEMA_PATH_SEPARATOR)

    # Find the schema file-type keyword — the file name occupies FILE_TYPE_SCHEMA +
    # the next segment (2 parts total). Any segment beyond those two is the block.
    for i, part in enumerate(parts):
        if part == FILE_TYPE_SCHEMA and i + 1 < len(parts):
            file_end_idx = i + 2  # index one past the second part of the filename
            if len(parts) > file_end_idx:
                block = parts[-1]
                schema_path = prefix + _SCHEMA_PATH_SEPARATOR.join(parts[:-1])
                return schema_path, block
            break  # zSchema.<name> found but no trailing block

    return model_path, None


class SchemaManager:
    """
    Manages schema loading, validation, and caching.
    
    Responsibilities:
        - Load schemas from zPath via zLoader
        - Validate Meta section for required fields
        - Resolve Data_Path from environment variables (security)
        - Manage wizard mode schema cache
        - Extract schema names for error context
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance
        loader: zLoader instance (from zos)

    Class Attributes:
        _server_registry: Server-wide map of table_name → schema dict, populated
            on every load_schema call so that $alias wizard transactions can
            bootstrap a fresh connection from cold (e.g. in zTerminal execute_code).
    """

    # Server-wide schema registry: {table_name: full_schema_dict}
    # Class-level so it persists across all sessions and is populated once at boot.
    _server_registry: Dict[str, Any] = {}

    def __init__(self, zos: Any, logger: Any) -> None:
        """
        Initialize SchemaManager.
        
        Args:
            zos: zOS framework instance
            logger: Logger instance
        """
        self.zos = zos
        self.logger = logger
        self.loader = zos.loader

    def _normalize_field_aliases(self, schema: Dict[str, Any]) -> None:
        """Rewrite readable field-key aliases to their canonical form, in place.

        Users may write the long, self-documenting ``foreign_key: t.col`` to match
        the rest of the vocabulary (``auto_increment``, ``on_delete``, ``primary_key``),
        but the engine reads ``fk``. Canonicalise here at the single load chokepoint so
        every consumer (DDL FK clause, on_delete scan, schema_diff, validator) agrees.
        A pre-existing canonical key always wins — we never clobber an explicit ``fk``.
        """
        for table_name, table_def in schema.items():
            if table_name in (_RESERVED_KEY_META, _RESERVED_KEY_DB_PATH):
                continue
            if not isinstance(table_def, dict):
                continue
            for field_def in table_def.values():
                if not isinstance(field_def, dict):
                    continue  # skip non-field entries (e.g. zConstraints list)
                for long_form, canonical in _FIELD_KEY_ALIASES.items():
                    if long_form in field_def and canonical not in field_def:
                        field_def[canonical] = field_def.pop(long_form)

    def load_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load and validate schema.
        
        Args:
            schema: Schema dictionary with Meta section and table definitions
            
        Returns:
            Validated schema dictionary
            
        Raises:
            ValueError: If Meta section missing required fields
        """
        # Validate Meta section
        self._validate_meta(schema)

        # Normalize readable field-key aliases (e.g. foreign_key → fk) before anyone reads it
        self._normalize_field_aliases(schema)

        # Register every table in the server-wide registry so $alias fallback works
        # from any execution context (zTerminal, zCLI, zBifrost) without pre-caching.
        schema_name = schema.get(_META_KEY, {}).get(_META_KEY_SCHEMA_NAME, "unknown")
        for key in schema:
            if key not in (_RESERVED_KEY_META, _RESERVED_KEY_DB_PATH):
                SchemaManager._server_registry[key] = schema
                self.logger.debug(_LOG_REGISTRY_REGISTERED, key, schema_name)

        return schema

    def load_schema_from_path(self, model_path: str) -> Dict[str, Any]:
        """
        Load schema from zPath via zLoader.

        Supports extended paths that include a block/table name as the last segment:
            @.models.Demos.zSchema.basic.demo_basic
        In that case the block is stripped before file loading and the returned
        schema is scoped to just that block: {block: fields, 'zMeta': meta}.

        Args:
            model_path: zPath to schema file (e.g., "@.zSchema.users" or
                        "@.models.Demos.zSchema.basic.demo_basic")

        Returns:
            Loaded schema dictionary (scoped to the specified block when present)

        Raises:
            SchemaNotFoundError: If schema file not found, load failed, or block missing
        """
        if not model_path:
            self.logger.error(_ERROR_NO_SCHEMA_PROVIDED)
            raise ValueError(_ERROR_NO_SCHEMA_PROVIDED)

        # Extract block from extended path (e.g. @.models.Demos.zSchema.basic.demo_basic)
        schema_path, block = parse_schema_model_path(model_path)

        self.logger.info(_LOG_LOADING_SCHEMA, schema_path)
        schema = self.loader.handle(schema_path)

        if schema == _RESULT_ERROR or not schema:
            self.logger.error(_ERROR_SCHEMA_LOAD_FAILED.format(path=schema_path))
            schema_name = self._extract_schema_name(schema_path)
            raise SchemaNotFoundError(
                schema_name=schema_name,
                context_type="python",
                zpath=model_path
            )

        schema = self.load_schema(schema)

        # Scope to the specified block: {block: fields, 'zMeta': meta}
        if block:
            block_dict = schema.get(block)
            if block_dict is None:
                raise SchemaNotFoundError(
                    schema_name=block,
                    context_type="python",
                    zpath=model_path
                )
            return {_META_KEY: schema.get(_META_KEY, {}), block: block_dict}

        return schema

    def load_wizard_schema(
        self,
        schema_cache: Any,
        alias_name: str,
        cached_schema: Optional[Dict[str, Any]]
    ) -> tuple[Dict[str, Any], bool]:
        """
        Load schema for wizard mode with connection reuse.
        
        Args:
            schema_cache: SchemaCache instance
            alias_name: Alias name for connection ($users, $products)
            cached_schema: Optional cached schema dictionary
            
        Returns:
            Tuple of (schema, is_reused_connection)
            
        Raises:
            ValueError: If no cached schema provided for first-time connection
        """
        # Check if connection already exists (reuse)
        existing_handler = schema_cache.get_connection(alias_name)
        if existing_handler:
            self.logger.info(_LOG_REUSING_CONNECTION, alias_name)
            return existing_handler.schema, True

        # First use in wizard - try cached_schema, then fall back to server registry.
        if not cached_schema:
            # Bootstrap from the server-wide registry populated at schema load time.
            # This allows $alias transactions to work cold in zTerminal/execute_code
            # without requiring an explicit 'load' command first.
            cached_schema = SchemaManager._server_registry.get(alias_name)
            if cached_schema:
                self.logger.info(_LOG_REGISTRY_FALLBACK, alias_name)
            else:
                self.logger.error(_LOG_REGISTRY_MISS, alias_name)
                self.logger.error(_ERROR_NO_CACHED_SCHEMA.format(alias=alias_name))
                self.logger.error(_HINT_USE_LOAD_COMMAND, alias_name)
                raise ValueError(_ERROR_NO_CACHED_SCHEMA.format(alias=alias_name))

        self.logger.info(_LOG_LOADING_FROM_PINNED, alias_name)
        return self.load_schema(cached_schema), False

    def resolve_data_path(self, schema: Dict[str, Any]) -> tuple[str, str]:
        """
        Resolve Data_Path from environment or schema Meta.
        
        Priority order:
        1. Data_Source: Explicit env var reference (e.g., "ZDATA_CONTACTS_URL")
        2. Convention: Auto-detect from schema name (e.g., zSchema.contacts → ZDATA_CONTACTS_URL)
        3. Data_Path: Direct in schema (DEPRECATED - logs security warning)
        
        Args:
            schema: Schema dictionary with Meta section
            
        Returns:
            Tuple of (data_path, source) where source is:
            - "env_explicit": Loaded from Data_Source env var
            - "env_convention": Auto-detected from schema name
            - "schema_file": Loaded from Data_Path in schema (deprecated)
            
        Raises:
            ValueError: If no connection info found
        """
        meta = schema.get(_META_KEY, {})
        data_path = None
        data_path_source: str | None = None

        # Option 1: Check for Data_Source (explicit env var reference)
        if _META_KEY_DATA_SOURCE in meta:
            env_var_name = meta[_META_KEY_DATA_SOURCE]
            data_path_from_env = os.getenv(env_var_name)

            if data_path_from_env:
                data_path = data_path_from_env
                data_path_source = "env_explicit"
                self.logger.debug(_SECURITY_INFO_LOADED_FROM_ENV.format(env_var=env_var_name))
            else:
                self.logger.warning(f"[zData] Environment variable not found: {env_var_name}")

        # Option 2: Try auto-convention (if no Data_Source and no Data_Path yet)
        if not data_path and _META_KEY_DATA_PATH not in meta:
            schema_name = meta.get(_META_KEY_SCHEMA_NAME, meta.get(_META_KEY_ZVAFILES, ""))
            if schema_name:
                # Extract: "zSchema.contacts.yaml" → "contacts"
                schema_key = schema_name.replace(
                    FILE_TYPE_SCHEMA + _SCHEMA_PATH_SEPARATOR, ""
                ).replace(".yaml", "").split("/")[-1]
                env_var_name = f"{_ENV_VAR_PREFIX}{schema_key.upper()}{_ENV_VAR_SUFFIX}"
                data_path_from_env = os.getenv(env_var_name)

                if data_path_from_env:
                    data_path = data_path_from_env
                    data_path_source = "env_convention"
                    self.logger.debug(_SECURITY_INFO_AUTO_CONVENTION.format(env_var=env_var_name))

        # Option 3: Fallback to Data_Path in schema (DEPRECATED)
        if not data_path:
            if _META_KEY_DATA_PATH in meta:
                data_path = meta[_META_KEY_DATA_PATH]
                data_path_source = "schema_file"
                self.logger.warning(_SECURITY_WARNING_DATA_PATH_IN_SCHEMA)
            else:
                raise ValueError(_ERROR_NO_DATA_CONNECTION)

        # Resolve special paths via zParser
        data_path = self.zos.zparser.resolve_data_path(data_path)
        
        # Type safety: data_path_source is guaranteed to be set by this point
        assert data_path_source is not None, "data_path_source must be set if data_path is resolved"
        return data_path, data_path_source

    def get_schema_tables(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get table definitions from schema (excludes Meta and reserved keys).
        
        Args:
            schema: Schema dictionary
            
        Returns:
            Dict of table definitions
        """
        return {
            k: v for k, v in schema.items()
            if k not in (_RESERVED_KEY_META, _RESERVED_KEY_DB_PATH)
        }

    def _validate_meta(self, schema: Dict[str, Any]) -> None:
        """
        Validate schema Meta section.
        
        Args:
            schema: Schema dictionary
            
        Raises:
            ValueError: If Meta missing required fields
        """
        meta = schema.get(_META_KEY, {})

        if _META_KEY_DATA_TYPE not in meta:
            raise ValueError(_ERROR_MISSING_META_FIELD.format(field=_META_KEY_DATA_TYPE))

    def _extract_schema_name(self, model_path: str) -> str:
        """
        Extract schema name from zPath for error messages.
        
        Args:
            model_path: zPath to schema file
            
        Returns:
            Schema name (e.g., "users" from "@.zSchema.users")
        """
        if not model_path:
            return _SCHEMA_NAME_FALLBACK
        return model_path.split(_SCHEMA_PATH_SEPARATOR)[-1]
