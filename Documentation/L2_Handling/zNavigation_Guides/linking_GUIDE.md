# Linking Module

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**

---

## Overview

The Linking module provides inter-file navigation with zLink expressions and RBAC permission checking. It enables declarative navigation between files and blocks with automatic session context updates.

**Module:** `navigation_modules/navigation_linking.py`

## Purpose

- **Inter-file Navigation**: Navigate between UI files and blocks
- **zLink Expressions**: Declarative linking with expression syntax
- **RBAC Integration**: Permission checking for navigation targets
- **Session Context**: Automatic updates to zVaFolder, zVaFile, zBlock

## Core Concepts

### zLink Expressions

zLink expressions provide declarative navigation syntax:

```python
# Basic format
zLink(folder.file.block)

# Examples
zLink(users.menu.list)           # Navigate to users/menu.yaml → list block
zLink(settings.profile.security) # Navigate to settings/profile.yaml → security block
zLink(admin.dashboard.overview)  # Navigate to admin/dashboard.yaml → overview block
```

**Expression Structure:**
- `folder`: Directory containing UI file
- `file`: UI file name (without .yaml extension)
- `block`: Block identifier within file

---

### RBAC Permission Checking

All zLink navigation respects RBAC permissions:

```python
# User tries to navigate to admin section
result = z.cli.navigation.handle_zLink("zLink(admin.settings.security)", walker)

# If user lacks admin permissions:
# - Navigation blocked
# - Error message displayed
# - User remains at current location
```

**Permission Resolution:**
1. Extract target from zLink expression
2. Check user permissions via zAuth
3. Allow/deny navigation based on result
4. Display appropriate messages

---

## Public API

### handle_zLink()

Process zLink expression and navigate to target.

```python
result = z.cli.navigation.handle_zLink(
    zHorizontal="zLink(users.menu.list_users)",
    walker=walker
)
```

**Parameters:**
- `zHorizontal` (str): zLink expression string
- `walker` (Walker): Walker instance for orchestration

**Returns:** Navigation result (file content or None)

**Side Effects:**
- Updates session context (zVaFolder, zVaFile, zBlock)
- Checks RBAC permissions
- Loads target file via zLoader
- Updates navigation state

---

## Usage Examples

### Basic Navigation

```python
# Navigate to users menu
result = z.cli.navigation.handle_zLink(
    "zLink(users.menu)",
    walker=walker
)

# Session context automatically updated:
# z.session['zVaFolder'] = 'users'
# z.session['zVaFile'] = 'menu'
# z.session['zBlock'] = None (no specific block)
```

### Navigate to Specific Block

```python
# Navigate to specific block within file
result = z.cli.navigation.handle_zLink(
    "zLink(users.list.edit_user)",
    walker=walker
)

# Session context:
# z.session['zVaFolder'] = 'users'
# z.session['zVaFile'] = 'list'
# z.session['zBlock'] = 'edit_user'
```

### RBAC-Protected Navigation

```python
# Try to navigate to admin section
result = z.cli.navigation.handle_zLink(
    "zLink(admin.settings.security)",
    walker=walker
)

# If user has admin role:
# - Navigation succeeds
# - File loaded and displayed

# If user lacks admin role:
# - Navigation blocked
# - Error: "Access denied: Insufficient permissions"
# - User remains at current location
```

### Navigation with zParser Integration

```python
# zLink expressions support zParser evaluation
# Use variables in navigation targets
z.session['zVars']['current_section'] = 'users'
z.session['zVars']['current_file'] = 'menu'

# Dynamic zLink (evaluated by zParser)
result = z.cli.navigation.handle_zLink(
    "zLink({current_section}.{current_file})",
    walker=walker
)
```

---

## Session Context Updates

When navigating via zLink, session context is automatically updated:

```python
# Before navigation
z.session['zVaFolder'] = 'home'
z.session['zVaFile'] = 'menu'
z.session['zBlock'] = None

# Navigate to users.list.edit
z.cli.navigation.handle_zLink("zLink(users.list.edit)", walker)

# After navigation
z.session['zVaFolder'] = 'users'
z.session['zVaFile'] = 'list'
z.session['zBlock'] = 'edit'
```

**Context Variables:**
- `zVaFolder`: Current folder (directory path)
- `zVaFile`: Current file (without extension)
- `zBlock`: Current block identifier

**Use Cases:**
- Display current location in UI
- Conditional rendering based on location
- Navigation state tracking
- Breadcrumb generation

---

## Integration with Other Modules

