**[← Back to zWizard Guide](zWizard_GUIDE.md) | [Home](../../README.md) | [Next: zBifrost Guide →](zBifrost_GUIDE.md)**

---

# zData

**zData** is a **Layer 3 orchestration subsystem** in **zOS**.
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

It provides unified data management across multiple backends - CSV, SQLite, PostgreSQL, SQL databases - through one declarative interface with automatic migrations, validation, and type safety.

You get:

- **Zero boilerplate**  
- **No ORM complexity**
- **No manual migrations**
- **Multi-backend support** (CSV, SQLite, PostgreSQL)  
- **Type-safe operations** with schema validation  
- **Automatic migrations** with conflict detection
- **Query builder** with WHERE clauses, JOINs, aggregations
- **Storage quotas** per user/service

## Architecture Overview

**zData** follows the **facade-orchestrator pattern** (like zBifrost). It's composed of specialized modules at two levels:

### Facade Layer (Lightweight)

```
zData (zData.py) - ~370 lines
├── Delegates to DataOrchestrator
├── Provides public API compatibility
└── Announces readiness via zDisplay
```

### Orchestrator Layer (Core)

```
DataOrchestrator (orchestrator.py)
├── SchemaManager: Schema loading and validation
├── ConnectionManager: Adapter initialization
├── RequestHandler: Request routing
├── LifecycleManager: Connection cleanup
└── MigrationEngine: Schema migrations
```

### Module Organization

