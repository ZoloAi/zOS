# Navigation State Module

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**

---

## Overview

The Navigation State module provides location tracking and navigation history management. It tracks where users are in your application and maintains a history of all navigation events.

**Module:** `navigation_modules/navigation_state.py`

## Purpose

- **Location Tracking**: Track current user location in application
- **History Management**: Maintain navigation history with FIFO overflow
- **Session Storage**: Persist navigation state in session
- **Metadata Management**: Store timestamps and context with navigation events

## Core Concepts

### Navigation Location

A navigation location represents a specific place in your application:

```python
# Location structure
{
    'target': 'users.menu.list_users',  # Where user is
    'context': {                        # Additional metadata
        'section': 'users',
        'action': 'list'
    },
    'timestamp': '2026-03-09T10:30:00'
}
```

**Target Format:** `folder.file.block` (hierarchical path)

---

### Navigation History

History is stored as a list of navigation events with automatic FIFO overflow:

```python
# History structure (session storage)
z.session['navigation_history'] = [
    {
        'target': 'home.menu',
        'context': {},
        'timestamp': '2026-03-09T10:29:00'
    },
    {
        'target': 'users.menu',
        'context': {'section': 'users'},
        'timestamp': '2026-03-09T10:30:00'
    },
    # ... up to max_history entries (default: 50)
]
```

**Overflow Behavior:**
- When history exceeds limit, oldest entries are removed (FIFO)
- Configurable limit via `max_history` parameter
- Default limit: 50 entries

---

## Public API

### navigate_to()

Navigate to a specific location and update current state.

```python
result = z.cli.navigation.navigate_to(
    target="users.menu.list_users",
    context={'section': 'users', 'action': 'list'}
)
```

**Parameters:**
- `target` (str): Navigation target (folder.file.block format)
- `context` (dict): Additional context metadata (optional)

**Returns:** Navigation result dictionary with location info

**Side Effects:**
- Updates current location in session
- Adds entry to navigation history
- Triggers history overflow if needed

---

### get_current_location()

Retrieve the current navigation location.

```python
location = z.cli.navigation.get_current_location()
# Returns: {'target': 'users.menu.list_users', 'context': {...}, 'timestamp': '...'}
```

**Returns:** Current location dictionary or `None` if no location set

---

### get_navigation_history()

Retrieve the complete navigation history.

```python
history = z.cli.navigation.get_navigation_history()
# Returns: List of navigation events (oldest to newest)
```

**Returns:** List of navigation event dictionaries

---

## Usage Examples

### Basic Location Tracking

```python
# Navigate to location
z.cli.navigation.navigate_to("users.menu")

# Get current location
location = z.cli.navigation.get_current_location()
print(f"Current location: {location['target']}")
# Output: Current location: users.menu
```

### Location with Context

```python
# Navigate with rich context
z.cli.navigation.navigate_to(
    target="users.edit.permissions",
    context={
        'user_id': 42,
        'section': 'users',
        'action': 'edit_permissions'
    }
)

# Retrieve context later
location = z.cli.navigation.get_current_location()
user_id = location['context'].get('user_id')
print(f"Editing user: {user_id}")
```

### History Management

```python
# Navigate to multiple locations
locations = [
    "home.menu",
    "users.menu",
    "users.list",
    "users.edit",
    "settings.menu"
]

for loc in locations:
    z.cli.navigation.navigate_to(loc)

# Get full history
history = z.cli.navigation.get_navigation_history()
print(f"History length: {len(history)}")

# Get last 3 locations
recent = history[-3:]
for entry in recent:
    print(f"- {entry['target']} at {entry['timestamp']}")
```

### FIFO Overflow Handling

```python
# Configure history limit
max_history = 10

# Navigate many times (exceeds limit)
for i in range(20):
    z.cli.navigation.navigate_to(f"section{i}.menu")

# History automatically trimmed to 10 entries
history = z.cli.navigation.get_navigation_history()
print(f"History length: {len(history)}")  # Output: 10

# Oldest entries (section0-section9) removed
# Newest entries (section10-section19) retained
```

---

## Session Storage

Navigation state is stored in session with these keys:

```python
# Current location
z.session['current_location'] = {
    'target': 'users.menu',
    'context': {'section': 'users'},
    'timestamp': '2026-03-09T10:30:00'
}

# Navigation history (FIFO list)
z.session['navigation_history'] = [
    # ... list of navigation events
]

# Configuration
z.session['navigation_config'] = {
    'max_history': 50,  # FIFO limit
    'track_timestamps': True
}
```

---

## Advanced Features

### Custom History Limits

```python
# Set custom history limit during navigation
z.cli.navigation.navigate_to(
    target="users.menu",
    context={'max_history': 100}  # Override default limit
)
```

### History Analysis

```python
# Get navigation patterns
history = z.cli.navigation.get_navigation_history()

# Find most visited locations
from collections import Counter
targets = [entry['target'] for entry in history]
most_common = Counter(targets).most_common(5)

print("Most visited locations:")
for target, count in most_common:
    print(f"- {target}: {count} visits")
```

### Context-Based Navigation

```python
# Store workflow state in context
z.cli.navigation.navigate_to(
    target="checkout.payment",
    context={
        'cart_items': ['item1', 'item2'],
        'total_price': 29.99,
        'step': 3
    }
)

# Later, retrieve workflow state
location = z.cli.navigation.get_current_location()
cart = location['context'].get('cart_items')
step = location['context'].get('step')
```

---

## Integration Points

**Depends on:**
- zSession: State and history storage
- zParser: Target expression parsing

**Used by:**
- Breadcrumbs: Location tracking for trail management
- Linking: Target resolution for zLink navigation
- zWalker: State tracking during orchestration

---

## Best Practices

### Target Naming

Use hierarchical, descriptive target names:

```python
# Good: Clear hierarchy
"home.menu"
"users.menu.list"
"users.menu.edit"
"settings.profile.security"

# Bad: Flat, unclear
"page1"
"screen2"
"view3"
```

### Context Usage

Store relevant metadata in context:

```python
# Good: Useful context
z.cli.navigation.navigate_to(
    "users.edit",
    context={
        'user_id': 42,
        'user_name': 'Alice',
        'edit_mode': 'permissions'
    }
)

# Bad: Redundant or missing context
z.cli.navigation.navigate_to("users.edit")  # No context
```

### History Management

Consider history limits based on application needs:

```python
# Short-lived sessions (dashboard, kiosk)
max_history = 10

# Long-running sessions (development tools)
max_history = 100

# Analytics applications
max_history = 500
```

---

## Related Modules

- [breadcrumbs_GUIDE.md](breadcrumbs_GUIDE.md) - Breadcrumb trail management
- [linking_GUIDE.md](linking_GUIDE.md) - Inter-file navigation with zLink

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**
