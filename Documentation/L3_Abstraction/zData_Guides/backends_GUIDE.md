# zData Backends Module Guide

> **Module:** `zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/`  
> **Purpose:** Multi-backend adapter architecture supporting CSV, SQLite, PostgreSQL, and SQL databases.

---

## Overview

The `backends` module provides adapter implementations for different data backends. All adapters implement a common interface (`BaseAdapter`) ensuring consistent operations across backends.

---

## Architecture

```
Backends Module
├── BaseAdapter: Common interface for all adapters
├── AdapterFactory: Creates backend-specific adapters
├── AdapterRegistry: Registers and discovers adapters
├── CSV Adapter: File-based CSV operations
├── SQLite Adapter: Embedded database operations
├── PostgreSQL Adapter: PostgreSQL database operations
└── SQL Adapter: Generic SQL database operations
```

---

## Supported Backends

| Backend | Data_Type | Use Case | Installation |
|---------|-----------|----------|--------------|
| **CSV** | `CSV` | Small datasets, portability, human-readable | Built-in |
| **SQLite** | `SQLite` | Embedded apps, local storage, single-user | Built-in |
| **PostgreSQL** | `PostgreSQL` | Production, multi-user, transactions | `pip install psycopg2-binary` |
| **SQL** | `SQL` | Generic SQL databases (MySQL, MariaDB) | Backend-specific driver |

---

## BaseAdapter Interface

All adapters implement this common interface:

```python
class BaseAdapter:
    """Base interface for all data backend adapters."""
    
    # Connection management
    def connect(self) -> bool:
        """Establish connection to backend."""
        pass
    
    def disconnect(self) -> bool:
        """Close connection to backend."""
        pass
    
    def is_connected(self) -> bool:
        """Check if connection is active."""
        pass
    
    # CRUD operations
    def insert(self, table: str, data: dict) -> dict:
        """Insert row(s) into table."""
        pass
    
    def select(self, table: str, where: str = None) -> list:
        """Query rows from table."""
        pass
    
    def update(self, table: str, data: dict, where: str) -> bool:
        """Update rows in table."""
        pass
    
    def delete(self, table: str, where: str) -> bool:
        """Delete rows from table."""
        pass
    
    def upsert(self, table: str, data: dict) -> dict:
        """Insert or update row."""
        pass
    
    # DDL operations
    def create_table(self, table: str, schema: dict) -> bool:
        """Create table from schema."""
        pass
    
    def drop_table(self, table: str) -> bool:
        """Drop table."""
        pass
    
    def table_exists(self, table: str) -> bool:
        """Check if table exists."""
        pass
    
    def get_table_schema(self, table: str) -> dict:
        """Get table schema/columns."""
        pass
    
    def list_tables(self) -> list:
        """List all tables in database."""
        pass
```

---

## CSV Adapter

File-based adapter for CSV operations.

### Configuration

```yaml
zMeta:
  Data_Type: CSV
  Data_Path: "@.data.users"
  Data_Label: users
  csv_delimiter: ","      # Optional: Default ","
  csv_quotechar: '"'      # Optional: Default '"'
  csv_encoding: "utf-8"   # Optional: Default "utf-8"
```

### Features

- **File Operations:** Read/write CSV files
- **Schema Inference:** Auto-detect columns from header row
- **Type Conversion:** String → typed values
- **WHERE Filtering:** In-memory filtering
- **JOIN Operations:** In-memory joins
- **ORDER BY:** In-memory sorting
- **Aggregations:** In-memory COUNT, SUM, AVG, MIN, MAX

### Limitations

- No transactions (file-level atomicity only)
- No concurrent writes (file locking)
- Large datasets load entirely into memory
- No indexes (full table scans)

### Use Cases

- Small datasets (< 100k rows)
- Data export/import
- Human-readable storage
- Prototyping
- Configuration files

---

## SQLite Adapter

Embedded database adapter for SQLite.

### Configuration

```yaml
zMeta:
  Data_Type: SQLite
  Data_Path: "@.data.users"
  Data_Label: users
```

### Features

