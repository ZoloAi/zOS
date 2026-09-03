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

# ── Step-mode vocabulary (SSOT for wrapperless mode inference) ────────────────
# A step's primitives usually determine its mode on their own, so the
# zCLI:/zBifrost: step wrappers are optional. Wrappers remain honored and are
# still needed for the genuinely ambiguous cases (e.g. a zLogger-only assert
# step that must be scoped to one mode).
# zCapture is DUAL-MODE since zOS#98: in zCLI it regexes the terminal output
# (as always); in zBifrost it reads the rendered DOM ({var, selector, property})
# or regexes the page text when only {var, pattern} is given — the SAME step
# can drive both surfaces, like zPick/zFill.
CLI_ONLY_STEP_KEYS = frozenset({
    "zExpect", "zVar", "zAllowError", "zMenu", "zWizard",
})
BIFROST_ONLY_STEP_KEYS = frozenset({
    "zOpen", "zViewport", "zType", "zClick", "zWait", "zShot", "zScreenshot",
    "zDrag", "zUpload", "zHistory", "zFetch", "zClean", "zExecute", "zBoot",
})
# zFill and zPick are DUAL-MODE (shared): the same {field: value}/Option step
# runs on both runners — cli_runner drives stdin, ws_runner translates to the
# rendered DOM ([name='field'] / button[data-zkey='Option']). Neither set above
# claims them, so _infer_step_mode falls through and both runners execute them.
#
# zSubmit is the one true collision: a scalar value is a CLI stdin submit,
# a dict ({path, gate, value}) is a WS wizard-gate submit. zAssert/zMarker/
# zLogger are shared vocabulary and never force a mode.

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
