# zSys Errors Guide

**[Home](../../README.md) | [zSys Overview](README.md)**

> **Error handling + diagnostics — Layer 0**
> Actionable exceptions, an interactive traceback UI, and a runtime-validation helper. Operates only on the live `zos` instance and on Python exception objects — it executes no foreign content and adds no network surface.

---

## What It Does

`zSys.errors` is the engine's **error vocabulary + diagnostics floor**: a family of hinted exceptions, the `zTraceback` handler that renders them, a small validation helper, and one constants module for the UI/fallback strings.

- ✅ **Actionable exceptions** — every `zCLIException` carries a `message`, a human `hint`, and a debug `context` dict; subclasses (`SchemaNotFoundError`, `ValidationError`, …) prebuild the hint for their case
- ✅ **Auto-registration** — on raise, an exception self-registers with the current `zos.zTraceback` (thread-local `get_current_zos()`), **failing silently** if no context exists so raising never breaks
- ✅ **Interactive traceback** — `zTraceback.interactive_handler` launches the Walker traceback UI (`@.UI.zUI.zcli_sys` → `Traceback`), inheriting the parent's deployment mode + log level
- ✅ **Fail-safe rendering** — when no logger / `zos` / UI is available, a single `_emergency_print` dumps to `stderr`
- ✅ **Vocabulary SSOT** — traceback UI headers/colors/styles, the return-to-menu prompt, and the fallback messages live in `errors_constants.py`
- ✅ **Secret-safe context** — `ValidationError` stores a **redacted descriptor** (`<str len=13>`), never the raw rejected value, so secrets can't leak into logs/UI

**Status:** ✅ Audited + fixed — open-core, CLEAN (no zGuard seam). SSOT/DRY findings E1–E4 resolved (facade splat re-export, lazy canonical session keys + deployment default, single `_emergency_print`, new `errors_constants.py`); security finding **E5** resolved (value redaction).

> This is a **facade overview**. For the exception families, the traceback handler, and the validation helper, see the [`errors_Guides/`](errors_Guides/) folder.

---

## Architecture Overview

Three clusters over one constants module, consumed across the runtime (and wired by `core/engine.py` for the excepthook):

| Cluster | Module | Responsibility | Guide |
|---------|--------|----------------|-------|
| **exceptions** | `exceptions.py` | `zCLIException` base + 13 hinted subclasses; auto-register with `zTraceback` on raise | [exceptions_GUIDE](errors_Guides/exceptions_GUIDE.md) |
| **traceback** | `traceback.py` | `zTraceback` (excepthook, `log_exception`, `interactive_handler`), `ExceptionContext`, the 3 display functions | [traceback_GUIDE](errors_Guides/traceback_GUIDE.md) |
| **validation** | `validation.py` | `validate_zos_instance(zos, name)` — catches init-order issues early | [validation_GUIDE](errors_Guides/validation_GUIDE.md) |
| **constants** | `errors_constants.py` | SSOT for traceback UI labels/colors/styles, prompts, fallback messages, the redaction marker | _(documented inline below)_ |

```
raise SomeError(...)                       (exceptions.py)
  └─ _register_with_traceback() ── get_current_zos() ── zos.zTraceback.log_exception(...)   (silent if no ctx)

sys.excepthook = custom_excepthook         (traceback.py, installed by engine)
  └─ session[zTraceback]? → interactive_handler → Walker UI (@.UI.zUI.zcli_sys / Traceback)
                          └─ no zos/UI → _emergency_print(exc, prefix) → stderr

with ExceptionContext(ztb, "operation"):   (traceback.py)
  └─ on exception → log_exception(..., message=OPERATION_PREFIX % op) → suppress or reraise

validate_zos_instance(zos, "x_subsystem")  (validation.py)  → ValueError on None / missing session

vocabulary: errors_constants.py  (HEADER_* · COLOR_* · STYLE_* · PROMPT_* · MSG_* · PREFIX_* · REDACTED)
```

---

## Constants vocabulary (`errors_constants.py`)

The single home for the traceback UI's display tokens and the fallback strings. Per-exception **hint text stays with its exception class** (cohesive with the error it describes) — only the shared/reused literals live here.

