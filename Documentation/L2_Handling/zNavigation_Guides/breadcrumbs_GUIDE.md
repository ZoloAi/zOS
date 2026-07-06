# Breadcrumbs Module

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**

---

## Overview

The Breadcrumbs module provides navigation trail management with "Back" functionality. It tracks where users have been and enables backward navigation through menu hierarchies.

**Module:** `navigation_modules/navigation_breadcrumbs.py`

## Purpose

- **Trail Management**: Track navigation path with breadcrumb trails
- **Back Functionality**: Navigate backwards through breadcrumb history
- **Session Storage**: Persist breadcrumbs in session
- **UI Reloading**: Reload UI files based on breadcrumb state

## Core Concepts

### What are Breadcrumbs?

Breadcrumbs are navigation markers that track where users have been in your application. Think of them as a trail of digital "breadcrumbs" leading back to where you started.

**Example Navigation Trail:**
```
Home → Users → List Users → Edit User
```

Each arrow represents a breadcrumb that the user can navigate back through.

---

## Public API

### handle_zCrumbs()

Add a breadcrumb to the navigation trail.

```python
z.cli.navigation.handle_zCrumbs(
    zBlock="users.menu",
    zKey="list_users",
    walker=walker
)
```

**Parameters:**
- `zBlock` (str): Block identifier (file.block format)
- `zKey` (str): Option key for breadcrumb
- `walker` (Walker): Walker instance for orchestration

**Returns:** Navigation result (varies based on breadcrumb action)

**When to use:** After menu selection, before navigating to new section

---

### handle_zBack()

Navigate backwards through the breadcrumb trail.

```python
result = z.cli.navigation.handle_zBack(
    show_banner=True,
    walker=walker
)
```

**Parameters:**
- `show_banner` (bool): Display "Going back..." banner (default: True)
- `walker` (Walker): Walker instance for orchestration

**Returns:** Previous location identifier (str)

**When to use:** When user selects "Back" option or presses back button

---

## Breadcrumb Storage

Breadcrumbs are stored in the session as a stack:

```python
# Session storage structure
z.session['breadcrumbs'] = [
    {
        'block': 'users.menu',
        'key': 'list_users',
        'timestamp': '2026-03-09T10:30:00'
    },
    {
        'block': 'users.list',
        'key': 'edit_user',
        'timestamp': '2026-03-09T10:31:00'
    }
]
```

**Stack Behavior:**
- New breadcrumbs push to end of list
- `handle_zBack()` pops from end (LIFO)
- Empty stack returns to default location

---

## Usage Examples

### Basic Breadcrumb Trail

```python
# User navigates: Home → Settings → Profile
z.cli.navigation.handle_zCrumbs("home.menu", "settings", walker)
z.cli.navigation.handle_zCrumbs("settings.menu", "profile", walker)

# User presses "Back"
result = z.cli.navigation.handle_zBack(walker=walker)
# Returns to: Settings menu
```

### Menu with Auto-Breadcrumbs

```python
# Breadcrumbs added automatically when allow_back=True
choice = z.cli.navigation.create(
    ["Settings", "Profile", "Logout"],
    title="Main Menu",
    allow_back=True,  # Enables breadcrumb integration
    walker=walker
)

if choice == "Back":
    # Automatically handled by system
    pass
```

### Multi-Level Navigation

```python
# Deep navigation hierarchy
z.cli.navigation.handle_zCrumbs("home.menu", "users", walker)
z.cli.navigation.handle_zCrumbs("users.menu", "list", walker)
z.cli.navigation.handle_zCrumbs("users.list", "edit", walker)
z.cli.navigation.handle_zCrumbs("users.edit", "permissions", walker)

# Navigate back step by step
z.cli.navigation.handle_zBack(walker=walker)  # → users.edit
z.cli.navigation.handle_zBack(walker=walker)  # → users.list
z.cli.navigation.handle_zBack(walker=walker)  # → users.menu
z.cli.navigation.handle_zBack(walker=walker)  # → home.menu
```

---

## UI File Reloading

When navigating back, the system automatically reloads the appropriate UI file:

```python
# User at: users.edit.permissions
z.cli.navigation.handle_zBack(walker=walker)

# System automatically:
# 1. Pops breadcrumb from stack
# 2. Identifies previous file (users.edit)
# 3. Reloads UI file: users.yaml
# 4. Displays previous block: edit
```

**File Resolution:**
- Breadcrumb block format: `folder.file.block`
- Extracts folder and file: `folder/file.yaml`
- Loads file via zLoader
- Displays specified block via Walker

---

## Integration Points

**Depends on:**
- zSession: Breadcrumb storage
- zLoader: UI file loading
- zWalker: Orchestration and file navigation

**Used by:**
- MenuSystem: Automatic breadcrumb integration
- zWalker: Back navigation handler
- User applications: Custom navigation flows

---

## Best Practices

### When to Add Breadcrumbs

✅ **Do add breadcrumbs:**
- After menu selection
- Before navigating to new section
- At the start of multi-step flows

❌ **Don't add breadcrumbs:**
- For lateral navigation (same level)
- In temporary modals/popups
- For error pages

### Breadcrumb Naming

Use descriptive, hierarchical block names:

```python
# Good: Clear hierarchy
"home.menu"
"users.menu"
"users.list"
"users.edit"

# Bad: Flat, unclear
"menu1"
"menu2"
"page3"
```

### Handling Empty Trails

```python
# Check if breadcrumb trail is empty
breadcrumbs = z.session.get('breadcrumbs', [])

if not breadcrumbs:
    # Return to default home location
    z.cli.navigation.navigate_to("home.menu")
else:
    # Navigate back normally
    z.cli.navigation.handle_zBack(walker=walker)
```

---

## Related Modules

- [menu_system_GUIDE.md](menu_system_GUIDE.md) - Menu creation with breadcrumb integration
- [navigation_state_GUIDE.md](navigation_state_GUIDE.md) - Navigation state tracking

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**
