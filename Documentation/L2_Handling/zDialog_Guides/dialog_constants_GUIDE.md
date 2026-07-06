# zDialog Constants Module Guide

> **Module:** `zOS/core/L2_Handling/j_zDialog/dialog_modules/dialog_constants.py`  
> **Purpose:** Shared constants, dictionary keys, and messages for zDialog subsystem.

---

## Overview

The `dialog_constants` module provides centralized constants for the zDialog subsystem, ensuring consistency across all modules and eliminating magic strings.

**Categories:**
1. **Dictionary Keys** - Standardized keys for data structures
2. **Display Configuration** - Colors, styles, indent levels
3. **Placeholder Constants** - Placeholder syntax and parsing
4. **WebSocket Events** - Event types for zBifrost mode
5. **Session Values** - Session-related constants
6. **Messages** - Log messages, errors, warnings

---

## Dictionary Keys

### Form Structure Keys

**Main form keys:**
```python
KEY_ZDIALOG = "zDialog"           # Top-level form key
KEY_MODEL = "model"               # Schema reference
KEY_FIELDS = "fields"             # Field definitions
KEY_TITLE = "title"               # Form title
KEY_ONSUBMIT = "onSubmit"         # Submission expression
```

**Usage example:**
```python
form_spec = {
    KEY_ZDIALOG: {                # "zDialog"
        KEY_MODEL: "@.zSchema.users",    # "model"
        KEY_FIELDS: [...],               # "fields"
        KEY_TITLE: "User Form",          # "title"
        KEY_ONSUBMIT: {...}              # "onSubmit"
    }
}
```

### Context Keys

**Dialog context keys:**
```python
KEY_ZCONV = "zConv"               # Collected form data
KEY_DATA = "data"                 # Generic data key
KEY_TABLE = "table"               # Explicit table/block name within the schema
KEY_DIALOG_MODE = "dialog_mode"   # Render-mode signal (e.g. confirm)
KEY_WEBSOCKET_DATA = "websocket_data"  # WebSocket-provided data (zBifrost)
```

### Dialog Modes

```python
DIALOG_MODE_CONFIRM = "confirm"   # fields: [] → confirm button / y-n prompt
```

**Usage:** when `fields` is empty, the facade sets `zContext[KEY_DIALOG_MODE] = DIALOG_MODE_CONFIRM` so every renderer (Bifrost, zCLI) reads the confirm intent from context instead of re-deriving from field count.

**Usage example:**
```python
zContext = {
    KEY_MODEL: "@.zSchema.users",
    KEY_FIELDS: [...],
    KEY_ZCONV: {                  # "zConv"
        "username": "alice",
        "email": "alice@example.com"
    }
}
```

### Submission Keys

**onSubmit expression keys:**
```python
KEY_ZDATA = "zData"               # zData command
KEY_ZCRUD = "zCRUD"               # zCRUD command (alias)
```

**Usage example:**
```python
on_submit = {
    KEY_ZDATA: {                  # "zData"
        "action": "create",
        "data": "zConv"
    }
}
```

---

## Display Configuration

### Colors

```python
COLOR_ZDIALOG = "ZDIALOG"         # zDialog display color (theme key)
COLOR_DISPATCH = "DISPATCH"       # dispatch display color (theme key)
```

**Usage:**
```python
walker.display.zDeclare(
    message="Form submitted",
    color=COLOR_ZDIALOG,          # "ZDIALOG"
    style="single"
)
```

### Styles

```python
_STYLE_SINGLE = "single"          # Single-line style
_STYLE_TILDE = "~"                # Tilde/return style
```

### Indent Levels

```python
_INDENT_DIALOG = 2                # Dialog message indent
_INDENT_SUBMIT = 3                # Submit message indent
```

---

## Placeholder Constants

### Placeholder Syntax

```python
_PLACEHOLDER_FULL = "zConv"       # Full zConv placeholder (exact match)
_PLACEHOLDER_PREFIX = "zConv."    # Dot notation prefix
```

**Usage:**
```python
# Full placeholder
if placeholder == _PLACEHOLDER_FULL:
    return zContext[KEY_ZCONV]

# Dot notation
if placeholder.startswith(_PLACEHOLDER_PREFIX):
    field_name = placeholder[len(_PLACEHOLDER_PREFIX):]
    return zContext[KEY_ZCONV][field_name]
```