| Category | Module | Purpose | Guide |
|----------|--------|---------|-------|
| **Core** | orchestrator | Coordinates all data operations | [orchestrator_GUIDE.md](zData_Guides/orchestrator_GUIDE.md) |
| | schema_manager | Schema loading, validation, caching | [schema_manager_GUIDE.md](zData_Guides/schema_manager_GUIDE.md) |
| | connection_manager | Adapter initialization, lifecycle | *(see [Module Structure](#module-structure))* |
| | request_handler | Request routing, execution + access gate | *(see [Module Structure](#module-structure))* |
| | lifecycle_manager | Connection state, cleanup | *(see [Module Structure](#module-structure))* |
| **Access** | access_guard | Authoritative `zRBAC` gate (fail-closed) | *(see [Trust Model & zGuard Seams](#trust-model--zguard-seams))* |
| **Backends** | adapters | CSV, SQLite, PostgreSQL, SQL adapters | [backends_GUIDE.md](zData_Guides/backends_GUIDE.md) |
| **Operations** | CRUD | Insert, read, update, delete, upsert | [crud_operations_GUIDE.md](zData_Guides/crud_operations_GUIDE.md) |
| | DDL | Create, drop, head, migrate tables | [ddl_operations_GUIDE.md](zData_Guides/ddl_operations_GUIDE.md) |
| | Aggregations | Sum, count, avg, min, max, group by | [aggregations_GUIDE.md](zData_Guides/aggregations_GUIDE.md) |
| | Validators | Schema, format, plugin validation | [validators_GUIDE.md](zData_Guides/validators_GUIDE.md) |
| | Parsers | WHERE clause, value, JOIN parsing | [parsers_GUIDE.md](zData_Guides/parsers_GUIDE.md) |
| **Migration** | migration | Automatic schema migrations, conflict detection | [migration_GUIDE.md](zData_Guides/migration_GUIDE.md) |

This guide provides a **facade overview** of zData. For deep dives into specific modules, see the guides in `zData_Guides/`.

---

## Module Structure

```
m_zData/                                  (core/L3_Abstraction/m_zData)
├── zData.py                              Facade — delegates to DataOrchestrator
└── zData_modules/
    ├── orchestrator.py                   Coordinates the managers
    ├── schema_manager.py                 Schema load / validate / cache
    ├── connection_manager.py             Adapter init + lifecycle
    ├── request_handler.py                Request routing + Phase-5.5 access gate
    ├── lifecycle_manager.py              Connection cleanup
    ├── migration/                        Auto-migration engine + schema discovery
    └── shared/
        ├── access_guard.py               Authoritative zRBAC gate (fail-closed)
        ├── data_keys.py                  SSOT: request keys (← g_zDispatch) + zMeta / db_path
        ├── operators.py                  SSOT: WHERE operator tokens + normalize_operator
        ├── chunk_bridge.py               zGuard seam — Bifrost display streaming
        ├── operations/                   CRUD / DDL / aggregation handlers
        ├── backends/                     CSV · SQLite · PostgreSQL · SQL adapters
        │   └── type_mapping.py           SSOT: abstract→SQL type resolver (dialect-aware)
        ├── parsers/                      WHERE-clause / value parsers
        └── validators/                   Schema validation + field-key SSOT (constants.py)
```

---

## Trust Model & zGuard Seams

zData is **fully open-core** — there is no sealed engine here. Its single zGuard
seam is `shared/chunk_bridge.py`, which streams display output over Bifrost; that is
a **rendering** seam, **not** an authorization boundary.

**Authoritative access control (`zRBAC`).** The data layer is where mutations
actually happen, so zData enforces access **itself** rather than trusting upstream
(render-time) checks. Every declarative request passes through a **fail-closed**
gate (`shared/access_guard.py`, request **Phase 5.5**) before any table is touched:

- The gate resolves the target table + action category (read vs. write) and asks
  **f_zAuth** (`zos.auth.check_data_access`) for the decision.
- Access is declared once, per schema/table, via a `zRBAC` block — the **same**
  vocabulary the wizard render-gate reads (f_zAuth owns the SSOT):

```yaml
users:
  zRBAC:
    require_auth: true                 # must be logged in
    require_role: admin                # ... with this role
    require_permission: users.write    # ... or this permission
    actions:                           # optional per-category override
      read:  { require_auth: false }   #   public reads
      write: { require_role: admin }   #   gated writes
  id:   { type: int, pk: true }
  name: { type: str, required: true }
```

- **Undeclared `zRBAC` = public** (backward-compatible). **Declared = enforced**,
  fail-closed — a denial blocks the operation before execution.
- f_zAuth's own bootstrap (`zos.data.*` during login) is exempt, so the gate can
  never deadlock authentication.

**Injection safety.** All SQL backends run **parameterized** queries (placeholders
+ a bound-params list); user values are never interpolated into SQL text. CSV
filtering uses pandas masks. The WHERE operator vocabulary is normalized through one
SSOT (`shared/operators.py`), so `$gt` / `$GT` / `>` behave identically across the
in-memory, CSV and SQL evaluators.

> **Docs-split.** The `zRBAC` *decision logic* and the sealed network/identity layer
> live in **f_zAuth** and **zGuard** (see the private zGuard docs). This guide
> documents only zData's open-core behavior + the seam contract. Production
> identity/attestation requires zGuard — contact admin / `z patch`.

---

## Initialization Order

When zData initializes:

1. **zOS Initialized** - Framework ready (zConfig, zComm, zDisplay, etc.)
2. **zData Facade Created** - `zdata = zData(zos)`
3. **DataOrchestrator Initialized** - Core coordination hub created
4. **Lazy Manager Loading** - Managers created on first use:
   - SchemaManager (on first schema load)
   - ConnectionManager (on first connection)
   - RequestHandler (on first request)
   - LifecycleManager (on first connection)
   - MigrationEngine (on first migration)
5. **zData Ready** - Data operations available

This lazy initialization ensures fast startup and avoids circular dependencies.

**Usage:**
```python
from zOS import zOS

z = zOS()  # Framework initialized
zdata = z.zdata  # zData facade ready (lazy initialization)

# First request triggers manager loading
request = {"model": "@.zSchema.users", "action": "read"}
result = zdata.handle_request(request)
```

---

## Tutorials

**Learn by doing!** 

The tutorials below are organized in a bottom-up fashion. Every tutorial below has a working demo you can run and modify.

**A Note on Learning zOS:**  
Each tutorial (lvl1, lvl2, lvl3...) progressively introduces more complex features of **this subsystem**. The early tutorials start with familiar imperative patterns (think Django-style conventions) to meet you where you are as a developer.

As you progress through zOS's subsystems, you'll notice a gradual shift from imperative to declarative patterns. This intentional journey helps reshape your mental model from imperative to declarative thinking. Only when you reach **Layer 3 (Orchestration)** will you see subsystems used **fully declaratively** as intended in production. By then, the true magic of declarative coding will reveal itself, and you'll understand why we started this way.

Get the demos:

```bash
# Clone only the Demos folder
git clone --depth 1 --filter=blob:none --sparse https://github.com/ZoloAi/zolo-zcli.git
cd zolo-zcli
git sparse-checkout set Demos
```

> All zData demos are in: `Demos/Layer_3/zData_Demo/`

---

# **zData - Level 1** (Schema & Connect)

### **i. Define Your Schema**

Before you can work with data, you need a schema. A **schema** is a blueprint that defines:
- What data you're storing (tables, fields)
- What types those fields have (text, number, date)
- Where the data lives (CSV file, SQLite database, PostgreSQL)
- Validation rules (required fields, formats, constraints)

**Think of a schema as a contract** - it tells zData exactly what your data looks like and how to work with it.

Let's create a simple users schema in `@.zSchema.users`:

```yaml
# @.zSchema.users.yaml
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

**What's in zMeta?**
- `Data_Type`: Which backend (CSV, SQLite, PostgreSQL)
- `Data_Path`: Where data is stored (file path or connection)
- `Data_Label`: Table name
- `Schema_Name`: Database identifier

**What's in the table definition?**
- `users`: Table name
- `id: PK`: Primary key (auto-generated)
- `name: TEXT`: Text field
- `email: TEXT`: Text field
- `created_at: TIMESTAMP`: Timestamp field

**🎯 Run the demo to see schema loading:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl1_schema/1_define_schema.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl1_schema/1_define_schema.py)

**What you'll discover:**
- Schema definition format
- zMeta section structure
- Table and field definitions
- Backend configuration

---

### **ii. Connect to Backend**

Once you have a schema, you can connect to the backend and create tables:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Define request to create table
request = {
    "model": "@.zSchema.users",  # Schema path
    "action": "create",           # Create table action
}

# Execute request
result = zdata.handle_request(request)

if result:
    print("✅ Table created successfully!")
else:
    print("❌ Failed to create table")
```

**What happens?**
1. zData loads schema from `@.zSchema.users`
2. SchemaManager validates zMeta section
3. ConnectionManager creates SQLite adapter
4. Adapter creates `users` table with defined fields
5. Connection is established and ready

**🎯 Run the demo to create your first table:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl1_schema/2_connect_backend.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl1_schema/2_connect_backend.py)

**What you'll discover:**
- How to execute zData requests
- Request structure (model, action)
- Table creation workflow
- Backend connection lifecycle

---

### **iii. Multiple Backends**

zData supports multiple backends through the same interface:

**CSV Backend:**
```yaml
zMeta:
  Data_Type: CSV
  Data_Path: "@.data.users"
  Data_Label: users
```

**SQLite Backend:**
```yaml
zMeta:
  Data_Type: SQLite
  Data_Path: "@.data.users"
  Data_Label: users
```

**PostgreSQL Backend:**
```yaml
zMeta:
  Data_Type: PostgreSQL
  Data_Source: USERS_DB  # Environment variable
  Data_Label: users
```

For PostgreSQL, store credentials in `.zEnv`:
```bash
# .zEnv
ZDATA_USERS_DB_URL=postgresql://user:pass@localhost:5432/mydb
```

**Security Best Practice:** Never hardcode database credentials in schema files. Use `Data_Source` to reference environment variables instead of `Data_Path`.

**🎯 Try different backends:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl1_schema/3_multi_backend.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl1_schema/3_multi_backend.py)

**What you'll discover:**
- Same API works across all backends
- CSV, SQLite, PostgreSQL support
- Environment variable configuration
- Security best practices

---

**🎯 Level 1 Complete!**

You've learned the foundation:
- ✅ **Schema definition** - Blueprint for your data
- ✅ **Backend connection** - Creating tables
- ✅ **Multi-backend support** - CSV, SQLite, PostgreSQL

---

# **zData - Level 2** (CRUD Operations)

### **i. Insert Data**

Now that you have a table, let's insert data:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Insert request
request = {
    "model": "@.zSchema.users",
    "action": "insert",
    "data": {
        "name": "Alice",
        "email": "alice@example.com",
        "created_at": "2024-01-15 10:30:00"
    }
}

result = zdata.handle_request(request)
print(f"Inserted: {result}")
```

**What happens?**
1. zData validates data against schema
2. Type checking (TEXT, TIMESTAMP)
3. Required field validation
4. Insert into backend
5. Returns inserted row with generated ID

**Bulk Insert:**
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

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl2_crud/1_insert_data.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl2_crud/1_insert_data.py)

**What you'll discover:**
- Insert single records
- Bulk insert multiple records
- Automatic validation
- Type safety

---

### **ii. Read Data**

Query data with flexible WHERE clauses:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Read all users
request = {
    "model": "@.zSchema.users",
    "action": "read"
}
result = zdata.handle_request(request)

# Read with WHERE clause
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "where": "name = 'Alice'"
}
result = zdata.handle_request(request)

# Read with operators
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "where": "name LIKE 'A%' AND created_at > '2024-01-01'"
}
result = zdata.handle_request(request)
```

**Supported WHERE Operators:**
- `=`, `!=`, `<`, `<=`, `>`, `>=`
- `LIKE` (pattern matching)
- `IN` (value in list)
- `BETWEEN` (range)
- `AND`, `OR` (logical)
- `IS NULL`, `IS NOT NULL`

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl2_crud/2_read_data.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl2_crud/2_read_data.py)

**What you'll discover:**
- Query data with WHERE clauses
- Pattern matching with LIKE
- Complex conditions with AND/OR
- Type-safe comparisons

---

### **iii. Update Data**

Modify existing records:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Update specific record
request = {
    "model": "@.zSchema.users",
    "action": "update",
    "data": {"email": "alice.new@example.com"},
    "where": "name = 'Alice'"
}
result = zdata.handle_request(request)

# Update multiple records
request = {
    "model": "@.zSchema.users",
    "action": "update",
    "data": {"created_at": "2024-01-20 10:00:00"},
    "where": "name LIKE 'A%'"
}
result = zdata.handle_request(request)
```

**Safety:** Always include a WHERE clause to avoid updating all records.

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl2_crud/3_update_data.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl2_crud/3_update_data.py)

---

### **iv. Delete Data**

Remove records:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Delete specific record
request = {
    "model": "@.zSchema.users",
    "action": "delete",
    "where": "name = 'Alice'"
}
result = zdata.handle_request(request)

# Delete with conditions
request = {
    "model": "@.zSchema.users",
    "action": "delete",
    "where": "created_at < '2024-01-01'"
}
result = zdata.handle_request(request)
```

**Safety:** Always include a WHERE clause to avoid deleting all records.

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl2_crud/4_delete_data.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl2_crud/4_delete_data.py)

---

### **v. Upsert (Insert or Update)**

Upsert combines insert and update - if record exists, update it; otherwise, insert it:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Upsert single record
request = {
    "model": "@.zSchema.users",
    "action": "upsert",
    "data": {
        "id": 1,
        "name": "Alice",
        "email": "alice.updated@example.com"
    }
}
result = zdata.handle_request(request)
```

**How it works:**
- Checks if record with `id=1` exists
- If exists: Updates email
- If not exists: Inserts new record

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl2_crud/5_upsert_data.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl2_crud/5_upsert_data.py)

---

**🎯 Level 2 Complete!**

You've mastered CRUD operations:
- ✅ **Insert** - Add new records
- ✅ **Read** - Query with WHERE clauses
- ✅ **Update** - Modify existing records
- ✅ **Delete** - Remove records
- ✅ **Upsert** - Insert or update

---

# **zData - Level 3** (Advanced Queries)

### **i. JOINs**

Combine data from multiple tables:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Inner join
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "join": {
        "type": "INNER",
        "table": "orders",
        "on": "users.id = orders.user_id"
    }
}
result = zdata.handle_request(request)

# Left join with WHERE
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
result = zdata.handle_request(request)
```

**Supported JOIN types:**
- `INNER` - Only matching records
- `LEFT` - All from left table, matching from right
- `RIGHT` - All from right table, matching from left
- `FULL` - All records from both tables

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl3_advanced/1_joins.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl3_advanced/1_joins.py)

---

### **ii. Aggregations**

Compute statistics across your data:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Count records
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "aggregate": {"function": "COUNT"}
}
result = zdata.handle_request(request)

# Sum with GROUP BY
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "SUM",
        "field": "total",
        "group_by": "user_id"
    }
}
result = zdata.handle_request(request)

