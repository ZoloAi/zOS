# zDialog Submit Module Guide

> **Module:** `zOS/core/L2_Handling/j_zDialog/dialog_modules/dialog_submit.py`  
> **Purpose:** Submission handling for zDialog forms via zDispatch.

---

## Overview

The `dialog_submit` module provides **Tier 2** submission handling for the zDialog subsystem:

1. **Dict-based submission** - Pure declarative paradigm via zDispatch
2. **Placeholder injection** - Automatic zConv.* and %session.* resolution
3. **Model injection** - Smart model reference injection for zData/zCRUD
4. **Session interpolation** - Access session variables in onSubmit

| Function | Purpose |
|---|---|
| `handle_submit()` | Main entry point for onSubmit processing |
| `_handle_dict_submit()` | Process dict-based submissions via zDispatch |
| `_inject_model_if_needed()` | Smart model injection logic (root-level only) |
| `_interpolate_session_values()` | Session placeholder resolution (`%session.*`) |
| `_mask_passwords_in_dict()` | Recursively mask password values for secure logging |
| `_mask_password_in_zfunc_string()` | Mask the password arg in `&auth.login(...)` strings |
| `_display_submit_return()` | DRY display helper for submit/return feedback |

---

## Architecture: Tier 2 Submit Handler

```
Tier 5: Package Root (__init__.py)
Tier 4: Facade (zDialog.py)
Tier 3: Package Aggregator (dialog_modules/__init__.py)
Tier 2: Submit Handler (dialog_submit.py) ← This module
Tier 1: Foundation (dialog_context.py)
```

**Design rationale:**
- **Depends on Tier 1** - Uses `inject_placeholders()` from dialog_context
- **Used by Tier 4** - Called by zDialog.handle() for submission
- **Pure declarative** - Dict-based only (string-based removed in v1.5.4)

---

## Public Functions

### `handle_submit()`

Main entry point for onSubmit expression processing.

**Signature:**
```python
def handle_submit(
    submit_expr: Dict[str, Any],
    zContext: Dict[str, Any],
    logger: Any,
    walker: Optional[Any] = None,
    zcli: Optional[Any] = None,
) -> Any
```

**Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `submit_expr` | `Dict[str, Any]` | onSubmit expression (must be dict) |
| `zContext` | `Dict[str, Any]` | Dialog context with model, zConv |
| `logger` | `Any` | Logger instance for debug output |
| `walker` | `Optional[Any]` | Walker instance (legacy; resolves zcli/zos + display) |
| `zcli` | `Optional[Any]` | zCLI/zOS instance (modern path, e.g. from execute_code) |

The zCLI/zOS instance is resolved from `walker.zcli` / `walker.zos` when a walker is given, otherwise from the `zcli` argument. **At least one of `walker`/`zcli` is required** — both `None` raises `ValueError`.

**Returns:**
- **Success**: Result from zDispatch execution
- **Invalid type** (not a dict): `False` (logs error)
- **Neither walker nor zcli**: raises `ValueError`

**Example 1 - Basic dict submission:**
```python
submit_expr = {
    "zData": {
        "query": "INSERT INTO users (name) VALUES (zConv.username)"
    }
}

zContext = {
    "model": "@.zSchema.users",
    "zConv": {"username": "alice"}
}

result = handle_submit(submit_expr, zContext, logger, walker)

# 1. Injects placeholders: "INSERT INTO users (name) VALUES ('alice')"
# 2. Executes via zDispatch: handle_zDispatch({"zData": {...}}, ...)
# 3. Returns: Result from zData execution
```

**Example 2 - Invalid type:**
```python
submit_expr = "some_string"  # Invalid (string-based removed)
result = handle_submit(submit_expr, zContext, logger, walker)

# Logs error: "Invalid onSubmit type: str"
# Returns: False
```

---

## Submission Flow

### Dict-Based Submission (Pure Declarative)

**Flow (`_handle_dict_submit`, in code order):**
1. Placeholder injection: `zConv.*` → form data (`inject_placeholders`)
2. Session interpolation: `%session.*` → session values (`_interpolate_session_values`)
3. Model injection: add model reference if needed (root-level, `_inject_model_if_needed`)
4. zDispatch execution: `handle_zDispatch("submit", payload, zos=…, walker=…, context=zContext)` — payload masked before logging
5. Display return feedback (`_display_submit_return`) and return result

