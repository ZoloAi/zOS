# zShell Runner Module Guide

> **Module:** `zOS/core/L3_Abstraction/o_zShell/shell_modules/shell_runner.py`  
> **Purpose:** The REPL session — prompt rendering, the input loop, persistent command history, history redaction, and special (non-routed) commands.

---

## Overview

`ShellRunner` owns the **Read-Eval-Print Loop**. It reads a line, hands real
commands to `CommandExecutor`, intercepts a few session-control commands itself,
and manages persistent history via Python's `readline` (with graceful fallback
when `readline` is unavailable).

---

## Architecture

```
ShellRunner.run()
├── _setup_history()        # load ~/.zolo/.zcli_history (readline)
├── loop:
│   ├── _get_prompt()       # mode-aware prompt (normal / wizard / zPath)
│   ├── input(prompt)
│   ├── _redact_history()   # scrub credentials from the readline entry
│   ├── _handle_special_commands()   # exit/clear/tips — handled locally
│   └── executor.execute()  # everything else → CommandExecutor
└── _save_history()         # on exit
```

---

## Responsibilities

1. **Input loop** — read, strip (except in wizard canvas, which preserves indentation), dispatch.
2. **Prompt rendering** — `_get_prompt()` switches between the normal prompt, the
   wizard-canvas prompt, and an optional zPath prompt (toggled by `where on`),
   formatted via `shell_paths.format_zpath`.
3. **History** — load/save a persistent history file (`~/.zolo/.zcli_history`,
   `HISTORY_LENGTH = 1000`) when `readline` is present.
4. **History redaction (security)** — `_redact_history()` rewrites the just-entered
   readline item in place so secrets never persist (see below).
5. **Special commands** — session-control verbs handled without routing.

---

## Special commands

| Command | Effect |
|---------|--------|
| `exit` / `quit` / `q` | Leave the REPL |
| `clear` / `cls` | Clear the screen |
| `tips` | Print quick tips |
| `#…` / blank line | Ignored |

These are intercepted by `_handle_special_commands()` *before* parsing, so they
never reach the command router.

---

## History redaction (security)

`readline` records every line before `input()` returns, so a credential typed
inline would otherwise be written verbatim to the history file. After each read,
`_redact_history()` calls the SSOT `shell_policy.redact_sensitive_command()` and,
when it returns a masked form, replaces the last history item in place:

```text
zOS> auth login alice s3cret
# history stores:  auth login alice ***
```

This covers `auth login <user> <password>` and `auth apikey verify <token>`. See
[security_GUIDE.md](security_GUIDE.md) for the redaction policy.

---

## Public API

### run()

Start the REPL loop. Blocks until the user exits (`exit`/`quit`/`q`, `Ctrl+C`, or
`Ctrl+D`).

```python
runner = ShellRunner(z)   # z = zOS instance
runner.run()
```

The runner is normally reached through the [zShell facade](../zShell_GUIDE.md)
(`zShell.run_shell()`), not constructed directly.

---

## Integration with zOS

- **zParser / CommandExecutor** — non-special lines are routed via `executor.execute()`.
- **zDisplay** — prompts, goodbye, and error banners render through `z.display`.
- **shell_paths** — the zPath prompt is formatted by the shared `format_zpath` helper.

---

## See Also

- [executor_GUIDE.md](executor_GUIDE.md) — command parsing, routing, and the Bifrost seal
- [help_GUIDE.md](help_GUIDE.md) — welcome message and tips shown by the runner
- [security_GUIDE.md](security_GUIDE.md) — credential redaction SSOT
- [internals_GUIDE.md](internals_GUIDE.md) — `shell_paths` prompt formatting

---

**[← Back to zShell Guide](../zShell_GUIDE.md)**
