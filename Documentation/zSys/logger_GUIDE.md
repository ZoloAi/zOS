# zSys Logger Guide

**[Home](../../README.md) | [zSys Overview](README.md)**

> **Pre-boot & standalone logging — Layer 0**
> One canonical log line reused everywhere, a buffering pre-boot logger that survives a framework that doesn't exist yet, and zSpark-driven log-level + deployment-mode parsing. A pure sink: strings in, formatted text out — it executes nothing.

---

## What It Does

`zSys.logger` is the **floor of the logging stack**. It is imported on the first line of `main.py`, long before `a_zConfig` / the `zOS` instance exist, so it is deliberately **isolated** — stdlib + sibling `zSys.*` only, never `zOS.*` at top-level.

- ✅ **One format truth** — `format_log_message()` defines the single canonical line (`TIMESTAMP [CONTEXT] LEVEL: MESSAGE`) used by Bootstrap, Framework, App, and standalone loggers
- ✅ **Pre-boot buffering** — `BootstrapLogger` captures messages in memory and flushes them into the framework log once it's available, with an **emergency dump** if init fails
- ✅ **Standalone logger** — `ConsoleLogger` gives WSGI workers the same format without the stdlib `logging` machinery
- ✅ **zSpark parsing (SSOT)** — log level (`zLog`/`zScrap`/…), the `z`-prefix framework-trace convention, and **deployment mode** (`zEnv`/`zState`/`deployment`/…) are parsed in one place
- ✅ **Custom `SESSION` level** — a level between `DEBUG` and `INFO` for environment/system context, registered idempotently on the stdlib `logging` module
- ✅ **Single colour/timestamp source** — level→colour map and timestamp formats are single-sourced; colours come from the `Colors` SSOT (no raw ANSI)

**Status:** ✅ Audited + fixed — open-core, CLEAN (no zGuard seam). SSOT/DRY findings U1–U3 + D1–D2 resolved (see [config_GUIDE](logger_Guides/config_GUIDE.md) and [formats_GUIDE](logger_Guides/formats_GUIDE.md)).

> This is a **facade overview**. For deep dives into each module cluster, see the [`logger_Guides/`](logger_Guides/) folder linked below.

---

## Architecture Overview

The logger is a set of small, single-responsibility modules around one format function. Each cluster has its own guide:

| Cluster | Modules | Responsibility | Guide |
|---------|---------|----------------|-------|
| **formats** | `formats.py`, `constants.py`, `levels.py` | The one canonical log line + `UnifiedFormatter`; level→colour map; timestamp-format + `SESSION`-level SSOTs | [formats_GUIDE](logger_Guides/formats_GUIDE.md) |
| **bootstrap** | `bootstrap.py` | `BootstrapLogger`: in-memory pre-boot buffer, flush-to-framework with severity routing, `--verbose`, emergency dump | [bootstrap_GUIDE](logger_Guides/bootstrap_GUIDE.md) |
| **config** | `config.py` | zSpark parsing: log level + `z`-prefix convention + `PROD` suppression, and the **deployment-mode vocabulary SSOT** | [config_GUIDE](logger_Guides/config_GUIDE.md) |
| **runtime** | `console.py`, `execution_context.py` | `ConsoleLogger` (WSGI/standalone) + CLI execution-context diagnostics | [runtime_GUIDE](logger_Guides/runtime_GUIDE.md) |

```
main.py
  └─ BootstrapLogger()                      (bootstrap.py)  ── buffers pre-boot logs in memory
        │  .info/.debug/.session/.error …
        │
        ├─ flush_to_framework(logger_config, verbose)  ── inject buffer → framework/session logs
        │     └─ format_bootstrap_verbose()  (formats.py) ── if --verbose, colored stdout
        └─ emergency_dump(exc)                            ── stderr + .zos-bootstrap-error.log (fail-safe)

format_log_message()  (formats.py)  ── THE canonical line, used by ↓
  ├─ UnifiedFormatter   (logging.Formatter for Framework/App)
  └─ ConsoleLogger      (console.py — WSGI workers)

SSOT:  LEVEL_COLORS → Colors (zSys.formatting)   ·   TS_FORMAT_* (constants.py)
       SESSION level (levels.py)   ·   DEPLOYMENT_* + LOG_LEVEL_* (config.py)
       └─ a_zConfig (L1) imports deployment vocabulary DOWN from here
```

**One format, many loggers:** Bootstrap, Framework, App, and Console output are byte-for-byte consistent because they all resolve to `format_log_message`.

---

## Quick Start

### Pre-boot (the `main.py` pattern)

```python
from zSys.logger import BootstrapLogger

boot_logger = BootstrapLogger()
boot_logger.info("Starting zOS...")
boot_logger.debug("Parsing arguments...")

try:
    cli = zCLI()
    # Inject buffered logs into the framework logger (verbose=True also prints to stdout)
    boot_logger.flush_to_framework(cli.logger, verbose=args.verbose)
except Exception as exc:
    boot_logger.emergency_dump(exc)   # stderr + .zos-bootstrap-error.log
    sys.exit(1)
```

### Standalone (WSGI worker)

