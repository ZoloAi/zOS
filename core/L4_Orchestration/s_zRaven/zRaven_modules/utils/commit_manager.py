# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/commit_manager.py
"""zCommit — additive milestone snapshots for a zRaven flow (spark + raven pair).

NOT git. No branches, no merges, no history truncation — a commit is a plain
numbered folder (c1, c2, ...) under zVersions/commits/<flow>/, written once and
never mutated. Every commit stores:

  snapshot/   full raw copy of the flow's own files (spark + active raven) AND
              the WHOLE app tree at that moment — every source file minus a
              noise list (_SNAPSHOT_EXCLUDES): plugins, styles, templates,
              public assets, schemas, spools, views, routes, all of it. A
              commit is a real restore point (zOS#99 — the old include-glob
              list covered only four .zolo folders, so a commit silently
              missed the app's plugin logic and stylesheet entirely)
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
import fnmatch
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# What a snapshot SKIPS — everything else in the app folder is captured.
# Exclude-based on purpose (zOS#99): the old include-glob list (four .zolo
# folders) meant plugins/, styles/, templates/, public/ were never archived —
# a "restore point" that silently wasn't one. The contract now mirrors
# `zolo push` (zguard/push/bundle.py _DEFAULT_IGNORE + full-tree walk): the
# app IS the folder minus noise — new folder conventions are captured by
# default instead of forgotten by default. Keep the two lists' SPIRIT in
# sync by hand; the code can't be shared (zOS core must work without zguard).
_SNAPSHOT_EXCLUDES = (
    # history/output — never source (zVersions would recurse into commits!)
    "zVersions",
    "zRaven/output",
    "zRaven/zShots",      # shots are copied separately, per-flow, to shots/
    # runtime state — captured by --run's Data isolation story, not commits
    "Data",
    "logs",
    "*.log",
    # tooling noise
    ".git", "__pycache__", "*.pyc", ".DS_Store",
    ".venv", "venv", "node_modules",
    # this machine's hosting link — local state, never a restore payload
    "zProject.*.receipt.zolo",
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


def _excluded(rel_posix: str) -> bool:
    """True if a workspace-relative path matches the snapshot noise list.

    Same matching spirit as push's _ignored: a pattern hits on the full
    relative path, on any single path segment (so `__pycache__` prunes at any
    depth), and as a directory prefix (so `zRaven/output` prunes the subtree).
    """
    parts = rel_posix.split("/")
    for pat in _SNAPSHOT_EXCLUDES:
        if fnmatch.fnmatch(rel_posix, pat):
            return True
        if "/" not in pat and any(fnmatch.fnmatch(seg, pat) for seg in parts):
            return True
        if rel_posix == pat or rel_posix.startswith(pat + "/"):
            return True
    return False


def _collect_shared_files(workspace: Path) -> list[Path]:
    """Every source file in the app tree, minus _SNAPSHOT_EXCLUDES (zOS#99)."""
    found: list[Path] = []
    for p in sorted(workspace.rglob("*")):
        if not p.is_file():
            continue
        if _excluded(p.relative_to(workspace).as_posix()):
            continue
        found.append(p)
    return found


def _is_binary(path: Path) -> bool:
    """Cheap binary sniff — a NUL byte in the first 8 KiB."""
    try:
        return b"\0" in path.read_bytes()[:8192]
    except OSError:
        return True


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
        # Binary (covers/fonts/images now in scope, zOS#99): note the change,
        # never inline a byte soup into the changelog.
        if _is_binary(old_p) or _is_binary(new_p):
            if old_p.read_bytes() != new_p.read_bytes():
                lines.append(f"=== binary changed: {rel} ===\n")
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

    # ── the rest of the app tree (historical record only, zOS#99) ─────────────
    shared_rel: list[str] = []
    for src in _collect_shared_files(workspace):
        rel = src.relative_to(workspace).as_posix()
        if rel in flow_owned_rel:
            continue  # spark + active raven already captured above
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
        # The snapshot contract, stated in the artifact itself (zOS#99): full
        # app tree minus these — so a reader of any single commit knows exactly
        # what was and wasn't captured, without source archaeology.
        "contract":   "full-tree",
        "excluded":   list(_SNAPSHOT_EXCLUDES),
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
