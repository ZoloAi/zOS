#!/usr/bin/env python3
"""
zraven — CLI entry point for the zRaven test runner.

Thin shell around the canonical zRaven subsystem modules.
All logic lives in core/L4_Orchestration/s_zRaven/zRaven_modules/.

Usage:
    zraven <zRaven.*.zolo> [--mode ws|cli]
           [--spark <name>] [--appdir <path>]
           [--ws ws://...] [--http http://...]
           [--vaFolder @.UI] [--vaFile zUI.foo] [--block MyBlock]
           [--timeout <seconds>]
"""

import asyncio
import sys
from pathlib import Path

from .zRaven_modules.utils.parser import parse_raven_file
from .zRaven_modules.utils.reporter import write_result
from .zRaven_modules.utils.validator import validate_structure
from .zRaven_modules.cli.cli_runner import CLIRunner
from .zRaven_modules.ws.ws_runner import ZRaven


def _arg(args: list, flag: str) -> str | None:
    return args[args.index(flag) + 1] if flag in args else None


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    raven_file = Path(args[0])
    if not raven_file.exists():
        print(f"ERROR: {raven_file} not found", flush=True)
        sys.exit(1)

    mode          = _arg(args, "--mode") or "ws"
    cli_spark     = _arg(args, "--spark")
    cli_app_dir   = _arg(args, "--appdir") or str(Path.cwd())
    cli_ws        = _arg(args, "--ws")
    cli_http      = _arg(args, "--http")
    cli_va_folder = _arg(args, "--vaFolder")
    cli_va_file   = _arg(args, "--vaFile")
    cli_block     = _arg(args, "--block")
    cli_timeout   = float(_arg(args, "--timeout") or 30)

    parsed      = parse_raven_file(raven_file.read_text(), str(raven_file), cli_timeout)
    data        = parsed["data"]
    stop_on_err = parsed["stop_on_error"]
    raven_opts  = parsed["raven_opts"]
    strict      = bool(raven_opts.get("strict", True))
    test_blocks = parsed["blocks"]

    # ── CLI mode ──────────────────────────────────────────────────────────────
    if mode == "cli":
        if not cli_spark:
            print("ERROR: --spark <name> required for --mode cli", flush=True)
            sys.exit(1)
        runner = CLIRunner(
            spark_name=cli_spark,
            app_dir=cli_app_dir,
            timeout=cli_timeout,
            stop_on_error=stop_on_err,
            strict=strict,
        )
        ok = runner.run(test_blocks)
        write_result(cli_app_dir, str(raven_file), runner.passed, runner.failed, runner.failed_steps)
        sys.exit(0 if ok else 1)

    # ── WS mode ───────────────────────────────────────────────────────────────
    connect  = parsed["connect"]
    ws_url   = cli_ws   or connect.get("ws",   "ws://127.0.0.1:8765")
    http_url = cli_http or connect.get("http", ws_url.replace("ws://", "http://").replace("wss://", "https://"))

    spark_boot: dict = {}
    if cli_va_file and cli_block:
        spark_boot = {
            "zVaFolder": cli_va_folder or "@.UI",
            "zVaFile":   cli_va_file,
            "zBlock":    cli_block,
        }

    if spark_boot:
        if not validate_structure(raven_file, data, spark_boot["zVaFolder"], spark_boot["zVaFile"], spark_boot["zBlock"]):
            sys.exit(1)

    runner_ws = ZRaven(
        ws_url=ws_url,
        http_url=http_url,
        spark_boot=spark_boot,
        raven_file=str(raven_file.resolve()),
        stop_on_error=stop_on_err,
        raven_opts=raven_opts,
    )
    ok = asyncio.run(runner_ws.run(test_blocks))
    write_result(
        str(Path(cli_app_dir).resolve()),
        str(raven_file),
        runner_ws.passed,
        runner_ws.failed,
        runner_ws.failed_steps,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
