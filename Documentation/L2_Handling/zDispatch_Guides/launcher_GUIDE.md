**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**

---

# Command Launcher

The **CommandLauncher** is the central routing engine for zDispatch, directing commands to appropriate subsystems based on command format and type.

## Overview

CommandLauncher handles two main command pathways:

1. **String Commands**: `"zFunc(...)"`, `"zLink(...)"`, `"zWizard(...)"`, etc.
2. **Dict Commands**: `{"zFunc": ...}`, `{"zData": ...}`, `{"zWizard": ...}`, etc.

## Architecture

```
CommandLauncher
├── launch()                # Main entry point (type detection)
├── _launch_string()        # Route string commands
├── _launch_dict()          # Route dict commands
├── _launch_list()          # Route array commands
└── Domain Handlers
    ├── SubsystemRouter     # zFunc, zWizard, zDialog
    ├── CRUDHandler         # Auto-detected CRUD
    ├── AuthHandler         # zLogin, zLogout
    ├── NavigationHandler   # zLink, menus
    └── DataResolver        # zRead, zData
```

## String Command Parsing

String commands use function-call syntax:

```python
# Function invocation
z.dispatch.handle("action", "zFunc(my_function)")

# With arguments
z.dispatch.handle("action", "zFunc(calculate, x=10, y=5)")

# Plugin invocation
z.dispatch.handle("action", "zFunc(&my_plugin.func)")

# Wizard invocation
z.dispatch.handle("wizard", "zWizard(onboarding)")

# Read operation
z.dispatch.handle("read", "zRead(users, where={'active': True})")
```

**Parsing flow:**
1. Detect command prefix (`zFunc(`, `zWizard(`, etc.)
2. Extract function name and arguments
3. Route to appropriate subsystem
4. Return result

## Dict Command Routing

Dict commands provide structured data:

```python
# Function with explicit arguments
command = {
    "zFunc": "calculate",
    "args": [10, 5],
    "kwargs": {"operation": "add"}
}
z.dispatch.handle("calc", command)

# Data operation
command = {
    "zData": {
        "action": "read",
        "model": "users",
        "where": {"id": 1}
    }
}
z.dispatch.handle("read", command)

# Wizard invocation
command = {
    "zWizard": "onboarding_wizard",
    "context": {"user_id": 123}
}
z.dispatch.handle("wizard", command)
```

**Routing logic:**
1. Check for subsystem keys (zFunc, zData, zWizard, etc.)
2. Auto-detect CRUD if action/model/table keys present
3. Route to appropriate handler
4. Return result

## Auto-Detection

### CRUD Auto-Detection

Commands with CRUD keywords route to zData automatically:

```python
# No explicit "zData" key needed!
command = {
    "action": "read",
    "model": "users",
    "where": {"id": 1}
}
z.dispatch.handle("read", command)
# Auto-routes to zData.crud()
```

**Detection rules:**
- Has `action` key? → CRUD
- Has `model` or `table` key? → CRUD
- Routes to `CRUDHandler` automatically

**Supported CRUD actions:**
- `read` - Query single record
- `list` - Query multiple records
- `create` - Insert new record
- `update` - Modify existing record
- `delete` - Remove record

### Wizard Detection

Commands with wizard patterns route to zWizard:

```python
# String format
"zWizard(setup_wizard)"

# Dict format
{"zWizard": "setup_wizard"}

# Auto-detected wizard dict
{
    "wizard": "setup_wizard",
    "steps": [...]
}
```

## Mode-Aware Behavior

CommandLauncher adjusts behavior based on execution mode:

### zCLI Mode (Terminal)

```python
# String commands (non-wizard) return None
result = z.dispatch.handle("action", "zFunc(my_func)")
# Returns: None (terminal output only)

# Wizard commands return "zBack"
result = z.dispatch.handle("wizard", "zWizard(setup)")
# Returns: "zBack" (trigger navigation)
```

### zBifrost Mode (Web)

```python
# All commands return actual results
result = z.dispatch.handle("action", "zFunc(my_func)")
# Returns: <actual function result>

# Events are buffered for web client
result = handle_zDispatch("action", {"zFunc": "my_func"}, zos=z)
# Returns: {"result": ..., "events": [...]}
```

## Plugin Support

Commands with `&` prefix invoke plugins via zParser:

