# zSys/cli/raven_generator.py
"""
zRaven generator — produces structural test files from .zolo UI definitions.

Usage:  z raven --gen  [--spark zSpark.app.zolo]  [--v v1.0.0]  [--out path]

File loading strategy
---------------------
All zVaFiles (.zolo UI and panel files) are loaded via
zos.loader.handle_absolute_path() — the zLoader/zParser SSOT.
This correctly handles @. paths, zolo string-first syntax, and all
zOS-specific extensions.

zSpark files are NOT zVaFiles (they are flat config, loaded before the
framework boots). Those are parsed with simple regex key extraction.

Generation rules
----------------
  zDash.sidebar       → panel nav steps + zH2.label assert per panel
  ~Name*: [items]     → Pick_Item (zCLI: zMenu: zPick:) + action steps (+ zBack for nested)
  ^Action: zDialog    → zCLI: zWizard fill steps for each declared field
  ^Action: zData      → shared zAssert: contains first column / model label
  ^Action: zWizard    → zCLI: nested wizard confirm/fill steps
  Export*/Import*     → sub-menu pick + content steps + zBack
  ^Button: zLogger    → zBifrost: zClick + zLogger assertions (inlined in Tests:)

Output: single Tests: block — step-level zCLI:/zBifrost: keys dispatch per mode.
zAssert:/zMarker: steps are shared (no mode key) and run in both modes.

Generated file is stamped: # zRavenVersion: <ui_version>
Re-running z raven --gen regenerates structure but PRESERVES hand-tuned zSubmit
values for any step that still exists (matched by step name + Enter_<field>).
The active file is archived to zVersions/tests/ before each overwrite (see
_archive_current_raven) so a regen is always reversible via --run --r N / --v.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from zSys import zpath  # zPath grammar — Layer-0 SSOT for sigil/segment decomposition

# ─────────────────────────────────────────────────────────────────────────────
# Field submit defaults
# ─────────────────────────────────────────────────────────────────────────────

_FIELD_DEFAULTS: Dict[str, str] = {
    # Generic fallbacks when no schema is available.
    # Unique-sensitive fields use a zraven_ prefix so cleanup is trivial.
    "email":    "zraven@test.local",
    "name":     "zRaven Test",
    "phone":    "555-0100",
    "company":  "Test Corp",
    "notes":    "zraven auto test",
    "status":   "lead",
    "query":    "test",
    "filename": "test.csv",
    "id":       "1",
    "title":    "Test Title",
    "message":  "test message",
    "slug":       "test-service",
    "category":   "general",
    "url":        "https://example.com",
    "key":        "test-key-001",
    "description":"zraven test description",
    "service_id": "1",
    "user_id":    "1",
    "contact_id": "1",
    "api_key_id": "1",
    "new_password": "newpassword123",
    "confirm_password": "newpassword123",
    # Use the seeded admin user for username-based flows (e.g. Forgot_Password)
    # Data isolation restores original password after each run.
    "username":     "admin",
    "reset_username": "admin",
}


def _field_default(field: str) -> str:
    return _FIELD_DEFAULTS.get(field.lower(), "test_" + field.lower())


# ─────────────────────────────────────────────────────────────────────────────
# Preserve hand-tuned zSubmit values across --gen runs
# ─────────────────────────────────────────────────────────────────────────────

def _parse_existing_submits(text: str) -> Dict[Tuple[str, str], str]:
    """Map (step_name, Enter_field) → preserved zSubmit value from an existing raven.

    Lets `z raven --gen` carry hand-tuned form inputs (valid enums, unique keys,
    real credentials) over a regeneration instead of resetting them to defaults.
    Coordinates are stable across regens because step names are deterministic.
    """
    preserved: Dict[Tuple[str, str], str] = {}
    cur_step: Optional[str] = None
    cur_enter: Optional[str] = None
    for line in text.splitlines():
        m_step = re.match(r'^ {4}(\w+):\s*$', line)
        if m_step:
            cur_step, cur_enter = m_step.group(1), None
            continue
        m_enter = re.match(r'^\s+(Enter_\w+):\s*$', line)
        if m_enter:
            cur_enter = m_enter.group(1)
            continue
        m_submit = re.match(r'^\s+zSubmit:\s*(.+?)\s*$', line)
        if m_submit and cur_step and cur_enter:
            preserved[(cur_step, cur_enter)] = m_submit.group(1)
    return preserved


def _apply_preserved_submits(
    text: str, preserved: Dict[Tuple[str, str], str]
) -> Tuple[str, int]:
    """Rewrite freshly generated zSubmit values with preserved ones. Returns (text, count)."""
    if not preserved:
        return text, 0
    out: List[str] = []
    cur_step: Optional[str] = None
    cur_enter: Optional[str] = None
    count = 0
    for line in text.splitlines():
        m_step = re.match(r'^ {4}(\w+):\s*$', line)
        if m_step:
            cur_step, cur_enter = m_step.group(1), None
            out.append(line)
            continue
        m_enter = re.match(r'^\s+(Enter_\w+):\s*$', line)
        if m_enter:
            cur_enter = m_enter.group(1)
            out.append(line)
            continue
        m_submit = re.match(r'^(\s+)zSubmit:\s*(.+?)\s*$', line)
        if m_submit and cur_step and cur_enter:
            key = (cur_step, cur_enter)
            if key in preserved and preserved[key] != m_submit.group(2):
                out.append(f"{m_submit.group(1)}zSubmit: {preserved[key]}")
                count += 1
                continue
        out.append(line)
    return "\n".join(out), count


# ─────────────────────────────────────────────────────────────────────────────
# Schema-aware field value resolver
# ─────────────────────────────────────────────────────────────────────────────

def _schema_defaults(fields: List[str], model_path: str, zos: Any) -> Dict[str, str]:
    """
    Load the linked zSchema and derive valid, schema-aware test values for each
    field in the dialog form.

    Rules:
      - `rules.allowed`  → use first allowed value
      - `unique: true`   → prefix value with "zraven_" so cleanup is trivial
                           and re-runs don't hit unique constraint errors
      - `rules.format: email` → "zraven@test.local"  (or "zraven_<field>@test.local")
      - `type: int`      → "1"
      - `type: bool`     → "true"
      - `required: false` → still generate a value (happy-path test)
      - `type: datetime` → skipped (auto-filled by `default: now`)
    Returns {} if schema cannot be loaded (falls back to _field_default).
    """
    if not zos or not model_path:
        return {}
    try:
        schema = zos.loader.handle(model_path)
        if not schema or not isinstance(schema, dict):
            return {}
        # schema has two keys: zMeta + table_name; find the table
        table_def: Dict[str, Any] = {}
        for k, v in schema.items():
            if k != "zMeta" and isinstance(v, dict):
                table_def = v
                break
        if not table_def:
            return {}

        result: Dict[str, str] = {}
        for field in fields:
            fdef = table_def.get(field, {})
            if not isinstance(fdef, dict):
                result[field] = _field_default(field)
                continue

            ftype   = fdef.get("type", "str")
            rules   = fdef.get("rules", {}) or {}
            unique  = fdef.get("unique", False)
            allowed = rules.get("allowed")
            fmt     = rules.get("format", "")
            min_len = rules.get("min_length", 1)

            # datetime — skip (default: now handles it)
            if ftype == "datetime":
                continue

            if ftype == "int":
                result[field] = "1"
            elif ftype == "bool":
                result[field] = "true"
            elif allowed:
                result[field] = str(allowed[0])
            elif fmt == "email" or "email" in field.lower():
                result[field] = "zraven@test.local" if not unique else "zraven@test.local"
            elif unique:
                # For unique string fields: use a predictable zraven_ prefix so
                # re-runs don't hit unique constraint errors.
                # Exception: if _FIELD_DEFAULTS has an explicit override (e.g. "username": "admin")
                # use it as-is — the override is intentional (existing-row lookup, not a create).
                explicit = _FIELD_DEFAULTS.get(field.lower())
                if explicit:
                    result[field] = explicit
                else:
                    base = _field_default(field)
                    result[field] = f"zraven_{base}" if not base.startswith("zraven") else base
            elif ftype == "str":
                base = _field_default(field)
                # Respect min_length
                if len(base) < min_len:
                    base = base + "_" + "x" * (min_len - len(base) - 1)
                result[field] = base
            else:
                result[field] = _field_default(field)

        return result
    except Exception:  # pylint: disable=broad-except
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_raven(
    spark_file: Path,
    target_version: Optional[str] = None,
    out_path: Optional[Path] = None,
    zos: Any = None,
    shots: Optional[List[str]] = None,
) -> Path:
    """
    Generate a zRaven test file from a zSpark + zUI definition.

    Parameters
    ----------
    spark_file : Path
        Path to the zSpark.*.zolo file.
    target_version : str, optional
        If given (e.g. 'v1.0.0'), loads the matching backup snapshot.
    out_path : Path, optional
        Override output path. Defaults to zRaven/<raven_name>.zolo.
    zos : Any
        Booted zOS instance. All zVaFile loading goes through
        zos.loader.handle_absolute_path() — the correct SSOT.
    shots : list[str], optional
        Viewports to screenshot (subset of mobile/tablet/desktop). When given,
        a zViewport + full-page zShot step pair is emitted per viewport after the
        page is ready, and the choice is stamped into the header (# zRavenShots:)
        so a later plain --gen keeps it. Empty/None → fall back to that header.
        zBifrost only — ignored (with a warning) for zCLI sparks.
    """
    workspace  = spark_file.parent
    spark      = _load_spark(spark_file)
    va_folder  = _resolve_at(spark.get("zVaFolder", "@.UI"), workspace)
    va_file    = spark.get("zVaFile", "")
    block_name = spark.get("zBlock", "")
    # Use spark file stem (matches runner's raven resolution logic in raven_command.py).
    # e.g. zSpark.zLogin.zolo → stem "zLogin" → zRaven.zLogin.zolo
    spark_stem = spark_file.stem.split(".", 1)[-1] if "." in spark_file.stem else spark_file.stem
    raven_name = spark.get("zRaven") or spark_stem

    # ── load root UI via zLoader ──────────────────────────────────────────────
    if target_version:
        ui_file_path, ui_parsed = _load_backup(workspace, va_folder, va_file,
                                               target_version, zos)
    else:
        ui_file_path = _find_ui_file(va_folder, va_file)
        ui_parsed    = _load_zvafile(ui_file_path, zos)

    ui_version = str(
        (ui_parsed.get("zMeta") or {}).get("zUIVersion", "v1.0.0")
    ).strip()

    root_block = ui_parsed.get(block_name, {}) or {}

    # ── generate ──────────────────────────────────────────────────────────────
    spark_mode = str(spark.get("zMode", "")).lower()
    is_bifrost = spark_mode not in ("zcli", "cli")
    wait_sel   = _root_class(root_block) or "body"

    # ── Screenshots: explicit flags win; else persist the previous choice from
    #    the active raven header (# zRavenShots:). zBifrost only.
    active_existing = workspace / "zRaven" / f"zRaven.{raven_name}.zolo"
    sticky_shots = (
        _parse_shot_header(active_existing.read_text(encoding="utf-8"))
        if active_existing.exists() else []
    )
    effective_shots = list(shots) if shots else sticky_shots
    if effective_shots and not is_bifrost:
        print("⚠️  Screenshots requested but spark is zCLI — skipping (zShot is zBifrost-only)")
        effective_shots = []

    lines: List[str] = []
    lines += _header_comment(ui_version, ui_file_path.name, effective_shots)
    # Single Tests: block — zCLI:/zBifrost: step-level keys route each step to
    # the correct runner. zMode in the active zSpark selects the path at runtime.
    # Shared steps (zAssert: contains:, zMarker:) run in both modes unchanged.
    lines += ["", "Tests:", ""]

    # Bifrost boot at the top so the page is ready for any browser interactions
    if is_bifrost:
        # zOpen: zSpark resolves the spark-default route at runtime — no URL/port here.
        lines += ["    # ── Bifrost: open page ──────────────────────────────────────────────"]
        lines += _bifrost_boot_steps(indent=1, wait_selector=wait_sel)
        # Screenshots of the entry page, one per requested viewport.
        if effective_shots:
            lines += _shot_steps(effective_shots, indent=1, wait_selector=wait_sel)

    _walk_block(root_block, lines, workspace, va_folder, zos, indent=1, top_level=True)

    # ── Bifrost-specific: zLogger assertions (inlined into Tests:) ──────────
    logger_steps = _collect_zlogger_steps(root_block, indent=1)
    if logger_steps:
        lines += ["", "    # ── Bifrost: zLogger assertions " + "─" * 37]
        lines += logger_steps

    lines += [""]
    lines += _step("Done", f"\n{'    ' * 2}zMarker: done", indent=1)

    # ── archive current raven before overwriting (default path only) ──────────
    raven_dir = workspace / "zRaven"
    raven_dir.mkdir(exist_ok=True)

    if out_path is None:
        out_path    = raven_dir / f"zRaven.{raven_name}.zolo"
        archived, r_ver, has_edits = _archive_current_raven(
            out_path, raven_name, ui_version, workspace
        )
        if archived:
            if has_edits:
                print(
                    f"⚠️  Active raven has manual edits — "
                    f"archived as r{r_ver} (previous auto-gen preserved)"
                )
            else:
                print(f"📦 Archived → zVersions/tests/zRaven.{raven_name}[{ui_version}]_r{r_ver}.zolo")

    final_text = "\n".join(lines)

    # ── Merge: preserve hand-tuned zSubmit values from the previous raven ─────
    # Structure is regenerated fresh, but form inputs the user tuned (valid enum
    # values, unique keys, real credentials) are carried over for any step that
    # still exists. New steps fall back to schema/placeholder defaults.
    if out_path.exists():
        try:
            preserved = _parse_existing_submits(out_path.read_text(encoding="utf-8"))
            final_text, n_kept = _apply_preserved_submits(final_text, preserved)
            if n_kept:
                print(f"🔁 Preserved {n_kept} tuned zSubmit value(s) from previous raven")
        except Exception:  # pylint: disable=broad-except
            pass

    out_path.write_text(final_text + "\n", encoding="utf-8")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Block walker
# ─────────────────────────────────────────────────────────────────────────────

def _walk_block(
    block: Dict[str, Any],
    lines: List[str],
    workspace: Path,
    va_folder: Path,
    zos: Any,
    indent: int,
    top_level: bool = False,
    panel_name: Optional[str] = None,
) -> None:
    if not isinstance(block, dict):
        return

    # Collect items already covered by ~Menu lists so submenus don't double-emit
    menu_items: set = set()
    has_nav = False
    for key, value in block.items():
        if _is_menu_key(key) and isinstance(value, list):
            has_nav = True
            for item in value:
                menu_items.add(item)

    for key, value in block.items():

        # zDash ────────────────────────────────────────────────────────────────
        if key == "zDash" and isinstance(value, dict):
            _gen_zdash(value, lines, workspace, zos, indent)

        # Nav*: [items] — navigation menu (with or without tilde anchor prefix)
        # Skip if this key's base label is already an item in a parent nav (sub-menu).
        elif _is_menu_key(key) and isinstance(value, list):
            base_label = key.lstrip("#~").rstrip("*")
            if base_label not in menu_items:
                _gen_menu(key, value, block, lines, workspace, va_folder,
                          zos, indent, top_level, menu_items, panel_name=panel_name)

        # Direct gate actions (^Action) with NO navigation wrapper ────────────
        # These auto-execute when the panel renders (no menu pick step needed).
        elif key.startswith("^") and top_level and not has_nav:
            action_name = key[1:]
            step_prefix = f"{_slug(panel_name)}_" if panel_name else ""
            _gen_action(action_name, value, lines, indent, step_prefix=step_prefix, zos=zos)

        # skip private / gate keys
        # NOTE: the old `!` suffix gate was retired 2026-06 (docs 14/15) — `key!`
        # is now just a literal key name, so it recurses like any other container.
        elif key.startswith("_") or key.startswith("^"):
            continue

        # Structural container — recurse to find nested menus/actions
        elif isinstance(value, dict):
            _walk_block(value, lines, workspace, va_folder, zos,
                        indent=indent, top_level=top_level, panel_name=panel_name)


def _gen_zdash(
    dash: Dict[str, Any],
    lines: List[str],
    workspace: Path,
    zos: Any,
    indent: int,
) -> None:
    sidebar   = dash.get("sidebar", [])
    default   = dash.get("default", sidebar[0] if sidebar else "")
    folder    = dash.get("folder", "")
    panel_dir = _resolve_at(folder, workspace) if folder else workspace / "UI"

    if not sidebar:
        return

    lines.append("")
    lines.append("    " * indent + "# ── Dashboard panels " + "─" * 50)
    # Default panel renders at boot. First navigation step acts as boot confirmation.

    # Default panel is auto-shown at boot — omit its Dash_Pick step.
    # Non-default panels need an explicit Dash_Pick to navigate there.
    for panel in sidebar:
        lines.append("")
        is_default = panel == default

        if not is_default:
            lines += _step(f"Dash_Pick_{_slug(panel)}", _zpick(panel, indent), indent=indent)

        # Recurse into panel's own menus.
        # top_level=True: zDash panel actions auto-return — no Back_From_X steps needed.
        # panel_name: passed so launcher items can re-navigate back into the panel.
        panel_parsed = _load_panel(panel_dir, panel, zos)
        panel_block: Dict[str, Any] = {}
        if panel_parsed:
            panel_block = panel_parsed.get(panel, {}) or {}

            if not is_default:
                # Use the panel's H2/H1 label for the assert so it matches actual rendered output.
                assert_text = _panel_heading(panel_block) or panel
                lines += _step(f"Assert_{_slug(panel)}", _zassert(assert_text, indent), indent=indent)

            _walk_block(panel_block, lines, workspace, panel_dir,
                        zos, indent=indent, top_level=True, panel_name=panel)

        # All nav menus (Name*) keep the terminal loop inside the panel until
        # the user picks zBack.  Add a zBack step before the next Dash_Pick.
        has_inner_nav = any(
            _is_menu_key(k) and isinstance(v, list)
            for k, v in panel_block.items()
        )
        if has_inner_nav:
            lines.append("")
            lines += _step(f"zBack_From_{_slug(panel)}", _zpick("zBack", indent), indent=indent)


def _gen_menu(
    key: str,
    items: List[str],
    block: Dict[str, Any],
    lines: List[str],
    workspace: Path,
    va_folder: Path,
    zos: Any,
    indent: int,
    top_level: bool,
    menu_items: set,
    panel_name: Optional[str] = None,
) -> None:
    label = re.sub(r"^[#~]+|[*]+$", "", key).strip("_")
    lines.append("")
    lines.append("    " * indent + f"# ── {label} " + "─" * max(0, 50 - len(label)))

    # Prefix step names with panel name to avoid duplicate keys across panels
    step_prefix = f"{_slug(panel_name)}_" if panel_name else ""

    for item in items:
        action     = block.get(f"^{item}")
        submenu_key = f"{item}*"
        has_submenu = submenu_key in block and isinstance(block[submenu_key], list)

        lines.append("")
        lines += _step(f"Pick_{step_prefix}{_slug(item)}", _zpick(item, indent), indent=indent)

        if has_submenu:
            if not top_level:
                # Navigable sub-menu (non-zDash): generate pick steps for sub-items
                _gen_submenu(submenu_key, block[submenu_key], block, lines, indent,
                             step_prefix=step_prefix)
            else:
                # zDash context — X* is a launcher that auto-executes; just picked.
                # After the launcher, the app returns to the Dashboard Menu.
                # Re-navigate back into the panel so subsequent items are reachable.
                if panel_name:
                    lines += _step(
                        f"Dash_Pick_{_slug(panel_name)}_After_{_slug(item)}",
                        _zpick(panel_name, indent), indent=indent,
                    )
        elif isinstance(action, dict):
            action_needs_back = _gen_action(item, action, lines, indent, step_prefix=step_prefix, zos=zos)
        else:
            action_needs_back = False

        if not top_level and not has_submenu:
            lines += _step(f"Back_From_{step_prefix}{_slug(item)}", _zpick("zBack", indent), indent=indent)
        elif top_level and not has_submenu and action_needs_back:
            # Action ended with zDelta — app is in sub-panel; press zBack to return.
            lines += _step(f"Back_From_{step_prefix}{_slug(item)}_Delta", _zpick("zBack", indent), indent=indent)


def _gen_submenu(
    key: str,
    items: List[str],
    block: Dict[str, Any],
    lines: List[str],
    indent: int,
    step_prefix: str = "",
) -> None:
    label = key.rstrip("*")
    lines.append("")
    lines.append("    " * indent + f"# ── {label} sub-menu " + "─" * max(0, 40 - len(label)))

    for item in items:
        action = block.get(f"^{item}")
        lines.append("")
        lines += _step(f"Pick_{step_prefix}{_slug(item)}", _zpick(item, indent), indent=indent)
        if isinstance(action, dict):
            _gen_action(item, action, lines, indent, step_prefix=step_prefix)

    lines += _step(f"Back_From_{step_prefix}{_slug(label)}_Sub", _zpick("zBack", indent), indent=indent)


def _wizard_has_zdelta(wizard: Dict[str, Any]) -> bool:
    """Return True if any wizard step contains zDelta (navigates away from current panel)."""
    if not isinstance(wizard, dict):
        return False
    return any(
        isinstance(step_val, dict) and "zDelta" in step_val
        for step_val in wizard.values()
    )


def _gen_action(name: str, action: Dict[str, Any], lines: List[str], indent: int,
                step_prefix: str = "", zos: Any = None) -> bool:
    """Generate test steps for an action.  Returns True when the action ends with
    zDelta (navigates to a sub-panel) so the caller can add a Back step."""
    if "zDialog" in action:
        dialog = action["zDialog"]
        if isinstance(dialog, dict):
            model_path = dialog.get("model") or action.get("model") or ""
            _gen_dialog_wizard(
                name, dialog.get("fields", []), lines, indent,
                step_prefix=step_prefix, model_path=str(model_path), zos=zos,
            )
        return False

    if "zWizard" in action:
        has_delta = _wizard_has_zdelta(action["zWizard"])
        _gen_wizard(name, action["zWizard"], lines, indent, step_prefix=step_prefix)
        return has_delta

    if "zData" in action:
        zdata = action["zData"]
        if isinstance(zdata, dict):
            cols     = zdata.get("columns", [])
            group_by = zdata.get("group_by")
            has_where = bool(zdata.get("where"))
            if has_where and not group_by:
                # Filtered query may return 0 rows; assert no error instead of column presence
                assert_block = f"zAssert:\n{'    ' * (indent + 2)}success: true"
                lines += _step(f"Assert_{step_prefix}{_slug(name)}", assert_block, indent=indent)
            elif cols:
                label = cols[0]
                lines += _step(f"Assert_{step_prefix}{_slug(name)}", _zassert(str(label), indent), indent=indent)
            elif group_by:
                # Aggregate action — output shows GROUP BY column values
                label = str(group_by).split(".")[-1]
                lines += _step(f"Assert_{step_prefix}{_slug(name)}", _zassert(str(label), indent), indent=indent)
            else:
                label = str(zdata.get("model", "")).split(".")[-1]
                lines += _step(f"Assert_{step_prefix}{_slug(name)}", _zassert(str(label), indent), indent=indent)
        return False

    if "zExport" in action:
        lines += _step(f"Assert_{step_prefix}{_slug(name)}", _zassert(".csv", indent), indent=indent)
    if "zImport" in action:
        lines += _step(f"Assert_{step_prefix}{_slug(name)}", _zassert("row", indent), indent=indent)
    return False


def _gen_dialog_wizard(name: str, fields: List[str], lines: List[str], indent: int,
                       step_prefix: str = "", model_path: str = "", zos: Any = None) -> None:
    p0 = "    " * indent          # step level
    p1 = "    " * (indent + 1)    # zCLI:
    p2 = "    " * (indent + 2)    # zWizard:
    p3 = "    " * (indent + 3)    # Enter_field:
    p4 = "    " * (indent + 4)    # zAssert: / zSubmit:

    schema_vals = _schema_defaults(fields, model_path, zos)

    body = [f"{p0}Fill_{step_prefix}{_slug(name)}_Form:", f"{p1}zCLI:", f"{p2}zWizard:"]
    for field in fields:
        submit_val = schema_vals.get(field) or _field_default(field)
        body += [
            f"{p3}Enter_{_slug(field)}:",
            f"{p4}zAssert:",
            f"{p4}    contains: {field}",
            f"{p4}zSubmit: {submit_val}",
        ]
    lines += body


def _gen_wizard(name: str, wizard: Dict[str, Any], lines: List[str], indent: int,
                step_prefix: str = "") -> None:
    if not isinstance(wizard, dict):
        return
    p0 = "    " * indent
    p1 = "    " * (indent + 1)   # zCLI:
    p2 = "    " * (indent + 2)   # zWizard:
    p3 = "    " * (indent + 3)   # step key
    p4 = "    " * (indent + 4)   # zAssert: / zSubmit:
    body = [f"{p0}Fill_{step_prefix}{_slug(name)}_Wizard:", f"{p1}zCLI:", f"{p2}zWizard:"]
    user_steps: List[str] = []
    for step_key, step_val in wizard.items():
        if not isinstance(step_val, dict):
            continue
        if "zBtn" in step_val:
            btn_label = step_val["zBtn"].get("label", step_key)
            user_steps += [
                f"{p3}{step_key}:",
                f"{p4}zAssert:",
                f"{p4}    contains: {str(btn_label)[:60]}",
                f"{p4}zSubmit: y",
            ]
        elif "zDialog" in step_val:
            for field in ((step_val["zDialog"] or {}).get("fields", [])):
                user_steps += [
                    f"{p3}Enter_{_slug(field)}:",
                    f"{p4}zAssert:",
                    f"{p4}    contains: {field}",
                    f"{p4}zSubmit: {_field_default(field)}",
                ]
    if user_steps:
        lines += body + user_steps


# ─────────────────────────────────────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────────────────────────────────────

def _root_class(block: Dict[str, Any]) -> str:
    """Return the first _zClass value found in the block (for Bifrost zWait)."""
    if not isinstance(block, dict):
        return ""
    cls = block.get("_zClass", "")
    if isinstance(cls, str) and cls:
        return "." + cls.split()[0]
    for v in block.values():
        found = _root_class(v)
        if found:
            return found
    return ""


def _bifrost_boot_steps(indent: int, wait_selector: str) -> List[str]:
    """Emit zOpen (zSpark) + zWait steps for Bifrost before any browser interactions.

    zOpen: zSpark resolves the live server URL at runtime (SSOT) — NEVER hardcode a
    port here. zRaven binds dedicated test ports (live app port + offset), so a
    hardcoded http://127.0.0.1:<port> would point at the wrong port and fail with
    net::ERR_CONNECTION_REFUSED.
    """
    p0 = "    " * indent
    p1 = "    " * (indent + 1)   # zBifrost:
    p2 = "    " * (indent + 2)   # zOpen: / zWait:
    p3 = "    " * (indent + 3)   # selector:
    return [
        f"{p0}Open_App:",
        f"{p1}zBifrost:",
        f"{p2}zOpen: zSpark",
        f"{p0}Wait_Ready:",
        f"{p1}zBifrost:",
        f"{p2}zWait:",
        f"{p3}selector: {wait_selector}",
        f"{p3}state: visible",
        f"{p3}timeout: 8000",
        "",
    ]


def _header_comment(version: str, filename: str,
                    shots: Optional[List[str]] = None) -> List[str]:
    out = [
        f"# zRavenVersion: {version}",
        f"# Generated by:  z raven --gen",
        f"# Source:        {filename}",
        "# Re-run z raven --gen to regenerate structural tests.",
        "# Hand-tuned zSubmit values are preserved across --gen for steps that still exist.",
        "# The previous version is archived to zVersions/tests/ (replay: z raven --run --r N).",
    ]
    if shots:
        # Sticky: plain --gen re-reads this and keeps the screenshot viewports.
        out.append(f"# zRavenShots: {','.join(shots)}")
    return out


def _parse_shot_header(text: str) -> List[str]:
    """Extract the screenshot viewports stamped in a raven's `# zRavenShots:` header."""
    for line in text.splitlines()[:12]:
        m = re.match(r"#\s*zRavenShots:\s*(.+)", line)
        if m:
            return [s.strip() for s in m.group(1).split(",") if s.strip()]
    return []


def _shot_steps(shots: List[str], indent: int, wait_selector: str) -> List[str]:
    """Emit viewport → re-open → wait → full-page zShot per viewport (zBifrost).

    The re-open is essential: the bifrost client renders content for the viewport
    it loaded at, so a post-load resize does NOT re-render — the page goes blank
    and the wait on the root selector times out. Setting the viewport and then
    re-opening (zOpen: zSpark) renders fresh at that size, matching how a real
    mobile browser loads. Proven by the zNest/zPricing multi-viewport ravens.

    Shots route to zRaven/zShots/<name>/<viewport>/<step>.png automatically. A
    trailing reset to desktop restores the default viewport for any later steps
    when the last requested shot wasn't desktop.
    """
    p0 = "    " * indent
    p1 = "    " * (indent + 1)   # zBifrost:
    p2 = "    " * (indent + 2)   # zViewport: / zOpen: / zWait: / zShot:
    p3 = "    " * (indent + 3)   # selector: / full_page:
    out: List[str] = []
    for vp in shots:
        out.append("")
        out.append(f"{p0}# ── Screenshot: {vp} " + "─" * max(0, 45 - len(vp)))
        out.append(f"{p0}Shot_{vp}_viewport:")
        out.append(f"{p1}zBifrost:")
        out.append(f"{p2}zViewport: {vp}")
        out.append(f"{p0}Shot_{vp}_open:")
        out.append(f"{p1}zBifrost:")
        out.append(f"{p2}zOpen: zSpark")
        out.append(f"{p0}Shot_{vp}_ready:")
        out.append(f"{p1}zBifrost:")
        out.append(f"{p2}zWait:")
        out.append(f"{p3}selector: {wait_selector}")
        out.append(f"{p3}state: visible")
        out.append(f"{p3}timeout: 8000")
        out.append(f"{p0}Shot_{vp}:")
        out.append(f"{p1}zBifrost:")
        out.append(f"{p2}zShot:")
        out.append(f"{p3}full_page: true")
    if shots and shots[-1] != "desktop":
        out.append("")
        out.append(f"{p0}Reset_Viewport_Desktop:")
        out.append(f"{p1}zBifrost:")
        out.append(f"{p2}zViewport: desktop")
    return out


def _step(name: str, body: str, indent: int) -> List[str]:
    return [f"{'    ' * indent}{name}:{body}"]


def _zassert(text: str, indent: int = 1) -> str:
    pad = "    " * (indent + 1)
    return f"\n{pad}zAssert:\n{pad}    contains: {text}"


def _zpick(item: str, indent: int = 1) -> str:
    p1 = "    " * (indent + 1)   # zCLI:
    p2 = "    " * (indent + 2)   # zMenu:
    p3 = "    " * (indent + 3)   # zPick:
    return f"\n{p1}zCLI:\n{p2}zMenu:\n{p3}zPick: {item}"


# ─────────────────────────────────────────────────────────────────────────────
# File loading — all zVaFiles go through zos.loader, zSpark via regex
# ─────────────────────────────────────────────────────────────────────────────

def _load_zvafile(file_path: Path, zos: Any) -> Dict[str, Any]:
    """
    Load a zVaFile (.zolo). With a live zOS, go through
    zos.loader.handle_absolute_path() — the SSOT (@. paths, string-first,
    all zOS extensions). Without one (standalone CLI), fall back to the
    SAME canonical zlsp parser zLoader/zParser wrap — never a hand-rolled
    yaml bridge, which would silently diverge from real parse semantics.
    """
    if zos is not None:
        return zos.loader.handle_absolute_path(str(file_path)) or {}

    try:
        from zlsp import parser as zolo  # pylint: disable=import-outside-toplevel
        return zolo.loads(file_path.read_text(encoding="utf-8"),
                          filename=str(file_path)) or {}
    except Exception as e:
        raise RuntimeError(f"Failed to parse {file_path}: {e}") from e


def _load_spark(spark_file: Path) -> Dict[str, Any]:
    """
    Load zSpark config via the canonical zlsp parser (grammar SSOT).

    Returns the ``zSpark`` block so sibling top-level blocks (zInfo, etc.) and
    nested config (zServer) never leak into the config dict. Falls back to a
    shallow regex scan only when zlsp is unavailable or the file has no
    ``zSpark`` block (keeps standalone/degraded generation working).
    """
    text = spark_file.read_text(encoding="utf-8")
    try:
        from zlsp import parser as _zolo  # pylint: disable=import-outside-toplevel
        parsed = _zolo.loads(text, filename=str(spark_file)) or {}
        spark = parsed.get("zSpark")
        if isinstance(spark, dict):
            return spark
    except Exception:  # pylint: disable=broad-except
        pass

    # Fallback: shallow regex (zlsp missing / non-standard file).
    # Match:  key: value  (strip inline comments and quotes)
    result: Dict[str, Any] = {}
    for m in re.finditer(r'^\s{4}(\w+):\s*([^#\n]+)', text, re.MULTILINE):
        key = m.group(1).strip()
        val = m.group(2).strip().strip('"').strip("'")
        if val.lower() in ("true", "yes"):
            result[key] = True
        elif val.lower() in ("false", "no"):
            result[key] = False
        else:
            result[key] = val
    return result


def _load_backup(
    workspace: Path,
    va_folder: Path,
    va_file: str,
    version: str,
    zos: Any,
) -> Tuple[Path, Dict[str, Any]]:
    ver_dir = workspace / "zVersions" / "interface"
    backup  = ver_dir / f"{va_file}.{version}.backup.zolo"
    if not backup.exists():
        raise FileNotFoundError(f"No backup for {va_file} @ {version}: {backup}")
    return backup, _load_zvafile(backup, zos)


def _find_ui_file(va_folder: Path, va_file: str) -> Path:
    for ext in (".zolo", ".yaml", ".yml"):
        c = va_folder / f"{va_file}{ext}"
        if c.exists():
            return c
    raise FileNotFoundError(f"UI file not found: {va_folder / va_file}")


def _load_panel(panel_dir: Path, panel_name: str, zos: Any) -> Optional[Dict[str, Any]]:
    for ext in (".zolo", ".yaml"):
        c = panel_dir / f"zUI.{panel_name}{ext}"
        if c.exists():
            try:
                return _load_zvafile(c, zos)
            except Exception:
                return None
    return None


def _panel_label(panel_dir: Path, panel_name: str, zos: Any) -> Optional[str]:
    parsed = _load_panel(panel_dir, panel_name, zos)
    if not parsed:
        return None
    block = parsed.get(panel_name, {}) or {}
    if not isinstance(block, dict):
        return None
    zh2 = block.get("zH2", {})
    return zh2.get("label") if isinstance(zh2, dict) else None


def _collect_zlogger_steps(block: Dict[str, Any], indent: int = 1) -> List[str]:
    """Scan a UI block (recursively) for ^Button entries with zLogger and emit zBifrost: steps.

    Emits per button:
        Click_<name>:
            zBifrost:
                zClick: <name>
        Assert_Log_<name>:
            zBifrost:
                zLogger: <message>
    """
    lines: List[str] = []
    p0 = "    " * indent
    p1 = "    " * (indent + 1)   # zBifrost:
    p2 = "    " * (indent + 2)   # zClick: / zLogger:
    for key, value in block.items():
        if not isinstance(value, dict):
            continue
        if key.startswith("^"):
            logger_cfg = value.get("zLogger")
            if not logger_cfg:
                continue
            btn_name = key.lstrip("^")
            slug     = _slug(btn_name)
            lines.append(f"{p0}Click_{slug}:")
            lines.append(f"{p1}zBifrost:")
            lines.append(f"{p2}zClick:")
            lines.append(f"{p2}    selector: \"[data-key='{btn_name}']\"")

            lines.append(f"{p0}Assert_Log_{slug}:")
            lines.append(f"{p1}zBifrost:")
            if isinstance(logger_cfg, str):
                lines.append(f"{p2}zLogger: {logger_cfg}")
            elif isinstance(logger_cfg, dict):
                msg   = logger_cfg.get("message", "")
                level = logger_cfg.get("level", "")
                lines.append(f"{p2}zLogger:")
                lines.append(f"{p2}    message: {msg}")
                if level:
                    lines.append(f"{p2}    level: {level}")
            lines.append("")
        elif not key.startswith("_"):
            # Structural container — recurse
            lines += _collect_zlogger_steps(value, indent=indent)
    return lines


def _derive_raven_name_from_spark(spark: dict, va_file: str) -> str:
    """
    Derive raven file name from spark config when zRaven key is absent.
    Both zCLI and zBifrost sparks default to the same stem so they share
    one unified zRaven file (mode dispatch is at the step level via zCLI:/zBifrost: keys).
    """
    return va_file.replace("zUI.", "").replace("zUI_", "")


def _resolve_at(path_str: str, workspace: Path) -> Path:
    if path_str.startswith(zpath.SIGIL_WORKSPACE):
        return workspace.joinpath(*zpath.split(path_str).segments)
    return workspace / path_str


def _is_menu_key(key: str) -> bool:
    """
    Navigation menu keys end with * and have a list value.
    Supports both anchor (~Name*) and back-enabled (Name*) forms.
    Plain tilde without asterisk (~Name) is NOT a menu key in zOS dispatch.
    """
    k = key.lstrip("#")
    return k.endswith("*")


def _panel_heading(panel_block: dict) -> str:
    """Return the first zH2 or zH1 label from a panel block for use in assertions."""
    for h_key in ("zH2", "zH1"):
        h = panel_block.get(h_key)
        if isinstance(h, dict):
            label = h.get("label", "")
            if label:
                return str(label)
        elif isinstance(h, str) and h:
            return h
    return ""


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")


# ─────────────────────────────────────────────────────────────────────────────
# Archive helpers — versioned storage for raven files
# ─────────────────────────────────────────────────────────────────────────────

def _archive_current_raven(
    active_path: Path,
    raven_name: str,
    ui_version: str,
    workspace: Path,
) -> Tuple[Optional[Path], int, bool]:
    """
    Archive the active raven file as a versioned snapshot before overwriting.

    Naming:  {workspace}/zVersions/tests/zRaven.{name}[{ui_ver}]_r{N}.zolo
             (kept in sync with raven_command._resolve_raven_target for --run --r N)

    Returns
    -------
    (archived_path, raven_version, has_manual_edits)
        archived_path    : Path of the new archive, or None if nothing to archive
        raven_version    : the rN number used for the archive
        has_manual_edits : True if active file differs from the previous archive
    """
    if not active_path.exists():
        return None, 0, False

    ver_dir = workspace / "zVersions" / "tests"
    ver_dir.mkdir(parents=True, exist_ok=True)

    # Find highest existing raven version for this (name, ui_version) pair.
    # Use iterdir() + startswith — avoids glob treating [v2.0.0] as a char class.
    prefix   = f"zRaven.{raven_name}[{ui_version}]_r"
    existing = sorted(
        p for p in ver_dir.iterdir()
        if p.name.startswith(prefix) and p.name.endswith(".zolo")
    )
    next_r    = 1
    last_path: Optional[Path] = None

    if existing:
        nums = []
        for p in existing:
            m = re.search(r'_r(\d+)\.zolo$', p.name)
            if m:
                nums.append((int(m.group(1)), p))
        if nums:
            _, last_path = max(nums, key=lambda x: x[0])
            next_r = max(n for n, _ in nums) + 1

    # Drift: does the active file differ from the last archive?
    has_manual_edits = False
    if last_path and last_path.exists():
        has_manual_edits = (
            active_path.read_text(encoding="utf-8")
            != last_path.read_text(encoding="utf-8")
        )

    archived = ver_dir / f"zRaven.{raven_name}[{ui_version}]_r{next_r}.zolo"
    archived.write_text(active_path.read_text(encoding="utf-8"), encoding="utf-8")
    return archived, next_r, has_manual_edits


def archive_raven(
    raven_name: str,
    ui_version: str,
    workspace: Path,
) -> Tuple[Optional[Path], int, bool]:
    """Public convenience wrapper used by raven_command --gen."""
    active = workspace / "zRaven" / f"zRaven.{raven_name}.zolo"
    return _archive_current_raven(active, raven_name, ui_version, workspace)


# ─────────────────────────────────────────────────────────────────────────────
__all__ = ["generate_raven", "archive_raven"]
