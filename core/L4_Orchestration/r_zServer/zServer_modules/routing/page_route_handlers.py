# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/page_route_handlers.py
"""
Page-rendering route handlers (template · zLoom · zWalker), extracted from
route_dispatcher. Mixed into RouteDispatcher; methods bind to the live instance
(self.handler / self.router / self.logger / self._serve_error). All three share the
render pipeline: walker coords → Jinja shell → navbar (RBAC) → inject → send.
"""

from urllib.parse import urlparse

from .utils import HandlerUtils
from .html_injectors import (
    _build_nav_html_safe,
    _inject_zui_head,
    _inject_title,
    _inject_watermark,
)


class PageRouteHandlersMixin:
    """Server-rendered HTML page handlers (template/zLoom/zWalker)."""

    def _finalize_page(self, html_content, zos, resolved_navbar, app_brand,
                       page_title, context, zVaFile_meta, extra_config=None):
        """Shared server-render tail for template + zWalker (SSOT).

        Nav HTML + styles/zCanvas + zui-config, then head/title/watermark inject.
        zWalker passes ``extra_config={"websocket": {...}}``; template passes nothing
        — their ONLY difference. One place to inject, so the paths can't drift.
        """
        nav_html = _build_nav_html_safe(resolved_navbar, app_brand, self.logger, zos)
        _styles_folder = (
            self.handler.mount_manager.mounts.get('/styles/')
            if hasattr(self.handler, 'mount_manager') else None
        )
        _zcanvas = (
            zos.config.zSpark.get("zCanvas")
            if (zos and hasattr(zos, 'config')
                and hasattr(zos.config, 'zSpark') and zos.config.zSpark)
            else None
        )
        zui_config_values = {
            "zVaFile": context.get("zVaFile"),
            "zVaFolder": context.get("zVaFolder"),
            "zBlock": context.get("zBlock"),
            "title": page_title,               # Per-page title (for document.title)
            "brand": app_brand,                # App brand (for navbar, always zSpark)
            "zNavBar": resolved_navbar,        # RBAC-filtered navbar (clean strings only)
            "nav_html": nav_html,              # 3A: Pre-built HTML — client injects directly
            "zMeta": zVaFile_meta,             # YAML metadata for client features (_zScripts, etc)
        }
        if extra_config:
            zui_config_values.update(extra_config)
        html_content = _inject_zui_head(
            html_content, zui_config_values, zVaFile_meta, _styles_folder,
            self.logger, zcanvas_name=_zcanvas
        )
        html_content = _inject_title(html_content, page_title, self.logger)
        html_content = _inject_watermark(html_content, zos, self.logger)
        return html_content

    def _handle_template_route(self, route: dict):
        """
        Handle template route - render Jinja2 template (like Flask render_template()).
        
        Now zWalker-aware: If route has zVaFile, it will be converted to URL and injected
        into template context for client-side loading (mixed mode support).
        
        Args:
            route: Route definition with "template" field and optional "context" dict
        """
        try:
            template_name = route.get("template", "")
            if not template_name:
                return self.handler.send_error(500, "Template route missing 'template' field")

            # Get context data (variables to pass to template)
            context = route.get("context", {})

            # Get zos instance from router
            if not hasattr(self.router, 'zos'):
                return self.handler.send_error(500, "zOS instance not available")

            # Auto-inject zSession values (zVaFile, zVaFolder, zBlock) into context
            # so templates can render them without manual Jinja plumbing
            zos = self.router.zos
            if hasattr(zos, 'session') and zos.session:
                # Check if this is the root route "/" - if so, use zSpark defaults (not session)
                clean_path = urlparse(self.handler.path).path
                is_root_route = (clean_path == "/" or clean_path == "")

                # Only inject if not already present in route context
                if "zVaFile" not in context:
                    if is_root_route and hasattr(zos, 'spark') and zos.spark:
                        # Root route: Use zSpark default (declarative, not stateful)
                        context["zVaFile"] = zos.spark.get("zVaFile")
                    else:
                        # Other routes: Use session state (allows navigation memory)
                        context["zVaFile"] = zos.session.get("zVaFile")

                if "zVaFolder" not in context:
                    if is_root_route and hasattr(zos, 'spark') and zos.spark:
                        context["zVaFolder"] = zos.spark.get("zVaFolder")
                    else:
                        context["zVaFolder"] = zos.session.get("zVaFolder")

                if "zBlock" not in context:
                    if is_root_route and hasattr(zos, 'spark') and zos.spark:
                        # Root route: Use zSpark default block (prevents session bleed)
                        context["zBlock"] = zos.spark.get("zBlock")
                    else:
                        # Other routes: Use session state
                        context["zBlock"] = zos.session.get("zBlock")

                # Debug: log what we got and from where
                if self.logger:
                    source = "zSpark (root route)" if is_root_route else "zSession"
                    self.logger.info(f"[RouteDispatcher] Auto-injected from {source}: zVaFile={context.get('zVaFile')}, zVaFolder={context.get('zVaFolder')}, zBlock={context.get('zBlock')}")

            # Route-level overrides (opt-in): Explicit route config takes precedence
            # This allows routes to override zSpark/session defaults
            zVaFile = route.get("zVaFile")
            if zVaFile:
                ui_folder_name = self.handler.mount_manager.get_folder_name("UI")
                ui_file_path = HandlerUtils.convert_zpath_to_url(zVaFile, ui_folder_name)
                context["zVaFile"] = ui_file_path
                if self.logger:
                    self.logger.debug(f"[RouteDispatcher] Route override: zVaFile={ui_file_path}")

            zBlock = route.get("zBlock")
            if zBlock:
                context["zBlock"] = zBlock
                if self.logger:
                    self.logger.debug(f"[RouteDispatcher] Route override: zBlock={zBlock}")

            # Get templates directory using MountManager
            from ..rendering.default_templates import render_zvaf

            templates_dir = self.handler.mount_manager.get_folder_path("templates")

            # Add cache-busting timestamp
            import time
            context['timestamp'] = int(time.time() * 1000)

            # Render template — physical templates/<name> wins; falls back to the
            # built-in default zVaF.html on TemplateNotFound (SSOT: default_templates).
            html_content = render_zvaf(templates_dir, template_name, context, self.logger)

            # Resolve navbar with route metadata fallback (same as zWalker routes)
            resolved_navbar = None
            if hasattr(zos, 'navigation'):
                # Load the zVaFile to check its meta.zNavBar (if provided in context)
                zVaFile = context.get("zVaFile")
                zVaFolder = context.get("zVaFolder")
                try:
                    # Construct zPath from zVaFolder/zVaFile (e.g., "@.UI" + "zUI.zAbout" → "@.UI.zUI.zAbout")
                    if zVaFile and zVaFolder:
                        # Construct full zPath (SSOT helper)
                        zPath = HandlerUtils.build_zpath(zVaFolder, zVaFile)
                        raw_zFile = zos.loader.handle(zPath=zPath)

                        # Extract zMeta section from YAML for client-side features (v1.5.13: _zScripts support)
                        if raw_zFile and isinstance(raw_zFile, dict):
                            meta_section = raw_zFile.get("zMeta", {})
                            if isinstance(meta_section, dict):
                                context["zVaFile_meta"] = meta_section
                                if self.logger:
                                    self.logger.info(f"[RouteDispatcher] Extracted YAML zMeta for client: {list(meta_section.keys())}")
                            else:
                                context["zVaFile_meta"] = {}
                        else:
                            context["zVaFile_meta"] = {}
                    else:
                        raw_zFile = None

                    # Get router meta for fallback
                    route_meta = self.router.meta if self.router and hasattr(self.router, 'meta') else {}
                    # Resolve navbar with priority chain (returns raw navbar with RBAC metadata)
                    resolved_navbar = zos.navigation.resolve_navbar(raw_zFile, route_meta=route_meta) if raw_zFile else None

                    # 🔒 RBAC Filter: Apply dynamic RBAC filtering for Bifrost (same as Terminal)
                    # This filters out items the current user can't access before injecting into HTML
                    if resolved_navbar:
                        resolved_navbar = zos.navigation._filter_navbar_byzRBAC(resolved_navbar)
                        if self.logger:
                            self.logger.debug(f"[RouteDispatcher] RBAC-filtered navbar for Bifrost: {resolved_navbar}")
                except Exception:
                    resolved_navbar = None

            # Extract page title from YAML metadata (zTitle field in zMeta)
            # Get app brand (always from zSpark for navbar consistency)
            zVaFile_meta = context.get("zVaFile_meta", {})
            app_brand = zos.config.zSpark.get("title") if hasattr(zos, 'config') and hasattr(zos.config, 'zSpark') and zos.config.zSpark else None
            page_ztitle = zVaFile_meta.get("zTitle") if zVaFile_meta else None
            
            # Construct full page title:
            # - If zTitle exists: "zSpark.title - zTitle" (e.g., "zCloud - zOS")
            # - Otherwise: just "zSpark.title" (e.g., "zCloud")
            if page_ztitle and app_brand:
                page_title = f"{app_brand} - {page_ztitle}"
            elif page_ztitle:
                page_title = page_ztitle
            else:
                page_title = app_brand
            
            # Set title in template context for Jinja {{ title }}
            if page_title:
                context["title"] = page_title

            # Shared server-render tail (SSOT) — nav + head/title/watermark inject.
            # The template path carries no websocket block (that's zWalker-only).
            html_content = self._finalize_page(
                html_content, zos, resolved_navbar, app_brand, page_title,
                context, zVaFile_meta
            )

            # Send HTML response with cache headers
            html_bytes = html_content.encode('utf-8')
            
            self.handler.send_response(200)
            self.handler.send_header("Content-type", "text/html; charset=utf-8")
            self.handler.send_header("Content-length", len(html_bytes))
            self.handler.cache_manager.add_cache_headers(
                self.handler, 
                file_path=None,
                file_type="template",
                content=html_bytes
            )
            self.handler.end_headers()
            self.handler.wfile.write(html_bytes)

        except Exception as e:
            if self.logger:
                self.logger.error(f"[RouteDispatcher] Template rendering error: {e}")
            return self.handler.send_error(500, f"Template rendering failed: {str(e)}")

    def _handle_zloom_route(self, route: dict):
        """
        Handle zLoom route — a VIRTUAL, data-gated extension of the one walker.

        A zLoom route has no physical page on disk (unlike auto-discovered static
        routes that mirror folders). The smart router synthesizes it at request
        time: capture the URL params (e.g. %username), resolve the block's primary
        zLoom read keyed off those params, and gate on the result —

            read returns a row  → render through the SAME zWalker path
            read returns nothing → 404 (path effectively does not exist)

        The gate read IS the block's own `zMeta.zLoom` source, so the gate
        predicate and the render predicate are identical (SSOT). Visibility
        (public/private/connections) therefore lives entirely in that read's
        where-clause — change the query, change the policy, "via the db and
        nothing else". Empty→404 (not 403) means a private/unknown handle never
        reveals whether it exists.
        """
        zos = self.router.zos if hasattr(self.router, 'zos') else None
        if not zos:
            return self.handler.send_error(500, "zOS instance not available")

        # 1. Seat-or-clear URL params in the zLoom route store so the gate read's
        #    %route.* tokens resolve — ONE seam, shared with SPA + full-page (request-scoped).
        if getattr(zos, "zloom", None):
            zos.zloom.set_route_params(route.get("_route_params"))

        # 2. Determine the gate read. Precedence: the route's own `zLoom` field (explicit,
        #    SSOT — alias or full @ zPath) wins; otherwise fall back to the rendered
        #    block's zMeta.zSpool (the page declares its own gate spool). zMeta lives UNDER
        #    the block (PublicProfile.zMeta.zSpool), with a top-level zMeta fallback.
        zloom = route.get("zLoom")
        if not zloom:
            zVaFile = route.get("zVaFile")
            zVaFolder = route.get("zVaFolder") or zos.session.get("zVaFolder")
            if not zVaFolder:
                spark = getattr(zos, 'spark', None) or getattr(zos, 'zspark_obj', None) or {}
                zVaFolder = spark.get("zVaFolder") if isinstance(spark, dict) else None
            zBlock = route.get("zBlock")
            if zos and zVaFile and zVaFolder:
                try:
                    zPath = HandlerUtils.build_zpath(zVaFolder, zVaFile)
                    raw_zFile = zos.loader.handle(zPath=zPath)
                    if isinstance(raw_zFile, dict):
                        block = raw_zFile.get(zBlock) if zBlock else None
                        block_meta = block.get("zMeta") if isinstance(block, dict) else None
                        top_meta = raw_zFile.get("zMeta")
                        zmeta = block_meta if isinstance(block_meta, dict) else (top_meta or {})
                        zloom = zmeta.get("zSpool")
                except Exception as exc:  # pylint: disable=broad-except
                    if self.logger:
                        self.logger.error(f"[RouteDispatcher] zLoom gate meta load failed: {exc}")

        gate_name = None
        if isinstance(zloom, (list, tuple)) and zloom:
            gate_name = zloom[0]
        elif isinstance(zloom, str):
            gate_name = zloom

        # 3. Resolve the gate read. Empty → 404 BEFORE any walker render, so a
        #    non-existent/not-visible handle never paints the page or hydrates data.
        if gate_name:
            exists = False
            try:
                resolver = zos.zloom
                results = resolver.resolve_spool([gate_name])
                # The merged key is the read NAME (alias) or the @-path TAIL, not the
                # raw gate_name — so read the single resolved value directly.
                row = next(iter(results.values()), None) if isinstance(results, dict) else None
                exists = bool(row)
            except Exception as exc:  # pylint: disable=broad-except
                if self.logger:
                    self.logger.error(f"[RouteDispatcher] zLoom gate '{gate_name}' resolve failed: {exc}")
                exists = False
            if not exists:
                if self.logger:
                    self.logger.info(
                        f"[RouteDispatcher] zLoom gate '{gate_name}' empty → 404 for {self.handler.path}"
                    )
                return self._serve_error(404, "Not found")
        elif self.logger:
            self.logger.warning(
                f"[RouteDispatcher] zLoom route {self.handler.path} has no zMeta.zLoom gate — serving ungated"
            )

        # 4. Visible → render through the SAME walker. One walker, one app.
        return self._handle_zwalker_route(route)

    def _handle_zwalker_route(self, route: dict):
        """
        Handle zWalker route - Execute zVaF blocks server-side using zVaF.html template.
        
        Supports hierarchical fallbacks: route → session
        - zVaFolder: route value OR session default
        - zVaFile: route value OR session default
        - zBlock: route value OR session default
        
        Args:
            route: Route definition with optional "context" dict
        """
        try:
            from ..rendering.default_templates import render_zvaf

            zos = self.router.zos if hasattr(self.router, 'zos') else None

            # ROUTE PARAMS → zLoom route store (owner: RouteOps). A parametrized route
            # (/users/:username) captures params into route["_route_params"]; block
            # rendering reads them via zos.zloom as %route.* (never zVars).
            # set_route_params is the ONE seam — it REPLACES the store per hop
            # (seat-or-clear) so no stale param survives. Keep BEFORE render/data.
            if zos and getattr(zos, "zloom", None):
                rparams = route.get("_route_params")
                zos.zloom.set_route_params(rparams)
                if self.logger and isinstance(rparams, dict) and rparams:
                    self.logger.debug(
                        f"[RouteDispatcher] Seated route params in zLoom store: "
                        f"{list(rparams.keys())}"
                    )

            # zWalker routes always use zVaF.html (full declarative mode)
            template_name = "zVaF.html"

            # Get context data (variables to pass to template)
            context = route.get("context", {})

            # NEW v1.5.12: Resolve _data queries at route level (Flask pattern)
            # This executes database queries BEFORE rendering, storing results in context
            if "_data" in route and zos:
                resolved_data = HandlerUtils.resolve_route_data(route["_data"], zos, self.logger)
                if resolved_data:
                    context["_resolved_data"] = resolved_data
                    if self.logger:
                        self.logger.info(f"[RouteDispatcher] Resolved {len(resolved_data)} data queries for route")

            # Route-level zLoom field → resolved data (SSOT named spools, declared on
            # the route instead of a block's zMeta.zSpool). Lets ANY route — incl. the
            # zSpark home — attach data to its view via %data.<name>. Bridged into the
            # resolver's zSpool key; merges into _resolved_data beside literal route _data.
            if zos and route.get("zLoom"):
                try:
                    resolver = zos.zloom
                    zloom_data = resolver.resolve_spool(route["zLoom"])
                    if zloom_data:
                        rd = context.setdefault("_resolved_data", {})
                        if isinstance(rd, dict):
                            rd.update(zloom_data)
                        if self.logger:
                            self.logger.info(f"[RouteDispatcher] Resolved {len(zloom_data)} route zLoom reads")
                except Exception as exc:  # pylint: disable=broad-except
                    if self.logger:
                        self.logger.error(f"[RouteDispatcher] route zLoom resolve failed: {exc}")

            # Apply hierarchical fallbacks: route → zSpark (root) / session (other)
            # Route-level values override defaults
            if zos:
                # Check if this is the root route "/" - if so, use zSpark defaults (not session)
                clean_path = urlparse(self.handler.path).path
                is_root_route = (clean_path == "/" or clean_path == "")

                # Priority: route → zspark_obj (root) / session (other)
                # zspark_obj is immutable; session.zBlock drifts after navigation
                spark = getattr(zos, 'spark', None) or getattr(zos, 'zspark_obj', None) or {}
                if is_root_route and spark:
                    # Root route: Use zSpark defaults (declarative, not stateful)
                    zVaFolder = route.get("zVaFolder") or spark.get("zVaFolder")
                    zVaFile   = route.get("zVaFile")   or spark.get("zVaFile")
                    zBlock    = route.get("zBlock")    or spark.get("zBlock")
                else:
                    # Other routes: Use session state (allows navigation memory)
                    zVaFolder = route.get("zVaFolder") or zos.session.get("zVaFolder")
                    zVaFile   = route.get("zVaFile")   or zos.session.get("zVaFile")
                    zBlock    = route.get("zBlock")    or zos.session.get("zBlock")

                if self.logger:
                    source = "zspark_obj (root)" if (is_root_route and spark) else "zSession"
                    self.logger.debug(f"[RouteDispatcher] zWalker resolved from {source} - Folder: {zVaFolder}, File: {zVaFile}, Block: {zBlock}")
            else:
                # No session available - use route values only
                zVaFolder = route.get("zVaFolder")
                zVaFile = route.get("zVaFile")
                zBlock = route.get("zBlock")

            # Store resolved values in context for template/future use
            if zVaFolder:
                context["zVaFolder"] = zVaFolder
            if zVaFile:
                context["zVaFile"] = zVaFile
            if zBlock:
                context["zBlock"] = zBlock

            # Store route metadata in session for zWalker access (navbar fallback)
            # This allows zWalker to check route-level meta.zNavBar as fallback
            if zos and hasattr(zos, 'session'):
                # Get router's route metadata (if exists)
                if self.router and hasattr(self.router, 'route_map'):
                    # Try to get route metadata from router
                    matched_route = self.router.route_map.get(self.handler.path)
                    if not matched_route:
                        # Try auto-discovered routes
                        matched_route = self.router.auto_discovered_routes.get(self.handler.path)

                    if matched_route:
                        # Store route metadata for walker access
                        zos.session['_route_meta'] = matched_route

                # Also inject router meta (global route config) as fallback
                if self.router and hasattr(self.router, 'meta'):
                    zos.session['_router_meta'] = self.router.meta

            # Get templates directory using MountManager
            templates_dir = self.handler.mount_manager.get_folder_path("templates")

            # Add cache-busting timestamp
            import time
            context['timestamp'] = int(time.time() * 1000)

            # Render template — physical templates/zVaF.html wins; falls back to the
            # built-in default zVaF.html on TemplateNotFound (SSOT: default_templates).
            html_content = render_zvaf(templates_dir, template_name, context, self.logger)

            # Resolve navbar with route metadata fallback
            resolved_navbar = None
            if zos and hasattr(zos, 'navigation'):
                # Load the zVaFile to check its meta.zNavBar
                try:
                    # Construct zPath from zVaFolder/zVaFile (e.g., "@.UI" + "zUI.zAbout" → "@.UI.zUI.zAbout")
                    if zVaFile and zVaFolder:
                        # Construct full zPath (SSOT helper)
                        zPath = HandlerUtils.build_zpath(zVaFolder, zVaFile)
                        raw_zFile = zos.loader.handle(zPath=zPath)

                        # zMeta SSOT — a BLOCK is the unit of a page. Prefer the rendered
                        # block's own zMeta (raw_zFile[zBlock].zMeta), fall back to the
                        # file-level zMeta as shared defaults. This unifies WHERE zMeta
                        # lives for BOTH data (zLoom, read block-level) AND page chrome
                        # (navbar/title/zBrush, historically read file-level only). Without
                        # this a block-level zMeta was invisible to the navbar — the
                        # "two homes for one keyword" leak. Multi-block files (zVaF fans
                        # out blocks) thus get per-block title/nav; single-page files keep
                        # working via the file-level fallback.
                        if raw_zFile and isinstance(raw_zFile, dict):
                            block = raw_zFile.get(zBlock) if zBlock else None
                            block_meta = block.get("zMeta") if isinstance(block, dict) else None
                            meta_section = block_meta if isinstance(block_meta, dict) else raw_zFile.get("zMeta", {})
                            if isinstance(meta_section, dict):
                                context["zVaFile_meta"] = meta_section
                                if self.logger:
                                    scope = 'block' if isinstance(block_meta, dict) else 'file'
                                    self.logger.info(f"[RouteDispatcher] Extracted zMeta ({scope}) for client: {list(meta_section.keys())}")
                            else:
                                meta_section = {}
                                context["zVaFile_meta"] = {}
                            # resolve_navbar reads raw_zFile['zMeta'] — feed it the effective
                            # (block-first) meta so a block-level zNavBar is honored too.
                            navbar_zFile = {**raw_zFile, "zMeta": meta_section}
                        else:
                            context["zVaFile_meta"] = {}
                            navbar_zFile = None
                    else:
                        raw_zFile = None
                        navbar_zFile = None

                    # Get router meta for fallback
                    route_meta = self.router.meta if self.router and hasattr(self.router, 'meta') else {}
                    # Resolve navbar with priority chain (returns raw navbar with RBAC metadata)
                    resolved_navbar = zos.navigation.resolve_navbar(navbar_zFile, route_meta=route_meta) if navbar_zFile else None

                    # 🔒 RBAC Filter: Apply dynamic RBAC filtering for Bifrost (same as Terminal)
                    # This filters out items the current user can't access before injecting into HTML
                    if resolved_navbar:
                        resolved_navbar = zos.navigation._filter_navbar_byzRBAC(resolved_navbar)
                        if self.logger:
                            self.logger.debug(f"[RouteDispatcher] RBAC-filtered navbar for zWalker route: {resolved_navbar}")
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"[RouteDispatcher] Could not resolve navbar: {e}")
                    resolved_navbar = None

            # Extract page title from YAML metadata (zTitle field in zMeta)
            # Get app brand (always from zSpark for navbar consistency)
            zVaFile_meta = context.get("zVaFile_meta", {})
            app_brand = zos.config.zSpark.get("title") if zos and hasattr(zos, 'config') and hasattr(zos.config, 'zSpark') and zos.config.zSpark else None
            page_ztitle = zVaFile_meta.get("zTitle") if zVaFile_meta else None
            
            # Construct full page title:
            # - If zTitle exists: "zSpark.title - zTitle" (e.g., "zCloud - zOS")
            # - Otherwise: just "zSpark.title" (e.g., "zCloud")
            if page_ztitle and app_brand:
                page_title = f"{app_brand} - {page_ztitle}"
            elif page_ztitle:
                page_title = page_ztitle
            else:
                page_title = app_brand
            
            # Set title in template context for Jinja {{ title }}
            if page_title:
                context["title"] = page_title
            
            # zWalker adds the websocket block the client needs to hydrate — the ONLY
            # difference from the template path. WS host/port fallback SSOT:
            # a_zConfig.config_websocket (never hardcode loopback/port here).
            _ws = getattr(zos.config, 'websocket', None) if (zos and hasattr(zos, 'config')) else None
            from zOS.L1_Foundation.a_zConfig.zConfig_modules.network.config_websocket import (
                DEFAULT_HOST as _WS_DEFAULT_HOST,
                DEFAULT_PORT as _WS_DEFAULT_PORT,
            )
            # WS host must MATCH the page host so the host-scoped zsid cookie
            # (SameSite=Lax) rides the WS upgrade — a loopback/localhost mismatch
            # makes the browser drop it. Advertise the request Host; keep the WS port.
            _req_host = None
            try:
                _host_hdr = self.handler.headers.get('Host')
                if _host_hdr:
                    _req_host = _host_hdr.rsplit(':', 1)[0].strip() or None
            except Exception:  # pylint: disable=broad-except
                _req_host = None
            _ws_host = _req_host or (_ws.host if _ws else _WS_DEFAULT_HOST)
            # Shared server-render tail (SSOT) — nav + head/title/watermark inject.
            html_content = self._finalize_page(
                html_content, zos, resolved_navbar, app_brand, page_title,
                context, zVaFile_meta,
                extra_config={"websocket": {
                    "ssl_enabled": _ws.ssl_enabled if _ws else False,
                    "host": _ws_host,
                    "port": _ws.port if _ws else _WS_DEFAULT_PORT,
                }},
            )

            # Send HTML response with cache headers. _status_code lets styled
            # error pages (UI/error/zUI.<code>) render through this same path but
            # carry their real HTTP status (e.g. 404) instead of 200.
            html_bytes = html_content.encode('utf-8')

            self.handler.send_response(route.get("_status_code", 200))
            self.handler.send_header("Content-type", "text/html; charset=utf-8")
            self.handler.send_header("Content-length", len(html_bytes))
            self.handler.cache_manager.add_cache_headers(
                self.handler, 
                file_path=None,
                file_type="ui",
                content=html_bytes
            )
            self.handler.end_headers()
            self.handler.wfile.write(html_bytes)

            if self.logger:
                self.logger.debug(f"[RouteDispatcher] Served zWalker route: {self.handler.path}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"[RouteDispatcher] zWalker rendering error: {e}")
            return self.handler.send_error(500, f"zWalker rendering failed: {str(e)}")

