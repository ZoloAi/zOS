**[← Back to zFunc Guide](zFunc_GUIDE.md) | [Home](../../README.md) | [Next: zOpen Guide →](zOpen_GUIDE.md)**

---

# zDialog

**zDialog** is a **Layer 2 subsystem** for interactive form/dialog operations.
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

It provides auto-validated, mode-agnostic form rendering with declarative submission handling through one unified interface.

You get:

- **Zero boilerplate** form validation
- **Schema-based validation** (auto-validated against zSchema on insert)
- **Mode-agnostic rendering** (zCLI terminal + zBifrost WebSocket)
- **Confirm mode** — `fields: []` → a y/n prompt (zCLI) or confirm button (Bifrost), no collection
- **Enum enrichment** — schema `enum` fields auto-render as pick-lists / `<select>`
- **Declarative submission** (via zDispatch)
- **Placeholder injection** (`zConv.*`, `%session.*`, model references)
- **Server-side onSubmit registry** — the handler is registered server-side; the client can't tamper with it
- **WebSocket integration** (real-time validation errors)

## Architecture Overview

**zDialog** is composed of specialized modules, each handling a specific aspect of dialog operations:

| Module | Purpose | Guide |
|--------|---------|-------|
| **dialog_context** | Context creation and placeholder injection (5 types) | [dialog_context_GUIDE.md](zDialog_Guides/dialog_context_GUIDE.md) |
| **dialog_submit** | Dict-based submission handling via zDispatch | [dialog_submit_GUIDE.md](zDialog_Guides/dialog_submit_GUIDE.md) |
| **dialog_constants** | Shared constants, keys, messages | [dialog_constants_GUIDE.md](zDialog_Guides/dialog_constants_GUIDE.md) |

This guide provides a **facade overview** of zDialog. For deep dives into specific modules, see the guides in `zDialog_Guides/`.

---

## 5-Tier Architecture

zDialog follows a clean 5-tier architecture pattern:

```
Tier 5: Package Root (__init__.py)
   ↓    Public API export (zDialog class, handle_zDialog function)
Tier 4: Facade (zDialog.py)
   ↓    Main orchestration: handle(), auto-validation, WebSocket
Tier 3: Package Aggregator (dialog_modules/__init__.py)
   ↓    Aggregates Tier 1-2 components
Tier 2: Submit Handler (dialog_submit.py)
   ↓    Dict-based submission via zDispatch
Tier 1: Foundation (dialog_context.py)
   ↓    Context creation, placeholder injection (5 types)
```

This tier structure ensures:
- **Clear separation of concerns** - Each tier has one responsibility
- **Testability** - Each tier can be tested independently
- **Maintainability** - Changes isolated to specific tiers
- **Reusability** - Lower tiers used by higher tiers

---

## Initialization Order

zDialog is initialized by zCLI.py during subsystem setup:

```python
# zCLI.py (approximate line 200)
self.zdialog = zDialog(self, walker=self.walker)
```

This makes zDialog available throughout the zOS framework:
- Direct access: `zcli.zdialog.handle(form_spec)`
- Via zDispatch: `{"zDialog": {"model": ..., "fields": ...}}`

**Dependencies:**
1. **zConfig** - Configuration (session, logger)
2. **zDisplay** - Form rendering (`zDisplay.zDialog()`)
3. **zData** - Auto-validation (`DataValidator`)
4. **zLoader** - Schema loading (`loader.handle()`)
5. **zDispatch** - Submission handling (`handle_zDispatch()`)
6. **zComm** - WebSocket broadcasting (zBifrost mode)

---

## Key Features

### Auto-Validation

zDialog automatically validates form data against zSchema definitions:

```python
form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",  # Schema reference triggers auto-validation
        "fields": [
            {"name": "username", "type": "text"},
            {"name": "email", "type": "text"}
        ],
        "onSubmit": {
            "zData": {"action": "create", "data": "zConv"}
        }
    }
}

# Auto-validates against @.zSchema.users before executing onSubmit
result = z.zdialog.handle(form_spec)
```

