# zData CRUD Operations Module Guide

> **Module:** `zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/`  
> **Purpose:** Create, Read, Update, Delete, and Upsert operations with validation and hooks.

---

## Overview

The `operations` module provides CRUD operation handlers that:
- Route operations to backend adapters
- Execute validation via DataValidator
- Execute zFunc hooks (onBeforeInsert, onAfterInsert, etc.)
- Handle errors gracefully with logging
- Return normalized results

---

## Architecture

```
CRUD Operations
├── crud_insert.py: Insert operation handler
├── crud_read.py: Read/query operation handler
├── crud_update.py: Update operation handler
├── crud_delete.py: Delete operation handler
├── crud_upsert.py: Upsert (insert or update) handler
└── helpers.py: Shared utilities (validation, hooks, errors)
```

---

## Supported Operations

| Operation | Action | Description | Handler File |
|-----------|--------|-------------|--------------|
| **INSERT** | `insert` | Insert new rows | `crud_insert.py` |
| **READ** | `read` | Query rows (with WHERE, JOIN, etc.) | `crud_read.py` |
| **UPDATE** | `update` | Update existing rows | `crud_update.py` |
| **DELETE** | `delete` | Delete rows | `crud_delete.py` |
| **UPSERT** | `upsert` | Insert or update (conflict resolution) | `crud_upsert.py` |

---

## INSERT Operation

Insert new rows into a table.

### Request Format

```python
request = {
    "model": "@.zSchema.users",
    "action": "insert",
    "data": {
        "name": "Alice",
        "email": "alice@example.com",
        "created_at": "2024-01-15 10:30:00"
    }
}
```

### Bulk Insert

```python
request = {
    "model": "@.zSchema.users",
    "action": "insert",
    "data": [
        {"name": "Bob", "email": "bob@example.com"},
        {"name": "Carol", "email": "carol@example.com"},
        {"name": "Dave", "email": "dave@example.com"},
    ]
}
```

### What Happens

1. **Validation** - Data validated against schema
2. **onBeforeInsert Hook** - Execute if defined
3. **Adapter Insert** - Backend-specific insert
4. **onAfterInsert Hook** - Execute if defined
5. **Return Result** - Inserted data with generated IDs

### Return Format

```python
{
    "success": True,
    "data": [
        {"id": 1, "name": "Alice", "email": "alice@example.com", ...}
    ],
    "count": 1
}
```

### Hooks

```yaml
# Schema definition
users:
  zFunc:
    onBeforeInsert: "@.zFunc.hash_password"
    onAfterInsert: "@.zFunc.send_welcome_email"
```

---

## READ Operation

Query rows from a table with flexible filters.

### Basic Query

```python
request = {
    "model": "@.zSchema.users",
    "action": "read"
}
# Returns all rows
```

### WHERE Clause

```python
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "where": "name = 'Alice'"
}

# Complex conditions
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "where": "age > 18 AND status = 'active'"
}

# Pattern matching
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "where": "email LIKE '%@example.com'"
}
```

### Supported WHERE Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Equals | `name = 'Alice'` |
| `!=` | Not equals | `status != 'deleted'` |
| `<` | Less than | `age < 18` |
| `<=` | Less than or equal | `age <= 65` |
| `>` | Greater than | `score > 100` |
| `>=` | Greater than or equal | `score >= 50` |
| `LIKE` | Pattern match | `name LIKE 'A%'` |
| `IN` | Value in list | `status IN ('active', 'pending')` |
| `BETWEEN` | Range | `age BETWEEN 18 AND 65` |
| `IS NULL` | Null check | `deleted_at IS NULL` |
| `IS NOT NULL` | Not null check | `email IS NOT NULL` |
| `AND` | Logical AND | `age > 18 AND status = 'active'` |
| `OR` | Logical OR | `role = 'admin' OR role = 'moderator'` |

### JOIN Operations

```python
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "join": {
        "type": "INNER",
        "table": "orders",
        "on": "users.id = orders.user_id"
    }
}

# LEFT JOIN
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "join": {
        "type": "LEFT",
        "table": "orders",
        "on": "users.id = orders.user_id"
    },
    "where": "orders.total > 100"
}
```

### Sorting & Pagination

```python
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "order_by": "name ASC",
    "limit": 10,
    "offset": 20
}
```

### Field Selection

```python
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "fields": ["id", "name", "email"]  # Only these fields
}
```

### Return Format

```python
{
    "success": True,
    "data": [
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob", "email": "bob@example.com"},
    ],
    "count": 2
}
```

---

