# zSys Shutdown Guide

**[Home](../../README.md) | [zSys Overview](README.md)**

> **Graceful teardown — Layer 0**
> Tears the engine down in reverse init order and turns OS signals (Ctrl-C / `kill`) into a clean, idempotent, fail-safe shutdown. Operates only on the live `zos` instance — it executes no foreign content and adds no network surface.

---

## What It Does

`zSys.shutdown` is the engine's **teardown floor**: two small functions the engine wires at boot, plus a single vocabulary of message/status constants.

- ✅ **Reverse-order cleanup** — `perform_shutdown()` closes subsystems in the reverse of init order: WebSocket → HTTP → Database → Logger
- ✅ **Fail-safe** — each subsystem teardown runs inside an `ExceptionContext`, so one failure never halts the rest of the shutdown
- ✅ **Idempotent** — guarded by `zos._shutdown_in_progress`; a second call (or a duplicate signal) is a no-op
- ✅ **Signal-driven** — `register_signal_handlers()` maps `SIGINT`/`SIGTERM` to a graceful shutdown, on the **main thread only**
- ✅ **Runner-aware** — under `ZRAVEN_RUNNER=1` the handler does **not** `sys.exit()`, so the zRaven runner's post-run work still executes
- ✅ **Vocabulary SSOT** — every status glyph, console line, and log/error string lives in `shutdown_constants.py`

**Status:** ✅ Audited + fixed — open-core, CLEAN (no zGuard seam). SSOT/DRY findings S1–S3 resolved (facade splat re-export, console-print constants, last inline log string promoted).

> This is a **facade overview**. For the teardown sequence and the signal posture, see the [`shutdown_Guides/`](shutdown_Guides/) folder.

---

## Architecture Overview

Two functions over one constants module, consumed by `core/engine.py`:

| Cluster | Module | Responsibility | Guide |
|---------|--------|----------------|-------|
| **cleanup** | `cleanup.py` | `perform_shutdown(zos)` — reverse-order subsystem teardown, fail-safe + idempotent, status report | [cleanup_GUIDE](shutdown_Guides/cleanup_GUIDE.md) |
| **signals** | `signals.py` | `register_signal_handlers(zos)` — SIGINT/SIGTERM → graceful shutdown, main-thread guard, runner-aware exit | [signals_GUIDE](shutdown_Guides/signals_GUIDE.md) |
| **constants** | `shutdown_constants.py` | SSOT for signal names, component keys, status glyphs, console prints, log/error messages | _(documented inline below)_ |

```
core/engine.py
  ├─ _register_signal_handlers() ── register_signal_handlers(self)   (signals.py)
  │        └─ SIGINT/SIGTERM → signal_handler → zos.shutdown() [→ sys.exit unless ZRAVEN_RUNNER]
  └─ shutdown()                  ── perform_shutdown(self)            (cleanup.py)
           └─ WebSocket → HTTP → Database → Logger   (each in ExceptionContext, fail-safe)
                 └─ status report → cleanup_status: Dict[str, bool]

vocabulary: shutdown_constants.py  (SIGNAL_* · SHUTDOWN_* keys/glyphs/prints · LOG_* · ERROR_*)
```

---

## Constants vocabulary (`shutdown_constants.py`)

The single home for everything user- or log-visible during shutdown. The facade `__init__` re-exports it via wildcard (no hand-maintained list — finding **S1**).

