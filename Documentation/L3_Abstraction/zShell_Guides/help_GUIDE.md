# zShell Help Module Guide

> **Modules:** `shell_modules/shell_help.py` (system help, welcome, tips) + `shell_modules/commands/shell_cmd_help.py` (Group-A direct help + walker help UI)  
> **Purpose:** Present command documentation — a startup welcome, quick tips, a command list, per-command detail, and an interactive walker help menu — filtered to what the current session may actually run.

---

## Overview

zShell has a **two-tier** help system:

- **`shell_help.py` — `HelpSystem`:** the welcome banner, quick tips, and a
  centralized `COMMANDS` map used for the command list and per-command usage. It is
  **mode-aware** (see below).
- **`shell_cmd_help.py` — `execute_help`:** the `help` command itself. With no
  args it launches the declarative help UI via zWalker (`zUI.zcli_sys` Help block);
  with a command name it shows direct help for Group-A terminal commands.

---

## Architecture

```
help            → execute_help([])      → walker help UI (zUI.zcli_sys)
help <command>  → execute_help([cmd])   → _show_command_help() (Group A)
welcome / tips  → HelpSystem.get_welcome_message() / get_quick_tips()
command list    → HelpSystem.show_help()        (mode-aware filter)
command detail  → HelpSystem.show_command_help() (mode-aware filter)
```

---

## Mode-aware filtering (security/UX)

`HelpSystem` takes the `zos` instance and consults the
`shell_policy.sealed_actions_for()` SSOT. In a **Bifrost** session it:

- **hides sealed usage/example lines** in `show_command_help()` (e.g. `data delete`,
  `data drop`, `config set`), and
- **hides fully-sealed commands** from the `show_help()` list.

So the shell never advertises a capability the seal-policy would block. In a local
zCLI session nothing is filtered. See [security_GUIDE.md](security_GUIDE.md).

```python
HelpSystem(display=z.display, zos=z)   # zos enables filtering
```

---

## Public API (`HelpSystem`)

| Method | Purpose |
|--------|---------|
| `get_welcome_message()` | Startup banner (shown by the runner) |
| `get_quick_tips()` | Quick tips (the `tips` special command) |
| `show_help()` | Command list (sealed commands hidden in Bifrost) |
| `show_command_help(type)` | Per-command detail (sealed lines filtered in Bifrost) |

`execute_help(zos, parsed)` is the routed `help` command (walker UI / direct help).

---

## Integration with zOS

- **zWalker** — `help` with no args launches the declarative help menu.
- **zDisplay** — all help output renders through `z.display` (UI adapter).
- **shell_policy** — the single source of truth for what is sealed/filtered.

---

## See Also

- [executor_GUIDE.md](executor_GUIDE.md) — `help` routing
- [security_GUIDE.md](security_GUIDE.md) — `sealed_actions_for` and the seal-policy
- [commands_GUIDE.md](commands_GUIDE.md) — the commands help documents

---

**[← Back to zShell Guide](../zShell_GUIDE.md)**
