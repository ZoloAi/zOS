# zLoader Cache Orchestrator Module Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_orchestrator.py`  
> **Purpose:** Unified cache routing to all cache tiers (System, Pinned, Schema, Plugin).

---

## Overview

The `cache_orchestrator` module provides the central orchestration layer for zLoader's caching system. It is composed of one public class exposed via `__init__.py`:

| Class | File | Purpose |
|---|---|---|
| `CacheOrchestrator` | `cache_orchestrator.py` | Unified cache router (routes to Tier 2 caches) |

---

## Architecture: Tier 3 Orchestrator

`CacheOrchestrator` serves as Tier 3 in the zLoader architecture, routing cache requests to appropriate Tier 2 implementations:

```
CacheOrchestrator (Tier 3)
├── SystemCache         (.system_cache)         — UI/config files with LRU eviction
├── PinnedCache         (.pinned_cache)         — User aliases with no eviction
├── SchemaCache         (.schema_cache)         — DB connections + transactions
└── PythonModuleCache   (.python_module_cache)  — Python/JS module instances + session injection
```

> The plugin tier class is `PythonModuleCache` (attribute `python_module_cache`). `.plugin_cache` remains as a backward-compatible alias to the same instance. Routing is driven by a `_cache_registry` dict (declarative `cache_type → (instance, method)` map) rather than if/elif chains.

**Design rationale:** Orchestrator pattern provides single point of control, simplifies facade logic, enables batch operations across all tiers.

---

## `CacheOrchestrator`

### Initialization

```python
from zLoader.loader_modules import CacheOrchestrator

orchestrator = CacheOrchestrator(session, logger, zos=None)
```

| Parameter | Type | Description |
|---|---|---|
| `session` | `Dict[str, Any]` | zOS session dictionary (for state management) |
| `logger` | `Any` | zOS logger instance (for debug/info logging) |
| `zos` | `Any \| None` | zOS framework instance (optional, required for plugin cache) |

**On init, automatically:**
- Creates SystemCache (UI/config with LRU eviction, max_size=100)
- Creates PinnedCache (user aliases, no eviction)
- Creates SchemaCache (DB connections + transactions)
- Creates PythonModuleCache (module instances + session injection, max_size=50)
- Builds the `_cache_registry` routing map
- Logs initialization details

> `zos` is optional but recommended: `PythonModuleCache` is always constructed, and `zos` is what gets injected into loaded plugin modules.

---

## Cache Type Routing

The orchestrator routes requests based on `cache_type` parameter:

### System Cache (`cache_type="system"`)

**Purpose:** UI files and config files (schema files bypass the cache — always loaded fresh)  
**Features:** LRU eviction (max_size=100), pattern matching, mtime invalidation  
**Methods (on SystemCache):** `get()`, `set()`, `get_metadata()`, `invalidate()`, `clear()`, `get_stats()`  
**`has` routing:** SystemCache has no `has()` — the orchestrator routes `has()` to `get()` + a `None` check.

```python
# Get from system cache
data = orchestrator.get("parsed:/path/to/file.yaml", cache_type="system", filepath="/path/to/file.yaml")

# Set in system cache
orchestrator.set("parsed:/path/to/file.yaml", data, cache_type="system", filepath="/path/to/file.yaml")
```

**Cache Key Format:** `"parsed:{absolute_filepath}"`

---

### Pinned Cache (`cache_type="pinned"`)

**Purpose:** User-loaded aliases (zLoad command)  
**Features:** No eviction, highest priority, user control  
**Methods:** `get_alias()`, `load_alias()`, `has_alias()`, `clear()`, `get_stats()`

```python
# Get from pinned cache
data = orchestrator.get("users", cache_type="pinned", zpath="@.zUI.users.yaml")

# Set in pinned cache
orchestrator.set("users", data, cache_type="pinned", zpath="@.zUI.users.yaml")
```

