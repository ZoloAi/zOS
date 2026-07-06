# zOS/core/L3_Abstraction/p_zShell/shell_modules/shell_paths.py

"""
Shell zPath SSOT — one resolver + one formatter for the whole zShell subsystem.

Why this is shell-local (and NOT delegated to k_zOpen.resolve_zpath):
    zOpen's resolver is a *file* contract — `~` means filesystem root, the last
    two dot-parts must be name+extension, and it returns None on a miss. The
    shell needs *navigation* semantics instead: `~` = home, directories (no
    extension), plus `~zMachine`/`..`/`.` and relative-to-cwd. The two contracts
    are intentionally distinct (see open_paths.py SSOT note), so the shell owns
    its own resolver — but only ONE copy of it, here.

Callers:
    - shell_cmd_cd.py     → resolve_nav_path (full) + format_zpath(None)
    - shell_cmd_ls.py     → resolve_nav_path (full)
    - shell_cmd_session   → resolve_zpath_symbol (prefix-only, pass-through)
    - shell_cmd_where.py  → format_zpath(fallback_absolute=True)
    - shell_runner.py     → format_zpath(fallback_absolute=True)
"""

from zOS import os, Path, Any, Optional
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_ZSPACE

# ── zPath symbols ────────────────────────────────────────────────────────────
ZPATH_WORKSPACE_PREFIX = "@."
ZPATH_HOME_PREFIX = "~."
ZPATH_HOME = "~"
ZPATH_PARENT = ".."
ZPATH_CURRENT = "."
ZPATH_SEPARATOR = "."
ZMACHINE_PREFIX_LONG = "~zMachine"
ZMACHINE_PREFIX_SHORT = "zMachine"


def resolve_zpath_symbol(zos: Any, target: str) -> Optional[Path]:
    """
    Resolve a zSymbol-prefixed path to an absolute Path, or None if `target`
    carries no recognized zPath symbol (the caller decides the fallback).

    Recognized symbols:
        @.a.b        → {zSpace}/a/b           (workspace-relative)
        ~zMachine    → user_data_dir          (alias: zMachine)
        ~zMachine.a  → user_data_dir/a
        ~.a.b        → ~/a/b                   (home-relative)
        ~            → home directory
    """
    # Workspace-relative (@.)
    if target.startswith(ZPATH_WORKSPACE_PREFIX):
        workspace_root = Path(zos.session.get(SESSION_KEY_ZSPACE, ZPATH_CURRENT))
        path_parts = target[len(ZPATH_WORKSPACE_PREFIX):].split(ZPATH_SEPARATOR)
        return (workspace_root / "/".join(path_parts)).resolve()

    # zMachine user-data paths (~zMachine.* or zMachine.*)
    if target.startswith(ZMACHINE_PREFIX_LONG) or target.startswith(ZMACHINE_PREFIX_SHORT):
        user_data_dir = zos.config.sys_paths.user_data_dir
        if target.startswith(ZMACHINE_PREFIX_LONG):
            remainder = target[len(ZMACHINE_PREFIX_LONG):]
        else:
            remainder = target[len(ZMACHINE_PREFIX_SHORT):]
        if not remainder or remainder == ZPATH_CURRENT:
            return Path(user_data_dir).resolve()
        if remainder.startswith(ZPATH_SEPARATOR):
            path_parts = remainder[1:].split(ZPATH_SEPARATOR)
            return (Path(user_data_dir) / "/".join(path_parts)).resolve()
        # Invalid format (no dot after zMachine) — not a clean symbol
        return None

    # Home-relative (~.)
    if target.startswith(ZPATH_HOME_PREFIX):
        path_parts = target[len(ZPATH_HOME_PREFIX):].split(ZPATH_SEPARATOR)
        return (Path.home() / "/".join(path_parts)).resolve()

    # Home directory shortcut (~)
    if target == ZPATH_HOME:
        return Path.home().resolve()

    return None


def resolve_nav_path(zos: Any, target: str) -> Path:
    """
    Full shell navigation resolver (cd / ls). Resolves zPath symbols, then
    `..` / `.` / absolute / relative-to-cwd. Always returns an absolute Path
    (not validated to exist). Raises on malformed input.
    """
    symbol = resolve_zpath_symbol(zos, target)
    if symbol is not None:
        return symbol

    current_dir = Path(os.getcwd())
    if target == ZPATH_PARENT:
        return current_dir.parent.resolve()
    if target == ZPATH_CURRENT:
        return current_dir.resolve()
    resolved = Path(target) if Path(target).is_absolute() else current_dir / target
    return resolved.resolve()


def format_zpath(path: Optional[Path] = None, *, fallback_absolute: bool = False) -> Optional[str]:
    """
    Format an absolute path as zPath display notation.

    Under home:   /Users/me            → "~"
                  /Users/me/Proj/app   → "~.Proj.app"
    Outside home: absolute string if `fallback_absolute` else None.

    `path` defaults to the current OS working directory.
    """
    try:
        target = (path if path is not None else Path(os.getcwd())).resolve()
        home = Path.home()
        if target.is_relative_to(home):
            relative = target.relative_to(home)
            if relative == Path(ZPATH_CURRENT):
                return ZPATH_HOME
            return ZPATH_HOME_PREFIX + ZPATH_SEPARATOR.join(relative.parts)
        return str(target) if fallback_absolute else None
    except (ValueError, AttributeError, OSError):
        return None
