# zData DDL Operations Module Guide

> **Module:** `zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/`  
> **Purpose:** Data Definition Language operations for table management (create, drop, alter, head).

---

## Overview

The `operations` module provides DDL operation handlers:
- **CREATE** - Create tables from schema definitions
- **DROP** - Drop/delete tables
- **HEAD** - Show table structure/columns
- **LIST_TABLES** - List all tables in database
- **ALTER** - Modify table structure (via migrations)

---

## Supported Operations

| Operation | Action | Description | Handler File |
|-----------|--------|-------------|--------------|
| **CREATE** | `create` | Create table from schema | `ddl_create.py` |
| **DROP** | `drop` | Drop/delete table | `ddl_drop.py` |
| **HEAD** | `head` | Show table schema/columns | `ddl_head.py` |
| **LIST_TABLES** | `list_tables` | List all tables | Backend adapter |

---

## CREATE Operation

Create tables from schema definitions.

### Request Format

```python
request = {
    "model": "@.zSchema.users",
    "action": "create"
}
result = zdata.handle_request(request)
```

### What Happens

1. **Load Schema** - From schema file
2. **Parse Meta** - Extract Data_Type, Data_Path, etc.
3. **Connect Backend** - Initialize adapter
4. **Check Existence** - Verify table doesn't exist
5. **Create Table** - Execute backend-specific CREATE
6. **Return Result** - Success/error status

### Schema Definition

```yaml
# @.zSchema.users
zMeta:
  Data_Type: SQLite
  Data_Path: "@.data.users"
  Data_Label: users
  Schema_Name: users_db

users:
  id: PK
  name: TEXT
  email: TEXT
  age: INTEGER
  created_at: TIMESTAMP
```

### Generated SQL (SQLite)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    age INTEGER,
    created_at TEXT
)
```

### Generated SQL (PostgreSQL)

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name TEXT,
    email TEXT,
    age INTEGER,
    created_at TIMESTAMP
)
```

### Return Format

```python
{
    "success": True,
    "table": "users",
    "backend": "SQLite"
}
```

---

## DROP Operation

Drop/delete tables from database.

### Request Format

```python
request = {
    "model": "@.zSchema.users",
    "action": "drop"
}
result = zdata.handle_request(request)
```

### Safety Confirmation

**DROP is destructive** - all data is lost permanently. Consider:

```python
# Backup before drop
request = {
    "action": "migrate_backend",
    "source": "@.zSchema.users",
    "target": "@.zSchema.users_backup"
}
zdata.handle_request(request)

# Then drop
request = {
    "model": "@.zSchema.users",
    "action": "drop"
}
zdata.handle_request(request)
```

### What Happens

1. **Load Schema** - From schema file
2. **Connect Backend** - Initialize adapter
3. **Check Existence** - Verify table exists
4. **Drop Table** - Execute backend-specific DROP
5. **Return Result** - Success/error status

### Generated SQL

```sql
DROP TABLE users
```

### Return Format

```python
{
    "success": True,
    "table": "users",
    "backend": "SQLite"
}
```

### Error Handling

```python
# Table doesn't exist
{
    "success": False,
    "error": "Table 'users' does not exist"
}

# Foreign key constraint
{
    "success": False,
    "error": "Cannot drop table: referenced by foreign key"
}
```

---

## HEAD Operation

Show table structure/columns.

### Request Format

```python
request = {
    "model": "@.zSchema.users",
    "action": "head"
}
result = zdata.handle_request(request)
```

### What Happens

1. **Load Schema** - From schema file
2. **Connect Backend** - Initialize adapter
3. **Query Structure** - Get columns from backend
4. **Return Schema** - Table structure

### Return Format

```python
{
    "success": True,
    "table": "users",
    "columns": [
        {
            "name": "id",
            "type": "INTEGER",
            "primary_key": True,
            "nullable": False
        },
        {
            "name": "name",
            "type": "TEXT",
            "primary_key": False,
            "nullable": True
        },
        {
            "name": "email",
            "type": "TEXT",
            "primary_key": False,
            "nullable": True
        },
        {
            "name": "age",
            "type": "INTEGER",
            "primary_key": False,
            "nullable": True
        },
        {
            "name": "created_at",
            "type": "TIMESTAMP",
            "primary_key": False,
            "nullable": True
        }
    ]
}
```

### Use Cases

- Schema inspection
- Table documentation
- Migration planning
- Debug schema mismatches

---

## LIST_TABLES Operation

List all tables in database.

### Request Format

```python
request = {
    "model": "@.zSchema.any",  # Any schema from the database
    "action": "list_tables"
}
result = zdata.handle_request(request)
```

### What Happens

1. **Load Schema** - Get database connection info
2. **Connect Backend** - Initialize adapter
3. **Query Tables** - Backend-specific table list query
4. **Return List** - All table names

### Return Format

```python
{
    "success": True,
    "tables": ["users", "orders", "products", "customers"],
    "count": 4,
    "backend": "SQLite"
}
```

### Backend Queries

**SQLite:**
```sql
SELECT name FROM sqlite_master WHERE type='table'
```

**PostgreSQL:**
```sql
SELECT tablename FROM pg_tables WHERE schemaname='public'
```

**CSV:**
```python
# Lists all .csv files in data directory
```

---

## CREATE with Constraints

Define constraints in schema for advanced table creation.

### Primary Key

```yaml
users:
  id: PK  # Auto-increment primary key
```

### Unique Constraint

