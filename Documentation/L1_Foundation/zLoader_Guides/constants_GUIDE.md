# zLoader Constants Module Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/loader_constants.py`  
> **Purpose:** Single source of truth for zLoader constants **and** the loader exception hierarchy (Tier 0).

---

## Overview

`loader_constants` centralizes every shared value in zLoader (no magic strings) and defines the exception classes used across the subsystem. It has no dependencies and is imported by every other tier.

---

## Exception Hierarchy

```
LoaderError                  # base — catch-all for the subsystem
├── CacheError               # cache get/set/clear failures
├── FileLoadError            # file I/O failures (not found, permission, read)
├── ValidationError          # fail-fast config/path/type validation
└── PluginTrustError         # plugin denied by the trust policy (zGuard seam)
```

```python
from zOS.L1_Foundation.c_zLoader.loader_modules import (
    LoaderError, CacheError, FileLoadError, ValidationError, PluginTrustError,
)
```

> `PluginTrustError` is part of the public seam so the zGuard wheel can import and raise it; it must propagate unwrapped. See [trust_GUIDE.md](trust_GUIDE.md).

---

## Color Constants

```python
COLOR_LOADER = "LOADER"        # zDisplay color key for zLoader
COLOR_SUBLOADER = "SUBLOADER"  # sub-operation color key
```

---

## Cache Type Constants (orchestrator routing)

```python
CACHE_TYPE_SYSTEM = "system"
CACHE_TYPE_PINNED = "pinned"
CACHE_TYPE_SCHEMA = "schema"
CACHE_TYPE_PLUGIN = "plugin"
CACHE_TYPE_ALL    = "all"
```

## Cache Key Constants

```python
CACHE_KEY_PREFIX = "parsed:"   # system-cache key format: "parsed:{absolute_filepath}"
```

---

## File Type Constants (filename detection)

```python
FILE_TYPE_UI     = "zUI"
FILE_TYPE_SCHEMA = "zSchema"
FILE_TYPE_CONFIG = "zConfig"
```

> Schema files are detected by the **`zSchema` filename prefix** (`zLoader._is_schema`), **not** by extension — `.zolo`, `.json`, `.yaml`, `.yml` are all resolved by zParser. There is intentionally no `SCHEMA_EXTENSION` constant (it was removed as broken/misleading) and no per-extension constants here.

---

## Default Values

```python
DEFAULT_PATH_SYMBOL    = "@"   # workspace-relative path symbol
DEFAULT_SYSTEM_MAX_SIZE = 100  # SystemCache LRU size
DEFAULT_PLUGIN_MAX_SIZE = 50   # PythonModuleCache LRU size
```

## File Constants

```python
PLUGIN_EXTENSION  = ".py"      # Python plugin extension
ZMACHINE_PREFIX   = "zMachine."
FILE_MODE_READ    = "r"
FILE_ENCODING_UTF8 = "utf-8"
```

---

## Session Key Constants

```python
SESSION_KEY_VAFILE   = "zVaFile"     # current UI filename
SESSION_KEY_VAFOLDER = "zVaFolder"   # current folder path
```

## Message Constants

```python
MSG_READY  = "zLoader Ready"
MSG_START  = "zLoader"
MSG_CACHED = "zLoader return (cached)"
MSG_RETURN = "zLoader return"
MSG_READING = "Reading"
```

## Display Style / Indent Constants

```python
STYLE_SINGLE = "single"
STYLE_FULL   = "full"
STYLE_TILDE  = "~"

INDENT_ROOT      = 0
INDENT_PRIMARY   = 1
INDENT_SECONDARY = 2
```

---

## Error Message Templates

Format-string templates (use `.format(...)`):

```python
ERROR_PLUGIN_NOT_FOUND    = "Plugin file not found: {filepath}"
ERROR_PLUGIN_LOAD_FAILED  = "Failed to load plugin: {error}"
ERROR_NO_PARSER           = "zParser subsystem not available"
ERROR_FILE_NOT_FOUND      = "Unable to load zFile (not found): {path}"
ERROR_PERMISSION_DENIED   = "Unable to load zFile (permission denied): {path}"
ERROR_GENERIC             = "Unable to load zFile: {path}"
ERROR_CACHE_MISS          = "Cache miss for key: {key}"
ERROR_INVALID_CACHE_TYPE  = "Invalid cache type: {type}"
ERROR_INVALID_MAX_SIZE    = "Invalid max_size: {value} (must be positive integer)"
ERROR_INVALID_FILE_PATH   = "Invalid file path: {path}"
ERROR_INVALID_CACHE_CONFIG = "Invalid cache configuration: {reason}"
```

---

## Statistics / Kwargs / Log Prefix Keys

```python
# Stats dict keys
STAT_KEY_NAMESPACE, STAT_KEY_SIZE, STAT_KEY_ALIASES,
STAT_KEY_ACTIVE_CONNECTIONS, STAT_KEY_CONNECTIONS,
STAT_KEY_HITS, STAT_KEY_MISSES, STAT_KEY_HIT_RATE

# Method kwargs keys (type-safe routing)
KWARGS_KEY_ZPATH = "zpath"
KWARGS_KEY_FILE_PATH = "file_path"
KWARGS_KEY_DEFAULT = "default"

# Log prefixes
LOG_PREFIX_ORCHESTRATOR  = "[CacheOrchestrator]"
LOG_PREFIX_SYSTEM_CACHE  = "[SystemCache]"
LOG_PREFIX_PINNED_CACHE  = "[PinnedCache]"
LOG_PREFIX_SCHEMA_CACHE  = "[SchemaCache]"
LOG_PREFIX_PLUGIN_CACHE  = "[PythonModuleCache]"
LOG_PREFIX_LOADER_IO     = "[LoaderIO]"
```

---

## Integration Points

**Used By:** every zLoader module (facade, orchestrator, all cache tiers, validator, I/O).  
**Exported By:** `loader_modules/__init__.py`.  
**Architecture Position:** Tier 0 (constants + exceptions; no dependencies).

---

## See Also

- [trust_GUIDE.md](trust_GUIDE.md) - `PluginTrustError` + trust gate
- [orchestrator_GUIDE.md](orchestrator_GUIDE.md) - Cache orchestrator
- [validator_GUIDE.md](validator_GUIDE.md) - Uses `ValidationError` + cache types
- [io_GUIDE.md](io_GUIDE.md) - Uses error/message constants
