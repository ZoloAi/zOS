# zData Migration Module Guide

> **Module:** `zOS/core/L3_Abstraction/m_zData/zData_modules/migration/`  
> **Purpose:** Automatic schema migrations, conflict detection, and backend-to-backend data transfer.

---

## Overview

The `migration` module provides automatic schema migration capabilities:
- **Schema Discovery** - Auto-detect database schemas
- **Schema Evolution** - Add/remove/modify columns automatically
- **Conflict Detection** - Detect incompatible changes requiring manual intervention
- **Backend Migration** - Transfer data between backends (CSV → SQLite → PostgreSQL)
- **Migration History** - Track applied migrations

---

## Architecture

```
Migration Module
├── migration_engine.py: Schema migration orchestration
├── backend_migration.py: Cross-backend data transfer
├── schema_discovery.py: Auto-detect schemas from databases
├── migration_history.py: Track applied migrations
└── schema_diff.py: Compute schema differences
```

---

## Schema Migration

Automatically evolve schema when structure changes.

### Request Format

```python
request = {
    "model": "@.zSchema.users",
    "action": "migrate"
}
result = zdata.handle_request(request)
```

### What Gets Migrated

**1. Add Column:**
```
Before: users(id, name)
After:  users(id, name, email)
Action: Adds email column, fills with NULL or default value
```

**2. Remove Column:**
```
Before: users(id, name, email)
After:  users(id, name)
Action: Removes email column, backs up dropped data
```

**3. Change Type:**
```
Before: users(age: TEXT)
After:  users(age: INTEGER)
Action: Converts "25" → 25, validates all rows
```

**4. Add Constraint:**
```
Before: users(email: TEXT)
After:  users(email: TEXT NOT NULL)
Action: Validates existing rows, adds constraint
```

---

## Migration Flow

### Step-by-Step Process

1. **Load Current Schema** - From schema file
2. **Discover Backend Schema** - From database
3. **Compute Diff** - Compare current vs backend
4. **Detect Conflicts** - Check for incompatible changes
5. **Generate Migration** - SQL/operations to apply
6. **Apply Migration** - Execute changes
7. **Record History** - Track migration in history table

### Example

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Schema file changed: added email column
# users:
#   id: PK
#   name: TEXT
#   email: TEXT  # <-- NEW

request = {
    "model": "@.zSchema.users",
    "action": "migrate"
}

result = zdata.handle_request(request)
print(result)
# {
#     "success": True,
#     "migrations_applied": [
#         "ALTER TABLE users ADD COLUMN email TEXT"
#     ],
#     "rows_affected": 0
# }
```

---

## Migration Scenarios

### Safe Migrations (Automatic)

These migrations apply automatically without conflicts:

**1. Add Nullable Column:**
```yaml
# Before
users:
  id: PK
  name: TEXT

# After
users:
  id: PK
  name: TEXT
  email: TEXT  # Nullable by default

# Migration: ALTER TABLE users ADD COLUMN email TEXT
```

**2. Add Column with Default:**
```yaml
# After
users:
  email:
    type: TEXT
    default: "unknown@example.com"

# Migration: ALTER TABLE users ADD COLUMN email TEXT DEFAULT 'unknown@example.com'
```

**3. Remove Column:**
```yaml
# Before
users:
  id: PK
  name: TEXT
  email: TEXT

# After
users:
  id: PK
  name: TEXT

# Migration: ALTER TABLE users DROP COLUMN email
# Note: Data backed up before drop
```

**4. Compatible Type Change:**
```yaml
# Before
users:
  age: TEXT  # Contains "25", "30", etc.

# After
users:
  age: INTEGER

# Migration: Converts TEXT → INTEGER if all values are numeric
```

---

### Conflicting Migrations (Manual Intervention)

These migrations require manual intervention:

**1. Incompatible Type Conversion:**
```yaml
# Before
users:
  name: TEXT  # Contains "Alice", "Bob"

# After
users:
  name: INTEGER

# Conflict: Cannot convert "Alice" to INTEGER
# Resolution: Fix data or revert schema change
```

**2. Add Required Field (No Default):**
```yaml
# Before
users:
  id: PK
  name: TEXT

# After
users:
  id: PK
  name: TEXT
  email:
    type: TEXT
    required: true  # <-- No default value

