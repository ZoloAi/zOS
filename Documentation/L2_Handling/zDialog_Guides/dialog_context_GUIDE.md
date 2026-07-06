# zDialog Context Module Guide

> **Module:** `zOS/core/L2_Handling/j_zDialog/dialog_modules/dialog_context.py`  
> **Purpose:** Context creation and placeholder injection for zDialog forms.

---

## Overview

The `dialog_context` module provides **Tier 1** foundation for the zDialog subsystem, handling:

1. **Context creation** - Standardized dialog context dictionaries
2. **Placeholder injection** - Sophisticated resolution of 5 placeholder types

| Function | Purpose |
|---|---|
| `create_dialog_context()` | Create standardized context dict from model and fields |
| `inject_placeholders()` | Recursively resolve placeholders in data structures |

---

## Architecture: Tier 1 Foundation

```
Tier 5: Package Root (__init__.py)
Tier 4: Facade (zDialog.py)
Tier 3: Package Aggregator (dialog_modules/__init__.py)
Tier 2: Submit Handler (dialog_submit.py)
Tier 1: Foundation (dialog_context.py) ← This module
```

**Design rationale:**
- **Lowest tier** - No dependencies on other dialog modules
- **Pure functions** - Stateless, testable, composable
- **Single responsibility** - Context creation and placeholder resolution only

---

## Public Functions

### `create_dialog_context()`

Create standardized dialog context dictionary.

**Signature:**
```python
def create_dialog_context(
    model: Optional[str],
    fields: List[Dict[str, Any]],
    logger: Any,
    zConv: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `model` | `Optional[str]` | Schema reference (e.g., `"@.zSchema.users"`). Triggers auto-validation if starts with `@`. |
| `fields` | `List[Dict[str, Any]]` | Field definitions for form |
| `logger` | `Any` | Logger instance for debug output |
| `zConv` | `Optional[Dict[str, Any]]` | Optional form data (collected values) |

**Returns:**
`Dict[str, Any]` - Standardized context dictionary:
```python
{
    "_dialogId": "…uuid4…",       # always generated (used by the server-side onSubmit registry)
    "model": "@.zSchema.users",   # Schema reference (may be None)
    "fields": [...],              # Field definitions
    "zConv": {...}                # only present when zConv is provided (absent otherwise)
}
```

**Example 1 - Basic context:**
```python
context = create_dialog_context(
    model="@.zSchema.users",
    fields=[
        {"name": "username", "type": "text"},
        {"name": "email", "type": "text"}
    ],
    logger=logger
)

# Returns:
# {
#     "_dialogId": "…uuid4…",
#     "model": "@.zSchema.users",
#     "fields": [{"name": "username", "type": "text"}, ...]
#     # no "zConv" key (none provided)
# }
```

**Example 2 - With form data:**
```python
context = create_dialog_context(
    model="@.zSchema.users",
    fields=[{"name": "username", "type": "text"}],
    logger=logger,
    zConv={"username": "alice"}
)

# Returns:
# {
#     "model": "@.zSchema.users",
#     "fields": [...],
#     "zConv": {"username": "alice"}
# }
```

---

### `inject_placeholders()`

Recursively resolve placeholders in data structures.

**Signature:**
```python
def inject_placeholders(
    obj: Any,
    zContext: Dict[str, Any],
    logger: Any
) -> Any
```

**Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `obj` | `Any` | Object to process (str, dict, list, or other) |
| `zContext` | `Dict[str, Any]` | Context dict containing `zConv` key with form data |
| `logger` | `Any` | Logger instance for debug output |

**Returns:**
`Any` - Object with all placeholders resolved

**Supported placeholder types:**

#### 1. Full zConv
Returns entire form data dictionary.

**Syntax:** `"zConv"` (exact string)

**Example:**
```python
zContext = {"zConv": {"username": "alice", "email": "alice@example.com"}}
result = inject_placeholders("zConv", zContext, logger)

# Returns: {"username": "alice", "email": "alice@example.com"}
```

#### 2. Dot Notation
Returns specific field value using dot notation.

**Syntax:** `"zConv.field_name"`

**Example:**
```python
zContext = {"zConv": {"username": "alice", "age": 25}}
result = inject_placeholders("zConv.username", zContext, logger)