**How it works:**
1. Auto-validation runs **only when** `model` starts with `@` **and** the onSubmit is a zData **insert** (`onSubmit.zData.action == "insert"`). Login/custom/read operations let their own onSubmit handler validate.
2. Resolve the table: explicit `table` field › last segment of an extended zPath (`parse_schema_model_path`) › schema `zMeta.Data_Label` › path tail.
3. Load schema via `loader.handle(...)` and build a lightweight `DataValidator` (no DB connection).
4. Validate collected data (`zConv`) via `validate_insert(table, zConv)`.
5. On failure: display errors (and broadcast a `validation_error` WebSocket event in zBifrost mode), then return `None` to prevent onSubmit execution.
6. Execute onSubmit only if validation passes. Schema-load errors are logged as a warning and the form still proceeds (backward compatibility).

**Validation errors displayed in both modes:**
- **zCLI mode**: Terminal output via `zData.display_validation_errors()`
- **zBifrost mode**: WebSocket broadcast via `z.comm.websocket_events.send_event()`

### Mode-Agnostic Rendering

zDialog works seamlessly in two execution modes:

**zCLI Mode (Interactive Terminal):**
```python
# User sees form in terminal, enters data interactively
result = z.zdialog.handle(form_spec)
# Displays form → Collects input → Validates → Submits
```

**zBifrost Mode (WebSocket):**
```python
# Data provided via WebSocket (already collected from browser)
context = {
    "websocket_data": {
        "data": {"username": "alice", "email": "alice@example.com"}
    }
}
result = z.zdialog.handle(form_spec, context=context)
# Skips rendering → Uses pre-provided data → Validates → Submits
```

Mode detection is automatic based on session configuration (`z.session['zMode']`).

### Declarative Submission

All submissions handled via dict-based zDispatch commands:

```python
"onSubmit": {
    "zData": {
        "query": "INSERT INTO users (name, email) VALUES (zConv.name, zConv.email)"
    }
}
```

**Placeholder injection** automatically resolves:
- Full zConv: `"zConv"` → entire form data dict
- Dot notation: `"zConv.username"` → specific field value
- Bracket notation: `"zConv['email']"` → specific field value
- Embedded: `"WHERE id = zConv.user_id"` → inline replacement
- Session values: `"%session.user_id"` → session variable

### WebSocket Integration

In zBifrost mode, zDialog integrates with WebSocket communication:

**Pre-provided data:**
```python
# Data from browser already validated client-side
context = {"websocket_data": {"data": {...}}}
result = z.zdialog.handle(form_spec, context=context)
```

**Validation error broadcasting:**
```python
# Validation errors sent to browser automatically
z.comm.websocket_events.send_event({
    "event": "validation_error",
    "errors": {...}
})
```

### Confirm Mode (no fields)

When `fields` is empty, zDialog switches to **confirm mode** — no data collection, just a confirm-and-fire gate. The backend signals this explicitly via `dialog_mode: "confirm"` in the context so every renderer reads it the same way (instead of re-deriving from field count):

```python
form_spec = {
    "zDialog": {
        "title": "Delete record",
        "model": "@.zSchema.users",
        "fields": [],   # → confirm mode
        "onSubmit": {"zData": {"action": "delete", "data": {"id": "%session.user_id"}}}
    }
}
```

- **zCLI mode:** prompts `… — proceed? (y/n):` directly via `read_string`; anything but `y`/`yes` cancels and returns `None`.
- **zBifrost mode:** emits the dialog event; the frontend renders a confirm button and fires `onSubmit` on click.

### Enum Fields → Pick-lists

Bare field-name strings are auto-enriched into `select` fields when the schema defines an `enum`. The frontend renders a `<select>`; the zCLI terminal shows a numbered pick-list:

```yaml
# schema: status field has enum: [active, suspended, closed]
fields: [username, status]   # "status" auto-becomes a select with those options
```

### Server-Side onSubmit Registry (anti-tamper)

