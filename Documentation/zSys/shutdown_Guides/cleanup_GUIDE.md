# zSys Shutdown — Cleanup Guide

> **Module:** `core/zSys/shutdown/cleanup.py`
> **Purpose:** Tear every subsystem down in the reverse of init order — fail-safe, idempotent — and return a per-component status map.

**[← Back to Shutdown Guide](../shutdown_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

`perform_shutdown(zos)` is the single teardown entry point (called by `zos.shutdown()` in `core/engine.py`). It closes subsystems in **reverse init order** so dependents go down before their dependencies:

```
WebSocket  →  HTTP server  →  Database  →  Logger
```

Each step is wrapped in its own `ExceptionContext` (from `zSys.errors`), so a failure in one subsystem is logged and **does not halt** the rest of the shutdown. The function returns a `Dict[str, bool]` recording which components cleaned up successfully (or `None` if a shutdown was already in progress).

```
perform_shutdown(zos)
  ├─ guard: zos._shutdown_in_progress?  → warn + return None        (idempotent)
  ├─ set zos._shutdown_in_progress = True
  ├─ ExceptionContext(WebSocket)  → close if running       → status[websocket]
  ├─ ExceptionContext(HTTP)       → stop if running        → status[http_server]
  ├─ ExceptionContext(Database)   → disconnect()/close()   → status[database]
  ├─ ExceptionContext(Logger)     → flush handlers         → status[logger]
  ├─ zTraceback.uninstall_exception_hook()
  └─ status report (per-component [ok]/✗) → return cleanup_status
```

---

## Idempotency

The first thing `perform_shutdown` checks is `zos._shutdown_in_progress`. If a teardown is already running (e.g. a second SIGINT, or the engine calling `shutdown()` after a signal already did), it logs `LOG_WARN_SHUTDOWN_IN_PROGRESS` and returns `None` — the work runs **exactly once**. The flag is set to `True` immediately after the guard, before any teardown begins.

---

## The four teardown steps

Every step follows the same shape: an `ExceptionContext` wrapper, then **graceful presence checks** before acting, recording `True` in `cleanup_status` for both the "cleaned up" and "nothing to clean" cases (a subsystem that was never initialised is not a failure).

| Order | Subsystem | Action | "Nothing to do" cases |
|-------|-----------|--------|------------------------|
| 1 | **WebSocket** | `_sync_shutdown()` if an event loop is running, else spin a fresh loop and `run_until_complete(ws.shutdown())` | not running / not initialised |
| 2 | **HTTP server** | `zos.server.stop()` if `is_running()` | not running / not initialised |
| 3 | **Database** | `adapter.disconnect()` (or `.close()`) | no adapter / not initialised |
| 4 | **Logger** | `flush()` every handler on the app + framework loggers | — (always flushes if present) |

> **WebSocket loop handling:** if a loop is already running, the async shutdown can't be driven inline, so it calls the synchronous `_sync_shutdown()` when available (else logs `LOG_WARN_ASYNC_SHUTDOWN_SKIPPED`). Otherwise it creates a temporary event loop, runs `ws.shutdown()` to completion, and closes it. Any exception there is caught and logged as `LOG_WARN_WEBSOCKET_ERROR` — never fatal.

After the four steps, the exception hook is uninstalled (`zTraceback.uninstall_exception_hook()`) and a status report is logged to the framework logger: a separator, then one `  %s %s` line per component (`SHUTDOWN_STATUS_SUCCESS` = `[ok]` or `SHUTDOWN_STATUS_FAIL` = `✗`).

---

## Console vs framework output

Each step emits on **two channels** (both single-sourced in `shutdown_constants.py`):

- **stdout** — a short user line, e.g. `SHUTDOWN_PRINT_WEBSOCKET` → `   [ok] Closing WebSocket connections...`
- **framework log** — a fuller trace, e.g. `SHUTDOWN_MSG_WEBSOCKET_CLOSE` → `[Shutdown] Closing WebSocket server...`

> **SSOT note (S2):** the six console prints were previously hardcoded literals (with the `[ok]` glyph baked in). They are now `SHUTDOWN_PRINT_*` constants composed from `SHUTDOWN_STATUS_SUCCESS`, so the success glyph has one home.

---

## Trust notes

- **No exec / no network / no file-write.** Operates on the live `zos` instance only.
- **Fail-safe by construction** — `ExceptionContext` around every step; a subsystem failure is logged and skipped, never propagated.
- **Foreign-content-free** — no `.zolo`/zSpark content reaches this path; nothing is interpreted. No Type-A/B/C surface.
- `# pylint: disable=protected-access` is deliberate: shutdown legitimately reaches into `zos.comm.websocket._running` / `_sync_shutdown()` to drive an orderly close.

**[← Back to Shutdown Guide](../shutdown_GUIDE.md) | [Home](../../../README.md)**
