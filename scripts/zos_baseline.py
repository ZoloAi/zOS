#!/usr/bin/env python3
"""
zos_baseline — the alpha release gate.

Stages every zDemo into an isolated directory (the way a random user would
get them), installs zolo-os into a fresh venv (from PyPI, or a release
candidate wheel), and runs every zRaven suite of every demo. The result is
one quantifiable number: N/N suites green.

Two staging modes:
  --stage git       (default) `git archive <ref>` — only committed content.
                    This is the release gate: if it isn't in git, it doesn't
                    exist. Untracked demos show up as missing == red.
  --stage worktree  copy the working tree's zDemos — for pre-commit iteration.

Two install modes:
  (default)         pip install zolo-os from PyPI — post-publish confirmation.
  --wheel PATH      install a local wheel — pre-publish release-candidate gate.

ALPHA SCOPE (2026-07): this machine only — darwin-arm64 / cp312. The zolo-os
wheel is pure Python (builds in seconds); the compiled zGuard image is
provisioned from zguard_bin/, which intentionally carries ONLY this platform
until the alpha ships. No cross-platform wheel matrix, no CI binary builds
in the loop. Widen zguard_bin (via zGuard CI + scripts/refresh_zguard_bin.py)
only when the alpha is out the door.

Deployment posture:
  --deployment production   (default) skips zEnv.development.zolo overlays,
                            which carry machine-specific dev mounts.
  --deployment development  reproduces the developer default.

Usage:
  python3 scripts/zos_baseline.py                       # full gate, PyPI
  python3 scripts/zos_baseline.py --wheel dist/zolo_os-1.7.0-py3-none-any.whl
  python3 scripts/zos_baseline.py --demos zHello,zTaskList --stage worktree
  python3 scripts/zos_baseline.py --keep                # keep the run dir

Exit code: 0 iff every discovered suite passed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import venv
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNS_DIR = Path.home() / "zos-baseline-runs"
DEFAULT_SUITE_TIMEOUT = 900  # seconds; zRM's canonical suite is ~51 browser steps

# Env vars that leak this machine's dev setup into the "random user" posture.
DEV_ENV_VARS = (
    "ZBIFROST_CLIENT_BASE",
    "ZGUARD_DEV_PATH",
    "ZRAVEN_FILE",
    "ZRAVEN_RUNNER",
    "ZRAVEN_TARGET",
    "PYTHONPATH",
    "VIRTUAL_ENV",
)


@dataclass
class SuiteResult:
    demo: str
    suite: str            # zRaven file name
    spark: str            # spark file name it was paired with
    status: str = "pending"   # pass | fail | timeout | error | unpaired
    duration_s: float = 0.0
    steps_failed: int = 0
    failed_steps: list = field(default_factory=list)
    log: str = ""             # path to captured output
    detail: str = ""


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


# ─────────────────────────────────────────────────────────────────────────────
# Staging
# ─────────────────────────────────────────────────────────────────────────────

def stage_demos_git(ref: str, dest: Path) -> list[str]:
    """Extract zDemos/ from a git ref. Returns list of staged demo names."""
    log(f"→ staging zDemos from git ref '{ref}' (committed content only)")
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tf:
        tar_path = Path(tf.name)
    try:
        with open(tar_path, "wb") as f:
            p = subprocess.run(["git", "archive", ref, "zDemos"], cwd=REPO_ROOT, stdout=f,
                               stderr=subprocess.PIPE)
        if p.returncode != 0:
            sys.exit(f"git archive failed: {p.stderr.decode().strip()}")
        with tarfile.open(tar_path) as tar:
            tar.extractall(dest, filter="data")
    finally:
        tar_path.unlink(missing_ok=True)
    demos_dir = dest / "zDemos"
    return sorted(d.name for d in demos_dir.iterdir() if d.is_dir())


def stage_demos_worktree(dest: Path) -> list[str]:
    """Copy zDemos/ from the working tree (pre-commit iteration mode)."""
    log("→ staging zDemos from the working tree (uncommitted content INCLUDED)")
    src = REPO_ROOT / "zDemos"
    demos_dir = dest / "zDemos"

    def ignore(_dir, names):
        return {n for n in names if n in ("output", "zShots", "logs", "__pycache__", ".DS_Store")}

    shutil.copytree(src, demos_dir, ignore=ignore)
    return sorted(d.name for d in demos_dir.iterdir() if d.is_dir())


# ─────────────────────────────────────────────────────────────────────────────
# Environment (venv + install)
# ─────────────────────────────────────────────────────────────────────────────

def build_venv(run_dir: Path, wheel: Path | None, pin: str | None) -> Path:
    venv_dir = run_dir / "venv"
    log(f"→ creating fresh venv: {venv_dir}")
    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    pip = venv_dir / "bin" / "pip"

    if wheel:
        target = str(wheel.resolve())
        log(f"→ installing release candidate wheel: {wheel.name}")
    else:
        target = f"zolo-os=={pin}" if pin else "zolo-os"
        log(f"→ installing {target} from PyPI (random-user posture)")

    r = run([str(pip), "install", "--quiet", target])
    if r.returncode != 0:
        sys.exit(f"install failed:\n{r.stderr}")

    z = venv_dir / "bin" / "z"
    if not z.exists():
        sys.exit("venv install completed but `z` entrypoint is missing")

    ver = run([str(pip), "show", "zolo-os"])
    for line in ver.stdout.splitlines():
        if line.startswith(("Version:", "Location:")):
            log(f"   {line}")

    log("→ ensuring Playwright Chromium (shared browser cache)")
    r = run([str(venv_dir / "bin" / "python"), "-m", "playwright", "install", "chromium"])
    if r.returncode != 0:
        log(f"   WARNING: playwright install failed: {r.stderr.strip()[:200]}")
    return venv_dir


def child_env(venv_dir: Path, deployment: str) -> dict:
    env = os.environ.copy()
    for var in DEV_ENV_VARS:
        env.pop(var, None)
    env["PATH"] = f"{venv_dir / 'bin'}:{env['PATH']}"
    env["DEPLOYMENT"] = deployment
    return env


# ─────────────────────────────────────────────────────────────────────────────
# Suite discovery
# ─────────────────────────────────────────────────────────────────────────────

def discover_suites(demo_dir: Path) -> list[tuple[str, str | None]]:
    """Pair each zRaven/zRaven.<flow>.zolo with its spark by stem.

    Canonical flows use zSpark.<flow>.zolo, dev flows use _zSpark.<flow>.zolo.
    Returns [(raven_filename, spark_filename_or_None), ...].
    """
    raven_dir = demo_dir / "zRaven"
    pairs = []
    for raven in sorted(raven_dir.glob("zRaven.*.zolo")):
        flow = raven.name[len("zRaven."):-len(".zolo")]
        spark = None
        for candidate in (f"zSpark.{flow}.zolo", f"_zSpark.{flow}.zolo"):
            if (demo_dir / candidate).is_file():
                spark = candidate
                break
        pairs.append((raven.name, spark))
    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# Suite execution
# ─────────────────────────────────────────────────────────────────────────────

def run_suite(demo_dir: Path, spark: str, raven: str, env: dict,
              timeout: int, log_path: Path) -> SuiteResult:
    result = SuiteResult(demo=demo_dir.name, suite=raven, spark=spark, log=str(log_path))
    z = "z"  # venv bin is first on PATH in env

    # z requirements: installs app-scoped zRequirements (e.g. zDarkroom → Pillow).
    # It confirms interactively ([y/N]) — feed it a yes. A demo without
    # zRequirements is a fast no-op.
    run([z, "requirements", spark], cwd=demo_dir, env=env, timeout=300, input="y\n")

    # Stale-result protection: the JSON below is the authoritative outcome,
    # so make sure we never read a previous run's file.
    last_result = demo_dir / "zRaven" / "output" / ".last_raven_result"
    last_result.unlink(missing_ok=True)

    start = time.monotonic()
    with open(log_path, "w") as lf:
        # --spark takes the spark FILENAME (works for both zSpark.* and _zSpark.*);
        # the bare `--run <name>` shorthand only resolves zSpark.<name>.zolo stems.
        proc = subprocess.Popen(
            [z, "raven", "--run", "--spark", spark],
            cwd=demo_dir, env=env, stdout=lf, stderr=subprocess.STDOUT,
            start_new_session=True,  # own process group → clean kill on timeout
        )
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            result.status = "timeout"
            result.duration_s = round(time.monotonic() - start, 1)
            result.detail = f"killed after {timeout}s"
            return result
    result.duration_s = round(time.monotonic() - start, 1)

    if last_result.exists():
        try:
            data = json.loads(last_result.read_text())
            result.status = "pass" if data.get("result") == "pass" else "fail"
            result.steps_failed = int(data.get("steps_failed") or 0)
            result.failed_steps = list(data.get("failed_steps") or [])
            return result
        except (json.JSONDecodeError, ValueError):
            pass
    # No result JSON: the run crashed before the reporter wrote anything.
    result.status = "pass" if rc == 0 else "error"
    if result.status == "error":
        result.detail = f"exit {rc}, no .last_raven_result written"
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────

STATUS_MARK = {"pass": "✓", "fail": "✗", "timeout": "⏱", "error": "!", "unpaired": "?"}


def print_scorecard(results: list[SuiteResult]) -> None:
    log("")
    log("=" * 72)
    log("zOS BASELINE SCORECARD")
    log("=" * 72)
    width = max(len(f"{r.demo}/{r.suite}") for r in results) + 2
    for r in results:
        name = f"{r.demo}/{r.suite}"
        mark = STATUS_MARK.get(r.status, "?")
        extra = ""
        if r.status == "fail":
            extra = f"  ({r.steps_failed} step(s): {', '.join(r.failed_steps[:3])})"
        elif r.detail:
            extra = f"  ({r.detail})"
        log(f"  {mark} {name:<{width}} {r.status.upper():<8} {r.duration_s:>7.1f}s{extra}")
    passed = sum(1 for r in results if r.status == "pass")
    log("-" * 72)
    log(f"  BASELINE: {passed}/{len(results)} suites green")
    log("=" * 72)


def write_report(run_dir: Path, results: list[SuiteResult], meta: dict) -> Path:
    report = {"meta": meta, "results": [asdict(r) for r in results],
              "passed": sum(1 for r in results if r.status == "pass"),
              "total": len(results)}
    path = run_dir / "baseline_report.json"
    path.write_text(json.dumps(report, indent=2))
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=("git", "worktree"), default="git")
    ap.add_argument("--ref", default="HEAD", help="git ref to stage from (default HEAD)")
    ap.add_argument("--wheel", type=Path, help="install this zolo-os wheel instead of PyPI")
    ap.add_argument("--pin", help="pin a zolo-os version from PyPI (e.g. 1.7.0)")
    ap.add_argument("--demos", help="comma-separated subset (default: all staged demos)")
    ap.add_argument("--deployment", default="production",
                    help="DEPLOYMENT overlay for demo boots (default: production)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_SUITE_TIMEOUT,
                    help=f"per-suite timeout in seconds (default {DEFAULT_SUITE_TIMEOUT})")
    ap.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    ap.add_argument("--keep", action="store_true",
                    help="keep the run dir even when all suites pass")
    args = ap.parse_args()

    if args.wheel and not args.wheel.is_file():
        sys.exit(f"wheel not found: {args.wheel}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = args.runs_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    logs_dir = run_dir / "logs"
    logs_dir.mkdir()
    log(f"run dir: {run_dir}")

    if args.stage == "git":
        staged = stage_demos_git(args.ref, run_dir)
    else:
        staged = stage_demos_worktree(run_dir)
    log(f"→ staged {len(staged)} demos: {', '.join(staged)}")

    wanted = None
    if args.demos:
        wanted = {d.strip() for d in args.demos.split(",")}
        missing = wanted - set(staged)
        if missing:
            log(f"   WARNING: requested but not staged (uncommitted?): {', '.join(sorted(missing))}")
        staged = [d for d in staged if d in wanted]

    venv_dir = build_venv(run_dir, args.wheel, args.pin)
    env = child_env(venv_dir, args.deployment)

    results: list[SuiteResult] = []
    for demo in staged:
        demo_dir = run_dir / "zDemos" / demo
        pairs = discover_suites(demo_dir)
        if not pairs:
            results.append(SuiteResult(demo=demo, suite="(none)", spark="",
                                       status="error", detail="no zRaven suites found"))
            continue
        for raven, spark in pairs:
            if spark is None:
                results.append(SuiteResult(demo=demo, suite=raven, spark="",
                                           status="unpaired",
                                           detail="no zSpark/_zSpark file for this flow"))
                continue
            log(f"→ {demo}: {spark} + {raven}")
            log_path = logs_dir / f"{demo}.{raven}.log"
            r = run_suite(demo_dir, spark, raven, env, args.timeout, log_path)
            mark = STATUS_MARK.get(r.status, "?")
            log(f"   {mark} {r.status.upper()} in {r.duration_s}s")
            results.append(r)

    meta = {
        "timestamp": stamp,
        "stage": args.stage,
        "ref": args.ref if args.stage == "git" else None,
        "install": str(args.wheel) if args.wheel else (f"zolo-os=={args.pin}" if args.pin else "zolo-os (PyPI latest)"),
        "deployment": args.deployment,
        "python": sys.version.split()[0],
    }
    report_path = write_report(run_dir, results, meta)
    print_scorecard(results)
    log(f"report: {report_path}")

    all_green = all(r.status == "pass" for r in results) and bool(results)
    if all_green and not args.keep:
        log("all green — removing run dir (use --keep to retain)")
        shutil.rmtree(run_dir, ignore_errors=True)
    return 0 if all_green else 1


if __name__ == "__main__":
    sys.exit(main())
