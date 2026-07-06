# zLoader Pinned Cache Module Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_pinned.py`  
> **Purpose:** No-eviction cache for user-defined aliases (via zLoad command).

---

## Overview

The `cache_pinned` module provides the Pinned Cache implementation (Tier 2) for zLoader's caching system. It is optimized for user-defined aliases with no automatic eviction.

| Class | File | Purpose |
|---|---|---|
| `PinnedCache` | `cache/cache_pinned.py` | No-eviction cache for user aliases |

---

## Key Features

**No Eviction:**
- User-loaded aliases persist until manually cleared
- Highest priority cache (user intent)
- Unlimited size (bounded only by memory)

**User Control:**
- Loaded via `zLoad` command
- Cleared via `zClear` command
- Listed via `zAlias` command

**Use Cases:**
- Frequently accessed UIs
- Navigation shortcuts
- Development workflows

---

## Architecture: Tier 2 Cache Implementation

`PinnedCache` serves as Tier 2 in the zLoader architecture, implementing no-eviction caching:

```
PinnedCache (Tier 2)
├── No Eviction          — User controls lifetime
├── Alias Management     — Named shortcuts
├── User Control         — Via zDispatch commands
└── Statistics           — Track hits, misses
```

---

## Method Reference

> Method names match the constructor signature `PinnedCache(session, logger)` — there is no `max_size` (no eviction).

### `load_alias(alias_name, parsed_schema, zpath)`

Pin a parsed value into the cache under a named alias.

**Returns:** The cached value (for chaining)

---

### `get_alias(alias_name)`

Get a pinned value by alias.

**Returns:** Cached value or `None` if missing

---

### `has_alias(alias_name)`

Check whether an alias exists.

**Returns:** `True` / `False`

---

### `remove_alias(alias_name)`

Remove a single alias.

**Returns:** `True` if removed, `False` if it didn't exist

---

### `clear(pattern=None)`

Clear pinned aliases. With no `pattern`, clears all; with a wildcard `pattern` (`"zUI*"`, `"*_panel"`, `"*test*"`), clears matching aliases only.

**Returns:** `int` — number of aliases removed

---

### `list_aliases()`

List all pinned aliases with metadata.

**Returns:** `List[Dict]` — each `{name, zpath, ...}`

---

### `get_info(alias_name)`

Get metadata for a single alias.

**Returns:** `Dict` or `None`

> Note: the orchestrator's `get_stats("pinned")` does not call a `get_stats()` on this class — it derives `{namespace, size, aliases}` from `list_aliases()`.

---

## Integration Points

**Used By:**
- CacheOrchestrator (`cache_orchestrator.py`) - Routes pinned cache requests
- zDispatch - zLoad/zClear/zAlias commands

**Architecture Position:**
- Tier 2 (Cache Implementation) - Provides no-eviction caching

---

## See Also

- [orchestrator_GUIDE.md](orchestrator_GUIDE.md) - Cache orchestrator (Tier 3)
- [cache_system_GUIDE.md](cache_system_GUIDE.md) - System cache (LRU eviction)
- [cache_schema_GUIDE.md](cache_schema_GUIDE.md) - Schema cache (DB connections)
- [cache_plugin_GUIDE.md](cache_plugin_GUIDE.md) - Plugin cache (modules)
