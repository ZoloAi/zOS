# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/handler.py

"""
Custom HTTP request handler with logging integration (Facade Pattern)

This module acts as a facade, delegating to specialized handler modules:
- SecurityChecker: Path validation and access control
- StaticFileHandler: Static file serving
- RouteDispatcher: Route matching and type-specific handling

The facade keeps the HTTP protocol integration while delegating business logic.
"""

from http.server import SimpleHTTPRequestHandler

from .http_headers import build_response_headers
from ..utils.zserver_constants import MOUNT_UI, HEALTH_PATH


class LoggingHTTPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP request handler with zOS logger integration + routing (Facade Pattern)"""

    def __init__(self, *args, logger=None, router=None, route_manager=None,
                 mount_manager=None, cache_manager=None, config=None, **kwargs):
        """
        Initialize HTTP request handler.
        
        Args:
            logger: Logger instance
            router: HTTPRouter instance (optional, legacy/explicit binding)
            route_manager: RouteManager instance (optional). When provided, the
                router is resolved PER REQUEST via route_manager.get_router() —
                http.server builds a fresh handler per request, so a hot reload
                that swaps the router is seen by the very next request with zero
                downtime. Falls back to the explicit `router` arg when absent.
            mount_manager: MountManager instance for file serving
            cache_manager: CacheManager instance for HTTP caching
            config: ConfigManager instance (response policy SSOT: body cap, CORS)
        """
        self.logger = logger
        # Per-request router resolution (SSOT for hot reload): a new handler is
        # constructed for every request, so reading get_router() here means a
        # swapped route table takes effect on the next request — no restart.
        self.router = route_manager.get_router() if route_manager is not None else router
        self.mount_manager = mount_manager
        self.cache_manager = cache_manager
        self.config = config
        
        # Backward compatibility properties (delegate to MountManager)
        self.serve_path = mount_manager.serve_path if mount_manager else "."
        self.static_mounts = mount_manager.get_all_mounts() if mount_manager else {}

        # Initialize modular handlers (lazy imports to avoid circular dependencies)
        from .security_checks import SecurityChecker
        from ..rendering.static_file_handler import StaticFileHandler
        from .route_dispatcher import RouteDispatcher
        self.security = SecurityChecker()
        self.static_handler = StaticFileHandler(self)
        # Key off the RESOLVED router (self.router), not the raw `router` arg — the
        # router may have been resolved per-request from route_manager.
        self.route_dispatcher = RouteDispatcher(self) if self.router else None

        super().__init__(*args, **kwargs)

    # =========================================================================
    # HTTP Protocol Methods (Core)
    # =========================================================================

    def log_message(self, format, *args):
        """Override to use zOS logger instead of stderr"""
        if self.logger:
            self.logger.info(f"[zServer] {self.address_string()} - {format % args}")
        else:
            # Fallback to default behavior if no logger
            super().log_message(format, *args)

    def end_headers(self):
        """Emit the shared security headers (+ CORS when configured) on every response.

        Header policy is centralized in http_headers (SSOT) so dev and WSGI are
        byte-identical. CORS is same-origin by default; it appears only when an
        operator sets cors_origin — never a wildcard.
        """
        cors_origin = getattr(self.config, "cors_origin", "") if self.config else ""
        for name, value in build_response_headers(cors_origin):
            self.send_header(name, value)
        super().end_headers()

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight"""
        self.send_response(200)
        self.end_headers()

    def _serve_health(self) -> bool:
        """Answer the reserved readiness probe (HEALTH_PATH) and return True if handled.

        Intercepted before security/mounts/routing so it can never collide with a
        user route or be gated by RBAC. Readiness is deliberately deeper than a TCP
        port being open: 200 only once a routing table is actually built (boot has
        progressed past route loading); 503 while still starting or after a failed
        route build. This is the single contract the blue-green coordinator (and a
        prod ingress/k8s probe) gates traffic flips on.
        """
        if self.path.split("?", 1)[0] != HEALTH_PATH:
            return False
        ready = self.router is not None
        import json
        body = json.dumps({
            "status": "ready" if ready else "starting",
            "routes": len(getattr(self.router, "routes", {}) or {}) if ready else 0,
        }).encode("utf-8")
        self.send_response(200 if ready else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    # =========================================================================
    # Shared request guards (run on EVERY verb — dev + WSGI, since the bridge
    # inherits these do_* methods). Path blocking and the body cap used to live
    # only on do_GET / the WSGI read; both are now uniform across all methods.
    # =========================================================================

    def _reject_if_blocked(self) -> bool:
        """Block sensitive paths (models/, .zEnv, dotfiles, …) on any method."""
        if self.security.is_path_blocked(self.path):
            if self.logger:
                self.logger.warning(f"[SECURITY] Blocked access attempt to: {self.path}")
            self.send_error(403, "Access Forbidden")
            return True
        return False

    def _reject_if_oversize(self) -> bool:
        """413 a request whose Content-Length exceeds the configured body cap (anti-DoS)."""
        cap = getattr(self.config, "max_body_bytes", 0) if self.config else 0
        if not cap or cap <= 0:
            return False
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            length = 0
        if length > cap:
            if self.logger:
                self.logger.warning(
                    f"[SECURITY] Payload too large ({length} > {cap}) for {self.command} {self.path}"
                )
            self.send_error(413, "Payload Too Large")
            return True
        return False

    def list_directory(self, path):
        """Disable directory listing for security"""
        self.send_error(403, "Directory listing is disabled")
        return None

    def send_error(self, code, message=None, explain=None):
        """
        Override send_error to serve custom zTheme error pages.
        
        Looks for templates/{code}.html first, falls back to built-in pages.
        """
        try:
            # Try to serve custom error page from templates/
            import os
            template_folder = self.mount_manager.get_folder_path("templates")
            error_page_path = os.path.join(template_folder, f"{code}.html")

            if os.path.exists(error_page_path):
                # Serve custom error page
                with open(error_page_path, 'rb') as f:
                    content = f.read()

                self.send_response(code)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.send_header("Content-length", len(content))
                self.end_headers()
                self.wfile.write(content)
                return
        except Exception as e:
            if self.logger:
                self.logger.error(f"[Handler] Error serving custom error page: {e}")

        # Fallback to built-in error pages
        from ..rendering.error_pages import get_error_page, has_error_page

        if has_error_page(code):
            html = get_error_page(code, message)
            content = html.encode('utf-8')

            self.send_response(code)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-length", len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            # Ultimate fallback to Python's default
            super().send_error(code, message, explain)

    def do_GET(self):
        """
        Handle GET requests with Flask-like conventions (v1.5.12 - SECURITY ENHANCED).
        
        Flow:
            0. SECURITY: Block access to sensitive paths (models/, .zEnv, etc.)
            1. Check for favicon.ico and serve default if not found
            2. Check for /static/* and auto-serve from static_folder
            3. Check for /UI/* and auto-serve from ui_folder (zVaF files)
            4. If router exists: Use declarative routing
            5. Otherwise: Fallback to static file serving (current behavior)
        """
        # Reserved readiness probe — answered before anything else (no routing/RBAC).
        if self._serve_health():
            return

        # SECURITY v1.5.12: Block access to sensitive folders and files
        if self._reject_if_blocked():
            return

        # Handle favicon.ico with default zolo favicon
        if self.path == '/favicon.ico':
            return self.static_handler.serve_default_favicon()

        # Canonical zSys assets — stream zOS's own SSOT data files (e.g. the emoji
        # a11y JSON) so the Bifrost client reads the exact file the zCLI does,
        # without each app copying it into static/.
        if self.path.startswith('/zsys/accessibility/'):
            asset_name = self.path.split('?', 1)[0].rsplit('/', 1)[-1]
            return self.static_handler.serve_zsys_asset(asset_name)

        # Check all mounts (unified handling via MountManager)
        mount_info = self.mount_manager.get_mount_for_path(self.path)
        if mount_info:
            url_prefix, fs_path = mount_info
            # Determine mount type for specialized handling
            if url_prefix == MOUNT_UI:
                # Case-insensitive UI file serving
                return self.static_handler.serve_ui_file()
            elif url_prefix == '/static/':
                return self.static_handler.serve_static_file()
            else:
                # Custom mount (plugins, etc.)
                return self.static_handler.serve_mounted_file(url_prefix, fs_path)

        # Check if router exists (declarative routing mode)
        if self.router:
            return self.route_dispatcher.handle_routed_request()

        # No router - fallback to static file serving
        if self.logger:
            self.logger.warning(f"[Handler] No router - falling back to static file serving for: {self.path}")
        return super().do_GET()

    def do_POST(self):
        """
        Handle POST requests for forms and APIs (v1.5.7 Phase 1.2).
        
        Flow:
            0. SECURITY: block sensitive paths + enforce body cap (all verbs)
            1. If router exists: Use declarative routing
            2. Otherwise: Return 405 Method Not Allowed
        """
        if self._reject_if_blocked() or self._reject_if_oversize():
            return
        # Check if router exists (declarative routing mode)
        if self.router:
            return self.route_dispatcher.handle_routed_request()

        # No router - POST not supported
        return self.send_error(405, "POST not supported without routing")

    def do_PUT(self):
        """Handle PUT requests — routes to zAPI handler (update operations)."""
        if self._reject_if_blocked() or self._reject_if_oversize():
            return
        if self.router:
            return self.route_dispatcher.handle_routed_request()
        return self.send_error(405, "PUT not supported without routing")

    def do_DELETE(self):
        """Handle DELETE requests — routes to zAPI handler (delete operations)."""
        if self._reject_if_blocked():
            return
        if self.router:
            return self.route_dispatcher.handle_routed_request()
        return self.send_error(405, "DELETE not supported without routing")

    def do_PATCH(self):
        """Handle PATCH requests — routes to zAPI handler (partial update)."""
        if self._reject_if_blocked() or self._reject_if_oversize():
            return
        if self.router:
            return self.route_dispatcher.handle_routed_request()
        return self.send_error(405, "PATCH not supported without routing")