### Parsing Characters

```python
_DOT_SEPARATOR = "."              # Dot notation separator
_BRACKET_OPEN = "["               # Bracket notation open
_BRACKET_CLOSE = "]"              # Bracket notation close
_QUOTE_CHARS = ["'", '"']         # Bracket notation quote chars
```

**Usage:**
```python
# Parse bracket notation: zConv['field'] or zConv["field"]
if _BRACKET_OPEN in placeholder and _BRACKET_CLOSE in placeholder:
    start = placeholder.index(_BRACKET_OPEN) + 1
    end = placeholder.index(_BRACKET_CLOSE)
    field_part = placeholder[start:end].strip()
    
    # Strip quotes if present
    for quote in _QUOTE_CHARS:
        field_part = field_part.strip(quote)
```

### Regex Pattern

```python
_REGEX_ZCONV_DOT_NOTATION = r'zConv\.(\w+)'  # Dot notation pattern
```

**Usage:**
```python
import re

text = "SELECT * FROM users WHERE id = zConv.user_id AND name = zConv.username"
matches = re.findall(_REGEX_ZCONV_DOT_NOTATION, text)
# Returns: ['user_id', 'username']

for match in matches:
    field_value = zContext[KEY_ZCONV].get(match)
    text = text.replace(f"zConv.{match}", format_value(field_value))
```

### Magic Numbers

```python
_EXPECTED_DOT_NOTATION_PARTS = 2  # Expected parts after split by "."
```

**Usage:**
```python
# Parse dot notation: "zConv.field_name"
parts = placeholder.split(_DOT_SEPARATOR)

if len(parts) != _EXPECTED_DOT_NOTATION_PARTS:
    logger.error(f"Invalid dot notation: {placeholder}")
    return placeholder  # Unchanged

prefix, field_name = parts
```

### Schema Path Separator

```python
_SCHEMA_PATH_SEPARATOR = "."      # Schema path separator (@.zSchema.users)
```

**Usage:**
```python
# Parse schema reference: "@.zSchema.users"
if model.startswith("@"):
    parts = model.split(_SCHEMA_PATH_SEPARATOR)
    # Returns: ["@", "zSchema", "users"]
```

---

## WebSocket Events

### Event Types

```python
_EVENT_VALIDATION_ERROR = "validation_error"  # Validation error event
```

**Usage:**
```python
# Broadcast validation errors in zBifrost mode
z.comm.websocket_events.send_event({
    "event": _EVENT_VALIDATION_ERROR,
    "errors": validation_errors
})
```

---

## Session Values

### Session Mode Values

```python
# Aliased from root zVocabulary (SSOT) — no local literal
from zOS.zVocabulary import ZMODE_ZBIFROST
_SESSION_VALUE_ZBIFROST = ZMODE_ZBIFROST   # "zBifrost"
```

The session-mode **key** (`SESSION_KEY_ZMODE`) is sourced from `a_zConfig` (`config_constants`), not redefined here.

**Usage:**
```python
# Check if running in zBifrost mode
if z.session.get(SESSION_KEY_ZMODE) == _SESSION_VALUE_ZBIFROST:
    # WebSocket mode - skip rendering, use pre-provided data
    pass
```

---

## Messages

### Log Messages

**Debug messages:**
```python
_DEBUG_CONTEXT_CREATED = "Dialog context created with model={model}, fields count={count}"
_DEBUG_SUBMIT_EXPR = "Processing onSubmit expression: {type}"
_DEBUG_CONTEXT_KEYS = "zContext keys: {keys}"
_DEBUG_DICT_PAYLOAD = "Dict payload after injection: {payload}"
```

**Info messages:**
```python
_INFO_DISPATCH_DICT = "Executing dict-based submission via zDispatch"
_LOG_AUTO_VALIDATION_ENABLED = "Auto-validation enabled (model starts with @)"
_LOG_AUTO_VALIDATION_PASSED = "Auto-validation passed"
_LOG_AUTO_VALIDATION_FAILED = "Auto-validation failed - returning None"
```