| Group | Examples | Use |
|-------|----------|-----|
| Signal names | `SIGNAL_INT` / `SIGNAL_TERM` | handler logging |
| Component keys | `SHUTDOWN_WEBSOCKET` / `SHUTDOWN_HTTP_SERVER` / `SHUTDOWN_DATABASE` / `SHUTDOWN_LOGGER` | `cleanup_status` dict keys |
| Status glyphs | `SHUTDOWN_STATUS_SUCCESS` (`[ok]`) / `SHUTDOWN_STATUS_FAIL` (`✗`) | status report |
| Console prints | `SHUTDOWN_PRINT_INITIATED` / `_WEBSOCKET` / `_HTTP` / `_DB` / `_LOGGER` / `_COMPLETE` | user stdout (compose from the success glyph — finding **S2**) |
| Log messages | `LOG_SHUTDOWN_*` / `LOG_WARN_*` / `LOG_DEBUG_*` | `zos.logger.framework.debug(...)` |
| Error operations | `ERROR_*_SHUTDOWN` / `ERROR_SIGNAL_RECEIVED` | `ExceptionContext(operation=...)` |

> The console prints (`SHUTDOWN_PRINT_*`) and the framework-debug constants (`SHUTDOWN_MSG_*`) are **two intentional channels** — the user sees a short `[ok] …` line on stdout while the framework log gets a fuller `[Shutdown] …` trace. Both are now single-sourced.

---

## Quick Start

The engine owns the wiring; callers rarely touch this module directly.

```python
# core/engine.py (sketch)
from zSys.shutdown import perform_shutdown, register_signal_handlers

class zCLI:
    def _register_signal_handlers(self):
        register_signal_handlers(self)        # SIGINT/SIGTERM → graceful shutdown

    def shutdown(self):
        return perform_shutdown(self)          # → Dict[str, bool] | None (None if already in progress)
```

---

## Public API (facade)

| Member | Description |
|--------|-------------|
| `perform_shutdown(zos)` | Reverse-order teardown; returns `Dict[str, bool]` component status, or `None` if a shutdown is already in progress |
| `register_signal_handlers(zos)` | Install SIGINT/SIGTERM handlers (main-thread only); runner-aware exit |
| `SIGNAL_*`, `SHUTDOWN_*`, `LOG_*`, `ERROR_*` | The shutdown vocabulary (re-exported from `shutdown_constants`) |

---

## Trust posture — CLEAN, OS-signal-driven

`zSys.shutdown` is **fully open-core** and needs **no zGuard seam**.

- **No code-exec / no network / no file-write** — no `eval`/`exec`/`subprocess`/`pickle`/`os.system`, no socket/bind. The only "dangerous-looking" calls are `signal.signal(...)` registration and an `asyncio.new_event_loop()` + `run_until_complete(ws.shutdown())` fallback — both standard teardown.
- **Process termination is OS-signal-driven, not network-reachable.** `sys.exit(0/1)` lives in the SIGINT/SIGTERM handler (Ctrl-C / `kill`), on the **main thread only**, and is **suppressed under `ZRAVEN_RUNNER=1`**. A remote client cannot reach it. Mirrors the `p_zWalker` `on_stop`/`on_error` local-only-exit posture.
- **Fail-safe + foreign-content-free** — every teardown step is wrapped in `ExceptionContext`; the module operates only on the live `zos` instance, never on `.zolo`/zSpark content → no Type-A/B/C surface.
- **Correct layering** — consumed *down* from `core/engine.py` (L0 util ← engine); no upward dependency.

---

## Summary

`zSys.shutdown` is the **graceful-teardown floor**: a reverse-order, fail-safe, idempotent cleanup and a main-thread signal handler that turns Ctrl-C / `kill` into a clean exit — with every status/console/log string single-sourced in one constants module.

| Go deeper | Guide |
|-----------|-------|
| The teardown sequence (WebSocket → HTTP → DB → Logger), fail-safe + status report | [cleanup_GUIDE](shutdown_Guides/cleanup_GUIDE.md) |
| Signal handling, main-thread guard, `ZRAVEN_RUNNER` posture, exit codes | [signals_GUIDE](shutdown_Guides/signals_GUIDE.md) |

**Architecture:** two functions (`perform_shutdown` | `register_signal_handlers`) over one constants SSOT, wired by `core/engine.py`
**Status:** ✅ Audited + fixed (open-core, CLEAN — no zGuard seam)

---

**[Home](../../README.md) | [zSys Overview](README.md)**