```python
from zSys.logger import ConsoleLogger

logger = ConsoleLogger(context="WSGI")
logger.info("Server started on port %d", 8000)
```

### zLog in your zSpark

```yaml
zLog: INFO       # your app's event output only (default)
zLog: zINFO      # app output + zOS engine trace (every internal step zOS takes)
```

The `z` prefix is a toggle: **without it** you see your app; **with it** you also see zOS running underneath it — parser expansions, dispatch routing, render events. Use `z`-prefix only when diagnosing unexpected zOS behaviour; `INFO` is right for everything else.

Valid base levels: `DEBUG` | `INFO` | `WARNING` | `ERROR` — any can be prefixed (`zDEBUG`, `zWARNING`, …).

`zLog` is canonical. `zScrap` is a deprecated alias (accepted, emits a warning).

---

### Parse zSpark (log level + deployment)

```python
from zSys.logger import get_log_level_from_zspark, is_production_from_zspark

level = get_log_level_from_zspark(zspark_obj)      # e.g. "ZINFO", "DEBUG", "PROD", or None
if is_production_from_zspark(zspark_obj):
    ...  # silent console, file-only
```

---

## Public API (facade)

| Member | Description |
|--------|-------------|
| `BootstrapLogger()` | Pre-boot buffering logger (`.debug/.info/.session/.warning/.error/.critical`) |
| `.flush_to_framework(cfg, verbose=False)` | Inject buffered records into the framework logger (severity-routed); optional stdout |
| `.emergency_dump(exc=None)` | Fail-safe dump of the buffer to stderr + a fixed-name CWD file |
| `ConsoleLogger(context)` | Lightweight standalone logger using the unified format (WSGI workers) |
| `UnifiedFormatter(context, include_details, console_colors)` | `logging.Formatter` that routes through `format_log_message` |
| `format_log_message(...)` | The single canonical log-line formatter |
| `format_bootstrap_verbose(ts, level, msg)` | Colored single-line bootstrap output for `--verbose` |
| `get_log_level_from_zspark(zspark)` | Extract log level via key aliases (`zLog`/`zScrap`/`logger`/…) |
| `is_zos_log_level` / `get_base_log_level` | `z`-prefix detection + strip (framework-trace convention) |
| `resolve_deployment_from_zspark(zspark, *, env_fallback=True)` | Raw deployment string (zSpark → `DEPLOYMENT` env → default) — **SSOT** |
| `is_production_from_zspark` / `is_testing_from_zspark` | Deployment-mode predicates |
| `ensure_session_level()` | Idempotently register the custom `SESSION` level (15) |
| `LOG_LEVEL_SESSION` / `LOG_LEVEL_PROD`, `DEPLOYMENT_*` | Level + deployment vocabulary constants |

---

## Trust posture — pure sink, CLEAN

The logger is **fully open-core** and needs **no zGuard seam**.

- **No code-exec / no network** — no `eval`/`exec`/`compile`/`subprocess`/`pickle`/`os.system`, no socket, no bind.
- **One bounded file write** — `emergency_dump` writes a **fixed-name** `.zos-bootstrap-error.log` in `Path.cwd()`, inside try/except (failure is swallowed). No user-controlled path → no traversal.
- **Benign global state** — `ensure_session_level()` registers the `SESSION` level on the stdlib `logging` module behind a `hasattr` guard (idempotent).
- **Foreign content is inert** — anything from a `.zolo`/zSpark reaches the logger only as a **message string**; it is formatted, never interpreted. No Type-A/B/C surface.

> **Info-disclosure (LOW / accepted):** the buffer, `emergency_dump`, and `--verbose` print pre-boot content **verbatim**. If a caller logged a secret pre-boot, it persists. The logger is a **sink** — redaction is the caller's job and is already enforced at the higher layers (`o_zShell` shell-history masking, `r_zRaven` log redaction, `j_zDialog` input masking). No change in the logger itself.

---

## Summary

`zSys.logger` is the **pre-boot logging floor**: one canonical line, a buffering bootstrap logger with a fail-safe emergency dump, a standalone WSGI logger, and a single home for log-level + deployment-mode parsing — all stdlib-only and import-safe before the framework exists.

| Go deeper | Guide |
|-----------|-------|
| The one format line, `UnifiedFormatter`, level→colour + timestamp + `SESSION` SSOTs | [formats_GUIDE](logger_Guides/formats_GUIDE.md) |
| Pre-boot buffering, flush routing, `--verbose`, emergency dump | [bootstrap_GUIDE](logger_Guides/bootstrap_GUIDE.md) |
| zSpark log-level parsing + the deployment-mode vocabulary SSOT | [config_GUIDE](logger_Guides/config_GUIDE.md) |
| `ConsoleLogger` + execution-context diagnostics | [runtime_GUIDE](logger_Guides/runtime_GUIDE.md) |

**Architecture:** one `format_log_message` → many loggers (Bootstrap | Framework | App | Console), with colour/timestamp/level/deployment SSOTs
**Status:** ✅ Audited + fixed (open-core, CLEAN — no zGuard seam)

---

**[Home](../../README.md) | [zSys Overview](README.md)**