**Usage:**
```python
logger.debug(_DEBUG_CONTEXT_CREATED.format(
    model=model,
    count=len(fields)
))

logger.info(_INFO_DISPATCH_DICT)
```

### Error Messages

**Validation errors:**
```python
_ERROR_INVALID_TYPE_DIALOG = "zHorizontal must be a dict, got: {type}"
_ERROR_INVALID_TYPE_SUBMIT = "Invalid onSubmit type: {type} - must be dict"
```

**Missing dependencies:**
```python
_ERROR_NO_ZCLI = "No zcli instance provided"
_ERROR_NO_ZCLI_OR_WALKER = "No zcli or walker instance provided"
_ERROR_NO_WALKER = "No walker instance - cannot execute zDispatch"
```

**Placeholder parsing:**
```python
_ERROR_PARSE_PLACEHOLDER_FAILED = "Failed to parse placeholder: {placeholder}"
_ERROR_PARSE_EMBEDDED_FAILED = "Failed to parse embedded placeholder: {error}"
```

**Dispatch execution:**
```python
_ERROR_DISPATCH_FAILED = "zDispatch execution failed"
```

**WebSocket communication:**
```python
_LOG_WEBSOCKET_BROADCAST_FAILED = "Failed to broadcast validation errors via WebSocket"
```

**Usage:**
```python
if not isinstance(zHorizontal, dict):
    logger.error(_ERROR_INVALID_TYPE_DIALOG.format(
        type=type(zHorizontal).__name__
    ))
    return None
```

### Warning Messages

```python
_WARNING_FIELD_NOT_FOUND = "Field '{field}' not found in zConv"
```

**Usage:**
```python
if field_name not in zContext[KEY_ZCONV]:
    logger.warning(_WARNING_FIELD_NOT_FOUND.format(field=field_name))
    return placeholder  # Return unchanged
```

### Display Messages

**Ready messages:**
```python
_MSG_ZDIALOG = "zDialog"
_MSG_ZDIALOG_READY = "zDialog subsystem initialized"
_MSG_ZDIALOG_RETURN_VALIDATION_FAILED = "Returning None (validation failed)"
```

**Log prefixes:**
```python
_LOG_RECEIVED_ZHORIZONTAL = "Received zHorizontal"
_LOG_ZCONTEXT = "zContext"
_LOG_WEBSOCKET_DATA = "Using websocket_data from context"
_LOG_MODEL_FIELDS_SUBMIT = "Model: {model}, Fields: {count}, onSubmit: {has_submit}"
_LOG_ONSUBMIT_EXECUTE = "Executing onSubmit"
_LOG_ONSUBMIT_FAILED = "onSubmit execution failed"
_LOG_AUTO_VALIDATION_SKIPPED_NO_MODEL = "Auto-validation skipped (no model)"
_LOG_AUTO_VALIDATION_SKIPPED_PREFIX = "Auto-validation skipped (model does not start with @)"
_LOG_AUTO_VALIDATION_ERROR = "Auto-validation error: {error}"
```

**Usage:**
```python
logger.info(_LOG_RECEIVED_ZHORIZONTAL)
logger.debug(_LOG_MODEL_FIELDS_SUBMIT.format(
    model=model,
    count=len(fields),
    has_submit=bool(on_submit)
))
```

---

## Import Patterns

### All constants together

```python
from .dialog_constants import (
    # Dictionary keys
    KEY_ZDIALOG,
    KEY_MODEL,
    KEY_FIELDS,
    KEY_ZCONV,
    KEY_ONSUBMIT,
    
    # Display config
    COLOR_ZDIALOG,
    _STYLE_SINGLE,
    _INDENT_DIALOG,
    
    # Placeholder constants
    _PLACEHOLDER_FULL,
    _PLACEHOLDER_PREFIX,
    _REGEX_ZCONV_DOT_NOTATION,
    
    # Messages
    _ERROR_INVALID_TYPE_DIALOG,
    _LOG_AUTO_VALIDATION_ENABLED
)
```

### Grouped by category

