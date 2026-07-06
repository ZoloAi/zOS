# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/constants.py
"""Single source of truth for zRaven vocabulary and shared literals.

Everything the runner/adapters/utils used to hard-code in several places lives
here: run modes, block-name prefixes, output paths, env-var names, and shared
display limits. Cross-layer SSOT (the CLI app-log tag, config env keys) is
re-exported from the modules that own it so there is still exactly one literal.
"""

from __future__ import annotations

# ── Run modes ─────────────────────────────────────────────────────────────────
MODE_CLI     = "cli"
MODE_BIFROST = "bifrost"

# ── Block-name prefixes that restrict a block to one mode ──────────────────────
# Unprefixed blocks (e.g. "Shared_Tests", "zSetup") run in both modes.
CLI_ONLY_PREFIXES     = ("CLI_",)
BIFROST_ONLY_PREFIXES = ("Browser_", "Bifrost_", "zBifrost_")

# ── Output layout (under the app dir) ──────────────────────────────────────────
RAVEN_DIRNAME  = "zRaven"
OUTPUT_DIRNAME = "output"
RUN_LOG_NAME   = "zRaven.last_run.log"

# ── Display limits ─────────────────────────────────────────────────────────────
# Max chars of captured output shown in an assertion-failure message.
ASSERT_CONTEXT_CHARS = 3000

# ── Env var names ──────────────────────────────────────────────────────────────
# ZRAVEN_TARGET is owned by zConfig (config_raven) — import it so the literal
# lives in exactly one place across the L1/L4 boundary.
try:
    from zOS.L1_Foundation.a_zConfig.zConfig_modules.network.config_raven import (
        ENV_TARGET_KEY as ENV_TARGET,
    )
except Exception:  # pylint: disable=broad-except
    ENV_TARGET = "ZRAVEN_TARGET"

ENV_FILE       = "ZRAVEN_FILE"        # optional raven-file path override
ENV_UNBUFFERED = "PYTHONUNBUFFERED"   # forced on the CLI test-target subprocess
