# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/helpers.py
"""
Shared Helper Facade for zData Operations.

This module is the single import surface every CRUD/DDL operation reaches for
(``from .helpers import ...``). It owns a small set of cross-cutting utilities
directly, and re-exports the rest from focused single-responsibility siblings so
call sites never need to know where a helper physically lives.

═══════════════════════════════════════════════════════════════════════════════
OWNED HERE (validation surfacing + hooks + messaging)
═══════════════════════════════════════════════════════════════════════════════

- display_validation_errors(table, errors, ops)
    Render field validation errors with actionable hints (via ValidationError)
    through zDisplay, and log a summary. Mode-agnostic (Terminal/Walker/Bifrost).

- execute_hook_if_defined(adapter, hook_name, *args, **kwargs)
    Call an optional adapter lifecycle hook (e.g. after_insert) if it exists —
    a no-op otherwise. Centralises the hasattr/getattr dance.

- surface_errors_to_session(errors, ops)
    Persist errors into the zOS session (SESSION_KEY_ZDATA_ERRORS) so the Bifrost
    form-submit handler can show them after a dispatch returns False. No-op in CLI.

- display_success_message(message, ops)
    Emit a mode-agnostic success line, prefixing "[ok]" when absent.

═══════════════════════════════════════════════════════════════════════════════
RE-EXPORTED FROM SIBLING MODULES (SSOT lives there, not here)
═══════════════════════════════════════════════════════════════════════════════

- request_extract.py
    extract_table_from_request  — 3-tier fallback (tables → table → model tail)
                                   + optional existence check.
    extract_where_clause        — dual-source (top-level / options) WHERE,
                                   quote-stripped and parsed.
    extract_field_values        — field/value pairs with reserved control keys
                                   filtered and values type-coerced.

- constraints_check.py
    check_unique_constraints    — single-column + composite unique enforcement.
    check_row_constraints       — cross-field ``zConstraints: check:`` rules.
    _evaluate_ir                — in-memory where-clause IR evaluation (also used
                                   by crud_read for pure-Python filtering).

- write_prep.py
    apply_transforms            — field ``transform:`` normalisation pre-write.
    apply_defaults              — fill omitted/empty fields from ``default:``.

- fk_cascade.py
    handle_on_delete            — referential-integrity enforcement before DELETE
                                   (restrict / cascade / set_null / set_default).
    resolve_fk_scan_tables      — scoped-schema → full-file resolver, shared with
                                   the TRUNCATE FK guard.

═══════════════════════════════════════════════════════════════════════════════
INTEGRATION WITH OTHER SUBSYSTEMS
═══════════════════════════════════════════════════════════════════════════════

- zDisplay: user-friendly, mode-agnostic error/success output.
- zLogger:  debug/error/warning messages for operations.
- zSys.errors: ValidationError (context-aware hints), DatabaseNotInitializedError.

All re-exports are intentional: keeping a stable ``helpers`` import surface means
the physical decomposition below can evolve without touching any call site.
"""

from zOS import Any, Dict
from ..validators.constants import SESSION_KEY_ZDATA_ERRORS

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Request-shape extraction (table / where / field-values) lives in its own module
# (SSOT); re-exported so existing `from .helpers import extract_*` sites keep working.
from .request_extract import (  # pylint: disable=wrong-import-position
    extract_table_from_request, extract_where_clause, extract_field_values,
)
# Constraint enforcement + in-memory row predicate live in their own module (SSOT);
# `_evaluate_ir` is re-exported because crud_read uses it for in-memory filtering.
from .constraints_check import (  # pylint: disable=wrong-import-position,unused-import
    check_unique_constraints, check_row_constraints, _evaluate_ir,
)
# FK referential-integrity engine lives in its own module (SSOT); re-exported here
# so existing `from .helpers import handle_on_delete` call sites keep working.
from .fk_cascade import (  # pylint: disable=wrong-import-position
    handle_on_delete, resolve_fk_scan_tables,
)
# Pre-write payload prep (transforms + defaults) lives in its own module (SSOT);
# re-exported so existing `from .helpers import apply_transforms` sites keep working.
from .write_prep import (  # pylint: disable=wrong-import-position
    apply_transforms, apply_defaults, normalize_write_values,
)

