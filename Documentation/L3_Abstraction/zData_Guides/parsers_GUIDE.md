# zData Parsers Module Guide

> **Module:** `zOS/core/L3_Abstraction/m_zData/zData_modules/shared/parsers/`  
> **Purpose:** WHERE clause parsing, value parsing, and query expression evaluation.

---

## Overview

The `parsers` module provides query parsing capabilities:
- **WHERE Parser** - Parse SQL-like WHERE clauses
- **Value Parser** - Parse and convert typed values
- **Expression Evaluation** - Evaluate complex conditions
- **Operator Support** - Comparison, logical, pattern matching

---

## Architecture

```
Parsers Module
├── where_parser.py: WHERE clause parsing and evaluation
├── value_parser.py: Value parsing and type conversion
└── __init__.py: Public API exports
```

---

## WHERE Parser

Parses SQL-like WHERE clauses into structured conditions.

### Supported Operators

#### Comparison Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Equals | `age = 25` |
| `!=` | Not equals | `status != 'deleted'` |
| `<` | Less than | `age < 18` |
| `<=` | Less than or equal | `age <= 65` |
| `>` | Greater than | `score > 100` |
| `>=` | Greater than or equal | `score >= 50` |

#### Pattern Matching

| Operator | Description | Example |
|----------|-------------|---------|
| `LIKE` | Pattern match | `name LIKE 'A%'` |
| `NOT LIKE` | Negative pattern | `email NOT LIKE '%@spam.com'` |

**LIKE patterns:**
- `%` - Matches any sequence of characters
- `_` - Matches single character
- `A%` - Starts with A
- `%A` - Ends with A
- `%A%` - Contains A

#### Set Operations

| Operator | Description | Example |
|----------|-------------|---------|
| `IN` | Value in list | `status IN ('active', 'pending')` |
| `NOT IN` | Value not in list | `role NOT IN ('guest', 'banned')` |

#### Range Operations

| Operator | Description | Example |
|----------|-------------|---------|
| `BETWEEN` | Value in range | `age BETWEEN 18 AND 65` |
| `NOT BETWEEN` | Value outside range | `score NOT BETWEEN 0 AND 50` |

#### NULL Operations

| Operator | Description | Example |
|----------|-------------|---------|
| `IS NULL` | Field is NULL | `deleted_at IS NULL` |
| `IS NOT NULL` | Field is not NULL | `email IS NOT NULL` |

#### Logical Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `AND` | Logical AND | `age > 18 AND status = 'active'` |
| `OR` | Logical OR | `role = 'admin' OR role = 'moderator'` |
| `NOT` | Logical NOT | `NOT (status = 'deleted')` |

---

## WHERE Clause Examples

### Simple Conditions

```python
# Equality
where = "name = 'Alice'"
where = "age = 25"
where = "active = true"

# Comparison
where = "age > 18"
where = "score <= 100"
where = "created_at < '2024-01-01'"

# Pattern matching
where = "name LIKE 'A%'"           # Starts with A
where = "email LIKE '%@gmail.com'" # Gmail addresses
where = "code LIKE '___-____'"     # Pattern: XXX-XXXX
```

### Complex Conditions

```python
# Multiple conditions with AND
where = "age > 18 AND status = 'active'"
where = "role = 'admin' AND last_login > '2024-01-01'"

# Multiple conditions with OR
where = "status = 'pending' OR status = 'approved'"
where = "role = 'admin' OR role = 'moderator'"

# Mixed AND/OR (precedence matters!)
where = "(age > 18 AND status = 'active') OR role = 'admin'"
where = "status = 'active' AND (role = 'admin' OR role = 'moderator')"
```

### Set Operations

```python
# IN operator
where = "status IN ('active', 'pending', 'approved')"
where = "role IN ('admin', 'moderator')"

# NOT IN operator
where = "status NOT IN ('deleted', 'banned')"
```

### Range Operations

```python
# BETWEEN operator
where = "age BETWEEN 18 AND 65"
where = "score BETWEEN 0 AND 100"
where = "created_at BETWEEN '2024-01-01' AND '2024-12-31'"

# NOT BETWEEN operator
where = "age NOT BETWEEN 0 AND 17"
```

