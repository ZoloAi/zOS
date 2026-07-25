# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/hint_analyzer.py
"""
z raven --hint — analyze zRaven/runs.csv and surface agent-level hints.

Data sources:
    zRaven/output/runs.csv           — one row per run (mode, result, error_class, …)
    zRaven/output/.last_raven_result — last run JSON (fallback if runs.csv absent)
    zVersions/tests/                 — archived revision names per UI version
    zRaven/zRaven.<name>.zolo        — line count of active raven file
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from .hint_rules import apply_all, Hint
from .issue_scout import scout
from .colors import GREEN, RED, YELLOW, CYAN, BOLD, DIM, RESET


_MAX_RUNS = 20   # rows read from runs.csv for analysis


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def _hints_with_scout(workspace: Path, data: dict) -> list[Hint]:
    """Rule hints + the framework-suspect scout verdict (when it fires)."""
    hints = apply_all(data)
    try:
        suspect = scout(workspace, data)
    except Exception:  # pylint: disable=broad-except
        suspect = None  # triage must never break the hint pass
    if suspect:
        hints.append(suspect)
    return hints


def analyze_and_print(workspace: Path, raven_name: str) -> list[Hint]:
    """Collect data, apply rules, print hints. Returns hint list."""
    data  = _collect(workspace, raven_name)
    hints = _hints_with_scout(workspace, data)
    _print_hints(data, hints, raven_name)
    return hints


def analyze_silent(workspace: Path, raven_name: str) -> list[Hint]:
    """Collect + apply rules without printing. Used for auto-append after --run."""
    data = _collect(workspace, raven_name)
    return _hints_with_scout(workspace, data)


# ─────────────────────────────────────────────────────────────────────────────
# Data collection
# ─────────────────────────────────────────────────────────────────────────────

def _collect(workspace: Path, raven_name: str) -> dict:
    raven_dir  = workspace / "zRaven"
    output_dir = raven_dir / "output"

    runs     = _read_runs(output_dir)
    last     = runs[-1] if runs else _read_last_result_fallback(output_dir)
    archived = _list_archived(workspace, raven_name)
    lines    = _count_lines(raven_dir, raven_name)
    raven_meta = _parse_raven_file(raven_dir, raven_name)

    ui_versions = list(dict.fromkeys(
        r.get("ui_version", "") for r in runs if r.get("ui_version")
    ))

    return {
        "runs":              runs,
        "last":              last,
        "archived":          archived,
        "raven_lines":       lines,
        "raven_name":        raven_name,
        "ui_versions":       ui_versions,
        "shot_count":        raven_meta["shot_count"],
        "dom_assert_count":  raven_meta["dom_assert_count"],
        "has_browser_steps": raven_meta["has_browser_steps"],
    }


def _read_runs(output_dir: Path) -> list[dict]:
    csv_path = output_dir / "runs.csv"
    if not csv_path.exists():
        return []
    try:
        rows = []
        with csv_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                rows.append(dict(row))
        return rows[-_MAX_RUNS:]
    except Exception:  # pylint: disable=broad-except
        return []


def _read_last_result_fallback(output_dir: Path) -> Optional[dict]:
    """Read .last_raven_result when runs.csv doesn't exist yet."""
    p = output_dir / ".last_raven_result"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        # Normalise to runs.csv column names
        d.setdefault("mode", "unknown")
        d.setdefault("error_class", "")
        d.setdefault("duration_sec", "")
        return d
    except Exception:  # pylint: disable=broad-except
        return None


def _list_archived(workspace: Path, raven_name: str) -> dict[str, list[str]]:
    """Return {ui_ver: [revision_names]} from zVersions/tests/.

    NB: archives live at {workspace}/zVersions/tests/ — the same path the
    generator writes and --run --r N resolves (raven_command). The old
    zRaven/zVersions/ location never existed, so rollback hints never fired.
    """
    ver_dir = workspace / "zVersions" / "tests"
    if not ver_dir.exists():
        return {}
    result: dict[str, list[str]] = {}
    prefix = f"zRaven.{raven_name}["
    for p in ver_dir.iterdir():
        if not (p.name.startswith(prefix) and p.name.endswith(".zolo")):
            continue
        # zRaven.hello[v1.0.0]_r2.zolo → ver=v1.0.0  rev=r2
        inner = p.name[len(prefix):]
        if "]" not in inner:
            continue
        ui_ver, rest = inner.split("]", 1)
        rev = rest.lstrip("_").replace(".zolo", "")
        result.setdefault(ui_ver, []).append(rev)
    return result


