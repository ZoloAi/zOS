# zData Validators Module Guide

> **Module:** `zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validators/`  
> **Purpose:** Schema validation, format validation, and plugin validation for data integrity.

---

## Overview

The `validators` module provides comprehensive validation:
- **Schema Validation** - Type checking, required fields, constraints
- **Format Validation** - Email, URL, phone, SSN, etc.
- **Plugin Validation** - Custom zFunc validators
- **Pattern Validation** - Regex-based validation
- **Numeric Validation** - Range, min, max validation
- **String Validation** - Length, pattern validation

---

## Architecture

```
Validators Module
├── core.py: Main DataValidator class
├── format_validator.py: Email, URL, phone format validation
├── plugin_validator.py: zFunc custom validators
├── pattern_validator.py: Regex pattern validation
├── numeric_validator.py: Range and numeric validation
├── string_validator.py: Length and string validation
└── constants.py: Validation constants and error messages
```

---

## DataValidator Class

Main validation orchestrator.

### Initialization

```python
from shared.validator import DataValidator

validator = DataValidator(schema, zfunc_handler=None)
```

**Parameters:**
- `schema` (dict): Schema with field definitions
- `zfunc_handler` (optional): zFunc handler for custom validators

### Validate Data

```python
is_valid = validator.validate(data)
errors = validator.get_errors()
```

**Returns:** `True` if valid, `False` if errors found

**Example:**
```python
schema = {
    "users": {
        "name": {"type": "TEXT", "required": True},
        "email": {"type": "TEXT", "format": "email"},
        "age": {"type": "INTEGER", "min": 0, "max": 150}
    }
}

validator = DataValidator(schema)

# Valid data
data = {"name": "Alice", "email": "alice@example.com", "age": 25}
is_valid = validator.validate(data)  # True

# Invalid data
data = {"email": "not-an-email", "age": 200}
is_valid = validator.validate(data)  # False
errors = validator.get_errors()
# [
#     "Field 'name' is required",
#     "Field 'email' has invalid format: email",
#     "Field 'age' exceeds maximum value: 150"
# ]
```

---

## Type Validation

Validates field types against schema.

### Supported Types

| Type | Python Type | Example |
|------|-------------|---------|
| `TEXT` | str | "Alice" |
| `INTEGER` | int | 42 |
| `REAL` | float | 3.14 |
| `BOOLEAN` | bool | True |
| `TIMESTAMP` | str (ISO format) | "2024-01-15 10:30:00" |
| `DATE` | str (ISO format) | "2024-01-15" |
| `TIME` | str (ISO format) | "10:30:00" |
| `JSON` | dict/list | {"key": "value"} |

### Schema Definition

```yaml
users:
  name: TEXT
  age: INTEGER
  score: REAL
  active: BOOLEAN
  created_at: TIMESTAMP
  birth_date: DATE
  login_time: TIME
  metadata: JSON
```

### Validation Examples

```python
# TEXT validation
data = {"name": "Alice"}  # Valid
data = {"name": 123}      # Invalid: must be str

# INTEGER validation
data = {"age": 25}        # Valid
data = {"age": "25"}      # Invalid: must be int
data = {"age": 25.5}      # Invalid: must be int

# TIMESTAMP validation
data = {"created_at": "2024-01-15 10:30:00"}  # Valid
data = {"created_at": "invalid"}              # Invalid: bad format
```

---

## Required Fields

Ensure fields are present in data.

### Schema Definition

```yaml
users:
  name:
    type: TEXT
    required: true
  email:
    type: TEXT
    required: true
  bio:
    type: TEXT
    required: false  # Optional
```

### Validation

```python
# Valid: All required fields present
data = {"name": "Alice", "email": "alice@example.com"}

# Invalid: Missing required field
data = {"name": "Alice"}
# Error: Field 'email' is required

# Valid: Optional field can be omitted
data = {"name": "Alice", "email": "alice@example.com"}
# (bio is optional)
```

---

## Format Validation

Validates field formats against predefined patterns.

### Supported Formats