```python
# Dictionary keys only
from .dialog_constants import (
    KEY_ZDIALOG,
    KEY_MODEL,
    KEY_FIELDS,
    KEY_ZCONV,
    KEY_ONSUBMIT,
    KEY_ZDATA,
    KEY_ZCRUD
)

# Placeholder constants only
from .dialog_constants import (
    _PLACEHOLDER_FULL,
    _PLACEHOLDER_PREFIX,
    _DOT_SEPARATOR,
    _BRACKET_OPEN,
    _BRACKET_CLOSE,
    _REGEX_ZCONV_DOT_NOTATION
)

# Error messages only
from .dialog_constants import (
    _ERROR_INVALID_TYPE_DIALOG,
    _ERROR_INVALID_TYPE_SUBMIT,
    _ERROR_NO_ZCLI,
    _ERROR_NO_WALKER
)
```

---

## Naming Conventions

### Public vs Private

**Public constants** (no underscore prefix):
- `KEY_*` - Dictionary keys
- `COLOR_*` - Display colors
- Used across multiple modules/subsystems

**Private constants** (underscore prefix):
- `_STYLE_*` - Internal display settings
- `_INDENT_*` - Internal layout values
- `_ERROR_*` - Error messages (module-internal)
- `_LOG_*` - Log messages (module-internal)
- `_DEBUG_*` - Debug messages (module-internal)
- `_PLACEHOLDER_*` - Placeholder parsing (module-internal)
- Used only within dialog_modules package

### Naming Patterns

**Dictionary keys:** `KEY_<NAME>`
```python
KEY_ZDIALOG = "zDialog"
KEY_MODEL = "model"
```

**Colors:** `COLOR_<NAME>`
```python
COLOR_ZDIALOG = "blue"
```

**Error messages:** `_ERROR_<DESCRIPTION>`
```python
_ERROR_INVALID_TYPE_DIALOG = "zHorizontal must be a dict, got: {type}"
```

**Log messages:** `_LOG_<DESCRIPTION>`
```python
_LOG_AUTO_VALIDATION_ENABLED = "Auto-validation enabled (model starts with @)"
```

**Debug messages:** `_DEBUG_<DESCRIPTION>`
```python
_DEBUG_CONTEXT_CREATED = "Dialog context created with model={model}, fields count={count}"
```

**Display messages:** `_MSG_<NAME>`
```python
_MSG_ZDIALOG = "zDialog"
_MSG_ZDIALOG_READY = "zDialog subsystem initialized"
```

**Style/Format:** `_STYLE_<NAME>` / `_INDENT_<NAME>`
```python
_STYLE_SINGLE = "single"
_INDENT_DIALOG = 1
```

**Placeholder parsing:** `_PLACEHOLDER_<TYPE>` / `_REGEX_<NAME>`
```python
_PLACEHOLDER_FULL = "zConv"
_REGEX_ZCONV_DOT_NOTATION = r'zConv\.(\w+)'
```

---

## Benefits of Centralized Constants

### 1. **Consistency**
- Same keys across all modules
- No typos (e.g., "zDialog" vs "zdialog")
- Single source of truth

### 2. **Maintainability**
- Change key once, updates everywhere
- Easy refactoring (rename KEY_MODEL → KEY_SCHEMA)
- Clear dependencies (grep for constant name)

### 3. **Discoverability**
- All constants in one place
- IDE autocomplete support
- Documentation in one location

### 4. **Type Safety**
- Import errors catch typos at import time
- Not at runtime when string is used
- Better error messages

---

## Best Practices

### DO:
✅ Import constants from dialog_constants  
✅ Use constants instead of magic strings  
✅ Group related imports together  
✅ Use public constants (KEY_*) for external API  
✅ Use private constants (_*) for internal implementation  
✅ Format error messages with .format() for dynamic values  

### DON'T:
❌ Hardcode dictionary keys ("zDialog" → KEY_ZDIALOG)  
❌ Hardcode error messages (use constants)  
❌ Mix public/private constant naming  
❌ Import * (explicit imports only)  
❌ Duplicate constants across modules  

---

## Version History

- **v1.5.4**: Industry-grade constants refactor
  - Added: 30+ new constants
  - Organized: Constants by category
  - Enhanced: Naming conventions
  - Documented: All constants with usage examples
- **v1.5.2**: Initial constants implementation
  - Basic dictionary keys
  - Simple error messages

---

**[← Back to zDialog Guide](../zDialog_GUIDE.md)**
