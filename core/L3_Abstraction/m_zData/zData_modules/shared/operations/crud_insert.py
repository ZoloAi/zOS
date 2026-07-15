# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/crud_insert.py
"""
INSERT operation handler with hooks, validation, and flexible data sources.

This module implements the INSERT operation for zData's CRUD system. It provides
a comprehensive handler for inserting rows into database tables with support for
multiple data sources, pre/post-insert hooks, and schema-based validation.

Operation Overview
-----------------
The INSERT operation adds a new row to an existing table. The handler supports:
- Multiple data sources (explicit fields/values, data dict, command-line options)
- Pre-insert hooks (onBeforeInsert) for data modification or abortion
- Schema-based validation (required fields, data types, patterns, format, plugins)
- Post-insert hooks (onAfterInsert) for side effects
- Integration with zDialog (form submissions)
- Flexible error handling and logging

Execution Flow
-------------
The INSERT operation follows a 6-phase execution flow:

    1. **Table Extraction:** Extract and validate table name from request
       ↓
    2. **Data Collection:** Gather field/value pairs from multiple sources
       ↓
    3. **onBeforeInsert Hook:** Execute pre-insert hook (optional)
       - Can modify data (return dict to update fields)
       - Can abort operation (return False)
       ↓
    4. **Validation:** Validate data against schema rules
       - Required fields check
       - Data type validation
       - Pattern matching (regex)
       - Format validation (email, url, etc.)
       - Plugin validators (custom business logic)
       ↓
    5. **Insert Execution:** Execute adapter's insert() method
       - Returns row_id (primary key or last insert ID)
       ↓
    6. **onAfterInsert Hook:** Execute post-insert hook (optional)
       - Receives inserted data + row_id
       - For side effects (notifications, logging, etc.)

Data Sources
-----------
The handler supports three data sources (checked in order):

**1. Data Dictionary (from zDialog):**
    request["data"] = {"name": "Alice", "age": 30}
    - Most common source for form submissions
    - Used by zDialog for interactive forms

**2. Explicit Fields/Values:**
    request["fields"] = ["name", "age"]
    request["values"] = ["Alice", 30]
    - Direct specification of columns and values
    - Used for programmatic inserts

**3. Command-Line Options:**
    request["name"] = "Alice"
    request["age"] = 30
    - Extracted by extract_field_values helper
    - Used for CLI commands

Hook Integration
---------------
**onBeforeInsert Hook:**
- Executed before validation
- Receives: {"zConv": data_dict, "table": table_name}
- Can modify data: Return dict to update/add fields
- Can abort: Return False to cancel insert
- Use cases: data enrichment, computed fields, business rules

**onAfterInsert Hook:**
- Executed after successful insert
- Receives: {"zConv": data_dict, "table": table_name, "row_id": insert_id}
- Return value ignored (side effects only)
- Use cases: notifications, audit logs, cascade operations

zConv Pattern
------------
"zConv" (zCLI Convention) is the standard key used to pass data dictionaries
in hook contexts. It represents the current conversation/transaction data and
is used consistently across zCLI subsystems (zDialog, zData, zWizard, zFunc).

Validation Integration
---------------------
Data validation is performed via ops.validator.validate_insert(), which enforces:
- Required fields (from schema)
- Data types (int, float, str, bool)
- Pattern matching (regex)
- Format validation (email, url, date, etc.)
- Plugin validators (custom business logic via zFunc)

If validation fails, errors are displayed via display_validation_errors() and
the operation is aborted.

Usage Examples
-------------
**Basic INSERT:**
    >>> request = {
    ...     "table": "users",
    ...     "data": {"name": "Alice", "email": "alice@example.com"}
    ... }
    >>> result = handle_insert(request, ops)
    [OK] Inserted row with ID: 1

**INSERT with onBeforeInsert Hook:**
    >>> # Schema with hook to add timestamp
    >>> schema = {
    ...     "users": {
    ...         "onBeforeInsert": "&add_timestamp"
    ...     }
    ... }
    >>> # Plugin function adds created_at field
    >>> result = handle_insert(request, ops)

**INSERT with Validation Errors:**
    >>> request = {"table": "users", "data": {"name": ""}}  # Empty name
    >>> result = handle_insert(request, ops)
    [ERROR] Validation failed for table 'users':
      - name: Field is required

Integration
----------
This module is used by:
- classical_data.py: Classical paradigm INSERT operations
- quantum_data.py: Quantum paradigm INSERT operations
- data_operations.py: CRUD operation router
"""

