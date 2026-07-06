# zShell Internals Module Guide

> **Modules:** `shell_modules/shell_paths.py`, `command_helpers.py`, `executor_constants.py`, `zshell_constants.py`  
> **Purpose:** The shared helpers and constants that keep the command executors DRY and single-sourced — zPath resolution, argument unpacking, fail-closed subsystem checks, and the canonical key/color/type vocabularies.

---

## Overview

These modules carry no command behavior of their own; they exist so every command
executor resolves paths, reads parsed keys, and styles output **the same way**.
Consolidating them removed duplicated logic and literal drift across the command set.

---

## shell_paths.py — zPath SSOT

Single source for zPath resolution and formatting, used by `cd`/`ls`/`where`/
`session` and the runner's zPath prompt.

| Function | Purpose |
|----------|---------|
| `resolve_zpath_symbol(...)` | Resolve a zPath symbol (`@.`/`~`) to a value |
| `resolve_nav_path(...)` | Resolve a navigation target for `cd`/`ls` |
| `format_zpath(...)` | Format a path for display (prompt / `pwd`) |

Before consolidation each of those commands carried its own near-identical
resolver/formatter; they now delegate here.

---

## command_helpers.py — executor boilerplate

| Helper | Purpose |
|--------|---------|
| `get_command_parts(parsed, *, action_default=None)` | Unpack `(action, args, options)` from a parsed command |
| `require_subsystem(zos, attr, error_msg=None)` | **Fail-closed** check that `zos.<attr>` exists; displays the error and returns `False` if not |

```python
action, args, options = get_command_parts(parsed)
if not require_subsystem(zos, "config", ERROR_NO_ZCONFIG):
    return None
```

Adopted by `config`/`auth`/`comm` (and the pattern is available to all executors).

---

## executor_constants.py — keys & types

The canonical vocabulary shared by the router and the executors:

- **Parsed-command keys:** `KEY_ACTION`, `KEY_ARGS`, `KEY_OPTIONS` (SSOT — command
  modules alias these instead of redefining `"action"`/`"args"`/`"options"`).
- **Command types:** `CMD_TYPE_DATA`, `CMD_TYPE_CONFIG`, `CMD_TYPE_COMM`, … used by
  the command map and the seal-policy.
- **Router keys:** `KEY_TYPE`, `KEY_ERROR`.

Single-sourcing these is what lets `shell_policy` key its seal map on the same
type/action strings the executors use.

---

## zshell_constants.py — colors & styles

Shared display vocabulary (`COLOR_INFO`/`COLOR_ERROR`/`COLOR_SUCCESS`, `STYLE_FULL`/
`STYLE_NONE`/`STYLE_SINGLE`, prompts, messages). Executors import these instead of
hardcoding `"INFO"`/`"full"` literals, so styling stays consistent and changeable
in one place. (Palette-based color definitions that affect rendered output are kept
local where remapping would change the result.)

---

## See Also

- [executor_GUIDE.md](executor_GUIDE.md) — consumer of the keys/types
- [commands_GUIDE.md](commands_GUIDE.md) — consumer of the helpers/constants
- [security_GUIDE.md](security_GUIDE.md) — `shell_policy` keys on `executor_constants`
- [runner_GUIDE.md](runner_GUIDE.md) — uses `format_zpath` for the prompt

---

**[← Back to zShell Guide](../zShell_GUIDE.md)**
