# zOS/core/L2_Core/d_zAuth/zAuth_modules/auth_login.py
"""
Built-in zLogin Action - Schema-Driven Authentication (v1.5.7+)

═══════════════════════════════════════════════════════════════════════════════
OVERVIEW
═══════════════════════════════════════════════════════════════════════════════

This module provides a built-in zLogin action for declarative authentication
without requiring application-specific plugin code. It auto-discovers user table
structure from zSchema and automatically creates multi-app session structures.

Key Features:
    - Schema-driven: Auto-discovers table, fields, and hash type from zSchema
    - Zero configuration: No plugin code required
    - Multi-app support: Automatically creates/updates app sessions
    - Dual-mode aware: Detects and enables dual-mode if zSession exists
    - Declarative: Works in both Terminal and Bifrost modes

Usage:
    # In zUI.zLogin.yaml
    onSubmit:
        zLogin: "zCloud"  # App name (creates applications["zCloud"])
    
    # For Zolo platform authentication
    onSubmit:
        zLogin: "zolo"  # Reserved keyword for zSession authentication

Auto-Discovery from zSchema:
    - Table name: Extracted from model path (e.g., "@.models.zSchema.contacts" → "contacts")
    - Identity field: Auto-detects "email" or "username"
    - Password field: Always "password"
    - Hash type: Detects "zHash: bcrypt" from schema
    - Role field: Auto-detects "role" field
    - Additional fields: All non-password fields stored in session

═══════════════════════════════════════════════════════════════════════════════
"""

import os

import bcrypt

from zOS import Any, Dict
from zOS.L1_Foundation.a_zConfig.zConfig_modules import (
    SESSION_KEY_ZVISITOR,
    SESSION_KEY_ZMODE,
    ZMODE_ZBIFROST,
    ZAUTH_KEY_AUTHENTICATED,
    ZAUTH_KEY_ID,
    ZAUTH_KEY_USERNAME,
    ZAUTH_KEY_ROLE,
    ZAUTH_KEY_API_KEY,
)
from zOS.L1_Foundation.a_zConfig.zConfig_modules.session.config_session import SessionConfig

# Constants
# Import centralized constants
from ..auth_constants import (
    # Public constants
    DEFAULT_IDENTITY_FIELDS,
    DEFAULT_PASSWORD_FIELD,
    DEFAULT_ROLE_FIELD,
    DEFAULT_ROLE,
    RESERVED_ZOLO_KEYWORD,
    # Internal constants (private)
    _LOG_PREFIX_LOGIN,
)

# Module uses _LOG_PREFIX_LOGIN as LOG_PREFIX for compatibility
LOG_PREFIX = _LOG_PREFIX_LOGIN