- **Embedded Database:** No server required
- **ACID Transactions:** Full transaction support
- **SQL Queries:** Native SQL support
- **Indexes:** CREATE INDEX support
- **Foreign Keys:** Relationship support
- **Triggers:** Event-driven operations

### Limitations

- Single-writer (concurrent reads OK)
- No network access (local file only)
- Limited concurrency (not for high-load servers)

### Use Cases

- Desktop applications
- Mobile apps
- Local storage
- Prototypes
- Single-user applications

---

## PostgreSQL Adapter

Production-grade adapter for PostgreSQL databases.

### Configuration

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

### Features

- **Production-Ready:** Enterprise-grade database
- **Multi-User:** Concurrent read/write
- **ACID Transactions:** Full transaction support
- **Advanced Features:** JOINs, indexes, views, stored procedures
- **Security:** Role-based access control
- **Scalability:** Handles millions of rows

### Requirements

```bash
pip install psycopg2-binary
```

### Use Cases

- Production applications
- Multi-user systems
- Large datasets
- Complex queries
- High availability

---

## AdapterFactory

Creates backend-specific adapters based on `Data_Type`.

### Usage

```python
from shared.backends.adapter_factory import AdapterFactory

# Create adapter from schema
adapter = AdapterFactory.create_adapter(
    data_type="SQLite",
    data_path="@.data.users",
    schema=schema,
    zos=z
)

# Connect to backend
adapter.connect()

# Use adapter operations
result = adapter.select("users", where="name = 'Alice'")

# Disconnect
adapter.disconnect()
```

### Supported Data Types

| Data_Type | Adapter Class | File |
|-----------|---------------|------|
| `CSV` | `CSVAdapter` | `csv_adapter.py` |
| `SQLite` | `SQLiteAdapter` | `sqlite_adapter.py` |
| `PostgreSQL` | `PostgreSQLAdapter` | `postgresql_adapter.py` |
| `SQL` | `SQLAdapter` | `sql_adapter.py` |

---

## AdapterRegistry

Registers and discovers available adapters.

### Usage

```python
from shared.backends.adapter_registry import AdapterRegistry

# Get all registered adapters
adapters = AdapterRegistry.get_all_adapters()

# Check if adapter is registered
is_registered = AdapterRegistry.is_registered("SQLite")

# Get adapter class
adapter_class = AdapterRegistry.get_adapter("SQLite")
```

### Registration

Adapters are auto-registered on import:

```python
# In csv_adapter.py
from .adapter_registry import AdapterRegistry

@AdapterRegistry.register("CSV")
class CSVAdapter(BaseAdapter):
    pass
```

---

## Backend-Specific Features

### CSV: WHERE Filtering

CSV adapter implements in-memory WHERE clause evaluation:

```python
# Supported operators
result = adapter.select("users", where="age > 18")
result = adapter.select("users", where="name LIKE 'A%'")
result = adapter.select("users", where="status IN ('active', 'pending')")
result = adapter.select("users", where="age BETWEEN 18 AND 65")
```

Implementation: See `csv_helpers/where_filtering.py`

---

### CSV: JOIN Operations

CSV adapter implements in-memory JOINs:

```python
# INNER JOIN
result = adapter.join(
    left_table="users",
    right_table="orders",
    join_type="INNER",
    on="users.id = orders.user_id"
)

# LEFT JOIN
result = adapter.join(
    left_table="users",
    right_table="orders",
    join_type="LEFT",
    on="users.id = orders.user_id"
)
```

Implementation: See `csv_helpers/join_operations.py`

---

### SQLite: Transactions

SQLite adapter supports transactions:

```python
# Begin transaction
adapter.begin_transaction()

# Multiple operations
adapter.insert("users", {"name": "Alice"})
adapter.update("users", {"email": "alice@new.com"}, where="name = 'Alice'")

# Commit or rollback
adapter.commit()  # or adapter.rollback()
```

---

### PostgreSQL: Connection Pooling

PostgreSQL adapter uses connection pooling:

```python
# Configuration in zMeta
zMeta:
  Data_Type: PostgreSQL
  Data_Source: USERS_DB
  pool_size: 10          # Max connections
  pool_timeout: 30       # Connection timeout (seconds)
```

---

## Error Handling

All adapters implement consistent error handling:

