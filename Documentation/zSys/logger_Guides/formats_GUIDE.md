# zSys Logger — Formats Guide

> **Modules:** `core/zSys/logger/formats.py`, `constants.py`, `levels.py`
> **Purpose:** Define the **single canonical log line** every logger emits, the `logging.Formatter` that wraps it, and the SSOTs it draws from — the level→colour map, the timestamp formats, and the custom `SESSION` level.

**[← Back to Logger Guide](../logger_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

There is exactly **one** function that defines what a zOS log line looks like: `format_log_message`. Bootstrap, Framework, App, and standalone (`ConsoleLogger`) output all resolve to it, so output is byte-for-byte consistent regardless of source. Everything else in this cluster feeds that function.

```
format_log_message(timestamp, level, context, message, …)
   ├─ time_str   ← constants.TS_FORMAT_FULL          ("%Y-%m-%d %H:%M:%S")
   ├─ level_color ← LEVEL_COLORS[level]              (Colors.* — SSOT)
   └─ context_color ← context_colors[context]
        → "TIMESTAMP [CONTEXT] LEVEL: MESSAGE"   (+ FILE:LINE when include_details)

UnifiedFormatter(logging.Formatter) ── format(record) → format_log_message(…)
```

---

## The canonical line

```
TIMESTAMP [CONTEXT] LEVEL: MESSAGE                       # console / simple
TIMESTAMP [CONTEXT] LEVEL [FILE:LINE]: MESSAGE           # include_details=True (file logs)
```

`format_log_message(timestamp, level, context, message, include_details=False, filename=None, lineno=None, console_colors=True)`:

- **Console** (`console_colors=True`) wraps `[CONTEXT]` and `LEVEL` in ANSI colour + `Colors.RESET`.
- **File** (`include_details=True`) emits **plain text** (no colour) and appends `[filename:lineno]`.
- `console_colors=False` yields the plain line without colour for non-TTY sinks.

> **Inspiration:** the simple, consistent `<priority> $(date) [context]: message` pattern from [mkma](https://github.com/israellevin/mkma).

---

## Single colour truth (`LEVEL_COLORS`)

`formats.py` exposes one module-level `LEVEL_COLORS` map, consumed by **both** `format_log_message` and `format_bootstrap_verbose`. Every value comes from the `Colors` SSOT (`zSys.formatting.colors`) — **no raw ANSI escapes** live in the logger.

| Level | Colour (`Colors.*`) | Intent |
|-------|---------------------|--------|
| `DEBUG` | `PEACH` | subtle |
| `SESSION` | `PRIMARY` | environment / system context |
| `INFO` | `CYAN` | general info |
| `WARNING` | `YELLOW` | warnings |
| `ERROR` | `RED` | errors |
| `CRITICAL` | `ERROR` (red bg) | critical |

A separate `context_colors` map (Bootstrap/Framework/App/SessionFramework) colours the `[CONTEXT]` tag for visual grouping.

> **SSOT/DRY fix (U2):** `format_bootstrap_verbose` previously hard-coded its *own* raw ANSI escapes + a second level→colour dict. It now shares `LEVEL_COLORS` and ends with `Colors.RESET`, so the two formatters can never drift (the `INFO`/verbose shade is now unified to `Colors.CYAN`).

---

## Timestamp formats (`constants.py`)

The three timestamp format strings are single-sourced so they can't drift across files:

| Constant | Value | Used by |
|----------|-------|---------|
| `TS_FORMAT_FULL` | `"%Y-%m-%d %H:%M:%S"` | `format_log_message` (console + file lines) |
| `TS_FORMAT_TIME` | `"%H:%M:%S"` | `format_bootstrap_verbose` (`--verbose`) |
| `TS_FORMAT_TIME_MS` | `"%H:%M:%S.%f"` | `bootstrap` injection + emergency dump (caller slices `[:-3]` for ms) |

> **SSOT/DRY fix (U3):** these literals were scattered across `formats.py`, `bootstrap.py`, and the now-deleted `legacy_formats.py`. `constants.py` is their single home.

---

## `UnifiedFormatter`

A `logging.Formatter` subclass so **Framework** and **App** loggers (stdlib `logging` handlers) produce the same line as Bootstrap:

```python
formatter = UnifiedFormatter("Framework", include_details=True)   # detailed, file/line
formatter = UnifiedFormatter("App", include_details=False)        # simple
handler.setFormatter(formatter)
```

`format(record)` simply forwards the record's timestamp/level/message into `format_log_message`, honouring `include_details` and `console_colors`.

---

## The `SESSION` level (`levels.py`)

A custom level **15**, between `DEBUG` (10) and `INFO` (20), for environment/system context that shouldn't be as loud as `INFO` but should outrank `DEBUG`.

```python
SESSION_LEVEL = 15
SESSION_LEVEL_NAME = "SESSION"

def ensure_session_level() -> int:
    """Register SESSION with the logging module if missing; return its value."""
    if not hasattr(logging, SESSION_LEVEL_NAME):
        logging.addLevelName(SESSION_LEVEL, SESSION_LEVEL_NAME)
        logging.SESSION = SESSION_LEVEL
    return logging.SESSION
```

- **Idempotent** — the `hasattr` guard makes repeated calls safe (it's called from both `config.py` import time and `bootstrap.py`).
- `BootstrapLogger.session(...)` logs at this level; `LEVEL_COLORS["SESSION"]` colours it green (`Colors.PRIMARY`).

---

## Removed: `legacy_formats.py` (D1/D2)

The old `legacy_formats.py` (`FORMAT_SIMPLE`/`FORMAT_DETAILED` `%`-style strings + `DATE_FORMAT`) was re-exported "for backward compatibility" but had **no consumer** in the repo, and its names **collided** with the unrelated `a_zConfig.loggers.constants.FORMAT_SIMPLE` (a format-*type* token). It was deleted and removed from `__init__`; the one live value (`DATE_FORMAT`) is now `TS_FORMAT_FULL` in `constants.py`.

---

## Trust notes

Pure string formatting — no I/O, no exec. `format_*` receive a level/context/message and return a string; colour escapes are constants. Foreign message content is interpolated as **data** (`%`-args in `ConsoleLogger`, plain `{message}` here), never evaluated.

**[← Back to Logger Guide](../logger_GUIDE.md) | [Home](../../../README.md)**