def handle_zLogin(
    app_or_type: str,
    zConv: Dict[str, Any],
    zContext: Dict[str, Any],
    zos: Any
) -> Dict[str, Any]:
    """
    Built-in zLogin handler - auto-discovers authentication from schema.
    
    This is the main entry point for declarative authentication in zOS.
    It requires NO plugin code - everything is auto-discovered from the
    zSchema model specified in the zDialog.
    
    Args:
        app_or_type: Application name (e.g., "zCloud") or "zolo" for platform auth
        zConv: Form data collected from zDialog (e.g., {"email": "...", "password": "..."})
        zContext: Dialog context containing model path and schema info
        zos: zOS instance (provides data, loader, session, logger access)
    
    Returns:
        Dict[str, Any]: Response dict for form rendering
            - success (bool): True if authentication successful
            - message (str): Success/error message for user feedback
            - redirect (str): Optional redirect URL (future feature)
    
    Raises:
        ValueError: If model is not specified in zContext (required for auto-discovery)
        Exception: If database query or password verification fails
    
    Examples:
        # Application authentication (zCloud app)
        >>> result = handle_zLogin("zCloud", {"email": "user@example.com", "password": "pass"}, zContext, zos)
        >>> # Creates: session[zAuth][applications]["zCloud"] = {...}
        
        # Zolo platform authentication (zSession)
        >>> result = handle_zLogin("zolo", {"username": "admin", "password": "pass"}, zContext, zos)
        >>> # Creates: session[zAuth][zSession] = {...}
    
    Auto-Discovery Process:
        1. Extract model path from zContext (e.g., "@.models.zSchema.contacts")
        2. Load schema via zos.loader.handle()
        3. Extract table name from model path → "contacts"
        4. Auto-detect identity field (email or username) from zConv keys
        5. Query user table: zos.data.select(table, where={identity_field: value})
        6. Verify password using bcrypt.checkpw()
        7. Create/update app session structure in session[zAuth][applications][app_name]
        8. Set active_context and active_app
        9. Detect dual-mode if zSession also authenticated
    
    Session Structure Created:
        session[SESSION_KEY_ZVISITOR][ZAUTH_KEY_APPLICATIONS][app_name] = {
            ZAUTH_KEY_AUTHENTICATED: True,
            ZAUTH_KEY_ID: user["id"],
            ZAUTH_KEY_USERNAME: user["name"] or user["email"],
            ZAUTH_KEY_ROLE: user["role"] or "zUser",
            ...additional_user_fields  # All non-password fields from user record
        }
    
    Notes:
        - Requires zDialog to specify 'model' starting with '@' (schema reference)
        - Password field is never stored in session (excluded automatically)
        - All other user fields are stored for app use (e.g., company, phone, etc.)
        - Multi-app: Multiple apps can be authenticated simultaneously
        - Dual-mode: Auto-detected if both zSession and app are authenticated
    """
    logger = zos.logger
    logger.info(f"{LOG_PREFIX} Authentication request for: {app_or_type}")

    # One zOS instance = one signed-in caller. Both the reserved "zolo" keyword
    # and any app name authenticate against the same ledger and write the single
    # session["zVisitor"]; the label only changes the success-response wording.
    label = None if app_or_type.lower() == RESERVED_ZOLO_KEYWORD else app_or_type
    model = (zContext or {}).get("model") or _default_auth_model()

    user, identity_field, fail = _lookup_and_verify_user(model, zConv, zos, logger)
    if user is None:
        return _login_failure(zos, fail)

    username, role = _apply_zvisitor(user, identity_field, zos, logger)
    logger.info(f"{LOG_PREFIX} Sign-in successful for {username} (role={role})")
    return _login_success_response(zos, username, role, label)


def authenticate_zolo_credentials(
    zConv: Dict[str, Any],
    zos: Any,
    model: Any = None,
) -> Any:
    """Programmatic sign-in — verify + write the single zVisitor, no UI.

    Headless sibling of the declarative ``zLogin`` handler for callers that must
    NOT emit display side-effects. Returns the resolved role, or ``None``.
    """
    logger = zos.logger
    user, identity_field, _fail = _lookup_and_verify_user(
        model or _default_auth_model(), zConv, zos, logger
    )
    if user is None:
        return None
    _username, role = _apply_zvisitor(user, identity_field, zos, logger)
    return role


def _apply_zvisitor(user: Dict[str, Any], identity_field: str, zos: Any, logger: Any):
    """Write the verified user into the single session["zVisitor"].

    SSOT for establishing the signed-in identity — shared by the declarative
    ``zLogin`` handler and the headless ``authenticate_zolo_credentials``.
    Returns ``(username, role)``.
    """
    role = _resolve_user_role(user, zos, logger)
    zos.session[SESSION_KEY_ZVISITOR] = {
        ZAUTH_KEY_AUTHENTICATED: True,
        ZAUTH_KEY_ID: user.get("id"),
        ZAUTH_KEY_USERNAME: user.get("name", user.get(identity_field)),
        ZAUTH_KEY_ROLE: role,
        ZAUTH_KEY_API_KEY: user.get(ZAUTH_KEY_API_KEY),
    }

    _post_login_refresh(zos, logger)
    _persist_cookie_identity(zos)

    return zos.session[SESSION_KEY_ZVISITOR][ZAUTH_KEY_USERNAME], role


