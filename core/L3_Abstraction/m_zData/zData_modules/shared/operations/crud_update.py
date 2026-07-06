# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/crud_update.py
"""
UPDATE operation handler with hooks, validation, and WHERE clause safety.

This module implements the UPDATE operation for zData's CRUD system. It provides
a comprehensive handler for modifying existing rows in database tables with support
for partial updates, pre/post-update hooks, schema-based validation, and WHERE
clause safety warnings.

Operation Overview
-----------------
The UPDATE operation modifies existing rows in a table. The handler supports:
- Partial updates (update specific fields, not all columns)
- WHERE clause filtering (which rows to update)
- WHERE clause safety warning (warns if missing to prevent accidental full-table updates)
- Pre-update hooks (onBeforeUpdate) for data modification or abortion
- Schema-based validation (required fields, data types, patterns, format, plugins)
- Post-update hooks (onAfterUpdate) for side effects
- Returns boolean based on affected row count (count > 0)
- Hook receives WHERE clause for conditional logic

Execution Flow
-------------
The UPDATE operation follows a 6-phase execution flow:

    1. **Table Extraction:** Extract and validate table name from request
       ↓
    2. **Field/Value Extraction:** Extract field/value pairs to update
       ↓
    3. **WHERE Clause Extraction:** Extract WHERE clause (warns if missing)
       ↓
    4. **onBeforeUpdate Hook:** Execute pre-update hook (optional)
       - Can modify data (return dict to update fields)
       - Can abort operation (return False)
       - Receives WHERE clause for conditional logic
       ↓
    5. **Validation:** Validate data against schema rules
       - Data type validation
       - Pattern matching (regex)
       - Format validation (email, url, etc.)
       - Plugin validators (custom business logic)
       ↓
    6. **Update Execution:** Execute adapter's update() method
       - Returns count of affected rows
       ↓
    7. **onAfterUpdate Hook:** Execute post-update hook (optional)
       - Receives updated data + WHERE clause + count
       - For side effects (notifications, logging, etc.)

Partial Updates
--------------
UPDATE supports partial updates - you can update specific fields without providing
all columns:

    request = {"table": "users", "fields": ["email"], "values": ["new@example.com"], "where": "id = 1"}
    # Only updates email field, other fields unchanged

WHERE Clause Safety
------------------
**IMPORTANT:** UPDATE without a WHERE clause will update ALL rows in the table.

The handler provides safety by:
- Warning if WHERE clause is missing (warn_if_missing=True)
- Logging a warning message to alert the operator
- Still allowing the operation (but with clear warning)

**Best Practice:** Always provide a WHERE clause unless you intentionally want to
update all rows.

Hook Integration
---------------
**onBeforeUpdate Hook:**
- Executed before validation
- Receives: {"zConv": data_dict, "table": table_name, "where": where_clause}
- Can modify data: Return dict to update/add fields
- Can abort: Return False to cancel update
- WHERE clause available for conditional logic
- Use cases: data enrichment, computed fields, conditional updates

**onAfterUpdate Hook:**
- Executed after successful update
- Receives: {"zConv": data_dict, "table": table_name, "where": where_clause, "count": affected_rows}
- Return value ignored (side effects only)
- Use cases: notifications, audit logs, cascade operations

zConv Pattern
------------
"zConv" (zCLI Convention) is the standard key used to pass data dictionaries
in hook contexts. It represents the current conversation/transaction data and
is used consistently across zCLI subsystems (zDialog, zData, zWizard, zFunc).

Validation Integration
---------------------
Data validation is performed via ops.validator.validate_update(), which enforces:
- Data types (int, float, str, bool)
- Pattern matching (regex)
- Format validation (email, url, date, etc.)
- Plugin validators (custom business logic via zFunc)

Note: Required field validation is typically less strict for UPDATE than INSERT,
as partial updates are allowed.

Return Value
-----------
The handler returns a boolean based on affected row count:
- Returns count > 0 (True if at least one row was updated)
- Returns False if no rows were affected or if operation failed

This differs from INSERT (returns True on success) because UPDATE may legitimately
affect zero rows if WHERE clause matches nothing.

Usage Examples
-------------
**Basic UPDATE with WHERE:**
    >>> request = {
    ...     "table": "users",
    ...     "fields": ["status"],
    ...     "values": ["active"],
    ...     "where": "id = 1"
    ... }
    >>> result = handle_update(request, ops)
    [OK] Updated 1 row(s) in users

**UPDATE without WHERE (all rows - WARNING):**
    >>> request = {"table": "users", "fields": ["status"], "values": ["active"]}
    >>> result = handle_update(request, ops)
    [WARN] No WHERE clause provided for UPDATE on users (will update ALL rows)
    [OK] Updated 150 row(s) in users

**UPDATE with onBeforeUpdate Hook:**
    >>> # Schema with hook to add updated_at timestamp
    >>> schema = {
    ...     "users": {
    ...         "onBeforeUpdate": "&add_updated_timestamp"
    ...     }
    ... }
    >>> result = handle_update(request, ops)

Integration
----------
This module is used by:
- classical_data.py: Classical paradigm UPDATE operations
- quantum_data.py: Quantum paradigm UPDATE operations
- data_operations.py: CRUD operation router
"""