**Example:**
```python
# Original onSubmit (dialog model = "@.zSchema.posts")
submit_expr = {
    "zData": {
        "action": "insert",
        "data": {"author_id": "%session.user_id", "title": "zConv.title"}
    }
}

# Step 1: Placeholder injection — zConv.title → 'My Post'
{"zData": {"action": "insert",
           "data": {"author_id": "%session.user_id", "title": "My Post"}}}

# Step 2: Session interpolation — standalone %session.user_id → 123 (native int)
{"zData": {"action": "insert",
           "data": {"author_id": 123, "title": "My Post"}}}

# Step 3: Model injection — dialog model injected into the zData block
{"zData": {"model": "@.zSchema.posts", "action": "insert",
           "data": {"author_id": 123, "title": "My Post"}}}

# Step 4: Execute via zDispatch (payload masked before logging)
result = handle_zDispatch("submit", payload, zos=zcli, walker=walker, context=zContext)
```

---

## Placeholder Types

### zConv Placeholders

Access form data using zConv placeholders (see [dialog_context_GUIDE.md](dialog_context_GUIDE.md)):

**Supported syntax:**
- Full: `"zConv"` → entire form data
- Dot notation: `"zConv.username"` → specific field
- Bracket: `"zConv['email']"` → specific field
- Embedded: `"WHERE id = zConv.user_id"` → inline replacement

**Example:**
```python
submit_expr = {
    "zData": {
        "query": "INSERT INTO users (username, email) VALUES (zConv.username, zConv.email)"
    }
}

zContext = {"zConv": {"username": "alice", "email": "alice@example.com"}}

# After injection:
# "INSERT INTO users (username, email) VALUES ('alice', 'alice@example.com')"
```

### Session Placeholders

Access session variables using the `%session.*` syntax. **Important:** session interpolation matches a string **only when the entire value is** `"%session.<path>"` (a standalone value) — it does **not** do embedded replacement inside a larger string. So put session refs in structured `data:` / `where:` blocks, not inside a raw `query:` string:

```python
submit_expr = {
    "zData": {
        "action": "insert",
        "data": {
            "author_id": "%session.zAuth.applications.zCloud.id",   # standalone → resolved
            "title": "zConv.title"                                  # zConv placeholder
        }
    }
}

session = {"zAuth": {"applications": {"zCloud": {"id": 123}}}}

# After zConv injection + session interpolation:
# {"zData": {"action": "insert",
#            "data": {"author_id": 123, "title": "My Post"}}}
```

**Nested paths** are navigated dot-by-dot through the session dict (`%session.a.b.c`). The resolved value keeps its **native type** (e.g. `int` 123, not `"123"`).

**Common session paths:**
- `%session.zS_id` — Session ID
- `%session.zMode` — Execution mode (zCLI / zBifrost)
- `%session.zAuth.applications.<app>.id` — authenticated app-user id

---

## Model Injection

### When Model Injection Happens

`_inject_model_if_needed()` operates on the **root** of the submit dict only (no recursion, single block). The dialog's `model` is injected when it is **missing** at the relevant level:

1. Dialog has a `model` reference (e.g., `"model": "@.zSchema.users"`)
2. onSubmit contains a root `zData` or `zCRUD` key (model injected **into that block**), **or** has no `model` at the root (model injected at root)
3. The relevant level does **NOT** already have a `model` key

**Example - Injection needed:**
```python
# Dialog definition
form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",  # Model defined here
        "fields": [...],
        "onSubmit": {
            "zData": {
                "action": "create",
                "data": "zConv"
                # No model here - injection needed
            }
        }
    }
}

# After injection:
{
    "zData": {
        "model": "@.zSchema.users",  # Auto-injected
        "action": "create",
        "data": "zConv"
    }
}
```

**Example - Injection NOT needed:**
```python
form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",
        "fields": [...],
        "onSubmit": {
            "zData": {
                "model": "@.zSchema.posts",  # Already has model - no injection
                "action": "create",
                "data": "zConv"
            }
        }
    }
}

# No injection - respects explicit model override
```

