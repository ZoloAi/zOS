# zOS/core/L4_Orchestration/r_zServer/zServer_modules/lifecycle/waitress_manager.py

"""
WaitressManager - cross-platform production WSGI runner.

Waitress is a pure-Python, production-grade WSGI server that runs identically on
Windows / macOS / Linux (no fork model, no C build). Unlike prefork WSGI servers
it serves IN-PROCESS, so it drives the live server's WSGI app directly — the same unified
pipeline (SecurityChecker, RBAC, all route types) the dev server uses, with the
real ``zos``. No generated worker module, no subprocess, no ``zos=None`` gap.

TLS is intentionally NOT handled here: agnostic production terminates TLS at an
upstream ingress/load balancer. (Local dev HTTPS uses the ``dev`` runner.)
"""

import threading


class WaitressManager:
    """Serves the live WSGI app via Waitress in a background thread."""

    DEFAULT_THREADS = 4

    def __init__(self, config_manager, get_app, logger):
        """
        Args:
            config_manager: ConfigManager (host/port/ssl).
            get_app: zero-arg callable returning the live WSGI app
                     (``zos.server.get_wsgi_app()``) — built lazily at start so
                     the worker holds the real, fully-initialized zServer.
            logger: zOS logger instance.
        """
        self.config = config_manager
        self._get_app = get_app
        self.logger = logger
        self._server = None
        self._thread = None
        self._running = False

    def start(self):
        if self._running:
            self.logger.warning("[zServer] Server is already running")
            return

        try:
            from waitress import create_server
        except ImportError as exc:
            raise RuntimeError(
                "[zServer] 'waitress' runner selected but waitress is not installed. "
                "Install it: pip install waitress"
            ) from exc

        if self.config.ssl_enabled:
            self.logger.warning(
                "[zServer] waitress does not terminate TLS — expecting HTTPS at an "
                "upstream ingress/proxy. Ignoring ssl_cert/ssl_key for this runner."
            )

        app = self._get_app()
        self._server = create_server(
            app,
            host=self.config.host,
            port=self.config.port,
            threads=self.DEFAULT_THREADS,
        )
        self._running = True
        self._thread = threading.Thread(
            target=self._run_server, daemon=True, name="zServer-waitress"
        )
        self._thread.start()
        self.logger.info(
            f"[zServer] Server ready at http://{self.config.host}:{self.config.port} "
            f"(runner: waitress, threads: {self.DEFAULT_THREADS})"
        )

    def _run_server(self):
        try:
            self._server.run()
        except Exception as e:  # pylint: disable=broad-except
            self.logger.error(f"[zServer] waitress error: {e}")
        finally:
            self._running = False

    def stop(self):
        if not self._running:
            self.logger.warning("[zServer] Server is not running")
            return
        self._running = False
        if self._server:
            self.logger.info("[zServer] Stopping waitress server...")
            try:
                # close() unblocks the run() loop from another thread
                self._server.close()
            except Exception as e:  # pylint: disable=broad-except
                self.logger.warning(f"[zServer] waitress close error: {e}")
            self._server = None
        if self._thread:
            self._thread.join(timeout=2)
        self.logger.info("[zServer] waitress server stopped")

    def is_running(self) -> bool:
        return self._running and (self._thread is not None and self._thread.is_alive())
