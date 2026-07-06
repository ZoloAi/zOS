**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**

---

# Modifiers System

The **ModifierProcessor** orchestrates prefix and suffix modifiers, enabling declarative flow control through simple symbols.

> **RETIRED — `!` (Required).** Gating is now an **event** (a `zBtn type: submit`, or a
> whole `zDialog`), never a modifier. The `!` glyph and its retry-until-success policy
> were removed in 2026-06; `RequiredModifier`/`modifier_required.py` no longer exist.
> The `!` sections below are kept only as a historical note — see the zWizard grammar
> leaf for the current "gating is an event" model.
>
> **Also stale:** the prefix-`^` *bounce* shown below predates the change that made `^`
> a **suffix** crumbs-rewind (`<key>^: <zPath>`). Treat the `^`-prefix examples as
> historical; this guide needs a broader refresh beyond the `!` retirement.

## Overview

Modifiers change command behavior through symbolic annotations:

- **Prefix Modifiers**: `~` (anchor)
- **Suffix Modifiers**: `*` (menu), `^` (crumbs-rewind)
- *(retired: `!` required, prefix-`^` bounce)*

## Architecture

```
ModifierProcessor
├── check_prefix()      # Detect ~
├── check_suffix()      # Detect * ^
├── process()           # Route to domain handlers
└── Domain Modifiers
    ├── MenuModifier          # * (create menu)
    └── CrumbsRewindModifier  # ^ suffix (<key>^: <zPath> bulk-back)
    # RETIRED: RequiredModifier (!) — gating is an event now
```

## Bounce Modifier (^)

**Execute action, then return based on mode.**

### Syntax

```python
# Prefix the key with ^
result = z.dispatch.handle("^save", {"zFunc": "save_data"})
```

### Behavior

**zCLI Mode (Terminal):**
```python
result = z.dispatch.handle("^save", {"zFunc": "save_data"})
# Executes save_data()
# Returns: "zBack" → triggers menu navigation
```

**zBifrost Mode (Web):**
```python
result = z.dispatch.handle("^save", {"zFunc": "save_data"})
# Executes save_data()
# Returns: <actual function result> → client handles navigation
```

### Use Cases

- **Menu actions**: Execute action, return to menu
- **Form submissions**: Process form, show menu again
- **One-shot operations**: Complete task, navigate back
- **Wizard steps**: Execute step, return to wizard flow

### Examples

```python
# Simple bounce
result = z.dispatch.handle("^delete", {"zFunc": "delete_user", "args": [user_id]})
# Deletes user, returns to menu

# Bounce with validation
result = z.dispatch.handle("^submit", {"zFunc": "submit_form", "args": [form_data]})
# Submits form, returns to menu

# Bounce in wizard
result = z.dispatch.handle("^confirm", {"zFunc": "confirm_step"}, walker=walker)
# Confirms step, returns to wizard
```

### Implementation

**Detection:**
```python
prefix_mods = modifiers.check_prefix("^save")
# Returns: ["^"]
```

**Processing:**
```python
# BounceModifier.process()
1. Strip ^ from key
2. Execute command via launcher.launch()
3. Check mode (zCLI vs. zBifrost)
4. Return "zBack" (zCLI) or actual result (zBifrost)
```

---

## Menu Modifier (*)

**Create interactive menu from data structure.**

### Syntax

```python
# Suffix the key with *
menu_data = {
    "title": "Main Menu",
    "items": {
        "opt1": {"zFunc": "action1", "label": "Action 1"},
        "opt2": {"zFunc": "action2", "label": "Action 2"}
    }
}
result = z.dispatch.handle("menu*", menu_data)
```

### Behavior

```python
# Creates menu via zNavigation.create()
# User sees:
# ┌─ Main Menu ─┐
# │ 1. Action 1 │
# │ 2. Action 2 │
# │ 0. Back     │
# └─────────────┘
# Select: _
```

### Menu Features

- **Automatic numbering**: Items numbered 1, 2, 3...
- **Back button**: Built-in "0: Back" option
- **Interactive selection**: User chooses via number input
- **Recursive dispatch**: Selected action dispatched automatically
- **Nested menus**: Menu items can trigger other menus

### Use Cases

- **Navigation menus**: Top-level app navigation
- **Action menus**: Choose operation to perform
- **Admin panels**: Administrative actions
- **Settings**: Configuration options

### Examples

```python
# Simple menu
admin_menu = {
    "title": "Admin Panel",
    "items": {
        "users": {"zFunc": "manage_users", "label": "Manage Users"},
        "settings": {"zFunc": "edit_settings", "label": "Settings"},
        "logout": {"zLogout": True, "label": "Logout"}
    }
}
z.dispatch.handle("admin*", admin_menu)

# Nested menu
main_menu = {
    "title": "Main Menu",
    "items": {
        "admin": {"menu*": admin_menu, "label": "Admin Panel"},
        "reports": {"menu*": reports_menu, "label": "Reports"}
    }
}
z.dispatch.handle("main*", main_menu)

# Data-driven menu
users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
user_menu = {
    "title": "Select User",
    "items": {
        f"user_{u['id']}": {"zFunc": "select_user", "args": [u['id']], "label": u['name']}
        for u in users
    }
}
z.dispatch.handle("users*", user_menu)
```

### Implementation

**Detection:**
```python
suffix_mods = modifiers.check_suffix("menu*")
# Returns: ["*"]
```

**Processing:**
```python
# MenuModifier.process()
1. Strip * from key
2. Check for ~ (anchor) modifier
3. Route to zNavigation.create(menu_data, anchor=<bool>)
4. Display menu and handle selection
5. Dispatch selected action
6. Return result
```

---

## Anchor Modifier (~)

