# zLoader Cache Utilities Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_utils.py`  
> **Purpose:** User-facing helpers to inspect and manage the cache (designed for zShell `func` commands and scripts).

---

## Overview

`cache_utils` provides high-level, `zos`-aware utilities that sit above the facade. Each function takes the `zos` instance (auto-injected when called via a `func` command) and reaches into `zos.loader.cache` to inspect or manage cached files.

> These are plain functions, not a class. They operate on the live caches (`zos.loader.cache.system_cache`, `pinned_cache`).

---

## Function Reference

### `get_cached_files(zos) -> List[str]`

List all currently cached files from the **system** and **pinned** tiers, as human-readable strings.

```python
get_cached_files(zos)
# [
#   "/workspace/zUI.users.zolo (System Cache)",
#   "@.Schemas.zSchema.users → $users (Pinned)",
# ]
```

- System-cache keys have their `"parsed:"` prefix stripped and are tagged `(System Cache)`.
- Pinned entries are rendered as `"{zpath} → ${name} (Pinned)"` from `pinned_cache.list_aliases()`.

---

### `get_cached_files_count(zos) -> Dict[str, Any]`

Return per-tier counts.

```python
get_cached_files_count(zos)
# {"system_cache": 3, "pinned_cache": 2, "total": 5}
```

---

### `clear_system_cache(zos) -> Dict[str, str]`

Clear **only** the system cache (Tier 2); pinned aliases are preserved.

```python
clear_system_cache(zos)
# {"status": "System cache cleared"}
```

Internally calls `zos.loader.cache.clear(cache_type="system")`.

---

### `create_shortcut_from_cache(zos) -> Dict[str, str]`

Interactive wizard (zShell): lists cached files as a numbered menu, prompts for a selection and a shortcut name, validates it, and stores `load <file>` under `session["zShortcuts"][name]`.

```python
create_shortcut_from_cache(zos)
# {"status": "created", "shortcut": "gs", "file": "...", "command": "load ..."}
# or {"status": "cancelled", "reason": "no_cache" | "no_selection" | "empty_name" | "invalid_name" | "exists"}
```

Used by `p_zShell/.../shell_cmd_shortcut.py` (the `shortcut cache` command).

---

## Integration Points

**Used By:**
- zShell `func` commands (interactive cache inspection / shortcut creation)
- Python scripts holding a `zos` instance

**Reads/Writes:**
- `zos.loader.cache.system_cache`, `zos.loader.cache.pinned_cache`
- `zos.session["zShortcuts"]` (shortcut creation)

**Architecture Position:** User-facing utilities above the facade.

---

## See Also

- [orchestrator_GUIDE.md](orchestrator_GUIDE.md) - Cache orchestrator
- [cache_system_GUIDE.md](cache_system_GUIDE.md) - System cache
- [cache_pinned_GUIDE.md](cache_pinned_GUIDE.md) - Pinned cache