| Group | Examples | Use |
|-------|----------|-----|
| Header labels | `HEADER_ERROR_DETAILS` / `HEADER_CONTEXT` / `HEADER_HINT` / `HEADER_FULL_TRACEBACK` | `display.handle({"event":"header", ...})` |
| Header colors / styles | `COLOR_ERROR` / `COLOR_CONTEXT` / `COLOR_HINT` / `COLOR_RESET` · `STYLE_FULL` / `STYLE_SINGLE` | header color + style tokens |
| Prompts / labels | `PROMPT_RETURN_TO_MENU` / `MSG_NO_EXCEPTION` / `LABEL_LOCATION` | UI prompts |
| Fallback messages | `DEFAULT_LOG_MESSAGE` · `PREFIX_ERROR` / `PREFIX_ORIGINAL_ERROR` · `MSG_INTERACTIVE_*` / `MSG_UI_LAUNCH_FAILED` · `OPERATION_PREFIX` | stderr + logger |
| Redaction | `REDACTED` (`<redacted>`) | secret-safe context marker (E5) |

---

## Quick Start

```python
from zSys.errors import (
    zCLIException, ValidationError, SchemaNotFoundError,   # raise with a hint
    zTraceback, ExceptionContext,                          # render / wrap
    validate_zos_instance,                                 # guard init order
)

# 1) Raise an actionable error (auto-registers with zTraceback if a zos exists)
raise SchemaNotFoundError("contacts", context_type="yaml_zdata")

# 2) Wrap a risky operation — logs + suppresses (or reraises) on failure
with ExceptionContext(zos.zTraceback, "loading schema", reraise=False):
    risky()

# 3) Guard a subsystem constructor against init-order bugs
validate_zos_instance(zos, "x_zNavigation")
```

---

## Public API (facade)

| Member | Description |
|--------|-------------|
| `zCLIException` + 13 subclasses | Hinted exceptions (`SchemaNotFoundError`, `FormModelNotFoundError`, `InvalidzPathError`, `DatabaseNotInitializedError`, `TableNotFoundError`, `zUIParseError`, `AuthenticationRequiredError`, `PermissionDeniedError`, `ConfigurationError`, `PluginNotFoundError`, `ValidationError`, `zMachinePathError`, `UnsupportedOSError`) |
| `zTraceback` | Exception handler: excepthook install/uninstall, `log_exception`, `interactive_handler`, `format_exception`, `get_traceback_info` |
| `ExceptionContext` | Context manager — log + suppress/reraise with a default return |
| `display_error_summary` / `display_full_traceback` / `display_formatted_traceback` | Walker UI render functions |
| `validate_zos_instance` / `validate_zcli_instance` | Init-order guard (alias for back-compat) |

> The facade re-exports each submodule's curated `__all__` via splat (no hand-maintained list — finding **E1**): 21 names total (14 exceptions + 5 traceback + 2 validation).

---

## Trust posture — CLEAN, diagnostics-only

`zSys.errors` is **fully open-core** and needs **no zGuard seam**.

- **No code-exec / no network / no file-write** — no `eval`/`exec`/`subprocess`/`pickle`/`os.system`, no socket/bind. The only "dangerous-looking" call is `sys.excepthook = …` (excepthook install) plus an in-method `import zCLI` to launch the traceback UI — both standard.
- **Auto-registration fails silent** — `_register_with_traceback` wraps everything in `try/except: pass`; a missing `zos` context never breaks `raise`.
- **Interactive excepthook is local-CLI-only** — the Walker UI launch is gated on `session[zTraceback]` (off by default in non-dev), and falls back to the original excepthook otherwise. Not network-reachable; mirrors the shutdown/`p_zWalker` local-only posture.
- **Secret-safe by construction (E5)** — `ValidationError` redacts the raw value into a `<type len=N>` descriptor before it reaches `context` → logs / the traceback screen. Other exceptions' contexts (schema names, resolved paths, usernames) are non-sensitive.
- **Layer-0 discipline** — top-level imports are stdlib + sibling `errors_constants` only; the canonical session keys (`zOS.zVocabulary`) and `DEPLOYMENT_DEFAULT` (`zSys.logger`) are **lazy-imported** inside post-boot methods (E2).

---

## Summary

`zSys.errors` is the **diagnostics floor**: hinted, auto-registering exceptions; a fail-safe interactive traceback handler; and a tiny init-order guard — with every UI/fallback string single-sourced and every rejected value redacted before it can leak.

| Go deeper | Guide |
|-----------|-------|
| The `zCLIException` base, the 13 subclasses, auto-registration | [exceptions_GUIDE](errors_Guides/exceptions_GUIDE.md) |
| `zTraceback`, the excepthook, `interactive_handler`, `ExceptionContext`, display functions | [traceback_GUIDE](errors_Guides/traceback_GUIDE.md) |
| `validate_zos_instance` — init-order guard | [validation_GUIDE](errors_Guides/validation_GUIDE.md) |

**Architecture:** three clusters (exceptions · traceback · validation) over one constants SSOT
**Status:** ✅ Audited + fixed (open-core, CLEAN — no zGuard seam)

---

**[Home](../../README.md) | [zSys Overview](README.md)**