# Multiple aggregations
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": [
        {"function": "AVG", "field": "total"},
        {"function": "MIN", "field": "total"},
        {"function": "MAX", "field": "total"}
    ]
}
result = zdata.handle_request(request)
```

**Supported functions:**
- `COUNT` - Count records
- `SUM` - Sum values
- `AVG` - Average value
- `MIN` - Minimum value
- `MAX` - Maximum value

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl3_advanced/2_aggregations.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl3_advanced/2_aggregations.py)

---

### **iii. Sorting & Pagination**

Control result ordering and limit results:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Sort ascending
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "order_by": "name ASC"
}
result = zdata.handle_request(request)

# Sort descending
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "order_by": "created_at DESC"
}
result = zdata.handle_request(request)

# Pagination
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "limit": 10,
    "offset": 20,
    "order_by": "name ASC"
}
result = zdata.handle_request(request)
```

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl3_advanced/3_sorting.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl3_advanced/3_sorting.py)

---

**🎯 Level 3 Complete!**

You've mastered advanced queries:
- ✅ **JOINs** - Combine tables
- ✅ **Aggregations** - Statistics and GROUP BY
- ✅ **Sorting** - ORDER BY
- ✅ **Pagination** - LIMIT and OFFSET

---

# **zData - Level 4** (Schema Migrations)