# Returns: "alice"
```

#### 3. Bracket Notation
Returns specific field value using bracket notation.

**Syntax:** `"zConv['field_name']"` or `'zConv["field_name"]'`

**Example:**
```python
zContext = {"zConv": {"email": "alice@example.com"}}
result = inject_placeholders("zConv['email']", zContext, logger)

# Returns: "alice@example.com"
```

#### 4. Embedded Placeholders
Replaces placeholders within larger strings.

**Syntax:** Any string containing `zConv.field_name`

**Example:**
```python
zContext = {"zConv": {"user_id": 42, "status": "active"}}
query = "SELECT * FROM users WHERE id = zConv.user_id AND status = zConv.status"
result = inject_placeholders(query, zContext, logger)

# Returns: "SELECT * FROM users WHERE id = 42 AND status = 'active'"
# Note: Numbers not quoted, strings quoted automatically
```

**Smart value formatting (embedded path):**
- **Numeric strings** (`value.isdigit()`) → no quotes: `id = 42`
- **`int` / `float`** → no quotes via `str(value)`. *Note:* `bool` is an `int` subclass in Python, so booleans render capitalized (`True` / `False`), not `true`.
- **Other strings** → single-quoted: `status = 'active'`
- **Missing / `None` field** → the token is **not** substituted; a "field not found" warning is logged and `zConv.<field>` is left in the string as-is (no `NULL` conversion).

#### 5. Regex Pattern Matching
Uses `r'zConv\\.(\w+)'` to find all dot notation occurrences.

**Example:**
```python
zContext = {"zConv": {"id": 123, "name": "John"}}
text = "user_id = zConv.id AND name = zConv.name"
result = inject_placeholders(text, zContext, logger)

# Returns: "user_id = 123 AND name = 'John'"
```

---

## Recursive Resolution

Placeholders resolved recursively in nested structures:

**Example 1 - Nested dict:**
```python
zContext = {"zConv": {"username": "alice", "email": "alice@example.com"}}

data = {
    "user": {
        "name": "zConv.username",
        "contact": {
            "email": "zConv.email"
        }
    }
}

result = inject_placeholders(data, zContext, logger)

# Returns:
# {
#     "user": {
#         "name": "alice",
#         "contact": {"email": "alice@example.com"}
#     }
# }
```

**Example 2 - Lists:**
```python
zContext = {"zConv": {"id": 1, "name": "Alice", "role": "admin"}}

data = [
    "zConv.id",
    "zConv.name",
    {"role": "zConv.role"}
]

result = inject_placeholders(data, zContext, logger)

# Returns: [1, "Alice", {"role": "admin"}]
```

**Example 3 - Mixed:**
```python
zContext = {"zConv": {"user_id": 42, "username": "alice"}}

data = {
    "query": "WHERE id = zConv.user_id",
    "params": ["zConv.username"],
    "nested": {
        "field": "zConv.user_id"
    }
}

result = inject_placeholders(data, zContext, logger)

# Returns:
# {
#     "query": "WHERE id = 42",
#     "params": ["alice"],
#     "nested": {"field": 42}
# }
```

---

## Error Handling

**Missing field — standalone dot/bracket placeholder → returns `None`:**
```python
zContext = {"zConv": {"username": "alice"}}
result = inject_placeholders("zConv.email", zContext, logger)
# Returns: None  (zconv_data.get("email"))

# Embedded missing field is different — the token is left in place and a
# "field not found" warning is logged:
result = inject_placeholders("WHERE email = zConv.email", zContext, logger)
# Returns: "WHERE email = zConv.email"  (unchanged, warning logged)
```

**Invalid syntax:**
```python
result = inject_placeholders("zConv..invalid", zContext, logger)

# Logs error: "Failed to parse placeholder: zConv..invalid"
# Returns: "zConv..invalid" (unchanged)
```

**No zConv key:**
```python
zContext = {}  # Missing zConv key
result = inject_placeholders("zConv.username", zContext, logger)

# Returns: "zConv.username" (unchanged, no error - graceful degradation)
```

---

## Implementation Details

### Regex Pattern

The module uses this regex pattern to find dot notation placeholders:

```python
_REGEX_ZCONV_DOT_NOTATION = r'zConv\.(\w+)'
```

**Matches:**
- `zConv.username` → Captures `username`
- `zConv.user_id` → Captures `user_id`
- `zConv.field123` → Captures `field123`

**Does not match:**
- `zConv` (exact, handled separately)
- `zConv['field']` (bracket notation, handled separately)
- `zConv..invalid` (double dots)
- `zConv.field.nested` (nested dots not supported)

### Value Formatting

Actual formatting logic inside the embedded-placeholder loop (no separate helper):

```python
value = zconv_data.get(field)
if value is not None:
    if isinstance(value, str) and value.isdigit():
        replacement = value           # numeric string → no quotes
    elif isinstance(value, (int, float)):
        replacement = str(value)      # int/float (and bool) → no quotes
    else:
        replacement = f"'{value}'"    # other strings → single-quoted
    result = result.replace(f"zConv.{field}", replacement)
