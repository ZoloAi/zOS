# zOS/core/L1_Foundation/c_zLoader/loader_modules/ui_version/handler_ui_version.py
"""
zUIVersion handler — session-start hook for UI file versioning.

Mirrors the zMigration pattern:
  - Hash-based short-circuit: if file hash matches last recorded hash → "UI up to date"
  - On hash mismatch: diff old vs new, record version row, snapshot backup
  - On first encounter: seed v1.0.0 record

Triggered from zLoader.handle() whenever zMeta.zUITracking is truthy.

CSV path convention (relative to the app root):
  <app_root>/zVersions/interface/<file_stem>.zVer.csv
  e.g. crm/zVersions/interface/zUI.crm.zVer.csv

Backup convention:
  <app_root>/zVersions/interface/<file_stem>.<version>.backup.zolo
  e.g. crm/zVersions/interface/zUI.crm.v1.0.0.backup.zolo
"""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

try:
    from .ui_diff import diff_ui, format_diff_summary, format_diff_detail
except ImportError:
    from ui_diff import diff_ui, format_diff_summary, format_diff_detail  # type: ignore

# ─────────────────────────────────────────────────────────────────────────────
# CSV schema
# ─────────────────────────────────────────────────────────────────────────────

VER_COLUMNS = [
    "id",
    "from_version",
    "to_version",
    "applied_at",
    "ui_hash",
    "changes_summary",
    "changes_detail",
    "backup_location",
    "rollback_possible",
    "status",
    # Phase 2 — raven result linkage (written by next session boot after z raven --run)
    "raven_result",    # "pass" | "fail" | ""
    "raven_rev",       # "active" | "r1" | "r2" | ...
    "failed_steps",    # pipe-separated step names e.g. "Pick_Export|Assert_Health"
]

# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def handle_ui_version(
    file_path: str,
    file_raw: str,
    parsed_ui: Dict[str, Any],
    zos: Any,
) -> None:
    """
    Check and record UI version for a loaded .zolo file.

    Called from zLoader.handle() after parsing when zMeta.zUITracking is true.

    Parameters
    ----------
    file_path : str
        Absolute path to the loaded .zolo file.
    file_raw : str
        Raw file content (used for hashing).
    parsed_ui : dict
        Parsed UI dictionary (used for structural diff).
    zos : Any
        zOS instance (for display and logging).
    """
    logger  = zos.logger
    display = zos.display

    try:
        meta       = parsed_ui.get("zMeta", {}) or {}
        to_version = str(meta.get("zUIVersion", "v1.0.0")).strip()
        ui_hash    = _hash(file_raw)
        ver_dir    = _ver_dir(file_path)
        ver_csv    = _ver_csv(ver_dir, file_path)

        os.makedirs(ver_dir, exist_ok=True)

        rows = _read_csv(ver_csv)

        # ── short-circuit: hash matches last row ──────────────────────────────
        if rows:
            last = rows[-1]
            if last.get("ui_hash") == ui_hash:
                recorded_ver = last.get("to_version", to_version)
                display.text(f"🔒 UI up to date ({recorded_ver})")
                _check_raven_drift(file_path, recorded_ver, display, logger)
                # Pick up any raven result written since last session
                _pick_up_raven_result(ver_dir, ver_csv, display, logger)
                logger.debug("[zUIVersion] hash match — skipping record for %s", file_path)
                return

        # ── determine from_version ────────────────────────────────────────────
        from_version = rows[-1]["to_version"] if rows else None

        # ── diff against previous backup (if available) ───────────────────────
        diff        = {}
        changes_sum = "initial version"
        changes_det = ""

        if rows:
            prev_backup = rows[-1].get("backup_location", "")
            if prev_backup and os.path.isfile(prev_backup):
                try:
                    with open(prev_backup, "r", encoding="utf-8") as f:
                        raw_backup = f.read()
                    # Use zOS parser for consistent structure (handles #~, @. refs, etc.)
                    _, ext = os.path.splitext(prev_backup)
                    old_ui = zos.zparser.parse_file_content(
                        raw_backup, ext, session=getattr(zos, "session", {}),
                        file_path=prev_backup
                    ) or {}
                    diff = diff_ui(old_ui, parsed_ui)
                    changes_sum = format_diff_summary(diff)
                    changes_det = format_diff_detail(diff)
                except Exception as e:
                    logger.warning("[zUIVersion] diff failed: %s", e)
                    changes_sum = "diff unavailable"

        # ── snapshot current file ─────────────────────────────────────────────
        backup_path = _backup_path(ver_dir, file_path, to_version)
        try:
            shutil.copy2(file_path, backup_path)
            rollback_possible = "true"
        except Exception as e:
            logger.warning("[zUIVersion] backup failed: %s", e)
            backup_path       = ""
            rollback_possible = "false"

        # ── write new version row ─────────────────────────────────────────────
        new_id = str(len(rows) + 1)
        row = {
            "id":               new_id,
            "from_version":     from_version or "",
            "to_version":       to_version,
            "applied_at":       _now(),
            "ui_hash":          ui_hash,
            "changes_summary":  changes_sum,
            "changes_detail":   changes_det,
            "backup_location":  backup_path,
            "rollback_possible": rollback_possible,
            "status":           "active",
        }
        _append_csv(ver_csv, row)

        # ── pick up any raven result from a previous run ──────────────────────
        _pick_up_raven_result(ver_dir, ver_csv, display, logger)

        # ── display feedback ──────────────────────────────────────────────────
        stem = os.path.basename(file_path)
        if from_version:
            display.text(f"📋 UI version recorded: {from_version} → {to_version} ({stem})")
            display.text(f"   Changes: {changes_sum}")
        else:
            display.text(f"🗂️  UI version tracked: {to_version} — initial ({stem})")

        logger.debug(
            "[zUIVersion] recorded %s → %s for %s (hash %s…)",
            from_version, to_version, file_path, ui_hash[:8],
        )

    except Exception as e:
        # Never block app startup for versioning errors
        zos.logger.warning("[zUIVersion] versioning skipped due to error: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# CSV helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_csv(path: str):
    if not os.path.isfile(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _append_csv(path: str, row: Dict[str, str]) -> None:
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=VER_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def _rewrite_csv(path: str, rows: list) -> None:
    """Overwrite the CSV with updated rows, filling any missing Phase-2 columns."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=VER_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # Back-fill Phase-2 columns that may be absent in pre-existing CSV rows
            for col in ("raven_result", "raven_rev", "failed_steps"):
                row.setdefault(col, "")
            writer.writerow(row)


# ─────────────────────────────────────────────────────────────────────────────
# Path helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ver_dir(file_path: str) -> str:
    """
    Return the shared zVersions/interface/ dir for this file.

    Walks up the directory tree from the file's location until it finds a
    directory named 'UI' (case-sensitive), then returns
    <app_root>/zVersions/interface/ (one level above UI/).
    This means panel files nested under UI/Dashboard/, UI/Forms/, etc.
    all cascade to the same zVersions/interface/ as the root zVaFile.

    Fallback: if no 'UI' ancestor is found, uses the file's own directory.

    Examples
    --------
    crm/UI/Dashboard/zUI.Overview.zolo  → crm/zVersions/interface/
    crm/UI/zUI.crm.zolo                 → crm/zVersions/interface/
    """
    current = os.path.dirname(os.path.abspath(file_path))
    while True:
        if os.path.basename(current) == "UI":
            app_root = os.path.dirname(current)
            return os.path.join(app_root, "zVersions", "interface")
        parent = os.path.dirname(current)
        if parent == current:
            # reached filesystem root — fallback
            return os.path.join(os.path.dirname(file_path), "zVersions", "interface")
        current = parent


def _ver_csv(ver_dir: str, file_path: str) -> str:
    stem = _stem(file_path)
    return os.path.join(ver_dir, f"{stem}.zVer.csv")


def _backup_path(ver_dir: str, file_path: str, version: str) -> str:
    stem = _stem(file_path)
    return os.path.join(ver_dir, f"{stem}.{version}.backup.zolo")


def _stem(file_path: str) -> str:
    """Filename without extension, e.g. 'zUI.crm'."""
    base = os.path.basename(file_path)
    return base.rsplit(".", 1)[0] if "." in base else base


# ─────────────────────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────────────────────

def _pick_up_raven_result(
    ver_dir: str,
    ver_csv: str,
    display: Any,
    logger: Any,
) -> None:
    """
    Read zRaven/.last_raven_result (written by zraven.py after a test run) and
    attach pass/fail data to the most recent row in ver_csv that matches
    the raven's reported ui_version.  Clears the result file after reading.

    Path convention:
        ver_dir  = <app>/UI/zVersions/
        raven    = <app>/zRaven/.last_raven_result
        (<app>   = two levels up from ver_dir)
    """
    import json as _json  # pylint: disable=import-outside-toplevel

    # ver_dir = <app_root>/zVersions/interface/ → go up two levels to app_root
    result_path = os.path.normpath(
        os.path.join(ver_dir, "..", "..", "zRaven", "output", ".last_raven_result")
    )
    if not os.path.isfile(result_path):
        return

    try:
        data = _json.loads(Path(result_path).read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug("[zUIVersion] could not read .last_raven_result: %s", e)
        return

    ui_version   = data.get("ui_version", "")
    raven_rev    = data.get("raven_rev", "")
    result       = data.get("result", "")
    failed       = data.get("failed_steps", [])
    failed_steps = "|".join(failed) if failed else ""
    timestamp    = data.get("timestamp", "")
    total        = data.get("steps_total", 0)
    passed       = data.get("steps_passed", 0)

    rows = _read_csv(ver_csv)
    if not rows:
        logger.debug("[zUIVersion] no rows in zVer.csv — skipping raven result attachment")
        _clear_result(result_path, logger)
        return

    # Find the most recent row matching this ui_version (or last row if no version stamp)
    target_idx = None
    for i in range(len(rows) - 1, -1, -1):
        if not ui_version or rows[i].get("to_version") == ui_version:
            target_idx = i
            break

    if target_idx is None:
        logger.debug(
            "[zUIVersion] no matching row for ui_version=%s — attaching to last row",
            ui_version,
        )
        target_idx = len(rows) - 1

    # Write updated row
    rows[target_idx]["raven_result"] = result
    rows[target_idx]["raven_rev"]    = raven_rev
    rows[target_idx]["failed_steps"] = failed_steps
    _rewrite_csv(ver_csv, rows)

    icon = "✅" if result == "pass" else "❌"
    display.text(
        f"{icon} zRaven result linked: {result} "
        f"({passed}/{total} steps{', ' + failed_steps if failed_steps else ''})"
        f"  [rev={raven_rev}, ui={ui_version or 'unknown'}]"
    )
    logger.debug(
        "[zUIVersion] raven result attached: %s rev=%s ui=%s failed=%s ts=%s",
        result, raven_rev, ui_version, failed_steps, timestamp,
    )
    _clear_result(result_path, logger)


def _clear_result(result_path: str, logger: Any) -> None:
    try:
        os.remove(result_path)
    except Exception as e:
        logger.debug("[zUIVersion] could not clear .last_raven_result: %s", e)


def _check_raven_drift(
    ui_file_path: str,
    ui_version: str,
    display: Any,
    logger: Any,
) -> None:
    """
    Check if the nearest zRaven file is stamped with the current UI version.
    Emits a warning if out of sync so agents know to regenerate.
    """
    try:
        ui_dir   = os.path.dirname(ui_file_path)
        raven_dir = os.path.join(ui_dir, "..", "zRaven")
        raven_dir = os.path.normpath(raven_dir)
        if not os.path.isdir(raven_dir):
            return

        for fname in os.listdir(raven_dir):
            if not fname.endswith(".zolo"):
                continue
            raven_path = os.path.join(raven_dir, fname)
            with open(raven_path, encoding="utf-8") as f:
                first_line = f.readline().strip()
            # Stamp format: # zRavenVersion: v2.0.0
            if first_line.startswith("# zRavenVersion:"):
                raven_ver = first_line.split(":", 1)[1].strip()
                if raven_ver != ui_version:
                    display.text(
                        f"⚠️  zRaven out of sync: tests are {raven_ver}, UI is {ui_version}"
                    )
                    display.text(
                        f"   Run: z raven --gen  to regenerate"
                    )
                    logger.warning(
                        "[zUIVersion] zRaven drift: %s is %s, UI is %s",
                        fname, raven_ver, ui_version,
                    )
    except Exception as e:
        logger.debug("[zUIVersion] raven drift check skipped: %s", e)


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────────────────────────────────────
__all__ = ["handle_ui_version"]
