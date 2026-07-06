# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/network/config_raven.py
"""zRaven Configuration Module"""

import os as _os
from typing import Any, Dict, Optional

_LOG_PREFIX      = "[zRavenConfig]"
_CONFIG_KEY      = "zRaven"      # zSpark key: zRaven: crm  (or false / absent)

# SSOT for the env var that flags a zRaven-spawned test-target subprocess.
# Public so the s_zRaven runner can import it instead of re-typing the literal.
ENV_TARGET_KEY   = "ZRAVEN_TARGET"  # set by CLIRunner on the test-target subprocess
_ENV_TARGET_KEY  = ENV_TARGET_KEY   # backward-compatible private alias
_DEFAULT_TIMEOUT = 120           # seconds before zRaven run is killed


class zRavenConfig:
    """
    Configuration for the zRaven test subsystem.

    Reads the `zRaven` key from zSpark_obj.

    zSpark syntax:
        zRaven: crm          # run zRaven/zRaven.crm.zolo
        zRaven: false        # disabled (default)
        # absent             # also disabled

    Attributes:
        enabled   bool         True when a valid test name is set
        name      str | None   The test name (e.g. "crm")
        timeout   int          Max seconds for the test run (default 120)
    """

    enabled: bool
    name: Optional[str]
    timeout: int

    def __init__(self, zspark_obj: Dict[str, Any], logger: Any) -> None:
        self.logger = logger
        raw = zspark_obj.get(_CONFIG_KEY)

        # When spawned as a CLIRunner test target, never self-activate zRaven
        if _os.environ.get(_ENV_TARGET_KEY):
            self.enabled = False
            self.name    = None
            self.timeout = _DEFAULT_TIMEOUT
            return

        # Normalise: false / absent / True (deprecated) → disabled
        if not raw or raw is True:
            if raw is True:
                logger.warning(
                    f"{_LOG_PREFIX} zRaven: true is deprecated — "
                    "use zRaven: <name>  e.g.  zRaven: crm"
                )
            self.enabled = False
            self.name    = None
        else:
            self.enabled = True
            self.name    = str(raw)

        self.timeout = int(zspark_obj.get("zRavenTimeout", _DEFAULT_TIMEOUT))

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"zRavenConfig(enabled={self.enabled}, "
            f"name={self.name!r}, timeout={self.timeout})"
        )
