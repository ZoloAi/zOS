# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/cli/cli_runner.py
"""CLIRunner — drives a zCLI zOS app via subprocess stdin/stdout.

Same zRaven grammar as the WS runner — zMode in zSpark selects the runner.

Primitives:
  zSubmit: value         → wait for output to settle → write value\\n to stdin
                           $varname references resolved from captured vars
  zAssert:
    contains: txt        → stdout since last submit must contain txt
    not_contains: txt    → stdout since last submit must NOT contain txt
    success: true        → no ERROR: in stdout since last submit
  zPick: option          → find option in rendered menu → send its index
  zFill: {field: value}  → per field: assert prompt contains field → submit value
                           (declarative form fill — one step per form)
  zExpect: deny          → PASS when RBAC blocks access, FAIL when it doesn't
  zCapture:
    var:     name        → variable name (referenced as $name in later steps)
    pattern: regex       → Python regex; group 1 = captured value (ANSI stripped)
  zMarker: done          → signal end of test, close stdin

Blocks:
  zSetup:                → runs before CLI_Tests as a soft block; failures are
                           ⚠ warnings (not counted) — use for fixtures / cleanup
"""

from __future__ import annotations

import os as _os
import queue as _queue
import re as _re
import select as _select
import sys
import threading as _threading
import time as _time
from typing import Any

from zOS.L1_Foundation.a_zConfig.zConfig_modules.loggers.app_emit import parse_cli_log_line

from ..assertions.evaluator import evaluate_text_assert
from ..base_runner import BaseStepRunner
from ..constants import (
    ENV_TARGET as _ENV_TARGET,
    ENV_UNBUFFERED as _ENV_UNBUFFERED,
    MODE_CLI as _MODE_CLI,
)
from ..utils.colors import BOLD, CYAN, DIM, RESET, YELLOW
from ..utils.reporter import close_log_tee, info, open_log_tee, strip_ansi
from ..utils.data_manager import snapshot_data_dir, restore_data_dir

# Signals that indicate an RBAC/auth denial in console output
_DENY_SIGNALS_RE = _re.compile(
    r"access\s+denied|\[rbac\]|rbac.*denied|denied.*rbac|not\s+authorized|permission\s+denied",
    _re.IGNORECASE,
)

_ECHO_APP_OUTPUT    = True


