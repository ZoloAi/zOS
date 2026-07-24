# zShell Executor Module Guide

> **Module:** `zOS/core/L3_Abstraction/p_zShell/shell_modules/shell_executor.py`  
> **Purpose:** Parse a command line, enforce the Bifrost seal-policy, and route the parsed command to the right command executor (O(1) dispatch).

---

## Overview

`CommandExecutor` is the routing engine. It parses input through zParser, checks
the **Bifrost seal-policy** before dispatch, then looks the command type up in a
dictionary command map and calls the matching executor. Wizard-canvas input is
delegated to `WizardCanvasManager`.

---

## Architecture

```
execute(command)
├── wizard active / "wizard …"? → WizardCanvasManager.handle_command()
├── zparser.parse_command()      → parsed {type, action, args, options}
└── _execute_parsed_command(parsed)
    ├── _validate_command_type()
    ├── enforce_bifrost_seal()    → blocks sealed ops in a remote session
    └── command_map[type](z, parsed)
```

---

## Responsibilities

1. **Wizard gate** — if the canvas is active or the line starts with `wizard `,
   delegate to the canvas manager (see [wizard_canvas_GUIDE.md](wizard_canvas_GUIDE.md)).
2. **Parsing** — delegate to `z.zparser.parse_command()`; surface parser errors.
3. **Seal enforcement** — call `shell_policy.enforce_bifrost_seal()` *before*
   dispatch so destructive/mutating ops are refused in Bifrost sessions.
4. **Routing** — O(1) command-map lookup, including aliases.
5. **Wizard step bridge** — `execute_wizard_step()` is the callback zWizard uses to
   run individual workflow steps in shell context.

---

## Command map

The router maps a command type to its executor. Aliases share an executor:

| Type(s) | Executor |
|---------|----------|
| `data` | `execute_data` |
| `func` | `execute_func` |
| `session` | `execute_session` |
| `walker` | `execute_walker` |
| `open` | `execute_open` |
| `auth` | `execute_auth` |
| `config` | `execute_config` |
| `comm` | `execute_comm` |
| `load` | `execute_load` |
| `ls` / `list` / `dir` | `execute_ls` |
| `cd` | `execute_cd` |
| `cwd` / `pwd` | `execute_pwd` |
| `shortcut` | `execute_shortcut` |
| `where` | `execute_where` |
| `help` | `execute_help` |

> `export` and `utils` remain mapped for backward compatibility but are
> deprecated (export redirects to config set/reset; plugin execution moved to
> `func`). The live set is always what `help` reports.

---

## The Bifrost seal (security)

Before any executor runs, `enforce_bifrost_seal(z, parsed)` consults the
`shell_policy` SSOT. In a Bifrost (remote) session it refuses the sealed
`(type, action)` pairs — `data delete/drop/migrate`, `config set/reset` — and
returns an error dict instead of dispatching. Read-only counterparts pass through.
Local zCLI sessions are unaffected. See [security_GUIDE.md](security_GUIDE.md).

---

## Public API

### execute()

```python
executor = CommandExecutor(z)
executor.execute("data read users --model @.zSchema.users")  # → None (renders via zDisplay)
executor.execute("nope")  # → {"error": "Unknown command type: nope"}
```

Returns `None` for UI-adapter commands (they render through zDisplay) or an
error dict on failure.

### execute_wizard_step()

Callback for zWizard to execute a single workflow step (`step_key`, `step_value`,
`step_context`) in shell context.

---

## See Also

- [runner_GUIDE.md](runner_GUIDE.md) — the REPL that calls `execute()`
- [commands_GUIDE.md](commands_GUIDE.md) — the executors the map routes to
- [wizard_canvas_GUIDE.md](wizard_canvas_GUIDE.md) — canvas delegation
- [security_GUIDE.md](security_GUIDE.md) — the seal-policy SSOT
- [internals_GUIDE.md](internals_GUIDE.md) — `executor_constants` command types/keys

---

**[← Back to zShell Guide](../zShell_GUIDE.md)**
