# zOS/core/L4_Orchestration/s_zRaven/zRaven.py
"""
zRaven — Automated Test Subsystem

First-class zOS subsystem (Layer 4r, Orchestration).
Mirrors the zServer lifecycle pattern: created at boot, started when ready.

Activation (zSpark):
    zRaven: crm          # run zRaven/zRaven.crm.zolo
    zRaven: false        # disabled (default)

Layer: 4r — comes after zServer (4q), depends on both zWalker and zBifrost
       being ready before tests can connect.
"""


from __future__ import annotations

__version__ = "1.0.0"

from typing import TYPE_CHECKING, Any

from .zRaven_modules.runner import ZRavenRunner

if TYPE_CHECKING:
    pass

_LOG_PREFIX      = "[zRaven]"
SUBSYSTEM_NAME   = "zRaven"
SUBSYSTEM_LAYER  = 4
SUBSYSTEM_VERSION = "2.0.0"


class zRaven:
    """
    zRaven test subsystem.

    Usage in engine:
        self.raven = zRaven(zos=self)
        if self.config.raven.enabled:
            self.raven.start()

    Public API:
        start()       — begin test run (non-blocking daemon thread)
        shutdown()    — terminate any running test process
        is_enabled    — True when zRaven: <name> is set in zSpark
    """

    def __init__(self, zos: Any) -> None:
        self._zos    = zos
        self._config = zos.config.raven       # zRavenConfig
        self._logger = zos.logger
        self._runner: ZRavenRunner | None = None

        if self._config.enabled:
            self._logger.debug(
                f"{_LOG_PREFIX} Initialized — test file: "
                f"zRaven/zRaven.{self._config.name}.zolo"
            )
        else:
            self._logger.debug(f"{_LOG_PREFIX} Disabled (no zRaven key in zSpark)")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @property
    def is_enabled(self) -> bool:
        return self._config.enabled

    def start(self) -> None:
        """
        Start the test runner in a daemon thread.
        Call only after zBifrost and zServer are ready.
        """
        if not self._config.enabled:
            return
        self._logger.info(
            f"{_LOG_PREFIX} Starting — zRaven: {self._config.name}"
        )
        self._runner = ZRavenRunner(self._zos, self._config)
        self._runner.start()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until test run completes. Returns True if all passed."""
        if self._runner:
            return self._runner.wait(timeout=timeout)
        return True

    def shutdown(self) -> None:
        """Terminate any running test process."""
        if self._runner:
            self._runner.shutdown()
            self._runner = None
        self._logger.debug(f"{_LOG_PREFIX} Shutdown complete")