else:
    logger.warning(_WARNING_FIELD_NOT_FOUND, field)   # left unreplaced
```

> ⚠️ This is **string interpolation**, not parameterization — a latent SQL-injection vector if the result is run as a **raw** query. Prefer structured `data:`/`where:` dicts; the authoritative escaping boundary lives in `m_zData`.

### Constants

All constants imported from `dialog_constants.py`:

```python
from .dialog_constants import (
    KEY_ZCONV,                        # "zConv"
    _PLACEHOLDER_FULL,                # "zConv" (exact match)
    _PLACEHOLDER_PREFIX,              # "zConv." (dot notation prefix)
    _DOT_SEPARATOR,                   # "."
    _BRACKET_OPEN,                    # "["
    _BRACKET_CLOSE,                   # "]"
    _QUOTE_CHARS,                     # ["'", '"'] (bracket notation quotes)
    _REGEX_ZCONV_DOT_NOTATION,        # r'zConv\.(\w+)'
    _EXPECTED_DOT_NOTATION_PARTS,     # 2 (split count)
    _WARNING_FIELD_NOT_FOUND,         # Error message
    _ERROR_PARSE_PLACEHOLDER_FAILED,  # Error message
    _ERROR_PARSE_EMBEDDED_FAILED,     # Error message
)
```

---

## Integration Points

**Used by:**
- `zDialog.py` — context creation in the `handle()` method
- `dialog_submit.py` — placeholder injection before submission

**Dependencies:**
- `dialog_constants.py` - Constants, keys, error messages
- Standard library: `re` module (regex pattern matching), `uuid` (`_dialogId`)

**No external dependencies** - Pure foundation layer, stdlib only.

---

## Best Practices

### DO:
✅ Use dot notation for simple field access: `"zConv.username"`  
✅ Use embedded placeholders for SQL queries: `"WHERE id = zConv.user_id"`  
✅ Check return value for None when field missing  
✅ Log context creation for debugging  
✅ Use full zConv when submitting entire form data  

### DON'T:
❌ Use nested dot notation: `"zConv.user.name"` (not supported)  
❌ Mix quote types in bracket notation: `"zConv['email\"]"` (parse error)  
❌ Manually quote values in embedded placeholders (auto-formatted)  
❌ Assume placeholder resolution always succeeds (check for unchanged values)  

---

## Performance Considerations

**Recursive resolution:**
- Handles deep nesting efficiently (tail recursion)
- No performance impact for typical form sizes (< 100 fields)
- Regex matching is O(n) where n = string length

**Optimization tips:**
- Use full zConv (`"zConv"`) when possible (no parsing needed)
- Avoid deeply nested structures (> 10 levels) in onSubmit
- Pre-format queries when possible to minimize placeholder parsing

---

## Testing

**Unit test coverage:**
- ✅ Full zConv placeholder
- ✅ Dot notation (valid and invalid)
- ✅ Bracket notation (single and double quotes)
- ✅ Embedded placeholders (single and multiple)
- ✅ Recursive resolution (dicts, lists, mixed)
- ✅ Error handling (missing fields, invalid syntax)
- ✅ Value formatting (strings, numbers, booleans, None)

**Test files:**
- `tests/test_dialog_context.py` - Unit tests
- `tests/test_placeholders.py` - Placeholder-specific tests

---

## Version History

- **v1.5.4**: Industry-grade refactor
  - Added: Type hints (100% coverage)
  - Added: Constants from dialog_constants
  - Added: Comprehensive docstrings (400+ lines)
  - Enhanced: Error handling and logging
- **v1.5.3**: Embedded placeholder support
  - Added: Regex pattern matching
  - Added: Smart value formatting
- **v1.5.2**: Initial implementation
  - Basic placeholder resolution
  - Context creation

---

**[← Back to zDialog Guide](../zDialog_GUIDE.md)**
