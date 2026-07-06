# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/runner.py
"""
ZRavenRunner — orchestrates a single zRaven test file against a live zOS session.

Design:
  Calls CLIRunner and ZRaven directly in-process — no subprocess spawning.
  URL/port resolution comes from the live zos object (SSOT); zRaven never
  hard-codes ports or passes them as arguments.

  CLI mode  → CLIRunner.run(test_blocks)   (drives app via stdin/stdout)
  WS mode   → asyncio.run(ZRaven.run(...)) (WS + Playwright in current process)
"""

from __future__ import annotations

import asyncio
import glob as _glob
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .constants import (
    BIFROST_ONLY_PREFIXES as _BIFROST_ONLY_PREFIXES,
    CLI_ONLY_PREFIXES as _CLI_ONLY_PREFIXES,
    ENV_FILE as _ENV_FILE,
    MODE_BIFROST as _MODE_BIFROST,
    MODE_CLI as _MODE_CLI,
)

if TYPE_CHECKING:
    from zOS.L1_Foundation.a_zConfig.zConfig_modules.network.config_raven import zRavenConfig

_LOG_PREFIX = "[zRaven]"


def _filter_blocks(test_blocks: dict, mode: str) -> dict:
    """Return only the blocks that should run for *mode* ('cli' or 'bifrost').

    Rules:
      - Block starts with a CLI-only prefix     → CLI only
      - Block starts with a Bifrost-only prefix → Bifrost only
      - Any other name (incl. zSetup, Shared_)  → both modes
    """
    result = {}
    for name, steps in test_blocks.items():
        is_cli_block     = any(name.startswith(p) for p in _CLI_ONLY_PREFIXES)
        is_bifrost_block = any(name.startswith(p) for p in _BIFROST_ONLY_PREFIXES)
        if is_cli_block and mode != _MODE_CLI:
            continue
        if is_bifrost_block and mode != _MODE_BIFROST:
            continue
        result[name] = steps
    return result