# Conflict: Existing rows have no email value
# Resolution: Add default value or migrate data first
```

**3. Add Unique Constraint with Duplicates:**
```yaml
# Before
users:
  email: TEXT  # Contains duplicates

# After
users:
  email:
    type: TEXT
    unique: true

# Conflict: Duplicate email values exist
# Resolution: Clean up duplicates first
```

### Conflict Response

When conflicts are detected:

```python
result = {
    "success": False,
    "conflict": True,
    "message": "Cannot convert TEXT to INTEGER",
    "field": "age",
    "resolution": "Fix data values or revert schema change"
}
```

---

## Backend Migration

Transfer data between backends.

### Request Format

```python
request = {
    "action": "migrate_backend",
    "source": "@.zSchema.users_csv",      # CSV backend
    "target": "@.zSchema.users_sqlite",   # SQLite backend
}
result = zdata.handle_request(request)
```

### Supported Migrations

| Source | Target | Notes |
|--------|--------|-------|
| CSV → SQLite | ✅ | Type conversion automatic |
| CSV → PostgreSQL | ✅ | Credentials required |
| SQLite → PostgreSQL | ✅ | Full feature migration |
| PostgreSQL → SQLite | ✅ | Some features lost (triggers, procedures) |
| SQLite → CSV | ✅ | Export/backup use case |
| PostgreSQL → CSV | ✅ | Export/backup use case |

### Migration Process

1. **Load Source Schema** - From source backend
2. **Load Target Schema** - From target backend (or create)
3. **Create Target Table** - If doesn't exist
4. **Read All Source Data** - Batch read for performance
5. **Transform Data** - Type conversions, format changes
6. **Insert into Target** - Bulk insert
7. **Validate** - Check row counts match
8. **Report Status** - Success/error summary

### Example: CSV → SQLite

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Source: CSV file
# @.zSchema.users_csv:
#   zMeta:
#     Data_Type: CSV
#     Data_Path: "@.data.users"

# Target: SQLite database
# @.zSchema.users_db:
#   zMeta:
#     Data_Type: SQLite
#     Data_Path: "@.data.users"

request = {
    "action": "migrate_backend",
    "source": "@.zSchema.users_csv",
    "target": "@.zSchema.users_db",
}

result = zdata.handle_request(request)
print(result)
# {
#     "success": True,
#     "rows_migrated": 1523,
#     "source_backend": "CSV",
#     "target_backend": "SQLite"
# }
```

---

## Schema Discovery

Auto-detect schemas from existing databases.

### Request Format

```python
request = {
    "action": "discover_schemas",
    "data_path": "@.data.users"  # SQLite database
}
result = zdata.handle_request(request)
```

### What Gets Discovered

**Tables:**
- Table names
- Column names
- Column types
- Primary keys
- Foreign keys (if supported)
- Indexes (if supported)

**Generates Schema Files:**
```yaml
# Auto-generated: @.zSchema.users_discovered
zMeta:
  Data_Type: SQLite
  Data_Path: "@.data.users"
  Data_Label: users
  Schema_Name: users_db

users:
  id: PK
  name: TEXT
  email: TEXT
  created_at: TIMESTAMP
```

### Example

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Discover schemas from existing database
request = {
    "action": "discover_schemas",
    "data_path": "@.data.existing"
}

result = zdata.handle_request(request)
print(result)
# {
#     "success": True,
#     "tables": ["users", "orders", "products"],
#     "schemas_generated": [
#         "@.zSchema.users_discovered",
#         "@.zSchema.orders_discovered",
#         "@.zSchema.products_discovered"
#     ]
# }
```

---

## Migration History

Track applied migrations to avoid re-applying them.

### History Table

zData creates a `_migration_history` table:

```sql
CREATE TABLE _migration_history (
    id INTEGER PRIMARY KEY,
    migration_name TEXT,
    applied_at TIMESTAMP,
    success BOOLEAN
)
```

### Query History

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Get migration history
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "options": {
        "table": "_migration_history"
    }
}

result = zdata.handle_request(request)
# Returns all applied migrations
```

### History Format

```python
[
    {
        "id": 1,
        "migration_name": "add_email_column",
        "applied_at": "2024-01-15 10:30:00",
        "success": True
    },
    {
        "id": 2,
        "migration_name": "remove_age_column",
        "applied_at": "2024-01-16 14:20:00",
        "success": True
    }
]
```

---

## Type Conversion

During migrations, zData handles type conversions:

### CSV → SQLite

| CSV | SQLite | Conversion |
|-----|--------|------------|
| "123" | INTEGER | Parse string to int |
| "3.14" | REAL | Parse string to float |
| "true" | INTEGER | "true" → 1, "false" → 0 |
| "2024-01-15" | TEXT | ISO format preserved |

### SQLite → PostgreSQL

| SQLite | PostgreSQL | Conversion |
|--------|------------|------------|
| INTEGER | INTEGER | Direct mapping |
| REAL | DOUBLE PRECISION | Direct mapping |
| TEXT | TEXT | Direct mapping |
| BLOB | BYTEA | Binary data |

### PostgreSQL → CSV

| PostgreSQL | CSV | Conversion |
|------------|-----|------------|
| INTEGER | "123" | Number to string |
| DOUBLE PRECISION | "3.14" | Float to string |
| BOOLEAN | "true" | Boolean to string |
| TIMESTAMP | "2024-01-15 10:30:00" | ISO format |

---

## Error Handling

All migration operations include comprehensive error handling:

### Schema Migration Errors

```python
# Conflict detected
{
    "success": False,
    "conflict": True,
    "message": "Cannot convert TEXT to INTEGER",
    "field": "age",
    "resolution": "Fix data or revert schema"
}

# Missing schema
{
    "success": False,
    "error": "Schema file not found: @.zSchema.users"
}

# Backend connection failed
{
    "success": False,
    "error": "Failed to connect to database"
}
```

### Backend Migration Errors

```python
# Source read error
{
    "success": False,
    "error": "Failed to read from source: CSV file not found"
}

# Target write error
{
    "success": False,
    "error": "Failed to write to target: Permission denied"
}

# Row count mismatch
{
    "success": False,
    "error": "Validation failed: 1000 rows read, 998 rows written"
}
```

---

## Best Practices

### 1. Test Migrations on Copy First

```python
# Good: Test on copy
request = {
    "action": "migrate_backend",
    "source": "@.zSchema.users_prod",
    "target": "@.zSchema.users_test",  # Test target first
}

# After validation, migrate to production
request = {
    "action": "migrate_backend",
    "source": "@.zSchema.users_test",
    "target": "@.zSchema.users_prod",
}
```

### 2. Backup Before Migration

```python
# Good: Backup to CSV before migration
request = {
    "action": "migrate_backend",
    "source": "@.zSchema.users_db",
    "target": "@.zSchema.users_backup_csv",
}

# Then apply schema migration
request = {
    "model": "@.zSchema.users_db",
    "action": "migrate"
}
```

### 3. Add Default Values for Required Fields

```yaml
# Good: Default value provided
users:
  email:
    type: TEXT
    required: true
    default: "unknown@example.com"

# Bad: No default (causes conflict)
users:
  email:
    type: TEXT
    required: true
```

### 4. Use Compatible Type Changes

```yaml
# Good: Compatible conversion
users:
  age: TEXT  # Contains "25", "30"
# → migrate to
users:
  age: INTEGER  # Converts successfully

# Bad: Incompatible conversion
users:
  name: TEXT  # Contains "Alice", "Bob"
# → migrate to
users:
  name: INTEGER  # Fails (cannot convert)
```

---

## Performance Considerations

### Large Dataset Migrations

For large datasets (> 100k rows), use batch processing:

```python
# Backend migration uses automatic batching
# Default batch size: 1000 rows
request = {
    "action": "migrate_backend",
    "source": "@.zSchema.large_csv",
    "target": "@.zSchema.large_db",
    "options": {
        "batch_size": 5000  # Adjust based on memory
    }
}
```

### Index Rebuilding

After migrations, indexes may need rebuilding:

```python
# SQLite
adapter.execute("VACUUM")  # Rebuild database

# PostgreSQL
adapter.execute("REINDEX TABLE users")  # Rebuild indexes
```

---

## See Also

- [backends_GUIDE.md](backends_GUIDE.md) - Backend adapter details
- [schema_manager_GUIDE.md](schema_manager_GUIDE.md) - Schema loading and validation
- [ddl_operations_GUIDE.md](ddl_operations_GUIDE.md) - DDL operations (create, drop)
- [crud_operations_GUIDE.md](crud_operations_GUIDE.md) - CRUD operations

---

**[← Back to zData Guide](../zData_GUIDE.md)**
