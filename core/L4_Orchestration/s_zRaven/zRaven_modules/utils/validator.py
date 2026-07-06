# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/validator.py
"""zUI ↔ zRaven structural validator.

Compares structural keys in zUI (source of truth) against zRaven.
Prints mismatches so agents know exactly what changed in the UI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from zSys import zpath  # zPath grammar — Layer-0 SSOT for sigil/segment decomposition
from .parser import zparse
from .colors import RED, YELLOW, RESET, BOLD
from .viewport import is_browser_block

# zolo vocabulary keys — appear in zUI/zRaven but are NOT user-defined paths.
# SSOT: derived live from zlsp.token_registry so this set never drifts from the
# locked grammar. Widgets, dispatch events, control-flow, and every leaf property
# come straight from the registry; only raven-runner-only primitives and a few
# meta/config keys (which the registry does not carry) are added here.
#
# NOTE: raven_generator.py does NOT import this set — it walks the UI tree with
# its own structural rules. This set is used solely by validate_structure() below
# to tell zolo vocabulary apart from user-defined block/step names.

# Raven-runner-only step primitives (not zUI vocabulary, so not in the registry).
_RAVEN_PRIMITIVE_KEYS = {
    "zPick", "zSubmit", "zFill", "zAssert", "zBoot", "zExecute", "zWait", "zClick",
    "zType", "zShot", "zScreenshot", "zDrag", "zExpect", "zUpload", "zMarker",
    "zViewport", "zOpen", "zFetch", "zClean", "zHistory", "zCapture",
    "zVar", "zAllowError", "zLogger", "zCLI", "zBifrost", "zSetup",
    # raven assert/shot sub-keys + connection config
    "not_contains", "success", "contains", "result", "dom", "style", "api",
    "equals", "matches", "status", "status_not", "body_contains",
    "json_contains", "json_key", "json_keys", "not_null", "min_length",
    "full_page", "resolution", "quality", "delay", "overwrite", "burst",
    "every", "count", "timestamp", "state", "selector", "property",
    "zConnect", "zRavenOptions", "ws", "http", "stop_on_error", "strict",
    "allow_external", "timestamp_shots",
}
# Special blocks + meta/config keys not enumerated as UI element keys.
_META_BLOCK_KEYS = {
    "zGate", "zRBAC", "zMeta", "ZNAVBAR", "zMachine", "zSpark", "Tests",
    "zTitle", "zBrush", "zScripts", "zCanvas", "panels",
}

try:  # Grammar SSOT — never hand-maintain the widget/property vocabulary.
    from zlsp.token_registry import (
        UI_ELEMENT_KEYS as _UI_ELEMENT_KEYS,
        DISPATCH_KEYS as _DISPATCH_KEYS,
        CONTROL_FLOW_KEYS as _CONTROL_FLOW_KEYS,
        UI_ELEMENT_PROPERTY_KEYS as _UI_ELEMENT_PROPERTY_KEYS,
        PLURAL_SHORTHAND_KEYS as _PLURAL_SHORTHAND_KEYS,
    )
    ZOLO_EVENT_KEYS = (
        set(_UI_ELEMENT_KEYS)
        | set(_DISPATCH_KEYS)
        | set(_CONTROL_FLOW_KEYS)
        | set(_UI_ELEMENT_PROPERTY_KEYS)
        | set(_PLURAL_SHORTHAND_KEYS)
        | _RAVEN_PRIMITIVE_KEYS
        | _META_BLOCK_KEYS
    )
except Exception:  # pylint: disable=broad-except
    # Degraded fallback if zlsp is unavailable — structure check still runs, just
    # with a narrower vocabulary (may report extra false "structural" keys).
    ZOLO_EVENT_KEYS = _RAVEN_PRIMITIVE_KEYS | _META_BLOCK_KEYS | {
        "zMenu", "zWizard", "zFunc", "zInput", "zBtn", "zText", "zMD",
        "zH1", "zH2", "zH3", "zH4", "zH5", "zH6", "zImage", "zTable", "zURL",
        "zData", "zDialog", "zCheckbox", "zSelect", "zRange", "zNavBar",
        "zSignal", "zError", "zWarning", "zSuccess", "zInfo", "zCrumbs",
        "zTerminal", "zDash", "folder", "sidebar", "default", "title",
        "options", "label", "action", "prompt", "content", "color", "if",
    }


def _build_line_map(file_path: Path) -> dict:
    """Build {key: line_number} from raw file text (1-indexed)."""
    line_map: dict[str, int] = {}
    with open(file_path) as f:
        for lineno, line in enumerate(f, start=1):
            stripped = line.lstrip()
            if ":" in stripped and not stripped.startswith("#"):
                key = stripped.split(":")[0].strip()
                if key and key not in line_map:
                    line_map[key] = lineno
    return line_map


def _collect_keys(node: Any, path: str, result: list, line_map: dict) -> None:
    """Walk a parsed zolo tree and collect all structural (user-defined) key paths."""
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        if key.startswith("_"):
            continue
        if key not in ZOLO_EVENT_KEYS:
            full_path = f"{path}.{key}" if path else key
            result.append((full_path, line_map.get(key, 0)))
        _collect_keys(value, f"{path}.{key}" if path else key, result, line_map)


def validate_structure(
    raven_file: Path,
    raven_data: dict,
    va_folder: str,
    va_file: str,
    block: str,
) -> bool:
    """
    Compare zUI structural keys against zRaven keys.
    zUI is the source of truth. Prints mismatches and returns False if any found.
    """
    folder_rel = zpath.strip_symbol(va_folder).lstrip("/")
    zui_path   = Path.cwd() / folder_rel / f"{va_file}.zolo"

    if not zui_path.exists():
        print(
            f"{YELLOW}[zRaven] zUI file not found for structure check: {zui_path}{RESET}",
            flush=True,
        )
        return True  # non-fatal — file may be in a different location

    zui_data = zparse(zui_path.read_text(), str(zui_path))

    if not zui_data or block not in zui_data:
        return True

    zui_block   = zui_data[block]
    raven_block = raven_data.get(block, {})

    # Unified step-level format (Tests: block) — no UI mirroring by design; skip.
    if "Tests" in raven_data:
        return True

    # Browser-only raven files are exempt from structure validation
    if not raven_block:
        if all(is_browser_block(v) for v in raven_data.values() if isinstance(v, dict)):
            return True

    zui_line_map   = _build_line_map(zui_path)
    raven_line_map = _build_line_map(raven_file)

    zui_keys:   list = []
    raven_keys: list = []
    _collect_keys(zui_block,   block, zui_keys,   zui_line_map)
    _collect_keys(raven_block, block, raven_keys, raven_line_map)

    zui_set   = {p for p, _ in zui_keys}
    raven_set = {p for p, _ in raven_keys}

    missing = zui_set - raven_set
    extra   = raven_set - zui_set

    if not missing and not extra:
        return True

    print(f"\n{BOLD}{RED}[zRaven] Structure mismatch — aborting{RESET}", flush=True)
    print(f"  zUI source of truth: {zui_path.name}\n", flush=True)

    if missing:
        print(f"  {RED}Missing in zRaven (defined in zUI):{RESET}", flush=True)
        for path_key in sorted(missing):
            line = zui_line_map.get(path_key.split(".")[-1], "?")
            print(f"    {RED}✗{RESET} {path_key}  {YELLOW}(zUI line {line}){RESET}", flush=True)

    if extra:
        print(f"\n  {YELLOW}Extra in zRaven (not in zUI):{RESET}", flush=True)
        for path_key in sorted(extra):
            line = raven_line_map.get(path_key.split(".")[-1], "?")
            print(f"    {YELLOW}~{RESET} {path_key}  {YELLOW}(zRaven line {line}){RESET}", flush=True)

    print()
    return False