When an `onSubmit` is present, zDialog registers it **server-side** under the form's `_dialogId` (`session["_dialog_registry"][dialog_id]`). The Bifrost `form_submit` handler looks up the handler by id rather than trusting an `onSubmit` echoed back by the client — the browser cannot inject or rewrite the submission command.

---

## Tutorials

**Learn by doing!**

The tutorials below are organized in a bottom-up fashion. Every tutorial demonstrates a specific aspect of zDialog functionality.

**A Note on Learning zOS:**
Each tutorial (lvl1, lvl2, lvl3...) progressively introduces more complex features of **this subsystem**. The early tutorials start with familiar imperative patterns to meet you where you are as a developer.

As you progress through zOS's subsystems, you'll notice a gradual shift from imperative to declarative patterns. This intentional journey helps reshape your mental model from imperative to declarative thinking.

Get the demos:

```bash
# Clone only the Demos folder
git clone --depth 1 --filter=blob:none --sparse https://github.com/ZoloAi/zolo-zcli.git
cd zolo-zcli
git sparse-checkout set Demos
```

> All zDialog demos are in: `Demos/Layer_2/zDialog_Demo/`

---

# **zDialog - Level 1** (Basic Forms)

### **i. Simple Form (No Validation)**

The simplest form - just collect data, no schema validation:

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "simple-form",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Define form without model (no auto-validation)
form_spec = {
    "zDialog": {
        "fields": [
            {"name": "username", "type": "text"},
            {"name": "email", "type": "text"}
        ]
    }
}

# Display form, collect data (no validation, no submission)
result = z.zdialog.handle(form_spec)
print(f"Collected data: {result}")
```

**What happens:**
1. Form rendered in terminal
2. User enters data
3. Data collected in `zConv` dict
4. No validation (no model specified)
5. No submission (no onSubmit specified)
6. Returns collected data

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zDialog_Demo/lvl1_basic/1_simple_form.py
```

[View demo source →](../../Demos/Layer_2/zDialog_Demo/lvl1_basic/1_simple_form.py)

**What you'll discover:**
- Minimal form definition (fields only)
- Interactive data collection
- No validation or submission logic
- Returns collected data as dict

---

### **ii. Form with Validation**

Add a schema reference to enable auto-validation:

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "validated-form",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Define form WITH model (enables auto-validation)
form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",  # Schema reference
        "fields": [
            {"name": "username", "type": "text"},
            {"name": "email", "type": "text"}
        ]
    }
}

# Display form, collect data, auto-validate
result = z.zdialog.handle(form_spec)

if result:
    print(f"✅ Validation passed: {result}")
else:
    print("❌ Validation failed (see errors above)")
```

**Schema file** (`@.zSchema.users`):
```yaml
# Workspace: zSchemas/users.yaml
zSchema:
  type: object
  required: [username, email]
  properties:
    username:
      type: string
      minLength: 3
      maxLength: 20
    email:
      type: string
      format: email
```

**What happens:**
1. Form rendered in terminal
2. User enters data
3. Schema loaded: `@.zSchema.users` → `zSchemas/users.yaml`
4. Data validated against schema
5. If validation fails:
   - Errors displayed in terminal
   - Returns `None`
6. If validation passes:
   - Returns collected data

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zDialog_Demo/lvl1_basic/2_validated_form.py
```

[View demo source →](../../Demos/Layer_2/zDialog_Demo/lvl1_basic/2_validated_form.py)

**What you'll discover:**
- Auto-validation triggered by model reference
- Schema validation (required fields, type checking, format validation)
- Validation error display
- Returns `None` on validation failure

---

### **iii. Form with Submission**

Add onSubmit to execute actions after successful validation:

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "form-with-submit",
    "logger": "INFO",
    "logger_path": "./logs",
})

form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",
        "fields": [
            {"name": "username", "type": "text"},
            {"name": "email", "type": "text"}
        ],
        "onSubmit": {
            "zData": {
                "action": "create",
                "model": "@.zSchema.users",
                "data": "zConv"  # Submit entire form data
            }
        }
    }
}

