# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/commit_manager.py
"""zCommit — additive milestone snapshots for a zRaven flow (spark + raven pair).

NOT git. No branches, no merges, no history truncation — a commit is a plain
numbered folder (c1, c2, ...) under zVersions/commits/<flow>/, written once and
never mutated. Every commit stores:

  snapshot/   full raw copy of the flow's own files (spark + active raven) AND
              the project's shared text-source state at that moment (schemas,
              zLoom spools, zUI views, routes) — whatever of those exist
  diff.txt    a plain unified diff against the PREVIOUS commit of this SAME
              flow (agent-only changelog; absent on the genesis commit c1)
  shots/      raw copy of zRaven/zShots/<flow>/ at commit time (Bifrost only)
  <title>.log raw copy of the flow's last run log, if one exists

manifest.json inside each commit folder records which snapshot paths are
flow-owned (spark + raven — the ONLY files zRevive ever writes back) vs shared
(everything else — historical record for the agent to read, never restored).

zVersions/commits.csv is the project-wide ledger — one row per commit across
every flow in this app, so `z raven --commit` history reads in one file.
"""

from __future__ import annotations

import csv
import difflib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Shared project text-source globs, relative to workspace root. A commit
# snapshots whichever of these exist — no error when a golden app has no
# routes/ or no models/ yet.
_SHARED_GLOBS = (
    "models/**/*.zolo",
    "zLoom/**/*.zolo",
    "zViews/**/*.zolo",
    "routes/**/*.zolo",
)

_LEDGER_COLUMNS = (
    "id", "flow", "commit", "label", "timestamp",
    "spark_file", "raven_file",
    "steps_total", "steps_passed", "steps_failed",
    "path",
)


class CommitBlockedError(Exception):
    """Raised when the flow's last run didn't pass and --force wasn't given."""


def _last_run_row(workspace: Path, raven_name: str) -> Optional[dict]:
    """Most recent runs.csv row for this raven file, or None if it never ran."""
    runs_csv = workspace / "zRaven" / "output" / "runs.csv"
    if not runs_csv.exists():
        return None
    target = f"zRaven.{raven_name}.zolo"
    last: Optional[dict] = None
    with runs_csv.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("raven_file") == target:
                last = row
    return last


def _next_commit_n(flow_dir: Path) -> int:
    if not flow_dir.exists():
        return 1
    nums = []
    for p in flow_dir.iterdir():
        if p.is_dir() and p.name.startswith("c") and p.name[1:].isdigit():
            nums.append(int(p.name[1:]))
    return (max(nums) + 1) if nums else 1