**Cache Key Format:** User-defined alias (string)

---

### Schema Cache (`cache_type="schema"`)

**Purpose:** Database connections, transaction management  
**Features:** Dual storage (in-memory connections + session metadata)  
**Methods:** `get_connection()`, `set_connection()`, `has_connection()`, `clear()`, `get_stats()`

```python
# Get from schema cache
connection = orchestrator.get("users", cache_type="schema")

# Set in schema cache
orchestrator.set("users", connection, cache_type="schema")
```

**Cache Key Format:** Schema name (string)

---

### Plugin Cache (`cache_type="plugin"`)

**Purpose:** Dynamically loaded plugin modules (Python and JS proxies)  
**Backed by:** `PythonModuleCache` (`python_module_cache`)  
**Features:** Collision detection, session injection, mtime invalidation, LRU, **plugin-trust gate before execution**  
**Registry methods:** `get`, `set`, `clear`, `get_stats`, plus `load` → `load_and_cache` and `invalidate`. `has` routes to `get()` + `None` check (no dedicated `has()`).

```python
# Get from plugin cache
plugin = orchestrator.get("my_plugin", cache_type="plugin", file_path="/path/to/plugin.py")

# Set in plugin cache
orchestrator.set("my_plugin", plugin, cache_type="plugin", file_path="/path/to/plugin.py")
```

**Cache Key Format:** Plugin name (string)

---

### Batch Operations (`cache_type="all"`)

**Purpose:** Operations across all cache tiers  
**Features:** Aggregates results from all 4 caches  
**Methods:** `clear()`, `get_stats()`

```python
# Clear all cache tiers
orchestrator.clear("all")

# Get stats from all tiers
stats = orchestrator.get_stats("all")
# Returns: {"total_hits": int, "total_misses": int, "hit_rate": float, ...}
```

---

## Method Reference

### `get(cache_key, cache_type, **kwargs)`

Get value from cache tier.

**Parameters:**
- `cache_key` (str): Cache key (format varies by tier)
- `cache_type` (str): Cache tier ("system", "pinned", "schema", "plugin")
- `**kwargs`: Tier-specific parameters (e.g., `filepath`, `zpath`)

**Returns:** Cached value or `None` if miss

**Example:**
```python
# System cache
data = orchestrator.get("parsed:/path/to/file.yaml", "system", filepath="/path/to/file.yaml")

# Pinned cache
data = orchestrator.get("users", "pinned", zpath="@.zUI.users.yaml")
```

---

### `set(cache_key, value, cache_type, **kwargs)`

Set value in cache tier.

**Parameters:**
- `cache_key` (str): Cache key (format varies by tier)
- `value` (Any): Value to cache
- `cache_type` (str): Cache tier ("system", "pinned", "schema", "plugin")
- `**kwargs`: Tier-specific parameters (e.g., `filepath`, `zpath`)

**Returns:** Cached value (for chaining)

**Example:**
```python
# System cache
orchestrator.set("parsed:/path/to/file.yaml", data, "system", filepath="/path/to/file.yaml")

# Plugin cache
orchestrator.set("my_plugin", plugin, "plugin", file_path="/path/to/plugin.py")
```

---

### `has(cache_key, cache_type)`

Check if cache tier has key.

**Parameters:**
- `cache_key` (str): Cache key (format varies by tier)
- `cache_type` (str): Cache tier ("system", "pinned", "schema", "plugin")

**Returns:** `True` if key exists, `False` otherwise

**Example:**
```python
# Check system cache
exists = orchestrator.has("parsed:/path/to/file.yaml", "system")

# Check pinned cache
exists = orchestrator.has("users", "pinned")
```

---

### `clear(cache_type="all", pattern=None)`

Clear cache tier(s), optionally by wildcard pattern.

