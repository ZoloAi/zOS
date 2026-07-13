"""
Compute drivers — the networking primitive behind the ``instance`` connection
point. "Run / reach another zOS app" is a *general* zOS capability, so it lives
here in the plugin SDK (not in any one app): a plugin asks for ``instance`` and
gets a facade that can wake / sleep / inspect a zOS app instance, regardless of
where that instance actually runs.

A :class:`ComputeDriver` is the swappable backend:

    * :class:`LocalProcessDriver` — dev/localhost. Sparks the app's zSpark as a
      child ``zolo`` process on its own ports. This is the SSOT seam that makes
      "test on my machine today, deploy to EKS later" true: the control flow
      (wake/sleep/status) never changes, only the driver does.
    * A ``K8sDriver`` (prod) is registered later via :func:`register_driver`
      with no change to callers.

An app to wake is described by an :class:`AppSpec` (or any object/dict carrying
``app_id`` + ``folder`` + ``spark``) — typically produced by a host platform's
own app registry (the registry table/columns are the platform's concern, never
this SDK's). The driver returns an :class:`Instance` value object whose
``address`` is where the live app is reachable.
"""

from __future__ import annotations

import abc
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

__all__ = [
    "AppSpec", "Instance", "ProxyTarget",
    "ComputeDriver", "LocalProcessDriver",
    "register_driver", "get_driver",
    "STATE_ASLEEP", "STATE_WAKING", "STATE_RUNNING", "STATE_ERROR",
    "DEFAULT_SPARK", "READINESS_PATH",
]

STATE_ASLEEP = "asleep"
STATE_WAKING = "waking"
STATE_RUNNING = "running"
STATE_ERROR = "error"

# Reserved readiness endpoint — the single contract between an instance (which
# serves it) and whatever probes it (the driver wake, the blue-green coordinator,
# a prod ingress/k8s readiness probe). SSOT lives here in the SDK because the
# probers live here; zServer imports this to register the served route. A 200
# means "routing table built and serving", strictly deeper than a TCP port open.
READINESS_PATH = "/zhealth"

# Default zSpark filename an app boots from when a spec / registry row omits one.
# Single source for the literal shared by AppSpec + the bundle store.
DEFAULT_SPARK = "zSpark.zApp.zolo"

# zEnv keys the child zOS process reads for its server bind. The driver injects
# per-instance values via the OS environment so each tenant gets its own ports
# without mutating the tenant's project folder. One place to change if the
# canonical key names ever move.
_ENV_HTTP_HOST = "HTTP_HOST"
_ENV_HTTP_PORT = "HTTP_PORT"
_ENV_WS_HOST = "WEBSOCKET_HOST"
_ENV_WS_PORT = "WEBSOCKET_PORT"


# ─────────────────────────────────────────────────────────────────────────────
# Value objects
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AppSpec:
    """What the driver needs to wake an app — folder + which zSpark to boot."""

    app_id: str
    folder: str
    spark: str = DEFAULT_SPARK
    host: str = "localhost"

    @property
    def spark_file(self) -> str:
        """The zSpark filename (tolerates passing a bare stem like ``hello``)."""
        s = self.spark
        if not s.endswith(".zolo"):
            s = f"zSpark.{s}.zolo" if not s.startswith("zSpark.") else f"{s}.zolo"
        return s

    @classmethod
    def coerce(cls, app: Any) -> "AppSpec":
        """Accept an AppSpec, a dict, or any object with the right attributes."""
        if isinstance(app, AppSpec):
            return app
        if isinstance(app, dict):
            get = app.get
        else:
            get = lambda k, d=None: getattr(app, k, d)  # noqa: E731
        app_id = get("app_id") or get("id") or get("name")
        folder = get("folder") or get("path")
        if not app_id or not folder:
            raise ValueError("AppSpec requires at least 'app_id' and 'folder'")
        return cls(
            app_id=str(app_id),
            folder=str(folder),
            spark=str(get("spark") or DEFAULT_SPARK),
            host=str(get("host") or "localhost"),
        )

    @classmethod
    def from_spark_path(
        cls,
        app_id: str,
        spark_path: Optional[str],
        workspace_dir: Optional[str] = None,
        host: str = "localhost",
        store: str = "apps",
    ) -> "AppSpec":
        """Build an AppSpec from a registry spark-path (folder=dir, spark=file).

        A real tenant path looks like ``<store>/<id>/zSpark.*.zolo`` → folder is its
        parent. Anything else (empty, or a legacy zPath like ``@.UI.zVaF``) falls
        back to the store convention ``<store>/<app_id>`` + the default zSpark. The
        ``store`` folder name is the host platform's convention (passed in by its
        registry) — the SDK only defaults it to a neutral ``apps``. This is the SSOT
        mapping shared by the front door and app-side registries.
        """
        sp = (spark_path or "").strip()
        if sp.endswith(".zolo") and ("/" in sp) and not sp.startswith("@"):
            folder = os.path.dirname(sp)
            spark = os.path.basename(sp)
        else:
            folder = os.path.join(store, str(app_id))
            spark = DEFAULT_SPARK
        if workspace_dir and not os.path.isabs(folder):
            folder = os.path.join(workspace_dir, folder)
        return cls(app_id=str(app_id), folder=folder, spark=spark, host=host)