### NULL Checks

```python
# IS NULL
where = "deleted_at IS NULL"      # Not deleted
where = "verified_at IS NULL"     # Not verified

# IS NOT NULL
where = "email IS NOT NULL"       # Has email
where = "completed_at IS NOT NULL"  # Completed
```

---

## Value Parser

Parses and converts string values to typed values.

### Type Conversion

```python
from parsers.value_parser import ValueParser

parser = ValueParser()

# String values
value = parser.parse("'Alice'", "TEXT")
# Returns: "Alice" (str)

# Integer values
value = parser.parse("25", "INTEGER")
# Returns: 25 (int)

# Float values
value = parser.parse("3.14", "REAL")
# Returns: 3.14 (float)

# Boolean values
value = parser.parse("true", "BOOLEAN")
# Returns: True (bool)

# Timestamp values
value = parser.parse("'2024-01-15 10:30:00'", "TIMESTAMP")
# Returns: "2024-01-15 10:30:00" (str, ISO format)
```

### String Quoting

Values can be quoted with single or double quotes:

```python
# Single quotes
where = "name = 'Alice'"

# Double quotes
where = 'name = "Alice"'

# Escape quotes
where = "name = 'O''Brien'"  # O'Brien
where = 'name = "Say \\"hello\\""'  # Say "hello"
```

### Null Values

```python
# NULL keyword
where = "deleted_at = NULL"  # Same as: deleted_at IS NULL

# NOT NULL
where = "email != NULL"      # Same as: email IS NOT NULL
```

---

## Expression Evaluation

WHERE parser evaluates expressions against row data.

### Parse and Evaluate

```python
from parsers.where_parser import WhereParser

parser = WhereParser()

# Parse WHERE clause
condition = parser.parse("age > 18 AND status = 'active'")

# Evaluate against row data
row = {"age": 25, "status": "active"}
matches = parser.evaluate(condition, row)
# Returns: True

row = {"age": 15, "status": "active"}
matches = parser.evaluate(condition, row)
# Returns: False
```

### Conditional Evaluation

```python
# AND logic (both must be true)
condition = "age > 18 AND score > 50"
row = {"age": 25, "score": 75}  # True
row = {"age": 25, "score": 30}  # False
row = {"age": 15, "score": 75}  # False

# OR logic (either can be true)
condition = "role = 'admin' OR role = 'moderator'"
row = {"role": "admin"}      # True
row = {"role": "moderator"}  # True
row = {"role": "user"}       # False

# NOT logic (negation)
condition = "NOT (status = 'deleted')"
row = {"status": "active"}   # True
row = {"status": "deleted"}  # False
```

---

## Operator Precedence

Operators are evaluated in this order (highest to lowest):

1. **Parentheses** - `()`
2. **NOT** - `NOT`
3. **Comparison** - `=`, `!=`, `<`, `<=`, `>`, `>=`
4. **Pattern** - `LIKE`, `IN`, `BETWEEN`, `IS NULL`
5. **AND** - `AND`
6. **OR** - `OR`

### Examples

```python
# Without parentheses (AND binds tighter than OR)
where = "role = 'admin' OR status = 'active' AND age > 18"
# Evaluated as: role = 'admin' OR (status = 'active' AND age > 18)

# With parentheses (explicit grouping)
where = "(role = 'admin' OR status = 'active') AND age > 18"
# Evaluated as: (role = 'admin' OR status = 'active') AND age > 18

# NOT has high precedence
where = "NOT status = 'deleted' AND age > 18"
# Evaluated as: (NOT (status = 'deleted')) AND age > 18
```

---

## Case Sensitivity

### Field Names

Field names are case-sensitive by default:

```python
# Schema defines: name, email, age
where = "name = 'Alice'"   # Valid
where = "Name = 'Alice'"   # Error: field 'Name' not found
where = "NAME = 'Alice'"   # Error: field 'NAME' not found
```

### Operators

