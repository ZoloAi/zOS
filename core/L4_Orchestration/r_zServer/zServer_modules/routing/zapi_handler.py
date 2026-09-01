# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/zapi_handler.py

"""
zAPI Handler — serve discovered zAPI endpoints as JSON REST APIs.

For each zAPI route the flow is:

  1. Method guard (405 if wrong verb)
  2. CORS preflight (OPTIONS → 204)
  3. Auth validation  (X-API-Key / Bearer token against auth_model)
  4. Parse request params  (GET → query-string, POST/PUT → JSON body)
  5. Resolve zConv.* placeholders in the zData config (reuse inject_placeholders)
  6. Execute zData via zos.data.handle_request() in silent mode
  7. Return {"ok": true, "data": <result>} as JSON
"""

import copy
import json
from urllib.parse import urlparse, parse_qs


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def handle(handler, route: dict, zos) -> None:
    """
    Dispatch a zAPI HTTP request.

    zAPI is the HTTP front-end onto zOS handlers — it is NOT a feature of zData.
    The flow is transport-agnostic:

        parse request  →  execute inner handler (by kind)  →  ZResult  →  serialise

    The `kind` selects which subsystem runs the request (zData today; zFunc and
    others wired in subsequent phases). Every kind returns a ``ZResult`` so the
    JSON envelope — and the feedback the zAgent sees — is uniform.

    Args:
        handler:  BaseHTTPRequestHandler instance (provides send_response, etc.)
        route:    Route dict from HTTPRouter (type="zAPI", includes kind + config)
        zos:      zOS instance (provides data, logger, loader)
    """
    method = handler.command.upper()

    # CORS preflight
    if method == "OPTIONS":
        _send_json(handler, 204, None, cors=True)
        return

    # HEAD is GET's shadow (RFC 7231): same guard, same execution — the
    # transport layer strips the body (see handler.do_HEAD / end_headers).
    if method == "HEAD":
        method = "GET"

    method_allowed = route.get("method", "GET").upper()
    if method != method_allowed:
        _send_json(handler, 405, {"error": f"Method not allowed. Expected {method_allowed}."})
        return

    zapi_config = route.get("zapi_config", {})

    # --- Auth ---------------------------------------------------------------
    if not _validate_auth(handler, zapi_config, zos):
        return

    # --- Parse params (text fields + uploaded files) ------------------------
    try:
        params, files = _parse_params(handler, method, zos)
    except Exception as exc:
        _send_json(handler, 400, {"error": f"Bad request body: {exc}"})
        return

    # Path params (%id / :id captured by the router for a hand-declared zAPI
    # route) join the query/body params uniformly, so a resource can be located
    # by URL segment: zData reads them as zConv.*, zFunc via the `params` provider.
    # The path segment is the canonical resource locator, so it wins on collision.
    route_params = route.get("_route_params") or {}
    if route_params:
        params = {**params, **route_params}

    # --- Execute inner handler (by kind) → ZResult --------------------------
    kind = route.get("kind", "zData")
    vars_before = _snapshot_session_vars(zos)
    try:
        if kind == "zData":
            zres = _execute_zdata(route, params, zos)
        elif kind == "zFunc":
            zres = _execute_zfunc(route, params, files, handler, zos)
        elif kind in ("zLogin", "zDialog"):
            zres = _execute_flow(route, params, zos)
        else:
            _send_json(handler, 500, {"error": f"Unsupported zAPI handler kind: {kind}"})
            return
    except Exception as exc:
        zos.logger.error(f"[zAPI] {kind} execution failed: {exc}", exc_info=True)
        _send_json(handler, 500, {"error": "Internal server error"})
        return

    # Write-through zVars the handler mutated (zOS#21). The request unit
    # RESTORED stored zVars at entry (zOS#94), and the WS path persists at the
    # zVar-write SSOT — but a plugin writing session['zVars'] directly over
    # zAPI had no persist site, so state died with the request and the next
    # call saw none of it (arm → guess flows broke). Persist only on change.
    _persist_session_vars(zos, vars_before)

    # --- Serialise ----------------------------------------------------------
    # A handler may return a RAW binary body (ZResult.binary) — a file, an image,
    # any non-JSON payload. Detected generically via ``is_binary`` and written
    # verbatim under its content-type instead of the JSON envelope.
    if getattr(zres, "is_binary", False):
        zos.logger.info(f"[zAPI] {method} {handler.path} → {zres.status}  (kind={kind}, binary)")
        _send_binary(handler, zres)
        return

    if kind == "zData":
        status_out, payload = _serialize_zdata(zres)
    else:
        status_out, payload = zres.to_http()

    zos.logger.info(f"[zAPI] {method} {handler.path} → {status_out}  (kind={kind})")
    _send_json(handler, status_out, payload, cors=True)


# ---------------------------------------------------------------------------
# Session write-through (zOS#21)
# ---------------------------------------------------------------------------

