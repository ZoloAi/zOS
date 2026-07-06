# zShell Commands Module Guide

> **Module:** `zOS/core/L3_Abstraction/o_zShell/shell_modules/commands/`  
> **Purpose:** One thin executor per shell command — adapters that translate a parsed command into a subsystem call and render the result through zDisplay.

---

## Overview

Each command is a small module (`shell_cmd_<name>.py`) exposing an
`execute_<name>(zos, parsed)` function. The executors are **UI adapters**: they
validate input, call the relevant subsystem, and return `None` (output goes
through zDisplay) — keeping the same command correct in terminal and Bifrost modes.

Shared boilerplate is factored into helpers (see
[internals_GUIDE.md](internals_GUIDE.md)): `get_command_parts()` unpacks
`action`/`args`/`options`, and `require_subsystem()` is the fail-closed
availability check.

---

## Command catalogue

### Navigation

| Command | Module | Notes |
|---------|--------|-------|
| `where` | `shell_cmd_where.py` | Toggle/show zPath in the prompt |
| `cd` | `shell_cmd_cd.py` | Change dir (zPath / `~` / `..` / absolute) |
| `pwd` / `cwd` | `shell_cmd_cd.py` | Print working directory (OS + zPath) |
| `ls` / `list` / `dir` | `shell_cmd_ls.py` | List contents; `--sizes/--hidden/--deep/--files/--dirs` |

zPath resolution/formatting for these is centralized in `shell_paths`
(see [internals_GUIDE.md](internals_GUIDE.md)).

### Resources & data

| Command | Module | Actions |
|---------|--------|---------|
| `load` | `shell_cmd_load.py` | Load + cache schemas/UI by zPath |
| `data` | `shell_cmd_data.py` | `read`, `insert`, `update`, `delete`, `upsert`, `create`, `drop`, `head`, `describe`, `migrate`, `history`, `connect`, `disconnect`, `status` |

`data` actions use the canonical zParser vocabulary (the parser emits `read`, not
`select`). Delegates to the zData facade; SELECT/HEAD render via AdvancedData
`zTable`.

### Identity & config

| Command | Module | Actions |
|---------|--------|---------|
| `auth` | `shell_cmd_auth.py` | `login` (hidden prompt), `logout`, `status`, `apikey issue/verify/revoke` |
| `config` | `shell_cmd_config.py` | `check`, `show`, `get`, `set`, `reset` |
| `comm` | `shell_cmd_comm.py` | service status / start / stop / install |

`auth login` never accepts a password on argv (see
[security_GUIDE.md](security_GUIDE.md)); `comm install --auto` is operator-gated.

### Execution & session

| Command | Module | Notes |
|---------|--------|-------|
| `func` | `shell_cmd_func.py` | Call a function: `func &plugin.fn(args)` |
| `open` | `shell_cmd_open.py` | Open files/URLs (mode-gated in k_zOpen) |
| `session` | `shell_cmd_session.py` | Inspect/set session keys |
| `walker` | `shell_cmd_walker.py` | Enter zWalker UI mode |
| `shortcut` | `shell_cmd_shortcut.py` | User shortcuts; `--save/--load` are path-contained |
| `help` | `shell_cmd_help.py` | Group-A direct help + walker help UI |

---

## The adapter pattern

```python
def execute_example(zos, parsed):
    action, args, options = get_command_parts(parsed)
    if not require_subsystem(zos, "example", ERROR_NO_EXAMPLE):
        return None                      # fail-closed, already displayed
    result = zos.example.do(action, args, options)
    zos.display.success(...)             # render via zDisplay
    return None                          # UI adapter
```

**Conventions:**
- Return `None`; render through `zos.display.*`.
- Use `get_command_parts()` / `require_subsystem()` instead of re-deriving keys or
  re-checking `hasattr`.
- Use parsed-key and color/style **constants**, not string literals
  (`executor_constants`, `zshell_constants`).

---

## Security-relevant executors

- **`shell_cmd_shortcut.py`** — `--save/--load` filenames are contained to the
  shortcuts directory (`.json` only; no absolute/`..`); loaded files accepted only
  as `name → command` string pairs.
- **`shell_cmd_auth.py`** — password always via hidden `getpass`; argv password
  ignored with a warning.
- **`shell_cmd_comm.py`** — `comm install --auto` shells out only on a local zCLI
  session with `ZTERMINAL_MODE: trusted`; blocked in Bifrost.

All three are summarized in [security_GUIDE.md](security_GUIDE.md).

---

## See Also

- [executor_GUIDE.md](executor_GUIDE.md) — how commands are routed
- [internals_GUIDE.md](internals_GUIDE.md) — `command_helpers`, `shell_paths`, constants
- [security_GUIDE.md](security_GUIDE.md) — credential/path/subprocess safeguards
- [zData Guide](../zData_GUIDE.md) — what `data` delegates to

---

**[← Back to zShell Guide](../zShell_GUIDE.md)**
