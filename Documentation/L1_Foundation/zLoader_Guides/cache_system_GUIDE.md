# zLoader System Cache Module Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_system.py`  
> **Purpose:** LRU cache for UI and config files with mtime invalidation.

---

## Overview

The `cache_system` module provides the System Cache implementation (Tier 2) for zLoader's caching system. It is optimized for UI files and config files with automatic mtime invalidation. (Schema files are **not** cached here — `zLoader.handle()` detects the `zSchema` prefix and always loads them fresh.)

| Class | File | Purpose |
|---|---|---|
| `SystemCache` | `cache/cache_system.py` | LRU cache with mtime invalidation |

---

## Architecture: Tier 2 Cache Implementation

`SystemCache` serves as Tier 2 in the zLoader architecture, implementing LRU eviction with mtime invalidation:

```
SystemCache (Tier 2)
├── LRU Eviction         — Least Recently Used eviction (max_size=100)
├── Mtime Invalidation   — Auto-reload on file changes
├── Pattern Matching     — Clear by pattern (e.g., "*.yaml")
└── Statistics           — Track hits, misses, evictions
```

**Design rationale:** LRU eviction prevents unbounded memory growth while keeping frequently accessed files cached. Mtime invalidation ensures cache consistency without manual clearing.

---

## `SystemCache`

### Initialization

```python
from zLoader.loader_modules import SystemCache

cache = SystemCache(session, logger, max_size=100)
```

| Parameter | Type | Description |
|---|---|---|
| `session` | `Dict[str, Any]` | zOS session dictionary (for state management) |
| `logger` | `Any` | zOS logger instance (for debug/info logging) |
| `max_size` | `int` | Maximum cache size (default: 100) |

**On init, automatically:**
- Creates empty cache storage (OrderedDict for LRU)
- Creates mtime tracking dict (for invalidation)
- Initializes statistics counters (hits, misses, evictions)
- Logs initialization details

---

## Cache Operations

### Get from Cache

```python
# Get value from cache
data = cache.get("parsed:/path/to/file.yaml", filepath="/path/to/file.yaml")

# Returns:
# - Cached value if hit AND mtime matches
# - None if miss OR mtime changed (invalidated)
```

**Mtime Invalidation:**
- Every `get()` checks file mtime against cached mtime
- If mtime changed: Cache invalidated, returns `None`
- If mtime matches: Cache hit, returns cached value

---

### Set in Cache

```python
# Set value in cache
cache.set("parsed:/path/to/file.yaml", data, filepath="/path/to/file.yaml")

# Returns: Cached value (for chaining)
```

**LRU Eviction:**
- If cache full (`size >= max_size`): Evicts least recently used entry
- New entry added to cache
- Mtime recorded for invalidation
- Statistics updated (evictions counter)

---

### Check Cache

```python
# Check if cache has key
exists = cache.has("parsed:/path/to/file.yaml")

# Returns: True if key exists, False otherwise
```

---

### Clear Cache

```python
# Clear entire cache
cache.clear()

# Clear by wildcard pattern (single clear() method, optional `pattern` arg)
cache.clear(pattern="zUI*")    # Clear keys starting with "zUI"
cache.clear(pattern="*users*") # Clear keys containing "users"
```

> There is no separate `clear_pattern()` method — pattern matching is the optional `pattern` argument to `clear()`, delegated to the shared `cache_pattern.matches_pattern()` matcher.

---

### Other Methods

```python
# Inspect entry metadata without counting a hit
meta = cache.get_metadata("parsed:/path/to/file.zolo")  # {mtime, cached_at, ...} or None

# Invalidate a single key
cache.invalidate("parsed:/path/to/file.zolo")
```

---

### Get Statistics

```python
# Get cache statistics
stats = cache.get_stats()

# Returns:
# {
#     "hits": int,           # Cache hits
#     "misses": int,         # Cache misses
#     "hit_rate": float,     # Hit rate (hits / total)
#     "size": int,           # Current cache size
#     "max_size": int,       # Maximum cache size
#     "evictions": int,      # Number of evictions
# }
```

---

## Cache Key Format

**System cache keys follow this format:**
```
"parsed:{absolute_filepath}"
```

**Examples:**
- `"parsed:/Users/name/workspace/zUI.users.yaml"`
- `"parsed:/Users/name/workspace/zConfig.app.yaml"`
- `"parsed:/Users/name/workspace/zSchema.users.yaml"`

**Why absolute paths?**
- Session-independent consistency
- Same file always uses same cache key
- Prevents duplicate cache entries
- Works across different working directories