### **i. Automatic Migrations**

When you change your schema, zData automatically migrates your data:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Migrate request
request = {
    "model": "@.zSchema.users",
    "action": "migrate"
}
result = zdata.handle_request(request)
```

**What migrations do:**
- Add new columns (with default values)
- Remove obsolete columns (with data backup)
- Change column types (with data conversion)
- Detect conflicts (manual resolution required)

**Migration scenarios:**

1. **Add column** - New field added to schema
   ```
   Before: users(id, name)
   After:  users(id, name, email)
   Result: Adds email column, fills with NULL
   ```

2. **Remove column** - Field removed from schema
   ```
   Before: users(id, name, email)
   After:  users(id, name)
   Result: Removes email column, backs up data
   ```

3. **Change type** - Field type changed
   ```
   Before: users(age: TEXT)
   After:  users(age: INTEGER)
   Result: Converts "25" → 25
   ```

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl4_migration/1_auto_migrate.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl4_migration/1_auto_migrate.py)

---

### **ii. Migration Conflicts**

Some schema changes require manual intervention:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Attempt migration
request = {
    "model": "@.zSchema.users",
    "action": "migrate"
}
result = zdata.handle_request(request)

if result.get("conflict"):
    print(f"Conflict detected: {result['message']}")
    print(f"Resolution: {result['resolution']}")
```