def _snapshot_session_vars(zos):
    """Deep-copy the request unit's ``zVars`` slice (None when absent)."""
    session = getattr(zos, "session", None)
    if not isinstance(session, dict):
        return None
    zvars = session.get("zVars")
    return copy.deepcopy(zvars) if isinstance(zvars, dict) else None


def _persist_session_vars(zos, vars_before) -> None:
    """Persist ``session['zVars']`` under the caller's zsid iff the handler changed it.

    Best-effort and change-gated: an anonymous read-only hit writes nothing to
    the store; a mutation (including a clear to ``{}``) propagates so the next
    request carrying the same cookie restores it at entry.
    """
    try:
        session = getattr(zos, "session", None)
        if not isinstance(session, dict):
            return
        zsid = session.get("_zsid")
        if not zsid:
            return
        zvars = session.get("zVars")
        if not isinstance(zvars, dict) or zvars == vars_before:
            return
        from zOS.L1_Foundation.a_zConfig.zConfig_modules.session import (  # pylint: disable=import-outside-toplevel
            session_cookie as _sc,
        )
        _sc.persist_vars(zos, zsid, session)
    except Exception:  # pylint: disable=broad-except
        pass


# ---------------------------------------------------------------------------
# Handler kinds — each returns a ZResult
# ---------------------------------------------------------------------------

def _execute_zdata(route: dict, params: dict, zos) -> "ZResult":
    """Resolve zConv.* placeholders into the zData config and run it."""
    from zOS.L2_Handling.j_zDialog.dialog_modules.dialog_context import inject_placeholders
    from zos_plugin import ZResult

    zdata_config = copy.deepcopy(route.get("zdata_config", {}))
    resolved = inject_placeholders(zdata_config, {"zConv": params}, zos.logger)
    resolved["silent"] = True
    result = zos.data.handle_request(resolved, context={})
    action = resolved.get("action", "read").lower()
    return ZResult.success(data=result, meta={"action": action})


def _serialize_zdata(zres: "ZResult"):
    """Render a zData ZResult into the established zAPI JSON envelope."""
    action = zres.meta.get("action", "read")
    result = zres.data

    if action in ("insert", "create"):
        if isinstance(result, int):
            result = {"id": result}
        elif result is None:
            result = {}
        return 201, {"ok": True, "action": action, "result": result}

    if action == "delete":
        return 200, {"ok": True, "action": action, "deleted": result}

    # read / search — return data array + count
    data_list = result if isinstance(result, list) else ([result] if result else [])
    return 200, {"ok": True, "data": data_list, "count": len(data_list)}


def _execute_flow(route: dict, params: dict, zos) -> "ZResult":
    """Run a zAPI-fronted FLOW (zLogin / zDialog) headless → ZResult.

    The flow IS the handler — zAPI is the transport adapter. zLogin runs the SSOT
    verify+session-write seam (`authenticate_zolo_credentials`), the same path the
    CLI `z login` and the boot cascade use, so the JSON envelope and the session
    state are identical across transports.
    """
    from zos_plugin import ZResult

    flow_config = route.get("flow_config", {})
    kind = route.get("kind")

    if kind == "zLogin":
        model = flow_config.get("model")
        role = zos.auth.authenticate_zolo_credentials(params, model=model)
        if not role:
            return ZResult.failure("Invalid credentials", status=401, meta={"kind": "zLogin"})

        # Identity read back from the session seam the verify just wrote — never
        # echo the submitted password; only surface the resolved identity fields.
        sess = getattr(zos, "session", {}) or {}
        zsession = sess.get("zVisitor", {}) if isinstance(sess, dict) else {}
        data = {"authenticated": True, "role": role}
        if isinstance(zsession, dict):
            for key in ("username", "email", "id", "user_id", "name"):
                if key in zsession:
                    data[key] = zsession[key]
        return ZResult.success(data=data, message="Signed in", meta={"kind": "zLogin"})

    # Generic zDialog flow front: onSubmit handlers are already discovered at the
    # event level; a bare flow-level zDialog+zAPI has no canonical headless path yet.
    return ZResult.failure(
        "zDialog flow zAPI execution not yet implemented", status=501, meta={"kind": kind}
    )


