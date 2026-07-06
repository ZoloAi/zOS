# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/base_runner.py
"""
BaseStepRunner — shared counters, recording helpers, and common primitives
for both CLI and Bifrost adapters.

Eliminates the copy-paste of passed/failed/failed_steps/stop_on_error state
and the associated pass_step / fail_step / warn_step bookkeeping that lived
identically in both CLIRunner and ZRaven.

Inheritance:
    CLIRunner(BaseStepRunner)   — subprocess stdin/stdout driver
    ZRaven(BaseStepRunner)      — async Playwright / WebSocket driver  (Step 4)
"""

from __future__ import annotations

from typing import Any

from .constants import MODE_CLI as _MODE_CLI
from .utils.colors import BOLD, GREEN, RED, RESET
from .utils.reporter import fail_step, pass_step, warn_step


class BaseStepRunner:
    """Shared state and helpers for step-executing zRaven adapters."""

    def __init__(self, stop_on_error: bool = True) -> None:
        self.passed:       int       = 0
        self.failed:       int       = 0
        self.failed_steps: list[str] = []
        self.stop_on_error: bool     = stop_on_error
        self._done:        bool      = False

    # ── Mode-aware step resolution ───────────────────────────────────────────

    @staticmethod
    def _resolve_mode_step(cfg: dict, mode: str) -> dict | None:
        """Resolve a step config for the current runner mode.

        Rules:
          - cfg has no zCLI/zBifrost keys → shared step, return cfg unchanged
          - cfg has the current-mode key   → return that key's dict as the step cfg
          - cfg has only the other-mode key → return None (skip silently)
          - cfg has both keys              → pick the current-mode key

        Args:
            cfg:  raw step config dict from the raven file
            mode: 'cli' or 'bifrost'
        """
        has_cli = "zCLI" in cfg
        has_bif = "zBifrost" in cfg
        if not has_cli and not has_bif:
            return cfg  # shared step — run as-is in both modes
        if mode == _MODE_CLI:
            if not has_cli:
                return None  # Bifrost-only step, skip
            val = cfg["zCLI"]
            return val if isinstance(val, dict) else {}
        else:
            if not has_bif:
                return None  # CLI-only step, skip
            val = cfg["zBifrost"]
            return val if isinstance(val, dict) else {}

    # ── Step recording ───────────────────────────────────────────────────────

    def _record_pass(self, step_name: str, detail: str = "") -> None:
        self.passed += 1
        pass_step(step_name, detail)

    def _record_fail(self, step_name: str, reason: str = "") -> None:
        self.failed += 1
        self.failed_steps.append(step_name)
        fail_step(step_name, reason)

    def _record_warn(self, step_name: str, reason: str = "") -> None:
        warn_step(step_name, reason)

    # ── zLogger assertion ────────────────────────────────────────────────────

    def _run_logger_assert(
        self,
        step_name: str,
        logger_cfg: Any,
        log_buffer: list,
        soft: bool = False,
    ) -> bool:
        """Evaluate a zLogger assertion against the captured log buffer."""
        from .assertions.evaluator import evaluate_logger_assert  # pylint: disable=import-outside-toplevel

        passed, reason = evaluate_logger_assert(logger_cfg, log_buffer)
        if passed:
            self._record_pass(step_name)
        elif soft:
            self._record_warn(step_name, reason[:120])
            return True
        else:
            self._record_fail(step_name, reason)
        return passed

    # ── Summary output ───────────────────────────────────────────────────────

    def print_summary(self) -> None:
        """Print the final pass/fail tally to stdout."""
        total = self.passed + self.failed
        if self.failed == 0:
            print(f"  {GREEN}{BOLD}✓ All {total} steps passed{RESET}", flush=True)
        else:
            print(f"  {RED}{BOLD}✗ {self.failed} / {total} steps failed{RESET}", flush=True)
            for s in self.failed_steps:
                print(f"    {RED}•{RESET} {s}", flush=True)
        print()