def _persist_cookie_identity(zos: Any) -> None:
    """Mirror the just-written identity into the session_store under the caller's zsid.

    Cookie-bound identity write-through (ZAUTH_INSTANCE.notes.md §19.L) — the single
    seam BOTH login tiers (zSession + application) call after writing
    ``session[zAuth]``. If the transport stamped a durable ``_zsid`` on this caller's
    unit, a hard reload / new tab carrying that cookie rehydrates signed-in.
    """
    try:
        zsid = zos.session.get("_zsid")
        if zsid:
            from zOS.L1_Foundation.a_zConfig.zConfig_modules.session import (  # type: ignore[reportMissingImports]
                session_cookie as _sc,
            )
            _sc.persist_identity(zos, zsid, zos.session)
    except Exception:  # pylint: disable=broad-except
        pass


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _lookup_and_verify_user(
    model: Any,
    zConv: Dict[str, Any],
    zos: Any,
    logger: Any,
):
    """Resolve the user-ledger model, find the identity row, verify its password.

    The single credential-verification path shared by the application (Tier-2)
    and Zolo-platform (Tier-1) logins — one SSOT against the zSchema user ledger.
    Today this reads the ledger directly (dev/local); the remote-authority swap
    lives in login_manager's remote path.

    Returns:
        (user, identity_field, None) on success;
        (None, None, "credentials" | "error") on failure (already logged).
    Raises:
        ValueError: if ``model`` is missing or not a schema reference ('@...').
    """
    if not model:
        error_msg = "zLogin requires 'model' in zDialog for schema auto-discovery"
        logger.error(f"{LOG_PREFIX} {error_msg}")
        raise ValueError(error_msg)
    if not model.startswith('@'):
        error_msg = f"zLogin requires schema reference (model starting with '@'), got: {model}"
        logger.error(f"{LOG_PREFIX} {error_msg}")
        raise ValueError(error_msg)

    table_name = _extract_table_name(model)
    logger.debug(f"{LOG_PREFIX} Auto-detected table: {table_name}")

    identity_field = identity_value = None
    for field in DEFAULT_IDENTITY_FIELDS:
        if field in zConv:
            identity_field, identity_value = field, zConv[field]
            break
    if not identity_field:
        logger.error(f"{LOG_PREFIX} No identity field. Expected one of: {DEFAULT_IDENTITY_FIELDS}")
        return None, None, "credentials"

    password = zConv.get(DEFAULT_PASSWORD_FIELD)
    if not password:
        logger.error(f"{LOG_PREFIX} Password field required")
        return None, None, "credentials"

    # Establish DB connection for this session (per-session zos.data starts unconnected).
    try:
        schema = zos.loader.handle(model)
        zos.data.load_schema(schema)
    except Exception as _schema_err:  # pylint: disable=broad-except
        logger.warning(f"{LOG_PREFIX} Schema pre-load warning: {_schema_err}")

    try:
        result = zos.data.select(table_name, where={identity_field: identity_value})
        if not result or len(result) == 0 or result == "error":
            logger.warning(f"{LOG_PREFIX} No user found for {identity_field}={identity_value}")
            return None, None, "credentials"
        user = result[0]
        logger.debug(f"{LOG_PREFIX} User found: ID={user.get('id')}")
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"{LOG_PREFIX} Database query failed: {e}", exc_info=True)
        return None, None, "error"

    stored_hash = user.get(DEFAULT_PASSWORD_FIELD)
    if not stored_hash:
        logger.error(f"{LOG_PREFIX} No password hash found for user {identity_value}")
        return None, None, "credentials"
    try:
        if not bcrypt.checkpw(password.encode('utf-8'), str(stored_hash).encode('utf-8')):
            logger.warning(f"{LOG_PREFIX} Password verification failed for {identity_value}")
            return None, None, "credentials"
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"{LOG_PREFIX} Password verification error: {e}", exc_info=True)
        return None, None, "error"

    logger.info(f"{LOG_PREFIX} Password verified successfully for {identity_value}")
    return user, identity_field, None


def _resolve_user_role(user: Dict[str, Any], zos: Any, logger: Any) -> str:
    """Resolve a user's role: direct ``role`` field, else users→user_roles→roles join."""
    user_role = user.get(DEFAULT_ROLE_FIELD)
    if not user_role:
        try:
            user_id = int(user.get("id"))
            user_roles_result = zos.data.select("user_roles", where={"user_id": user_id})
            if user_roles_result and len(user_roles_result) > 0:
                role_id = int(user_roles_result[0].get("role_id"))
                roles_result = zos.data.select("roles", where={"id": role_id})
                if roles_result and len(roles_result) > 0:
                    user_role = roles_result[0].get("name")
                    logger.debug(f"{LOG_PREFIX} Role lookup: user_id={user_id} → role={user_role}")
        except Exception as e:  # pylint: disable=broad-except
            logger.debug(f"{LOG_PREFIX} Role lookup failed: {e}, using default")
    return user_role or DEFAULT_ROLE


def _login_failure(zos: Any, fail_kind: Any) -> Any:
    """Standard login-failure response (mode-aware), preserving prior UX.

    ``error`` → generic system error; anything else → invalid credentials.
    Bifrost returns a dict; Terminal displays + returns None (retry-friendly).
    """
    msg = "Authentication system error" if fail_kind == "error" else "Invalid login credentials"
    if _is_bifrost_mode(zos):
        return {"success": False, "message": msg}
    zos.display.error(msg)
    return None


