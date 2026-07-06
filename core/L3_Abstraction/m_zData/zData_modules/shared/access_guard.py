# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/access_guard.py
"""
Authoritative data-layer access guard (zRBAC enforcement).

zOS access control is declared once via a ``zRBAC`` block (SSOT vocabulary +
decision live in f_zAuth). The wizard/dispatch RBAC gates are *presentational /
render-time*; this guard is the **authoritative** re-check that runs inside
zData before any declarative request reads or mutates data. It closes the gap
flagged by the zWizard audit (V3): a Bifrost gate continuation (form submit →
write) can reach the data layer without re-traversing the render gate, so the
data layer must enforce access itself.

Design:
    - Fail-closed: when a table/schema declares a ``zRBAC`` requirement but no
      auth subsystem is present, access is DENIED.
    - Backward compatible: schemas with no ``zRBAC`` are public and incur zero
      auth calls (the guard returns immediately).
    - Scope: gates the declarative entry (``handle_request``) used by dispatch,
      wizard, and zAPI. The auth subsystem's own bootstrap (login reads, the
      permissions table writes) uses direct ``zos.data.*`` primitives and is
      intentionally NOT routed through here, so there is no chicken-and-egg.

The decision itself (auth/role/permission, context-aware) is single-sourced in
``zos.auth.check_data_access`` — this module only resolves the target table and
the action's access category, then delegates.
"""

from zOS import Any, Dict, Optional

from .operations.helpers import extract_table_from_request
from .data_keys import SCHEMA_KEY_META as _RESERVED_META

# Declarative keyword (language-level, mirrors how `zMeta` is referenced across
# subsystems). The zRBAC field names and the allow/deny decision are owned by
# f_zAuth; this guard only needs to detect *presence* of a requirement so it can
# fail closed when auth is unavailable.
_ZRBAC_KEY = "zRBAC"

# Action → access category. Anything that writes maps to "write"; everything
# else (read/head/aggregate/window/list_tables) is a read. Used for optional
# per-category zRBAC overrides (`zRBAC.actions.write` / `.read`).
_WRITE_ACTIONS = frozenset({
    "insert", "update", "delete", "upsert", "truncate", "drop", "create",
    "migrate", "set",
})
_CATEGORY_WRITE = "write"
_CATEGORY_READ = "read"

_AUTH_METHOD = "check_data_access"
_LOG_DENIED = "[zData][RBAC] Access denied (action=%s table=%s): %s"
_REASON_NO_AUTH = "zRBAC declared but no auth subsystem available (fail-closed)"


def _category_for(action: Optional[str]) -> str:
    """Classify a data action into the read/write category bucket."""
    return _CATEGORY_WRITE if action in _WRITE_ACTIONS else _CATEGORY_READ


def _declares_zrbac(meta: Any) -> bool:
    """True when a schema fragment carries a usable ``zRBAC`` block."""
    return isinstance(meta, dict) and isinstance(meta.get(_ZRBAC_KEY), dict)


def enforce_access(
    request: Dict[str, Any],
    action: Optional[str],
    orchestrator: Any,
    zos: Any,
    logger: Any,
) -> bool:
    """
    Authoritatively enforce ``zRBAC`` for a declarative data request.

    Args:
        request: The data request dict (model/tables/action/options/...).
        action: The resolved action verb for this request.
        orchestrator: DataOrchestrator (provides ``schema`` and ``operations``).
        zos: zOS framework instance (for the auth subsystem).
        logger: Logger for security audit of denials.

    Returns:
        True if the request may proceed, False if access is denied.
    """
    schema = getattr(orchestrator, "schema", None)
    if not isinstance(schema, dict):
        # No loaded schema to enforce against — nothing declared, allow.
        return True

    # Resolve the target table WITHOUT side effects: no existence check, never
    # raise (a failed resolution must not crash the gate — it just means no
    # table-level rule applies and we fall back to the schema-level default).
    table: Optional[str] = None
    try:
        table = extract_table_from_request(
            request, action or "", orchestrator.operations, check_exists=False
        )
    except Exception:  # pylint: disable=broad-except
        table = None

    table_meta = schema.get(table) if table else None
    schema_meta = schema.get(_RESERVED_META)

    # No declared requirement anywhere → public (backward compatible, no auth).
    if not _declares_zrbac(table_meta) and not _declares_zrbac(schema_meta):
        return True

    # A requirement exists → the auth subsystem is mandatory. Fail closed.
    auth = getattr(zos, "auth", None)
    if auth is None or not hasattr(auth, _AUTH_METHOD):
        logger.error(_LOG_DENIED, action, table or "?", _REASON_NO_AUTH)
        return False

    allowed, reason = auth.check_data_access(
        table_meta, schema_meta, action, _category_for(action)
    )
    if not allowed:
        logger.warning(_LOG_DENIED, action, table or "?", reason)
    return allowed
