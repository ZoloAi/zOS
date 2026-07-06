# zOS/core/L1_Foundation/c_zLoader/loader_modules/ui_version/ui_diff.py
"""
Structural diff engine for .zolo UI files.

Mirrors schema_diff.py in design: pure Python, no I/O, returns a structured
diff dict that handler_ui_version.py uses to build version records.

Detects:
  - Top-level blocks added / removed
  - Menu items added / removed in ~Name* lists
  - zDash sidebar panels added / removed
  - Key dispatch changes inside ^Action blocks (action, model, columns, etc.)
"""

from __future__ import annotations
from typing import Any, Dict, List


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def diff_ui(old_ui: Dict[str, Any], new_ui: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two parsed .zolo UI dicts (old vs new).

    Parameters
    ----------
    old_ui : dict
        Previously recorded parsed content (loaded from backup or prior parse).
    new_ui : dict
        Current parsed content.

    Returns
    -------
    dict with keys:
        blocks_added    : list[str]
        blocks_removed  : list[str]
        blocks_modified : dict[str, dict]  block_name → per-block changes
    """
    # Skip zMeta when computing structural diff — version bumps come from there
    _skip = {"zMeta", "meta"}

    old_keys = {k for k in old_ui if k not in _skip}
    new_keys = {k for k in new_ui if k not in _skip}

    result: Dict[str, Any] = {
        "blocks_added":    sorted(new_keys - old_keys),
        "blocks_removed":  sorted(old_keys - new_keys),
        "blocks_modified": {},
    }

    for key in sorted(old_keys & new_keys):
        changes = _diff_block(old_ui[key], new_ui[key])
        if changes:
            result["blocks_modified"][key] = changes

    return result


def format_diff_summary(diff: Dict[str, Any]) -> str:
    """One-line human-readable summary, e.g. '+2 block(s), ~1 modified'."""
    parts: List[str] = []
    if diff["blocks_added"]:
        parts.append(f"+{len(diff['blocks_added'])} block(s)")
    if diff["blocks_removed"]:
        parts.append(f"-{len(diff['blocks_removed'])} block(s)")
    if diff["blocks_modified"]:
        parts.append(f"~{len(diff['blocks_modified'])} modified")
    return ", ".join(parts) if parts else "structural match"


def format_diff_detail(diff: Dict[str, Any]) -> str:
    """Multi-line detail string for changes_detail column."""
    lines: List[str] = []

    if diff["blocks_added"]:
        lines.append(f"ADDED blocks: {', '.join(diff['blocks_added'])}")
    if diff["blocks_removed"]:
        lines.append(f"REMOVED blocks: {', '.join(diff['blocks_removed'])}")

    for block, changes in diff["blocks_modified"].items():
        lines.append(f"MODIFIED {block}:")
        for key, detail in changes.items():
            lines.append(f"  {key}: {detail}")

    return " | ".join(lines) if lines else ""


def is_empty_diff(diff: Dict[str, Any]) -> bool:
    """True when old and new are structurally identical."""
    return (
        not diff["blocks_added"]
        and not diff["blocks_removed"]
        and not diff["blocks_modified"]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _diff_block(old_block: Any, new_block: Any) -> Dict[str, Any]:
    """
    Diff a single block.  Returns empty dict when no structural change found.
    """
    if not isinstance(old_block, dict) or not isinstance(new_block, dict):
        if old_block != new_block:
            return {
                "value_changed": {
                    "old": str(old_block)[:120],
                    "new": str(new_block)[:120],
                }
            }
        return {}

    changes: Dict[str, Any] = {}

    all_keys = set(list(old_block.keys()) + list(new_block.keys()))

    for key in sorted(all_keys):
        # ── Menu lists: ~Name* or #~Name* ────────────────────────────────────
        if _is_menu_key(key):
            old_menu = _as_list(old_block.get(key))
            new_menu = _as_list(new_block.get(key))
            added   = [i for i in new_menu if i not in old_menu]
            removed = [i for i in old_menu if i not in new_menu]
            if added or removed:
                changes[key] = {k: v for k, v in [
                    ("items_added",   added),
                    ("items_removed", removed),
                ] if v}

        # ── zDash sidebar panels ──────────────────────────────────────────────
        elif key == "zDash":
            old_dash = old_block.get("zDash", {})
            new_dash = new_block.get("zDash", {})
            if isinstance(old_dash, dict) and isinstance(new_dash, dict):
                old_sidebar = _as_list(old_dash.get("sidebar"))
                new_sidebar = _as_list(new_dash.get("sidebar"))
                s_added   = [p for p in new_sidebar if p not in old_sidebar]
                s_removed = [p for p in old_sidebar if p not in new_sidebar]
                default_changed = old_dash.get("default") != new_dash.get("default")
                if s_added or s_removed or default_changed:
                    dash_changes: Dict[str, Any] = {}
                    if s_added:
                        dash_changes["panels_added"] = s_added
                    if s_removed:
                        dash_changes["panels_removed"] = s_removed
                    if default_changed:
                        dash_changes["default"] = {
                            "old": old_dash.get("default"),
                            "new": new_dash.get("default"),
                        }
                    changes["zDash"] = dash_changes

        # ── ^Action blocks: check dispatch key changes ────────────────────────
        elif key.startswith("^") and key in old_block and key in new_block:
            action_changes = _diff_action(old_block[key], new_block[key])
            if action_changes:
                changes[key] = action_changes

        # ── ^Action added / removed ───────────────────────────────────────────
        elif key.startswith("^"):
            if key not in old_block:
                changes[key] = {"added": True}
            elif key not in new_block:
                changes[key] = {"removed": True}

    return changes


def _diff_action(old_action: Any, new_action: Any) -> Dict[str, Any]:
    """Diff the content of a ^Action block at the top level."""
    if not isinstance(old_action, dict) or not isinstance(new_action, dict):
        return {}

    DISPATCH_KEYS = {"action", "model", "columns", "where", "order_by", "limit",
                     "group_by", "function", "zDialog", "zWizard"}

    changes: Dict[str, Any] = {}
    for prop in DISPATCH_KEYS:
        if old_action.get(prop) != new_action.get(prop):
            changes[prop] = {
                "old": str(old_action.get(prop))[:80],
                "new": str(new_action.get(prop))[:80],
            }
    return changes


def _is_menu_key(key: str) -> bool:
    """True for ~Name* and #~Name* keys."""
    k = key.lstrip("#")
    return k.startswith("~") and k.endswith("*")


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


# ─────────────────────────────────────────────────────────────────────────────
__all__ = [
    "diff_ui",
    "format_diff_summary",
    "format_diff_detail",
    "is_empty_diff",
]