```python
try:
    result = adapter.select("users")
except ConnectionError as e:
    print(f"Connection failed: {e}")
except TableNotFoundError as e:
    print(f"Table not found: {e}")
except QueryError as e:
    print(f"Query failed: {e}")
```

**Common errors:**
- `ConnectionError`: Failed to connect to backend
- `TableNotFoundError`: Table doesn't exist
- `QueryError`: Invalid query syntax
- `ValidationError`: Data validation failed
- `ConstraintError`: Foreign key/unique constraint violated

---

## Type Conversion

Adapters handle type conversion between schema types and backend types:

| Schema Type | CSV | SQLite | PostgreSQL |
|-------------|-----|--------|------------|
| `PK` | INTEGER | INTEGER PRIMARY KEY | SERIAL PRIMARY KEY |
| `TEXT` | string | TEXT | TEXT |
| `INTEGER` | int | INTEGER | INTEGER |
| `REAL` | float | REAL | DOUBLE PRECISION |
| `TIMESTAMP` | ISO string | TEXT | TIMESTAMP |
| `DATE` | ISO string | TEXT | DATE |
| `TIME` | ISO string | TEXT | TIME |
| `BOOLEAN` | "true"/"false" | INTEGER (0/1) | BOOLEAN |
| `JSON` | JSON string | TEXT | JSONB |

---

## Performance Considerations

### CSV Performance

- **Read:** O(n) full file scan
- **Write:** O(n) full file rewrite
- **Query:** O(n) in-memory filtering
- **JOIN:** O(n*m) nested loop join
- **Memory:** Entire dataset in RAM

**Best for:** < 100k rows, infrequent writes

---

### SQLite Performance

- **Read:** O(log n) with indexes, O(n) without
- **Write:** O(log n) with indexes
- **Query:** Native SQL optimization
- **JOIN:** Query planner optimization
- **Memory:** Pages cached, disk-backed

**Best for:** < 1M rows, single-writer

---

### PostgreSQL Performance

- **Read:** O(log n) with indexes
- **Write:** O(log n) with indexes
- **Query:** Advanced query planner
- **JOIN:** Multi-strategy optimization
- **Memory:** Shared buffers, query cache

**Best for:** > 1M rows, multi-user, production

---

## Best Practices

### 1. Choose the Right Backend

```python
# Small datasets, portability
Data_Type: CSV

# Embedded apps, local storage
Data_Type: SQLite

# Production, multi-user
Data_Type: PostgreSQL
```

### 2. Use Environment Variables for Credentials

```yaml
# Good: Environment variable
zMeta:
  Data_Type: PostgreSQL
  Data_Source: USERS_DB

# Bad: Hardcoded credentials
zMeta:
  Data_Type: PostgreSQL
  Data_Path: "postgresql://user:pass@host/db"
```

### 3. Always Disconnect After Use

```python
# Good: Explicit disconnect
adapter = AdapterFactory.create_adapter(...)
adapter.connect()
try:
    result = adapter.select("users")
finally:
    adapter.disconnect()

# Orchestrator handles this automatically
```

### 4. Check Connection Status

```python
# Good: Check before operations
if adapter.is_connected():
    result = adapter.select("users")
else:
    adapter.connect()
```

---

## Migration Between Backends

zData supports migrating data between backends:

```python
# See migration_GUIDE.md for details
request = {
    "action": "migrate_backend",
    "source": "@.zSchema.users_csv",  # CSV
    "target": "@.zSchema.users_db",   # SQLite
}
```

**What's migrated:**
- Table structure (schema)
- All data (rows)
- Type conversions applied

**What's NOT migrated:**
- Indexes (must recreate)
- Triggers (backend-specific)
- Stored procedures (backend-specific)

---

## See Also

- [crud_operations_GUIDE.md](crud_operations_GUIDE.md) - CRUD operation details
- [ddl_operations_GUIDE.md](ddl_operations_GUIDE.md) - DDL operation details
- [migration_GUIDE.md](migration_GUIDE.md) - Backend migration process
- [connection_manager_GUIDE.md](connection_manager_GUIDE.md) - Connection lifecycle

---

**[← Back to zData Guide](../zData_GUIDE.md)**