Operators are case-insensitive:

```python
# All valid (equivalent)
where = "age > 18 AND status = 'active'"
where = "age > 18 and status = 'active'"
where = "age > 18 AnD status = 'active'"

# LIKE is case-insensitive
where = "name LIKE 'a%'"
where = "name like 'a%'"
```

### String Values

String comparisons are case-sensitive by default:

```python
where = "name = 'Alice'"   # Matches "Alice"
where = "name = 'alice'"   # Does NOT match "Alice"

# Use LIKE with % for case-insensitive (backend-dependent)
where = "name LIKE 'alice'"  # May match "Alice" (SQLite does, PostgreSQL doesn't)
```

---

## Error Handling

Parser errors return structured error messages:

### Syntax Errors

```python
# Missing quotes
where = "name = Alice"
# Error: Syntax error: missing quotes around string value

# Unmatched parentheses
where = "(age > 18 AND status = 'active'"
# Error: Syntax error: unmatched parentheses

# Invalid operator
where = "age === 25"
# Error: Invalid operator: ===
```

### Field Errors

```python
# Unknown field
where = "unknown_field = 'value'"
# Error: Unknown field: unknown_field

# Type mismatch
where = "age = 'twenty-five'"
# Error: Type mismatch: expected INTEGER, got TEXT
```

---

## Performance Considerations

### Indexed Fields

Use indexed fields in WHERE clauses for better performance:

```python
# Good: WHERE on primary key (indexed)
where = "id = 123"

# Good: WHERE on indexed field
where = "email = 'alice@example.com'"

# Slow: WHERE on non-indexed field
where = "bio LIKE '%developer%'"
```

### LIKE Patterns

Leading wildcards prevent index usage:

```python
# Good: Can use index
where = "name LIKE 'A%'"  # Starts with A

# Bad: Cannot use index (full table scan)
where = "name LIKE '%Alice%'"  # Contains Alice
```

### Complex Conditions

Simplify complex conditions when possible:

```python
# Good: Simple condition
where = "status = 'active' AND age > 18"

# Bad: Overly complex (hard to optimize)
where = "(status = 'active' OR status = 'pending') AND (age > 18 OR role = 'admin') AND (NOT (deleted_at IS NOT NULL))"
```

---

## Best Practices

### 1. Use Parentheses for Clarity

```python
# Good: Explicit grouping
where = "(age > 18 AND status = 'active') OR role = 'admin'"

# Bad: Relies on precedence rules
where = "age > 18 AND status = 'active' OR role = 'admin'"
```

### 2. Quote String Values

```python
# Good: Quoted strings
where = "name = 'Alice'"

# Bad: Unquoted (syntax error)
where = "name = Alice"
```

### 3. Use IN for Multiple Values

```python
# Good: IN operator
where = "status IN ('active', 'pending', 'approved')"

# Bad: Multiple OR conditions
where = "status = 'active' OR status = 'pending' OR status = 'approved'"
```

### 4. Use BETWEEN for Ranges

```python
# Good: BETWEEN operator
where = "age BETWEEN 18 AND 65"

# Bad: Two comparisons
where = "age >= 18 AND age <= 65"
```

---

## Backend-Specific Behavior

### CSV Backend

WHERE clauses evaluated in Python:
- All operators supported
- LIKE is case-insensitive
- No database optimization

### SQLite Backend

WHERE clauses executed as SQL:
- All operators supported
- LIKE is case-insensitive by default
- Index optimization available

### PostgreSQL Backend

WHERE clauses executed as SQL:
- All operators supported
- LIKE is case-sensitive by default
- Advanced index optimization
- Use `ILIKE` for case-insensitive (PostgreSQL-specific)

---

## See Also

- [crud_operations_GUIDE.md](crud_operations_GUIDE.md) - CRUD operations using WHERE
- [validators_GUIDE.md](validators_GUIDE.md) - Data validation
- [backends_GUIDE.md](backends_GUIDE.md) - Backend-specific WHERE handling

---

**[← Back to zData Guide](../zData_GUIDE.md)**
