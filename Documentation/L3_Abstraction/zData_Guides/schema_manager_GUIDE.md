# zData Schema Manager Module Guide

> **Module:** `zOS/core/L3_Abstraction/m_zData/zData_modules/schema_manager.py`  
> **Purpose:** Schema loading, validation, caching, and security (environment variable resolution).

---

## Overview

The `schema_manager` module provides the `SchemaManager` class responsible for:
- Loading schemas from zPath via zLoader
- Validating Meta section for required fields
- Managing schema cache for wizard mode
- Resolving Data_Path from environment variables (security)
- Providing schema context for error messages

---

## Architecture

```
SchemaManager
├── zLoader Integration: Load schemas via zPath notation
├── Meta Validation: Check required fields (Data_Type, Data_Path, etc.)
├── Environment Resolution: Security-first credential loading
├── Wizard Mode Cache: Reuse schemas across requests
└── Error Context: Schema-aware error messages
```

---

## Class: SchemaManager

### Initialization

```python
from zData_modules.schema_manager import SchemaManager

schema_mgr = SchemaManager(zos=z, logger=z.logger)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `zos` | `Any` | zOS framework instance (required) |
| `logger` | `Any` | Logger instance (required) |

---

## Public Methods

### load_schema()

Load and validate schema from model path or cache.

```python
schema = schema_mgr.load_schema(
    model_path="@.zSchema.users",
    context={}
)
```

**Parameters:**
- `model_path` (str): Schema path (e.g., "@.zSchema.users")
- `context` (dict): Optional context with wizard_mode, schema_cache

**Returns:** Schema dict with validated Meta section

**Raises:** `SchemaNotFoundError` if schema cannot be loaded

**Example:**
```python
# Load from file
schema = schema_mgr.load_schema("@.zSchema.users")

# Load with wizard mode caching
context = {"wizard_mode": True, "schema_cache": {}}
schema = schema_mgr.load_schema("@.zSchema.users", context)
```

---

### validate_meta()

Validate Meta section for required fields.

```python
is_valid = schema_mgr.validate_meta(schema)
```

**Parameters:**
- `schema` (dict): Schema dictionary

**Returns:** `True` if valid, raises `ValueError` if invalid

**Validates:**
- `Data_Type` field exists and valid (CSV, SQLite, PostgreSQL, SQL)
- `Data_Path` or `Data_Source` field exists
- `Data_Label` field exists
- `Schema_Name` field exists

**Example:**
```python
schema = {
    "zMeta": {
        "Data_Type": "SQLite",
        "Data_Path": "@.data.users",
        "Data_Label": "users",
        "Schema_Name": "users_db"
    },
    "users": {...}
}

schema_mgr.validate_meta(schema)  # Returns True
```

---

### resolve_data_path()

Resolve Data_Path from environment variables (security).

```python
data_path = schema_mgr.resolve_data_path(schema)
```

**Parameters:**
- `schema` (dict): Schema with Meta section

**Returns:** Resolved Data_Path string

**Security Pattern:**

1. **Check Data_Source first** (environment variable reference):
   ```yaml
   zMeta:
     Data_Source: USERS_DB  # Environment variable name
   ```
   Looks for: `ZDATA_USERS_DB_URL` in `.zEnv` or environment

2. **Fall back to Data_Path** (direct path, warns about security):
   ```yaml
   zMeta:
     Data_Path: "postgresql://user:pass@localhost/db"
   ```
   Logs security warning to move credentials to `.zEnv`

3. **Auto-convention** (infer from Schema_Name):
   ```yaml
   zMeta:
     Schema_Name: users_db
   ```
   Looks for: `ZDATA_USERS_DB_URL` automatically

**Example:**
```python
# .zEnv file:
# ZDATA_USERS_DB_URL=postgresql://user:pass@localhost:5432/mydb

schema = {
    "zMeta": {
        "Data_Type": "PostgreSQL",
        "Data_Source": "USERS_DB",  # Will resolve to ZDATA_USERS_DB_URL
        "Schema_Name": "users_db"
    }
}

data_path = schema_mgr.resolve_data_path(schema)
# Returns: "postgresql://user:pass@localhost:5432/mydb"
```

---

### get_schema_name()

Extract human-readable schema name for error messages.

```python
name = schema_mgr.get_schema_name(model_path, schema)
```

**Parameters:**
- `model_path` (str): Schema path (e.g., "@.zSchema.users")
- `schema` (dict): Optional schema dict

**Returns:** Schema name string

**Example:**
```python
name = schema_mgr.get_schema_name("@.zSchema.users")
# Returns: "users"

name = schema_mgr.get_schema_name(None, {"zMeta": {"Schema_Name": "my_db"}})
# Returns: "my_db"
```

---

## Wizard Mode Caching

Schema caching improves performance in interactive sessions:

```python
context = {
    "wizard_mode": True,
    "schema_cache": {}  # Shared cache
}

# First load reads from file
schema1 = schema_mgr.load_schema("@.zSchema.users", context)

# Second load uses cache (no file I/O)
schema2 = schema_mgr.load_schema("@.zSchema.users", context)

