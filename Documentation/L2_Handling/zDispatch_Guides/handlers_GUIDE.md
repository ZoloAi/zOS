**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**

---

# Handlers

**Handlers** are domain-specific components that integrate zDispatch with subsystems for authentication, CRUD operations, navigation, and routing.

## Overview

Handlers encapsulate integration logic for specific domains:

| Handler | Purpose | Subsystems |
|---------|---------|------------|
| **AuthHandler** | Authentication operations | zAuth |
| **CRUDHandler** | Auto-detected database operations | zData |
| **NavigationHandler** | Menu creation and navigation | zNavigation |
| **SubsystemRouter** | Function/wizard/dialog routing | zFunc, zWizard, zDialog |
| **RoutingHandlers** | Mixin for routing logic | All |
| **WizardDataHandlers** | Wizard-specific data routing | zWizard, zData |

---

## AuthHandler

**Handles zLogin and zLogout commands.**

### Purpose

Integrates zDispatch with zAuth subsystem for authentication operations.

### Commands

```python
# Login
z.dispatch.handle("auth", {"zLogin": True})
# Triggers zAuth.login() flow

# Logout
z.dispatch.handle("auth", {"zLogout": True})
# Triggers zAuth.logout() flow

# Login with context
z.dispatch.handle("auth", {"zLogin": True}, context={"redirect": "/dashboard"})
```

### Implementation

```python
class AuthHandler:
    def handle_login(self, context=None):
        """Execute zAuth.login() with optional context."""
        return self.zos.auth.login(context=context)
    
    def handle_logout(self, context=None):
        """Execute zAuth.logout() with optional context."""
        return self.zos.auth.logout(context=context)
```

### Integration

- **Input**: `{"zLogin": True}` or `{"zLogout": True}`
- **Output**: Authentication result from zAuth
- **Side effects**: Session state changes, redirect navigation

---

## CRUDHandler

**Auto-detects and routes CRUD operations to zData.**

### Purpose

Simplifies database operations by auto-detecting CRUD patterns and routing to zData subsystem.

### Detection Rules

Commands with these keys are auto-detected as CRUD:

- Has `action` key → CRUD
- Has `model` or `table` key → CRUD
- Routes to zData automatically

### Commands

```python
# Auto-detected CRUD (no "zData" wrapper needed)
command = {
    "action": "read",
    "model": "users",
    "where": {"id": 1}
}
z.dispatch.handle("read", command)
# Auto-routes to zData.crud()

# Explicit zData format (also works)
command = {
    "zData": {
        "action": "read",
        "model": "users",
        "where": {"id": 1}
    }
}
z.dispatch.handle("read", command)
```

### CRUD Actions

| Action | Purpose | Example |
|--------|---------|---------|
| `read` | Query single record | `{"action": "read", "model": "users", "where": {"id": 1}}` |
| `list` | Query multiple records | `{"action": "list", "model": "users", "limit": 10}` |
| `create` | Insert new record | `{"action": "create", "model": "users", "values": {...}}` |
| `update` | Modify existing record | `{"action": "update", "model": "users", "values": {...}, "where": {...}}` |
| `delete` | Remove record | `{"action": "delete", "model": "users", "where": {"id": 1}}` |

### Implementation

```python
class CRUDHandler:
    def is_crud_dict(self, horizontal):
        """Check if dict is CRUD operation."""
        if not isinstance(horizontal, dict):
            return False
        # Has action key?
        if "action" in horizontal:
            return True
        # Has model or table key?
        if "model" in horizontal or "table" in horizontal:
            return True
        return False
    
    def handle_crud(self, horizontal, context=None):
        """Route to zData.crud()."""
        return self.zos.data.crud(horizontal, context=context)
```

### Integration

- **Input**: Dict with action/model/table keys
- **Output**: Database operation result from zData
- **Side effects**: Database modifications

---

## NavigationHandler

**Creates menus via zNavigation subsystem.**

### Purpose

Integrates zDispatch with zNavigation for interactive menu creation.

### Commands

```python
# Menu with back button
menu_data = {
    "title": "Main Menu",
    "items": {
        "opt1": {"zFunc": "action1", "label": "Action 1"},
        "opt2": {"zFunc": "action2", "label": "Action 2"}
    }
}
z.dispatch.handle("menu*", menu_data)

# Anchored menu (no back button)
z.dispatch.handle("~menu*", menu_data)
```

### Menu Structure

```python
menu_data = {
    "title": "Menu Title",          # Required
    "items": {                       # Required
        "key1": {
            "label": "Option 1",     # Display text
            "zFunc": "action1"       # Action (any command)
        },
        "key2": {
            "label": "Option 2",
            "zWizard": "wizard1"
        }
    },
    "anchor": False                  # Optional (default: False)
}
```

### Implementation

```python
class NavigationHandler:
    def create_menu(self, menu_data, anchor=False, walker=None):
        """Create menu via zNavigation.create()."""
        return self.zos.navigation.create(
            menu_data=menu_data,
            anchor=anchor,
            walker=walker
        )
```

### Integration

- **Input**: Menu data dict with title and items
- **Output**: User selection result
- **Side effects**: Interactive menu display, user input collection

---

## SubsystemRouter

**Routes commands to zFunc, zWizard, and zDialog subsystems.**

### Purpose

Centralizes routing logic for function execution, workflows, and forms.

### Commands

```python
# Function execution
z.dispatch.handle("action", {"zFunc": "my_function"})
z.dispatch.handle("action", "zFunc(my_function)")

# Wizard invocation
z.dispatch.handle("wizard", {"zWizard": "setup_wizard"})
z.dispatch.handle("wizard", "zWizard(setup_wizard)")

# Dialog/form display
z.dispatch.handle("form", {"zDialog": "contact_form"})
```