def _execute_zfunc(route: dict, params: dict, files: dict, handler, zos) -> "ZResult":
    """Run the &plugin.fn handler over the canonical (CLI/wizard) invocation path.

    zAPI is just a transport adapter: it builds the transport-shaped
    ``Invocation`` (zos + files + params + session) and then runs the *same*
    ``&plugin.fn`` string the CLI runs. @zfunc injects the connection points the
    plugin declared (``user``/``files``/``transfer``/``data``/...) from that
    env. Whatever the plugin returns is coerced into a uniform ``ZResult``.
    """
    from zos_plugin import ZResult, Invocation, set_env, reset_env

    inv = Invocation(
        zos=zos,
        files=files,
        params=params,
        session=getattr(zos, "session", None),
        meta={
            "method":       handler.command,
            "path":         handler.path,
            "headers":      dict(handler.headers),
            "route_params": route.get("_route_params", {}),
        },
    )
    # The route stores the handler bare (``&avatar.upload``); the resolver wants
    # call syntax (``&avatar.upload()``). Normalise so a no-arg zFunc just runs.
    handler_ref = (route.get("handler", "") or "").strip()
    if handler_ref and "(" not in handler_ref:
        handler_ref += "()"

    token = set_env(inv)
    try:
        raw = zos.zparser.resolve_plugin_invocation(handler_ref)
    finally:
        reset_env(token)
    return ZResult.coerce(raw)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _validate_auth(handler, zapi_config: dict, zos) -> bool:
    """
    Validate API key if auth is configured.

    Returns True when the request is authorised (or auth is disabled).
    Sends the error response and returns False otherwise.
    """
    auth_type = zapi_config.get("auth")
    if not auth_type or auth_type is False:
        return True  # No auth required

    api_key = (
        handler.headers.get("X-API-Key")
        or handler.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    )
    if not api_key:
        _send_json(handler, 401, {"error": "Missing API key (X-API-Key header)"})
        return False

    auth_model = zapi_config.get("auth_model")
    if not auth_model:
        # Fail CLOSED: auth was requested but there is no model to validate the key
        # against. Returning True here would silently expose an "authed" endpoint to
        # any non-empty key — a misconfiguration must deny, not open the door.
        zos.logger.error("[zAPI] auth: 'auth' set but no 'auth_model' — denying (fail-closed)")
        _send_json(handler, 500, {"error": "Auth misconfigured: missing auth_model"})
        return False

    try:
        rows = zos.data.handle_request(
            {"action": "read", "model": auth_model, "silent": True},
            context={},
        )
        rows = rows if isinstance(rows, list) else ([rows] if rows else [])
        for row in rows:
            if (
                isinstance(row, dict)
                and row.get("key_value") == api_key
                and row.get("status", "").lower() == "active"
            ):
                return True
        _send_json(handler, 403, {"error": "Invalid or inactive API key"})
        return False

    except Exception as exc:
        zos.logger.error(f"[zAPI] Auth check error: {exc}")
        _send_json(handler, 500, {"error": "Auth validation error"})
        return False


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

def _parse_params(handler, method: str, zos):
    """Parse a request into ``(fields, files)``.

    - GET                       → query-string → fields, no files
    - POST/PUT JSON             → JSON body     → fields, no files
    - POST/PUT multipart/form   → text fields + uploaded files
    """
    if method == "GET":
        parsed = urlparse(handler.path)
        qs = parse_qs(parsed.query)
        return {k: (v[0] if len(v) == 1 else v) for k, v in qs.items()}, {}

    content_type = (handler.headers.get("Content-Type", "") or "")
    content_length = int(handler.headers.get("Content-Length", 0) or 0)
    body = handler.rfile.read(content_length) if content_length > 0 else b""

    if "multipart/form-data" in content_type.lower():
        from zOS.L4_Orchestration.r_zServer.zServer_modules.rendering.form_utils import parse_multipart
        parsed = parse_multipart(body, content_type, zos.logger)
        return parsed.get("fields", {}), parsed.get("files", {})

    # JSON body (default)
    if not body:
        return {}, {}
    return json.loads(body.decode("utf-8")), {}


# ---------------------------------------------------------------------------
# Response helper
# ---------------------------------------------------------------------------

def _send_binary(handler, zres) -> None:
    """Write a raw binary ZResult body verbatim (bytes + content-type).

    The generic non-JSON transport path: emits ``zres.data`` under
    ``zres.content_type`` with a Content-Length, an optional inline
    Content-Disposition (``zres.filename``), and honours HEAD (headers only).
    Security/CORS headers are still applied centrally by ``end_headers``.
    """
    body = zres.as_bytes()
    handler.send_response(zres.status)
    handler.send_header("Content-Type", zres.content_type or "application/octet-stream")
    handler.send_header("Content-Length", str(len(body)))
    if zres.filename:
        handler.send_header("Content-Disposition", f'inline; filename="{zres.filename}"')
    handler.end_headers()
    if body and handler.command.upper() != "HEAD":
        handler.wfile.write(body)


def _send_json(handler, status: int, data, cors: bool = False) -> None:
    # NOTE: `cors` is retained for call-site compatibility but is now a NO-OP.
    # CORS + security headers are emitted centrally by handler.end_headers()
    # (http_headers SSOT), driven by config.cors_origin — no per-response wildcard,
    # no duplicate Access-Control-Allow-Origin headers.
    body = b"" if data is None else json.dumps(data, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    if body:
        handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    if body:
        handler.wfile.write(body)