# Display → Collect → Validate → Submit
result = z.zdialog.handle(form_spec)

if result:
    print(f"✅ Form submitted successfully: {result}")
else:
    print("❌ Validation or submission failed")
```

**What happens:**
1. Form rendered in terminal
2. User enters data
3. Data validated against schema
4. If validation passes:
   - onSubmit executed via zDispatch
   - `"data": "zConv"` → entire form data sent to zData
   - Database record created
5. Returns submission result

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zDialog_Demo/lvl1_basic/3_form_submit.py
```

[View demo source →](../../Demos/Layer_2/zDialog_Demo/lvl1_basic/3_form_submit.py)

**What you'll discover:**
- Declarative submission via zDispatch
- onSubmit only executes after successful validation
- Placeholder injection: `"zConv"` → entire form data
- Integration with zData subsystem

---

**🎯 Level 1 Complete!**

You've learned the core zDialog workflow:
- ✅ **Simple forms** - Collect data without validation
- ✅ **Validated forms** - Auto-validation with schema reference
- ✅ **Form submission** - Declarative onSubmit via zDispatch

---

# **zDialog - Level 2** (Placeholder Injection)

### **i. Dot Notation Placeholders**

Access specific form fields using dot notation:

```python
form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",
        "fields": [
            {"name": "username", "type": "text"},
            {"name": "email", "type": "text"}
        ],
        "onSubmit": {
            "zData": {
                "query": "INSERT INTO users (username, email) VALUES (zConv.username, zConv.email)"
            }
        }
    }
}

# User enters: username="alice", email="alice@example.com"
# Query becomes: INSERT INTO users (username, email) VALUES ('alice', 'alice@example.com')
```

**Placeholder types:**
- `"zConv"` → Entire form data dict
- `"zConv.username"` → Specific field (dot notation)
- `"zConv['email']"` → Specific field (bracket notation)

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zDialog_Demo/lvl2_placeholders/1_dot_notation.py
```

[View demo source →](../../Demos/Layer_2/zDialog_Demo/lvl2_placeholders/1_dot_notation.py)

**What you'll discover:**
- Dot notation placeholder resolution
- Automatic type conversion (strings quoted, numbers not)
- Embedded placeholders in SQL queries
- Smart value formatting

---

### **ii. Embedded Placeholders**

Mix placeholders with text for complex queries:

```python
form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",
        "fields": [
            {"name": "user_id", "type": "number"},
            {"name": "status", "type": "text"}
        ],
        "onSubmit": {
            "zData": {
                "query": "SELECT * FROM users WHERE id = zConv.user_id AND status = zConv.status"
            }
        }
    }
}

# User enters: user_id=42, status="active"
# Query becomes: SELECT * FROM users WHERE id = 42 AND status = 'active'
# Note: Numbers not quoted, strings quoted automatically
```

**Smart formatting:**
- Numbers → No quotes: `id = 42`
- Strings → Quoted: `status = 'active'`
- Booleans → Lowercase: `active = true`
- Null → SQL NULL: `value = NULL`

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zDialog_Demo/lvl2_placeholders/2_embedded.py
```

[View demo source →](../../Demos/Layer_2/zDialog_Demo/lvl2_placeholders/2_embedded.py)

**What you'll discover:**
- Embedded placeholders in complex queries
- Automatic type detection and formatting
- Multiple placeholders in one string
- SQL-safe value quoting

---

### **iii. Recursive Placeholder Resolution**

Placeholders resolved recursively in nested data structures:

```python
form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",
        "fields": [
            {"name": "username", "type": "text"},
            {"name": "email", "type": "text"}
        ],
        "onSubmit": {
            "zData": {
                "action": "create",
                "data": {
                    "user": {
                        "name": "zConv.username",
                        "contact": {
                            "email": "zConv.email"
                        }
                    },
                    "query": "WHERE name = zConv.username"
                }
            }
        }
    }
}

# All placeholders resolved recursively:
# {
#     "user": {
#         "name": "alice",
#         "contact": {"email": "alice@example.com"}
#     },
#     "query": "WHERE name = 'alice'"
# }
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zDialog_Demo/lvl2_placeholders/3_recursive.py
```

