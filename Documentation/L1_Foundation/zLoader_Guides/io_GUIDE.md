# zLoader I/O Module Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/loader_io.py`  
> **Purpose:** Raw file I/O for zLoader (Tier 1 Foundation).

---

## Overview

`loader_io` is the lowest tier (Tier 1): a single function that reads a file from disk as a UTF-8 string with consistent error handling and optional display feedback. Higher tiers (facade, caches) call it only on a cache miss.

| Function | File | Purpose |
|---|---|---|
| `load_file_raw()` | `loader_io.py` | Read raw file content (UTF-8) |

---

## `load_file_raw(full_path, logger, display=None) -> str`

```python
def load_file_raw(full_path: str, logger: Any, display: Optional[Any] = None) -> str: ...
```

**Parameters**
- `full_path` (str): Absolute path to an existing, readable file.
- `logger` (Any): Logger for debug/error messages.
- `display` (Any, optional): If provided, shows a `"Reading"` message (SUBLOADER color, indent=2) before the read. Defaults to `None`.

**Returns:** Raw file content as a UTF-8 string (whitespace/newlines preserved).

**Raises:** `RuntimeError` for **all** I/O failures, with the original exception chained via `from e`. The message comes from `loader_constants`:
- not found → `ERROR_FILE_NOT_FOUND` → `"Unable to load zFile (not found): {path}"`
- permission → `ERROR_PERMISSION_DENIED` → `"Unable to load zFile (permission denied): {path}"`
- any other error → `ERROR_GENERIC` → `"Unable to load zFile: {path}"`

> Note: failures surface as `RuntimeError` (not `FileNotFoundError`/`IOError`/`UnicodeDecodeError`); the underlying exception is preserved in the chain for tracebacks. `display` is only used for the "Reading" message — errors are logged and raised, not shown via display here.

### Usage

```python
from zOS.L1_Foundation.c_zLoader.loader_modules import load_file_raw

# Without display feedback
content = load_file_raw("/app/config.zolo", logger)

# With display feedback (zCLI / Bifrost modes)
content = load_file_raw("/app/ui.zolo", logger, zos.display)

# Error handling
try:
    content = load_file_raw("/missing.zolo", logger)
except RuntimeError as e:
    print(e)  # "Unable to load zFile (not found): /missing.zolo"
```

---

## Encoding

Files are read with **UTF-8** (`FILE_ENCODING_UTF8`) in read mode (`FILE_MODE_READ`), via a context manager (handle always closed). The entire file is loaded into memory — appropriate for config/UI/schema files.

---

## Integration Points

**Used By:**
- zLoader facade (`zLoader.py`) — on cache miss (`handle()` / `handle_absolute_path()`)
- Cache tiers indirectly via the facade

**Depends On:**
- Python stdlib `open()`
- `loader_constants` — `MSG_READING`, `COLOR_SUBLOADER`, `STYLE_TILDE`, `INDENT_SECONDARY`, `FILE_MODE_READ`, `FILE_ENCODING_UTF8`, `ERROR_*`

**Architecture Position:** Tier 1 (Foundation) — raw file I/O.

---

## Best Practices

- Pass **absolute** paths (resolve via zParser before calling).
- Don't call repeatedly for the same file — let the cache tiers + mtime invalidation handle reuse.
- Catch `RuntimeError` (the single failure type) rather than guessing OS exception classes.

---

## See Also

- [orchestrator_GUIDE.md](orchestrator_GUIDE.md) - Cache orchestrator (Tier 3)
- [cache_system_GUIDE.md](cache_system_GUIDE.md) - System cache (Tier 2)
- [validator_GUIDE.md](validator_GUIDE.md) - Input validation
- [constants_GUIDE.md](constants_GUIDE.md) - Error/message constants