def _count_lines(raven_dir: Path, raven_name: str) -> int:
    p = raven_dir / f"zRaven.{raven_name}.zolo"
    if not p.exists():
        return 0
    try:
        return sum(1 for _ in p.open(encoding="utf-8"))
    except Exception:  # pylint: disable=broad-except
        return 0


def _parse_raven_file(raven_dir: Path, raven_name: str) -> dict:
    """
    Light parse of the active .zolo file.

    Returns:
        shot_count      int  — number of zShot: primitives
        dom_assert_count int — number of zAssert/dom blocks that check
                               className, tagName, or style (structural CSS checks)
        has_browser_steps bool — True if any zOpen/zBoot/zShot steps found
    """
    p = raven_dir / f"zRaven.{raven_name}.zolo"
    if not p.exists():
        return {"shot_count": 0, "dom_assert_count": 0, "has_browser_steps": False}

    try:
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()

        shot_count = sum(1 for ln in lines if ln.strip().startswith("zShot:"))
        dom_struct_props = {"className", "tagName", "style", "computedStyle"}
        dom_assert_count = sum(
            1 for ln in lines
            if any(prop in ln for prop in dom_struct_props)
        )
        has_browser_steps = any(
            ln.strip().startswith(("zShot:", "zOpen:", "zBoot:", "zViewport:"))
            for ln in lines
        )
        return {
            "shot_count": shot_count,
            "dom_assert_count": dom_assert_count,
            "has_browser_steps": has_browser_steps,
        }
    except Exception:  # pylint: disable=broad-except
        return {"shot_count": 0, "dom_assert_count": 0, "has_browser_steps": False}


# ─────────────────────────────────────────────────────────────────────────────
# Display
# ─────────────────────────────────────────────────────────────────────────────

def _print_hints(data: dict, hints: list[Hint], raven_name: str) -> None:
    runs = data.get("runs") or []
    last = data.get("last") or {}

    print(f"\n{BOLD}{CYAN}💡 z raven --hint{RESET}  {DIM}({raven_name}){RESET}\n")

    # ── Run summary ───────────────────────────────────────────────────────────
    if last:
        failed_n = int(last.get("steps_failed", 0) or 0)
        total_n  = int(last.get("steps_total",  0) or 0)
        result   = last.get("result") or ("pass" if (failed_n == 0 and total_n > 0) else "fail")
        passed  = last.get("steps_passed", 0)
        total   = last.get("steps_total", 0)
        mode    = last.get("mode", "?")
        ts      = str(last.get("timestamp", ""))[:16].replace("T", " ")
        dur     = last.get("duration_sec") or ""
        dur_str = f"  {dur}s" if dur else ""
        eclass  = last.get("error_class") or ""
        eclass_str = f"  [{eclass}]" if eclass and eclass != "clean" else ""
        color   = GREEN if result == "pass" else RED
        icon    = "✓" if result == "pass" else "✗"
        print(f"  Last run:  {color}{icon} {result.upper()}{RESET}"
              f"  {passed}/{total} steps"
              f"  {DIM}{mode}{eclass_str}{dur_str}  {ts}{RESET}")

    if runs:
        pass_count = sum(1 for r in runs
                         if int(r.get("steps_failed", 0) or 0) == 0
                         and int(r.get("steps_total", 0) or 0) > 0)
        modes_seen = set(r.get("mode", "") for r in runs if r.get("mode"))
        modes_str  = " + ".join(sorted(modes_seen)) if modes_seen else "?"
        print(f"  History:   {pass_count}/{len(runs)} passed"
              f"  {DIM}(last {len(runs)} runs, modes: {modes_str}){RESET}")

    print()

    # ── Hints ─────────────────────────────────────────────────────────────────
    if not hints:
        print(f"  {GREEN}✓ All clear — no actionable hints{RESET}\n")
        return

    for i, hint in enumerate(hints, 1):
        print(f"  {YELLOW}⚡{RESET} {BOLD}{i}.{RESET}  {hint.message}")
        if hint.command:
            print(f"      {CYAN}${RESET} {DIM}{hint.command}{RESET}")
        print()
