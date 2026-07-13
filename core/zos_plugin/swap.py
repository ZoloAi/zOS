"""
Blue-green cutover coordinator — composes the SDK seams (compute ``drivers`` +
the readiness contract, and later the traffic front + ``session_store``) into a
zero-downtime runtime swap. "Replace a running app with a newer copy of it
without dropping anyone" is a *general* zOS capability, so it lives here in the
plugin SDK (sibling to :mod:`drivers`, which runs instances).

Phase 2 (this module): :func:`prepare_green` ONLY. It spawns a NEW (green)
instance via the active :class:`ComputeDriver`, then blocks on the *deep*
readiness contract (:data:`READINESS_PATH` → HTTP 200, not merely an open port).
On any failure it tears the green instance down so a failed swap leaves nothing
behind. It NEVER touches the live (blue) instance and NEVER moves traffic — so it
is safe to run against a running app: worst case a green is started and reaped.

Later phases extend the coordinator with the traffic flip (front → green), the
bounded drain of blue, and session resume — each additive, none changing this
fail-safe spawn→readiness→rollback core.

Production-agnostic by construction: every backend is env-selected. The dev
:class:`LocalProcessDriver` sparks a child ``zolo`` process; a prod ``K8sDriver``
registers later with no change to this coordinator — the control flow is identical.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from .drivers import AppSpec, Instance, get_driver, READINESS_PATH, STATE_ERROR

__all__ = ["CutoverResult", "prepare_green", "commit_green", "swap", "READINESS_PATH"]

# How long green has to come up AND pass readiness before we roll it back.
DEFAULT_READY_TIMEOUT = 30.0
# Grace window granted to blue's in-flight connections before it is stopped.
DEFAULT_DRAIN_TIMEOUT = 10.0
# Gap between readiness polls while waiting for green.
_POLL_INTERVAL = 0.5
# Per-probe HTTP timeout (a hung green must not stall the whole budget).
_PROBE_TIMEOUT = 1.5


@dataclass
class CutoverResult:
    """Outcome of a cutover step. ``ok`` means green is up AND passed readiness;
    ``committed`` means the front was flipped to green and blue retired."""

    ok: bool
    green: Optional[Instance] = None
    error: Optional[str] = None
    rolled_back: bool = False
    committed: bool = False

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "green": self.green.as_dict() if self.green else None,
            "error": self.error,
            "rolled_back": self.rolled_back,
            "committed": self.committed,
        }


def _probe_ready(address: str, timeout: float = _PROBE_TIMEOUT) -> bool:
    """GET ``{address}{READINESS_PATH}`` → True only on HTTP 200.

    503 (still starting / failed route build) and any connection error read as
    not-ready. This is the deep gate: a listening socket is not enough.
    """
    url = f"{address}{READINESS_PATH}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # nosec B310 (local http)
            return getattr(resp, "status", resp.getcode()) == 200
    except urllib.error.HTTPError:
        # Any explicit HTTP status other than 200 (e.g. 503) = not ready yet.
        return False
    except (urllib.error.URLError, OSError):
        return False


def prepare_green(
    zos: Any,
    app: Any,
    ready_timeout: float = DEFAULT_READY_TIMEOUT,
    logger: Any = None,
) -> CutoverResult:
    """Spawn a green instance and block until it passes the readiness contract.

    Phase 2 skeleton — proves spawn → readiness → rollback in isolation; it does
    NOT move traffic and never touches the live instance.

    Args:
        zos: zOS instance (used to resolve the active driver + logger).
        app: An :class:`AppSpec`, a dict, or any object carrying ``app_id`` +
            ``folder`` (coerced via :meth:`AppSpec.coerce`).
        ready_timeout: Total seconds for green to start AND go ready before rollback.
        logger: Optional logger; falls back to ``zos.logger``.

    Returns:
        CutoverResult: ``ok=True`` with the ready green Instance, or ``ok=False``
        with an error (and ``rolled_back=True`` when a started green was reaped).
    """
    log = logger or getattr(zos, "logger", None)
    spec = AppSpec.coerce(app)
    driver = get_driver(zos)

    if log:
        log.info("[zSwap] Preparing green for '%s' (driver=%s)",
                 spec.app_id, type(driver).__name__)

    deadline = time.time() + ready_timeout

    # 1) STAGE green ALONGSIDE blue (never touches the live instance). The driver
    #    returns once the port is open (or it errors / times out). Port-open is
    #    necessary but NOT sufficient — the readiness gate follows.
    inst = driver.stage(spec, timeout=ready_timeout)
    if inst.state == STATE_ERROR or not inst.address:
        if log:
            log.error("[zSwap] Green failed to start for '%s': %s",
                      spec.app_id, inst.error)
        # _spawn already reaped a hard-failed process; abort clears any staged record.
        driver.abort(spec.app_id)
        return CutoverResult(ok=False, green=inst,
                             error=inst.error or "green failed to start")

    # 2) Deep readiness gate — wait for /zhealth 200 within the shared budget.
    while time.time() < deadline:
        if _probe_ready(inst.address):
            if log:
                log.info("[zSwap] Green ready for '%s' at %s",
                         spec.app_id, inst.address)
            return CutoverResult(ok=True, green=inst)
        time.sleep(_POLL_INTERVAL)

    # 3) Never became ready → ABORT (kill staged green only; blue stays live).
    rolled = driver.abort(spec.app_id)
    if log:
        log.error("[zSwap] Green not ready before timeout for '%s' — rolled back (%s)",
                  spec.app_id, rolled)
    return CutoverResult(ok=False, green=inst,
                         error="green not ready before timeout", rolled_back=rolled)


def commit_green(
    zos: Any,
    app: Any,
    drain_timeout: float = DEFAULT_DRAIN_TIMEOUT,
    logger: Any = None,
) -> bool:
    """Flip the front to the staged green and drain+retire blue (atomic promotion).

    Call ONLY after :func:`prepare_green` returned ``ok=True``. Returns True if a
    staged instance was promoted. The flip itself is a single assignment in the
    driver (no request sees a half state); blue is then drained for ``drain_timeout``
    before being stopped.
    """
    log = logger or getattr(zos, "logger", None)
    spec = AppSpec.coerce(app)
    driver = get_driver(zos)
    committed = driver.commit(spec.app_id, drain_timeout=drain_timeout)
    if log:
        log.info("[zSwap] Commit for '%s': front flipped to green, blue retired (%s)",
                 spec.app_id, committed)
    # Ingress: re-point <slug>.<domain> at green's ports — the flip above only
    # moved the driver's front pointer; direct-subdomain visitors ride the proxy.
    if committed:
        from .ingress import IngressConfig  # pylint: disable=import-outside-toplevel
        ingress = IngressConfig.from_env()
        if ingress:
            inst = driver.status(spec.app_id)
            if inst.port:
                try:
                    ingress.publish(spec.app_id, inst.port, inst.ws_port)
                except Exception as exc:  # pylint: disable=broad-except
                    if log:
                        log.error("[zSwap] Ingress re-publish failed for '%s': %s",
                                  spec.app_id, exc)
    return committed


def swap(
    zos: Any,
    app: Any,
    ready_timeout: float = DEFAULT_READY_TIMEOUT,
    drain_timeout: float = DEFAULT_DRAIN_TIMEOUT,
    logger: Any = None,
) -> CutoverResult:
    """End-to-end blue-green swap: stage green → readiness gate → commit + drain blue.

    Fail-safe: if green never passes readiness it is aborted and blue stays live
    (``ok=False``). On success the front is flipped to green, blue is drained and
    retired, and ``committed=True``.
    """
    res = prepare_green(zos, app, ready_timeout=ready_timeout, logger=logger)
    if not res.ok:
        return res
    res.committed = commit_green(zos, app, drain_timeout=drain_timeout, logger=logger)
    return res