## UPDATE Operation

Modify existing rows in a table.

### Request Format

```python
request = {
    "model": "@.zSchema.users",
    "action": "update",
    "data": {"email": "alice.new@example.com"},
    "where": "name = 'Alice'"
}
```

### What Happens

1. **Validation** - WHERE clause required (safety)
2. **Data Validation** - New data validated against schema
3. **onBeforeUpdate Hook** - Execute if defined
4. **Adapter Update** - Backend-specific update
5. **onAfterUpdate Hook** - Execute if defined
6. **Return Result** - Number of rows updated

### Safety

**Always include a WHERE clause** to avoid updating all rows:

```python
# Good: Specific WHERE clause
request = {
    "action": "update",
    "data": {"status": "inactive"},
    "where": "last_login < '2023-01-01'"
}

# Bad: No WHERE clause (updates ALL rows)
request = {
    "action": "update",
    "data": {"status": "inactive"}
}
# Returns error: "WHERE clause required for update"
```

### Return Format

```python
{
    "success": True,
    "rows_affected": 1
}
```

### Hooks

```yaml
users:
  zFunc:
    onBeforeUpdate: "@.zFunc.validate_update"
    onAfterUpdate: "@.zFunc.log_change"
```

---

## DELETE Operation

Remove rows from a table.

### Request Format

```python
request = {
    "model": "@.zSchema.users",
    "action": "delete",
    "where": "name = 'Alice'"
}
```

### Safety

**Always include a WHERE clause** to avoid deleting all rows:

```python
# Good: Specific WHERE clause
request = {
    "action": "delete",
    "where": "status = 'deleted' AND deleted_at < '2023-01-01'"
}

# Bad: No WHERE clause (deletes ALL rows)
request = {
    "action": "delete"
}
# Returns error: "WHERE clause required for delete"
```

### What Happens

1. **Validation** - WHERE clause required (safety)
2. **Adapter Delete** - Backend-specific delete
3. **Return Result** - Number of rows deleted

### Return Format

```python
{
    "success": True,
    "rows_affected": 1
}
```

### Notes

- DELETE does not support hooks (by design)
- DELETE is permanent (no soft delete by default)
- For soft delete, use UPDATE: `{"deleted_at": "2024-01-15"}`

---

## UPSERT Operation

Insert or update - if record exists, update it; otherwise, insert it.

### Request Format

```python
request = {
    "model": "@.zSchema.users",
    "action": "upsert",
    "data": {
        "id": 1,
        "name": "Alice",
        "email": "alice.updated@example.com"
    }
}
```

### How It Works

1. **Check Existence** - Query for record by primary key (id)
2. **Update if Exists** - Execute UPDATE with existing id
3. **Insert if Not Exists** - Execute INSERT
4. **Return Result** - Inserted or updated data

### Conflict Resolution

Upsert uses primary key (PK) to detect conflicts:

```yaml
users:
  id: PK  # Used for conflict detection
  email:
    type: TEXT
    unique: true  # Also used for conflict detection
```

**SQLite/PostgreSQL:** Uses native UPSERT (INSERT ON CONFLICT)
**CSV:** Manual check + update/insert

### Return Format

```python
{
    "success": True,
    "action": "insert",  # or "update"
    "data": {"id": 1, "name": "Alice", "email": "alice.updated@example.com"}
}
```

### Notes

- UPSERT does not support hooks (by design)
- Requires primary key (PK) in data
- Unique constraints respected

---

## Validation

All operations validate data against schema:

### Type Validation

```python
# Schema
users:
  age: INTEGER
  email: TEXT
  created_at: TIMESTAMP

# Valid data
{"age": 25, "email": "alice@example.com", "created_at": "2024-01-15 10:30:00"}

# Invalid data (type error)
{"age": "twenty-five"}  # Error: age must be INTEGER
```

### Format Validation

```python
# Schema
users:
  email:
    type: TEXT
    format: email

# Valid data
{"email": "alice@example.com"}

# Invalid data (format error)
{"email": "not-an-email"}  # Error: invalid email format
```

### Required Fields

```python
# Schema
users:
  name:
    type: TEXT
    required: true

# Valid data
{"name": "Alice"}

# Invalid data (missing field)
{}  # Error: name is required
```

### Enum Validation

```python
# Schema
users:
  status:
    type: TEXT
    enum: [active, inactive, pending]

# Valid data
{"status": "active"}

# Invalid data (invalid enum)
{"status": "deleted"}  # Error: status must be one of [active, inactive, pending]
```