class CLIRunner(BaseStepRunner):
    """Drives a zCLI zOS app via subprocess stdin/stdout."""

    _SETTLE_S      = 2.0   # seconds of quiet before drain returns (per-step)
    _SETTLE_BOOT_S = 6.0   # longer settle for initial boot (rides through migration pauses)
    _WAIT_FIRST    = 8.0

    def __init__(
        self,
        spark_name: str,
        app_dir: str,
        timeout: float = 30.0,
        stop_on_error: bool = True,
        strict: bool = True,
    ) -> None:
        super().__init__(stop_on_error=stop_on_error)
        self.spark_name    = spark_name
        self.app_dir       = app_dir
        self.timeout       = timeout
        # Strict mode (default on): a leaf step with no recognized zRaven key
        # fails instead of silently passing. Opt out with zRavenOptions.strict: false.
        self.strict        = strict
        self._proc         = None
        self._q: _queue.Queue = _queue.Queue()
        self._step_buf: list[str] = []
        self._all_buf:  list[str] = []
        self._vars: dict[str, str] = {}
        self._app_log_buffer: list[dict] = []

    # ── Public ──────────────────────────────────────────────────────────────

    def run(self, test_blocks: dict) -> bool:
        import subprocess as _sub

        _data_snapshot = snapshot_data_dir(self.app_dir)
        if _data_snapshot:
            info(f"data snapshot: {len(_data_snapshot)} file(s) in Data/ — will restore on exit")

        self._log_fh, _orig_stdout, _orig_stderr = open_log_tee(self.app_dir)

        env = {**_os.environ, _ENV_UNBUFFERED: "1", _ENV_TARGET: "1"}
        self._proc = _sub.Popen(
            ["z", self.spark_name],
            cwd=self.app_dir,
            stdin=_sub.PIPE,
            stdout=_sub.PIPE,
            stderr=_sub.STDOUT,
            env=env,
            bufsize=0,
        )
        _threading.Thread(target=self._reader, daemon=True).start()
        # Boot drain: use a longer settle so we ride out all migration/UI-load
        # pauses and capture the very first interactive prompt (e.g. "username:").
        self._drain(wait_first=True, settle_s=self._SETTLE_BOOT_S)

        if self.stop_on_error:
            info("stop_on_error enabled — run halts on first failure")

        ok = True
        for block_name, block_steps in test_blocks.items():
            if self._done:
                break
            if not isinstance(block_steps, dict):
                continue
            if block_name == "zSetup":
                print(f"{BOLD}[ zSetup ]{RESET}  {YELLOW}(soft — failures are warnings){RESET}", flush=True)
                self._run_steps(block_steps, soft=True)
                print()
                continue
            print(f"{BOLD}[ {block_name} ]{RESET}", flush=True)
            if not self._run_steps(block_steps):
                ok = False
        if self._done and self.stop_on_error and self.failed > 0:
            print(f"{YELLOW}⚡ stop_on_error: halted after first failure{RESET}", flush=True)
        print()

        self.print_summary()

        try:
            if not self._done:
                self._proc.stdin.close()
            self._proc.wait(timeout=5)
        except Exception:  # pylint: disable=broad-except
            self._proc.kill()
        finally:
            close_log_tee(self._log_fh, _orig_stdout, _orig_stderr)
            if _data_snapshot:
                restore_data_dir(self.app_dir, _data_snapshot)
                print(f"  {CYAN}↩ data restored: {len(_data_snapshot)} file(s){RESET}", flush=True)
        return ok

    # ── IO internals ────────────────────────────────────────────────────────

    def _reader(self) -> None:
        fd  = self._proc.stdout.fileno()
        buf = b""
        while True:
            ready, _, _ = _select.select([fd], [], [], 0.05)
            if ready:
                try:
                    chunk = _os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                parts = buf.split(b"\n")
                buf = parts[-1]
                for part in parts[:-1]:
                    line = part.decode("utf-8", errors="replace")
                    self._q.put(line)
                    if _ECHO_APP_OUTPUT:
                        print(f"{DIM}  [app] {line}{RESET}", file=sys.stderr, flush=True)
            else:
                if buf:
                    line = buf.decode("utf-8", errors="replace")
                    self._q.put(line)
                    if _ECHO_APP_OUTPUT:
                        print(f"{DIM}  [app] {line}{RESET}", file=sys.stderr, flush=True)
                    buf = b""
                if self._proc.poll() is not None:
                    break
        if buf:
            line = buf.decode("utf-8", errors="replace")
            self._q.put(line)
            if _ECHO_APP_OUTPUT:
                print(f"{DIM}  [app] {line}{RESET}", file=sys.stderr, flush=True)
        self._q.put(None)

    def _handle_line(self, raw: str) -> None:
        """Classify and store a stdout line — ZLOG tags go to app_log_buffer."""
        stripped = raw.rstrip("\n")
        parsed = parse_cli_log_line(stripped)
        if parsed is not None:
            self._app_log_buffer.append(parsed)
        else:
            self._step_buf.append(stripped)
            self._all_buf.append(stripped)

    def _drain(self, wait_first: bool = False, settle_s: float = 0.0) -> str:
        _settle = settle_s if settle_s > 0 else self._SETTLE_S
        if wait_first and not self._step_buf:
            deadline_first = _time.time() + self._WAIT_FIRST
            while _time.time() < deadline_first:
                try:
                    line = self._q.get(timeout=0.1)
                    if line is None:
                        return "\n".join(self._step_buf)
                    self._handle_line(line)
                    if self._step_buf:
                        break
                except _queue.Empty:
                    continue

        last_item = _time.time()
        while True:
            if _time.time() - last_item >= _settle:
                break
            try:
                line = self._q.get(timeout=0.05)
                if line is None:
                    break
                self._handle_line(line)
                last_item = _time.time()
            except _queue.Empty:
                continue
        return "\n".join(self._step_buf)

    _PROMPT_RE = _re.compile(
        r"^[\w\s]{1,40}:\s*$"          # lines ending with ":" (short — a prompt)
        r"|^\s*\d+[.\]]\s",             # numbered menu option
        _re.MULTILINE,
    )

    def _drain_until_prompt(self, timeout: float = 10.0) -> str:
        """Read output until a prompt pattern appears or timeout expires.

        A prompt is either:
          - a short line ending with ':'  (e.g. "password: ", "username: ")
          - a numbered menu option       (e.g. "1. Overview", "2] Logout")

        Falls back to the normal settle-based drain if no prompt found within
        the first `_SETTLE_S` seconds of silence (avoids hanging on non-prompt
        responses like error messages or data tables).
        """
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            try:
                line = self._q.get(timeout=0.05)
                if line is None:
                    break
                self._handle_line(line)
            except _queue.Empty:
                pass
            # Check if the latest buffered line looks like an interactive prompt
            if self._step_buf:
                candidate = self._strip_ansi(self._step_buf[-1]).strip()
                if self._PROMPT_RE.match(candidate):
                    # Drain a tiny extra tail so any trailing whitespace/newline settles
                    self._drain(settle_s=0.15)
                    return "\n".join(self._step_buf)
        # No prompt detected — fall back to normal settle drain
        return self._drain(settle_s=self._SETTLE_S)

    def _send(self, value: str) -> None:
        info(f"stdin → {value!r}")
        self._step_buf.clear()
        self._proc.stdin.write((value + "\n").encode("utf-8"))
        self._proc.stdin.flush()
        _time.sleep(0.05)
        self._drain_until_prompt()

    def _resolve_vars(self, value: str) -> str:
        if "$" not in value:
            return value
        def _sub(m: "_re.Match[str]") -> str:
            name = m.group(1)
            resolved = self._vars.get(name)
            if resolved is None:
                self._record_warn(f"variable ${name} not defined — keeping literal")
                return m.group(0)
            return resolved
        return _re.sub(r"\$(\w+)", _sub, value)

    def _strip_ansi(self, text: str) -> str:
        return strip_ansi(text)

    # ── Step runners ────────────────────────────────────────────────────────

    def _run_steps(self, steps: dict, soft: bool = False) -> bool:
        if not steps or not isinstance(steps, dict):
            return True
        ok = True
        for step_name, step_cfg in steps.items():
            if self._done:
                break
            if not isinstance(step_cfg, dict):
                continue
            # Step-level mode dispatch: zCLI:/zBifrost: keys route to the right runner.
            step_cfg = self._resolve_mode_step(step_cfg, _MODE_CLI)
            if step_cfg is None:
                continue  # Bifrost-only step — skip silently
            if step_name == "zWizard":
                if not self._run_steps(step_cfg, soft=soft):
                    ok = False
                    if self.stop_on_error and not soft:
                        self._done = True
                continue
            if step_name == "zMenu":
                if not self._run_container(step_name, step_cfg, soft=soft):
                    ok = False
                    if self.stop_on_error and not soft:
                        self._done = True
                continue
            if "zWizard" in step_cfg:
                if not self._run_steps(step_cfg["zWizard"], soft=soft):
                    ok = False
                    if self.stop_on_error and not soft:
                        self._done = True
                continue
            if "zMenu" in step_cfg:
                if not self._run_container(step_name, step_cfg["zMenu"], soft=soft):
                    ok = False
                    if self.stop_on_error and not soft:
                        self._done = True
                continue
            if not self._run_leaf(step_name, step_cfg, soft=soft):
                ok = False
                if self.stop_on_error and not soft:
                    self._done = True
        return ok

    def _run_container(self, step_name: str, cfg: dict, soft: bool = False) -> bool:
        self._drain(wait_first=True)
        ok = True
        for key, val in cfg.items():
            if key == "zPick":
                if not self._run_pick(step_name, val, soft=soft):
                    ok = False
            elif key == "zAssert":
                buf = "\n".join(self._step_buf)
                passed, reason = self._check_assert(val, buf)
                if passed:
                    self._record_pass(step_name)
                elif soft:
                    self._record_warn(step_name, reason[:120])
                else:
                    self._record_fail(step_name, reason)
                    ok = False
        return ok

    def _run_capture(self, step_name: str, cfg: dict, soft: bool = False) -> bool:
        var     = cfg.get("var")
        pattern = cfg.get("pattern")
        if not var or not pattern:
            msg = "zCapture requires 'var' and 'pattern'"
            if soft:
                self._record_warn(step_name, msg)
                return True
            self._record_fail(step_name, msg)
            return False

        buf   = "\n".join(self._step_buf)
        clean = self._strip_ansi(buf)
        m     = _re.search(pattern, clean, _re.IGNORECASE | _re.MULTILINE)
        if not m:
            tail = clean[-400:].strip() if len(clean) > 400 else clean.strip()
            msg  = f"pattern {pattern!r} not found\n  Last output:\n{tail}"
            if soft:
                self._record_warn(step_name, f"pattern {pattern!r} not found — skipping capture")
                return True
            self._record_fail(step_name, msg)
            return False

        value = m.group(1) if m.lastindex else m.group(0)
        self._vars[var] = value
        info(f"captured ${var} = {value!r}")
        self._record_pass(step_name)
        return True

    def _run_leaf(self, step_name: str, cfg: dict, soft: bool = False) -> bool:
        if "zMarker" in cfg:
            info("zMarker reached — closing stdin")
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            self._done = True
            self._record_pass(step_name)
            return True

        if "zCapture" in cfg:
            return self._run_capture(step_name, cfg["zCapture"], soft=soft)

        if "zFill" in cfg:
            return self._run_fill(step_name, cfg["zFill"], soft=soft)

        if "zLogger" in cfg:
            return self._run_logger_assert(step_name, cfg["zLogger"], self._app_log_buffer, soft=soft)

        if not self._step_buf:
            self._drain(wait_first=True)
        buf        = "\n".join(self._step_buf)
        assert_cfg = cfg.get("zAssert", {})

        if "zSubmit" in cfg:
            if assert_cfg:
                # Fast-path: check if current buffer already satisfies the assertion.
                # If not, the next interactive prompt may not have arrived yet
                # (timing gap between _send's _drain_until_prompt returning and the
                # subprocess flushing its prompt text).  Do one targeted re-drain so
                # we capture it before declaring failure.
                _pre_ok, _ = self._check_assert(assert_cfg, buf)
                if not _pre_ok:
                    self._drain_until_prompt(timeout=3.0)
                    buf = "\n".join(self._step_buf)
                passed, reason = self._check_assert(assert_cfg, buf)
                if not passed:
                    # When the step buffer is empty, show the last app output as context
                    if not buf.strip() and self._all_buf:
                        last_app = "\n".join(self._all_buf[-15:])
                        reason = reason.rstrip() + f"\n\n  [last app output]:\n{last_app}"
                    if soft:
                        self._record_warn(f"{step_name} [display]", reason[:400])
                        return True
                    self._record_fail(f"{step_name} [display]", reason)
                    return False
            submit_val = self._resolve_vars(str(cfg["zSubmit"]))
            self._send(submit_val)
            # zVar: varname — store submitted value for later $varname references
            if "zVar" in cfg:
                var_name = str(cfg["zVar"]).strip()
                self._vars[var_name] = submit_val
            # Law: any ERROR: in post-submit output is a hard failure unless
            # the step opts out with  zAllowError: true
            if not cfg.get("zAllowError"):
                post_buf = "\n".join(self._step_buf)
                if "ERROR:" in post_buf:
                    err_lines = [l.strip() for l in post_buf.splitlines() if "ERROR:" in l]
                    reason = "app reported ERROR after submit:\n  " + "\n  ".join(err_lines[:5])
                    reason += "\n  (add zAllowError: true to the step to permit this)"
                    if soft:
                        self._record_warn(f"{step_name} [error]", reason[:400])
                        return True
                    self._record_fail(f"{step_name} [error]", reason)
                    return False
            self._record_pass(step_name)
            return True

        if "zExpect" in cfg:
            return self._run_expect(step_name, cfg, soft=soft)

        if "zPick" in cfg:
            return self._run_pick(step_name, cfg["zPick"], soft=soft)

        if assert_cfg:
            passed, reason = self._check_assert(assert_cfg, "\n".join(self._step_buf))
            if passed:
                self._record_pass(step_name)
            elif soft:
                self._record_warn(step_name, reason[:120])
                return True
            else:
                self._record_fail(step_name, reason)
            return passed

        # Strict vocabulary check: no zSubmit/zPick/zExpect/zCapture/zLogger/
        # zMarker/zAssert on this leaf — it's a typo or a silent no-op. Fail
        # loudly (soft blocks warn). Opt out with zRavenOptions.strict: false.
        unknown = [k for k in cfg if k not in ("zCLI", "zBifrost")]
        msg = (f"no recognized zRaven key in step (keys: {unknown or ['<empty>']}) — "
               f"set zRavenOptions.strict: false to allow no-op steps")
        if soft or not self.strict:
            self._record_warn(step_name, msg[:200])
            return True
        self._record_fail(step_name, msg)
        return False

    def _run_fill(self, step_name: str, fields: Any, soft: bool = False) -> bool:
        """zFill: declarative form fill — {field: value, ...} in one step.

        For each field, in order: assert the current prompt mentions the field
        name (same normalization as zAssert contains), submit the value, then
        apply the post-submit ERROR law. Replaces the per-field
        Enter_x / zAssert / zSubmit boilerplate the generator used to emit.
        """
        if not isinstance(fields, dict) or not fields:
            msg = "zFill requires a {field: value} mapping"
            if soft:
                self._record_warn(step_name, msg)
                return True
            self._record_fail(step_name, msg)
            return False

        for field, value in fields.items():
            label = f"{step_name}.{field}"
            if not self._step_buf:
                self._drain(wait_first=True)
            buf = "\n".join(self._step_buf)
            passed, reason = self._check_assert({"contains": field}, buf)
            if not passed:
                # Prompt may not have flushed yet — one targeted re-drain.
                self._drain_until_prompt(timeout=3.0)
                buf = "\n".join(self._step_buf)
                passed, reason = self._check_assert({"contains": field}, buf)
            if not passed:
                if soft:
                    self._record_warn(f"{label} [prompt]", reason[:400])
                    return True
                self._record_fail(f"{label} [prompt]", reason)
                return False
            # bool -> lowercase "true"/"false": str(True) is "True", but a
            # rendered checkbox/select prompt only recognizes the lowercase
            # token (zolo's own written form, per data_crud bool type).
            send_value = "true" if value is True else "false" if value is False else str(value)
            self._send(self._resolve_vars(send_value))
            post_buf = "\n".join(self._step_buf)
            if "ERROR:" in post_buf:
                err_lines = [l.strip() for l in post_buf.splitlines() if "ERROR:" in l]
                reason = "app reported ERROR after submit:\n  " + "\n  ".join(err_lines[:5])
                if soft:
                    self._record_warn(f"{label} [error]", reason[:400])
                    return True
                self._record_fail(f"{label} [error]", reason)
                return False
        self._record_pass(step_name)
        return True

    def _run_pick(self, step_name: str, option: str, soft: bool = False) -> bool:
        # zolo is string-first: a bare `zPick: 4` parses to an int, not str —
        # coerce once here so every downstream use (index match, difflib
        # fallback) gets a real string, matching how the rendered menu option
        # itself is always text.
        option = str(option)
        # Refresh buffer to capture any menu output that arrived after the last send.
        self._drain(wait_first=not bool(self._step_buf))
        buf = "\n".join(self._step_buf)
        idx = self._resolve_menu_index(option, buf)
        if idx is None:
            actual = self._extract_menu_options(buf)
            hint = ""
            if actual:
                import difflib as _dl  # pylint: disable=import-outside-toplevel
                close = _dl.get_close_matches(option, actual, n=2, cutoff=0.4)
                hint = f"\n  Suggestion: {close}" if close else f"\n  Available: {actual}"
            msg = f"option '{option}' not found in menu output{hint}"
            if soft:
                self._record_warn(step_name, f"option '{option}' not found — skipping")
                return True
            self._record_fail(step_name, msg)
            return False
        info(f"menu pick → [{idx}] {option}")
        self._send(str(idx))
        self._record_pass(step_name)
        return True

    def _run_expect(self, step_name: str, cfg: dict, soft: bool = False) -> bool:
        mode = str(cfg.get("zExpect", "")).lower().strip()
        if mode != "deny":
            self._record_fail(step_name, f"zExpect: unknown mode '{mode}' — only 'deny' is supported")
            return False

        if "zPick" not in cfg:
            self._record_fail(step_name, "zExpect: deny requires a companion zPick")
            return False

        buf    = "\n".join(self._step_buf)
        option = cfg["zPick"]
        idx    = self._resolve_menu_index(option, buf)
        if idx is None:
            actual = self._extract_menu_options(buf)
            self._record_fail(step_name, f"option '{option}' not found — cannot probe RBAC gate\n  Available: {actual}")
            return False

        info(f"menu pick → [{idx}] {option}  [expect: deny]")
        self._send(str(idx))
        self._drain(wait_first=True)

        output = "\n".join(self._step_buf)
        clean  = self._strip_ansi(output)
        denied = _DENY_SIGNALS_RE.search(clean) is not None

        if denied:
            self._record_pass(step_name, "EXPECT DENY — RBAC gate held")
            return True

        tail = clean[-600:].strip() if len(clean) > 600 else clean.strip()
        self._record_fail(step_name, f"EXPECT DENY — gate did NOT hold (security gap!)\n  Output tail:\n{tail}")
        return False

    def _extract_menu_options(self, output: str) -> list:
        opts = []
        for line in output.splitlines():
            m = _re.search(r"^\s*\d+[.\]]\s+(.+)", line)
            if m:
                label = _re.sub(r"^\[.*?\]\s*", "", m.group(1).strip()).strip()
                if label:
                    opts.append(label)
        return opts

    def _resolve_menu_index(self, option: str, output: str) -> int | None:
        bare        = option.lstrip("^")
        bare_spaced = bare.replace("_", " ")
        for line in output.splitlines():
            m = _re.search(r"^\s*(\d+)[.\]]\s+", line)
            if m:
                line_lower = line.lower()
                if bare.lower() in line_lower or bare_spaced.lower() in line_lower:
                    return int(m.group(1))
        return None

    def _check_assert(self, cfg: dict, output: str) -> tuple[bool, str]:
        # SSOT: same evaluator as the WS runner; CLI adds case-insensitive
        # matching and underscore→space variants ("new_password" matches the
        # rendered label "New Password").
        return evaluate_text_assert(
            cfg, output,
            case_insensitive=True,
            underscore_variants=True,
            resolve=self._resolve_vars,
        )
