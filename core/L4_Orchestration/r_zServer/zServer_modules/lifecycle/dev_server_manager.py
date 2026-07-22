# zOS/core/L4_Orchestration/r_zServer/zServer_modules/lifecycle/dev_server_manager.py

"""
DevServerManager - Development server lifecycle management

Handles:
- http.server setup and configuration
- SSL context creation
- Server thread management
- Development mode lifecycle (start, stop, status)
"""

import errno
import os
import socket
import threading
import functools
from http.server import HTTPServer

from ..routing.handler import LoggingHTTPRequestHandler


class _ReusePortHTTPServer(HTTPServer):
    """HTTPServer that sets SO_REUSEPORT so a zero-downtime self-replace can bind a
    green instance on the SAME port while blue still serves. The kernel load-balances
    new connections across both SO_REUSEPORT listeners until blue drains and exits,
    leaving green sole owner — no ``Address already in use`` during the handoff.

    The flag cuts both ways (#22, and zGuard#7 for the WS twin): with it, bind
    SUCCEEDS on top of whatever instance already owns the port, the port-keyed
    registry sees only one of N, and z swap/z reload can't tell duplicates exist.
    So server_bind first probes with a PLAIN socket: a genuinely-taken port is
    only co-bindable by a self-replace green (marked by the swap sentinel in its
    env); any other boot gets the honest ``Address already in use``.
    """

    allow_reuse_port = True  # Python 3.11+ → server_bind sets SO_REUSEPORT

    def server_bind(self):
        host, port = self.server_address[:2]
        if (hasattr(socket, "SO_REUSEPORT")
                and not os.environ.get("ZOS_SWAP_READY_FILE")
                and self._port_taken(host, port)):
            raise OSError(
                errno.EADDRINUSE,  # callers already handle this errno path
                f"port {port} is already owned by another running instance — "
                f"refusing to co-bind (zOS#22). Stop it, `z swap` it, or pick "
                f"another HTTP_PORT.",
            )
        super().server_bind()

    @staticmethod
    def _port_taken(host, port):
        """Plain-bind probe (SO_REUSEADDR only, like HTTPServer's own bind) —
        sees a live flag-carrying listener as taken, tolerates TIME_WAIT."""
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
            return False
        except OSError:
            return True
        finally:
            probe.close()


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

        # Port hunting (zOS#43): pinned port = sacred (fail loud below, never
        # hunt); unpinned default = zOS decides — walk the window for a free
        # port BEFORE constructing the server. The chosen port is written back
        # into config so every downstream consumer (instance registry, get_url,
        # zOpen media URLs, the ready banner) reads the truth, not the wish.
        requested_port = self.config.port
        chosen_port = self._resolve_port()
        if chosen_port != requested_port:
            self.config.port = chosen_port
            underlying = getattr(self.config, "config", None)
            if underlying is not None:
                underlying.port = chosen_port

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

            # The address banner goes to STDOUT unconditionally (zOS#43): a
            # hunted port nobody announces is worse than a crash, and the
            # logger channel is environment-shaped (and wounded — zOS#6's
            # 0-byte files). This one line is the user's door.
            moved = ""
            if chosen_port != requested_port:
                moved = f"   ({requested_port} busy — moved over)"
            print(f"[zOS] app  {protocol}://{self.config.host}:{self.config.port}{moved}",
                  flush=True)

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

    def _resolve_port(self):
        """Resolve the port to bind (zOS#43 — the pinned-vs-hunt doctrine).

        PINNED (zSpark/zEnv/env said a number): return it untouched — a taken
        pinned port must fail loudly in server_bind, never wander; deployments,
        launchd, and proxies all point at pins. Also never hunt mid self-replace
        (the swap-green MUST co-bind the same port — that's the whole handoff).

        UNPINNED (bare code default): the user said "zOS decides" — walk the
        deterministic window (DEFAULT..+PORT_HUNT_WINDOW-1) for the first free
        port, using the same plain-bind probe the co-bind guard trusts. A fully
        exhausted window falls through to the requested port and the honest
        EADDRINUSE — hunting must never turn a full house into a silent hang.
        """
        port = self.config.port
        if getattr(self.config, "port_pinned", True):
            return port
        if os.environ.get("ZOS_SWAP_READY_FILE"):
            return port

        from zOS.L1_Foundation.a_zConfig.zConfig_modules.network.config_http_server import (
            PORT_HUNT_WINDOW,
        )
        host = self.config.host
        for candidate in range(port, port + PORT_HUNT_WINDOW):
            if not _ReusePortHTTPServer._port_taken(host, candidate):
                if candidate != port:
                    self.logger.info(
                        f"[zServer] Port {port} busy and unpinned — hunted to "
                        f"{candidate} (window {port}-{port + PORT_HUNT_WINDOW - 1}, zOS#43)")
                return candidate
        self.logger.error(
            f"[zServer] No free port in the hunt window "
            f"{port}-{port + PORT_HUNT_WINDOW - 1} — binding {port} to fail honestly")
        return port

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
