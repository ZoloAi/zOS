# zLoader Cache Pattern Matcher Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_pattern.py`  
> **Purpose:** Single source of truth (SSOT) for cache-key wildcard matching, shared by all cache tiers.

---

## Overview

`cache_pattern` exposes one function, `matches_pattern()`, used by `SystemCache`, `PinnedCache`, and `PythonModuleCache` whenever they clear by pattern. Previously each cache reimplemented its own matcher with subtle divergence on multi-wildcard patterns; consolidating into one function guarantees identical semantics everywhere (a DRY/SSOT fix).

| Function | File | Purpose |
|---|---|---|
| `matches_pattern(key, pattern)` | `cache/cache_pattern.py` | Wildcard match of a cache key against a pattern |

---

## `matches_pattern(key: str, pattern: str) -> bool`

| Pattern form | Meaning | Example |
|---|---|---|
| `foo` (no `*`) | exact match | `"ui_main"` matches only `ui_main` |
| `foo*` | prefix | `"ui_*"` matches `ui_main`, `ui_users` |
| `*foo` | suffix | `"*_plugin"` matches `calc_plugin` |
| `*foo*` | contains | `"*test*"` matches `my_test_2` |
| `a*b` (interior `*`) | fallback: contains the literal with `*` stripped | `"a*b"` → contains `"ab"` |

```python
from zOS.L1_Foundation.c_zLoader.loader_modules.cache.cache_pattern import matches_pattern

matches_pattern("ui_users", "ui_*")     # True  (prefix)
matches_pattern("calc_plugin", "*_plugin")  # True  (suffix)
matches_pattern("my_test_2", "*test*")  # True  (contains)
matches_pattern("ui_main", "ui_main")   # True  (exact)
```

---

## Where it's used

Each cache's private `_matches_pattern()` now delegates here, and is invoked by `clear(pattern=...)`:

- `SystemCache.clear(pattern)`
- `PinnedCache.clear(pattern)` → returns count removed
- `PythonModuleCache.clear(pattern)`
- (`SchemaCache` does **not** support patterns — `clear()` drops all connections.)

`CacheOrchestrator.clear(cache_type, pattern)` forwards `pattern` to the system/pinned/plugin tiers.

---

## See Also

- [orchestrator_GUIDE.md](orchestrator_GUIDE.md) - Forwards `pattern` to tiers
- [cache_system_GUIDE.md](cache_system_GUIDE.md) - Pattern-based clearing
- [cache_pinned_GUIDE.md](cache_pinned_GUIDE.md) - Pattern-based clearing
- [cache_plugin_GUIDE.md](cache_plugin_GUIDE.md) - Pattern-based clearing