def _login_success_response(zos: Any, username: Any, role: Any, app_name: Any = None) -> Any:
    """Standard login-success response (mode-aware)."""
    if _is_bifrost_mode(zos):
        resp = {
            "success": True,
            "message": f"Welcome back, {username}!",
            "username": username,
            "role": role,
        }
        if app_name:
            resp["app"] = app_name
        return resp
    zos.display.success(f"[ok] Welcome back, {username}! (Role: {role})")
    return True  # Truthy for the ! modifier retry logic in Terminal mode.


def _post_login_refresh(zos: Any, logger: Any) -> None:
    """Post-login housekeeping shared by both tiers: regenerate session_hash
    (frontend cache invalidation) and drop parsed-UI caches so the navbar/RBAC
    re-evaluate for the newly authenticated identity."""
    try:
        SessionConfig.regenerate_session_hash(zos.session)
    except Exception as e:  # pylint: disable=broad-except
        logger.debug(f"{LOG_PREFIX} session_hash regen skipped: {e}")

    if hasattr(zos, 'loader') and hasattr(zos.loader, 'cache') and hasattr(zos.loader.cache, 'system_cache'):
        try:
            cache_dict = zos.loader.cache.system_cache._cache  # pylint: disable=protected-access
            cleared = 0
            for key in list(cache_dict.keys()):
                if key.startswith('parsed:') and ('.zUI.' in key or '/zUI/' in key or '/UI/' in key):
                    del cache_dict[key]
                    cleared += 1
            if cleared:
                logger.debug(f"{LOG_PREFIX} Cleared {cleared} cached UI file(s) for RBAC re-evaluation")
        except Exception as e:  # pylint: disable=broad-except
            logger.debug(f"{LOG_PREFIX} Could not clear UI cache: {e}")


def _extract_table_name(model_path: str) -> str:
    """
    Extract table name from model path.
    
    Examples:
        "@.models.zSchema.contacts" → "contacts"
        "@.zSchema.users" → "users"
        "zSchema.products" → "products"
    
    Args:
        model_path: Schema model path (e.g., "@.models.zSchema.contacts")
    
    Returns:
        str: Table name (last component of path)
    """
    # Split by '.' and take last component
    parts = model_path.split('.')
    return parts[-1]


def _is_bifrost_mode(zos: Any) -> bool:
    """
    Check if current mode is Bifrost (GUI).
    
    Args:
        zos: zOS instance
        
        Returns:
        bool: True if Bifrost mode, False if Terminal mode
    """
    return zos.session.get(SESSION_KEY_ZMODE) == ZMODE_ZBIFROST


# ============================================================================
# zLogin BLOCK PRIMITIVE (new declarative form)
# ============================================================================

# Generic fallback when the app declares no ZAUTH_USER_MODEL in zEnv.
_FALLBACK_AUTH_MODEL = "@.models.zSchema.users"


def _default_auth_model() -> str:
    """Resolve the user/identity ledger model declaratively (SSOT).

    zOS never bakes a table name: the app's zEnv declares ``ZAUTH_USER_MODEL``
    (loaded into os.environ), and this is the one place every credential path
    falls back to when a caller passes no explicit model. Absent that key, use
    the generic ``zSchema.users`` so non-zCloud apps keep working unchanged.
    """
    return os.getenv("ZAUTH_USER_MODEL") or _FALLBACK_AUTH_MODEL


def expand_zLogin_block(login_config: Dict[str, Any], zos: Any) -> Dict[str, Any]:
    """
    Expand the zLogin block shorthand into its canonical zDialog event.

    zLogin is a zForm — a dispatch event that composes existing, already
    mode-wired primitives. Its body is sugar over a zDialog whose onSubmit
    runs the zAuth `zLogin` action:

        zLogin:                          →   zDialog:
            title: Sign in to zCloud            title: Sign in to zCloud
            model: @.models.zSchema.users       model: @.models.zSchema.users
            fields: [email, password]           fields: [email, password]
            onSuccess: {zLink: ...}             onSubmit:
                                                    zLogin: <app>

    The onSuccess follow-up is NOT part of the dialog — it is dispatched by
    the caller once the session is established (CLI: after dialog returns;
    Bifrost: after handle_form_submit's zLogin success).

    This reuses zDialog wholesale (no reinvented prompting/rendering) — the
    SSOT for credential collection in both CLI and Bifrost.
    """
    app_name = _resolve_block_app_name(login_config.get("zApp"), zos)
    dialog: Dict[str, Any] = {
        "title": login_config.get("title", "Sign in"),
        "onSubmit": {"zLogin": app_name},
    }
    model = login_config.get("model")
    if model:
        dialog["model"] = model
    # `fields` is preferred (matches zDialog grammar); `inputs` is an alias.
    fields = login_config.get("fields") or login_config.get("inputs")
    if fields:
        dialog["fields"] = fields
    return dialog


