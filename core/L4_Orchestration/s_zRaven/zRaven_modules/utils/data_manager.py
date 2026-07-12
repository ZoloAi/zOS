# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/data_manager.py
"""Isolated test data — makes every zRaven run idempotent.

Strategy: filesystem swap (not in-memory snapshot).
  prepare_test_data(app_dir)
    1. Rename  Data/         →  Data._zraven_bak/   (original — never touched)
    2. Copy    Data._zraven_bak/  →  Data/           (fresh test copy)
  teardown_test_data(app_dir)
    3. Delete  Data/                                  (discard test mutations)
    4. Rename  Data._zraven_bak/  →  Data/           (restore original)

The server keeps reading/writing Data/ normally; the original files are
completely isolated from test mutations. No in-memory buffering needed,
so large SQLite DBs are handled safely.

Fallback functions snapshot_data_dir / restore_data_dir are preserved for
callers that pre-date the swap strategy (e.g. zClean mid-test cleanup).
"""

from __future__ import annotations

import shutil
from pathlib import Path

_BAK_SUFFIX = "._zraven_bak"


# ── Primary: filesystem swap ──────────────────────────────────────────────────

def prepare_test_data(app_dir: str) -> bool:
    """Back up Data/ and create a fresh copy for the test run.
    Returns True if isolation was set up (or already active), False if Data/ does not exist.

    Idempotent: if the parent runner already took the snapshot (Data._zraven_bak/ exists),
    this is a no-op — do NOT overwrite the pre-migration backup with a post-migration one.
    """
    data_dir = Path(app_dir) / "Data"
    bak_dir  = Path(app_dir) / f"Data{_BAK_SUFFIX}"
    if not data_dir.is_dir():
        return False
    # Parent already isolated (pre-migration snapshot taken in raven_command._handle_run)
    if bak_dir.exists():
        return True  # already isolated — skip to preserve the pre-migration backup
    try:
        data_dir.rename(bak_dir)
        shutil.copytree(bak_dir, data_dir)
        return True
    except Exception:  # pylint: disable=broad-except
        # If rename/copy fails, try to restore and give up
        if bak_dir.exists() and not data_dir.exists():
            try:
                bak_dir.rename(data_dir)
            except Exception:  # pylint: disable=broad-except
                pass
        return False


def teardown_test_data(app_dir: str) -> bool:
    """Discard the test copy of Data/ and restore the original.
    Returns True if restoration succeeded.

    Retries with backoff: on Windows the just-stopped server's file handles can
    outlive process exit by a beat, making rmtree leave locked files behind —
    ignore_errors=True would then let the rename fail and SILENTLY hand the next
    suite polluted data (zRM's feed-order assert caught exactly this).
    """
    import time  # pylint: disable=import-outside-toplevel

    data_dir = Path(app_dir) / "Data"
    bak_dir  = Path(app_dir) / f"Data{_BAK_SUFFIX}"
    if not bak_dir.exists():
        return False
    for attempt in range(5):
        try:
            if data_dir.exists():
                shutil.rmtree(data_dir)
            bak_dir.rename(data_dir)
            return True
        except OSError:
            time.sleep(0.2 * (attempt + 1))
    return False


# ── Fallback: in-memory snapshot (used by zClean mid-test row delete) ─────────

def snapshot_data_dir(app_dir: str) -> dict:
    """Read every file in {app_dir}/Data/ into memory → {filename: bytes}."""
    data_dir = Path(app_dir) / "Data"
    snapshot: dict[str, bytes] = {}
    if not data_dir.is_dir():
        return snapshot
    for p in data_dir.iterdir():
        if p.is_file():
            try:
                snapshot[p.name] = p.read_bytes()
            except Exception:  # pylint: disable=broad-except
                pass
    return snapshot


def restore_data_dir(app_dir: str, snapshot: dict) -> None:
    """Write snapshotted files back to {app_dir}/Data/.
    Files created during the test that were NOT in the snapshot are deleted.
    """
    data_dir = Path(app_dir) / "Data"
    if not data_dir.is_dir():
        return
    for name, content in snapshot.items():
        try:
            (data_dir / name).write_bytes(content)
        except Exception:  # pylint: disable=broad-except
            pass
    for p in data_dir.iterdir():
        if p.is_file() and p.name not in snapshot:
            try:
                p.unlink()
            except Exception:  # pylint: disable=broad-except
                pass