from zOS import Any, Dict, uuid

# ============================================================
# Module Constants - Operation Name
# ============================================================

_OP_INSERT = "INSERT"

# ============================================================
# Module Constants - Request Keys
# ============================================================

from ..data_keys import KEY_FIELDS, KEY_VALUES, KEY_TABLE  # pylint: disable=wrong-import-position
_KEY_FIELDS = KEY_FIELDS
_KEY_VALUES = KEY_VALUES
_KEY_DATA = "data"
_KEY_TABLE = KEY_TABLE
_KEY_SCHEMA = "schema"
_KEY_ROW_ID = "row_id"

# ============================================================
# Module Constants - Hook Names
# ============================================================

_HOOK_BEFORE_INSERT = "onBeforeInsert"
_HOOK_AFTER_INSERT = "onAfterInsert"

# ============================================================
# Module Constants - zConv Key
# ============================================================

_ZCONV_KEY = "zConv"

# ============================================================
# Module Constants - Log Messages
# ============================================================

_LOG_EXTRACT_TABLE = "Extracting table from request for %s operation"
_LOG_EXTRACT_FIELDS = "Extracting fields/values from request"
_LOG_BUILD_DATA = "Building data dictionary from fields/values"
_LOG_HOOK_BEFORE = "Executing %s hook for %s"
_LOG_HOOK_AFTER = "Executing %s hook for %s"
_LOG_VALIDATE = "Validating data for %s operation on table %s"
_LOG_INSERT = "Executing insert operation on table %s"
_LOG_SUCCESS = "[OK] Inserted row with ID: %s"
_LOG_HOOK_ABORT = "%s hook returned False, aborting %s operation"
_LOG_HOOK_MODIFY = "%s hook returned dict, updating data"
_LOG_VALIDATION_ERROR = "Validation failed for table %s"
_LOG_INSERT_ERROR = "Insert operation failed for table %s"

# ============================================================
# Module Constants - Error Messages
# ============================================================

_ERR_NO_TABLE = "No table specified for INSERT operation"
_ERR_NO_FIELDS = "No fields specified for INSERT operation"
_ERR_HOOK_ABORT = "onBeforeInsert hook aborted operation"
_ERR_VALIDATION_FAILED = "Validation failed"
_ERR_INSERT_FAILED = "Insert operation failed"
_ERR_NO_DATA = "No data provided for INSERT operation"
_ERR_INVALID_DATA = "Invalid data format"
_ERR_HOOK_ERROR = "Hook execution error"

# ============================================================
# Imports - Helper Functions
# ============================================================

try:
    from .helpers import (
        extract_table_from_request,
        extract_field_values,
        display_validation_errors,
        check_unique_constraints,
        check_row_constraints,
        surface_errors_to_session,
        apply_transforms,
        apply_defaults,
        normalize_write_values,
    )
    from .crud_helpers import _display_returning
    from .blob_ops import coerce_blob_fields, store_blob_fields
    from ..parsers.where_parser import parse_where_clause
except ImportError:
    from helpers import (
        extract_table_from_request,
        extract_field_values,
        display_validation_errors,
        check_unique_constraints,
        check_row_constraints,
        surface_errors_to_session,
        apply_transforms,
        apply_defaults,
        normalize_write_values,
    )
    from crud_helpers import _display_returning
    from blob_ops import coerce_blob_fields, store_blob_fields
    from parsers.where_parser import parse_where_clause

# ============================================================
# Public API
# ============================================================

__all__ = ["handle_insert"]