### Model Injection Logic

The `_inject_model_if_needed()` function evaluates the root in priority order (first match wins):

**Case 1 — root `zCRUD` present → inject into the zCRUD block:**
```python
# Before
{"zCRUD": {"action": "create", "data": "zConv"}}

# After
{"zCRUD": {"model": "@.zSchema.users", "action": "create", "data": "zConv"}}
```

**Case 2 — root `zData` present → inject into the zData block:**
```python
# Before
{"zData": {"action": "create", "data": "zConv"}}

# After
{"zData": {"model": "@.zSchema.users", "action": "create", "data": "zConv"}}
```

**Case 3 — neither zCRUD nor zData → inject at root:**
```python
# Before
{"command": "custom", "param": "value"}

# After
{"command": "custom", "param": "value", "model": "@.zSchema.config"}
```

**Case 3b — implicit wizard sequence (all values are dict/list) → NO injection:**
```python
# Before (all nested) — left untouched so the CRUD handler doesn't mistake
# a model-only dict for a read command
{"step1": {...}, "step2": {...}}

# After (unchanged)
{"step1": {...}, "step2": {...}}
```

**Case 4 — already has a `model` at the relevant level → no injection (explicit override respected).**

> No recursion: only the root `zData`/`zCRUD` block (or the root itself) is considered — nested blocks are not walked.

---

## Session Interpolation

### How Session Interpolation Works

The `_interpolate_session_values()` function recursively resolves **standalone** `%session.<path>` values (it does **not** use a regex and does **not** replace embedded substrings):

**Supported types:**
- Strings that **start with** `"%session."` → resolved to the session value (whole-string only)
- Dicts (recursive over values)
- Lists (recursive over items)
- Other types / non-`%session.` strings → unchanged

**Example 1 — standalone string:**
```python
obj = "%session.user_id"
session = {"user_id": 123}

result = _interpolate_session_values(obj, session, logger)
# Returns: 123  (native int, not "123")
```

**Example 2 — nested dotted path:**
```python
obj = {"id": "%session.zAuth.applications.zCloud.id"}
session = {"zAuth": {"applications": {"zCloud": {"id": 1}}}}

result = _interpolate_session_values(obj, session, logger)
# Returns: {"id": 1}
```

**Example 3 — list (recursive):**
```python
obj = ["%session.user_id", "literal", {"role": "%session.role"}]
session = {"user_id": 123, "role": "admin"}

result = _interpolate_session_values(obj, session, logger)
# Returns: [123, "literal", {"role": "admin"}]
```

