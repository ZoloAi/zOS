# zSys Logger — Bootstrap Guide

> **Module:** `core/zSys/logger/bootstrap.py`
> **Purpose:** Log **before the framework exists**. Buffer pre-boot messages in memory, then flush them into the framework log once it's available — or dump them safely if init fails.

**[← Back to Logger Guide](../logger_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

`main.py` needs to log from its very first line, long before `a_zConfig` / the framework logger exist. `BootstrapLogger` solves this: it captures every pre-boot record in memory and **replays** them into the real logger later, with an emergency path if the framework never comes up.

```
BootstrapLogger()
  ├─ stdlib logging.Logger("zCLI.bootstrap")  (propagate=False, level=DEBUG)
  └─ RecordCapture handler ── appends every record → self.buffered_records[]

  .info/.debug/.session/.warning/.error/.critical(msg, *args)   → buffered

  ── once framework is ready ──
  .flush_to_framework(logger_config, verbose)
        ├─ ERROR/CRITICAL → framework + session_framework  (devs + users)
        ├─ else           → session_framework only         (user context)
        └─ verbose=True   → also print format_bootstrap_verbose() to stdout

  ── if init fails ──
  .emergency_dump(exc)  → stderr + .zos-bootstrap-error.log
```

---

## Why in-memory buffering

The framework logger (file handlers, formatters, routing) doesn't exist during argument parsing and early setup. Rather than drop those logs or write them somewhere ad-hoc, `BootstrapLogger` keeps them in a list and injects them once `cli.logger` is constructed — so the **pre-boot story ends up in the same `zcli-framework.log`** as everything else, in order.

A nested `RecordCapture(logging.Handler)` stores raw `LogRecord`s (not formatted strings), so severity, timestamp, and message args survive until flush time.

---

## Convenience methods

| Method | Level |
|--------|-------|
| `.debug(msg, *args)` | `DEBUG` (10) |
| `.session(msg, *args)` | `SESSION` (15 — see [formats_GUIDE](formats_GUIDE.md#the-session-level-levelspy)) |
| `.info(msg, *args)` | `INFO` (20) |
| `.warning(msg, *args)` | `WARNING` (30) |
| `.error(msg, *args)` | `ERROR` (40) |
| `.critical(msg, *args)` | `CRITICAL` (50) |

`*args` follow stdlib `%`-style deferred formatting (the record stores them; interpolation happens at emit/format time).

---

## `flush_to_framework(logger_config, verbose=False)`

Replays the buffer into the framework loggers with **severity-based routing**:

- **`ERROR` / `CRITICAL`** → **both** `framework` (for framework devs) and `session_framework` (for users) — failures everyone should see.
- **`DEBUG` / `INFO` / `SESSION`** → `session_framework` **only** — user-facing context.

Each record is prefixed `[Bootstrap:HH:MM:SS.mmm]` (timestamp via `TS_FORMAT_TIME_MS[:-3]`), bracketed by an injection header + footer carrying the message count and elapsed seconds. When `verbose=True`, each record is also printed to stdout via `format_bootstrap_verbose`, and a completion line is shown. The buffer is cleared afterward.

> `print_buffered_logs()` is the no-framework variant: it prints the buffer to stdout directly (used by commands like the info banner that never build a `zCLI`, but still honour `--verbose`).

---

## `emergency_dump(exception=None)`

The fail-safe for when framework init itself throws. It writes the buffer to **two** places:

1. **stderr** — a boxed banner, the exception + traceback, then every buffered record.
2. **`.zos-bootstrap-error.log`** in `Path.cwd()` — the same content, persisted for post-mortem.

```python
temp_file = Path.cwd() / ".zos-bootstrap-error.log"
try:
    with open(temp_file, "w", encoding="utf-8") as f:
        ...   # exception + traceback + buffered records
except Exception:
    # writing the diagnostic must never mask the original failure
    print("⚠️  Failed to save bootstrap log: …", file=sys.stderr)
```

---

## Trust notes

- **Bounded, fixed-name file write.** The path is **not** user-controlled (`Path.cwd() / ".zos-bootstrap-error.log"`) → no traversal. The write is wrapped in try/except so a diagnostic failure never escalates the original crash (**fail-safe**).
- **No exec / no network** — stdlib `logging`, `datetime`, `traceback`, `Path`, and `print` only.
- **Info-disclosure (LOW / accepted):** stderr + the dump file contain pre-boot messages **verbatim**. The logger is a sink; secret redaction is the caller's responsibility (already enforced at higher layers). If a caller logs a secret pre-boot, it can land in `.zos-bootstrap-error.log` — operators should treat that file as diagnostic-only.

**[← Back to Logger Guide](../logger_GUIDE.md) | [Home](../../../README.md)**