class ZRavenRunner:
    """
    Runs a single zRaven test file inside a live zOS session.

    Lifecycle:
        runner = ZRavenRunner(zos, config)
        runner.start()          # non-blocking, runs in daemon thread
        runner.wait(timeout=120)
        runner.passed / runner.failed
    """

    def __init__(self, zos: Any, config: "zRavenConfig") -> None:
        self._zos     = zos
        self._config  = config
        self._logger  = zos.logger
        self._thread: threading.Thread | None = None
        self._exit_code: int | None = None

        self.passed = 0
        self.failed = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn test run in a daemon thread (non-blocking)."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="zRaven")
        self._thread.start()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until test run completes. Returns True if all passed."""
        if self._thread:
            self._thread.join(timeout=timeout)
        return self._exit_code == 0

    def shutdown(self) -> None:
        """No subprocess to terminate — thread will complete naturally."""
        self._logger.debug(f"{_LOG_PREFIX} Shutdown requested")

    # ── Resolution helpers ────────────────────────────────────────────────────

    def _resolve_raven_file(self) -> Path | None:
        override = os.environ.get(_ENV_FILE)
        if override:
            p = Path(override)
            if p.exists():
                self._logger.debug(f"{_LOG_PREFIX} Using ZRAVEN_FILE override: {p.name}")
                return p
            self._logger.warning(f"{_LOG_PREFIX} ZRAVEN_FILE not found: {override}")

        name = self._config.name
        path = Path.cwd() / "zRaven" / f"zRaven.{name}.zolo"
        if not path.exists():
            self._logger.warning(f"{_LOG_PREFIX} File not found: {path} — skipping")
            return None
        return path

    def _resolve_ws_url(self) -> str:
        try:
            health = self._zos.bifrost.health_check()
            if health.get("running"):
                return f"ws://{health.get('host', '127.0.0.1')}:{health.get('port', 8765)}"
        except Exception:  # pylint: disable=broad-except
            pass
        return "ws://127.0.0.1:8765"

    def _resolve_http_url(self) -> str:
        """Resolve from the live server object — single source of truth."""
        try:
            return self._zos.server.get_url()
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            http     = self._zos.config.http_server
            protocol = "https" if getattr(http, "ssl_enabled", False) else "http"
            return f"{protocol}://{http.host}:{http.port}"
        except Exception:  # pylint: disable=broad-except
            from zOS.L1_Foundation.a_zConfig.zConfig_modules.network.config_http_server import (
                DEFAULT_PORT as _DEFAULT_HTTP_PORT,
            )
            return f"http://127.0.0.1:{_DEFAULT_HTTP_PORT}"

    def _is_cli_mode(self) -> bool:
        zmode = self._zos.zspark_obj.get("zMode", "zCLI")
        return str(zmode).lower() in ("zcli", "cli")

    def _find_spark_name(self) -> str | None:
        matches = _glob.glob(str(Path.cwd() / "zSpark.*.zolo"))
        if matches:
            stem  = Path(matches[0]).stem
            parts = stem.split(".", 1)
            return parts[1] if len(parts) == 2 else None
        return None

    def _spark_boot(self) -> dict:
        spark = self._zos.zspark_obj
        va_file   = spark.get("zVaFile", "")
        va_folder = spark.get("zVaFolder", "@.UI")
        block     = spark.get("zBlock", "")
        if va_file and block:
            return {"zVaFolder": va_folder, "zVaFile": va_file, "zBlock": block}
        return {}

    # ── Main dispatch ─────────────────────────────────────────────────────────

    def _run(self) -> None:
        try:
            if self._is_cli_mode():
                self._run_cli()
            else:
                self._run_ws()
        except Exception as exc:  # pylint: disable=broad-except
            import traceback
            print(f"\n{_LOG_PREFIX} FATAL unhandled error in runner thread:", flush=True)
            traceback.print_exc()
            self._exit_code = 1
            try:
                self._zos.request_shutdown(source="zRaven")
            except Exception:  # pylint: disable=broad-except
                pass

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _finish_run(self, ok: bool, runner, raven_file: Path, app_dir: str, mode: str, start_time: float) -> None:
        """Record counters, write result CSV, set exit code, log summary, shut down."""
        from .utils.reporter import write_result  # pylint: disable=import-outside-toplevel
        self.passed = runner.passed
        self.failed = runner.failed
        write_result(
            app_dir, str(raven_file), runner.passed, runner.failed, runner.failed_steps,
            mode=mode, start_time=start_time,
        )
        self._exit_code = 0 if ok else 1
        if self._exit_code == 0:
            self._logger.info(f"{_LOG_PREFIX} All {mode} tests passed ✓")
        else:
            self._logger.warning(f"{_LOG_PREFIX} Some {mode} tests failed")
        self._zos.request_shutdown(source="zRaven")

    # ── CLI mode ──────────────────────────────────────────────────────────────

    def _run_cli(self) -> None:
        from .cli.cli_runner import CLIRunner
        from .utils.parser import parse_raven_file

        raven_file = self._resolve_raven_file()
        if not raven_file:
            self._exit_code = 1
            self._zos.request_shutdown(source="zRaven")
            return

        # Use the spark file stem injected by raven_command (SSOT).
        # e.g. zSpark.zLogin_cli.zolo → zSparkStem="zLogin_cli" → ["z", "zLogin_cli"]
        # Falls back to glob scan (correct for single-spark projects).
        spark_name = (self._zos.zspark_obj or {}).get("zSparkStem") or self._find_spark_name()
        if not spark_name:
            self._logger.error(f"{_LOG_PREFIX} Could not find zSpark.*.zolo in {Path.cwd()}")
            self._exit_code = 1
            self._zos.request_shutdown(source="zRaven")
            return

        app_dir = str(Path.cwd())
        parsed        = parse_raven_file(raven_file.read_text(), str(raven_file), self._config.timeout)
        stop_on_error = parsed["stop_on_error"]
        timeout       = parsed["timeout"]
        strict        = bool(parsed["raven_opts"].get("strict", True))
        test_blocks   = _filter_blocks(parsed["blocks"], _MODE_CLI)

        self._logger.info(f"{_LOG_PREFIX} Running CLI tests: {raven_file.name} (spark: {spark_name})")

        # CLIRunner owns its own log Tee (opens the same path), so we skip the
        # outer Tee here to avoid double-writing and file-handle conflicts.
        start_time = time.time()
        runner = CLIRunner(
            spark_name=spark_name,
            app_dir=app_dir,
            timeout=timeout,
            stop_on_error=stop_on_error,
            strict=strict,
        )
        ok = runner.run(test_blocks)
        self._finish_run(ok, runner, raven_file, app_dir, _MODE_CLI, start_time)

    # ── WS / Bifrost mode ─────────────────────────────────────────────────────

    def _run_ws(self) -> None:
        from .ws.ws_runner import ZRaven
        from .utils.parser import parse_raven_file
        from .utils.reporter import close_log_tee, open_log_tee
        from .utils.validator import validate_structure

        time.sleep(1.5)  # allow server to become ready

        raven_file = self._resolve_raven_file()
        if not raven_file:
            self._exit_code = 1
            self._zos.request_shutdown(source="zRaven")
            return

        ws_url   = self._resolve_ws_url()
        http_url = self._resolve_http_url()
        app_dir  = str(Path.cwd())

        parsed        = parse_raven_file(raven_file.read_text(), str(raven_file), self._config.timeout)
        data          = parsed["data"]
        raven_opts    = parsed["raven_opts"]
        timeout       = parsed["timeout"]
        stop_on_error = parsed["stop_on_error"]
        test_blocks   = _filter_blocks(parsed["blocks"], _MODE_BIFROST)

        spark_boot = self._spark_boot()
        if spark_boot:
            validate_structure(
                raven_file, data,
                spark_boot["zVaFolder"], spark_boot["zVaFile"], spark_boot["zBlock"],
            )

        # Live route table (SSOT) so structured `zOpen: {type, zLoom|zUI, params}`
        # resolves URLs from the same routes the server serves — no magic paths.
        routes_table: dict = {}
        try:
            router = self._zos.server.route_manager.get_router()
            # Explicit routes + auto-discovered page routes (folder = URL) —
            # zOpen: <zPath> must resolve discovered pages too, not just the
            # handful declared in zServer.routes.zolo.
            routes_table = dict(getattr(router, "route_map", {}) or {})
            routes_table.update(getattr(router, "auto_discovered_routes", {}) or {})
        except Exception:  # pylint: disable=broad-except
            self._logger.debug(f"{_LOG_PREFIX} Route table unavailable for zOpen resolution")

        self._logger.info(f"{_LOG_PREFIX} Running tests: {raven_file.name} (ws={ws_url}, http={http_url})")
        self._ensure_playwright()

        log_fh, orig_out, orig_err = open_log_tee(app_dir)
        start_time = time.time()
        runner = ZRaven(
            ws_url=ws_url,
            http_url=http_url,
            timeout=timeout,
            spark_boot=spark_boot,
            raven_file=str(raven_file),
            stop_on_error=stop_on_error,
            raven_opts=raven_opts,
            routes_table=routes_table,
        )

        ok = False
        try:
            ok = asyncio.run(runner.run(test_blocks))
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.error(f"{_LOG_PREFIX} Runner error: {exc}")
            close_log_tee(log_fh, orig_out, orig_err)
            self._exit_code = 1
            self._zos.request_shutdown(source="zRaven")
            return
        finally:
            close_log_tee(log_fh, orig_out, orig_err)

        self._finish_run(ok, runner, raven_file, app_dir, _MODE_BIFROST, start_time)

    # ── Playwright install ────────────────────────────────────────────────────

    def _ensure_playwright(self) -> None:
        # Only fetch the browser binary; never run `--with-deps` (that escalates
        # to a system package install / sudo apt). Skip entirely when the
        # playwright package is not installed — there is nothing to install into.
        import importlib.util  # pylint: disable=import-outside-toplevel
        import subprocess, sys  # pylint: disable=import-outside-toplevel
        if importlib.util.find_spec("playwright") is None:
            self._logger.debug(f"{_LOG_PREFIX} Playwright package not installed — skipping browser fetch")
            return
        try:
            subprocess.check_call(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:  # pylint: disable=broad-except
            self._logger.debug(f"{_LOG_PREFIX} 'playwright install chromium' failed — continuing")
