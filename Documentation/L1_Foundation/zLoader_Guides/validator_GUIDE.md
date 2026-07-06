# zLoader Validator Module Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/loader_validator.py`  
> **Purpose:** Fail-fast validation of cache configuration, file paths, cache types, and session structure.

---

## Overview

`LoaderValidator` is a **stateless** validator that catches bad inputs *before* operations run, following a_zConfig's `ConfigValidator` pattern. All checks raise `ValidationError` (from `loader_constants`) with a clear message.

> Scope note: this module does **not** do format detection or file-type sniffing. Path resolution and format/extension handling live in **zParser** (`identify_zFile`, `parse_file_content`), and schema detection is `zLoader._is_schema` (the `zSchema` filename prefix). The validator only checks structural validity of inputs.

| Class | File | Purpose |
|---|---|---|
| `LoaderValidator` | `loader_validator.py` | Fail-fast input validation |

---

## Method Reference

### `validate_cache_config(cache_config: Dict) -> None`

Validates a cache config dict:
- must be a `dict`
- `max_size` (if present) must be a positive `int`
- `cache_type` (if present) must be valid (delegates to `validate_cache_type`)

```python
validator.validate_cache_config({"max_size": 100})   # OK
validator.validate_cache_config({"max_size": -1})     # ValidationError
```

---

### `validate_file_path(file_path, must_exist=False, must_be_absolute=True) -> None`

Validates a path string/`Path`:
- non-empty `str`/`Path`
- absolute (when `must_be_absolute=True`, the default)
- exists on disk (when `must_exist=True`)

```python
validator.validate_file_path("/abs/path/file.zolo")              # OK
validator.validate_file_path("relative/file.zolo")               # ValidationError (not absolute)
validator.validate_file_path("/missing.zolo", must_exist=True)   # ValidationError (file not found)
```

---

### `validate_cache_type(cache_type: str) -> None`

Validates against `VALID_CACHE_TYPES = ("system", "pinned", "schema", "plugin", "all")`. Case-sensitive.

```python
validator.validate_cache_type("system")    # OK
validator.validate_cache_type("unknown")    # ValidationError (lists valid types)
```

---

### `validate_session_structure(session: Dict, namespace: str) -> None`

Checks `session` is a dict and (if `namespace` is given) that the namespace key exists.

```python
validator.validate_session_structure({"zCache": {...}}, "zCache")  # OK
validator.validate_session_structure({}, "zCache")                  # ValidationError
```

---

## Integration Points

**Used By:**
- `zLoader` (facade) — validates configuration / paths
- `CacheOrchestrator` — validates `cache_type` before routing

**Raises:** `ValidationError` (defined in `loader_constants`, part of the `LoaderError` hierarchy).

**Architecture Position:** Support module (Tier 2.5 — validation between facade and operations).

---

## See Also

- [constants_GUIDE.md](constants_GUIDE.md) - `ValidationError` + cache-type constants
- [io_GUIDE.md](io_GUIDE.md) - Raw file I/O
- [orchestrator_GUIDE.md](orchestrator_GUIDE.md) - Cache orchestrator