### Routing Logic

```python
class SubsystemRouter:
    def route_zfunc(self, func_name, args=None, kwargs=None, context=None):
        """Route to zFunc subsystem."""
        return self.zos.func.execute(
            func_name=func_name,
            args=args,
            kwargs=kwargs,
            context=context
        )
    
    def route_zwizard(self, wizard_name, context=None, walker=None):
        """Route to zWizard subsystem."""
        return self.zos.wizard.start(
            wizard_name=wizard_name,
            context=context,
            walker=walker
        )
    
    def route_zdialog(self, dialog_name, context=None):
        """Route to zDialog subsystem."""
        return self.zos.dialog.show(
            dialog_name=dialog_name,
            context=context
        )
```

### Plugin Support

```python
# Plugin function (& prefix)
z.dispatch.handle("action", "zFunc(&my_plugin.func)")

# Router detects & prefix → calls zParser
result = self.zos.parser.resolve_plugin("my_plugin.func")
# Then executes resolved function
```

### Integration

- **zFunc**: Function execution with args/kwargs
- **zWizard**: Multi-step workflow orchestration
- **zDialog**: Interactive form display
- **zParser**: Plugin resolution for & prefix

---

## RoutingHandlers

**Mixin providing routing utilities for CommandLauncher.**

### Purpose

Shared routing logic used by CommandLauncher for common patterns.

### Methods

```python
class RoutingHandlers:
    def _route_to_subsystem(self, subsystem_name, command_data, context):
        """Generic subsystem routing."""
        subsystem = getattr(self.zos, subsystem_name)
        return subsystem.handle(command_data, context=context)
    
    def _extract_args_kwargs(self, command_dict):
        """Extract args and kwargs from command dict."""
        args = command_dict.get("args", [])
        kwargs = command_dict.get("kwargs", {})
        return args, kwargs
    
    def _get_display_for_context(self, walker):
        """Get appropriate display instance."""
        return walker.display if walker else self.display
```

### Usage

```python
class CommandLauncher(RoutingHandlers):
    def _launch_dict(self, horizontal, context, walker):
        # Use inherited routing methods
        args, kwargs = self._extract_args_kwargs(horizontal)
        display = self._get_display_for_context(walker)
        # ...
```

---

## WizardDataHandlers

**Handles wizard-specific data operations.**

### Purpose

Integrates wizard context with data operations for wizard steps that read/write data.

### Commands

```python
# Read operation in wizard step
result = z.dispatch.handle(
    "read",
    {
        "zRead": {
            "model": "users",
            "where": {"id": context["user_id"]}
        }
    },
    walker=walker
)

# Data operation with wizard context
result = z.dispatch.handle(
    "save",
    {
        "zData": {
            "action": "update",
            "model": "profile",
            "values": wizard_data,
            "where": {"user_id": context["user_id"]}
        }
    },
    walker=walker
)
```

### Implementation

```python
class WizardDataHandlers:
    def handle_wizard_read(self, read_data, walker):
        """Handle zRead in wizard context."""
        # Merge wizard context with read data
        context = walker.context if walker else {}
        return self.zos.data.read(read_data, context=context)
    
    def handle_wizard_data(self, data_command, walker):
        """Handle zData in wizard context."""
        # Pass walker context to data operations
        context = walker.context if walker else {}
        return self.zos.data.crud(data_command, context=context)
```

### Integration

- **Input**: Data commands with walker context
- **Output**: Data operation results
- **Side effects**: Database operations scoped to wizard context

---

## Handler Integration Flow

```
User Command
    ↓
CommandLauncher.launch()
    ↓
[Detect Command Type]
    ↓
├─ {"zLogin": ...}  → AuthHandler.handle_login()
├─ {"zLogout": ...} → AuthHandler.handle_logout()
├─ {"action": ...}  → CRUDHandler.handle_crud()
├─ {"zFunc": ...}   → SubsystemRouter.route_zfunc()
├─ {"zWizard": ...} → SubsystemRouter.route_zwizard()
└─ menu* modifier   → NavigationHandler.create_menu()
    ↓
Subsystem Execution
    ↓
Return Result
```

---

## Error Handling

All handlers provide graceful error handling:

```python
# AuthHandler
try:
    result = auth_handler.handle_login()
except AuthError as e:
    logger.error(f"Login failed: {e}")
    return None

# CRUDHandler
if not crud_handler.is_crud_dict(command):
    logger.warning("Not a valid CRUD command")
    return None

# NavigationHandler
if "title" not in menu_data or "items" not in menu_data:
    logger.error("Invalid menu structure")
    return None
```

---

## Best Practices

### Use Auto-Detection

```python
# ✅ Good: Let CRUD auto-detect
command = {
    "action": "read",
    "model": "users"
}

# ❌ Bad: Unnecessary wrapper
command = {
    "zData": {
        "action": "read",
        "model": "users"
    }
}
```

### Pass Context

```python
# ✅ Good: Include context for handlers
context = {"user_id": 123, "session": session_id}
z.dispatch.handle("action", command, context=context)

# ❌ Bad: Missing context for scoped operations
z.dispatch.handle("action", command)  # No user context
```

### Use Walker in Wizards

```python
# ✅ Good: Pass walker to handlers
z.dispatch.handle("step", command, walker=walker)
# Handlers use walker.display and walker.context

# ❌ Bad: No walker in wizard step
z.dispatch.handle("step", command)
# Loses wizard context
```

---

**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**
