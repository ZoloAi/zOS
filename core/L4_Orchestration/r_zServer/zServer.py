# zOS/core/L4_Orchestration/r_zServer/zServer.py

"""
zServer - Lightweight HTTP Server Facade

Minimal facade that delegates to specialized managers for:
- Configuration management
- Static mount management
- Route detection and loading
- Schema auto-initialization
- Server lifecycle (Development/Production modes)

Designed to work standalone or alongside zBifrost WebSocket server.
"""


__version__ = "1.0.0"
from .zServer_modules.core.config_manager import ConfigManager
from .zServer_modules.core.mount_manager import MountManager
from .zServer_modules.core.route_manager import RouteManager
from .zServer_modules.core.schema_manager import SchemaManager
from .zServer_modules.core.cache_manager import CacheManager
from .zServer_modules.lifecycle.dev_server_manager import DevServerManager
from .zServer_modules.lifecycle.lifecycle_manager import LifecycleManager


class zServer:
    """
    Lightweight HTTP server facade.
    
    Delegates all responsibilities to specialized managers:
    - ConfigManager: Configuration and path resolution
    - MountManager: Static file mount management
    - RouteManager: Route detection and loading
    - SchemaManager: Database schema initialization
    - DevServerManager: Development server lifecycle
    - LifecycleManager: Orchestrates dev vs production modes
    
    Features:
    - Serves static files (HTML, CSS, JS)
    - Declarative routing via zServer route files (.zolo, .yaml, .json)
    - Auto-mounts plugins
    - Auto-initializes database schemas
    - Runs in background thread (dev) or in-process Waitress (production)
    - Integrates with zOS logger
    - CORS enabled for local development
    """

    def __init__(self, logger, *, zos, config):
        """
        Initialize zServer subsystem.
        
        Args:
            logger: zOS logger instance
            zos: zOS instance (required for routing, auth, data integration)
            config: HttpServerConfig instance from zConfig (required)
        """
        self.logger = logger
        self.zos = zos

        # Initialize managers
        self.config_manager = ConfigManager(config, zos, logger)
        self.mount_manager = MountManager(
            self.config_manager.serve_path,
            self.config_manager.static_mounts,
            logger
        )
        self.cache_manager = CacheManager(
            self.config_manager,
            logger
        )
        self.route_manager = RouteManager(
            self.config_manager.serve_path,
            zos,
            logger
        )
        self.schema_manager = SchemaManager(
            self.config_manager.serve_path,
            zos,
            logger
        )

        # Setup phase - only if server is enabled
        if self.config_manager.enabled:
            # Auto-mount common folders
            # Note: Bifrost removed - configure via ZSERVER_MOUNTS in zEnv (Dev) or use CDN (Prod)
            self.mount_manager.auto_mount_plugins()
            self.mount_manager.auto_mount_styles()
            self.mount_manager.auto_mount_zsyntax()

            # Setup routes
            if self.config_manager.routes_file:
                self.route_manager.routes_files = [self.config_manager.routes_file]
            else:
                self.route_manager.auto_detect_routes_files()

            # Build the router even with ZERO route files — the default `/` zWalker
            # is auto-injected inside load_and_merge_routes (SSOT for zero-config
            # apps: no routes/ folder needed just to serve the zSpark homepage).
            if zos:
                self.route_manager.load_and_merge_routes(self.route_manager.routes_files)

            # Auto-initialize database schemas
            if zos:
                self.schema_manager.auto_detect_and_initialize()

            # Log initialization (consolidated)
            self.logger.info(f"[zServer] Initialized - serving from: {self.config_manager.serve_path}")
            
            # Log all mounts (default + custom)
            all_mounts = self.mount_manager.get_all_mounts()
            if all_mounts:
                mount_names = ", ".join([prefix.strip('/') for prefix in all_mounts.keys()])
                self.logger.info(f"[zServer] Mounts: {len(all_mounts)} registered ({mount_names})")
                for url_prefix, fs_path in all_mounts.items():
                    self.logger.debug(f"[zServer]   {url_prefix} → {fs_path}")

            if self.route_manager.get_router():
                self.logger.debug(
                    f"[zServer] Declarative routing enabled "
                    f"with {len(self.route_manager.routes_files)} file(s)"
                )
        else:
            self.logger.debug("[zServer] Disabled - skipping route/schema loading")

        # Initialize lifecycle manager
        dev_manager = DevServerManager(
            self.config_manager,
            self.mount_manager,
            self.route_manager,
            self.cache_manager,
            logger
        )

        self.lifecycle_manager = LifecycleManager(
            self.config_manager,
            self.route_manager,
            dev_manager,
            self.mount_manager,
            self.cache_manager,
            logger
        )

    def start(self):
        """
        Start HTTP server (deployment-aware).
        
        Delegates to LifecycleManager which routes to:
        - Development/Testing → http.server (background thread)
        - Production → Waitress (in-process, cross-platform)
        """
        self.lifecycle_manager.start()

    def stop(self):
        """Stop HTTP server (works in all modes)."""
        self.lifecycle_manager.stop()

    def reload(self) -> dict:
        """
        Hot-reload the served app — re-scan routes/zAPIs + bust parsed-file cache.

        Zero downtime: the socket, WS bridge, and live sessions are untouched; the
        next request resolves against the new route table. Fail-safe: a broken edit
        keeps the previous table live. Triggered by SIGHUP / ``z reload`` / Ctrl+R.

        Returns:
            dict: {"ok": bool, "routes": int, "zapis": int, "error": str|None}
        """
        return self.lifecycle_manager.reload()

    def swap(self) -> dict:
        """Zero-downtime self-replace — spawn a fresh copy of this app on the SAME
        port, hand off, and exit. Unlike :meth:`reload` (in-place re-scan of
        declarative config) this picks up new Python / a patched zGuard binary,
        because the replacement is a brand-new interpreter. Triggered by SIGUSR2 /
        ``z swap``. Fail-safe: if green never goes ready, blue stays live."""
        return self.lifecycle_manager.self_replace()

    def wait(self):
        """
        Block until server is interrupted.
        
        Keeps the process alive while the server runs. Signal handlers (SIGINT/SIGTERM)
        registered by zOS will automatically call shutdown, which stops the server.
        """
        self.lifecycle_manager.wait()

    def is_running(self) -> bool:
        """Check if server is running (works in all modes)."""
        return self.lifecycle_manager.is_running()

    def get_wsgi_app(self):
        """
        Build the WSGI application over THIS live server (real router + real zos).

        Used by the in-process Waitress runner and by external WSGI hosts that
        import the static ``wsgi.py`` (each boots its own zOS and calls this).
        Because it wraps the live server, the WSGI app inherits the full request
        pipeline — security checks, RBAC, and every route type — identical to dev.
        """
        from .zServer_modules.lifecycle.wsgi_app import zServerWSGIApp
        return zServerWSGIApp(self)

    def get_url(self) -> str:
        """Get server URL."""
        protocol = "https" if self.config_manager.ssl_enabled else "http"
        return f"{protocol}://{self.config_manager.host}:{self.config_manager.port}"

    def health_check(self) -> dict:
        """
        Get health status of HTTP server.
        
        Returns:
            dict: Server health status with keys:
                - running (bool): Whether server is running
                - host (str): Server host address
                - port (int): Server port
                - url (str|None): Server URL (None if not running)
                - serve_path (str): Directory being served
        """
        return {
            "running": self.is_running(),
            "host": self.config_manager.host,
            "port": self.config_manager.port,
            "url": self.get_url() if self.is_running() else None,
            "serve_path": self.config_manager.serve_path
        }

    # Public property accessors for zOS subsystem integration
    @property
    def serve_path(self) -> str:
        """Get serve path (used by zParser, zOpen, and other subsystems)."""
        return self.config_manager.serve_path

    @property
    def router(self):
        """Get router instance (used by request handlers)."""
        return self.route_manager.get_router()

    @property
    def static_mounts(self) -> dict:
        """Get static mounts (used by request handlers)."""
        return self.mount_manager.get_static_mounts()