[View demo source →](../../Demos/Layer_2/zDialog_Demo/lvl2_placeholders/3_recursive.py)

**What you'll discover:**
- Placeholders in nested dicts
- Placeholders in lists
- Mixed placeholder types
- Deep recursion support

---

**🎯 Level 2 Complete!**

You've mastered placeholder injection:
- ✅ **Dot notation** - Access specific fields
- ✅ **Embedded placeholders** - Mix with text
- ✅ **Recursive resolution** - Nested structures

---

# **zDialog - Level 3** (Advanced Features)

### **i. Session Placeholders**

Access session variables in onSubmit expressions:

```python
# Session contains: {"user_id": 123, "role": "admin"}
form_spec = {
    "zDialog": {
        "model": "@.zSchema.posts",
        "fields": [
            {"name": "title", "type": "text"},
            {"name": "content", "type": "text"}
        ],
        "onSubmit": {
            "zData": {
                "query": "INSERT INTO posts (author_id, title, content) VALUES (%session.user_id, zConv.title, zConv.content)"
            }
        }
    }
}

# Query becomes: INSERT INTO posts (author_id, title, content) VALUES (123, 'My Post', 'Content...')
```

**Session placeholder syntax:**
- `"%session.user_id"` → Access session variable
- `"%session.zS_id"` → Session ID
- `"%session.zMode"` → Execution mode

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zDialog_Demo/lvl3_advanced/1_session_placeholders.py
```

[View demo source →](../../Demos/Layer_2/zDialog_Demo/lvl3_advanced/1_session_placeholders.py)

**What you'll discover:**
- Session variable interpolation
- Combined session + form placeholders
- Secure data injection (no user control)

---

### **ii. zBifrost Mode (WebSocket)**

Handle forms in zBifrost mode with pre-provided data:

```python
# Server-side (Python)
form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",
        "fields": [
            {"name": "username", "type": "text"},
            {"name": "email", "type": "text"}
        ],
        "onSubmit": {
            "zData": {"action": "create", "data": "zConv"}
        }
    }
}

# Data from WebSocket (browser already collected it)
context = {
    "websocket_data": {
        "data": {"username": "alice", "email": "alice@example.com"}
    }
}

# Skips rendering, uses pre-provided data, validates, submits
result = z.zdialog.handle(form_spec, context=context)
```

**What happens:**
1. No form rendering (data already provided)
2. Uses `websocket_data.data` as form data
3. Validates against schema
4. If validation fails:
   - Broadcasts errors via WebSocket
   - Returns `None`
5. If validation passes:
   - Executes onSubmit
   - Returns result

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zDialog_Demo/lvl3_advanced/2_zbifrost_mode.py
```

[View demo source →](../../Demos/Layer_2/zDialog_Demo/lvl3_advanced/2_zbifrost_mode.py)

**What you'll discover:**
- Mode detection: zCLI vs zBifrost
- Pre-provided data handling
- WebSocket validation error broadcasting
- Real-time form validation

---

### **iii. Custom Validation Handlers**

Extend validation with custom logic:

```python
# Schema validation + custom business logic
form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",
        "fields": [
            {"name": "username", "type": "text"},
            {"name": "age", "type": "number"}
        ],
        "onSubmit": {
            "zData": {
                "action": "create",
                "data": "zConv",
                "validate": {
                    "custom": "check_age_restriction"  # Custom validation function
                }
            }
        }
    }
}

# Custom validation function
def check_age_restriction(data, schema, logger):
    if data.get("age", 0) < 18:
        return {"valid": False, "errors": {"age": "Must be 18 or older"}}
    return {"valid": True}
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zDialog_Demo/lvl3_advanced/3_custom_validation.py
```

[View demo source →](../../Demos/Layer_2/zDialog_Demo/lvl3_advanced/3_custom_validation.py)

**What you'll discover:**
- Custom validation functions
- Combined schema + custom validation
- Error message formatting
- Validation error display