**Disable back navigation in menus.**

### Syntax

```python
# Prefix the key with ~, suffix with *
menu_data = {
    "title": "Welcome (No Back)",
    "items": {
        "start": {"zFunc": "start_app", "label": "Start"},
        "exit": {"zFunc": "exit_app", "label": "Exit"}
    }
}
result = z.dispatch.handle("~menu*", menu_data)
```

### Behavior

```python
# Creates menu WITHOUT back button
# User sees:
# ┌─ Welcome (No Back) ─┐
# │ 1. Start            │
# │ 2. Exit             │
# └─────────────────────┘
# Select: _
```

### Use Cases

- **Welcome screens**: Entry point with no back
- **Login menus**: Must authenticate or exit
- **Confirmation dialogs**: Must choose yes/no
- **Terminal states**: No going back (e.g., game over)

### Examples

```python
# Welcome screen
welcome = {
    "title": "Welcome to MyApp",
    "items": {
        "login": {"zLogin": True, "label": "Login"},
        "register": {"zFunc": "register", "label": "Register"},
        "demo": {"zFunc": "demo_mode", "label": "Try Demo"}
    }
}
z.dispatch.handle("~welcome*", welcome)

# Confirmation
confirm = {
    "title": "Delete User?",
    "items": {
        "yes": {"zFunc": "delete_user", "args": [user_id], "label": "Yes, Delete"},
        "no": {"zFunc": "cancel", "label": "No, Cancel"}
    }
}
z.dispatch.handle("~confirm*", confirm)
```

### Implementation

**Detection:**
```python
prefix_mods = modifiers.check_prefix("~menu*")
suffix_mods = modifiers.check_suffix("~menu*")
# prefix_mods: ["~"]
# suffix_mods: ["*"]
```

**Processing:**
```python
# MenuModifier.process()
1. Detect ~ in prefix_mods
2. Set anchor=True
3. Route to zNavigation.create(menu_data, anchor=True)
4. Menu displayed without back button
```

---

## Required Modifier (!) — RETIRED

**Removed in 2026-06.** `!` is no longer a modifier; `RequiredModifier` and
`modifier_required.py` were deleted, and `!` was dropped from `SUFFIX_MODIFIERS`.

The need it served — "hold the flow on a step that must land first" — is now expressed
as an **event**, not a glyph:

- **Gating** (hold the walk until the user acts): use a `zBtn` with `type: submit`, or a
  whole `zDialog`. The walk holds at the event; steps after it don't run until submit.
- **Failure handling**: read by **zForce** (the step's return). A `False`/throw shows its
  own error and the walk carries on — there is no built-in retry-until-success loop.

See the zWizard grammar leaf ("The gate — where the walk waits for you") for the model.

---

## Combined Modifiers

Modifiers can be combined for powerful declarative patterns:

### Anchor + Menu (~*)

**Menu without back navigation.**

```python
# Welcome screen with no back button
result = z.dispatch.handle("~welcome*", welcome_menu)
```

**Use cases:**
- Entry points
- Authentication screens
- Terminal states

### Combining (~*)

While technically possible, not all combinations make semantic sense:

```python
# Anchor (~) is only meaningful with Menu (*)
```

**Valid combinations:**
- `menu*` - Menu
- `~menu*` - Anchored menu

**Invalid combinations:**
- `~action` - Anchor without menu (meaningless)

*(Retired: `!` required and prefix-`^` bounce combinations.)*

---

## Modifier Priority

When multiple modifiers detected, processing order:

1. **Menu (*)** - Highest priority (creates menu structure)
2. **Crumbs-rewind (`<key>^`)** - mint the bulk-back signal
3. **Anchor (~)** - Modifies menu behavior (no standalone processing)

*(Retired: `!` required and prefix-`^` bounce.)*

---

## Mode Behavior

Modifiers adjust behavior based on execution mode:

### zCLI Mode (Terminal)

```python
# Menu creates interactive selection
result = z.dispatch.handle("menu*", data)
# Displays menu → waits for input → dispatches selection
```

### zBifrost Mode (Web)

```python
# Menu creates structured response
result = z.dispatch.handle("menu*", data)
# Returns: menu structure → client renders UI
```

---

## Error Handling

Modifiers handle errors gracefully:

```python
# Invalid modifier combination
result = z.dispatch.handle("^~action", cmd)
# Logs warning, processes as regular command

# Missing command after modifier
result = z.dispatch.handle("^", None)
# Returns: None (logs error)

# Modifier on invalid command
result = z.dispatch.handle("menu*", "not a dict")
# Returns: None (logs error)
```

---

## Best Practices

### Use Bounce for Actions

```python
# ✅ Good: Bounce on actions that should return
z.dispatch.handle("^delete", {"zFunc": "delete_user"})

# ❌ Bad: No bounce when you want to stay
z.dispatch.handle("delete", {"zFunc": "delete_user"})
# User stuck after deletion
```

### Use Anchor for Entry Points

```python
# ✅ Good: Anchor welcome screens
z.dispatch.handle("~welcome*", welcome_menu)

# ❌ Bad: Back button on welcome screen
z.dispatch.handle("welcome*", welcome_menu)
# User can "go back" to nothing
```

### Gate with an Event (not `!`)

Validation / "must land first" is no longer a modifier. Gate the flow with an event —
a `zBtn type: submit` or a `zDialog` holds the walk until the user acts; the step's own
return (zForce) decides pass/fail. See the zWizard grammar leaf.

### Combine Thoughtfully

```python
# ✅ Good: Meaningful combination
z.dispatch.handle("~menu*", data)     # Entry point menu

# ❌ Bad: Meaningless combination
z.dispatch.handle("~action", cmd)     # Anchor without menu?
```

---

**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**
