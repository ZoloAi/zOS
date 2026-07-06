# zSys Logger — Config Guide

> **Module:** `core/zSys/logger/config.py`
> **Purpose:** Parse logging intent out of zSpark — the **log level** (+ the `z`-prefix framework-trace convention + `PROD` suppression) — and own the **deployment-mode vocabulary SSOT** shared with the foundation network config.

**[← Back to Logger Guide](../logger_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

`config.py` is where raw zSpark values become logging decisions. It answers two questions:

1. **What level do we log at?** — `get_log_level_from_zspark`, the `z`-prefix convention, `PROD` suppression.
2. **Which deployment mode are we in?** — `resolve_deployment_from_zspark` + the `DEPLOYMENT_*` constants, the **SSOT** that `a_zConfig` (L1) imports *down*.

It registers the `SESSION` level at import time (`ensure_session_level()`).

---

## Log-level parsing

```python
LOG_LEVEL_KEY_ALIASES = ("zLog", "zScrap", "logger", "log_level", "logLevel", "zLogger")
```

`get_log_level_from_zspark(zspark_obj)` returns the **first** matching alias's value, upper-cased (or `None`). So `zLog: zInfo` → `"ZINFO"`.

### The `z`-prefix convention (framework trace)

A level prefixed with `z` (e.g. `zDEBUG`, `zINFO`) means *"app-level output at that level **plus** full zOS framework trace"* (ASCII boxes, structured framework logs). The plain level is app-only.

| Helper | Behaviour |
|--------|-----------|
| `is_zos_log_level(level)` | `True` for a `z`-prefixed level (excludes `ZSESSION`) → enable framework trace |
| `get_base_log_level(level)` | Strip the leading `Z` → underlying Python level (`"ZINFO"` → `"INFO"`) |

```
zLog: DEBUG  → app debug only
zLog: zDEBUG → app debug + full zOS framework trace
```

### `PROD` suppression

`LOG_LEVEL_PROD = "PROD"` is a **deprecated** sentinel (prefer `zLog: zINFO`). `should_suppress_init_prints(level)` returns `True` only when the level is `PROD` — used to silence init prints so logs go to file only. `LOG_LEVEL_SESSION = "SESSION"` names the custom level for callers.

---

## Deployment-mode vocabulary (SSOT)

The single home for "which deployment am I?" parsing. The logger needs it (to gate console output); `a_zConfig`'s zServer/WebSocket config needs it (for deployment-aware SSL). Rather than duplicate the key list + values, it is owned **here** and imported **down** by L1.

```python
DEPLOYMENT_KEYS = ("zEnv", "zState", "deployment", "Deployment", "DEPLOYMENT")
DEPLOYMENT_PRODUCTION = "production"
DEPLOYMENT_TESTING    = "testing"
DEPLOYMENT_INFO       = "info"          # deprecated alias for testing
DEPLOYMENT_DEFAULT    = "Development"
ENV_VAR_DEPLOYMENT    = "DEPLOYMENT"
```

### `resolve_deployment_from_zspark(zspark_obj, *, env_fallback=True)`

The one lookup everyone calls. First present `DEPLOYMENT_KEYS` wins; if zSpark is silent and `env_fallback=True`, it reads the `DEPLOYMENT` env var (then `DEPLOYMENT_DEFAULT`).

```python
deployment   = resolve_deployment_from_zspark(zspark_obj)            # raw string
is_production = deployment.lower() == DEPLOYMENT_PRODUCTION
is_testing    = deployment.lower() in (DEPLOYMENT_TESTING, DEPLOYMENT_INFO)
```

`is_production_from_zspark` / `is_testing_from_zspark` are thin predicates over the same `DEPLOYMENT_KEYS` (no env fallback — a missing key is `False`).

> **Why not `zVocabulary`?** The core logger runs **pre-boot** and never imports `zOS.*` at top-level (importing `zOS.zVocabulary` would trigger `zOS/__init__` while the logger is loaded on `main.py`'s first line). So the SSOT lives at the **lowest consumer (L0, here)** and L1 imports *down* — the same pattern as `from zSys.logger import LOG_LEVEL_SESSION`. `zVocabulary` is reserved for tokens whose lowest consumer is L1+.

### Consumers (L1, import DOWN)

| File | Use |
|------|-----|
| `a_zConfig/.../network/config_http_server.py` | `resolve_deployment_from_zspark` → `is_production` / `is_testing` for SSL + runner defaults |
| `a_zConfig/.../network/config_websocket.py` | `resolve_deployment_from_zspark` → `is_production` for WSS auto-enable |

> **SSOT/DRY fix (U1):** the `DEPLOYMENT_KEYS` list + `"production"`/`("testing","info")` values were copy-pasted across these three files (with `is_testing_from_zspark` even using a *narrower* nested-`get`). They now share this single vocabulary + helper; `is_testing_from_zspark` was unified onto `DEPLOYMENT_KEYS`. (`a_zConfig/zConfig.py::is_production` is env-based delegation, a different mechanism — intentionally left alone.)

---

## Trust notes

- **No exec / no network.** Pure dict/string parsing + one `os.getenv("DEPLOYMENT")` read.
- **Foreign values are data** — zSpark values are `str()`-coerced and compared `.lower()`, never interpreted.
- **Fail-closed defaults** — absent keys yield `False` predicates / `DEPLOYMENT_DEFAULT`; deployment-mode never silently escalates to production.

**[← Back to Logger Guide](../logger_GUIDE.md) | [Home](../../../README.md)**