from zOS import Any, Dict, uuid

try:
    from ..validators.constants import ERR_IMMUTABLE_FIELD
except ImportError:
    from validators.constants import ERR_IMMUTABLE_FIELD

# ============================================================
# Module Constants - Operation Name
# ============================================================

_OP_UPDATE = "UPDATE"

# ============================================================
# Module Constants - Request Keys (SSOT: shared/data_keys)
# ============================================================

from ..data_keys import KEY_FIELDS, KEY_VALUES, KEY_TABLE, KEY_WHERE  # pylint: disable=wrong-import-position

_KEY_FIELDS = KEY_FIELDS
_KEY_VALUES = KEY_VALUES
_KEY_TABLE = KEY_TABLE
_KEY_WHERE = KEY_WHERE
_KEY_SCHEMA = "schema"
_KEY_COUNT = "count"

# ============================================================
# Module Constants - Hook Names
# ============================================================

_HOOK_BEFORE_UPDATE = "onBeforeUpdate"
_HOOK_AFTER_UPDATE = "onAfterUpdate"

# ============================================================
# Module Constants - zConv Key
# ============================================================

_ZCONV_KEY = "zConv"

# ============================================================
# Module Constants - Log Messages
# ============================================================

_LOG_EXTRACT_TABLE = "Extracting table from request for %s operation"
_LOG_EXTRACT_FIELDS = "Extracting fields/values from request"
_LOG_EXTRACT_WHERE = "Extracting WHERE clause from request"
_LOG_HOOK_BEFORE = "Executing %s hook for %s"
_LOG_HOOK_AFTER = "Executing %s hook for %s"
_LOG_VALIDATE = "Validating data for %s operation on table %s"
_LOG_UPDATE = "Executing update operation on table %s"
_LOG_SUCCESS = "[OK] Updated %d row(s) in %s"
_LOG_HOOK_ABORT = "%s hook returned False, aborting %s operation"
_LOG_HOOK_MODIFY = "%s hook returned dict, updating data"
_LOG_VALIDATION_ERROR = "Validation failed for table %s"
_LOG_NO_ROWS = "No rows affected by UPDATE (WHERE clause matched nothing)"

# ============================================================
# Module Constants - Error Messages
# ============================================================

_ERR_NO_TABLE = "No table specified for UPDATE operation"
_ERR_NO_FIELDS = "No fields specified for UPDATE operation"
_ERR_HOOK_ABORT = "onBeforeUpdate hook aborted operation"
_ERR_VALIDATION_FAILED = "Validation failed"
_ERR_UPDATE_FAILED = "Update operation failed"
_ERR_NO_WHERE = "No WHERE clause provided (will update ALL rows)"
_ERR_INVALID_DATA = "Invalid data format"
_ERR_HOOK_ERROR = "Hook execution error"

# ============================================================
# Imports - Helper Functions
# ============================================================

try:
    from .helpers import (
        extract_table_from_request,
        extract_where_clause,
        extract_field_values,
        display_validation_errors,
        check_unique_constraints,
        check_row_constraints,
        surface_errors_to_session,
        apply_transforms,
    )
    from .crud_helpers import _display_returning
    from .crud_update_cond import has_conditional_set, handle_conditional_update
    from .crud_update_join import is_join_update, handle_join_update
    from .crud_set_expr import has_computed_set
    from .blob_ops import coerce_blob_fields, store_blob_fields, blob_fields