def _collect_shared_files(workspace: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in _SHARED_GLOBS:
        found.extend(sorted(workspace.glob(pattern)))
    return found


def _resolve_log_path(workspace: Path, title: str, log_dir_hint: str) -> Optional[Path]:
    """Best-effort locate the flow's run log (SSOT filename: '{title}.log')."""
    if not title:
        return None
    rel = log_dir_hint.removeprefix("@.").lstrip("/") if log_dir_hint else "logs"
    candidate = workspace / rel / f"{title}.log"
    if candidate.exists():
        return candidate
    # Fallback: scan for it anywhere one level under workspace.
    matches = list(workspace.glob(f"*/{title}.log"))
    return matches[0] if matches else None


def _write_diff(old_snapshot: Path, new_snapshot: Path, out_path: Path) -> None:
    """Unified diff of every tracked file, old commit vs new — plain text, git-diff-like."""
    old_files = {p.relative_to(old_snapshot).as_posix() for p in old_snapshot.rglob("*") if p.is_file()}
    new_files = {p.relative_to(new_snapshot).as_posix() for p in new_snapshot.rglob("*") if p.is_file()}

    lines: list[str] = []
    for rel in sorted(old_files | new_files):
        old_p, new_p = old_snapshot / rel, new_snapshot / rel
        if rel in old_files and rel not in new_files:
            lines.append(f"=== removed: {rel} ===\n")
            continue
        if rel not in old_files and rel in new_files:
            lines.append(f"=== added: {rel} ===\n")
            continue
        old_text = old_p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        new_text = new_p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if old_text == new_text:
            continue
        diff = difflib.unified_diff(old_text, new_text, fromfile=f"a/{rel}", tofile=f"b/{rel}")
        lines.extend(diff)
        lines.append("\n")

    if lines:
        out_path.write_text("".join(lines), encoding="utf-8")


def create_commit(
    workspace: Path,
    spark_path: Path,
    raven_name: str,
    zspark_config: dict,
    label: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Capture a zCommit for one flow. Returns a summary dict for CLI printing.

    Raises CommitBlockedError if the flow's last run didn't pass (steps_failed
    != 0, or it never ran) and force is False — a commit is a milestone claim,
    so an unproven or broken state needs an explicit override to record.
    """
    last_run = _last_run_row(workspace, raven_name)
    if not force:
        if last_run is None:
            raise CommitBlockedError(
                f"No run history for zRaven.{raven_name}.zolo — run `z raven --run` "
                f"first, or pass --force to commit anyway."
            )
        if last_run.get("steps_failed", "0") not in ("0", ""):
            raise CommitBlockedError(
                f"Last run of zRaven.{raven_name}.zolo failed "
                f"({last_run.get('steps_passed')}/{last_run.get('steps_total')} passed) "
                f"— fix it or pass --force to commit anyway."
            )

    commits_root = workspace / "zVersions" / "commits"
    flow_dir     = commits_root / raven_name
    n            = _next_commit_n(flow_dir)
    commit_dir   = flow_dir / f"c{n}"
    snapshot_dir = commit_dir / "snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # ── flow-owned files (the ONLY ones zRevive ever restores) ────────────────
    flow_owned_rel: list[str] = []
    raven_active = workspace / "zRaven" / f"zRaven.{raven_name}.zolo"
    for src in (spark_path, raven_active):
        if not src.exists():
            continue
        rel = src.relative_to(workspace).as_posix()
        dest = snapshot_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        flow_owned_rel.append(rel)

    # ── shared project text-source state (historical record only) ─────────────
    shared_rel: list[str] = []
    for src in _collect_shared_files(workspace):
        rel = src.relative_to(workspace).as_posix()
        dest = snapshot_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        shared_rel.append(rel)

    # ── diff vs previous commit of this same flow ──────────────────────────────
    if n > 1:
        prev_snapshot = flow_dir / f"c{n - 1}" / "snapshot"
        if prev_snapshot.exists():
            _write_diff(prev_snapshot, snapshot_dir, commit_dir / "diff.txt")

    # ── shots (Bifrost only — absent for zCLI flows, that's fine) ──────────────
    shots_src = workspace / "zRaven" / "zShots" / raven_name
    has_shots = shots_src.exists() and any(shots_src.iterdir())
    if has_shots:
        shutil.copytree(shots_src, commit_dir / "shots")

    # ── log ─────────────────────────────────────────────────────────────────
    title    = zspark_config.get("title", "")
    log_hint = zspark_config.get("zLogPath", "@.logs")
    log_src  = _resolve_log_path(workspace, title, log_hint)
    has_log  = log_src is not None
    if log_src is not None:
        shutil.copy2(log_src, commit_dir / log_src.name)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "flow":       raven_name,
        "commit":     f"c{n}",
        "label":      label or "",
        "timestamp":  timestamp,
        "spark_file": spark_path.name,
        "raven_file": raven_active.name,
        "flow_owned": flow_owned_rel,
        "shared":     shared_rel,
        "has_shots":  has_shots,
        "has_log":    has_log,
        "last_run":   {
            "steps_total":  last_run.get("steps_total")  if last_run else None,
            "steps_passed": last_run.get("steps_passed") if last_run else None,
            "steps_failed": last_run.get("steps_failed") if last_run else None,
        },
    }
    (commit_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # ── project-wide ledger ─────────────────────────────────────────────────
    ledger = workspace / "zVersions" / "commits.csv"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    write_header = not ledger.exists()
    with ledger.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_LEDGER_COLUMNS), extrasaction="ignore")
        if write_header:
            writer.writeheader()
        row_id = 1
        if not write_header:
            with ledger.open("r", encoding="utf-8") as rfh:
                row_id = sum(1 for _ in rfh)
        writer.writerow({
            "id":           row_id,
            "flow":         raven_name,
            "commit":       f"c{n}",
            "label":        label or "",
            "timestamp":    timestamp,
            "spark_file":   spark_path.name,
            "raven_file":   raven_active.name,
            "steps_total":  manifest["last_run"]["steps_total"]  or "",
            "steps_passed": manifest["last_run"]["steps_passed"] or "",
            "steps_failed": manifest["last_run"]["steps_failed"] or "",
            "path":         str(commit_dir.relative_to(workspace)),
        })

    return {
        "flow":        raven_name,
        "commit":      f"c{n}",
        "path":        commit_dir,
        "flow_owned":  flow_owned_rel,
        "shared":      shared_rel,
        "has_shots":   has_shots,
        "has_log":     has_log,
        "has_diff":    (commit_dir / "diff.txt").exists(),
    }