@dataclass
class Instance:
    """A (maybe) running app instance — what a wake produced / a status found."""

    app_id: str
    state: str = STATE_ASLEEP
    host: str = "localhost"
    port: Optional[int] = None
    ws_port: Optional[int] = None
    pid: Optional[int] = None
    started_at: Optional[float] = None
    error: Optional[str] = None

    @property
    def address(self) -> Optional[str]:
        if self.port is None:
            return None
        return f"http://{self.host}:{self.port}"

    @property
    def ws_url(self) -> Optional[str]:
        if self.ws_port is None:
            return None
        return f"ws://{self.host}:{self.ws_port}"

    @property
    def running(self) -> bool:
        return self.state == STATE_RUNNING

    def as_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "state": self.state,
            "address": self.address,
            "ws_url": self.ws_url,
            "pid": self.pid,
            "error": self.error,
        }


@dataclass
class ProxyTarget:
    """Where a visitor should be sent to reach an app — the front-door contract.

    In dev this is the instance's own ``host:port`` (redirect hand-off); in prod
    it's a stable ingress URL that reverse-proxies HTTP/WS to the pod. Either way
    callers only care about ``url`` + ``ready``.
    """

    app_id: str
    state: str
    url: Optional[str] = None
    ws_url: Optional[str] = None
    error: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self.state == STATE_RUNNING


# ─────────────────────────────────────────────────────────────────────────────
# Driver contract
# ─────────────────────────────────────────────────────────────────────────────

class ComputeDriver(abc.ABC):
    """Backend that knows how to run/reach a zOS app instance."""

    @abc.abstractmethod
    def wake(self, app: AppSpec, timeout: float = 25.0) -> Instance:
        """Ensure ``app`` is running and reachable; return its :class:`Instance`."""

    @abc.abstractmethod
    def sleep(self, app_id: str) -> bool:
        """Tear down ``app_id``'s instance. Returns True if something was stopped."""

    @abc.abstractmethod
    def status(self, app_id: str) -> Instance:
        """Report current state for ``app_id`` (never raises)."""

    # -- blue-green cutover (staging) --------------------------------------------
    # The front pointer for an app is whatever ``wake``/resolve returns. Blue-green
    # brings up a SECOND (green) instance, then atomically re-points the front and
    # retires the old (blue) one. dev = swap the in-process instance record; prod
    # (k8s) = roll the Deployment / flip the Service selector. The coordinator in
    # :mod:`swap` owns the sequence + the readiness gate; these own the mechanism.

    @abc.abstractmethod
    def stage(self, app: AppSpec, timeout: float = 25.0) -> Instance:
        """Bring up a fresh (green) instance ALONGSIDE any live one, held staged
        until :meth:`commit` or :meth:`abort`. Must NOT return or disturb the live
        instance — the front keeps pointing at blue until commit."""

    @abc.abstractmethod
    def commit(self, app_id: str, drain_timeout: float = 10.0) -> bool:
        """Promote the staged (green) instance to live (atomic front flip) and then
        drain + retire the previously-live (blue) one. False if nothing was staged."""

    @abc.abstractmethod
    def abort(self, app_id: str) -> bool:
        """Discard the staged (green) instance, leaving the live one untouched
        (rollback). False if nothing was staged."""


