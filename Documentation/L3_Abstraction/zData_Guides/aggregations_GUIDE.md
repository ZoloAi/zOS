# zData Aggregations Module Guide

> **Module:** `zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/`  
> **Purpose:** Aggregation operations for statistical analysis (COUNT, SUM, AVG, MIN, MAX, GROUP BY).

---

## Overview

The `operations` module provides aggregation capabilities:
- **COUNT** - Count rows
- **SUM** - Sum numeric values
- **AVG** - Average numeric values
- **MIN** - Minimum value
- **MAX** - Maximum value
- **GROUP BY** - Group aggregations by field

---

## Supported Functions

| Function | Description | Supported Types | Example |
|----------|-------------|-----------------|---------|
| `COUNT` | Count rows | All types | Count total users |
| `SUM` | Sum values | INTEGER, REAL | Sum order totals |
| `AVG` | Average value | INTEGER, REAL | Average age |
| `MIN` | Minimum value | INTEGER, REAL, TEXT, TIMESTAMP | Oldest user |
| `MAX` | Maximum value | INTEGER, REAL, TEXT, TIMESTAMP | Newest user |

---

## COUNT Operation

Count total rows in table.

### Request Format

```python
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "aggregate": {
        "function": "COUNT"
    }
}
result = zdata.handle_request(request)
```

### Return Format

```python
{
    "success": True,
    "data": {
        "count": 1523
    }
}
```

### COUNT with WHERE

```python
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "aggregate": {
        "function": "COUNT"
    },
    "where": "status = 'active'"
}
# Returns: {"count": 842}
```

### COUNT DISTINCT (field-specific)

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "COUNT",
        "field": "user_id",
        "distinct": True
    }
}
# Returns: Count of unique users
```

---

## SUM Operation

Sum numeric values.

### Request Format

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "SUM",
        "field": "total"
    }
}
result = zdata.handle_request(request)
```

### Return Format

```python
{
    "success": True,
    "data": {
        "sum_total": 125480.50
    }
}
```

### SUM with WHERE

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "SUM",
        "field": "total"
    },
    "where": "status = 'completed'"
}
# Returns: Sum of completed orders only
```

---

## AVG Operation

Calculate average of numeric values.

### Request Format

```python
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "aggregate": {
        "function": "AVG",
        "field": "age"
    }
}
result = zdata.handle_request(request)
```

### Return Format

```python
{
    "success": True,
    "data": {
        "avg_age": 32.5
    }
}
```

### AVG with WHERE

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "AVG",
        "field": "total"
    },
    "where": "created_at > '2024-01-01'"
}
# Returns: Average order total for 2024
```

---

## MIN Operation

Find minimum value.

### Request Format

```python
request = {
    "model": "@.zSchema.products",
    "action": "read",
    "aggregate": {
        "function": "MIN",
        "field": "price"
    }
}
result = zdata.handle_request(request)
```

### Return Format

```python
{
    "success": True,
    "data": {
        "min_price": 9.99
    }
}
```

### MIN with Timestamps

```python
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "aggregate": {
        "function": "MIN",
        "field": "created_at"
    }
}
# Returns: Earliest registration date
```

---

## MAX Operation

Find maximum value.

### Request Format

```python
request = {
    "model": "@.zSchema.products",
    "action": "read",
    "aggregate": {
        "function": "MAX",
        "field": "price"
    }
}
result = zdata.handle_request(request)
```

### Return Format

```python
{
    "success": True,
    "data": {
        "max_price": 999.99
    }
}
```

### MAX with Timestamps

```python
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "aggregate": {
        "function": "MAX",
        "field": "last_login"
    }
}
# Returns: Most recent login
```

---

## GROUP BY

Group aggregations by field values.

### Simple GROUP BY

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "COUNT",
        "group_by": "status"
    }
}
```

**Return Format:**
```python
{
    "success": True,
    "data": [
        {"status": "pending", "count": 42},
        {"status": "completed", "count": 1523},
        {"status": "cancelled", "count": 15}
    ]
}
```

### GROUP BY with SUM

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "SUM",
        "field": "total",
        "group_by": "user_id"
    }
}
```

**Return Format:**
```python
{
    "success": True,
    "data": [
        {"user_id": 1, "sum_total": 1250.50},
        {"user_id": 2, "sum_total": 842.30},
        {"user_id": 3, "sum_total": 523.00}
    ]
}
```

### Multiple GROUP BY Fields

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "COUNT",
        "group_by": ["status", "user_id"]
    }
}
```

**Return Format:**
```python
{
    "success": True,
    "data": [
        {"status": "pending", "user_id": 1, "count": 2},
        {"status": "pending", "user_id": 2, "count": 5},
        {"status": "completed", "user_id": 1, "count": 10},
        {"status": "completed", "user_id": 2, "count": 8}
    ]
}
```

---

## Multiple Aggregations

Compute multiple aggregations in one query.

### Request Format

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": [
        {"function": "COUNT"},
        {"function": "SUM", "field": "total"},
        {"function": "AVG", "field": "total"},
        {"function": "MIN", "field": "total"},
        {"function": "MAX", "field": "total"}
    ]
}
```

### Return Format

```python
{
    "success": True,
    "data": {
        "count": 1580,
        "sum_total": 125480.50,
        "avg_total": 79.42,
        "min_total": 5.99,
        "max_total": 1250.00
    }
}
```

---

## HAVING Clause

Filter grouped results (similar to WHERE, but for aggregations).