# Cache key format: "alias:$users" (from "@.zSchema.users")
```

**Cache benefits:**
- Avoids redundant file I/O
- Reduces zLoader overhead
- Faster request processing
- Shared across orchestrator lifecycle

**Cache invalidation:**
- Cleared when session ends
- User can manually clear via `schema_cache.clear()`
- Not persisted across zOS restarts

---

## Security: Environment Variable Resolution

**Problem:** Hardcoded credentials in schema files are a security risk.

**Solution:** Store credentials in `.zEnv`, reference via `Data_Source`.

### Three Resolution Strategies

**1. Explicit Data_Source (Recommended):**
```yaml
# Schema file
zMeta:
  Data_Type: PostgreSQL
  Data_Source: USERS_DB  # Reference to environment variable

# .zEnv file
ZDATA_USERS_DB_URL=postgresql://user:pass@localhost:5432/mydb
```

**2. Auto-convention (Inferred):**
```yaml
# Schema file (no Data_Source or Data_Path)
zMeta:
  Data_Type: PostgreSQL
  Schema_Name: users_db

# .zEnv file (auto-inferred from Schema_Name)
ZDATA_USERS_DB_URL=postgresql://user:pass@localhost:5432/mydb
```

**3. Direct Data_Path (Not Recommended):**
```yaml
# Schema file (SECURITY WARNING logged)
zMeta:
  Data_Type: PostgreSQL
  Data_Path: "postgresql://user:pass@localhost:5432/mydb"
```

### Environment Variable Naming Convention

Format: `ZDATA_{UPPERCASE_NAME}_URL`

Examples:
- `USERS_DB` → `ZDATA_USERS_DB_URL`
- `ANALYTICS` → `ZDATA_ANALYTICS_URL`
- `prod_users` → `ZDATA_PROD_USERS_URL`

---

## Error Messages

The schema manager provides detailed error context:

**Schema not found:**
```
Failed to load schema from: @.zSchema.users
Hint: Use 'load @data.users' or provide model path directly
```

**Missing Meta field:**
```
Schema Meta missing required field: 'Data_Type'
Valid options: CSV, SQLite, PostgreSQL, SQL
```

**No connection info:**
```
No database connection info found.
Use Data_Source (env var) or Data_Path in schema Meta.
```

**Cached schema not found (wizard mode):**
```
No cached schema for first-time connection: $users
Hint: Use 'load @data.users' or provide model path directly
```

---

## Integration with zLoader

Schema loading delegates to zLoader for consistent path resolution:

```python
# SchemaManager internally calls:
schema = self.zos.loader.load(model_path)

# Supports all zPath notations:
# - "@.zSchema.users" (workspace-relative)
# - "~/.zSchemas/users" (home directory)
# - "/absolute/path/to/schema" (absolute)
```

See [zLoader Guide](../../L1_Foundation/zLoader_GUIDE.md) for zPath notation details.

---

## Best Practices

### 1. Always Use Data_Source for Production

```yaml
# Good: Data_Source references environment variable
zMeta:
  Data_Type: PostgreSQL
  Data_Source: USERS_DB

# Bad: Hardcoded credentials
zMeta:
  Data_Type: PostgreSQL
  Data_Path: "postgresql://user:pass@localhost/db"
```

### 2. Enable Wizard Mode for Interactive Sessions

```python
# Good: Cache schemas in wizard mode
context = {"wizard_mode": True, "schema_cache": {}}
schema = schema_mgr.load_schema(path, context)

# Bad: Re-load schema every request
schema = schema_mgr.load_schema(path)  # No caching
```

### 3. Validate Meta Early

```python
# Good: Validate before using schema
schema = schema_mgr.load_schema(path)
schema_mgr.validate_meta(schema)

# Bad: Assume schema is valid
# adapter = create_adapter(schema)  # May fail later
```

### 4. Use Auto-convention for Simplicity

```yaml
# Good: Let zData infer environment variable
zMeta:
  Schema_Name: users_db
  # Auto-resolves to ZDATA_USERS_DB_URL

# Explicit is fine too:
zMeta:
  Data_Source: USERS_DB
```

---

## Performance Considerations

**File I/O:**
- Schema loading reads from disk via zLoader
- Wizard mode caching eliminates redundant reads
- Cache hit = O(1) dictionary lookup

**Environment Resolution:**
- Environment variables loaded once at startup
- Subsequent lookups are O(1) from memory
- No repeated .zEnv file parsing

**Validation:**
- Meta validation is fast (dict key checks)
- Performed once per schema load
- Cached schemas skip re-validation

---

## See Also

- [orchestrator_GUIDE.md](orchestrator_GUIDE.md) - Core orchestration logic
- [connection_manager_GUIDE.md](connection_manager_GUIDE.md) - Adapter initialization
- [validators_GUIDE.md](validators_GUIDE.md) - Schema validation rules
- [zLoader Guide](../../L1_Foundation/zLoader_GUIDE.md) - Path resolution and file loading

---

**[← Back to zData Guide](../zData_GUIDE.md)**
