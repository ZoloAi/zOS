# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/revive_manager.py
"""zRevive — restore a flow's own files from a zCommit back into the working tree.

The read-back counterpart to zCommit (commit_manager.py). Stricter than zCommit
on purpose:

  flow-owned only   restores ONLY the flow-owned snapshot paths recorded in the
                     commit's manifest.json (spark + active raven) — the shared
                     project text-source captured alongside them (schemas,
                     zLoom, zUI, routes) is NEVER written back, not even with
                     --force; it exists in the commit purely as a historical
                     record for the agent to read, never as a restore target
  any commit        targets any cN for a flow, not just the latest — zRevive
                     does not care about "ahead" commits, there is no history
                     to rewind through, just a folder to copy from
  conflict = error  if a flow-owned file already exists in the working tree
                     and differs from the commit being revived, zRevive REFUSES
                     by default (prints the diverging paths + how to proceed)
                     rather than silently overwriting recent, uncommitted work;
                     --force overwrites. Identical files are a silent no-op.
  drift = info only shared files that have moved on since the commit are
                     reported as an FYI note — never a blocker, never restored

zVersions/revives.csv is the project-wide ledger — one row per revive attempt
(success or conflict), mirroring commits.csv / clears.csv.
"""

from __future__ import annotations

import csv
import filecmp
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_LEDGER_COLUMNS = ("id", "timestamp", "flow", "commit", "action", "detail")


class ReviveNotFoundError(Exception):
    """No such flow, or no such commit number, exists to revive from."""


class ReviveConflictError(Exception):
    """A flow-owned file in the working tree diverges from the target commit."""


def _resolve_commit_dir(workspace: Path, flow: str, commit_n: Optional[int]) -> Path:
    flow_dir = workspace / "zVersions" / "commits" / flow
    if not flow_dir.exists():
        raise ReviveNotFoundError(f"No commits found for flow '{flow}'.")

    if commit_n is not None:
        commit_dir = flow_dir / f"c{commit_n}"
        if not commit_dir.exists():
            raise ReviveNotFoundError(f"No commit c{commit_n} found for flow '{flow}'.")
        return commit_dir

    nums = [int(p.name[1:]) for p in flow_dir.iterdir() if p.is_dir() and p.name[1:].isdigit()]
    if not nums:
        raise ReviveNotFoundError(f"No commits found for flow '{flow}'.")
    return flow_dir / f"c{max(nums)}"


def _append_ledger(workspace: Path, flow: str, commit: str, action: str, detail: str) -> None:
    ledger = workspace / "zVersions" / "revives.csv"
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
            "id": row_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "flow": flow,
            "commit": commit,
            "action": action,
            "detail": detail,
        })


def list_commits(workspace: Path, flow: Optional[str] = None) -> list[dict]:
    """Read zVersions/commits.csv, optionally filtered to one flow — for a
    no-argument `--revive` to show what's available before the user picks."""
    ledger = workspace / "zVersions" / "commits.csv"
    if not ledger.exists():
        return []
    with ledger.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [r for r in rows if not flow or r.get("flow") == flow]


def revive_flow(workspace: Path, flow: str, commit_n: Optional[int] = None, force: bool = False) -> dict:
    """Restore a flow's own (spark + raven) files from a commit snapshot.

    Raises ReviveNotFoundError (bad flow/commit) or ReviveConflictError (a
    flow-owned file diverged and --force wasn't given). Returns a summary dict
    on success: {flow, commit, restored: [...], shared_drift: [...]}.
    """
    commit_dir = _resolve_commit_dir(workspace, flow, commit_n)
    manifest   = json.loads((commit_dir / "manifest.json").read_text(encoding="utf-8"))
    snapshot   = commit_dir / "snapshot"
    commit_tag = manifest.get("commit", commit_dir.name)

    conflicts: list[str] = []
    for rel in manifest.get("flow_owned", []):
        target   = workspace / rel
        archived = snapshot / rel
        if target.exists() and archived.exists() and not filecmp.cmp(target, archived, shallow=False):
            conflicts.append(rel)

    if conflicts and not force:
        detail = ", ".join(conflicts)
        _append_ledger(workspace, flow, commit_tag, "conflict", detail)
        raise ReviveConflictError(
            f"Working copy diverges from {commit_tag} on: {detail}\n"
            f"   → commit the current state first (z raven --commit), or pass --force to overwrite."
        )

    restored: list[str] = []
    for rel in manifest.get("flow_owned", []):
        archived = snapshot / rel
        if not archived.exists():
            continue
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archived, target)
        restored.append(rel)

    shared_drift: list[str] = []
    for rel in manifest.get("shared", []):
        current  = workspace / rel
        archived = snapshot / rel
        if not archived.exists():
            continue
        if not current.exists() or not filecmp.cmp(current, archived, shallow=False):
            shared_drift.append(rel)

    reason = "restored" + (" (forced over conflict)" if conflicts else "")
    _append_ledger(workspace, flow, commit_tag, "revived", reason)

    return {
        "flow": flow,
        "commit": commit_tag,
        "restored": restored,
        "shared_drift": shared_drift,
    }
