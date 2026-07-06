# zSys Errors — Traceback Guide

> **Module:** `core/zSys/errors/traceback.py`
> **Purpose:** Centralized exception handling — a custom excepthook, structured logging, the interactive Walker traceback UI, an `ExceptionContext` wrapper, and the display render functions.

**[← Back to Errors Guide](../errors_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

`zTraceback` is the single object that turns a raised exception into something useful: a logged record, an interactive screen, or — when nothing else is available — a clean `stderr` dump.

```
zTraceback(logger=None, zos=None)
  ├─ install_exception_hook()   → sys.excepthook = custom_excepthook
  │     └─ session[zTraceback]? → interactive_handler   else → original excepthook
  ├─ log_exception(exc, message, context)   → logger.error(..., exc_info=True) + debug(context)
  │     └─ no logger → _emergency_print(exc, message)
  ├─ interactive_handler(exc, context)      → launch Walker UI (@.UI.zUI.zcli_sys / Traceback)
  │     └─ no zos / UI fails → _emergency_print(exc, prefix)
  ├─ format_exception / get_traceback_info  → str / structured dict
  └─ uninstall_exception_hook()
```

---

## The custom excepthook

`install_exception_hook()` swaps `sys.excepthook` for `custom_excepthook`, which:

1. checks `zos.session[SESSION_KEY_ZTRACEBACK]` — if interactive mode is **off**, it defers to the **original** excepthook (default Python behaviour),
2. otherwise calls `interactive_handler(...)` to launch the UI,
3. if the handler itself throws, logs `MSG_INTERACTIVE_HANDLER_FAILED` and falls back to the original excepthook.

`SESSION_KEY_ZTRACEBACK` is **lazy-imported** from `zOS.zVocabulary` inside `install_exception_hook` — the Layer-0 top-level rule forbids importing `zOS.*` at module scope, but this runs post-boot (E2).

---

## interactive_handler — the Walker UI

When enabled, `interactive_handler` boots a small secondary `zCLI` instance pointed at the system traceback UI (`@.UI.zUI.zcli_sys`, block `Traceback`), **inheriting the parent's environment** so the UI looks/logs like the session that raised:

| Inherited | Source | Default |
|-----------|--------|---------|
| deployment mode | `zos.config.get_environment('deployment')` | `DEPLOYMENT_DEFAULT` (`"Development"`) |
| logger level | `zos.session[SESSION_KEY_ZLOGGER]` | `"INFO"` |

`SESSION_KEY_ZLOGGER` (`zOS.zVocabulary`) and `DEPLOYMENT_DEFAULT` (`zSys.logger`) are lazy-imported here for the same Layer-0 reason — alongside the existing lazy `import zCLI` (E2). If there's no `zos`, or the UI fails to launch, the handler logs and calls `_emergency_print`.

---

## _emergency_print — the fail-safe (E3)

The "no logger / no zos / UI launch failed" paths all need the same last resort: print to `stderr` + dump the traceback. That was duplicated; it's now one helper:

```python
def _emergency_print(self, exc, prefix):
    print(f"{prefix}: {exc}", file=sys.stderr)
    traceback.print_exc()
```

Called from three sites — `log_exception` (no logger, prefix = the log `message`), `interactive_handler` (no `zos`, `PREFIX_ERROR`), and the UI-launch-failed path (`PREFIX_ORIGINAL_ERROR`). The excepthook's own fallback uses `_original_excepthook` (not `print_exc`) and is intentionally left as-is.

---

## ExceptionContext — wrap a risky operation

A context manager for "log it, then suppress or reraise":

```python
with ExceptionContext(zos.zTraceback, "loading schema", reraise=False, default_return=None) as ctx:
    ctx.result = risky()
```

On exception it stores `exc_val`, calls `log_exception(message=OPERATION_PREFIX % operation, context=…)`, then either returns `False` (reraise) or `True` (suppress, leaving `self.result = default_return`). `OPERATION_PREFIX` is the single-sourced `"Error during %s"` (E4).

---

## Display functions

Three render functions drive the Walker traceback UI, all using the `errors_constants` tokens (E4) — no inline labels/colors:

| Function | Renders |
|----------|---------|
| `display_error_summary(zcli)` | `HEADER_ERROR_DETAILS` + the exception line, `LABEL_LOCATION` (file/line/function), `HEADER_CONTEXT` (the context dict), `HEADER_HINT` (if the exception has one) — ends on `PROMPT_RETURN_TO_MENU` |
| `display_full_traceback(zcli)` | `HEADER_FULL_TRACEBACK` + every formatted frame |
| `display_formatted_traceback(zcli)` | both of the above, in order |

Each shows `MSG_NO_EXCEPTION` if there's nothing stored.

---

## Trust notes

- **No exec / no network / no file-write.** The only notable calls are `sys.excepthook = …` and the in-method `import zCLI` to launch the UI.
- **Interactive UI is gated + local-only** — launched only when `session[zTraceback]` is set; otherwise the original excepthook runs. Not network-reachable.
- **Layer-0 discipline** — `zOS.zVocabulary` / `zSys.logger` constants are lazy-imported inside post-boot methods, never at module top-level.
- **Fail-safe everywhere** — every "missing dependency" path degrades to `_emergency_print` rather than throwing.

**[← Back to Errors Guide](../errors_GUIDE.md) | [Home](../../../README.md)**