# ────────────────────────────────────────────────────────────────────────────
# Error / Log Messages (validation surfacing)
# ────────────────────────────────────────────────────────────────────────────
_ERR_VALIDATION_FAILED_LOG = "[FAIL] Validation failed for table '%s' with %d error(s)"
_LOG_VALIDATION_SUMMARY = "[FAIL] Validation summary: %d field(s) failed for table '%s'"

# ────────────────────────────────────────────────────────────────────────────
# Special Values
# ────────────────────────────────────────────────────────────────────────────
_VALUE_PLACEHOLDER = "<provided value>"  # Placeholder for ValidationError when actual value unavailable

# ────────────────────────────────────────────────────────────────────────────
# Success Messages
# ────────────────────────────────────────────────────────────────────────────
_MSG_SUCCESS = "[ok] %s"  # Generic success message template

# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────
__all__ = [
    "extract_table_from_request",
    "extract_where_clause",
    "extract_field_values",
    "display_validation_errors",
    "execute_hook_if_defined",
    "display_success_message",
    "check_unique_constraints",
    "check_row_constraints",
    "surface_errors_to_session",
    "apply_transforms",
    "apply_defaults",
    "normalize_write_values",
    "handle_on_delete",
    "resolve_fk_scan_tables",
]


def display_validation_errors(
    table: str,
    errors: Dict[str, str],
    ops: Any
) -> None:
    """
    Display validation errors with actionable hints using ValidationError exception.
    
    This function displays field validation errors to the user with context-aware
    actionable hints by leveraging the ValidationError exception. Each error is
    raised and caught to generate formatted error messages with hints, then
    displayed using zDisplay for mode-agnostic output.
    
    ValidationError Integration:
        Each field error is raised as a ValidationError exception to generate:
        - Formatted error message with field, value, and constraint
        - Context-aware actionable hint based on constraint type
        - Schema name for context
    
    Display Integration:
        Errors are displayed using ops.display.write_line() for mode-agnostic
        output (works in Terminal, Walker, and Bifrost modes). Each error is
        displayed with blank lines for readability.
    
    Logger Integration:
        - Error level: Summary of total errors
        - Debug level: Detailed validation summary
    
    Args:
        table: Table name where validation failed (used for schema_name context)
        errors: Dictionary mapping field names to error messages
                Example: {"email": "Pattern mismatch", "age": "Value out of range"}
        ops: Operations context with logger and display
    
    Returns:
        None: Displays errors and logs summary (no return value)
    
    Examples:
        # Display validation errors for multiple fields
        errors = {
            "email": "Pattern mismatch: must match email format",
            "age": "Value out of range: must be >= 18"
        }
        display_validation_errors("users", errors, ops)
        
        # Logs:
        # [FAIL] Validation failed for table 'users' with 2 error(s)
        # [FAIL] Validation summary: 2 field(s) failed for table 'users'
        
        # Displays:
        # 
        # [ValidationError] Field 'email' validation failed: Pattern mismatch
        # Hint: Check the field format requirements in the schema
        # 
        # 
        # [ValidationError] Field 'age' validation failed: Value out of range
        # Hint: Check the numeric range constraints in the schema
        # 
    
    Notes:
        - Uses ValidationError exception for formatted error messages
        - Value placeholder "<provided value>" used (actual value not available)
        - Each error displayed with blank lines for readability
        - Logger used for error/debug messages (not displayed to user)
        - zDisplay integration ensures mode-agnostic output
    """
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1: Import - Get ValidationError exception
    # ─────────────────────────────────────────────────────────────────────────
    from zSys.errors import ValidationError

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2: Log Summary - Record validation failure
    # ─────────────────────────────────────────────────────────────────────────
    ops.logger.error(_ERR_VALIDATION_FAILED_LOG, table, len(errors))

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 3: Display Errors - Show each error with actionable hints
    # ─────────────────────────────────────────────────────────────────────────
    for field, message in errors.items():
        try:
            # Raise ValidationError to get actionable hints
            raise ValidationError(
                field=field,
                value=_VALUE_PLACEHOLDER,  # Actual value not available here
                constraint=message,
                schema_name=table
            )
        except ValidationError as e:
            # Display the formatted error with hint (mode-agnostic via zDisplay)
            ops.display.write_line("")
            ops.display.write_line(str(e))
            ops.display.write_line("")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 4: Log Details - Record validation summary for debugging
    # ─────────────────────────────────────────────────────────────────────────
    ops.logger.debug(_LOG_VALIDATION_SUMMARY, len(errors), table)