### zParser Integration

zLink expressions are evaluated by zParser:

```python
# zParser evaluates variables and expressions
# Before evaluation: "zLink({folder}.{file})"
# After evaluation: "zLink(users.menu)"

result = z.cli.navigation.handle_zLink(
    "zLink({folder}.{file})",
    walker=walker
)
```

### zLoader Integration

Target files are loaded via zLoader:

```python
# zLink triggers file loading
result = z.cli.navigation.handle_zLink("zLink(users.menu)", walker)

# Internally:
# 1. Parse expression: folder='users', file='menu'
# 2. Construct path: 'users/menu.yaml'
# 3. Load file via zLoader
# 4. Return file content to Walker
```

### zAuth Integration

RBAC permissions checked via zAuth:

```python
# Check permissions before navigation
result = z.cli.navigation.handle_zLink("zLink(admin.settings)", walker)

# Internally:
# 1. Extract target: 'admin.settings'
# 2. Check permissions: zAuth.check_permission('admin', user)
# 3. Allow/deny navigation
# 4. Display appropriate message
```

---

## Advanced Features

### Conditional Navigation

```python
# Navigate based on user role
user_role = z.session.get('user_role')

if user_role == 'admin':
    target = "admin.dashboard"
elif user_role == 'user':
    target = "user.dashboard"
else:
    target = "guest.landing"

result = z.cli.navigation.handle_zLink(f"zLink({target})", walker)
```

### Navigation with Validation

```python
# Validate target before navigation
def validate_target(target):
    """Check if target file exists."""
    # Custom validation logic
    return True  # or False

target = "users.menu"
if validate_target(target):
    result = z.cli.navigation.handle_zLink(f"zLink({target})", walker)
else:
    print(f"Invalid target: {target}")
```

### Dynamic Menu Navigation

```python
# Generate navigation targets from data
users = fetch_users()  # [{'id': 1, 'name': 'Alice'}, ...]

# Create menu with zLink targets
menu_options = []
for user in users:
    option = {
        'label': user['name'],
        'action': f"zLink(users.edit.{user['id']})"
    }
    menu_options.append(option)

# Display menu (selections auto-navigate via zLink)
choice = z.cli.navigation.create(menu_options, walker=walker)
```

---

## Error Handling

### Permission Denied

```python
# User lacks permissions
result = z.cli.navigation.handle_zLink("zLink(admin.settings)", walker)

# If permission denied:
# - Returns None
# - Displays error: "Access denied: Insufficient permissions"
# - User remains at current location
# - No session context update
```

### Invalid Target

```python
# File doesn't exist
result = z.cli.navigation.handle_zLink("zLink(invalid.file)", walker)

# If file not found:
# - Returns None
# - Displays error: "File not found: invalid/file.yaml"
# - User remains at current location
```

### Malformed Expression

```python
# Invalid zLink syntax
result = z.cli.navigation.handle_zLink("zLink(invalid)", walker)

# If expression invalid:
# - Returns None
# - Displays error: "Invalid zLink expression"
# - User remains at current location
```

---

## Integration Points

**Depends on:**
- zParser: Expression evaluation
- zLoader: File loading
- zAuth: RBAC permission checking
- zSession: Context storage

**Used by:**
- zWalker: Orchestration and navigation flow
- Menu options: Click actions
- User applications: Programmatic navigation

---

## Best Practices

### Target Naming

Use clear, hierarchical target names:

```python
# Good: Descriptive hierarchy
"users.menu"
"users.list.edit"
"settings.profile.security"

# Bad: Unclear, flat
"page1"
"screen2"
```

### Permission Structure

Align navigation targets with RBAC roles:

```python
# Good: Role-based targets
"admin.settings"      # Requires 'admin' role
"user.profile"        # Requires 'user' role
"public.landing"      # No role required

# Bad: Inconsistent with roles
"settings.admin"      # Confusing role mapping
"admin_page"          # Unclear hierarchy
```

### Expression Validation

Validate zLink expressions before use:

```python
# Good: Validate before navigation
if is_valid_zlink(expression):
    result = z.cli.navigation.handle_zLink(expression, walker)
else:
    print("Invalid navigation expression")

# Bad: No validation
result = z.cli.navigation.handle_zLink(untrusted_input, walker)
```

---

## Related Modules

- [navigation_state_GUIDE.md](navigation_state_GUIDE.md) - Navigation state tracking
- [resolvers_GUIDE.md](resolvers_GUIDE.md) - zLink expression resolution

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**