See [validators_GUIDE.md](validators_GUIDE.md) for all validation rules.

---

## Hook Execution

zFunc hooks execute custom business logic:

### Hook Types

| Hook | Operation | Timing | Use Case |
|------|-----------|--------|----------|
| `onBeforeInsert` | INSERT | Before DB insert | Hash passwords, generate IDs |
| `onAfterInsert` | INSERT | After DB insert | Send emails, log events |
| `onBeforeUpdate` | UPDATE | Before DB update | Validate changes, audit |
| `onAfterUpdate` | UPDATE | After DB update | Invalidate cache, notify |

### Hook Definition

```yaml
# Schema
users:
  zFunc:
    onBeforeInsert: "@.zFunc.hash_password"
    onAfterInsert: "@.zFunc.send_welcome_email"
```

### Hook Context

Hooks receive context with operation data:

```python
# @.zFunc.hash_password
def hash_password(context):
    data = context['data']
    if 'password' in data:
        data['password'] = bcrypt.hash(data['password'])
    return data
```

### Hook Errors

If hook fails, operation is aborted:

```python
# Hook raises error
def validate_email(context):
    email = context['data']['email']
    if not is_valid_email(email):
        raise ValueError("Invalid email format")

# Operation returns error
{
    "success": False,
    "error": "Hook failed: Invalid email format"
}
```

See [zFunc Guide](../../L2_Handling/zFunc_GUIDE.md) for hook implementation details.

---

## Error Handling

All operations return normalized error responses:

```python
# Success
{
    "success": True,
    "data": [...],
    "count": 10
}

# Error
{
    "success": False,
    "error": "Table not found: users"
}
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Table not found` | Table doesn't exist | Create table first |
| `Validation error` | Data validation failed | Fix data format |
| `WHERE clause required` | Missing WHERE in update/delete | Add WHERE clause |
| `Hook failed` | zFunc hook raised error | Fix hook logic |
| `Connection failed` | Backend unavailable | Check connection |
| `Constraint violation` | Unique/foreign key violated | Fix data conflict |

---

## Performance Considerations

### Bulk Operations

```python
# Good: Bulk insert (single transaction)
request = {
    "action": "insert",
    "data": [
        {"name": "Alice"},
        {"name": "Bob"},
        {"name": "Carol"},
    ]
}

# Bad: Individual inserts (multiple transactions)
for user in users:
    zdata.handle_request({"action": "insert", "data": user})
```

### Indexed Queries

```python
# Good: WHERE clause uses indexed column
request = {
    "action": "read",
    "where": "id = 123"  # id is primary key (indexed)
}

# Slow: WHERE clause uses non-indexed column
request = {
    "action": "read",
    "where": "name = 'Alice'"  # name not indexed
}
```

### Field Selection

```python
# Good: Only needed fields
request = {
    "action": "read",
    "fields": ["id", "name"]
}

# Bad: All fields (unnecessary data transfer)
request = {
    "action": "read"
}
```

---

## Best Practices

### 1. Always Include WHERE in Update/Delete

```python
# Good
request = {"action": "update", "data": {...}, "where": "id = 123"}

# Bad (updates ALL rows)
request = {"action": "update", "data": {...}}
```

### 2. Use Bulk Operations When Possible

```python
# Good
request = {"action": "insert", "data": [user1, user2, user3]}

# Bad
for user in users:
    zdata.handle_request({"action": "insert", "data": user})
```

### 3. Validate Data Before Operations

```python
# Good: Validation happens automatically
request = {"action": "insert", "data": {"email": "alice@example.com"}}

# But you can pre-validate if needed
validator = DataValidator(schema)
is_valid = validator.validate(data)
```

### 4. Use Upsert for Conflict Resolution

```python
# Good: Upsert handles insert vs update
request = {"action": "upsert", "data": {"id": 1, "name": "Alice"}}

# Bad: Manual check + insert/update
if exists:
    zdata.handle_request({"action": "update", ...})
else:
    zdata.handle_request({"action": "insert", ...})
```

---

## See Also

- [ddl_operations_GUIDE.md](ddl_operations_GUIDE.md) - DDL operations (create, drop, etc.)
- [aggregations_GUIDE.md](aggregations_GUIDE.md) - Aggregation operations
- [validators_GUIDE.md](validators_GUIDE.md) - Validation rules
- [parsers_GUIDE.md](parsers_GUIDE.md) - WHERE clause parsing
- [backends_GUIDE.md](backends_GUIDE.md) - Backend adapters

---

**[← Back to zData Guide](../zData_GUIDE.md)**