**Parameters:**
- `cache_type` (str): Cache tier to clear ("system", "pinned", "schema", "plugin", "all"). Default: `"all"`.
- `pattern` (str | None): Wildcard pattern for selective clearing (`"zUI*"`, `"*_plugin"`, `"*test*"`). Honored by system, pinned, and plugin tiers; the schema tier ignores it and clears all connections.

**Returns:** `None`

**Example:**
```python
# Clear all tiers
orchestrator.clear()                 # cache_type defaults to "all"
orchestrator.clear("all")

# Clear a specific tier
orchestrator.clear("system")

# Selective clear by pattern
orchestrator.clear("system", pattern="zUI*")
```

---

### `get_stats(cache_type)`

Get cache statistics.

**Parameters:**
- `cache_type` (str): Cache tier ("system", "pinned", "schema", "plugin", "all")

**Returns:** Dict **keyed by tier name** (`system_cache`, `pinned_cache`, `schema_cache`, `plugin_cache`); each value is that tier's own stats dict. It is not a flattened total.

**Example:**
```python
# Get stats from all tiers
stats = orchestrator.get_stats("all")
print(stats["system_cache"]["hit_rate"])    # e.g. "83.3%"
print(stats["plugin_cache"]["collisions"])

# Get stats from a specific tier (still tier-keyed)
system_stats = orchestrator.get_stats("system")["system_cache"]
print(f"Cache size: {system_stats['size']}/{system_stats['max_size']}")
```

**Per-tier shapes:**
- `system_cache` / `plugin_cache`: full stats (`hits`, `misses`, `hit_rate`, `size`, `max_size`, `evictions`, `invalidations`; plugin adds `loads`, `collisions`)
- `pinned_cache`: `namespace`, `size`, `aliases`
- `schema_cache`: `namespace`, `active_connections`, `connections`

---

## Integration Points

**Used By:**
- zLoader facade (`zLoader.py`) - Main consumer

**Delegates To:**
- SystemCache (`cache/cache_system.py`)
- PinnedCache (`cache/cache_pinned.py`)
- SchemaCache (`cache/cache_schema.py`)
- PythonModuleCache (`cache/cache_python_module.py`)

**Architecture Position:**
- Tier 3 (Orchestrator) - Routes requests to Tier 2 implementations

---

## Best Practices

### When to Use Each Tier

**System Cache:**
- UI files that change infrequently
- Config files shared across commands
- Static YAML schemas

**Pinned Cache:**
- User-defined aliases (via zLoad command)
- Frequently accessed UIs needing persistent cache
- Navigation shortcuts

**Schema Cache:**
- Database connections (expensive to recreate)
- Transaction management
- Session-based connection pooling

**Plugin Cache:**
- Dynamically loaded modules
- Custom functions/classes
- Plugin instances with session injection

### Cache Key Best Practices

**System Cache Keys:**
- Use absolute paths for consistency
- Format: `"parsed:{absolute_filepath}"`
- Example: `"parsed:/Users/name/workspace/zUI.users.yaml"`

**Pinned Cache Keys:**
- Use meaningful aliases
- Format: User-defined string
- Example: `"users"`, `"settings"`, `"admin_panel"`

**Schema Cache Keys:**
- Use schema names
- Format: Schema identifier string
- Example: `"users"`, `"products"`, `"orders"`

**Plugin Cache Keys:**
- Use plugin names
- Format: Plugin identifier string
- Example: `"my_plugin"`, `"data_processor"`

---

## See Also

- [cache_system_GUIDE.md](cache_system_GUIDE.md) - System cache implementation
- [cache_pinned_GUIDE.md](cache_pinned_GUIDE.md) - Pinned cache implementation
- [cache_schema_GUIDE.md](cache_schema_GUIDE.md) - Schema cache implementation
- [cache_plugin_GUIDE.md](cache_plugin_GUIDE.md) - Plugin cache implementation
- [utils_GUIDE.md](utils_GUIDE.md) - Cache statistics and utilities