> An **embedded** ref like `"WHERE id = %session.user_id"` does **not** match (the string doesn't start with `%session.`) and is left unchanged — use a structured dict instead.

### Error Handling

**Unresolvable path (missing key, or path runs through a non-dict):**
```python
obj = "%session.missing.key"
session = {"user_id": 123}

result = _interpolate_session_values(obj, session, logger)
# Logs warning: "Failed to interpolate session path: %session.missing.key"
# Returns: None
```

---

## Secure Logging (password masking)

Before any submit payload or `zConv` is logged, it is masked so secrets never hit the logs:

- **`_mask_passwords_in_dict(data)`** — recurses dicts/lists; any key whose name contains `password` (case-insensitive) becomes `********`.
- **`_mask_password_in_zfunc_string(s)`** — for a `zFunc` value like `&auth.login('email', 'secret')`, masks just the password argument → `&auth.login('email', '********')`.

```python
# zConv masked for the debug log
masked_zconv = _mask_passwords_in_dict(zContext.get(KEY_ZCONV))
# full submit dict masked before the info log
masked_submit = _mask_passwords_in_dict(submit_dict)
```

> This duplicates `i_zFunc/zFunc._mask_passwords_in_data` — tracked for a future shared-helper dedup pass (not fixed here).

---

## Integration Points

**Used by:**
- `zDialog.py` — submission in the `handle()` method

**Dependencies:**
- `dialog_context.py` - `inject_placeholders()`, constants
- `zDispatch.py` - `handle_zDispatch()` for command execution
- `zDisplay.py` - `walker.display.zDeclare()` for visual feedback

**External dependencies:**
- zDispatch subsystem (Layer 2 / `g_zDispatch`)
- zDisplay subsystem (Layer 2 / `e_zDisplay`)

---

## Error Handling

### Invalid Submission Type

```python
submit_expr = 123  # Not a dict
result = handle_submit(submit_expr, zContext, logger, walker)

# Logs: "Invalid onSubmit type: int - must be dict"
# Returns: False
```

### No Walker and No zcli

```python
result = handle_submit(submit_expr, zContext, logger, walker=None, zcli=None)

# Raises: ValueError("handle_submit requires a walker instance")
```

(Passing either `walker` or `zcli` is sufficient.)

### zDispatch Execution Failure

```python
# zDispatch raises exception
result = handle_submit(submit_expr, zContext, logger, walker)

# Exception caught and logged
# Visual feedback displayed via zDisplay
# Returns: False
```

---

## Constants

All constants imported from `dialog_constants.py`:

```python
from .dialog_constants import (
    KEY_ZCRUD,                    # "zCRUD"
    KEY_ZDATA,                    # "zData"
    KEY_MODEL,                    # "model"
    KEY_ZCONV,                    # "zConv"
    COLOR_ZDIALOG,                # Display color
    _DISPATCH_CMD_SUBMIT,         # "submit"
    _STYLE_SINGLE,                # Display style
    _STYLE_TILDE,                 # Display style
    _INDENT_DIALOG,               # Indent level
    _INDENT_SUBMIT,               # Indent level
    _DEBUG_SUBMIT_EXPR,           # Debug message
    _DEBUG_CONTEXT_KEYS,          # Debug message
    _DEBUG_DICT_PAYLOAD,          # Debug message
    _INFO_DISPATCH_DICT,          # Info message
    _ERROR_INVALID_TYPE_SUBMIT,   # Error message
    _ERROR_NO_WALKER,             # Error message
    _ERROR_DISPATCH_FAILED,       # Error message
)
```

---

## Best Practices

### DO:
✅ Use dict-based onSubmit expressions (pure declarative)  
✅ Let model injection handle schema references automatically  
✅ Use session placeholders for user context (%session.user_id)  
✅ Use zConv placeholders for form data (zConv.username)  
✅ Check return value for False (indicates failure)  
✅ Log submission expressions for debugging  

### DON'T:
❌ Use string-based submissions (removed in v1.5.4)  
❌ Manually inject model when not needed (auto-handled)  
❌ Hardcode user IDs (use %session.user_id)  
❌ Assume submission always succeeds (check return value)  
❌ Mix placeholder types incorrectly (use correct syntax)  

---

## Performance Considerations

**Recursive operations:**
- Session interpolation: O(n) where n = object size
- Placeholder injection: O(n) where n = object size
- Model injection: O(n) where n = nesting depth

**Optimization tips:**
- Keep onSubmit expressions shallow (< 5 levels deep)
- Pre-format queries when possible
- Minimize nested zData/zCRUD blocks

---

## Testing

**Unit test coverage:**
- ✅ Dict-based submission (valid and invalid)
- ✅ Session interpolation (strings, dicts, lists)
- ✅ Placeholder injection integration
- ✅ Model injection (all cases)
- ✅ Error handling (invalid types, no walker, dispatch failure)
- ✅ Visual feedback display

**Test files:**
- `tests/test_dialog_submit.py` - Unit tests
- `tests/test_session_interpolation.py` - Session-specific tests

---

## Version History

- **v1.5.4**: Industry-grade refactor + String-based removal
  - **REMOVED**: String-based submissions (architectural purity)
  - Added: Type hints (100% coverage)
  - Added: Constants from dialog_constants
  - Added: Comprehensive docstrings (500+ lines)
  - Enhanced: Error handling and logging
- **v1.5.3**: Dict-based submission support
  - Added: Dict-based submission via zDispatch
  - Added: Session interpolation
  - Added: Model injection logic
- **v1.5.2**: Initial implementation
  - String-based submissions only (removed)

---

**[← Back to zDialog Guide](../zDialog_GUIDE.md)**
