# zLoader Python Module Cache Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_python_module.py`  
> **Purpose:** LRU cache for dynamically loaded code modules (Python + JS proxies) with collision detection, session injection, and a plugin-trust gate.

---

## Overview

The `cache_python_module` module provides the **`PythonModuleCache`** (Tier 2), the only cache tier that stores executable code. It is the single source of truth for all dynamic module loading in zOS (plugins, functions, etc.).

| Class | File | Purpose |
|---|---|---|
| `PythonModuleCache` | `cache/cache_python_module.py` | Module cache with collision detection + session injection |

> Historical note: earlier docs called this `PluginCache`. The class is `PythonModuleCache`; the orchestrator exposes it as `python_module_cache` (with `plugin_cache` kept as a backward-compatible alias).

---

## Key Features

- **Plugin-trust gate** — `verify_plugin_trust()` is called before any code executes (`exec_module` for `.py`, before registering a `.js` proxy). Permissive in open-core; sealed by zGuard when installed. See [trust_GUIDE.md](trust_GUIDE.md).
- **Collision detection** — loading two different files with the same stem raises `ValueError` (prevents silent overwrites).
- **Session injection** — the live `zos` instance is injected into each module after execution.
- **Mtime invalidation** — `get()` checks file mtime and reloads stale modules.
- **LRU eviction** — `OrderedDict` with `max_size=50` (default).
- **JS support** — `.js` plugins are stored as proxy modules and executed via Node through zFunc.

---

## Architecture: Tier 2 Cache Implementation

```
PythonModuleCache (Tier 2)   keyed by filename stem (e.g. "calculator")
├── Trust gate          — verify_plugin_trust() before execution
├── Module loading      — importlib exec_module (.py) / Node proxy (.js)
├── Session injection   — module.zos = self.zos
├── Collision detection — same stem, different path → ValueError
├── Mtime invalidation  — reload on file change
└── LRU eviction        — max 50 entries
```

---

## Method Reference

Constructor: `PythonModuleCache(session, logger, zos, max_size=50)`.

| Method | Purpose |
|---|---|
| `load_and_cache(file_path, plugin_name=None)` | **Primary entry.** Trust-gate → `exec_module` → inject `zos` → cache. Returns the module. Raises `ValueError` on collision/failure, `PluginTrustError` if denied. |
| `register_js_plugin(file_path, plugin_name=None)` | Trust-gate → register a `.js` proxy module (executed via zFunc). Returns the proxy. |
| `register_import_module(module, module_name, import_path)` | Register an already-imported module (dotted import path; no mtime tracking). |
| `get(plugin_name, default=None)` | Get a cached module; performs mtime freshness check and LRU bump. |
| `set(plugin_name, module, file_path)` | Store a module entry (used internally by `load_and_cache`). |
| `invalidate(plugin_name)` | Remove a single cached module. |
| `clear(pattern=None)` | Clear all, or wildcard-matching entries (via `cache_pattern.matches_pattern`). |
| `get_stats()` | Stats dict: `hits`, `misses`, `hit_rate`, `size`, `max_size`, `loads`, `evictions`, `invalidations`, `collisions`. |
| `list_modules()` | List cached modules with metadata. (`list_plugins()` is a deprecated alias.) |
| `check_and_reload_all()` | Proactively reload any cached modules whose files changed; returns reloaded names. |

> The orchestrator routes `cache_type="plugin"` here. There is no `has()` method — the orchestrator implements `has` as `get()` + a `None` check.

---

## Usage (via the facade)

```python
# Batch load (best-effort; failures don't halt boot)
z.loader.load_plugins(["/path/to/calculator.py", "/path/to/utils.js"])

# Access a loaded plugin
calc = z.loader.get_plugin("calculator")

# Direct module loading
mod = z.loader.load_python_module("/path/to/calculator.py")

# Active hot-reload of all cached modules
reloaded = z.loader.cache.python_module_cache.check_and_reload_all()
```

---

## Integration Points

**Used By:**
- `CacheOrchestrator` (`cache/cache_orchestrator.py`) — routes `cache_type="plugin"`
- zLoader facade (`zLoader.py`) — `load_plugins`, `get_plugin`, `load_python_module`, etc.
- zFunc — invokes cached modules (incl. JS execution) via `&Name.function(...)`

**Depends On:**
- `loader_trust.verify_plugin_trust` — trust gate (zGuard seam)
- `cache_pattern.matches_pattern` — wildcard clearing
- `loader_constants.PluginTrustError` — propagated on denial

**Architecture Position:** Tier 2 (Cache Implementation).

---

## See Also

- [trust_GUIDE.md](trust_GUIDE.md) - Plugin-trust gate (zGuard seam)
- [orchestrator_GUIDE.md](orchestrator_GUIDE.md) - Cache orchestrator (Tier 3)
- [pattern_GUIDE.md](pattern_GUIDE.md) - Wildcard matcher (SSOT)
- [cache_system_GUIDE.md](cache_system_GUIDE.md) - System cache (UI/config)
