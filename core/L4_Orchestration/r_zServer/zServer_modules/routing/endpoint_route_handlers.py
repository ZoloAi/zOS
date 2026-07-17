# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/endpoint_route_handlers.py
"""
Non-page route handlers (static file · zProxy redirect · zAPI), extracted from
route_dispatcher. Mixed into RouteDispatcher; each method binds to the live
dispatcher instance. These return bytes / JSON / redirects — no HTML shell render.

NOTE: the `type: zFunc` route + its `_handle_zfunc_route` handler were removed
(2026-07, ZAPI_SSOT memo). A plugin reaches HTTP ONLY through zAPI now — `zFunc`
survives as a handler-KIND behind zAPI (`_execute_zfunc` in zapi_handler), never as
its own transport. Rendered HTML → pages; platform protocol endpoints → zHost.
"""

from zOS import os

from .utils import HandlerUtils
from .http_headers import sanitize_header_value


class EndpointRouteHandlersMixin:
    """File / redirect / function / API handlers (no page render)."""

    def _handle_static_route(self, route: dict):
        """Handle static file route."""
        # Serve static file directly
        file_path = self.router.resolve_file_path(route)

        # Check if file exists. Route through _serve_error so the app's styled
        # zViews/error/zUI.404 renders (not the plain default page).
        if not os.path.exists(file_path):
            return self._serve_error(404, "Not found")

        # A directory is not a servable page → treat as not-found. The
        # default_route catch-all (match_route step 5) lands unknown URLs here, so
        # this is the styled-404 path for missing pages; 404 (not 403) is also the
        # correct, non-leaking answer for "no such page".
        if os.path.isdir(file_path):
            return self._serve_error(404, "Not found")

        # Serve the file directly
        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            # Determine content type (SSOT helper)
            content_type = HandlerUtils.guess_content_type(file_path)

            self.handler.send_response(200)
            self.handler.send_header("Content-type", content_type)
            self.handler.send_header("Content-length", len(content))
            self.handler.end_headers()
            self.handler.wfile.write(content)

        except Exception as e:
            if self.logger:
                self.logger.error(f"[RouteDispatcher] Error serving static file: {e}")
            return self._serve_error(500, "Error serving file")

    def _handle_zproxy_route(self, route: dict):
        """Front door: resolve %slug → wake the tenant app → 302 to its address.

        The hosted app is a separate zOS instance with its own HTTP+WS. We wake it
        (scale-from-zero) via the ``proxy`` connection point and redirect the
        visitor straight to it (redirect hand-off — no WS reverse-proxy here; in
        prod a stable ingress URL fronts the pod and forwards HTTP/WS). The wake is
        synchronous = the simplest "waiting room"; a polling interstitial is a
        later polish.

        Policy is declared on the route (kept generic, like zLoom's binding) — the
        registry table/columns are the HOST PLATFORM's, never baked into zServer::

            /app/%slug:
                type: zProxy
                zProxy:
                    table: <your registry table>   # REQUIRED — no default
                    model: @.models.zSchema.<t>     # schema handle for the table —
                                                    # per-request zos.data sessions
                                                    # start UNCONNECTED (zData is
                                                    # schema-at-a-time), same reason
                                                    # zLogin declares `model`
                    key: slug                       # url param → row lookup column
                    spark_field: spark_path         # column holding the boot path
                    visibility_field: status        # optional — omit to serve any row
                    visibility_value: live          # paired with visibility_field
                    build_field: active_build_id    # optional — versions the driver
                                                    # key (slug#<build>, zRelease's
                                                    # vocabulary) so repushes retarget
                                                    # the front door to the new build

        Visibility: when ``visibility_field`` is set, only rows where it equals
        ``visibility_value`` resolve; anything else 404s (a paused/unknown app never
        reveals whether it exists). The gate is OFF by default — a platform opts into
        privacy by declaring the field/value; generic zServer ships no status vocabulary.
        """
        zos = self.router.zos if hasattr(self.router, 'zos') else None
        if not zos:
            return self.handler.send_error(500, "zOS instance not available")

        cfg = route.get("zProxy")
        cfg = cfg if isinstance(cfg, dict) else {}
        # The registry table is the platform's — REQUIRED on the route, no zCloud
        # default. A zProxy route with no table is a misconfiguration, not a default.
        table = cfg.get("table")
        if not table:
            if self.logger:
                self.logger.error("[RouteDispatcher] zProxy route missing 'table' in zProxy config")
            return self._serve_error(500, "Proxy route misconfigured (no registry table)")
        key = cfg.get("key", "slug")
        spark_field = cfg.get("spark_field", "spark_path")
        # Optional: registry column carrying the active build id. When declared,
        # the wake is keyed `slug#<build>` — the SAME driver vocabulary zRelease
        # uses — so a repush pointer-flip retargets the front door to the new
        # build instead of holding a stale bare-slug record (SSOT key unification).
        build_field = cfg.get("build_field")
        # Visibility gate — declarative field/value (SSOT on the route, not baked in).
        # Default OFF: no visibility_field → any matching row resolves. A platform
        # sets both to gate on its own status vocabulary (e.g. status == live).
        vis_field = cfg.get("visibility_field")
        vis_value = cfg.get("visibility_value")

        params = route.get("_route_params") or {}
        slug = params.get(key)
        if not slug:
            return self._serve_error(404, "No app identifier")

        try:
            # Per-request zos.data starts unconnected (zData is schema-at-a-time);
            # connect the registry's schema before the read — the same reason
            # zLogin/zpush connect their model first. `model` on the route wins;
            # the conventional @.models.zSchema.<table> handle is the fallback.
            model = cfg.get("model") or f"@.models.zSchema.{table}"
            try:
                zos.data.load_schema(zos.loader.handle(model))
            except Exception as exc:  # pylint: disable=broad-except
                if self.logger:
                    self.logger.warning(f"[RouteDispatcher] zProxy schema connect warning: {exc}")
            rows = zos.data.select(table=table, where={key: slug})
        except Exception as exc:  # pylint: disable=broad-except
            if self.logger:
                self.logger.error(f"[RouteDispatcher] zProxy registry read failed: {exc}")
            return self._serve_error(500, "Registry unavailable")

        if vis_field:
            row = next((r for r in (rows or [])
                        if str(r.get(vis_field)) == str(vis_value)), None)
        else:
            row = next(iter(rows or []), None)
        if not row:
            if self.logger:
                self.logger.info(f"[RouteDispatcher] zProxy '{slug}' not visible → 404")
            return self._serve_error(404, "App not available")

        try:
            # Front door is a control-plane job — delegate to zHost. zServer only
            # performs the 302 / interstitial; it no longer imports the compute engine.
            serve_path = getattr(self.router, 'serve_path', None)
            target = zos.zhost.resolve_proxy(
                slug, row.get(spark_field), workspace_dir=serve_path,
                build=row.get(build_field) if build_field else None)
        except Exception as exc:  # pylint: disable=broad-except
            if self.logger:
                self.logger.error(f"[RouteDispatcher] zProxy wake failed for '{slug}': {exc}")
            return self._serve_error(502, "App failed to start")

        if target.ready and target.url:
            if self.logger:
                self.logger.info(f"[RouteDispatcher] zProxy '{slug}' → 302 {target.url}")
            self.handler.send_response(302)
            self.handler.send_header("Location", sanitize_header_value(target.url))
            self.handler.send_header("Cache-Control", "no-store")
            self.handler.end_headers()
            return

        # Not ready within the wake window — ask the client to retry (interstitial
        # with auto-poll is the planned polish; a 503 keeps the contract honest).
        # Log the WHY (state + driver error) — the styled 503 page swallows the
        # message, so without this line a failed wake is undiagnosable from logs.
        if self.logger:
            self.logger.warning(
                f"[RouteDispatcher] zProxy '{slug}' not ready → 503 "
                f"(state={target.state}, url={target.url!r}, error={target.error!r})")
        return self._serve_error(503, f"App is starting ({target.state}) — retry shortly")

    def _handle_zapi_route(self, route: dict):
        """
        Handle a zAPI route — execute the registered zData operation and return JSON.

        zAPI routes are auto-discovered from zUI files at startup via zapi_scanner.
        Each route carries the resolved zdata_config and zapi_config.
        """
        if not hasattr(self.router, 'zos'):
            return self.handler.send_error(500, "zOS instance not available")

        zos = self.router.zos

        try:
            from .zapi_handler import handle as handle_zapi
            handle_zapi(self.handler, route, zos)
        except Exception as exc:
            if self.logger:
                self.logger.error(f"[RouteDispatcher] zAPI route error: {exc}", exc_info=True)
            return self.handler.send_error(500, "zAPI execution failed")