| Format | Description | Example |
|--------|-------------|---------|
| `email` | Email address | alice@example.com |
| `url` | HTTP/HTTPS URL | https://example.com |
| `phone` | Phone number | +1-555-123-4567 |
| `ssn` | Social Security Number | 123-45-6789 |
| `zip` | ZIP code | 12345 or 12345-6789 |
| `ipv4` | IPv4 address | 192.168.1.1 |
| `ipv6` | IPv6 address | 2001:0db8::1 |
| `uuid` | UUID v4 | 550e8400-e29b-41d4-a716-446655440000 |
| `date` | ISO date | 2024-01-15 |
| `time` | ISO time | 10:30:00 |
| `datetime` | ISO datetime | 2024-01-15T10:30:00 |

### Schema Definition

```yaml
users:
  email:
    type: TEXT
    format: email
  website:
    type: TEXT
    format: url
  phone:
    type: TEXT
    format: phone
```

### Validation Examples

```python
# Email validation
data = {"email": "alice@example.com"}  # Valid
data = {"email": "not-an-email"}       # Invalid

# URL validation
data = {"website": "https://example.com"}  # Valid
data = {"website": "not-a-url"}            # Invalid

# Phone validation
data = {"phone": "+1-555-123-4567"}  # Valid
data = {"phone": "12345"}            # Invalid
```

---

## Pattern Validation

Custom regex patterns for validation.

### Schema Definition

```yaml
users:
  username:
    type: TEXT
    pattern: "^[a-zA-Z0-9_]{3,20}$"  # Alphanumeric + underscore, 3-20 chars
  product_code:
    type: TEXT
    pattern: "^[A-Z]{2}-[0-9]{4}$"   # Two letters, dash, four digits
```

### Validation Examples

```python
# Username validation
data = {"username": "alice_123"}  # Valid
data = {"username": "a"}          # Invalid: too short
data = {"username": "alice@123"}  # Invalid: invalid character

# Product code validation
data = {"product_code": "AB-1234"}  # Valid
data = {"product_code": "AB1234"}   # Invalid: missing dash
```

---

## Numeric Validation

Range and constraint validation for numbers.

### Schema Definition

```yaml
users:
  age:
    type: INTEGER
    min: 0
    max: 150
  score:
    type: REAL
    min: 0.0
    max: 100.0
  rating:
    type: INTEGER
    min: 1
    max: 5
```

### Validation Examples

```python
# Age validation
data = {"age": 25}    # Valid
data = {"age": -5}    # Invalid: below minimum
data = {"age": 200}   # Invalid: above maximum

# Score validation
data = {"score": 85.5}   # Valid
data = {"score": -10.0}  # Invalid: below minimum
data = {"score": 150.0}  # Invalid: above maximum
```

---

## String Validation

Length and content validation for strings.

### Schema Definition

```yaml
users:
  name:
    type: TEXT
    minlength: 2
    maxlength: 50
  bio:
    type: TEXT
    maxlength: 500
  code:
    type: TEXT
    length: 6  # Exact length
```

### Validation Examples

```python
# Name validation
data = {"name": "Alice"}  # Valid
data = {"name": "A"}      # Invalid: too short (minlength: 2)
data = {"name": "A" * 100}  # Invalid: too long (maxlength: 50)

# Code validation (exact length)
data = {"code": "ABC123"}  # Valid (length: 6)
data = {"code": "ABC12"}   # Invalid: wrong length
```

---

## Enum Validation

Restrict values to predefined set.

### Schema Definition

```yaml
users:
  status:
    type: TEXT
    enum: [active, inactive, pending, deleted]
  role:
    type: TEXT
    enum: [user, admin, moderator]
```

### Validation Examples

```python
# Status validation
data = {"status": "active"}    # Valid
data = {"status": "suspended"}  # Invalid: not in enum

# Role validation
data = {"role": "admin"}   # Valid
data = {"role": "guest"}   # Invalid: not in enum
```

---

## Unique Constraint

Ensure field values are unique across all rows.

### Schema Definition

```yaml
users:
  email:
    type: TEXT
    unique: true
  username:
    type: TEXT
    unique: true
```

