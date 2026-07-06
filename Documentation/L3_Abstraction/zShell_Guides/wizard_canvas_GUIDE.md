# zShell Wizard Canvas Module Guide

> **Module:** `zOS/core/L3_Abstraction/o_zShell/shell_modules/wizard_canvas.py`  
> **Purpose:** The interactive canvas for staging multiple shell commands and running them together as one workflow, delegated to zWizard for execution.

---

## Overview

`WizardCanvasManager` provides a small modal UX layered on top of the REPL. While
the canvas is active, ordinary lines are **buffered** (not executed); `wizard`
sub-commands control the buffer and trigger execution through zWizard. State lives
in the session under `SESSION_KEY_WIZARD_MODE`.

---

## Architecture

```
ShellRunner / CommandExecutor
        │  (line starts with "wizard " OR canvas active)
        ▼
WizardCanvasManager.handle_command()
├── --start  → activate canvas, begin buffering
├── (line)   → append to buffer (step)
├── --show   → display staged steps
├── --run    → hand buffer to zWizard for execution
├── --clear  → empty the buffer
└── --stop   → deactivate canvas
```

---

## Commands

| Command | Effect |
|---------|--------|
| `wizard --start` | Enter canvas mode (subsequent lines are staged, not run) |
| `wizard --show` | Show the staged steps |
| `wizard --run` | Execute all staged steps via zWizard |
| `wizard --clear` | Empty the buffer (stay in canvas) |
| `wizard --stop` | Leave canvas mode |

Both YAML (`zWizard:` block) and shell-line step formats are accepted; the buffer
records the chosen format alongside the lines.

---

## Example

```text
zOS> wizard --start
zOS> data insert users --model $db --fields name --values "Alice"
zOS> data insert posts --model $db --fields author --values "Alice"
zOS> wizard --show
zOS> wizard --run        # both inserts run together via zWizard
zOS> wizard --stop
```

---

## Public API

### is_active()

Returns whether the canvas is currently buffering (read from session state).

### handle_command(command)

Process one canvas line — either a `wizard --…` control verb or a step to buffer.
Renders feedback via zDisplay; returns `None` (UI adapter).

---

## Integration with zOS

- **zWizard** — `--run` delegates the staged steps to the zWizard engine; zShell
  only provides the canvas UX and the per-step command bridge
  (`CommandExecutor.execute_wizard_step`).
- **zSession** — active/lines/format state is persisted under the wizard session key.
- **zDisplay** — banners, buffer listing, and run feedback render through `z.display`.

---

## See Also

- [executor_GUIDE.md](executor_GUIDE.md) — how canvas input is detected and delegated
- [zWizard Guide](../zWizard_GUIDE.md) — the workflow engine that executes the buffer

---

**[← Back to zShell Guide](../zShell_GUIDE.md)**
