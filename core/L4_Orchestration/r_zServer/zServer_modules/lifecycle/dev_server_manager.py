# zOS/core/L4_Orchestration/r_zServer/zServer_modules/lifecycle/dev_server_manager.py

"""
DevServerManager - Development server lifecycle management

Handles:
- http.server setup and configuration
- SSL context creation
- Server thread management
- Development mode lifecycle (start, stop, status)
"""

import threading
import functools
from http.server import HTTPServer

from ..routing.handler import LoggingHTTPRequestHandler


class _ReusePortHTTPServer(HTTPServer):
    """HTTPServer that sets SO_REUSEPORT so a zero-downtime self-replace can bind a
    green instance on the SAME port while blue still serves. The kernel load-balances
    new connections across both SO_REUSEPORT listeners until blue drains and exits,
    leaving green sole owner — no ``Address already in use`` during the handoff.
    """

    allow_reuse_port = True  # Python 3.11+ → server_bind sets SO_REUSEPORT


class DevServerManager:
    """
    Manages the development HTTP server (http.server).
    
    Handles server lifecycle for Development/Testing modes using Python's
    built-in http.server running in a background thread.
    """

    def __init__(self, config_manager, mount_manager, route_manager, cache_manager, logger):
        """
        Initialize DevServerManager.
        
        Args:
            config_manager: ConfigManager instance
            mount_manager: MountManager instance
            route_manager: RouteManager instance
            cache_manager: CacheManager instance
            logger: zOS logger instance
        """
        self.config = config_manager
        self.mounts = mount_manager
        self.route_manager = route_manager
        self.cache_manager = cache_manager
        self.logger = logger

        self.server = None
        self.thread = None
        self._running = False

    def start(self):
        """
        Start http.server in background thread.
        
        Creates an HTTPServer with custom handler, optionally wraps with SSL,
        and starts serving in a daemon thread.
        
        Raises:
            OSError: If port is already in use or server fails to start
        """
        if self._running:
            self.logger.warning("[zServer] Server is already running")
            return

        # NOTE: no os.chdir — the handler is rooted at serve_path via `directory=`
        # (see start handler wiring). This keeps the dev runner's cwd posture
        # identical to waitress (which never chdirs) and avoids a process-wide
        # cwd mutation that leaked to unrelated subsystems.
        self.logger.info("[zServer] Starting in Development mode (http.server)...")

        try:
            # Create handler with logger, router, mount manager, cache manager, and
            # config (response policy SSOT: body cap + CORS). `directory=` keeps the
            # no-router static fallback rooted at serve_path WITHOUT a process-wide
            # os.chdir (which used to leak to the whole process and diverge from
            # waitress, which never chdirs).
            # Pass the route_manager (not a fixed router): http.server builds a
            # fresh handler per request, so resolving get_router() in the handler
            # means a hot reload's swapped table is live on the next request.
            handler = functools.partial(
                LoggingHTTPRequestHandler,
                logger=self.logger,
                route_manager=self.route_manager,
                mount_manager=self.mounts,
                cache_manager=self.cache_manager,
                config=self.config,
                directory=self.config.serve_path,
            )

            # Create HTTP server (SO_REUSEPORT so a self-replace green can co-bind).
            self.server = _ReusePortHTTPServer((self.config.host, self.config.port), handler)

            # Wrap with SSL if enabled
            ssl_context = self._create_ssl_context()
            if ssl_context:
                self.server.socket = ssl_context.wrap_socket(
                    self.server.socket,
                    server_side=True
                )
                protocol = "https"
                self.logger.info("[zServer] SSL/TLS encryption enabled (HTTPS)")
            else:
                protocol = "http"
                # Surface a silent downgrade: config asked for TLS but no usable
                # cert/key was found, so we're serving PLAIN HTTP. Without this the
                # operator sees http:// and assumes a config bug. Run `z certs --dev`.
                if getattr(self.config, "ssl_enabled", False):
                    self.logger.warning(
                        "[zServer] ssl_enabled=true but no usable cert/key — "
                        "serving PLAIN HTTP. Generate a local cert with `z certs --dev` "
                        "or check HTTP_SSL_CERT / HTTP_SSL_KEY."
                    )

            self._running = True

            # Start server in background thread
            self.thread = threading.Thread(target=self._run_server, daemon=True)
            self.thread.start()

            # Consolidated INFO log
            self.logger.info(f"[zServer] Server ready at {protocol}://{self.config.host}:{self.config.port} (serving: {self.config.serve_path})")

        except OSError as e:
            self._running = False
            if e.errno == 48:  # Address already in use
                error_msg = f"[zServer] Port {self.config.port} already in use"
                self.logger.error(error_msg)
                raise OSError(error_msg) from e
            raise
        except Exception as e:
            self._running = False
            self.logger.error(f"[zServer] Failed to start: {e}")
            raise

    def _run_server(self):
        """
        Run server (called in background thread).
        
        Serves requests until shutdown is called.
        """
        try:
            self.server.serve_forever()
        except Exception as e:
            self.logger.error(f"[zServer] Server error: {e}")
        finally:
            self._running = False

    def stop(self):
        """
        Stop http.server.
        
        Gracefully shuts down the server and waits for the thread to finish.
        """
        if not self._running:
            self.logger.warning("[zServer] Server is not running")
            return

        if self.server:
            self.logger.info("[zServer] Stopping HTTP server...")

            # Mark as not running first to prevent new requests
            self._running = False

            # Shutdown must be called from a different thread to avoid deadlock
            shutdown_thread = threading.Thread(target=self.server.shutdown)
            shutdown_thread.daemon = True
            shutdown_thread.start()
            shutdown_thread.join(timeout=2)

            # Close the server socket
            self.server.server_close()

            # Wait for server thread to finish
            if self.thread:
                self.thread.join(timeout=2)

            self.logger.info("[zServer] HTTP server stopped")

    def is_running(self) -> bool:
        """
        Check if server is running.
        
        Returns:
            bool: True if server is running
        """
        return self._running

    def _create_ssl_context(self):
        """
        Create SSL context from config if SSL is enabled.
        
        Delegates to zComm Layer 0 SSL primitive for consistent SSL handling
        across all zOS servers (HTTP, WebSocket, etc.).
        
        Returns:
            ssl.SSLContext if SSL enabled and configured, None otherwise
        """
        # Check if SSL is enabled in config
        if not self.config.ssl_enabled:
            return None

        # Lazy import to avoid circular dependency
        from zOS.L1_Foundation.b_zComm.zComm_modules.comm_ssl import create_ssl_context  # type: ignore[import-not-found]

        # Delegate to zComm Layer 0 SSL primitive
        return create_ssl_context(
            ssl_enabled=self.config.ssl_enabled,
            ssl_cert=self.config.ssl_cert,
            ssl_key=self.config.ssl_key,
            logger=self.logger,
            log_prefix="[zServer]"
        )