---

**🎯 Level 3 Complete!**

You've mastered advanced zDialog features:
- ✅ **Session placeholders** - Access session variables
- ✅ **zBifrost mode** - WebSocket integration
- ✅ **Custom validation** - Extend schema validation

---

## Advanced Features

### Model Injection

zDialog automatically injects the model reference into onSubmit for zData/zCRUD operations:

```python
form_spec = {
    "zDialog": {
        "model": "@.zSchema.users",  # Model reference
        "fields": [...],
        "onSubmit": {
            "zData": {
                "action": "create",
                "data": "zConv"
                # No need to specify model again - auto-injected!
            }
        }
    }
}

# Automatically becomes:
# {"zData": {"action": "create", "model": "@.zSchema.users", "data": {...}}}
```

**When model injection happens:**
- onSubmit contains `zData` or `zCRUD` key
- onSubmit does NOT already have `model` key
- Dialog has `model` reference

**Smart injection logic** (see [dialog_submit_GUIDE.md](zDialog_Guides/dialog_submit_GUIDE.md) for details):
1. Check if injection needed (zData/zCRUD present, model absent)
2. Inject at correct nesting level
3. Preserve existing structure
4. Log injection for debugging

---

### Validation Error Display

Validation errors displayed differently based on execution mode:

**zCLI Mode (Terminal):**
```
❌ Validation failed:
  - username: Must be at least 3 characters
  - email: Invalid email format
```

**zBifrost Mode (WebSocket):**
```json
{
    "event": "validation_error",
    "errors": {
        "username": "Must be at least 3 characters",
        "email": "Invalid email format"
    }
}
```

Automatically handles both modes - no configuration needed.

---

### Facade API Reference

The `zDialog` class provides these methods:

**Main Interface:**
```python
# Initialize (typically done by zCLI)
dialog = zDialog(zcli_instance, walker=walker_instance)

# Handle form operation
result = dialog.handle(
    zHorizontal: Dict[str, Any],      # Form specification ({"zDialog": {...}})
    context: Optional[Dict] = None,   # Optional context (WebSocket data)
)
```

> Model/fields/title/table come from inside `zHorizontal["zDialog"]` — they are **not** separate `handle()` parameters.

**Return Values:**
- **Success**: Returns submission result (dict or other)
- **Validation failure**: Returns `None`
- **No onSubmit**: Returns collected data (`zConv`)

**Legacy Interface:**
```python
# Backward-compatible function interface
from zOS.L2_Handling.j_zDialog import handle_zDialog

result = handle_zDialog(
    zHorizontal: Dict[str, Any],
    zcli: Any,
    context: Optional[Dict] = None,
    model: Optional[str] = None,
    fields: Optional[List] = None
)
```

**Direct Module Access:**
```python
# Access lower-tier components
from zOS.L2_Handling.j_zDialog.dialog_modules import (
    create_dialog_context,    # Tier 1: Context creation
    inject_placeholders,      # Tier 1: Placeholder resolution
    handle_submit             # Tier 2: Submission handling
)
```

---

## Module Structure

zDialog follows a clean 5-tier architecture:

**Core Modules:**
- `zDialog.py` - Tier 4: Main facade class (orchestration)
- `__init__.py` - Tier 5: Package root (public API export)

**Foundation Modules (dialog_modules/):**
- `dialog_context.py` - Tier 1: Context creation, placeholder injection
- `dialog_submit.py` - Tier 2: Submission handling via zDispatch
- `dialog_constants.py` - Shared constants, keys, messages
- `__init__.py` - Tier 3: Package aggregator

**Architecture Pattern:**
zDialog uses the **Facade pattern** combined with **5-tier hierarchy**:
- `z.zdialog.handle()` → `zDialog.handle()` (Tier 4)
  - Delegates to `create_dialog_context()` (Tier 1)
  - Delegates to `zDisplay.zDialog()` (external)
  - Delegates to `DataValidator.validate()` (external)
  - Delegates to `handle_submit()` (Tier 2)
    - Delegates to `inject_placeholders()` (Tier 1)
    - Delegates to `handle_zDispatch()` (external)