def _free_port() -> int:
    """Grab an OS-assigned free TCP port. Small TOCTOU race is fine for dev."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class LocalProcessDriver(ComputeDriver):
    """Dev driver: each app instance is a child ``zolo`` process on its own ports.

    Per-instance ports are injected through the OS environment (the zEnv server
    keys) so the tenant's project folder is never mutated. Processes are started
    in their own session group so :meth:`sleep` can reap any re-exec'd children
    (zOS may re-exec itself into a patched interpreter on first boot).
    """

    def __init__(self, runtime_dir: Optional[str] = None):
        self._instances: Dict[str, Dict[str, Any]] = {}
        # Staged (green) instances awaiting commit/abort — kept OUT of _instances so
        # the live (blue) instance the front resolves to is never disturbed.
        self._staged: Dict[str, Dict[str, Any]] = {}
        self._runtime = Path(runtime_dir or os.path.join(tempfile.gettempdir(), "zhost"))

    # -- internals ----------------------------------------------------------

    def _zolo_argv(self, spark_file: str) -> list:
        override = os.environ.get("ZHOST_ZOLO_BIN")
        if override:
            return [override, spark_file]
        zolo = shutil.which("zolo")
        if zolo:
            return [zolo, spark_file]
        return [sys.executable, "-m", "zOS.main", spark_file]

    def _alive(self, rec: Dict[str, Any]) -> bool:
        proc = rec.get("proc")
        return bool(proc) and proc.poll() is None

    def _to_instance(self, app_id: str, rec: Dict[str, Any], state: str) -> Instance:
        return Instance(
            app_id=app_id,
            state=state,
            host=rec.get("host", "localhost"),
            port=rec.get("port"),
            ws_port=rec.get("ws_port"),
            pid=rec.get("pid"),
            started_at=rec.get("started_at"),
        )

    def _spawn(self, app: AppSpec, timeout: float):
        """Start ONE fresh child ``zolo`` process for ``app`` on its own ports.

        Returns ``(Instance, record)``. ``record`` is None only on a hard pre-/early
        failure (missing zSpark, or the process exited before its port opened); the
        caller decides where to file the record (live slot vs staging slot), so this
        never mutates ``_instances``/``_staged`` itself.
        """
        folder = Path(app.folder)
        spark_path = folder / app.spark_file
        if not spark_path.exists():
            return Instance(app_id=app.app_id, state=STATE_ERROR,
                            error=f"zSpark not found: {spark_path}"), None

        port = _free_port()
        ws_port = _free_port()
        log_dir = self._runtime / app.app_id
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"instance_{port}.log"

        child_env = os.environ.copy()
        child_env[_ENV_HTTP_HOST] = app.host
        child_env[_ENV_HTTP_PORT] = str(port)
        child_env[_ENV_WS_HOST] = app.host
        child_env[_ENV_WS_PORT] = str(ws_port)
        # Published tenants (ZHOST_INGRESS_DOMAIN set) additionally advertise the
        # ingress WS port + their own subdomain origin; binds above stay private.
        from .ingress import ingress_child_env  # pylint: disable=import-outside-toplevel
        child_env.update(ingress_child_env(app.app_id))

        log_fh = open(log_path, "ab", buffering=0)  # noqa: SIM115 (kept for child lifetime)
        # Own process group so _stop_proc can take down the whole tree:
        # setsid on POSIX, CREATE_NEW_PROCESS_GROUP on Windows (where
        # start_new_session=True raises ValueError).
        group_kw = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                    if os.name == "nt" else {"start_new_session": True})
        proc = subprocess.Popen(
            self._zolo_argv(app.spark_file),
            cwd=str(folder),
            env=child_env,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            **group_kw,
        )

        rec = {
            "proc": proc, "log": log_fh, "log_path": str(log_path),
            "host": app.host, "port": port, "ws_port": ws_port,
            "pid": proc.pid, "started_at": time.time(),
        }

        deadline = time.time() + timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                try:
                    log_fh.close()
                except OSError:
                    pass
                return Instance(app_id=app.app_id, state=STATE_ERROR, pid=proc.pid,
                                error=f"instance exited early (code {proc.returncode}); "
                                      f"see {log_path}"), None
            if _port_open(app.host, port):
                return self._to_instance(app.app_id, rec, STATE_RUNNING), rec
            time.sleep(0.25)

        return self._to_instance(app.app_id, rec, STATE_WAKING), rec

    def _stop_proc(self, rec: Dict[str, Any]) -> bool:
        """Terminate a record's process group (SIGTERM→SIGKILL) and close its log."""
        proc = rec.get("proc")
        stopped = False
        if proc and proc.poll() is None:
            if os.name == "nt":
                # No killpg on Windows — taskkill /T fells the whole tree.
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True, check=False)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), 15)  # SIGTERM the whole group
                except (ProcessLookupError, PermissionError, OSError):
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(proc.pid), 9)
                    except (ProcessLookupError, PermissionError, OSError):
                        proc.kill()
            stopped = True
        log_fh = rec.get("log")
        if log_fh:
            try:
                log_fh.close()
            except OSError:
                pass
        return stopped

    def _drain_and_stop(self, rec: Dict[str, Any], drain_timeout: float) -> bool:
        """Grant a bounded grace window, then stop ``rec``.

        The dev front is a 302 redirect, so AFTER the commit flip new visitors
        already resolve to green; existing visitors hold direct connections to this
        (old/blue) instance. We grant a grace window for those to finish, then stop.
        Connection-count-aware draining + client resume lands with the session store.
        """
        if drain_timeout and drain_timeout > 0:
            time.sleep(drain_timeout)
        return self._stop_proc(rec)

    # -- contract -----------------------------------------------------------

    def wake(self, app: AppSpec, timeout: float = 25.0) -> Instance:
        rec = self._instances.get(app.app_id)
        if rec and self._alive(rec) and _port_open(rec["host"], rec["port"]):
            return self._to_instance(app.app_id, rec, STATE_RUNNING)
        inst, rec = self._spawn(app, timeout)
        if rec is not None:
            self._instances[app.app_id] = rec
        return inst

    def sleep(self, app_id: str) -> bool:
        rec = self._instances.pop(app_id, None)
        if not rec:
            return False
        return self._stop_proc(rec)

    def stage(self, app: AppSpec, timeout: float = 25.0) -> Instance:
        spec = AppSpec.coerce(app)
        # Reap any prior staged green for this app (a re-staged / retried swap).
        prior = self._staged.pop(spec.app_id, None)
        if prior is not None:
            self._stop_proc(prior)
        inst, rec = self._spawn(spec, timeout)
        if rec is not None:
            self._staged[spec.app_id] = rec
        return inst

    def commit(self, app_id: str, drain_timeout: float = 10.0) -> bool:
        staged = self._staged.pop(app_id, None)
        if staged is None:
            return False
        old = self._instances.get(app_id)
        self._instances[app_id] = staged  # ← atomic front flip (single assignment)
        if old is not None and old is not staged:
            self._drain_and_stop(old, drain_timeout)
        return True

    def abort(self, app_id: str) -> bool:
        staged = self._staged.pop(app_id, None)
        if staged is None:
            return False
        return self._stop_proc(staged)

    def status(self, app_id: str) -> Instance:
        rec = self._instances.get(app_id)
        if not rec:
            return Instance(app_id=app_id, state=STATE_ASLEEP)
        if self._alive(rec) and _port_open(rec["host"], rec["port"]):
            return self._to_instance(app_id, rec, STATE_RUNNING)
        if self._alive(rec):
            return self._to_instance(app_id, rec, STATE_WAKING)
        return Instance(app_id=app_id, state=STATE_ASLEEP)