except ImportError:
    from helpers import (
        extract_table_from_request,
        extract_where_clause,
        extract_field_values,
        display_validation_errors,
        check_unique_constraints,
        check_row_constraints,
        surface_errors_to_session,
        apply_transforms,
    )
    from crud_helpers import _display_returning
    from crud_update_cond import has_conditional_set, handle_conditional_update
    from crud_update_join import is_join_update, handle_join_update
    from crud_set_expr import has_computed_set
    from blob_ops import coerce_blob_fields, store_blob_fields, blob_fields

# ============================================================
# Public API
# ============================================================

__all__ = ["handle_update"]

# ============================================================
# CRUD Operation - UPDATE
# ============================================================

def handle_update(request: Dict[str, Any], ops: Any) -> bool:
    """
    Handle UPDATE operation to modify existing rows in a table.

    This function implements the complete UPDATE workflow including table/field extraction,
    WHERE clause safety, pre-update hooks, validation, update execution, and post-update
    hooks. It supports partial updates (update specific fields only) and provides safety
    warnings for missing WHERE clauses.

    Args:
        request (Dict[str, Any]): The UPDATE request with the following keys:
            - "table" (str): Name of the table to update
            - "fields" (List[str]): List of field names to update
            - "values" (List[Any]): List of values (same order as fields)
            - "where" (str, optional): SQL WHERE clause (e.g., "id = 1")
              WARNING: Missing WHERE clause will update ALL rows
        ops (Any): The operations object with the following attributes/methods:
            - schema (Dict): Schema dictionary with table definitions and hooks
            - logger: Logger instance for operation tracking
            - validator: Validator instance for data validation
            - execute_hook(hook_name, context): Execute a hook function
            - update(table, fields, values, where): Execute the UPDATE operation

    Returns:
        bool: True if at least one row was updated (count > 0), False if operation
              failed or no rows were affected. Note: This differs from INSERT which
              returns True on success, because UPDATE may legitimately affect zero
              rows if WHERE clause matches nothing.

    Raises:
        No explicit exceptions are raised. Errors are logged and False is returned.

    Examples:
        >>> # Basic UPDATE with WHERE clause
        >>> request = {
        ...     "table": "users",
        ...     "fields": ["email", "status"],
        ...     "values": ["newemail@example.com", "active"],
        ...     "where": "id = 1"
        ... }
        >>> result = handle_update(request, ops)
        [OK] Updated 1 row(s) in users

        >>> # UPDATE without WHERE (WARNING - updates ALL rows)
        >>> request = {"table": "users", "fields": ["status"], "values": ["active"]}
        >>> result = handle_update(request, ops)
        [WARN] No WHERE clause provided for UPDATE on users (will update ALL rows)
        [OK] Updated 150 row(s) in users

        >>> # UPDATE with onBeforeUpdate hook (adds updated_at timestamp)
        >>> # Schema: {"users": {"onBeforeUpdate": "&add_timestamp"}}
        >>> result = handle_update(request, ops)
        Executing onBeforeUpdate hook for users
        [OK] Updated 1 row(s) in users

    Note:
        - Partial updates are supported (update specific fields, not all columns)
        - WHERE clause is optional but strongly recommended (warns if missing)
        - onBeforeUpdate hook can modify data (return dict) or abort (return False)
        - Hook receives WHERE clause for conditional logic
        - onAfterUpdate hook receives count of affected rows
        - Returns boolean based on count > 0 (differs from INSERT)
    """
    # ============================================================
    # Phase 1: Table Extraction
    # ============================================================
    table = extract_table_from_request(request, _OP_UPDATE, ops, check_exists=True)
    if not table:
        return False

    # ============================================================
    # Phase 1.5: `set:` alias + conditional (zCase) / computed delegation
    # `set:` reads naturally for UPDATE and is an alias of `data:`. When any SET
    # field carries a zCase block or a computed spec ($inc / zExpr), hand off to
    # the per-row executor — those values differ per row, so a single literal
    # write cannot express them.
    # ============================================================
    if is_join_update(request):
        return handle_join_update(request, ops)
    set_container = request.get("set")
    if set_container is not None and "data" not in request and not request.get("fields"):
        request = {**request, "data": set_container}
    _set = request.get("set") if request.get("set") is not None else request.get("data")
    if has_conditional_set(_set) or has_computed_set(_set):
        return handle_conditional_update(request, ops)

    # ============================================================
    # Phase 2: Field/Value Extraction
    # ============================================================
    # Check for explicit top-level fields/values first (consistent with UPSERT and documented API)
    fields = request.get("fields", [])
    values = request.get("values")

    # Support data: {field: value} dict format (same as insert/upsert — unified API)
    if not fields and not values:
        data_dict = request.get("data")
        if isinstance(data_dict, dict) and data_dict:
            fields = list(data_dict.keys())
            values = list(data_dict.values())

    # If no explicit values, extract from options dict (legacy support)
    if not values:
        fields, values = extract_field_values(request, _OP_UPDATE, ops)
        if not fields:
            return False
    elif not fields:
        # Values provided but no fields - error
        ops.logger.error("Values provided but no fields for UPDATE operation")
        return False

    # Build data dictionary for validation and hooks
    data = dict(zip(fields, values))

    # ============================================================
    # Phase 2.5: Immutable Field Check
    # Reject update if any submitted field is marked immutable: true in the schema.
    # Enforcement is at operation level, not validator level — immutable is a write
    # policy, not a value constraint.
    # ============================================================
    table_schema_pre = ops.schema.get(table, {})
    immutable_violations = {}
    for field_name in list(data.keys()):
        field_def = table_schema_pre.get(field_name)
        if isinstance(field_def, dict) and field_def.get('immutable', False) is True:
            immutable_violations[field_name] = ERR_IMMUTABLE_FIELD.format(field_name=field_name)
    if immutable_violations:
        ops.logger.error("[zData] Update rejected: immutable field(s) in payload: %s", list(immutable_violations.keys()))
        display_validation_errors(table, immutable_violations, ops)
        surface_errors_to_session(immutable_violations, ops)
        return False

    # ============================================================
    # Phase 3: WHERE Clause Extraction (with safety warning)
    # ============================================================
    where = extract_where_clause(request, ops, warn_if_missing=True)

    # ============================================================
    # Phase 3.5: Auto-generate UUID for uuid-typed fields submitted empty
    # ============================================================
    table_schema = ops.schema.get(table, {})
    uuid_modified = False
    for field_name in list(data.keys()):
        field_def = table_schema.get(field_name, {})
        if isinstance(field_def, dict) and field_def.get('type') in ('uuid',):
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

    # ============================================================
    # Phase 3.9: Apply field-level transforms (pre-validate normalisation)
    # ============================================================
    data = apply_transforms(table, data, table_schema, ops)
    fields = list(data.keys())
    values = list(data.values())

    # ============================================================
    # Phase 3.95: Coerce blob fields to bytes (validation sizes the bytes;
    # conversion to the backend storage cell happens after validation, Phase 5.5)
    # ============================================================
    data = coerce_blob_fields(data, table_schema)
    fields = list(data.keys())
    values = list(data.values())

    # ============================================================
    # Phase 3.75: RETURNING — pre-fetch matching row IDs before update
    # Must happen before the write so the WHERE condition still resolves
    # correctly even when the updated field is the filter field.
    # ============================================================
    returning = request.get("returning")
    pre_fetch_ids = []
    if returning and where:
        try:
            auto_id_field = 'id'
            for _fn, _fd in table_schema.items():
                if isinstance(_fd, dict) and _fd.get('auto_increment'):
                    auto_id_field = _fn
                    break
            id_rows = ops.select(table, where=where)
            pre_fetch_ids = [r[auto_id_field] for r in id_rows if auto_id_field in r]
        except Exception as _e:  # pylint: disable=broad-except
            ops.logger.warning(f"[zData] UPDATE RETURNING pre-fetch failed: {_e}")

    # ============================================================
    # Phase 4: onBeforeUpdate Hook (data modification/abortion)
    # ============================================================
    on_before_update = table_schema.get(_HOOK_BEFORE_UPDATE)
    if on_before_update:
        ops.logger.info(_LOG_HOOK_BEFORE, _HOOK_BEFORE_UPDATE, table)
        hook_result = ops.execute_hook(on_before_update, {
            _ZCONV_KEY: data,
            _KEY_TABLE: table,
            _KEY_WHERE: where
        })
        if hook_result is False:
            ops.logger.error(_LOG_HOOK_ABORT, _HOOK_BEFORE_UPDATE, _OP_UPDATE)
            return False
        # If hook returns a dict, use it to update data
        if isinstance(hook_result, dict):
            ops.logger.info(_LOG_HOOK_MODIFY, _HOOK_BEFORE_UPDATE)
            data.update(hook_result)
            fields = list(data.keys())
            values = list(data.values())

    # ============================================================
    # Phase 4.5: Unique Constraint Check
    # Passes the operation's WHERE clause so the current row is excluded —
    # prevents a false violation when a field is updated to its existing value.
    # ============================================================
    unique_errors = check_unique_constraints(table, data, table_schema, ops, exclude_where=where)
    if unique_errors:
        ops.logger.error(_LOG_VALIDATION_ERROR, table)
        display_validation_errors(table, unique_errors, ops)
        surface_errors_to_session(unique_errors, ops)
        return False

    # ============================================================
    # Phase 4.75: Row-level constraint check (zConstraints: check:)
    # Fetch the current row first so fields not in the update payload
    # are still available for cross-field expression evaluation.
    # ============================================================
    current_row = None
    if where:
        try:
            rows = ops.select(table, where=where)
            if rows:
                current_row = rows[0]
        except Exception:  # pylint: disable=broad-except
            pass
    row_errors = check_row_constraints(table, data, table_schema, ops, current_row=current_row)
    if row_errors:
        ops.logger.error(_LOG_VALIDATION_ERROR, table)
        display_validation_errors(table, row_errors, ops)
        surface_errors_to_session(row_errors, ops)
        return False

    # ============================================================
    # Phase 5: Validation
    # ============================================================
    is_valid, errors = ops.validator.validate_update(table, data)
    if not is_valid:
        ops.logger.error(_LOG_VALIDATION_ERROR, table)
        display_validation_errors(table, errors, ops)
        surface_errors_to_session(errors, ops)
        return False

    # ============================================================
    # Phase 5.5: Store blobs (bytes → backend cell) just before persistence
    # ============================================================
    data = store_blob_fields(data, table, table_schema, ops)
    fields = list(data.keys())
    values = list(data.values())

    # ============================================================
    # Phase 6: Update Execution
    # ============================================================
    count = ops.update(table, fields, values, where)
    ops.logger.info(_LOG_SUCCESS, count, table)

    # Release the previous sidecar for any blob field that was overwritten
    # (CSV orphan cleanup; no-op on SQL backends). current_row holds the old cell.
    if count > 0 and current_row:
        for _bf in blob_fields(table_schema):
            if _bf in data and _bf in current_row:
                ops.adapter.delete_blob(table, _bf, current_row[_bf])

    msg = f"[updated] {count} row(s) in {table}"
    ops.display.success(msg)

    # ============================================================
    # Phase 6.5: RETURNING — fetch and display post-update row(s)
    # Uses IDs pre-fetched before the write (handles the edge case
    # where the updated field is also the WHERE filter field).
    # ============================================================
    returned = None
    if returning and pre_fetch_ids:
        returned = _display_returning(table, pre_fetch_ids, returning, ops)

    # ============================================================
    # Phase 7: onAfterUpdate Hook (side effects)
    # ============================================================
    on_after_update = table_schema.get(_HOOK_AFTER_UPDATE)
    if on_after_update:
        ops.logger.info(_LOG_HOOK_AFTER, _HOOK_AFTER_UPDATE, table)
        context = {
            _ZCONV_KEY: data,
            _KEY_TABLE: table,
            _KEY_WHERE: where,
            _KEY_COUNT: count
        }
        ops.execute_hook(on_after_update, context)

    if returning:
        return returned if returned is not None else []

    # Return True if at least one row was updated (count > 0)
    return count > 0