**Conflict scenarios:**

1. **Incompatible type conversion**
   ```
   Before: users(name: TEXT) = "Alice"
   After:  users(name: INTEGER)
   Conflict: Cannot convert "Alice" to integer
   Resolution: Manual data cleanup or revert schema
   ```

2. **Required field without default**
   ```
   Before: users(id, name)
   After:  users(id, name, email: TEXT NOT NULL)
   Conflict: Existing rows have no email value
   Resolution: Add default value or migrate data first
   ```

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl4_migration/2_conflicts.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl4_migration/2_conflicts.py)

---

### **iii. Backend Migrations**

Migrate data between backends:

```python
from zOS import zOS

z = zOS()
zdata = z.zdata

# Migrate from CSV to SQLite
request = {
    "action": "migrate_backend",
    "source": "@.zSchema.users_csv",  # CSV schema
    "target": "@.zSchema.users_db",   # SQLite schema
}
result = zdata.handle_request(request)

# Migrate from SQLite to PostgreSQL
request = {
    "action": "migrate_backend",
    "source": "@.zSchema.users_db",      # SQLite schema
    "target": "@.zSchema.users_postgres",  # PostgreSQL schema
}
result = zdata.handle_request(request)
```

**What happens:**
1. Reads all data from source backend
2. Creates table in target backend
3. Inserts data with type conversion
4. Validates data integrity
5. Reports migration status

