# zOS/core/L4_Orchestration/r_zServer/zServer_modules/lifecycle/lifecycle_manager.py

"""
LifecycleManager - Server lifecycle orchestration

Handles:
- Server runner selection (dev / waitress) — both BIND a socket, SINGLE-PROCESS
- Server start/stop coordination
- Wait/blocking behavior

WSGI note: WSGI is the PEP 3333 calling convention, not a runner. zServer exposes
the app callable via get_wsgi_app(); waitress (and any external host) consume it.
External hosts import the app's static `wsgi.py` (see WSGI_ENTRY_MODULE). zOS no
longer generates a throwaway WSGI module nor runs a "bind nothing" posture.

Both runners are single-process by design so the in-process HTTP server and the
single stateful Bifrost WebSocket bridge coexist in one process. Multi-process
prefork servers (e.g. gunicorn) are intentionally NOT runners — each fork would
boot a competing WS bridge. Scale zBifrost horizontally (N instances + sticky LB).
"""

from zOS import time

from zOS.L1_Foundation.a_zConfig.zConfig_modules.network.config_http_server import (
    SERVER_TYPE_DEV,
    SERVER_TYPE_WAITRESS,
)


class LifecycleManager:
    """
    Orchestrates server lifecycle across single-process binding runners.

    Routes to DevServerManager (local http.server) or WaitressManager (cross-platform
    production) based on the resolved server_type.
    """

    def __init__(self, config_manager, route_manager, dev_manager, mount_manager, cache_manager, logger):
        """
        Initialize LifecycleManager.
        
        Args:
            config_manager: ConfigManager instance
            route_manager: RouteManager instance (for WSGI generation)
            dev_manager: DevServerManager instance
            mount_manager: MountManager instance
            cache_manager: CacheManager instance
            logger: zOS logger instance
        """
        self.config = config_manager
        self.route_manager = route_manager
        self.dev_manager = dev_manager
        self.mount_manager = mount_manager
        self.cache_manager = cache_manager
        self.logger = logger
        self.waitress_manager = None
        self._reload_in_progress = False
        self._swap_in_progress = False

    def _resolve_server_type(self) -> str:
        """Return the configured runner type (SSOT resolved in HttpServerConfig)."""
        return getattr(self.config, "server_type", SERVER_TYPE_DEV)

    def start(self):
        """
        Start HTTP server (runner-aware). Every runner BINDS a socket.

        ``server_type`` selects which server binds, chosen explicitly (NOT by the
        environment name). Both runners drive the same request pipeline / security /
        RBAC and are single-process:
        - "dev"      → http.server (background thread, local)
        - "waitress" → Waitress WSGI server in-process (cross-platform production)

        Serving over WSGI to an EXTERNAL host (uWSGI / serverless / any systemd-managed
        WSGI host) is not a runner — the host imports the app's static `wsgi.py`
        (zServer.get_wsgi_app()) and binds the socket itself. zOS isn't "started" in
        that case; the importing process boots zOS with ZSERVER_WSGI_WORKER=1.

        Raises:
            RuntimeError: If server is already running, or the runner's package is missing
            OSError: If port is already in use
        """
        if self.is_running():
            self.logger.warning("[zServer] Server is already running")
            return

        server_type = self._resolve_server_type()

        if server_type == SERVER_TYPE_WAITRESS:
            self._start_waitress()
        else:
            self.dev_manager.start()

        # Register in the instance registry so `z reload` (another shell) can
        # discover us — by port (unique) + a human title for the pick list.
        if self.is_running():
            try:
                from .pidfile import register_instance
                title, mode = self._instance_identity()
                register_instance(
                    port=getattr(self.config, "port", None),
                    title=title,
                    mode=mode,
                )
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.debug(f"[zServer] Could not register instance: {exc}")

        # If we were spawned as the GREEN half of a self-replace, signal the parent
        # (blue) that we are up and serving — this is the deep readiness handshake
        # that lets blue hand off and exit. No-op for a normal boot.
        self._signal_swap_ready()

    def _signal_swap_ready(self) -> None:
        """Touch the parent's readiness sentinel when booted as a self-replace green.

        ``ZOS_SWAP_READY_FILE`` is injected by blue's :meth:`self_replace`. Writing it
        here — only after the server is bound and routes are loaded — is strictly
        deeper than a port being open (same contract as ``/zhealth``). We then drop the
        var so this green's OWN future swap mints a fresh sentinel.
        """
        import os  # pylint: disable=import-outside-toplevel
        path = os.environ.get("ZOS_SWAP_READY_FILE")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(str(os.getpid()))
            self.logger.info("[zSwap] Ready — signalled parent for handoff")
        except OSError as exc:
            self.logger.debug(f"[zServer] Could not write swap readiness sentinel: {exc}")
        finally:
            os.environ.pop("ZOS_SWAP_READY_FILE", None)

    def _zolo_argv(self, spark_file: str) -> list:
        """Argv to boot a fresh zOS on ``spark_file`` (mirrors the compute driver)."""
        import os  # pylint: disable=import-outside-toplevel
        import sys  # pylint: disable=import-outside-toplevel
        import shutil  # pylint: disable=import-outside-toplevel
        override = os.environ.get("ZHOST_ZOLO_BIN")
        if override:
            return [override, spark_file]
        zolo = shutil.which("zolo")
        if zolo:
            return [zolo, spark_file]
        return [sys.executable, "-m", "zOS.main", spark_file]

    def _spark_file(self):
        """Absolute path of the zSpark that booted us (recorded at boot), or None."""
        zos = getattr(self.config, "zos", None) or getattr(self.route_manager, "zos", None)
        return getattr(zos, "zspark_file", None)

    def self_replace(self, ready_timeout: float = 30.0, drain_timeout: float = 3.0) -> dict:
        """Zero-downtime self-replacement (blue-green) of THIS running server.

        Spawns a brand-new copy of this app that co-binds our listening port(s) via
        SO_REUSEPORT, waits for it to pass the readiness handshake, then gracefully
        shuts US down and exits — leaving the new (green) process serving on the same
        port. Because green is a fresh interpreter it picks up new open-source Python
        (and a patched zGuard binary); the soft ``reload`` path can only re-read
        declarative config in-place, so code/binary updates land here.

        Fail-safe: if green never signals ready (e.g. a zGuard ABI mismatch — it can't
        boot zBifrost), we reap it and KEEP serving (blue stays live). Triggered by
        SIGUSR2 (``z swap``); runs in that handler and exits the process on a
        successful handoff.

        Returns a status dict; on success it does not return (process exits).
        """
        import os  # pylint: disable=import-outside-toplevel
        import sys  # pylint: disable=import-outside-toplevel
        import time as _time  # pylint: disable=import-outside-toplevel
        import signal as _signal  # pylint: disable=import-outside-toplevel
        import tempfile  # pylint: disable=import-outside-toplevel
        import subprocess  # pylint: disable=import-outside-toplevel

        if not self.is_running():
            self.logger.warning("[zSwap] Swap requested but server is not running")
            return {"ok": False, "error": "server not running"}
        if getattr(self, "_swap_in_progress", False):
            self.logger.warning("[zSwap] Swap already in progress — ignoring")
            return {"ok": False, "error": "swap in progress"}

        def _emit(line: str) -> None:
            print(line, flush=True)

        self._swap_in_progress = True
        try:
            spark = self._spark_file()
            if not spark or not os.path.exists(spark):
                _emit("[zSwap] Cannot self-replace — booting zSpark file is unknown.")
                return {"ok": False, "error": "spark unknown"}

            serve_path = getattr(self.config, "serve_path", None) or os.getcwd()
            ready_dir = os.path.join(tempfile.gettempdir(), "zos", "swap")
            os.makedirs(ready_dir, exist_ok=True)
            ready_file = os.path.join(ready_dir, f"ready-{os.getpid()}-{int(_time.time())}")
            try:
                if os.path.exists(ready_file):
                    os.remove(ready_file)
            except OSError:
                pass

            _emit("\n[zSwap] Zero-downtime update — starting a new instance on the same "
                  "port (current stays live)…")

            # Green inherits our env (same zEnv → same port) + the explicit port and
            # the readiness sentinel. Detached session so it outlives our exit.
            child_env = os.environ.copy()
            child_env["ZOS_SWAP_READY_FILE"] = ready_file
            port = getattr(self.config, "port", None)
            if port:
                child_env["HTTP_PORT"] = str(port)
            ws_port = getattr(self.config, "websocket_port", None) or getattr(self.config, "ws_port", None)
            if ws_port:
                child_env["WEBSOCKET_PORT"] = str(ws_port)

            try:
                proc = subprocess.Popen(
                    self._zolo_argv(spark), cwd=serve_path, env=child_env,
                    stdin=subprocess.DEVNULL, start_new_session=True,
                )
            except OSError as exc:
                _emit(f"[zSwap] Could not spawn new instance: {exc} — current stays live.")
                return {"ok": False, "error": f"spawn failed: {exc}"}

            deadline = _time.time() + ready_timeout
            while _time.time() < deadline:
                if proc.poll() is not None:
                    _emit(f"[zSwap] New instance exited before ready (code {proc.returncode}) "
                          "— keeping current. If zGuard changed, run `z patch` first.")
                    return {"ok": False, "error": "green exited early"}
                if os.path.exists(ready_file):
                    break
                _time.sleep(0.25)
            else:
                _emit("[zSwap] New instance not ready in time — rolling back (current stays live).")
                try:
                    os.killpg(os.getpgid(proc.pid), _signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    proc.terminate()
                return {"ok": False, "error": "green not ready before timeout"}

            try:
                os.remove(ready_file)
            except OSError:
                pass

            _emit(f"[zSwap] New instance ready (pid {proc.pid}). Handing off and draining…")

            # Stop accepting on OUR listeners so all new connections land on green
            # (the remaining SO_REUSEPORT listener); give in-flight work a short grace.
            try:
                self.stop()
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.debug(f"[zSwap] stop during handoff raised (continuing): {exc}")
            if drain_timeout and drain_timeout > 0:
                _time.sleep(drain_timeout)

            _emit("[zSwap] Handoff complete — new code is live on the same port. "
                  "This instance is exiting.\n")

            zos = getattr(self.config, "zos", None) or getattr(self.route_manager, "zos", None)
            try:
                if zos and hasattr(zos, "shutdown"):
                    zos.shutdown()
            finally:
                sys.exit(0)
        finally:
            self._swap_in_progress = False

    def _instance_identity(self):
        """Best-effort (title, mode) for the reload pick list, from the active zSpark."""
        zos = getattr(self.config, "zos", None) or getattr(self.route_manager, "zos", None)
        spark = getattr(zos, "spark", None) or getattr(zos, "zspark_obj", None) or {}
        if isinstance(spark, dict) and isinstance(spark.get("zSpark"), dict):
            spark = spark["zSpark"]
        if not isinstance(spark, dict):
            spark = {}
        title = spark.get("title") or spark.get("zTitle")
        mode = spark.get("zMode")
        return title, mode

    def _start_waitress(self):
        """Start the Waitress WSGI server in-process (cross-platform production)."""
        from .waitress_manager import WaitressManager

        zos = getattr(self.config, "zos", None)

        def _get_app():
            # Built lazily so we wrap the fully-initialized live server (real zos).
            return zos.server.get_wsgi_app()

        self.waitress_manager = WaitressManager(self.config, _get_app, self.logger)
        try:
            self.waitress_manager.start()
        except Exception as e:
            self.logger.error(f"[zServer] Failed to start waitress: {e}")
            self.waitress_manager = None
            raise

    def reload(self) -> dict:
        """
        Hot-reload the served app (routes / zAPIs / parsed-file cache) — no downtime.

        Re-scans ``zViews``/route files and rebuilds the route table WITHOUT touching
        the listening socket, the WS bridge, or in-memory sessions. Order matters:
        the loader's parsed-file cache is busted FIRST so the rebuild re-reads the
        edited files instead of stale parsed dicts. The rebuild is fail-safe — a
        broken edit leaves the previous table live (the site never goes dark).

        Trigger-agnostic: called by SIGHUP, ``z reload``, or Ctrl+R — all land here.

        Returns:
            dict: {"ok": bool, "routes": int, "zapis": int, "error": str|None}
        """
        from ..utils.zserver_constants import (
            RELOAD_PRINT_INITIATED, RELOAD_PRINT_ROUTES, RELOAD_PRINT_ZAPIS,
            RELOAD_PRINT_CACHE, RELOAD_PRINT_SESSIONS, RELOAD_PRINT_COMPLETE,
            RELOAD_PRINT_ABORTED, RELOAD_PRINT_ABORTED_TAIL, RELOAD_WARN_GLYPH,
            RELOAD_LOG_START, RELOAD_LOG_DONE, RELOAD_LOG_ABORTED,
            RELOAD_LOG_NOT_RUNNING, RELOAD_LOG_IN_PROGRESS,
        )
        from zSys.shutdown import SHUTDOWN_STATUS_SUCCESS, SHUTDOWN_STATUS_FAIL

        if not self.is_running():
            self.logger.warning(RELOAD_LOG_NOT_RUNNING)
            return {"ok": False, "routes": 0, "zapis": 0, "error": "server not running"}

        if getattr(self, "_reload_in_progress", False):
            self.logger.warning(RELOAD_LOG_IN_PROGRESS)
            return {"ok": False, "routes": 0, "zapis": 0, "error": "reload in progress"}

        # Reload runs from a SIGHUP handler and does NOT exit the process, so
        # stdout is never flushed by an exit — emit with flush so the receipt is
        # visible in real time even when stdout is block-buffered (non-TTY).
        def _emit(line: str) -> None:
            print(line, flush=True)

        self._reload_in_progress = True
        try:
            _emit(RELOAD_PRINT_INITIATED)
            self.logger.framework.debug(RELOAD_LOG_START)

            # 1. Bust the loader's parsed-file cache FIRST so the rebuild re-reads
            #    edited zViews/route files instead of serving stale parsed dicts.
            cache_cleared = self._bust_loader_cache()

            # 2. Rebuild the route table off to the side, then atomic swap (fail-safe).
            result = self.route_manager.reload()

            if not result.get("ok"):
                _emit(RELOAD_PRINT_ABORTED.format(fail=SHUTDOWN_STATUS_FAIL, detail=result.get("error")))
                _emit(RELOAD_PRINT_ABORTED_TAIL.format(warn=RELOAD_WARN_GLYPH))
                self.logger.warning(RELOAD_LOG_ABORTED, result.get("error"))
                return result

            ok = SHUTDOWN_STATUS_SUCCESS
            _emit(RELOAD_PRINT_ROUTES.format(ok=ok, n=result.get("routes", 0)))
            _emit(RELOAD_PRINT_ZAPIS.format(ok=ok, n=result.get("zapis", 0)))
            if cache_cleared:
                _emit(RELOAD_PRINT_CACHE.format(ok=ok))
            _emit(RELOAD_PRINT_SESSIONS.format(ok=ok))
            _emit(RELOAD_PRINT_COMPLETE.format(ok=ok))
            self.logger.info(RELOAD_LOG_DONE, result.get("routes", 0), result.get("zapis", 0))
            return result
        finally:
            self._reload_in_progress = False

    def _bust_loader_cache(self) -> bool:
        """Clear the zLoader system cache (parsed UI/route files) so a reload re-reads disk."""
        try:
            zos = getattr(self.route_manager, "zos", None) or getattr(self.config, "zos", None)
            loader = getattr(zos, "loader", None)
            cache = getattr(loader, "cache", None)
            if cache and hasattr(cache, "clear"):
                cache.clear(cache_type="system")
                return True
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.warning(f"[zServer] Loader cache bust failed (continuing): {exc}")
        return False

    def stop(self):
        """
        Stop HTTP server. Delegates to the active binding runner.
        """
        try:
            from .pidfile import unregister_instance
            unregister_instance(getattr(self.config, "port", None))
        except Exception:  # pylint: disable=broad-except
            pass

        server_type = self._resolve_server_type()

        if server_type == SERVER_TYPE_WAITRESS:
            if self.waitress_manager:
                self.waitress_manager.stop()
                self.waitress_manager = None
            return

        # Stop http.server
        self.dev_manager.stop()

    def wait(self):
        """
        Block until server is interrupted.
        
        Keeps the process alive while the server runs. Signal handlers (SIGINT/SIGTERM)
        registered by zOS will automatically call shutdown, which stops the server.
        
        This eliminates boilerplate try/except/KeyboardInterrupt blocks in applications.
        
        Note:
            - Signal handlers (Ctrl+C, SIGTERM) already registered by zOS
            - zOS.shutdown() automatically calls server.stop()
            - This method just keeps the process alive
        """
        if not self.is_running():
            self.logger.debug("[zServer] Server is not running, nothing to wait for")
            return

        try:
            while self.is_running():
                time.sleep(1)
        except KeyboardInterrupt:
            # Signal handler will call shutdown, which calls stop()
            # Just exit gracefully
            pass

    def is_running(self) -> bool:
        """
        Check if server is running (works in all modes).
        
        Returns:
            bool: True if server is running
        """
        if self.waitress_manager:
            return self.waitress_manager.is_running()
        return self.dev_manager.is_running()
