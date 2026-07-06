# CSV Adapter Documentation

CSV database backend adapter with pandas-powered DataFrames and in-memory caching.

This module implements a sophisticated CSV adapter that uses pandas DataFrames for
powerful data manipulation, in-memory table caching for performance, multi-table
JOIN support, and comprehensive WHERE clause filtering. Perfect for lightweight
data storage, prototyping, and file-based databases.

## Architecture Overview

CSVAdapter sits at the concrete layer of the adapter hierarchy:

```
BaseDataAdapter (ABC)
       ↓
CSVAdapter (File-based with pandas DataFrames)
```

**Design Philosophy:**
- **Pandas-powered:** Uses DataFrames for efficient data manipulation
- **In-memory caching:** Tables cached in self.tables dict for performance
- **File-based persistence:** Each table stored as {table_name}.csv
- **Multi-table JOINs:** Merge multiple tables with auto-join detection
- **Type coercion:** Schema-based type enforcement via pandas dtypes
- **WHERE filtering:** Comprehensive operator support (eq, gt, lt, like, in, etc.)

## CSV-Specific Features

### 1. Pandas DataFrames
All tables loaded as pandas DataFrames for powerful operations:
- Filtering, sorting, grouping via pandas API
- Type coercion (int, float, bool, datetime, str)
- Efficient column operations (add, drop, rename)
- to_csv() for persistence, read_csv() for loading

### 2. In-Memory Table Caching
Tables cached in self.tables dict for performance:
```python
self.tables = {
    "users": DataFrame(...),
    "orders": DataFrame(...)
}
```
- Load once, access many times (no repeated file I/O)
- Automatic save on disconnect() flushes cache to disk
- Memory-efficient for small-to-medium datasets

### 3. Multi-Table JOIN Support
Powerful join operations with pandas merge():
- Manual JOINs: Specify join conditions explicitly
- AUTO JOIN: Detects relationships from schema foreign keys
- Merge strategies: inner, left, right, outer
- Multi-table queries: join("users", "orders", "products")

### 4. WHERE Clause Filtering
Comprehensive filtering with operators:
- **Equality:** `{"age": 25}` → age == 25
- **Comparison:** `{"age__gt": 18}` → age > 18
- **LIKE:** `{"name__like": "John%"}` → name.str.startswith("John")
- **IN:** `{"city__in": ["NYC", "LA"]}` → city.isin(["NYC", "LA"])
- **IS NULL:** `{"deleted__is_null": True}` → deleted.isna()
- **OR conditions:** `{"or": [{"city": "NYC"}, {"city": "LA"}]}`

### 5. Type Coercion
Schema-based type enforcement:
```python
schema = {"age": {"type": "int"}, "price": {"type": "float"}}
df = df.astype({"age": "int64", "price": "float64"})
```

### 6. UPSERT Support
Insert or update with conflict resolution:
- Merge new data with existing data on conflict_fields
- drop_duplicates(subset=conflict_fields, keep='last')

## File Structure

Each table stored as a separate CSV file:
```
base_path/
    users.csv
    orders.csv
    products.csv
```

**CSV Format:**
- Header row with column names
- Pandas to_csv(index=False) - no row index
- UTF-8 encoding by default
- Comma delimiter (configurable)

## Caching Strategy

**Load → Cache → Save cycle:**
1. **connect():** Ensure base_path exists
2. **_load_table():** Read CSV → DataFrame, cache in self.tables
3. **Operations:** Work with cached DataFrame (fast)
4. **_save_table():** Write DataFrame → CSV (on demand or disconnect)
5. **disconnect():** Flush all cached tables to disk

**Memory Management:**
- Tables stay in memory for session duration
- Large datasets: Consider chunking or database backend
- self.tables.clear() on disconnect frees memory

## Usage Examples

### Basic connection and CRUD:
```python
from zOS.L3_Abstraction.n_zData.zData_modules.shared.backends.csv_adapter import CSVAdapter

config = {"path": "/data/myapp", "label": "csvdb"}
adapter = CSVAdapter(config, logger=logger)
adapter.connect()

# Create table
schema = {
    "id": {"type": "int", "pk": True},
    "name": {"type": "str", "required": True},
    "age": {"type": "int"}
}
adapter.create_table("users", schema)

# Insert (cached in memory)
row_id = adapter.insert("users", ["name", "age"], ["John", 30])

# Select with WHERE
rows = adapter.select("users", where={"age__gte": 18})

# Disconnect (saves all cached tables)
adapter.disconnect()
```

### Multi-table JOINs:
```python
# Manual JOIN
joins = [{"table": "orders", "on": "users.id == orders.user_id"}]
rows = adapter.select(["users", "orders"], joins=joins)

# AUTO JOIN (detects FK from schema)
rows = adapter.select(
    ["users", "companies"],
    auto_join=True,
    schema=schema
)
```

### WHERE operators:
```python
# Comparison
rows = adapter.select("users", where={"age__gt": 18, "age__lt": 65})

# LIKE pattern
rows = adapter.select("users", where={"name__like": "John%"})

# IN list
rows = adapter.select("users", where={"city__in": ["NYC", "LA"]})

# OR conditions
rows = adapter.select("users", where={
    "status": "active",
    "or": [{"city": "NYC"}, {"city": "LA"}]
})
```

## Dependencies

**Required:**
- pandas

**Installation:**
```bash
pip install pandas
# or
pip install zolo-zcli[csv]
```

## Integration

This adapter is used by:
- classical_data.py: CRUD orchestration
- data_operations.py: High-level operations
- quantum_data.py: Abstracted data structures (if CSV backend selected)

## See Also

- base_adapter.py: Abstract adapter interface
- sqlite_adapter.py: SQL-based file storage
- postgresql_adapter.py: SQL-based network storage