# ============================================================
# Internal - single-row processing pipeline
# ============================================================

def _process_row(table: str, raw_data: Dict[str, Any], table_schema: Dict[str, Any], ops: Any):
    """
    Run the full single-row pipeline: hash → UUID → transform → hook → unique →
    row-constraints → validate.

    Returns (processed_data, None) on success, or (None, error_msg) on failure.
    """
    data = dict(raw_data)

    # defaults — fill omitted/empty fields so required+default columns satisfy NOT NULL
    data = apply_defaults(table, data, table_schema, ops)

    # hash
    for field_name, field_value in list(data.items()):
        field_def = table_schema.get(field_name, {})
        if isinstance(field_def, dict) and field_def.get('zHash') == 'bcrypt':
            if ops.zos and hasattr(ops.zos, 'auth'):
                try:
                    data[field_name] = ops.zos.auth.hash_password(str(field_value))
                except Exception as e:
                    return None, f"Failed to hash '{field_name}': {e}"
            else:
                return None, f"zHash: bcrypt on '{field_name}' but zAuth not available"

    # UUID auto-gen
    for field_name, field_def in table_schema.items():
        if not isinstance(field_def, dict):
            continue
        if field_def.get('type') not in ('uuid',):
            continue
        if not data.get(field_name):
            version = (field_def.get('rules') or {}).get('version', 4)
            data[field_name] = str(uuid.uuid1()) if version == 1 else str(uuid.uuid4())

    # transforms
    data = apply_transforms(table, data, table_schema, ops)

    # zNull sentinel → NULL; date/datetime values → ISO canonical (zOS#18)
    data = normalize_write_values(table, data, table_schema, ops)

    # blob coercion — normalise blob inputs to bytes so validation sizes the bytes.
    # Conversion to the backend storage cell happens after validation (caller).
    data = coerce_blob_fields(data, table_schema)

    # onBeforeInsert hook
    on_before = table_schema.get(_HOOK_BEFORE_INSERT)
    if on_before:
        hook_result = ops.execute_hook(on_before, {_ZCONV_KEY: data, _KEY_TABLE: table})
        if hook_result is False:
            return None, "onBeforeInsert hook aborted"
        if isinstance(hook_result, dict):
            data.update(hook_result)

    # unique constraints
    unique_errors = check_unique_constraints(table, data, table_schema, ops)
    if unique_errors:
        display_validation_errors(table, unique_errors, ops)
        surface_errors_to_session(unique_errors, ops)
        return None, "unique constraint violation"

    # row-level constraints
    row_errors = check_row_constraints(table, data, table_schema, ops)
    if row_errors:
        display_validation_errors(table, row_errors, ops)
        surface_errors_to_session(row_errors, ops)
        return None, "row constraint violation"

    # field validation
    is_valid, errors = ops.validator.validate_insert(table, data)
    if not is_valid:
        display_validation_errors(table, errors, ops)
        surface_errors_to_session(errors, ops)
        return None, "validation failed"

    return data, None


# ============================================================
# CRUD Operations - INSERT
# ============================================================