### Validation

```python
# Unique validation checks existing data
data = {"email": "alice@example.com"}  # Valid if not exists
data = {"email": "alice@example.com"}  # Invalid if already exists
# Error: Field 'email' must be unique, value already exists
```

**Note:** Unique validation requires querying existing data in the database.

---

## Plugin Validation (zFunc)

Custom validators via zFunc integration.

### Schema Definition

```yaml
users:
  password:
    type: TEXT
    validator: "@.zFunc.validate_password_strength"
  username:
    type: TEXT
    validator: "@.zFunc.check_username_available"
```

### Validator Function

```python
# @.zFunc.validate_password_strength
def validate_password_strength(value, context):
    """
    Custom password validation.
    
    Args:
        value: Field value to validate
        context: Validation context (field name, schema, etc.)
    
    Returns:
        True if valid, raises ValueError if invalid
    """
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    
    if not any(c.isupper() for c in value):
        raise ValueError("Password must contain uppercase letter")
    
    if not any(c.isdigit() for c in value):
        raise ValueError("Password must contain digit")
    
    return True
```

### Validation Examples

```python
# Valid password
data = {"password": "Secure123"}  # Valid

# Invalid password
data = {"password": "weak"}       # Invalid
# Error: Password must be at least 8 characters
```

---

## Validation Errors

All validators return structured error messages.

### Error Format

```python
errors = [
    "Field 'email' is required",
    "Field 'age' has invalid type: expected INTEGER, got TEXT",
    "Field 'email' has invalid format: email",
    "Field 'age' exceeds maximum value: 150",
    "Field 'status' must be one of: [active, inactive, pending]",
    "Field 'email' must be unique, value already exists"
]
```

### Error Handling

```python
validator = DataValidator(schema)

is_valid = validator.validate(data)
if not is_valid:
    errors = validator.get_errors()
    for error in errors:
        print(f"❌ {error}")
    
    # Return error response
    return {
        "success": False,
        "errors": errors
    }
```

---

## Validation Context

Validators receive context for advanced validation:

```python
context = {
    "field_name": "email",
    "field_schema": {"type": "TEXT", "format": "email"},
    "full_schema": {...},
    "operation": "insert",  # or "update"
    "existing_data": [...],  # For unique validation
}
```

---

## Best Practices

### 1. Define Required Fields

```yaml
# Good: Explicit required fields
users:
  name:
    type: TEXT
    required: true
  email:
    type: TEXT
    required: true

# Bad: Assume fields are required
users:
  name: TEXT
  email: TEXT
```

### 2. Use Format Validators

```yaml
# Good: Format validation
users:
  email:
    type: TEXT
    format: email

# Bad: Manual pattern matching
users:
  email:
    type: TEXT
    pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
```

### 3. Add Range Constraints

```yaml
# Good: Range constraints
users:
  age:
    type: INTEGER
    min: 0
    max: 150

# Bad: No constraints (allows negative or huge values)
users:
  age: INTEGER
```

### 4. Use Enums for Status Fields

```yaml
# Good: Enum validation
users:
  status:
    type: TEXT
    enum: [active, inactive, deleted]

# Bad: Free-form text (allows typos)
users:
  status: TEXT
```

---

## Performance Considerations

**Field-level validation:**
- Fast (< 1ms per field)
- No database queries

**Format validation:**
- Regex matching (< 1ms)
- Cached compiled patterns

**Unique validation:**
- Requires database query
- Can be slow for large datasets
- Use indexes on unique fields

**Plugin validation:**
- Depends on validator implementation
- Can be slow if validator does I/O

---

## See Also

- [crud_operations_GUIDE.md](crud_operations_GUIDE.md) - CRUD operations with validation
- [schema_manager_GUIDE.md](schema_manager_GUIDE.md) - Schema loading and structure
- [parsers_GUIDE.md](parsers_GUIDE.md) - WHERE clause and value parsing
- [zFunc Guide](../../L2_Handling/zFunc_GUIDE.md) - Custom validator functions

---

**[← Back to zData Guide](../zData_GUIDE.md)**
