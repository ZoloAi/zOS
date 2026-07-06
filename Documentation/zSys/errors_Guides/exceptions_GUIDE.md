# zSys Errors — Exceptions Guide

> **Module:** `core/zSys/errors/exceptions.py`
> **Purpose:** A family of exceptions that carry an actionable **hint** and a debug **context**, and self-register with `zTraceback` on raise.

**[← Back to Errors Guide](../errors_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

Every zCLI error derives from `zCLIException`, which takes three things:

```python
zCLIException(message: str, hint: Optional[str] = None, context: Optional[dict] = None)
```

- **`message`** — what went wrong (the `str(exc)` line)
- **`hint`** — *how to fix it* (appended to the message as `HINT: …`, and rendered in its own section by the traceback UI)
- **`context`** — a debug dict (field/schema/path/…) surfaced to logs and the interactive screen

The subclasses exist so callers don't hand-write hints: each builds the message + the right hint + a structured context for its situation.

```
raise SchemaNotFoundError("contacts", context_type="yaml_zdata")
  ├─ message  = "Schema 'contacts' not found"
  ├─ hint     = "In zUI files, use zPath syntax WITHOUT .yaml extension: …"
  ├─ context  = {"schema": "contacts", "context_type": "yaml_zdata", "zpath": None}
  └─ _register_with_traceback()  → zos.zTraceback.log_exception(...)   (silent if no zos)
```

---

## The exception family

| Exception | Raised when | Notable context |
|-----------|-------------|-----------------|
| `zCLIException` | base — direct raises with a custom hint | `message`, `hint`, `context` |
| `SchemaNotFoundError` | a schema file / loaded schema is missing | `schema`, `context_type`, `zpath` |
| `FormModelNotFoundError` | a zDialog form model isn't defined | model + schema names |
| `InvalidzPathError` | a malformed `@.` zPath | the bad path |
| `DatabaseNotInitializedError` | DB access before init | — |
| `TableNotFoundError` | unknown table | table name |
| `zUIParseError` | a `.zolo` UI block fails to parse | file / block |
| `AuthenticationRequiredError` | a gated action without a session | resource / role |
| `PermissionDeniedError` | a logged-in user lacks rights | `user`, permission |
| `ConfigurationError` | bad / missing config | key |
| `PluginNotFoundError` | unknown plugin | plugin name |
| `ValidationError` | a field fails a schema constraint | `field`, **redacted** `value`, `constraint`, `schema` |
| `zMachinePathError` | machine-path resolution failure | path |
| `UnsupportedOSError` | running on an unsupported platform | os |

> The full list is the module's `__all__` (14 names — base + 13), re-exported by the facade via splat (finding **E1**).

---

## Auto-registration with zTraceback

`zCLIException.__init__` calls `_register_with_traceback(message)`, which:

1. lazily `from zOS.zCLI import get_current_zos` (avoids a circular import — `zCLI` imports the exceptions),
2. fetches the current `zos` via the **thread-local** accessor,
3. if a `zos` with an initialised `zTraceback` exists, calls `zos.zTraceback.log_exception(self, message=…, context=self.context)`.

The whole block is wrapped in `try/except: pass` — **registration must never break a `raise`**. With no `zos` context (pre-boot, standalone worker, unit test), the exception behaves like any plain Python exception.

---

## Secret-safe ValidationError (E5)

`ValidationError(field, value, constraint, schema_name)` is the one subclass that receives a **user value** — which could be a password or PII being validated. It therefore never stores the raw value:

```python
# the rejected value may be a secret → store only a type/length descriptor
safe_value = f"<{type(value).__name__}"
try:
    safe_value += f" len={len(value)}>"
except TypeError:
    safe_value += ">"
context = {"field": field, "value": safe_value, "constraint": constraint, "schema": schema_name}
```

So validating `password="hunter2secret"` yields `context["value"] == "<str len=13>"` — enough to debug a constraint failure, with no secret reaching `log_exception` → the framework log or the traceback screen.

---

## Trust notes

- **No exec / no network / no file-write.** Construction only builds strings + a dict.
- **Fail-silent registration** — `get_current_zos()` and `log_exception` are guarded; a missing context degrades to a plain exception.
- **Redaction at the source** — sensitive values are descriptored *before* they enter `context`, so every downstream sink (logs, UI) is safe by construction.

**[← Back to Errors Guide](../errors_GUIDE.md) | [Home](../../../README.md)**
