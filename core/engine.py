# zOS/core/engine.py
# ═══════════════════════════════════════════════════════════════════════════════
"""
zCLI Core Engine - Top-Level Orchestrator

4-Layer Architecture (bottom-up):
    Layer 0: Foundation       → zConfig, zComm, zLoader
    Layer 1: Core (8)         → zParser, zDisplay, zAuth, zDispatch,
                                zNavigation, zFunc, zDialog, zOpen
    Layer 2: Abstraction (3)  → zWizard, zData, zShell
    Layer 3: Orchestration    → zWalker

Thread-safe via contextvars.ContextVar. Supports zCLI and zBifrost (WebSocket) modes.
Graceful shutdown via SIGINT/SIGTERM handlers (reverse initialization order).
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS (Centralized from __init__.py per IMPORT_CENTRALIZATION_RULES.md)
# ═══════════════════════════════════════════════════════════════════════════════

import os
from pathlib import Path

from . import Any, Dict, Optional, contextvars, logging
from zSys.shutdown import (  # pylint: disable=import-error,wrong-import-order
    perform_shutdown,
    register_signal_handlers,
)
# Per-caller session indirection (Phase 1, ZAUTH_INSTANCE.notes.md §19). Leaf module,
# stdlib-only — safe to import at engine module load (no cycle).
from .L1_Foundation.a_zConfig.zConfig_modules.session import (  # pylint: disable=wrong-import-order
    session_registry,
)

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# Session Keys (4) - Used in session dict
# ─────────────────────────────────────────────────────────────────────────────
SESSION_KEY_ZS_ID: str = "zS_id"
SESSION_KEY_ZMODE: str = "zMode"
SESSION_KEY_ZMACHINE: str = "zMachine"
SESSION_KEY_ZSPARK: str = "zSpark_obj"

# ─────────────────────────────────────────────────────────────────────────────
# Mode Constants (3) - zMode values
# ─────────────────────────────────────────────────────────────────────────────
MODE_ZCLI: str = "zCLI"
MODE_ZBIFROST: str = "zBifrost"
MODE_WALKER: str = "Walker"

# ─────────────────────────────────────────────────────────────────────────────
# Logger Messages - Info (10)
# ─────────────────────────────────────────────────────────────────────────────
LOG_INIT_COMPLETE: str = "zCLI Core initialized - Mode: %s"
LOG_MODE_ZCLI: str = "Starting zCLI in zCLI mode..."
LOG_MODE_ZBIFROST: str = "Starting zCLI in zBifrost mode via zWalker..."
LOG_HTTP_START: str = "HTTP server auto-started at %s"
LOG_SESSION_INIT: str = "Session initialized:"
LOG_SESSION_ID_PREFIX: str = "  zS_id: %s"
LOG_SESSION_MODE_PREFIX: str = "  zMode: %s"
LOG_SESSION_MACHINE_PREFIX: str = "  zMachine hostname: %s"

# ─────────────────────────────────────────────────────────────────────────────
# Logger Messages - Warning (5)
# ─────────────────────────────────────────────────────────────────────────────
LOG_WARN_PLUGIN_FAIL: str = "Failed to load plugins: %s"

# ─────────────────────────────────────────────────────────────────────────────
# Logger Messages - Debug (9)
# ─────────────────────────────────────────────────────────────────────────────
LOG_DEBUG_SESSION_ID: str = "  zS_id: %s"
LOG_DEBUG_SESSION_MODE: str = "  zMode: %s"
LOG_DEBUG_SESSION_MACHINE: str = "  zMachine hostname: %s"

# ─────────────────────────────────────────────────────────────────────────────
# Layer Names (4) - For architecture documentation
# ─────────────────────────────────────────────────────────────────────────────
LAYER_0_FOUNDATION: str = "Layer 0: Foundation"
LAYER_1_CORE: str = "Layer 1: Core Subsystems"
LAYER_2_ABSTRACTION: str = "Layer 2: Core Abstraction"
LAYER_3_ORCHESTRATION: str = "Layer 3: Orchestration"

# ─────────────────────────────────────────────────────────────────────────────
# Plugin Config Keys (1)
# ─────────────────────────────────────────────────────────────────────────────
ZSPARK_PLUGINS_KEY: str = "plugins"

# ─────────────────────────────────────────────────────────────────────────────
# Context Variable Name (1)
# ─────────────────────────────────────────────────────────────────────────────
CONTEXT_VAR_NAME: str = "current_zcli"

# Global context variable for current zCLI instance (thread-safe, async-safe)
# Follows Django/Flask/FastAPI pattern for request/application context
_current_zos: contextvars.ContextVar = contextvars.ContextVar(CONTEXT_VAR_NAME, default=None)


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API - Context Access
# ═══════════════════════════════════════════════════════════════════════════════

def get_current_zos() -> Optional["zOS"]:
    """
    Get current zCLI instance from thread-local context.

    Thread-safe access following Django/Flask/FastAPI patterns. Used by zExceptions
    for auto-registration. Returns None if not in a zCLI context.
    """
    return _current_zos.get()


# ═══════════════════════════════════════════════════════════════════════════════
# CORE CLASS - zCLI
# ═══════════════════════════════════════════════════════════════════════════════

class zOS:  # pylint: disable=invalid-name
    """
    Core zCLI Engine - orchestrates 16 subsystems across 4 layers.

    Attributes (Public):
        config, comm, display, auth, dispatch, navigation, zparser, loader, zfunc,
        dialog, open, wizard, data, shell, walker, server (optional)

        logger, session, zTraceback (set by zConfig)

    Key Methods:
        run()          → Start zCLI or zBifrost mode
        run_shell()    → Explicit zCLI mode (REPL)
        run_command()  → Execute single command
        shutdown()     → Graceful cleanup (reverse init order)

    Thread-safe via contextvars. Supports context manager protocol.
    Signal handlers (SIGINT/SIGTERM) registered automatically.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Type Hints for Attributes Set by Subsystems
    # ─────────────────────────────────────────────────────────────────────────
    logger: logging.Logger          # Set by zConfig
    zTraceback: Any                 # Set by zConfig (zTraceback instance)
    # NOTE: `session` is a property (below), not a plain attribute. It resolves the
    # context-current session from session_registry, falling back to this instance's
    # default (the single CLI session) so N=1 behaviour is unchanged. §19.D.

    # ─────────────────────────────────────────────────────────────────────────
    # session — per-caller indirection (Phase 1)
    # ─────────────────────────────────────────────────────────────────────────
    @property
    def session(self) -> Dict[str, Any]:
        """The live session dict for the current context.

        Returns the context-current session if the resolver has bound one
        (zServer, later); otherwise this instance's default — the single session
        created at boot. Read path is a contextvar get + dict lookup (cheap).
        """
        current = session_registry.get_current()
        if current is not None:
            return current
        return self._session_default

    @session.setter
    def session(self, value: Dict[str, Any]) -> None:
        """Assigning ``zos.session`` registers the unit and marks it current.

        The canonical caller is ``zConfig`` at boot (``zos.session = session_data``).
        At N=1 this registers the one session and makes it the context-current, so
        the getter returns the very same dict — identical to the old plain attribute.
        """
        self._session_default = value
        if isinstance(value, dict):
            sid = session_registry.register(value)
            session_registry.set_current(sid)

    def __init__(self, zSpark_obj: Optional[Dict[str, Any]] = None, verbose: bool = False) -> None:  # pylint: disable=invalid-name
        """
        Initialize zCLI with all 17 subsystems in dependency order.

        Parameters
        ----------
        zSpark_obj : Optional[Dict[str, Any]]
            Config dict. Common keys: zMode ("zCLI"|"zBifrost"), plugins (List[str]),
            log_level, database, port. Defaults: zCLI mode, INFO logging.
        verbose : bool
            If True, show initialization output (default: False for silent mode)

        Side Effects: Registers in thread context, sets SIGINT/SIGTERM handlers,
        may auto-start HTTP server, creates session dict.
        """

        # Initialize zSpark_obj config dict
        self.zspark_obj = zSpark_obj or {}

        # Default session backing for the `session` property — set BEFORE zConfig
        # runs (zConfig assigns zos.session, which routes through the setter). Until
        # then the getter must have something to return. §19 Phase 1.
        self._session_default: Optional[Dict[str, Any]] = None

        # Shutdown coordination
        self._shutdown_requested = False
        self._shutdown_in_progress = False
        # zRaven is initialised as a subsystem below; this legacy attr is kept for
        # shutdown compat until old _auto_run_zraven code is fully removed.
        self._raven_proc = None

        # Register this instance as current context (thread-safe)
        # Enables automatic exception registration for zExceptions
        _current_zos.set(self)

        # ─────────────────────────────────────────────────────────────
        # Layer 0: Foundation
        # ─────────────────────────────────────────────────────────────
        # Initialize zConfig FIRST (machine config, environment config, session)
        # Logger and traceback are also initialized here.
        # After this call, self.session, self.logger, and self.zTraceback are ready to use
        from .L1_Foundation.a_zConfig import zConfig  # pylint: disable=import-outside-toplevel
        self.config = zConfig(zos=self, zSpark_obj=zSpark_obj, verbose=verbose)

        # zRaven runs on its OWN designated ports (app port + offset). Applied BEFORE
        # port-clearing and server bind so the bound server, the pre-flight clear, and
        # the runner's URL resolution all agree (SSOT). This is why a test run never
        # collides with — or SIGKILLs — a live `z zApp` on the default ports.
        if self.config.raven.enabled:
            self._apply_raven_port_offset()

        # Pre-flight port clear — runs before any server starts (WS + HTTP). With the
        # offset applied above, this only ever clears zRaven's OWN test ports (a stale
        # prior test server), NEVER the live app's ports.
        if self.config.raven.enabled:
            self._clear_ports_for_raven()

        # App-level logging handle (zos.log) — emit orchestrator lives in the
        # loggers SSOT (a_zConfig); this is just the public, ergonomic surface.
        from .L1_Foundation.a_zConfig.zConfig_modules.loggers import AppLog  # pylint: disable=import-outside-toplevel
        self.log = AppLog(self)

        # Initialize zComm (Communication infrastructure for zBifrost and zData)
        from .L1_Foundation.b_zComm import zComm  # pylint: disable=import-outside-toplevel
        self.comm = zComm(self)

        # Initialize display subsystem (needed by zLoader for visual feedback)
        from .L2_Handling.e_zDisplay import zDisplay  # pylint: disable=import-outside-toplevel
        self.display = zDisplay(self)
        self.mycolor = "MAIN"

        # Initialize loader subsystem (foundation - file I/O)
        from .L1_Foundation.c_zLoader import zLoader  # pylint: disable=import-outside-toplevel
        self.loader = zLoader(self)
        
        # Load plugins from zSpark immediately after zLoader (migrated from zUtils v1.7.0)
        self._load_plugins()

        # ─────────────────────────────────────────────────────────────
        # Layer 1: Core Subsystems
        # ─────────────────────────────────────────────────────────────
        # Initialize parser subsystem (transformation - content parsing)
        from .L2_Handling.d_zParser import zParser  # pylint: disable=import-outside-toplevel
        self.zparser = zParser(self)

        # Initialize authentication subsystem
        from .L2_Handling.f_zAuth import zAuth  # pylint: disable=import-outside-toplevel
        self.auth = zAuth(self)

        # Initialize dispatch subsystem
        from .L2_Handling.g_zDispatch import zDispatch  # pylint: disable=import-outside-toplevel
        self.dispatch = zDispatch(self)

        # Initialize navigation subsystem
        from .L2_Handling.h_zNavigation import zNavigation  # pylint: disable=import-outside-toplevel
        self.navigation = zNavigation(self)

        # Initialize function subsystem
        from .L2_Handling.i_zFunc import zFunc  # pylint: disable=import-outside-toplevel
        self.zfunc = zFunc(self)

        # Initialize dialog subsystem
        from .L2_Handling.j_zDialog import zDialog  # pylint: disable=import-outside-toplevel
        self.dialog = zDialog(self)

        # Initialize open subsystem
        from .L2_Handling.k_zOpen import zOpen  # pylint: disable=import-outside-toplevel
        self.open = zOpen(self)


        # ─────────────────────────────────────────────────────────────
        # Layer 2: Core Abstraction
        # ─────────────────────────────────────────────────────────────
        # Initialize the walk engine (zEngine - no upper dependencies).
        from .L3_Abstraction.l_zEngine import zEngine  # pylint: disable=import-outside-toplevel
        self.zEngine = zEngine(self)

        # Initialize data subsystem (may use zWizard for interactive operations)
        from .L3_Abstraction.m_zData import zData  # pylint: disable=import-outside-toplevel
        self.data = zData(self)

        # Initialize zLoom — the data-binding subsystem (sibling of zData). Owns
        # the binding grammar (%data / _data / zList / %token resolution / gates).
        # Constructed after zData because it runs zData reads at resolve time.
        from .L3_Abstraction.n_zLoom import zLoom  # pylint: disable=import-outside-toplevel
        self.zloom = zLoom(self)

        # Initialize zGate — the gating subsystem (sibling of zLoom). One engine for
        # every yes/no gate (auth / conditional / value). Delegates trust to
        # check_zrbac and values to zloom, so it is built after both.
        from .L3_Abstraction.n_zLoom import zGate  # pylint: disable=import-outside-toplevel
        self.zgate = zGate(self)

        # Initialize zBifrost WebSocket bridge orchestrator (Layer 2)
        # Coordinates zCLI↔Web communication using z.comm infrastructure
        from .L3_Abstraction.o_zBifrost import zBifrost  # pylint: disable=import-outside-toplevel
        self.bifrost = zBifrost(self)

        # Initialize shell and command executor (depends on zWizard, zData)
        from .L3_Abstraction.p_zShell import zShell  # pylint: disable=import-outside-toplevel
        self.shell = zShell(self)

        # Layer 3: Orchestration
        # Initialize walker subsystem
        from .L4_Orchestration.q_zWalker import zWalker  # pylint: disable=import-outside-toplevel
        # Modern walker with unified navigation (can use plugins immediately)
        self.walker = zWalker(self)

        # Initialize zServer (HTTP/WSGI server subsystem) - Layer 4 (Orchestration)
        # v1.5.8: Independent subsystem (was factory method in zComm)
        from .L4_Orchestration.r_zServer import zServer  # pylint: disable=import-outside-toplevel
        self.server = zServer(
            logger=self.logger,
            zos=self,
            config=self.config.http_server if hasattr(self.config, "http_server") else None
        )

        # Initialize zHost (control plane) - Layer 4 peer that orchestrates zServers:
        # front door (which app, wake it, hand off), instance lifecycle, and — later —
        # fleet blue-green + deploy. zServer serves one app; zHost decides which.
        from .L4_Orchestration.t_zHost import zHost  # pylint: disable=import-outside-toplevel
        self.zhost = zHost(self)

        # Auto-start if enabled in config.
        # ZRAVEN_TARGET=1 means this process is the CLI test target spawned by CLIRunner —
        # it only needs stdin/stdout, never a server. Skipping avoids port conflicts with the
        # parent zRaven process that already owns the configured port.
        import os as _os_env  # pylint: disable=import-outside-toplevel
        _is_raven_target = _os_env.environ.get("ZRAVEN_TARGET") == "1"
        # ZSERVER_WSGI_WORKER=1 means this instance was booted by a WSGI worker
        # module solely to expose its live server's WSGI app — it must NOT
        # auto-start a server itself (that would recursively spawn another runner).
        _is_wsgi_worker = _os_env.environ.get("ZSERVER_WSGI_WORKER") == "1"
        if (
            hasattr(self.config, "http_server")
            and self.config.http_server.enabled
            and not _is_raven_target
            and not _is_wsgi_worker
        ):
            self.server.start()
            # Server ready message is logged by dev_server_manager - no need for duplicate

            # v1.5.8: Auto-wait if configured (declarative lifecycle management)
            # Must happen AFTER signal handlers are registered but BEFORE returning to user code
            # Note: We defer the actual wait() call until after __init__ completes
        elif _is_raven_target and hasattr(self, 'server') and self.server is not None:
            # Subprocess skips server but still needs schemas loaded so zData insert/read work.
            # Mirrors what zServer.SchemaManager.auto_detect_and_initialize() does at boot.
            try:
                from .L4_Orchestration.r_zServer.zServer_modules.core.schema_manager import SchemaManager as _SM  # pylint: disable=import-outside-toplevel
                _serve_path = (
                    getattr(self.server, 'serve_path', None)
                    or getattr(self.config, 'serve_path', None)
                    or _os_env.getcwd()
                )
                _sm = _SM(serve_path=_serve_path, zos=self, logger=self.logger)
                _sm.auto_detect_and_initialize()
            except Exception:  # pylint: disable=broad-except
                pass

        # Initialize zRaven test subsystem (Layer 4r) — after zServer + zBifrost are ready
        from .L4_Orchestration.s_zRaven import zRaven as _zRaven  # pylint: disable=import-outside-toplevel
        self.raven = _zRaven(zos=self)

        # Initialize session (sets zMode from zSpark_obj or defaults to zCLI)
        self._init_session()

        # Resolve the runtime's platform identity (Tier-1 / zSession) via the boot
        # cascade: persistent token → env creds → zSpark policy. Read-mostly and
        # defensive — never fails boot; leaves the session anonymous if nothing
        # resolves. Runs here so zData/zLoader (ledger reads) are ready.
        #
        # CLI ONLY. The machine/instance owner (zolo login / PAT / env) is the
        # OPERATOR identity — used for `zolo push`, `z <cli-app>`, and instance
        # ownership (zApps.owner_id). It is a SEPARATE thing from a zServer RBAC
        # session: a server is multi-tenant, so every browser MUST authenticate
        # per-connection via the app's zLogin (Tier-2 applications.<app>). Adopting
        # the instance owner into the shared server session would auto-login every
        # visitor as the owner — the RBAC gate, Bifrost connection identity, and
        # dual-mode detection all read the active context. So in server mode we do
        # NOT adopt it: web sessions start anonymous. (boot_identity itself stays a
        # pure resolver — the mode policy lives here, at the orchestration layer.)
        if self.session.get(SESSION_KEY_ZMODE) == MODE_ZBIFROST:
            self.logger.framework.debug(
                "[zAuth.boot] server mode → instance-owner identity NOT adopted; "
                "web sessions authenticate per-connection via zLogin"
            )
        else:
            try:
                self.auth.resolve_boot_identity()
            except Exception as _identity_err:  # pylint: disable=broad-except
                self.logger.debug(f"[zAuth.boot] identity resolution skipped: {_identity_err}")

        # Register signal handlers for graceful shutdown
        self._register_signal_handlers()

        # Note: Constructor returns immediately. Call z.run() to start execution.
        # Note: zAuth database is workspace-relative (@), ensuring each zCLI instance
        # is fully isolated. Auth DB lazy-loads on first save_session().
        # This preserves the "no global state" principle of the zCLI architecture.

        self.logger.framework.debug(LOG_INIT_COMPLETE, self.session.get(SESSION_KEY_ZMODE))

    # Ports owned by macOS system services or well-known daemons.
    # zRaven will NEVER kill processes on these ports — raises a config error instead.
    _PROTECTED_PORTS = {
        22,    # SSH
        80,    # HTTP
        443,   # HTTPS
        631,   # CUPS printing
        5000,  # AirPlay / Bonjour (macOS)
        5001,  # AirPlay Receiver (macOS 12+)
        5353,  # mDNS / Bonjour
        7000,  # AirPlay mirroring
        7001,  # AirPlay mirroring (alt)
        49152, # ephemeral range start — nothing above here should be app ports
    }

    # zRaven binds the live app ports + this offset, so a test run is isolated from a
    # live `z zApp` and only ever clears its OWN test ports. Single source of truth.
    _ZRAVEN_PORT_OFFSET = 100
    # A fixed offset alone made every project's zRaven run land on the SAME computed
    # port (e.g. two concurrent `z raven --run` in different repos both want 8180/8865)
    # — _reserve_free_port then walks forward from that starting point so concurrent
    # runs (different repos, different agents) each settle on their own free port
    # instead of colliding/SIGKILLing each other's test server. Bounded so a runaway
    # scan can never wander into the ephemeral range.
    _ZRAVEN_PORT_SCAN_TRIES = 50

    # Cross-process reservation ledger: a plain bind-probe alone has a TOCTOU gap
    # (probe closes the socket immediately, but the real zServer/websocket bind
    # happens much later in boot) — two zRaven processes launched moments apart can
    # both probe the SAME "free" port before either actually binds it. A flock'd
    # registry in the shared system temp dir (visible across repos/agents on this
    # machine, unlike anything inside a single workspace) closes that gap: port
    # choice is serialized machine-wide, and a reservation sticks for as long as its
    # owning PID is alive — dead PIDs (crashes, SIGKILL) are pruned on next use, so
    # no manual cleanup step is required.
    _ZRAVEN_PORT_REGISTRY = Path("/tmp/zos_zraven_ports.json")
    _ZRAVEN_PORT_LOCK     = Path("/tmp/zos_zraven_ports.lock")

    @classmethod
    def _reserve_free_port(cls, host: str, start_port: int, max_tries: int, tag: str) -> int:
        """Atomically pick + reserve the first free port at/after *start_port*.

        *tag* namespaces this reservation (e.g. "http"/"ws") so one PID can hold
        more than one reservation at once without colliding with itself.
        """
        import fcntl as _fcntl    # pylint: disable=import-outside-toplevel
        import json as _json     # pylint: disable=import-outside-toplevel
        import socket as _socket # pylint: disable=import-outside-toplevel

        def _bindable(port: int) -> bool:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return True
            except OSError:
                return False
            finally:
                sock.close()

        cls._ZRAVEN_PORT_LOCK.touch(exist_ok=True)
        lock_fd = os.open(str(cls._ZRAVEN_PORT_LOCK), os.O_RDWR)
        try:
            _fcntl.flock(lock_fd, _fcntl.LOCK_EX)  # blocks — serializes port picks machine-wide

            try:
                registry = _json.loads(cls._ZRAVEN_PORT_REGISTRY.read_text())
            except (FileNotFoundError, ValueError):
                registry = {}

            # Prune reservations whose owning process is gone — self-cleaning, so a
            # crashed/SIGKILLed run never permanently squats on a port.
            live = {}
            for key, entry in registry.items():
                pid = entry.get("pid")
                try:
                    os.kill(pid, 0)
                    live[key] = entry
                except (OSError, TypeError):
                    pass
            registry = live

            reserved_ports = {entry["port"] for entry in registry.values()}
            for candidate in range(start_port, start_port + max_tries):
                if candidate in zOS._PROTECTED_PORTS or candidate in reserved_ports:
                    continue
                if _bindable(candidate):
                    registry[f"{os.getpid()}:{tag}"] = {"port": candidate, "pid": os.getpid()}
                    cls._ZRAVEN_PORT_REGISTRY.write_text(_json.dumps(registry))
                    return candidate

            raise OSError(
                f"[zRaven] No free {tag} port found in range "
                f"{start_port}-{start_port + max_tries - 1} on {host}. Set an explicit "
                f"ZRAVEN_HTTP_PORT/ZRAVEN_WS_PORT or zRavenPort/zRavenWsPort in zSpark."
            )
        finally:
            _fcntl.flock(lock_fd, _fcntl.LOCK_UN)
            os.close(lock_fd)

    def _apply_raven_port_offset(self) -> None:
        """Shift HTTP + WS ports into zRaven's designated range (app port + offset).

        SINGLE SOURCE OF TRUTH for zRaven port selection. Called only when zRaven is
        enabled, immediately after zConfig and before any port-clearing or server bind,
        so the bound server, the pre-flight clear, and the runner's URL resolution all
        agree. Keeps the test server off the live app's ports so a zSpark with `zRaven:`
        (or `z raven --run`) never SIGKILLs a running `z zApp`. Idempotent via a guard.

        Resolution order (same for every server type / entry path):
          1. Explicit override → ZRAVEN_HTTP_PORT / ZRAVEN_WS_PORT env, then
             zRavenPort / zRavenWsPort in zSpark. Set absolute (NO offset, NO scan —
             an explicit override is a deliberate pin, honored exactly).
          2. Otherwise → live app port + offset, then scanned + reserved via the
             cross-process registry (see _reserve_free_port) — this is what keeps
             two concurrent `z raven --run` invocations (different repos/agents)
             from both computing the same fixed port and stepping on each other.

        NOTE: callers (e.g. raven_command) must NOT pre-mutate zServer/websocket ports;
        doing so would stack on top of the offset and desync the runner's URL.
        """
        if getattr(self, "_raven_ports_offset_applied", False):
            return

        import os as _os  # pylint: disable=import-outside-toplevel

        offset = self._ZRAVEN_PORT_OFFSET
        spark  = self.zspark_obj or {}

        def _override(env_key: str, spark_key: str):
            val = _os.environ.get(env_key) or spark.get(spark_key)
            return int(val) if val else None

        http_override = _override("ZRAVEN_HTTP_PORT", "zRavenPort")
        ws_override   = _override("ZRAVEN_WS_PORT", "zRavenWsPort")

        # http_server.port is a plain attribute; websocket.port is a read-only property
        # backed by an internal dict (mutate via its update() method).
        if hasattr(self.config, "http_server"):
            http_host = getattr(self.config.http_server, "host", "127.0.0.1")
            self.config.http_server.port = (
                http_override if http_override is not None
                else self._reserve_free_port(
                    http_host, self.config.http_server.port + offset, self._ZRAVEN_PORT_SCAN_TRIES, "http"
                )
            )
        if hasattr(self.config, "websocket"):
            ws_host = getattr(self.config.websocket, "host", "127.0.0.1")
            new_ws = (
                ws_override if ws_override is not None
                else self._reserve_free_port(
                    ws_host, self.config.websocket.port + offset, self._ZRAVEN_PORT_SCAN_TRIES, "ws"
                )
            )
            self.config.websocket.update("port", new_ws)

        self._raven_ports_offset_applied = True
        _src = "override" if (http_override or ws_override) else f"live app port +{offset}, scanned free"
        self.logger.info(
            f"[zRaven] Designated test ports ({_src}): "
            f"HTTP={getattr(getattr(self.config, 'http_server', None), 'port', '?')} "
            f"WS={getattr(getattr(self.config, 'websocket', None), 'port', '?')}"
        )

    def _clear_ports_for_raven(self) -> None:
        """
        Kill any stale processes holding the configured HTTP/WS ports before server start.
        Only called when zRaven is enabled — safe for dev/test, never runs in production.

        Protected ports (system services) are never killed — a config error is raised
        so the developer knows to choose a different port in zEnv.
        """
        import signal as _signal  # pylint: disable=import-outside-toplevel
        import time as _time      # pylint: disable=import-outside-toplevel
        from zOS import os as _os   # pylint: disable=import-outside-toplevel

        ports = []
        if hasattr(self.config, "http_server"):
            ports.append(self.config.http_server.port)
        if hasattr(self.config, "websocket"):
            ports.append(self.config.websocket.port)

        killed_any = False
        for port in ports:
            if port in self._PROTECTED_PORTS:
                raise OSError(
                    f"[zRaven] Port {port} is reserved by a system service and cannot be used. "
                    f"Set a different HTTP_PORT / WEBSOCKET_PORT in your zEnv file."
                )
            try:
                result = _os.popen(f"lsof -ti :{port}").read().strip()
                if result:
                    for pid_str in result.splitlines():
                        pid = int(pid_str.strip())
                        try:
                            _os.kill(pid, _signal.SIGKILL)
                            self.logger.info(f"[zRaven] Cleared port {port} (killed PID {pid})")
                            killed_any = True
                        except (ProcessLookupError, PermissionError):
                            pass  # already gone or protected by OS
            except OSError:
                raise
            except Exception:  # pylint: disable=broad-except
                pass  # port clearing is best-effort — never block startup

        if killed_any:
            _time.sleep(0.5)  # give OS time to release ports before servers bind

    def _load_plugins(self) -> None:
        """
        Load plugins from zSpark_obj["plugins"] via zLoader.

        Migrated from zUtils v1.7.0 - plugin loading now centralized in zLoader.
        Supports single string or list. Failures logged as warnings, don't halt init.
        Plugins can use get_current_zos() to access subsystems.
        """
        try:
            plugin_paths = self.zspark_obj.get(ZSPARK_PLUGINS_KEY) or []
            if isinstance(plugin_paths, (list, tuple)):
                self.loader.load_plugins(plugin_paths)
            elif isinstance(plugin_paths, str):
                self.loader.load_plugins([plugin_paths])
        except (ImportError, AttributeError, TypeError) as e:
            self.logger.warning(LOG_WARN_PLUGIN_FAIL, e)

    def _init_session(self) -> None:
        """
        Set session[zS_id] and log config. zMode already set by zConfig.
        """
        # Set session ID - always required
        self.session[SESSION_KEY_ZS_ID] = self.config.session.generate_id("zS")

        # zMode was already set by zConfig.session.detect_zMode() during session creation
        # It checks zSpark_obj.get("zMode") and defaults to "zCLI"
        # No need to override it here

        self.logger.framework.debug(LOG_SESSION_INIT)
        self.logger.framework.debug(LOG_DEBUG_SESSION_ID, self.session[SESSION_KEY_ZS_ID])
        self.logger.framework.debug(LOG_DEBUG_SESSION_MODE, self.session[SESSION_KEY_ZMODE])
        self.logger.framework.debug(
            LOG_DEBUG_SESSION_MACHINE,
            self.session[SESSION_KEY_ZMACHINE].get("hostname"),
        )

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def run_command(self, command: str) -> Any:
        """
        Execute single command string via zShell.

        Returns command result (type varies). Output typically via zDisplay.
        """
        return self.shell.execute_command(command)

    def run_shell(self) -> None:
        """
        Start zCLI mode (interactive REPL). Blocks until exit.
        """
        return self.shell.run_shell()

    def run(self) -> Any:
        """
        Main entry point - centralized execution for all zCLI modes.

        Decision Priority:
        1. zServer running + zShell → REPL with HTTP in background
        2. zServer running (silent) → Block on server.wait()
        3. zVaFile specified → zWalker (handles zCLI/zBifrost internally)
        4. zMode: zBifrost → zWalker (WebSocket mode)
        5. zMode: zCLI (default) → zShell REPL

        Returns:
            Any: Result from the executed subsystem (walker, shell, or server)
        """
        # Priority 1 & 2: zServer lifecycle management
        if self.server and self.server.is_running():
            if hasattr(self.config, "http_server") and self.config.http_server.zShell:
                # Interactive mode: REPL with HTTP server in background
                print("\n" + "="*70)
                print(f"  Server: http://{self.server.config_manager.host}:{self.server.config_manager.port}")
                print("  Entering zShell REPL (type 'exit' to stop server)")
                print("="*70 + "\n")
                return self.run_shell()
            else:
                # zCLI mode + zVaFile: server runs in background, walker runs in foreground.
                # Server is SSOT for static serving; CLI walker runs independently.
                _zmode = self.session.get(SESSION_KEY_ZMODE, MODE_ZCLI)
                _cli_with_vafile = (_zmode == MODE_ZCLI and self.session.get("zVaFile"))
                _raven_with_vafile = (self.raven.is_enabled and self.session.get("zVaFile"))
                if not _cli_with_vafile and not _raven_with_vafile:
                    # Silent blocking mode: Just wait for Ctrl+C
                    self.logger.framework.debug("[zCLI] Blocking on zServer (silent mode)")
                    self.raven.start()   # no-op if not enabled
                    if self.zspark_obj.get("zDesktop"):
                        return self._run_zdesktop_main()
                    return self.server.wait()
                # else: fall through to Priority 3 — walker or raven drives, server stays as daemon

        # Priority 3: zVaFile specified → zRaven drives (CLI/Bifrost) or walker runs
        if self.session.get("zVaFile"):
            if self.raven.is_enabled:
                # CLI: drives app subprocess via stdin/stdout
                # Bifrost: drives browser via WS; server stays alive as daemon
                self.logger.info("[zCLI] zRaven enabled — handing off to runner")
                self.raven.start()
                self.raven.wait()
                return
            self.logger.info("[zCLI] Launching zWalker (zVaFile detected)")
            result = self.walker.run()
            # zServer enabled: the walker is a one-shot render, but the server
            # must outlive it so served/opened URLs stay reachable. Block until
            # Ctrl+C (parity with the silent-server path and with Bifrost, whose
            # WS server keeps the process alive). Without this, zOS exits the
            # moment the walk completes and the dev HTTP server is torn down.
            if self.server and self.server.is_running():
                self.logger.framework.debug(
                    "[zCLI] Walker complete — blocking on zServer (Ctrl+C to stop)"
                )
                return self.server.wait()
            return result

        # Priority 4 & 5: Mode detection for walker vs shell
        zmode = self.session.get(SESSION_KEY_ZMODE, MODE_ZCLI)

        if zmode == MODE_ZBIFROST:
            self.logger.info(LOG_MODE_ZBIFROST)
            return self.walker.run()

        self.logger.info(LOG_MODE_ZCLI)
        return self.run_shell()

    # ═══════════════════════════════════════════════════════════════════════
    # ZRAVEN AUTO-TEST RUNNER
    # ═══════════════════════════════════════════════════════════════════════

    # _auto_run_zraven removed — replaced by self.raven (s_zRaven subsystem, L4)

    # ═══════════════════════════════════════════════════════════════════════
    # ZDESKTOP NATIVE WINDOW LAUNCHER
    # ═══════════════════════════════════════════════════════════════════════

    def _run_zdesktop_main(self) -> None:
        """
        zDesktop mode: pywebview MUST run on the main thread.

        Parks server.wait() in a background daemon thread, then calls
        launch_desktop_window() blocking on the main thread. When the
        window is closed, shutdown() is called and the server thread exits.
        """
        import threading as _threading  # pylint: disable=import-outside-toplevel
        from .zDesktop import launch_desktop_window  # pylint: disable=import-outside-toplevel

        server_thread = _threading.Thread(
            target=self.server.wait,
            daemon=True,
            name="zServer-wait",
        )
        server_thread.start()

        launch_desktop_window(self)  # blocks main thread until window closes

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL HANDLERS & GRACEFUL SHUTDOWN
    # ═══════════════════════════════════════════════════════════════════════

    def _register_signal_handlers(self) -> None:
        """
        Register SIGINT/SIGTERM handlers for graceful shutdown.

        Prevents duplicate attempts via _shutdown_in_progress flag.
        Exit codes: 0 (clean) | 1 (error).
        """
        register_signal_handlers(self)

    def request_shutdown(self, source: str = "unknown") -> None:
        """Request graceful shutdown (non-blocking, safe to call from threads)."""
        import os as _os, signal as _signal  # pylint: disable=import-outside-toplevel
        self.logger.info(f"[zOS] Shutdown requested by {source}")
        _os.kill(_os.getpid(), _signal.SIGINT)

    def reload_server(self, source: str = "unknown") -> Optional[Dict[str, Any]]:
        """
        Hot-reload the served app (routes / zAPIs / parsed-file cache) — no downtime.

        Re-scans the app WITHOUT stopping the process: the socket, WS bridge, and
        in-memory sessions are preserved. Triggered by SIGHUP, ``z reload``, or
        Ctrl+R. No-op when no server is running.

        Returns the reload status dict, or None if there is no server.
        """
        server = getattr(self, "server", None)
        if not server:
            self.logger.warning("[zOS] Reload requested but no server is present")
            return None
        self.logger.info(f"[zOS] Server reload requested by {source}")
        return server.reload()

    def swap_server(self, source: str = "unknown") -> Optional[Dict[str, Any]]:
        """Zero-downtime self-replace of the running server (blue-green).

        Spawns a fresh copy of this app on the SAME port, waits for it to go ready,
        then drains and exits — leaving the new process serving. Unlike
        :meth:`reload_server` (in-place re-scan), this picks up new Python / a patched
        zGuard binary. Triggered by SIGUSR2 / ``z swap``. No-op without a
        server. On a successful handoff the process exits and this does not return.
        """
        server = getattr(self, "server", None)
        if not server:
            self.logger.warning("[zOS] Swap requested but no server is present")
            return None
        self.logger.info(f"[zOS] Server self-replace requested by {source}")
        return server.swap()

    def shutdown(self) -> Optional[Dict[str, bool]]:
        """
        Gracefully shutdown all subsystems in reverse init order.

        Cleanup: zRaven → WebSocket → HTTP → Database → Logger. Each wrapped in ExceptionContext
        (failures don't halt shutdown). Idempotent via _shutdown_in_progress flag.

        Returns Dict[str, bool] with component status, or None if already in progress.
        """
        # Shut down zRaven first so Playwright releases its WS connection
        # before the WS/HTTP servers stop — prevents port-not-clearing on restart.
        if hasattr(self, "raven"):
            self.raven.shutdown()
        return perform_shutdown(self)

    def __enter__(self) -> "zOS":
        """Context manager entry - register in thread context."""
        _current_zos.set(self)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """
        Context manager exit - clear thread context.

        Does NOT call shutdown() automatically. Returns False (exceptions propagate).
        """
        _current_zos.set(None)
        return False  # Don't suppress exceptions