---

## Mtime Invalidation Strategy

System cache uses **mtime (modification time) invalidation** to detect file changes:

**How it works:**
1. On `set()`: Record file mtime alongside cached value
2. On `get()`: Check current file mtime vs cached mtime
3. If mtime changed: Invalidate cache entry, return `None`
4. If mtime matches: Return cached value

**Why mtime?**
- **Automatic**: No manual cache clearing needed
- **Reliable**: Detects all file modifications
- **Fast**: OS-level stat call (microseconds)
- **Transparent**: Works without user intervention

**Edge cases handled:**
- File deleted: Returns `None` (cache miss)
- File recreated: Returns `None` (mtime changed)
- File touched: Returns `None` (mtime changed)

---

## LRU Eviction Strategy

System cache uses **LRU (Least Recently Used) eviction** to prevent unbounded memory growth:

**How it works:**
1. Cache has `max_size` limit (default: 100 entries)
2. On `set()`: If cache full, evict least recently used entry
3. On `get()`: Move accessed entry to end (mark as recently used)
4. Eviction happens automatically, no manual management

**Why LRU?**
- **Simple**: Easy to understand and predict
- **Effective**: Keeps frequently accessed files cached
- **Bounded**: Prevents memory exhaustion
- **Automatic**: No manual eviction policy needed

---

## Pattern Matching

System cache supports **pattern-based clearing** for selective cache invalidation, via the `pattern` argument to `clear()`:

**Supported patterns** (prefix `foo*`, suffix `*foo`, substring `*foo*`, exact `foo`):
```python
# Clear keys starting with a prefix
cache.clear(pattern="zUI*")

# Clear keys ending with a suffix
cache.clear(pattern="*.zolo")

# Clear keys containing a substring
cache.clear(pattern="*users*")
```

Matching is performed by the shared `cache_pattern.matches_pattern()` SSOT (see [pattern_GUIDE.md](pattern_GUIDE.md)).

**Use cases:**
- Development: Clear specific file types
- Testing: Reset cache state for specific files
- Debugging: Invalidate suspicious cache entries

---

## Integration Points

**Used By:**
- CacheOrchestrator (`cache_orchestrator.py`) - Routes system cache requests
- zLoader facade (`zLoader.py`) - Indirect via orchestrator

**Delegates To:**
- loader_io (`loader_io.py`) - Raw file I/O for mtime checks
- cache_utils (`cache_utils.py`) - Statistics utilities

**Architecture Position:**
- Tier 2 (Cache Implementation) - Provides LRU caching with mtime invalidation

---

## Best Practices

### When to Use System Cache

**Good for:**
- UI files (zUI.*.yaml)
- Config files (zConfig.*.yaml)
- Static YAML schemas
- Frequently accessed files
- Files that change infrequently

**Not good for:**
- Database schemas (use SchemaCache instead)
- User aliases (use PinnedCache instead)
- Plugin modules (use PythonModuleCache instead)
- Files that change frequently (mtime invalidation overhead)

### Cache Key Best Practices

**Use absolute paths:**
```python
# Good: Absolute path
cache.get("parsed:/Users/name/workspace/zUI.users.yaml", filepath="...")

# Bad: Relative path
cache.get("parsed:zUI.users.yaml", filepath="...")  # Won't work consistently
```

**Use consistent keys:**
```python
# Good: Same key for same file
cache.get("parsed:/workspace/file.yaml", filepath="/workspace/file.yaml")

# Bad: Different keys for same file
cache.get("parsed:file.yaml", filepath="/workspace/file.yaml")
```

### Performance Tips

**Maximize cache hits:**
- Use consistent file paths
- Avoid unnecessary file modifications
- Let mtime invalidation handle updates
- Don't clear cache unless necessary

**Minimize evictions:**
- Increase `max_size` if needed (default: 100)
- Monitor eviction count via `get_stats()`
- Consider using PinnedCache for critical files

---

## See Also

- [orchestrator_GUIDE.md](orchestrator_GUIDE.md) - Cache orchestrator (Tier 3)
- [cache_pinned_GUIDE.md](cache_pinned_GUIDE.md) - Pinned cache (no eviction)
- [cache_schema_GUIDE.md](cache_schema_GUIDE.md) - Schema cache (DB connections)
- [cache_plugin_GUIDE.md](cache_plugin_GUIDE.md) - Plugin cache (modules)
- [utils_GUIDE.md](utils_GUIDE.md) - Cache statistics and utilities
