# zSys Shutdown — Signals Guide

> **Module:** `core/zSys/shutdown/signals.py`
> **Purpose:** Turn OS termination signals (Ctrl-C / `kill`) into a graceful, idempotent shutdown — on the main thread only, and without breaking the zRaven runner.

**[← Back to Shutdown Guide](../shutdown_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

`register_signal_handlers(zos)` installs a single handler for both `SIGINT` (Ctrl-C) and `SIGTERM` (`kill`). When a signal fires, the handler requests a graceful shutdown via `zos.shutdown()` and then — in the normal CLI case — exits the process with a clean code.

```
register_signal_handlers(zos)
  ├─ main thread?  ── no → log LOG_DEBUG_SIGNAL_SKIP_NONMAIN, return (can't set handlers off-main)
  └─ yes → signal.signal(SIGINT,  signal_handler)
           signal.signal(SIGTERM, signal_handler)

signal_handler(signum, frame)
  ├─ already in progress?  → warn (LOG_WARN_SIGNAL_DUPLICATE), return
  ├─ zos._shutdown_requested = True
  ├─ zos.shutdown()
  └─ unless ZRAVEN_RUNNER=1:  sys.exit(0)   (or sys.exit(1) on exception)
```

---

## Main-thread guard

Python only allows `signal.signal()` to be called from the **main thread**. `register_signal_handlers` checks `threading.current_thread() is threading.main_thread()`:

- **main thread** → install both handlers, log `LOG_DEBUG_SIGNAL_HANDLERS`.
- **otherwise** → skip silently (log `LOG_DEBUG_SIGNAL_SKIP_NONMAIN`) rather than raise. This matters because zOS may be embedded in a worker/thread (e.g. a WSGI context) where signal registration isn't permitted.

> **SSOT note (S3):** that skip message was the one bare string literal left in the subsystem; it is now the named constant `LOG_DEBUG_SIGNAL_SKIP_NONMAIN`.

---

## Duplicate-signal handling

A user may hit Ctrl-C repeatedly. The handler checks `zos._shutdown_in_progress` and, if a shutdown is already running, logs `LOG_WARN_SIGNAL_DUPLICATE` and returns immediately — the actual teardown (`perform_shutdown`) runs once. It also sets `zos._shutdown_requested = True` so cooperating loops can observe the request.

---

## Runner-aware exit (`ZRAVEN_RUNNER`)

This is the subtle part. Normally the handler calls `sys.exit(0)` after `zos.shutdown()` so the process ends promptly. But when **this process is the zRaven runner** (`ZRAVEN_RUNNER=1`), exiting here would raise `SystemExit` and **bypass the runner's post-run work** — hint analysis, `Data/` teardown, result CSV — which must run after `zcli.run()` returns.

```python
is_runner = _os.environ.get("ZRAVEN_RUNNER") == "1"
try:
    zos.shutdown()
    if not is_runner:
        sys.exit(0)
except Exception as exc:
    zos.zTraceback.log_exception(exc, message=ERROR_SHUTDOWN_SIGNAL % signal_name, context={"signal": signum})
    if not is_runner:
        sys.exit(1)
```

| Context | On signal |
|---------|-----------|
| Normal CLI | `zos.shutdown()` → `sys.exit(0)` (or `1` on error) |
| zRaven runner (`ZRAVEN_RUNNER=1`) | `zos.shutdown()` → **return** (no `sys.exit`), let the runner finish post-run work |

> Distinct from `ZRAVEN_TARGET`, which disables zRaven *activation* in the test-target subprocess. `ZRAVEN_RUNNER` marks the *driving* process so it isn't killed mid-teardown.

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Clean shutdown |
| `1` | Exception during shutdown (logged via `zTraceback.log_exception`) |

---

## Trust notes

- **Process termination is OS-signal-driven, not network-reachable.** The `sys.exit` paths fire only from a real `SIGINT`/`SIGTERM` delivered by the OS/operator, on the main thread. No remote/`.zolo` input can reach them — mirrors the `q_zWalker` local-only-exit posture.
- **No exec / no network / no file-write.** Lazy stdlib imports (`signal`, `sys`, `threading`, `os`) inside the function; nothing else.
- **Fail-closed logging** — a teardown exception is routed through `zTraceback.log_exception` with the signal name + number as context, then a non-zero exit (outside the runner).

**[← Back to Shutdown Guide](../shutdown_GUIDE.md) | [Home](../../../README.md)**