```python
# Plugin function
z.dispatch.handle("action", "zFunc(&analytics.report)")

# Plugin with arguments
z.dispatch.handle("action", "zFunc(&plugins.process, data=payload)")

# Dict format
command = {
    "zFunc": "&my_plugin.calculate",
    "args": [10, 20]
}
z.dispatch.handle("calc", command)
```

**Resolution flow:**
1. Detect `&` prefix in function name
2. Route to zParser for plugin resolution
3. Execute resolved plugin function
4. Return result

## List Commands

Array commands process multiple items:

```python
# List of commands
commands = [
    {"zFunc": "action1"},
    {"zFunc": "action2"},
    {"zFunc": "action3"}
]
result = z.dispatch.handle("batch", commands)
# Executes each command in sequence
```

**Processing:**
- Iterates through list
- Dispatches each item
- Collects results
- Returns list of results

## Integration Points

CommandLauncher integrates with 8+ subsystems:

| Subsystem | Command Keys | Purpose |
|-----------|--------------|---------|
| **zFunc** | `zFunc` | Function execution |
| **zData** | `zData`, `zRead`, auto-CRUD | Data operations |
| **zWizard** | `zWizard` | Multi-step workflows |
| **zDialog** | `zDialog` | Interactive forms |
| **zAuth** | `zLogin`, `zLogout` | Authentication |
| **zNavigation** | `zLink`, menus | Navigation |
| **zParser** | `&` prefix | Plugin resolution |
| **zLoader** | `zVaFile`, `zBlock` | UI file loading |

## Error Handling

CommandLauncher handles errors gracefully:

```python
# Unknown command type
result = z.dispatch.handle("action", 12345)
# Returns: None (logs warning)

# Missing function
result = z.dispatch.handle("action", "zFunc(nonexistent)")
# Returns: None (logs error)

# Invalid wizard
result = z.dispatch.handle("wizard", "zWizard(missing)")
# Returns: None (logs error)
```

**Error behavior:**
- Logs errors to framework logger
- Returns `None` on failure
- Never crashes the application
- Provides clear error messages

## Context Passing

Commands can receive context data:

```python
# Pass context to command
context = {
    "user_id": 123,
    "session_id": "abc",
    "websocket_data": {...}
}

result = z.dispatch.handle(
    "action",
    {"zFunc": "process_user"},
    context=context
)

# Function receives context
def process_user(context):
    user_id = context.get("user_id")
    # ...
```

**Context uses:**
- User session data
- WebSocket request data
- Request-scoped variables
- Authentication state

## Walker Integration

Commands can be dispatched within wizard walkers:

```python
# In wizard step
result = z.dispatch.handle(
    "action",
    {"zFunc": "save_step"},
    walker=walker
)

# Uses walker.display instead of zos.display
# Inherits walker context
# Returns to wizard flow
```

**Walker benefits:**
- Scoped display (walker.display)
- Context inheritance
- Navigation integration
- Step-level control flow

## Best Practices

### Command Structure

```python
# ✅ Good: Structured dict
command = {
    "zFunc": "calculate",
    "args": [10, 5],
    "kwargs": {"operation": "add"}
}

# ❌ Bad: Unstructured string with complex args
command = "zFunc(calculate, 10, 5, operation='add')"  # Hard to parse
```

### Auto-Detection

```python
# ✅ Good: Let auto-detection work
command = {
    "action": "read",
    "model": "users",
    "where": {"id": 1}
}

# ❌ Bad: Unnecessary wrapping
command = {
    "zData": {
        "action": "read",
        "model": "users",
        "where": {"id": 1}
    }
}  # Extra nesting
```

### Mode Awareness

```python
# ✅ Good: Check mode before expecting result
is_bifrost = z.session.get(SESSION_KEY_ZMODE) == ZMODE_ZBIFROST
if is_bifrost:
    # Expect actual result
    result = z.dispatch.handle("action", cmd)
else:
    # Terminal output only
    z.dispatch.handle("action", cmd)
```

### Error Handling

```python
# ✅ Good: Check for None
result = z.dispatch.handle("action", cmd)
if result is None:
    print("Command failed")

# ❌ Bad: Assume result exists
result = z.dispatch.handle("action", cmd)
print(result.data)  # May crash if None
```

## Configuration

No explicit configuration needed - CommandLauncher uses zConfig settings:

```python
# Mode from session
mode = z.session.get(SESSION_KEY_ZMODE)

# Logger from zOS
logger = z.logger

# Display from zOS or walker
display = walker.display if walker else z.display
```

---

**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**
