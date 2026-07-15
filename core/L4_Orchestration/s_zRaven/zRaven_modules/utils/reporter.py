# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/reporter.py
"""zRaven output utilities: Tee logging, pass/fail/warn/info printers, result writer."""

from __future__ import annotations

import json as _json
import re as _re
import sys as _sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .colors import GREEN, RED, YELLOW, CYAN, RESET, BOLD
from ..constants import ASSERT_CONTEXT_CHARS, OUTPUT_DIRNAME, RAVEN_DIRNAME, RUN_LOG_NAME

# ── Log tee ───────────────────────────────────────────────────────────────────

_ANSI_RE = _re.compile(r"\x1b\[[0-9;]*[mKHJABCDEFGnsu]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences (SSOT for zRaven ANSI stripping)."""
    return _ANSI_RE.sub("", text)


class Tee:
    """
    Wraps a stream so writes go to both the original stream and a log file.
    Strips ANSI codes from the log file for clean plain-text output.
    Used to give zRaven an unbounded log file — bypasses terminal size limits.
    """

    def __init__(self, stream: Any, log_fh: Any) -> None:
        self._stream = stream
        self._log    = log_fh

    def write(self, data: str) -> int:
        self._stream.write(data)
        self._log.write(_ANSI_RE.sub("", data))
        return len(data)

    def flush(self) -> None:
        self._stream.flush()
        self._log.flush()

    def fileno(self) -> int:
        # Delegate only when the underlying stream has a real fd (tty / regular file).
        # Piped stdout may raise UnsupportedOperation — let it propagate so callers
        # that need a real fd (e.g. select.select) get the correct error early.
        return self._stream.fileno()

    @property
    def isatty(self):  # type: ignore[override]
        # Propagate isatty so downstream tty-detection works correctly.
        return self._stream.isatty

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def open_log_tee(app_dir: str):
    """Redirect stdout/stderr to a Tee writing the run log file.

    SSOT for the zRaven run-log path + Tee wiring. Returns
    (log_fh, orig_stdout, orig_stderr) for later restore via close_log_tee.
    """
    log_path = Path(app_dir) / RAVEN_DIRNAME / OUTPUT_DIRNAME / RUN_LOG_NAME
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh   = open(log_path, "w", encoding="utf-8")  # noqa: WPS515
    orig_out = _sys.stdout
    orig_err = _sys.stderr
    # Use raw __stdout__/__stderr__ as the live target so piped/redirected
    # parents don't buffer or deadlock.
    live_out = _sys.__stdout__ if _sys.__stdout__ is not None else _sys.stdout
    live_err = _sys.__stderr__ if _sys.__stderr__ is not None else _sys.stderr
    _sys.stdout = Tee(live_out, log_fh)
    _sys.stderr = Tee(live_err, log_fh)
    print(f"  {CYAN}📄 full log → {log_path}{RESET}", flush=True)
    return log_fh, orig_out, orig_err


def close_log_tee(log_fh, orig_out, orig_err) -> None:
    """Restore stdout/stderr and close the run log file."""
    if _sys.stdout is not orig_out:
        _sys.stdout = orig_out
    if _sys.stderr is not orig_err:
        _sys.stderr = orig_err
    try:
        log_fh.close()
    except Exception:  # pylint: disable=broad-except
        pass


# ── Step result printers ──────────────────────────────────────────────────────

_ASSERT_CONTEXT_CHARS = ASSERT_CONTEXT_CHARS


def pass_step(label: str, detail: str = "") -> None:
    msg = f"  {GREEN}✓{RESET} {label}"
    if detail:
        msg += f"  {detail}"
    print(msg, flush=True)


def fail_step(label: str, detail: str = "") -> None:
    msg = f"  {RED}✗{RESET} {label}"
    if detail:
        msg += f"\n    {RED}{detail[:_ASSERT_CONTEXT_CHARS]}{RESET}"
    print(msg, flush=True)


def warn_step(label: str, detail: str = "") -> None:
    msg = f"  {YELLOW}⚠{RESET} {label}"
    if detail:
        msg += f"  {detail}"
    print(msg, flush=True)


def info(msg: str) -> None:
    print(f"  {CYAN}→{RESET} {msg}", flush=True)


# ── Error class heuristic ─────────────────────────────────────────────────────

_STEP_TIMEOUT_WORDS  = ("wait", "timeout")
_STEP_SELECTOR_WORDS = ("click", "open", "browser")


def _classify_error(failed: int, failed_steps: list, mode: str) -> str:
    """
    Classify the dominant failure class from step names + mode.

    Values:
        clean             — all steps passed
        structure_mismatch — zRaven keys out of sync with zUI (printed before run)
        timeout           — Wait/Timeout steps failed (selector state never reached)
        selector          — Bifrost mode, Click/Open steps failed (element not found)
        assertion         — assertion failures (catch-all)
    """
    if failed == 0:
        return "clean"

    lowered = [s.lower() for s in (failed_steps or [])]
    if any(w in s for s in lowered for w in _STEP_TIMEOUT_WORDS):
        return "timeout"
    if mode == "bifrost" and any(w in s for s in lowered for w in _STEP_SELECTOR_WORDS):
        return "selector"
    return "assertion"


# ── Result writer ─────────────────────────────────────────────────────────────

_RUNS_CSV_COLUMNS = (
    "id", "timestamp", "mode", "raven_file", "ui_version", "raven_rev",
    "steps_total", "steps_passed", "steps_failed", "failed_steps",
    "duration_sec", "error_class", "zguard_origin",
)


def _zguard_origin() -> str:
    """The zguard provenance this run's process resolved (SSOT: zguard_provision).

    Stamped into every result so "green" always means "green AGAINST THIS
    zguard" — a raven run under a dev checkout and a user boot on the fetched
    wheel are different systems even when every app file matches.
    """
    try:
        from zSys.cli.zguard_provision import zguard_origin  # pylint: disable=import-outside-toplevel,import-error
        return zguard_origin()
    except Exception:  # pylint: disable=broad-except
        return "unknown"


def write_result(
    app_dir: str,
    raven_file_path: str,
    passed: int,
    failed: int,
    failed_steps: list,
    mode: str = "unknown",
    start_time: float | None = None,
) -> None:
    """
    Write .last_raven_result JSON + append a row to zRaven/runs.csv.

    .last_raven_result — read by handler_ui_version.py on next boot to attach
        pass/fail data to the matching zVer.csv row.
    zRaven/runs.csv — one row per run; queried by `z raven --hint`.
    """
    import csv as _csv  # pylint: disable=import-outside-toplevel

    raven_path = Path(raven_file_path)

    # Extract zRavenVersion stamp from first line: # zRavenVersion: v2.0.0
    ui_version = ""
    try:
        first_line = raven_path.read_text(encoding="utf-8").splitlines()[0]
        m = _re.match(r"#\s*zRavenVersion:\s*(\S+)", first_line)
        if m:
            ui_version = m.group(1)
    except Exception:  # pylint: disable=broad-except
        pass

    # Extract raven revision from filename: zRaven.crm_cli[v2.0.0]_r2.zolo → r2
    raven_rev = "active"
    m = _re.search(r"_r(\d+)\.zolo$", raven_path.name)
    if m:
        raven_rev = f"r{m.group(1)}"

    import time as _time  # pylint: disable=import-outside-toplevel
    duration_sec = round(_time.time() - start_time, 1) if start_time else None
    error_class  = _classify_error(failed, failed_steps, mode)
    timestamp    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    zguard_origin = _zguard_origin()

    result = {
        "timestamp":    timestamp,
        "raven_file":   raven_path.name,
        "ui_version":   ui_version,
        "raven_rev":    raven_rev,
        "mode":         mode,
        "zguard_origin": zguard_origin,
        "steps_total":  passed + failed,
        "steps_passed": passed,
        "steps_failed": failed,
        "failed_steps": failed_steps,
        "duration_sec": duration_sec,
        "error_class":  error_class,
        "result":       "pass" if failed == 0 else "fail",
    }

    out_dir = Path(app_dir) / "zRaven" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── .last_raven_result ─────────────────────────────────────────────────
    try:
        (out_dir / ".last_raven_result").write_text(
            _json.dumps(result, indent=2), encoding="utf-8"
        )
    except Exception:  # pylint: disable=broad-except
        pass

    # ── runs.csv — one row per run ─────────────────────────────────────────
    runs_csv = out_dir / "runs.csv"
    try:
        write_header = not runs_csv.exists()
        with runs_csv.open("a", encoding="utf-8", newline="") as fh:
            writer = _csv.DictWriter(fh, fieldnames=list(_RUNS_CSV_COLUMNS), extrasaction="ignore")
            if write_header:
                writer.writeheader()
            # Compute auto-increment id from existing row count
            row_id = 1
            if not write_header:
                with runs_csv.open("r", encoding="utf-8") as rfh:
                    row_id = sum(1 for _ in rfh)  # header + data rows; next id = count
            writer.writerow({
                "id":           row_id,
                "timestamp":    timestamp,
                "mode":         mode,
                "raven_file":   raven_path.name,
                "ui_version":   ui_version,
                "raven_rev":    raven_rev,
                "steps_total":  passed + failed,
                "steps_passed": passed,
                "steps_failed": failed,
                "failed_steps": "|".join(str(s) for s in (failed_steps or [])),
                "duration_sec": duration_sec if duration_sec is not None else "",
                "error_class":  error_class,
                "zguard_origin": zguard_origin,
            })
    except Exception:  # pylint: disable=broad-except
        pass  # never block the test run for a result-write failure