```yaml
users:
  email:
    type: TEXT
    unique: true
```

### Not Null Constraint

```yaml
users:
  name:
    type: TEXT
    required: true  # Translates to NOT NULL
```

### Default Values

```yaml
users:
  status:
    type: TEXT
    default: "active"
  created_at:
    type: TIMESTAMP
    default: "CURRENT_TIMESTAMP"
```

### Foreign Keys (PostgreSQL/SQLite)

```yaml
orders:
  id: PK
  user_id:
    type: INTEGER
    foreign_key:
      table: users
      column: id
```

### Generated SQL (Advanced)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
```

---

## CREATE Multiple Tables

Create multiple tables from one schema.

### Schema Definition

```yaml
# @.zSchema.app
zMeta:
  Data_Type: SQLite
  Data_Path: "@.data.app"
  Data_Label: users  # Primary table
  Schema_Name: app_db

users:
  id: PK
  name: TEXT
  email: TEXT

orders:
  id: PK
  user_id: INTEGER
  total: REAL

products:
  id: PK
  name: TEXT
  price: REAL
```

### Request Format

```python
# Create all tables
request = {
    "model": "@.zSchema.app",
    "action": "create",
    "options": {
        "tables": "all"  # Create all tables in schema
    }
}

# Create specific tables
request = {
    "model": "@.zSchema.app",
    "action": "create",
    "options": {
        "tables": ["users", "orders"]  # Only these tables
    }
}
```

---

## Table Existence Check

Check if table exists before operations.

### Request Format

```python
from shared.backends.adapter_factory import AdapterFactory

adapter = AdapterFactory.create_adapter(...)
exists = adapter.table_exists("users")

if not exists:
    # Create table
    zdata.handle_request({"action": "create", ...})
```

### Use Cases

- Avoid duplicate table creation
- Conditional migrations
- Setup scripts
- Testing

---

## Error Handling

All DDL operations return structured errors:

### CREATE Errors

```python
# Table already exists
{
    "success": False,
    "error": "Table 'users' already exists"
}

# Invalid schema
{
    "success": False,
    "error": "Schema validation failed: missing Data_Type"
}

# Connection failed
{
    "success": False,
    "error": "Failed to connect to database"
}
```

### DROP Errors

```python
# Table doesn't exist
{
    "success": False,
    "error": "Table 'users' does not exist"
}

# Foreign key constraint
{
    "success": False,
    "error": "Cannot drop table: foreign key constraint"
}
```

### HEAD Errors

```python
# Table doesn't exist
{
    "success": False,
    "error": "Table 'users' does not exist"
}

# Connection failed
{
    "success": False,
    "error": "Failed to query table structure"
}
```

---

## Best Practices

### 1. Check Existence Before CREATE

```python
# Good: Check first
adapter = get_adapter()
if not adapter.table_exists("users"):
    zdata.handle_request({"action": "create", ...})

# Bad: Assume table doesn't exist
zdata.handle_request({"action": "create", ...})
# May error if table exists
```

### 2. Backup Before DROP

```python
# Good: Backup first
zdata.handle_request({
    "action": "migrate_backend",
    "source": "@.zSchema.users",
    "target": "@.zSchema.users_backup"
})
zdata.handle_request({"action": "drop", ...})

# Bad: Drop without backup
zdata.handle_request({"action": "drop", ...})
# Data lost forever
```

### 3. Define Constraints in Schema

```yaml
# Good: Explicit constraints
users:
  email:
    type: TEXT
    unique: true
    required: true

# Bad: No constraints (data integrity issues)
users:
  email: TEXT
```

### 4. Use Foreign Keys for Relationships

```yaml
# Good: Foreign key constraint
orders:
  user_id:
    type: INTEGER
    foreign_key:
      table: users
      column: id

# Bad: No relationship enforcement
orders:
  user_id: INTEGER
```

---

## Backend-Specific Features

### SQLite

- **AUTOINCREMENT** - PK fields use AUTOINCREMENT
- **Foreign Keys** - Supported but disabled by default (enable with PRAGMA)
- **Transactions** - DDL operations are transactional

### PostgreSQL

- **SERIAL** - PK fields use SERIAL type
- **Foreign Keys** - Fully supported and enforced
- **Transactions** - DDL operations are transactional
- **Schemas** - Support for schemas beyond public

### CSV

- **Table = File** - Each table is a CSV file
- **No DDL** - CREATE/DROP operations are file operations
- **No Constraints** - No foreign keys, unique, etc.

---

## Performance Considerations

### Large Tables

Creating large tables can be slow:

```python
# Good: Create table, then bulk insert
zdata.handle_request({"action": "create", ...})
zdata.handle_request({
    "action": "insert",
    "data": large_dataset,  # Bulk insert
})

# Bad: Create table with many inserts
zdata.handle_request({"action": "create", ...})
for row in large_dataset:
    zdata.handle_request({"action": "insert", "data": row})
```

### Indexes

Create indexes for frequently queried fields:

```sql
-- After CREATE, add indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_orders_user_id ON orders(user_id);
```

---

## See Also

- [crud_operations_GUIDE.md](crud_operations_GUIDE.md) - CRUD operations
- [migration_GUIDE.md](migration_GUIDE.md) - Schema migrations (ALTER operations)
- [backends_GUIDE.md](backends_GUIDE.md) - Backend-specific DDL
- [schema_manager_GUIDE.md](schema_manager_GUIDE.md) - Schema definitions

---

**[← Back to zData Guide](../zData_GUIDE.md)**