def handle_insert(request: Dict[str, Any], ops: Any) -> bool:
    """
    Handle INSERT operation to insert a new row into an existing table.

    This function implements the complete INSERT workflow including table validation,
    data collection from multiple sources, pre-insert hooks, schema validation,
    insert execution, and post-insert hooks.

    Args:
        request: Request dictionary containing operation parameters
            - "table" (str): Table name to insert into
            - "data" (dict, optional): Data dictionary (from zDialog)
            - "fields" (list, optional): Field names
            - "values" (list, optional): Field values
            - Additional keys extracted as field/value pairs (command-line)
        ops: Operations object providing:
            - schema (dict): Table schemas with validation rules and hooks
            - validator: Validator instance for data validation
            - logger: Logger instance for diagnostic output
            - insert(table, fields, values): Insert method
            - execute_hook(hook, context): Hook execution method

    Returns:
        bool: True if insert succeeded, False if failed (validation, hook abort, etc.)

    Raises:
        None: All errors are logged and return False

    Examples:
        >>> # Basic INSERT with data dict
        >>> request = {"table": "users", "data": {"name": "Alice", "age": 30}}
        >>> result = handle_insert(request, ops)
        [OK] Inserted row with ID: 1

        >>> # INSERT with hook that adds timestamp
        >>> request = {"table": "logs", "data": {"message": "System started"}}
        >>> result = handle_insert(request, ops)
        Executing onBeforeInsert hook for logs
        [OK] Inserted row with ID: 42

    Notes:
        - Data sources checked in order: data dict, fields/values, command-line
        - onBeforeInsert hook can modify data or abort (return False)
        - Validation enforced via validator.validate_insert()
        - onAfterInsert hook for side effects (notifications, logging)
        - zConv key used to pass data in hook context
    """
    # Phase 1: Extract and validate table name
    table = extract_table_from_request(request, _OP_INSERT, ops, check_exists=False)
    if not table:
        return False

    table_schema = ops.schema.get(table, {})

    # ── SELECT path: insert rows sourced from a read of another table ────────
    select_block = request.get("select")
    if select_block and isinstance(select_block, dict):
        # Resolve source table name from model path (last segment)
        source_model = select_block.get("model") or select_block.get("table", "")
        source_table = source_model.split(".")[-1] if "." in source_model else source_model
        if not source_table:
            ops.logger.error("[zData] INSERT … SELECT: missing select.model")
            ops.display.error("INSERT … SELECT: missing select.model")
            return False

        # Parse optional WHERE for the source query
        where_str = select_block.get("where")
        where_dict = parse_where_clause(where_str) if where_str else None

        # Fetch source rows
        try:
            source_rows = ops.select(source_table, where=where_dict)
        except Exception as e:  # pylint: disable=broad-except
            ops.logger.error(f"[zData] INSERT … SELECT: source read failed: {e}")
            ops.display.error(f"INSERT … SELECT: failed to read from {source_table}: {e}")
            return False

        if not source_rows:
            msg = f"[insert…select] 0 rows matched in {source_table} — nothing inserted"
            ops.logger.info(msg)
            ops.display.success(msg)
            return True

        # Apply explicit field subset (select.fields: [col1, col2])
        subset_fields = select_block.get("fields")
        if subset_fields and isinstance(subset_fields, list):
            source_rows = [{k: v for k, v in row.items() if k in subset_fields}
                           for row in source_rows]
        else:
            # Auto-project: strip columns unknown to the target schema to avoid
            # validation failures when source has extra columns.
            known_fields = set(table_schema.keys())
            source_rows = [{k: v for k, v in row.items() if k in known_fields}
                           for row in source_rows]

        # Apply optional column renaming (select.map: {src_col: tgt_col})
        col_map = select_block.get("map")
        if col_map and isinstance(col_map, dict):
            source_rows = [{col_map.get(k, k): v for k, v in row.items()}
                           for row in source_rows]

        # Run each source row through the full single-row insert pipeline
        processed_rows = []
        for idx, row_raw in enumerate(source_rows):
            processed, err = _process_row(table, row_raw, table_schema, ops)
            if err:
                ops.logger.error(f"[zData] INSERT … SELECT aborted at row {idx}: {err}")
                return False
            processed_rows.append(processed)

        processed_rows = [store_blob_fields(p, table, table_schema, ops) for p in processed_rows]
        row_ids = ops.insert_many(table, processed_rows)
        msg = (f"[insert…select] {len(row_ids)} row(s) from {source_table} "
               f"→ {table} (ids: {row_ids})")
        ops.logger.info(msg)
        ops.display.success(msg)

        returning = request.get("returning")
        returned = _display_returning(table, row_ids, returning, ops) if returning else None

        on_after = table_schema.get(_HOOK_AFTER_INSERT)
        if on_after:
            ops.execute_hook(on_after, {_ZCONV_KEY: processed_rows,
                                         _KEY_TABLE: table, _KEY_ROW_ID: row_ids})
        return returned if returning else True

    # ── Bulk path: data is a list of dicts ──────────────────────────────────
    data_raw = request.get(_KEY_DATA)
    if isinstance(data_raw, list):
        ops.logger.info(f"[zData] Bulk insert: {len(data_raw)} row(s) into {table}")
        processed_rows = []
        for idx, row_raw in enumerate(data_raw):
            if not isinstance(row_raw, dict):
                ops.logger.error(f"[zData] Bulk insert row {idx} is not a dict, aborting")
                ops.display.error(f"Bulk insert aborted: row {idx} is not a dict")
                return False
            processed, err = _process_row(table, row_raw, table_schema, ops)
            if err:
                ops.logger.error(f"[zData] Bulk insert aborted at row {idx}: {err}")
                return False
            processed_rows.append(processed)
        processed_rows = [store_blob_fields(p, table, table_schema, ops) for p in processed_rows]
        row_ids = ops.insert_many(table, processed_rows)
        msg = f"[bulk-inserted] {len(row_ids)} row(s) into {table} (ids: {row_ids})"
        ops.logger.info(msg)
        ops.display.success(msg)
        returning = request.get("returning")
        returned = _display_returning(table, row_ids, returning, ops) if returning else None
        on_after = table_schema.get(_HOOK_AFTER_INSERT)
        if on_after:
            ops.execute_hook(on_after, {_ZCONV_KEY: processed_rows, _KEY_TABLE: table, _KEY_ROW_ID: row_ids})
        return returned if returning else True

    # Phase 2: Extract field/value pairs from request (single-row path)
    fields = request.get(_KEY_FIELDS, [])
    values = request.get(_KEY_VALUES)

    # Check if data dictionary is provided (from zDialog/zData)
    data_dict = request.get(_KEY_DATA)
    if data_dict and isinstance(data_dict, dict):
        fields = list(data_dict.keys())
        values = list(data_dict.values())
    # If no explicit values, extract from command-line options
    elif not values:
        fields, values = extract_field_values(request, _OP_INSERT, ops)
        if not fields:
            return False

    # Build data dictionary for validation and hooks
    data = dict(zip(fields, values))

    # Phase 2.4: Apply declared defaults to omitted/empty fields. Done before
    # hashing/validation so a required+default column still satisfies NOT NULL.
    data = apply_defaults(table, data, table_schema, ops)
    fields = list(data.keys())
    values = list(data.values())

    # Phase 2.5: Auto-hash password fields (if zHash: bcrypt in schema)
    hash_modified = False
    for field_name, field_value in list(data.items()):
        field_def = table_schema.get(field_name, {})
        if isinstance(field_def, dict) and field_def.get('zHash') == 'bcrypt':
            # Hash the password using zAuth
            if ops.zos and hasattr(ops.zos, 'auth'):
                try:
                    ops.logger.info(
                        f"[zData] Auto-hashing field '{field_name}' with bcrypt "
                        f"(plaintext MASKED for security)"
                    )
                    hashed_value = ops.zos.auth.hash_password(str(field_value))
                    data[field_name] = hashed_value
                    hash_modified = True
                    ops.logger.debug(
                        f"[zData] Field '{field_name}' hashed successfully "
                        f"(hash length: {len(hashed_value)} chars)"
                    )
                except Exception as e:
                    ops.logger.error(f"[zData] Failed to hash field '{field_name}': {e}")
                    return False
            else:
                ops.logger.error(f"[zData] zHash: bcrypt specified for '{field_name}' but zAuth not available")
                return False

    # Rebuild fields/values from potentially modified data
    if hash_modified:
        fields = list(data.keys())
        values = list(data.values())

    # Phase 2.75: Auto-generate UUID v4 for uuid-typed fields that are empty / absent
    uuid_modified = False
    for field_name, field_def in table_schema.items():
        if not isinstance(field_def, dict):
            continue
        if field_def.get('type') not in ('uuid',):
            continue
        current_val = data.get(field_name)
        if current_val is None or current_val == '':
            version = (field_def.get('rules') or {}).get('version', 4)
            generated = str(uuid.uuid1()) if version == 1 else str(uuid.uuid4())
            data[field_name] = generated
            uuid_modified = True
            ops.logger.info(f"[zData] Auto-generated UUID v{version} for '{field_name}': {generated}")

    if uuid_modified:
        fields = list(data.keys())
        values = list(data.values())

    # Phase 2.9: Apply field-level transforms (pre-validate normalisation)
    data = apply_transforms(table, data, table_schema, ops)
    fields = list(data.keys())
    values = list(data.values())

    # Phase 2.92: zNull sentinel → NULL; date/datetime → ISO canonical (zOS#18)
    data = normalize_write_values(table, data, table_schema, ops)
    fields = list(data.keys())
    values = list(data.values())

    # Phase 2.95: Coerce blob fields to bytes (validation sizes the bytes;
    # conversion to the backend storage cell happens after validation, Phase 4.9)
    data = coerce_blob_fields(data, table_schema)
    fields = list(data.keys())
    values = list(data.values())

    # Phase 3: Execute onBeforeInsert hook (can modify data or abort)
    on_before_insert = table_schema.get(_HOOK_BEFORE_INSERT)
    if on_before_insert:
        ops.logger.info(_LOG_HOOK_BEFORE, _HOOK_BEFORE_INSERT, table)
        hook_result = ops.execute_hook(on_before_insert, {_ZCONV_KEY: data, _KEY_TABLE: table})
        if hook_result is False:
            ops.logger.error(_LOG_HOOK_ABORT, _HOOK_BEFORE_INSERT, _OP_INSERT)
            return False
        # If hook returns a dict, use it to update data
        if isinstance(hook_result, dict):
            ops.logger.debug(_LOG_HOOK_MODIFY, _HOOK_BEFORE_INSERT)
            data.update(hook_result)
            fields = list(data.keys())
            values = list(data.values())

    # Phase 3.5: Check unique constraints (cross-record, adapter-agnostic via ops.select)
    unique_errors = check_unique_constraints(table, data, table_schema, ops)
    if unique_errors:
        ops.logger.error(_LOG_VALIDATION_ERROR, table)
        display_validation_errors(table, unique_errors, ops)
        surface_errors_to_session(unique_errors, ops)
        return False

    # Phase 3.75: Check row-level constraints (zConstraints: check:)
    row_errors = check_row_constraints(table, data, table_schema, ops)
    if row_errors:
        ops.logger.error(_LOG_VALIDATION_ERROR, table)
        display_validation_errors(table, row_errors, ops)
        surface_errors_to_session(row_errors, ops)
        return False

    # Phase 4: Validate data before inserting
    is_valid, errors = ops.validator.validate_insert(table, data)
    if not is_valid:
        ops.logger.error(_LOG_VALIDATION_ERROR, table)
        display_validation_errors(table, errors, ops)
        surface_errors_to_session(errors, ops)
        return False

    # Phase 4.9: Store blobs (bytes → backend cell) just before persistence
    data = store_blob_fields(data, table, table_schema, ops)
    fields = list(data.keys())
    values = list(data.values())

    # Phase 5: Execute insert using operations' insert method
    row_id = ops.insert(table, fields, values)
    ops.logger.info(_LOG_SUCCESS, row_id)

    # Phase 5.5: RETURNING — fetch and display the inserted row(s)
    returning = request.get("returning")
    returned = _display_returning(table, [row_id], returning, ops) if returning else None

    # Phase 6: Execute onAfterInsert hook (for side effects)
    on_after_insert = table_schema.get(_HOOK_AFTER_INSERT)
    if on_after_insert:
        ops.logger.info(_LOG_HOOK_AFTER, _HOOK_AFTER_INSERT, table)
        context = {_ZCONV_KEY: data, _KEY_TABLE: table, _KEY_ROW_ID: row_id}
        ops.execute_hook(on_after_insert, context)

    return returned if returning else True
