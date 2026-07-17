"""
zRelease — zero-downtime rollout of a hosted app version (Phase 4).

NAMING (SSOT): ``zRelease`` is a *hosting/release* concept — the act of making a
specific versioned build the live one for a slug. It is deliberately distinct
from the zSpark ``zPersist`` key (formerly ``zSwap``), which is about an app's
persistent storage / hot-reload and has nothing to do with deployment.

A :class:`ReleaseManager` runs the blue/green dance over *any* :class:`ComputeDriver`
(``LocalProcessDriver`` in dev, a ``K8sDriver`` later) so the control flow never
changes — only the backend does:

    1. WAKE GREEN   start the new build as its own instance (key ``slug#<build>``)
    2. DRAIN-IN     wait until green is actually serving (driver health) — if it
                    never comes up, stop it and abort with the old version intact
    3. FLIP         call back into the registry to point the slug at the new build
                    (active-pointer) — only now do visitors reach green
    4. DRAIN-OUT    grace period so in-flight requests on blue finish
    5. SLEEP BLUE   stop the old instance

Ownership of *state* stays with the caller: the manager never touches the
registry directly — it invokes a ``flip`` callback. That keeps storage/DB policy
with the host platform and orchestration here, mirroring drivers/bundle_store.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .drivers import AppSpec, ComputeDriver, Instance, get_driver

__all__ = ["ReleaseResult", "ReleaseManager", "instance_key", "normalize_build_id"]

# Default seconds to let blue serve in-flight requests after the flip, before
# it is stopped. Small in dev; a real driver may override per environment.
DEFAULT_DRAIN_GRACE = 2.0


def normalize_build_id(build_id: Any) -> str:
    """Canonical string form of a build id — robust to CSV float coercion.

    A NULLABLE int column (``active_build_id`` / ``previous_build_id``) can't hold
    NaN in pandas int64, so the CSV backend widens it to float64 and a build id
    read from a row arrives as ``2.0`` instead of ``2``. Unnormalized it poisons
    dir names (``builds/2.0``) and prune comparisons (``"1.0" != "1"`` → the
    rollback build gets deleted). Coerce a whole float to its int form so every
    build-id rendering — instance keys, build dirs, prune sets — is identical.
    """
    if build_id is None:
        return ""
    try:
        as_float = float(build_id)
    except (TypeError, ValueError):
        return str(build_id)
    return str(int(as_float)) if as_float.is_integer() else str(build_id)


def instance_key(slug: str, build_id: Any) -> str:
    """Per-version driver instance key so blue and green coexist.

    The driver tables instances by id; ``slug#<build>`` keeps two versions of the
    same app distinct (vs. one slot per slug), which is what blue/green needs.
    """
    return f"{slug}#{normalize_build_id(build_id)}"


@dataclass
class ReleaseResult:
    """Outcome of a rollout — enough for the caller to update the registry/UI."""

    ok: bool
    slug: str
    build_id: Any
    instance: Optional[Instance] = None
    previous_build_id: Any = None
    flipped: bool = False
    blue_stopped: bool = False
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "slug": self.slug,
            "build_id": self.build_id,
            "previous_build_id": self.previous_build_id,
            "flipped": self.flipped,
            "blue_stopped": self.blue_stopped,
            "reason": self.reason,
            "instance": self.instance.as_dict() if self.instance else None,
        }


class ReleaseManager:
    """Orchestrates a blue/green rollout over a :class:`ComputeDriver`."""

    def __init__(
        self,
        driver: Optional[ComputeDriver] = None,
        zos: Any = None,
        logger: Any = None,
        drain_grace: float = DEFAULT_DRAIN_GRACE,
    ):
        # Resolve via the same env-selected seam as everything else (dev=local).
        self.driver = driver or get_driver(zos)
        self.logger = logger or getattr(zos, "logger", None)
        self.drain_grace = drain_grace

    def _log(self, level: str, msg: str) -> None:
        if self.logger is not None:
            getattr(self.logger, level, lambda *_a, **_k: None)(msg)

    def deploy(
        self,
        slug: str,
        build_id: Any,
        build_dir: str,
        spark: str,
        flip: Callable[[], None],
        previous_build_id: Any = None,
        host: str = "localhost",
        timeout: float = 25.0,
    ) -> ReleaseResult:
        """Roll ``build_id`` live for ``slug`` with zero downtime.

        Args:
            slug:        the app slug (front-door key).
            build_id:    the new build/version being released.
            build_dir:   folder the new build's spark boots from (driver cwd).
            spark:       zSpark filename for the new build.
            flip:        callback that repoints the registry at ``build_id`` — the
                         single atomic "now live" act. Raising here aborts cleanly.
            previous_build_id: the build currently live (blue), if any, to drain+stop.

        Never raises for operational failures; returns a ``ReleaseResult``.
        """
        green_id = instance_key(slug, build_id)
        result = ReleaseResult(ok=False, slug=slug, build_id=build_id,
                               previous_build_id=previous_build_id)

        # 1+2. Wake green and drain-in (driver.wake blocks until the port serves).
        green = AppSpec(app_id=green_id, folder=build_dir, spark=spark, host=host)
        self._log("info", f"[zRelease] {slug}: waking green build {build_id}")
        inst = self.driver.wake(green, timeout=timeout)
        result.instance = inst
        if not inst.running:
            # Green never became healthy — tear it down, leave blue serving.
            self._log("error", f"[zRelease] {slug}: green build {build_id} unhealthy "
                               f"({inst.state}: {inst.error}); aborting, blue intact")
            self.driver.sleep(green_id)
            result.reason = f"green unhealthy: {inst.error or inst.state}"
            return result

        # 3. Flip the active pointer — visitors reach green only after this.
        try:
            flip()
            result.flipped = True
            self._log("info", f"[zRelease] {slug}: flipped active pointer → build {build_id}")
        except Exception as exc:  # pylint: disable=broad-except
            # Pointer never moved → roll back green, keep blue live.
            self._log("error", f"[zRelease] {slug}: flip failed ({exc}); rolling back green")
            self.driver.sleep(green_id)
            result.reason = f"flip failed: {exc}"
            return result

        # 3b. Ingress re-point (prod): the registry pointer moved, but the
        # reverse proxy still dials blue's port — a direct-subdomain visitor
        # would hit a dead upstream once blue stops below. Re-publish the BARE
        # slug at green's ports now (same rule as resolve_proxy/commit_green).
        # Best-effort: the front door re-publishes on the next /app/<slug> wake.
        if inst.port:
            try:
                from .ingress import IngressConfig  # pylint: disable=import-outside-toplevel
                ingress = IngressConfig.from_env()
                if ingress:
                    ingress.publish(slug, inst.port, inst.ws_port)
                    self._log("info", f"[zRelease] {slug}: ingress re-pointed → green ports")
            except Exception as exc:  # pylint: disable=broad-except
                self._log("warning", f"[zRelease] {slug}: ingress re-point failed ({exc}); "
                                    f"front door will re-publish on next wake")

        # 4+5. Drain-out blue, then stop it. Failure here is non-fatal: green is
        # already live and pointed-to; a lingering blue is a leak, not an outage.
        if previous_build_id is not None and previous_build_id != build_id:
            blue_id = instance_key(slug, previous_build_id)
            if self.drain_grace:
                time.sleep(self.drain_grace)
            try:
                result.blue_stopped = self.driver.sleep(blue_id)
                self._log("info", f"[zRelease] {slug}: drained+stopped blue build "
                                  f"{previous_build_id} ({result.blue_stopped})")
            except Exception as exc:  # pylint: disable=broad-except
                self._log("warning", f"[zRelease] {slug}: blue stop failed ({exc}); "
                                    f"green live, blue leaked")

        result.ok = True
        result.reason = "released"
        return result

    def rollback(self, slug: str, build_id: Any) -> bool:
        """Stop a build's instance (e.g. to undo a bad release). Best-effort."""
        try:
            return self.driver.sleep(instance_key(slug, build_id))
        except Exception as exc:  # pylint: disable=broad-except
            self._log("warning", f"[zRelease] {slug}: rollback stop failed ({exc})")
            return False