This separation allows each tier to be tested and evolved independently while maintaining a stable public API.

---

## Layer 2 Design Philosophy

As a **Layer 2 subsystem**, zDialog has specific design considerations:

**Integration Points:**
- **Depends on:** zConfig (session, logger), zDisplay (rendering), zData (validation), zLoader (schemas), zDispatch (submission), zComm (WebSocket)
- **Used by:** zCLI, zDispatch, user applications
- **Provides for:** Interactive form operations, auto-validation, declarative submission

**Pure Declarative Paradigm:**
- String-based submissions removed in v1.5.4
- All submissions via dict-based zDispatch
- Automatic placeholder injection
- Schema-based auto-validation

**Mode-Agnostic:**
- Works in zCLI mode (interactive terminal)
- Works in zBifrost mode (WebSocket)
- Automatic mode detection
- Consistent behavior across modes

---

## Security & Trust

zDialog is a **declarative orchestration layer** — it assembles a submission dict and hands it off. It has **no code-execution surface of its own** (no `eval`/`exec`/`subprocess`), so there is **nothing zDialog-specific to seal in zGuard**. Trust is delegated correctly:

- **Submission execution** goes through `g_zDispatch` → owning subsystem; any plugin/`zFunc` routing inherits the `c_zLoader` plugin-trust gate. zDialog never loads code.
- **Anti-tamper:** the `onSubmit` handler is registered server-side by `_dialogId` (see Server-Side onSubmit Registry) — the client cannot substitute a different command.
- **Secure logging:** `zConv` and the dispatched dict are masked before logging — any field whose name contains `password` becomes `********`, and `&auth.login(...)` plugin strings have their password argument masked (`_mask_passwords_in_dict`).
- **Placeholder injection (latent SQLi — tracked):** `inject_placeholders` does smart-quoted string interpolation of `zConv.*` values into onSubmit strings (numbers unquoted, strings single-quoted). This is only a risk if the result is executed as a **raw** SQL string. Modern zData operations use **structured/parameterized** dicts, so this is currently latent; the authoritative escaping boundary lives in `m_zData` (tracked there, not fixed here). Prefer structured `data:`/`where:` blocks over raw `query:` strings.

## Constants & SSOT

- The zBifrost protocol-mode value is **aliased from root `zVocabulary`** (`_SESSION_VALUE_ZBIFROST = ZMODE_ZBIFROST`) — no local literal.
- The session-mode key (`SESSION_KEY_ZMODE`) is sourced from **`a_zConfig`** (`config_constants`).
- All other dialog keys, colors, styles, indents, regex, and messages are single-sourced in `dialog_constants.py` (see [dialog_constants_GUIDE.md](zDialog_Guides/dialog_constants_GUIDE.md)). No magic strings.
- Cross-subsystem overlaps tracked for a unified pass (not fixed here): the `"zConv"` literal (also in zFunc/zData/zDispatch), the command-contract keys (`KEY_MODEL`/`KEY_TABLE`/`KEY_DATA`/`KEY_ZDATA`/`KEY_ZCRUD`, overlap zDispatch/zData), and the duplicated password-masking + `%session.*` interpolation helpers (overlap zFunc / zDispatch `dispatch_launcher`).

---

## What's Next?

You've mastered **zDialog** (interactive form/dialog operations). Now continue to other **Layer 2** subsystems:

**→ Continue to [zOpen Guide](zOpen_GUIDE.md)**

Layer 2 includes:
- **zDialog** - Interactive forms (you are here)
- **zOpen** - File/folder opening with OS-native apps
- **zWizard** - Multi-step workflow orchestration
- **zData** - Database operations and validation
- **zShell** - Command-line shell operations
- **zWalker** - Menu navigation and command dispatch
- **zServer** - HTTP server and static file serving

---

**[← Back to zFunc Guide](zFunc_GUIDE.md) | [Home](../../README.md) | [Next: zOpen Guide →](zOpen_GUIDE.md)**