def execute_hook_if_defined(
    adapter: Any,
    hook_name: str,
    *args,
    **kwargs
) -> None:
    """
    Execute adapter hook method if it exists (DRY helper).
    
    Eliminates 4 occurrences of "if hasattr(adapter, hook_name)" checks across
    CRUD operations by providing a centralized hook execution pattern.
    
    Args:
        adapter: Backend adapter instance
        hook_name: Name of the hook method to execute (e.g., "after_insert")
        *args: Positional arguments to pass to the hook
        **kwargs: Keyword arguments to pass to the hook
    
    Examples:
        >>> # Instead of:
        >>> if hasattr(adapter, "after_insert"):
        >>>     adapter.after_insert(table, row_id)
        >>> 
        >>> # Use:
        >>> execute_hook_if_defined(adapter, "after_insert", table, row_id)
    
    Notes:
        - No-op if hook doesn't exist (safe to call)
        - Uses getattr with hasattr for safe method lookup
        - Supports both args and kwargs forwarding
    """
    if hasattr(adapter, hook_name):
        hook = getattr(adapter, hook_name)
        hook(*args, **kwargs)

def surface_errors_to_session(errors: Dict[str, str], ops: Any) -> None:
    """
    Persist validation / unique-constraint errors into the zOS session so the
    Bifrost WebSocket handler can surface them to the frontend after dispatch
    returns False.

    Key: ``SESSION_KEY_ZDATA_ERRORS`` (``"_zdata_errors"``)
    Lifetime: consumed once by the Bifrost form-submit handler.

    No-op when a session is not available (e.g. pure zCLI context).
    """
    if not (ops.zos and hasattr(ops.zos, "session") and isinstance(ops.zos.session, dict)):
        return
    ops.zos.session[SESSION_KEY_ZDATA_ERRORS] = [
        f"{field}: {msg}" for field, msg in errors.items()
    ]


def display_success_message(
    message: str,
    ops: Any
) -> None:
    """
    Display success message in mode-agnostic way (DRY helper).
    
    Eliminates 11 occurrences of "ops.display.success()" checks across CRUD
    operations by providing a centralized success display pattern.
    
    Args:
        message: Success message to display
        ops: Operations context with display
    
    Examples:
        >>> # Instead of:
        >>> ops.display.success(f"[ok] Inserted row into {table} with ID: {row_id}")
        >>> 
        >>> # Use:
        >>> display_success_message(f"Inserted row into {table} with ID: {row_id}", ops)
    
    Notes:
        - Uses ops.display.success() for mode-agnostic output
        - Automatically prefixes message with checkmark ([ok]) if not present
        - Works in Terminal, Walker, and Bifrost modes
    """
    # Add checkmark prefix if not present
    if not message.startswith("[ok]"):
        message = _MSG_SUCCESS % message
    ops.display.success(message)