**🎯 Run the demo:**

```bash
python3 Demos/Layer_3/zData_Demo/lvl4_migration/3_backend_migration.py
```

[View demo source →](../../Demos/Layer_3/zData_Demo/lvl4_migration/3_backend_migration.py)

---

**🎯 Level 4 Complete!**

You've mastered migrations:
- ✅ **Automatic migrations** - Schema evolution
- ✅ **Conflict detection** - Manual resolution
- ✅ **Backend migrations** - Cross-backend data transfer

---

## Facade API Reference

The `zData` class provides these convenience methods:

**Request Handling:**
```python
# Main request handler
result = zdata.handle_request(request, context={})

# Request structure
request = {
    "model": "@.zSchema.users",  # Schema path
    "action": "read",             # Operation
    "data": {...},                # Data payload (insert/update/upsert)
    "where": "...",               # WHERE clause (read/update/delete)
    "join": {...},                # JOIN clause (read)
    "aggregate": {...},           # Aggregation (read)
    "order_by": "...",            # Sorting (read)
    "limit": 10,                  # Pagination (read)
    "offset": 0,                  # Pagination (read)
}
```

**CRUD Operations:**
```python
# Insert
zdata.handle_request({"model": "...", "action": "insert", "data": {...}})

# Read
zdata.handle_request({"model": "...", "action": "read", "where": "..."})

# Update
zdata.handle_request({"model": "...", "action": "update", "data": {...}, "where": "..."})

# Delete
zdata.handle_request({"model": "...", "action": "delete", "where": "..."})

# Upsert
zdata.handle_request({"model": "...", "action": "upsert", "data": {...}})
```

**DDL Operations:**
```python
# Create table
zdata.handle_request({"model": "...", "action": "create"})

# Drop table
zdata.handle_request({"model": "...", "action": "drop"})

# Show schema
zdata.handle_request({"model": "...", "action": "head"})

# List tables
zdata.handle_request({"model": "...", "action": "list_tables"})
```

**Migration Operations:**
```python
# Schema migration
zdata.handle_request({"model": "...", "action": "migrate"})

# Backend migration
zdata.handle_request({
    "action": "migrate_backend",
    "source": "@.zSchema.source",
    "target": "@.zSchema.target"
})

# Discover schemas
zdata.handle_request({
    "action": "discover_schemas",
    "data_path": "path/to/db"
})
```

**File Operations:**
```python
# Open schema in editor
zdata.open_schema("@.zSchema.users")

# Open CSV file
zdata.open_csv("@.data.users")
```

**Direct Module Access:**
```python
# Access orchestrator directly
zdata.orchestrator                # DataOrchestrator instance
zdata.orchestrator.schema_manager # SchemaManager instance
zdata.orchestrator.connection_manager  # ConnectionManager instance
zdata.orchestrator.request_handler     # RequestHandler instance
zdata.orchestrator.lifecycle_manager   # LifecycleManager instance
```

---

## Advanced Features

### Storage Quotas

zData includes storage quota management per user/service:

```python
# Request with quota check
request = {
    "model": "@.zSchema.users",
    "action": "insert",
    "data": {...},
    "options": {
        "user_id": 42,
        "enforce_quota": True
    }
}
result = zdata.handle_request(request)
```

**What happens:**
- Checks current storage usage for user_id=42
- Compares against configured quota
- Rejects insert if quota exceeded
- Returns error with quota information

For detailed documentation, see [storage_quota_GUIDE.md](zData_Guides/storage_quota_GUIDE.md) *(coming soon)*.

---

### Validation Rules

zData supports comprehensive validation:

**Field-level validation:**
```yaml
users:
  email:
    type: TEXT
    format: email
    required: true
  age:
    type: INTEGER
    min: 0
    max: 150
  status:
    type: TEXT
    enum: [active, inactive, pending]
```