### Request Format

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "SUM",
        "field": "total",
        "group_by": "user_id"
    },
    "having": "sum_total > 1000"
}
```

**Return Format:**
```python
{
    "success": True,
    "data": [
        {"user_id": 1, "sum_total": 1250.50},
        {"user_id": 5, "sum_total": 1842.30}
    ]
}
# Only users with total orders > 1000
```

---

## ORDER BY with Aggregations

Sort aggregated results.

### Request Format

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "SUM",
        "field": "total",
        "group_by": "user_id"
    },
    "order_by": "sum_total DESC"
}
```

**Return Format:**
```python
{
    "success": True,
    "data": [
        {"user_id": 5, "sum_total": 1842.30},
        {"user_id": 1, "sum_total": 1250.50},
        {"user_id": 3, "sum_total": 842.30},
        {"user_id": 2, "sum_total": 523.00}
    ]
}
# Top spenders first
```

---

## LIMIT with Aggregations

Limit aggregated results.

### Request Format

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "SUM",
        "field": "total",
        "group_by": "user_id"
    },
    "order_by": "sum_total DESC",
    "limit": 10
}
```

**Return Format:**
```python
{
    "success": True,
    "data": [
        # Top 10 spenders
        {"user_id": 5, "sum_total": 1842.30},
        {"user_id": 1, "sum_total": 1250.50},
        ...
    ]
}
```

---

## Aggregation with WHERE

Combine aggregations with WHERE filtering.

### Request Format

```python
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "SUM",
        "field": "total",
        "group_by": "user_id"
    },
    "where": "status = 'completed' AND created_at > '2024-01-01'"
}
```

**What happens:**
1. Filter rows with WHERE clause
2. Group filtered rows by user_id
3. Compute SUM for each group

---

## Use Cases

### Sales Analytics

```python
# Total revenue
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {"function": "SUM", "field": "total"}
}

# Revenue by month
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "SUM",
        "field": "total",
        "group_by": "month"
    }
}

# Top customers
request = {
    "model": "@.zSchema.orders",
    "action": "read",
    "aggregate": {
        "function": "SUM",
        "field": "total",
        "group_by": "user_id"
    },
    "order_by": "sum_total DESC",
    "limit": 10
}
```

### User Analytics

```python
# Active users count
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "aggregate": {"function": "COUNT"},
    "where": "last_login > '2024-01-01'"
}

# Average age by region
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "aggregate": {
        "function": "AVG",
        "field": "age",
        "group_by": "region"
    }
}
```

### Product Analytics

```python
# Price statistics
request = {
    "model": "@.zSchema.products",
    "action": "read",
    "aggregate": [
        {"function": "MIN", "field": "price"},
        {"function": "MAX", "field": "price"},
        {"function": "AVG", "field": "price"}
    ]
}

# Products by category
request = {
    "model": "@.zSchema.products",
    "action": "read",
    "aggregate": {
        "function": "COUNT",
        "group_by": "category"
    }
}
```

---

## Error Handling

All aggregation operations include error handling:

### Invalid Function

```python
{
    "success": False,
    "error": "Unknown aggregation function: AVERAGE"
}
# Valid: AVG, not AVERAGE
```

### Missing Field

```python
{
    "success": False,
    "error": "Field 'total' required for SUM aggregation"
}
```

### Type Mismatch

```python
{
    "success": False,
    "error": "Cannot compute SUM on TEXT field 'name'"
}
# SUM only works on INTEGER/REAL
```

---

## Performance Considerations

### Indexed Columns

Use indexed columns in GROUP BY for better performance:

```python
# Good: GROUP BY indexed column (user_id is foreign key)
request = {
    "aggregate": {"function": "COUNT", "group_by": "user_id"}
}

# Slow: GROUP BY non-indexed column
request = {
    "aggregate": {"function": "COUNT", "group_by": "notes"}
}
```

### WHERE Before Aggregation

Filter with WHERE before aggregation to reduce dataset:

```python
# Good: Filter first, then aggregate
request = {
    "where": "status = 'completed'",
    "aggregate": {"function": "SUM", "field": "total"}
}

# Bad: Aggregate all, filter with HAVING
request = {
    "aggregate": {"function": "SUM", "field": "total", "group_by": "status"},
    "having": "status = 'completed'"
}
```

---

## Best Practices

### 1. Use COUNT(*) for Total Rows

```python
# Good: COUNT without field
request = {"aggregate": {"function": "COUNT"}}

# Also works: COUNT on specific field
request = {"aggregate": {"function": "COUNT", "field": "id"}}
```

### 2. Combine Multiple Aggregations

```python
# Good: One query for all stats
request = {
    "aggregate": [
        {"function": "COUNT"},
        {"function": "AVG", "field": "age"},
        {"function": "MIN", "field": "age"},
        {"function": "MAX", "field": "age"}
    ]
}

# Bad: Multiple queries
count = zdata.handle_request({"aggregate": {"function": "COUNT"}})
avg = zdata.handle_request({"aggregate": {"function": "AVG", "field": "age"}})
```

### 3. Use ORDER BY with GROUP BY

```python
# Good: Sorted groups
request = {
    "aggregate": {"function": "COUNT", "group_by": "status"},
    "order_by": "count DESC"
}

# Bad: Unsorted (random order)
request = {
    "aggregate": {"function": "COUNT", "group_by": "status"}
}
```

---

## See Also

- [crud_operations_GUIDE.md](crud_operations_GUIDE.md) - CRUD operations
- [parsers_GUIDE.md](parsers_GUIDE.md) - WHERE clause parsing
- [backends_GUIDE.md](backends_GUIDE.md) - Backend-specific aggregation

---

**[← Back to zData Guide](../zData_GUIDE.md)**
