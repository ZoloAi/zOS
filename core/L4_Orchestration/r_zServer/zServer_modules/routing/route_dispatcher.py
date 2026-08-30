# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/route_dispatcher.py

"""
Route Dispatcher - HTTP route handling and processing

Handles:
- Route matching and RBAC enforcement
- Type-specific route processing. Dispatched types: static, template, zWalker,
  zLoom, zProxy, zAPI. (`zSpark` is the `/` anchor — resolved upstream in the
  router into a zWalker route, so it never reaches this dispatcher.)
- Request/response flow for each route type

Retired: content, json, form, dynamic, redirect (2026-06 sweep). `zFunc` route type
removed (2026-07, ZAPI_SSOT memo) — plugins reach HTTP ONLY through zAPI now (zFunc
is a handler-KIND behind zAPI, never a transport). Do NOT re-add any of these.
"""

from zOS import os
from urllib.parse import urlparse

from .utils import HandlerUtils
from .html_injectors import _build_nav_html_safe
from .page_route_handlers import PageRouteHandlersMixin
from .endpoint_route_handlers import EndpointRouteHandlersMixin


class RouteDispatcher(PageRouteHandlersMixin, EndpointRouteHandlersMixin):
    """Handles HTTP route matching, RBAC, and type-specific processing."""

    def __init__(self, handler):
        """
        Initialize route dispatcher.
        
        Args:
            handler: Parent HTTP request handler instance
        """
        self.handler = handler
        self.logger = getattr(handler, 'logger', None)
        self.router = getattr(handler, 'router', None)

    def _load_zmeta_for_route(self, route):
        """
        Load the zMeta block from a route's zVaFile (SSOT for per-page metadata).

        Auto-discovered routes already carry zMeta, but explicit zWalker routes
        (like the home '/') do not. Mirrors the full-page render: build the zPath
        from zVaFolder + zVaFile and read zMeta via the loader.
        """
        zos = getattr(self.router, 'zos', None)
        zVaFile = route.get('zVaFile')
        zVaFolder = route.get('zVaFolder')
        if not (zos and zVaFile and zVaFolder):
            return {}
        try:
            zPath = HandlerUtils.build_zpath(zVaFolder, zVaFile)
            raw_zFile = zos.loader.handle(zPath=zPath)
            if isinstance(raw_zFile, dict):
                meta = raw_zFile.get('zMeta', {})
                return meta if isinstance(meta, dict) else {}
        except Exception as exc:  # pylint: disable=broad-except
            if self.logger:
                self.logger.debug(f'[RouteDispatcher] zMeta load skipped for {zVaFile}: {exc}')
        return {}

    def _resolve_navbar_payload(self, route):
        """Resolve a route's navbar exactly like the full-page render (SSOT).

        SPA navigation (zLink / client-side routing) must honor each destination
        page's ``zNavBar`` the same way a full-page load does — otherwise the
        entry page's navbar chrome lingers when you land on a ``zNavBar: false``
        page. This mirrors the block-first zMeta → ``resolve_navbar`` → RBAC
        filter → ``nav_html`` chain used by ``_handle_zwalker_route`` so there is
        exactly ONE navbar authority for both full-page and SPA arrivals.

        Returns
        -------
        Tuple[Optional[list], str]
            ``(resolved_navbar | None, nav_html | "")`` — ``None``/empty means
            the destination page wants NO navbar (client hides the chrome).
        """
        zos = getattr(self.router, 'zos', None)
        zVaFile = route.get('zVaFile')
        zVaFolder = route.get('zVaFolder')
        zBlock = route.get('zBlock')
        if not (zos and hasattr(zos, 'navigation') and zVaFile and zVaFolder):
            return None, ""
        try:
            zPath = HandlerUtils.build_zpath(zVaFolder, zVaFile)
            raw_zFile = zos.loader.handle(zPath=zPath)
            if not (raw_zFile and isinstance(raw_zFile, dict)):
                return None, ""
            # Block-first zMeta (SSOT with the full-page render): a block is the
            # unit of a page, so prefer the rendered block's own zMeta and fall
            # back to file-level zMeta as shared defaults.
            block = raw_zFile.get(zBlock) if zBlock else None
            block_meta = block.get("zMeta") if isinstance(block, dict) else None
            meta_section = (
                block_meta if isinstance(block_meta, dict)
                else raw_zFile.get("zMeta", {})
            )
            navbar_zFile = {
                **raw_zFile,
                "zMeta": meta_section if isinstance(meta_section, dict) else {},
            }
            route_meta = self.router.meta if self.router and hasattr(self.router, 'meta') else {}
            resolved = zos.navigation.resolve_navbar(navbar_zFile, route_meta=route_meta)
            if resolved:
                resolved = zos.navigation._filter_navbar_byzRBAC(resolved)
            app_brand = (
                zos.config.zSpark.get("title")
                if zos and hasattr(zos, 'config')
                and hasattr(zos.config, 'zSpark') and zos.config.zSpark
                else None
            )
            # zBrand is the navbar's SSOT ({label, icon, logo, href}); zSpark.title
            # is only the text fallback. SPA arrivals rebuild nav_html here, so
            # reading the handler's brand is what keeps a logo from reverting to
            # bare title text after a client-side navigation.
            brand_decl = getattr(
                getattr(zos.navigation, "navbar_handler", None), "brand", None
            ) or app_brand
            nav_html = _build_nav_html_safe(resolved, brand_decl, self.logger, zos) if resolved else ""
            return (resolved or None), (nav_html or "")
        except Exception as exc:  # pylint: disable=broad-except
            if self.logger:
                self.logger.debug(f'[RouteDispatcher] navbar resolve skipped for {zVaFile}: {exc}')
        return None, ""

    def _handle_route_config_request(self):
        """
        2B: Return walker config (zBlock, zVaFile, zVaFolder) for a given path.

        Client calls GET /api/route-config?path=/zProducts/zOS to get the three
        parameters it needs for execute_walker, instead of parsing paths locally.
        """
        import json
        from urllib.parse import parse_qs
        query = parse_qs(urlparse(self.handler.path).query)
        path = query.get('path', [''])[0]

        if not path:
            body = json.dumps({'error': 'Missing ?path= parameter'}).encode('utf-8')
            self.handler.send_response(400)
        else:
            route = self.router.match_route(path)
            zos = getattr(self.router, 'zos', None)
            # ROOT ROUTE ('/') — the home/brand target is a TEMPLATE route that
            # carries the zSpark DEFAULT block, not an explicit zWalker route. SPA
            # nav (brand/home click) still needs walker params, so resolve them from
            # zSpark — SSOT with _handle_template_route's is_root_route branch —
            # instead of 404-ing on the missing zWalker type. Without this the brand
            # click hits "No zWalker route for /" and SPA navigation dies.
            is_root_route = path in ('/', '')
            if is_root_route and zos is not None and getattr(zos, 'spark', None):
                if route and not self.router.check_access(route)[0]:
                    if self.logger:
                        self.logger.warning(f"[SECURITY] route-config access denied for {path}")
                    body = json.dumps({'error': 'Access denied'}).encode('utf-8')
                    self.handler.send_response(403)
                else:
                    spark = zos.spark
                    spark_route = {
                        'zBlock':    spark.get('zBlock'),
                        'zVaFile':   spark.get('zVaFile'),
                        'zVaFolder': spark.get('zVaFolder'),
                    }
                    _navbar, _nav_html = self._resolve_navbar_payload(spark_route)
                    payload = {
                        **spark_route,
                        'zMeta': self._load_zmeta_for_route(spark_route) or {},
                        'navbar': _navbar,
                        'nav_html': _nav_html,
                    }
                    body = json.dumps(payload).encode('utf-8')
                    self.handler.send_response(200)
            elif not route or route.get('type') != 'zWalker':
                body = json.dumps({'error': f'No zWalker route for {path}'}).encode('utf-8')
                self.handler.send_response(404)
            elif not self.router.check_access(route)[0]:
                # RBAC parity: this API exposes a route's walker config (zBlock,
                # zVaFile/Folder, zMeta). It must enforce the SAME access check the
                # full-page render does — otherwise SPA nav leaks config for routes
                # the user can't open. Deny without disclosing which roles are needed.
                if self.logger:
                    self.logger.warning(f"[SECURITY] route-config access denied for {path}")
                body = json.dumps({'error': 'Access denied'}).encode('utf-8')
                self.handler.send_response(403)
            else:
                # ROUTE PARAMS → zLoom route store (SPA parity with the full-page
                # handler). SPA navigation resolves every route via this config API (no
                # full-page load), so we seat-OR-CLEAR the store on each hop: a
                # parametrized route (/users/%username) seats its params; a paramless
                # hop clears them. This is what makes the store request-scoped — the
                # previous route's params can NEVER linger and re-render the old profile
                # under a new URL (the old "stale page" edge is impossible by construction).
                zos = getattr(self.router, 'zos', None)
                _rparams = route.get('_route_params')
                if zos and getattr(zos, 'zloom', None):
                    zos.zloom.set_route_params(_rparams)

                # Explicit zWalker routes (e.g. '/') carry no zMeta; load it from the
                # zVaFile so SPA navigation can inject per-page zBrush CSS (SSOT: same
                # loader path the full-page render uses).
                zmeta = route.get('zMeta') or self._load_zmeta_for_route(route)
                _navbar, _nav_html = self._resolve_navbar_payload(route)
                payload = {
                    'zBlock':     route.get('zBlock'),
                    'zVaFile':    route.get('zVaFile'),
                    'zVaFolder':  route.get('zVaFolder'),
                    'zMeta':      zmeta or {},
                    'navbar':     _navbar,
                    'nav_html':   _nav_html,
                    # SSOT parity with the full-page zui-config injection (see
                    # page_route_handlers._handle_zwalker_route): SPA nav ALSO
                    # needs to hand this back on the next execute_walker so the
                    # WS-side render — not just this JSON response's OWN
                    # set_route_params above — sees %route.* too.
                    'routeParams': _rparams if isinstance(_rparams, dict) and _rparams else None,
                }
                body = json.dumps(payload).encode('utf-8')
                self.handler.send_response(200)

        self.handler.send_header('Content-Type', 'application/json')
        self.handler.send_header('Content-Length', len(body))
        self.handler.send_header('Cache-Control', 'no-store')
        self.handler.end_headers()
        self.handler.wfile.write(body)

    def handle_routed_request(self):
        """Per-request session scope (§19 Phase 4b) wrapping the real dispatch.

        Each HTTP request runs under its OWN ephemeral session unit so concurrent
        requests (waitress is multi-threaded) never clobber each other's nav state
        — zVaFile/zVaFolder/zBlock/zVars/_route_meta are written onto zos.session
        during dispatch. HTTP carries no cookie identity, so the unit is seeded
        anonymous from the boot default with deep-copied per-caller slices and
        dropped afterwards. Degrades to the shared session if the registry is
        unavailable.

        The whole dispatch holds a READ slot on the reload gate: a ``z reload``
        (SIGHUP, main thread) busts the loader cache + swaps the route table —
        racing an in-flight request (a push mid-zRelease, a zProxy wake) wedges
        the request thread on half-swapped state. The gate makes the reload
        wait for us instead (see lifecycle/reload_gate.py).
        """
        from ..lifecycle.reload_gate import get_gate  # pylint: disable=import-outside-toplevel

        with get_gate().request() as admitted:
            if not admitted:
                # A reload held the gate past the wait window — never dispatch
                # against a table mid-swap; ask the client to retry.
                return self.handler.send_error(
                    503, "Server reloading — retry shortly")
            token, sid = self._enter_request_session()
            try:
                return self._dispatch_routed_request()
            finally:
                self._exit_request_session(token, sid)

    def _enter_request_session(self):
        """Seed + bind a per-request session unit; return (token, sid) for cleanup.

        Cookie-bound identity (ZAUTH_INSTANCE.notes.md §19.L): the request's ``zsid``
        cookie resolves a stored ``zAuth`` from the session_store, so a plain page
        load (hard reload / new tab) renders SIGNED-IN instead of anonymous. A first
        visitor gets a fresh zsid set on the response. The registry key stays an
        ephemeral ``http_<uuid>`` so concurrent requests sharing a cookie never
        clobber each other's nav slice — only the IDENTITY is shared, via the store.
        """
        zos = getattr(self.router, 'zos', None)
        if zos is None:
            return None, None
        try:
            import copy as _copy
            import uuid as _uuid
            from zOS.L1_Foundation.a_zConfig.zConfig_modules.session import (  # type: ignore[reportMissingImports]
                session_registry as _sr,
                session_cookie as _sc,
            )
        except Exception:  # pylint: disable=broad-except
            return None, None
        base = getattr(zos, '_session_default', None)
        if not isinstance(base, dict):
            base = getattr(zos, 'session', None)
        if not isinstance(base, dict):
            return None, None
        try:
            # Resolve (or mint) the durable zsid from the request cookie.
            cookie_hdr = None
            try:
                cookie_hdr = self.handler.headers.get('Cookie')
            except Exception:  # pylint: disable=broad-except
                cookie_hdr = None
            zsid = _sc.read_zsid(cookie_hdr)
            new_cookie = not zsid
            if new_cookie:
                zsid = _sc.new_zsid()

            unit = dict(base)  # shallow: shares config/singletons (logger, zMachine, zCache)
            for key in ('zVisitor', 'zCrumbs', 'zVars', 'zRoute', 'wizard_mode'):
                if key in base:
                    unit[key] = _copy.deepcopy(base[key])
            # Rehydrate a prior signed-in identity (if this zsid has one stored).
            _sc.restore_into_unit(unit, _sc.load_identity(zos, zsid))
            unit['_zsid'] = zsid  # write-through key for login (_apply_zsession)

            sid = f"http_{_uuid.uuid4().hex}"
            _sr.register(unit, session_id=sid)
            token = _sr.set_current(sid)
            if new_cookie:
                self._install_session_cookie(zsid)
            return token, sid
        except Exception as exc:  # pylint: disable=broad-except
            if self.logger:
                self.logger.debug(f"[RouteDispatcher] per-request session seed failed: {exc}")
            return None, None

    def _install_session_cookie(self, zsid):
        """Emit ``Set-Cookie: zsid=…`` on this response by wrapping end_headers.

        end_headers is the single choke point every response path calls, so one
        wrap covers HTML/JSON/redirect/error/static alike. Restored in
        :meth:`_exit_request_session` (a dev keep-alive handler is reused across
        requests).
        """
        handler = self.handler
        if getattr(handler, '_zsid_cookie_installed', False):
            return
        try:
            from zOS.L1_Foundation.a_zConfig.zConfig_modules.session import (  # type: ignore[reportMissingImports]
                session_cookie as _sc,
            )
        except Exception:  # pylint: disable=broad-except
            return
        orig = handler.end_headers
        # Secure on https (prod behind a TLS proxy sets X-Forwarded-Proto); omitted
        # on plain-http loopback dev, where browsers drop Secure cookies.
        secure = False
        try:
            proto = (handler.headers.get('X-Forwarded-Proto') or '').strip().lower()
            secure = proto == 'https'
        except Exception:  # pylint: disable=broad-except
            secure = False
        cookie_val = _sc.build_set_cookie(zsid, secure=secure)

        def _patched_end_headers():
            try:
                handler.send_header('Set-Cookie', cookie_val)
            except Exception:  # pylint: disable=broad-except
                pass
            return orig()

        handler.end_headers = _patched_end_headers
        handler._zsid_cookie_installed = True
        handler._zsid_end_headers_orig = orig

    def _exit_request_session(self, token, sid):
        """Restore prior context-current + drop the per-request unit (best-effort)."""
        # Undo the cookie wrap so a reused (keep-alive) handler isn't double-patched.
        handler = self.handler
        orig = getattr(handler, '_zsid_end_headers_orig', None)
        if orig is not None:
            handler.end_headers = orig
            handler._zsid_cookie_installed = False
            handler._zsid_end_headers_orig = None
        if token is None and sid is None:
            return
        try:
            from zOS.L1_Foundation.a_zConfig.zConfig_modules.session import (  # type: ignore[reportMissingImports]
                session_registry as _sr,
            )
            if token is not None:
                _sr.restore(token)
            if sid:
                _sr.unregister(sid)
        except Exception:  # pylint: disable=broad-except
            pass

    def _dispatch_routed_request(self):
        """
        Handle request using HTTPRouter with RBAC enforcement.
        
        Flow:
            1. Match route (without query params)
            2. Check RBAC
            3. Dispatch to type-specific handler
        """
        # Strip query parameters for route matching
        clean_path = urlparse(self.handler.path).path

        # 2B: Route-config API — served before RBAC/router to avoid needing a yaml entry
        if clean_path == '/api/route-config':
            return self._handle_route_config_request()

        # Per-request dispatch chatter is framework-internal noise → framework.debug
        # (not INFO — this fires on every hit and drowns the console at INFO level).
        if self.logger:
            self.logger.framework.debug(f"[RouteDispatcher] Attempting to match route: {clean_path}")
            self.logger.framework.debug(f"[RouteDispatcher] Router has {len(self.router.auto_discovered_routes)} auto-discovered routes")

        # Built-in SEO endpoints (issue #24 Phase A) — checked BEFORE the route
        # match because a wildcard/catch-all route would otherwise swallow them
        # into the styled 404. An app's OWN explicit route for either path
        # (route_map or auto-discovered static) still shadows the default.
        if clean_path in ('/robots.txt', '/sitemap.xml'):
            _explicit = (clean_path in (self.router.route_map or {})
                         or clean_path in (self.router.auto_discovered_routes or {}))
            if not _explicit:
                from .seo_endpoints import serve_robots, serve_sitemap
                zos = getattr(self.router, 'zos', None)
                if clean_path == '/robots.txt':
                    return serve_robots(self.handler)
                return serve_sitemap(self.handler, self.router, zos, logger=self.logger)

        # Match route (without query parameters)
        route = self.router.match_route(clean_path)
        if not route:
            # No route found - 404 (styled if UI/error/zUI.404.* exists)
            if self.logger:
                self.logger.warning(f"[RouteDispatcher] No route match found for: {self.handler.path}")
            return self._serve_error(404, "Route not found")

        # Check RBAC
        has_access, error_page = self.router.check_access(route)
        if not has_access:
            # Access denied - log security event with details
            if self.logger:
                required_roles = route.get('roles', [])
                self.logger.warning(f"[SECURITY] Access denied to {clean_path} - Required roles: {required_roles}")
            return self._serve_error(403, "Access Denied")

        # Access granted - log with route details (framework channel, per-request noise)
        route_type = route.get("type", "static")
        if self.logger:
            self.logger.framework.debug(f"[RouteDispatcher] Access granted - Route: {clean_path}, Type: {route_type}")

        if route_type == "static":
            return self._handle_static_route(route)
        elif route_type == "template":
            return self._handle_template_route(route)
        elif route_type == "zWalker":
            return self._handle_zwalker_route(route)
        elif route_type == "zLoom":
            return self._handle_zloom_route(route)
        elif route_type == "zProxy":
            return self._handle_zproxy_route(route)
        elif route_type == "zAPI":
            return self._handle_zapi_route(route)

        # Unknown route type
        return self.handler.send_error(501, f"Route type '{route_type}' not supported")

    def _serve_error(self, status_code: int, message: str = ""):
        """
        Serve a styled error page from UI/error/zUI.<code>.* if one exists, else
        fall back to the plain default error.

        zServer-agnostic default: ANY zApp can brand its error pages by dropping
        zUI.404.zolo / zUI.403.zolo / zUI.500.zolo … into its UI/error/ folder.
        No registration, no config — the convention IS the wiring. The page
        renders through the SAME walker (shell + WS hydration) as every other
        page, so error pages are styled exactly like the rest of the app; only
        the HTTP status differs (carried via the synthetic route's _status_code).

        The block rendered is the file's first top-level block (any name), so
        authors avoid YAML's numeric-key pitfall (a block literally named `404`
        parses as an int) — name it `NotFound`, `Error`, etc.
        """
        try:
            zos = self.router.zos if hasattr(self.router, 'zos') else None
            serve_path = getattr(self.router, 'serve_path', None)
            try:
                ui_folder = self.handler.mount_manager.get_folder_name("UI") or "UI"
            except Exception:  # pylint: disable=broad-except
                ui_folder = "UI"

            if zos and serve_path:
                error_dir = os.path.join(serve_path, ui_folder, "error")
                if os.path.isdir(error_dir):
                    for ext in (".zolo", ".json", ".yaml", ".yml"):
                        candidate = os.path.join(error_dir, f"zUI.{status_code}{ext}")
                        if not os.path.isfile(candidate):
                            continue
                        zPath = f"@.{ui_folder}.error.zUI.{status_code}"
                        raw_zFile = zos.loader.handle(zPath=zPath)
                        zblock = None
                        if isinstance(raw_zFile, dict):
                            zblock = next((k for k in raw_zFile.keys() if k != "zMeta"), None)
                        if zblock:
                            error_route = {
                                "type": "zWalker",
                                "zVaFolder": f"@.{ui_folder}.error",
                                "zVaFile": f"zUI.{status_code}",
                                "zBlock": zblock,
                                "_status_code": status_code,
                            }
                            if self.logger:
                                self.logger.info(
                                    f"[RouteDispatcher] Styled error page zUI.{status_code} "
                                    f"→ {self.handler.path}"
                                )
                            return self._handle_zwalker_route(error_route)
        except Exception as exc:  # pylint: disable=broad-except
            if self.logger:
                self.logger.error(f"[RouteDispatcher] Styled error page failed ({status_code}), falling back: {exc}")

        return self.handler.send_error(status_code, message)