**Custom validators:**
```yaml
users:
  username:
    type: TEXT
    validator: "@.zFunc.validate_username"
```

For detailed documentation, see [validators_GUIDE.md](zData_Guides/validators_GUIDE.md).

---

### zFunc Hooks

Integrate custom business logic with zFunc hooks:

```yaml
users:
  zFunc:
    onBeforeInsert: "@.zFunc.hash_password"
    onAfterInsert: "@.zFunc.send_welcome_email"
    onBeforeUpdate: "@.zFunc.validate_update"
    onAfterUpdate: "@.zFunc.log_change"
```

**Hook execution flow:**
1. `onBeforeInsert` - Modify data before insertion
2. Insert operation
3. `onAfterInsert` - Post-insertion actions
4. Similar for update operations

For zFunc integration, see [zFunc Guide](L2_Handling/zFunc_GUIDE.md).

---

## What's Next?

You've mastered **zData** (unified data management). Now continue to **zWalker** - the file system navigator that orchestrates zData operations through an interactive UI.

**→ Continue to [zWalker Guide](../L4_Orchestration/zWalker_GUIDE.md)**

---

# Appendix: Schema Definition Reference

## zMeta Section

Required fields in every schema:

```yaml
zMeta:
  Data_Type: CSV | SQLite | PostgreSQL | SQL
  Data_Path: "@.data.file"  # or Data_Source: ENV_VAR
  Data_Label: table_name
  Schema_Name: db_identifier
```

| Field | Required | Description |
|-------|----------|-------------|
| `Data_Type` | Yes | Backend type (CSV, SQLite, PostgreSQL, SQL) |
| `Data_Path` | Yes* | File path or connection string |
| `Data_Source` | Yes* | Environment variable name (security) |
| `Data_Label` | Yes | Table name in database |
| `Schema_Name` | Yes | Database/schema identifier |
| `zVaFiles` | No | Validation files list |

*Either `Data_Path` or `Data_Source` required (use `Data_Source` for production)

---

## Field Types

Supported field types across backends:

| Type | Description | Example Values |
|------|-------------|----------------|
| `PK` | Primary key (auto-increment) | 1, 2, 3... |
| `TEXT` | Text/string | "Alice", "bob@example.com" |
| `INTEGER` | Whole number | 42, -10, 0 |
| `REAL` | Floating point | 3.14, -2.5, 0.0 |
| `TIMESTAMP` | Date and time | "2024-01-15 10:30:00" |
| `DATE` | Date only | "2024-01-15" |
| `TIME` | Time only | "10:30:00" |
| `BOOLEAN` | True/False | true, false |
| `JSON` | JSON object | {"key": "value"} |

---

## Validation Formats

Built-in format validators:

```yaml
users:
  email:
    type: TEXT
    format: email  # Email validation
  url:
    type: TEXT
    format: url    # URL validation
  phone:
    type: TEXT
    format: phone  # Phone number validation
  ssn:
    type: TEXT
    format: ssn    # Social Security Number validation
```

For all format validators, see [validators_GUIDE.md](zData_Guides/validators_GUIDE.md).

---

## Backend-Specific Configuration

### CSV Backend

```yaml
zMeta:
  Data_Type: CSV
  Data_Path: "@.data.users"
  Data_Label: users
  csv_delimiter: ","     # Optional: Default ","
  csv_quotechar: '"'     # Optional: Default '"'
  csv_encoding: "utf-8"  # Optional: Default "utf-8"
```

### SQLite Backend

```yaml
zMeta:
  Data_Type: SQLite
  Data_Path: "@.data.users"
  Data_Label: users
```

### PostgreSQL Backend

```yaml
zMeta:
  Data_Type: PostgreSQL
  Data_Source: USERS_DB  # Environment variable
  Data_Label: users
```

Store credentials in `.zEnv`:
```bash
ZDATA_USERS_DB_URL=postgresql://user:pass@localhost:5432/mydb
```

---

**[← Back to zWizard Guide](zWizard_GUIDE.md) | [Home](../../README.md) | [Next: zBifrost Guide →](zBifrost_GUIDE.md)**