def handle_zLogin_block(
    login_config: Dict[str, Any],
    zos: Any,
    walker: Any = None,
) -> Any:
    """
    Handle the zLogin block dispatch event.

    Composition (no new mechanics):
        1. FORM   — dispatch the expanded zDialog (zAuth `zLogin` on submit)
        2. AUTH   — handled inside the dialog's onSubmit (existing zAuth action)
        3. FOLLOW-UP — on a successful default session login, dispatch onSuccess

    In Bifrost the dialog renders via the walker chunk pipeline and submits
    through handle_form_submit; this returns None so the block is not executed
    synchronously. In CLI the dialog prompts inline and returns the auth result,
    after which the onSuccess zEvent is dispatched.
    """
    if _is_bifrost_mode(zos):
        # Bifrost: dialog is rendered/expanded in the walker pipeline and the
        # onSuccess follow-up fires from handle_form_submit after auth.
        return None

    logger = zos.logger if hasattr(zos, "logger") else None
    dialog = expand_zLogin_block(login_config, zos)

    # FORM + AUTH: reuse zDialog (collects credentials, runs onSubmit zLogin).
    from zOS.L2_Handling.g_zDispatch import handle_zDispatch  # pylint: disable=import-outside-toplevel
    result = handle_zDispatch("zDialog", dialog, zos=zos, walker=walker, context={})

    # FOLLOW-UP: dispatch onSuccess once the session is established. Its
    # result REPLACES the dialog's own return — a zLink onSuccess stages a
    # trampoline navigate signal (zNavigation.navigate_or_recurse) that the
    # sequential walker's key loop only honors when it's the value returned
    # for THIS step; swallowing it here (returning the dialog's plain login
    # result instead) breaks the chain and the walk falls through to the
    # next sibling key (e.g. a "Back" button) instead of landing on target.
    if result:
        on_success = login_config.get("onSuccess")
        if on_success is not None:
            nav_result = _dispatch_on_success(on_success, zos, walker, logger)
            if nav_result is not None:
                return nav_result
    return result


def _dispatch_on_success(on_success: Any, zos: Any, walker: Any, logger: Any) -> Any:
    """
    Dispatch the onSuccess zEvent after a successful login.

    onSuccess is a full zEvent (not a bare path), e.g.:
        onSuccess:                       # nested zEvent dict (preferred)
            zLink: @.UI.zUI.zVaF.zVaF
        onSuccess: zLink(@.UI.zUI.zVaF.zVaF)   # string call form (legacy)
        onSuccess:
            zFunc: refresh_dashboard     # any nested event

    Routed through the zDispatch facade so onSuccess can hold ANY nested
    zEvent (mirrors zDialog onSubmit semantics) — not just navigation.
    """
    try:
        from zOS.L2_Handling.g_zDispatch import handle_zDispatch  # pylint: disable=import-outside-toplevel
        return handle_zDispatch("onSuccess", on_success, zos=zos, walker=walker, context={})
    except Exception as nav_err:  # pylint: disable=broad-except
        if logger:
            logger.warning(f"[zLogin block] onSuccess dispatch failed: {nav_err}")
        return None


def _resolve_block_app_name(zapp: Any, zos: Any) -> str:
    """
    Resolve the app identity for session scoping (SSOT: resolve_app_id).

    Identity derives from zSpark `title`; `zApp` (block or spark) is a deprecated
    optional override. Precedence: block zApp → spark zApp → title → zVaFile stem.
    """
    try:
        from zOS.L1_Foundation.a_zConfig.zConfig_modules.helpers.config_helpers import (  # pylint: disable=import-outside-toplevel
            resolve_app_id,
        )
        zspark = getattr(zos, "zspark_obj", None) or {}
        block_zapp = zapp if isinstance(zapp, str) and zapp else None
        return resolve_app_id(zspark, block_zapp=block_zapp)
    except Exception:  # pylint: disable=broad-except
        return zapp if isinstance(zapp, str) and zapp else "app"