# ─────────────────────────────────────────────────────────────────────────────
# Driver registry — env selects the backend (dev=local, prod=k8s, …)
# ─────────────────────────────────────────────────────────────────────────────

_DRIVERS: Dict[str, Callable[[], ComputeDriver]] = {
    "local": LocalProcessDriver,
}
_SINGLETONS: Dict[str, ComputeDriver] = {}


def register_driver(name: str, factory: Callable[[], ComputeDriver]) -> None:
    """Register a backend factory (e.g. ``register_driver('k8s', K8sDriver)``)."""
    _DRIVERS[name] = factory


def get_driver(zos: Any = None) -> ComputeDriver:
    """Resolve the active driver: ``ZHOST_DRIVER`` env → zos config → 'local'.

    A single instance per driver name is reused so the in-process instance table
    survives across plugin invocations within the same host process.
    """
    name = os.environ.get("ZHOST_DRIVER")
    if not name and zos is not None:
        cfg = getattr(zos, "config", None)
        if isinstance(cfg, dict):
            name = cfg.get("ZHOST_DRIVER")
        else:
            name = getattr(cfg, "ZHOST_DRIVER", None) if cfg is not None else None
    name = name or "local"

    if name not in _SINGLETONS:
        factory = _DRIVERS.get(name) or _DRIVERS["local"]
        _SINGLETONS[name] = factory()
    return _SINGLETONS[name]
