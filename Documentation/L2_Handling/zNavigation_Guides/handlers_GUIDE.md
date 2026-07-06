# Handlers Module

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**

---

## Overview

The Handlers module provides specialized handlers for navigation operations - navbar management, panel handling, breadcrumb operations, history tracking, and back navigation. These handlers orchestrate complex navigation workflows.

**Module:** `navigation_modules/handlers/`

## Purpose

- **Navbar Management**: Handle navigation bar state and interactions
- **Panel Handling**: Manage navigation panels and sidebars
- **Breadcrumb Operations**: Advanced breadcrumb trail operations
- **History Tracking**: Navigation history analysis and management
- **Back Navigation**: Enhanced back functionality with state restoration

## Handler Components

### handler_navbar.py

**Purpose:** Navigation bar state management and interaction handling

**Key Responsibilities:**
- Navbar state tracking
- Active item highlighting
- Navbar rendering coordination
- Click event handling

**Public API:**
```python
# Update navbar state
z.cli.navigation.handlers.navbar.update_state(
    active_item="users",
    visible_items=["home", "users", "settings"]
)

# Get current navbar state
state = z.cli.navigation.handlers.navbar.get_state()
```

**Use Cases:**
- Top-level navigation menus
- Tab-based navigation
- Section switching

---

### handler_panels.py

**Purpose:** Navigation panel management (sidebars, drawers)

**Key Responsibilities:**
- Panel visibility state
- Panel content updates
- Multi-panel coordination
- Drawer open/close handling

**Public API:**
```python
# Show navigation panel
z.cli.navigation.handlers.panels.show(
    panel_id="sidebar",
    content={"items": ["A", "B", "C"]}
)

# Hide navigation panel
z.cli.navigation.handlers.panels.hide(panel_id="sidebar")

# Check panel state
is_visible = z.cli.navigation.handlers.panels.is_visible("sidebar")
```

**Use Cases:**
- Sidebar navigation
- Drawer menus
- Contextual navigation panels

---

### handler_breadcrumbs_ops.py

**Purpose:** Advanced breadcrumb operations and management

**Key Responsibilities:**
- Breadcrumb trail manipulation
- Custom breadcrumb formatting
- Trail truncation (long paths)
- Breadcrumb rendering styles

**Public API:**
```python
# Add breadcrumb with metadata
z.cli.navigation.handlers.breadcrumbs_ops.add_with_metadata(
    label="User Edit",
    target="users.edit",
    metadata={'user_id': 42}
)

# Truncate long breadcrumb trails
z.cli.navigation.handlers.breadcrumbs_ops.truncate(max_items=5)

# Format breadcrumb trail for display
formatted = z.cli.navigation.handlers.breadcrumbs_ops.format_trail(
    style="compact"  # or "full", "minimal"
)
```

**Use Cases:**
- Custom breadcrumb rendering
- Long path management
- Metadata-rich breadcrumbs

---

### handler_history.py

**Purpose:** Navigation history analysis and management

**Key Responsibilities:**
- History entry filtering
- Navigation pattern analysis
- History cleanup operations
- Statistics generation

**Public API:**
```python
# Get history entries matching criteria
entries = z.cli.navigation.handlers.history.filter_entries(
    target_pattern="users.*",
    time_range="last_hour"
)

# Analyze navigation patterns
patterns = z.cli.navigation.handlers.history.analyze_patterns()

# Clear old history entries
z.cli.navigation.handlers.history.cleanup(older_than_days=7)

# Get navigation statistics
stats = z.cli.navigation.handlers.history.get_statistics()
# Returns: {'total_navigations': 150, 'unique_targets': 25, ...}
```

**Use Cases:**
- Analytics dashboards
- User behavior analysis
- History management tools

---

### handler_zback.py

**Purpose:** Enhanced back navigation with state restoration

**Key Responsibilities:**
- Smart back navigation
- State restoration on back
- Back button customization
- Multi-step back operations

**Public API:**
```python
# Navigate back with state restoration
result = z.cli.navigation.handlers.zback.navigate_back(
    restore_state=True,
    steps=1  # Number of steps to go back
)

# Navigate back multiple steps
result = z.cli.navigation.handlers.zback.navigate_back(steps=3)

# Check if back is available
can_back = z.cli.navigation.handlers.zback.can_navigate_back()

# Get back button configuration
config = z.cli.navigation.handlers.zback.get_button_config()
```

**Use Cases:**
- Multi-step workflows
- Form wizards with back
- Deep navigation hierarchies

---

## Usage Examples

### Navbar with Active State

```python
# Update navbar when navigating to section
def navigate_to_section(section):
    # Update navbar active state
    z.cli.navigation.handlers.navbar.update_state(
        active_item=section,
        visible_items=["home", "users", "settings", "admin"]
    )
    
    # Navigate to section
    z.cli.navigation.navigate_to(f"{section}.menu")

# Usage
navigate_to_section("users")
```

### Sidebar Panel Toggle

```python
# Toggle sidebar visibility
def toggle_sidebar():
    panel_id = "main_sidebar"
    
    if z.cli.navigation.handlers.panels.is_visible(panel_id):
        z.cli.navigation.handlers.panels.hide(panel_id)
    else:
        # Show with navigation items
        z.cli.navigation.handlers.panels.show(
            panel_id,
            content={
                "items": [
                    {"label": "Dashboard", "target": "home.dashboard"},
                    {"label": "Users", "target": "users.menu"},
                    {"label": "Settings", "target": "settings.menu"}
                ]
            }
        )
```

### Custom Breadcrumb Rendering

```python
# Display breadcrumbs with custom styling
def render_breadcrumbs():
    # Add current location to breadcrumbs
    z.cli.navigation.handlers.breadcrumbs_ops.add_with_metadata(
        label="User Profile",
        target="users.profile",
        metadata={'user_id': 42, 'section': 'users'}
    )
    
    # Format for display (truncate if too long)
    if len(z.session.get('breadcrumbs', [])) > 5:
        z.cli.navigation.handlers.breadcrumbs_ops.truncate(max_items=5)
    
    # Get formatted trail
    trail = z.cli.navigation.handlers.breadcrumbs_ops.format_trail(
        style="compact"
    )
    
    print(f"Current path: {trail}")
```

### Navigation History Analysis

```python
# Analyze user navigation patterns
def analyze_user_behavior():
    # Get all history entries
    history = z.cli.navigation.handlers.history.filter_entries()
    
    # Find most visited targets
    stats = z.cli.navigation.handlers.history.get_statistics()
    
    print(f"Total navigations: {stats['total_navigations']}")
    print(f"Unique targets: {stats['unique_targets']}")
    
    # Analyze patterns
    patterns = z.cli.navigation.handlers.history.analyze_patterns()
    print(f"Common sequences: {patterns['sequences']}")
```

### Multi-Step Back Navigation

```python
# Navigate back through wizard steps
def back_in_wizard(current_step):
    # Check if back is available
    if not z.cli.navigation.handlers.zback.can_navigate_back():
        print("Cannot go back - at first step")
        return
    
    # Calculate steps to go back
    if current_step > 1:
        steps = 1  # Go back one step
    else:
        steps = current_step  # Go back to start
    
    # Navigate back with state restoration
    result = z.cli.navigation.handlers.zback.navigate_back(
        restore_state=True,
        steps=steps
    )
    
    print(f"Returned to: {result}")
```

---

## Integration Points

**Depends on:**
- Navigation State: Location and history tracking
- Breadcrumbs: Trail management
- zSession: State storage
- zDisplay: UI rendering

**Used by:**
- zWalker: Navigation orchestration
- Menu System: Navigation actions
- User applications: Custom navigation flows

---

## Advanced Features

### Custom Navbar Rendering

```python
# Define custom navbar renderer
def custom_navbar_renderer(state):
    """Custom navbar rendering logic."""
    items = state['visible_items']
    active = state['active_item']
    
    # Render with custom styling
    for item in items:
        style = "active" if item == active else "normal"
        print(f"[{style}] {item}")

# Register custom renderer
z.cli.navigation.handlers.navbar.set_renderer(custom_navbar_renderer)
```

### Panel Event Handlers

```python
# Register panel event handlers
z.cli.navigation.handlers.panels.on_show("sidebar", lambda: print("Sidebar opened"))
z.cli.navigation.handlers.panels.on_hide("sidebar", lambda: print("Sidebar closed"))

# Trigger events
z.cli.navigation.handlers.panels.show("sidebar", content={})
# Output: "Sidebar opened"
```

### History Export

```python
# Export navigation history for analysis
history_data = z.cli.navigation.handlers.history.export(
    format="json",
    include_metadata=True
)

# Save to file
with open("navigation_history.json", "w") as f:
    f.write(history_data)
```

---

## Best Practices

### Navbar State Management

```python
# Good: Update navbar on every navigation
def navigate(section):
    z.cli.navigation.handlers.navbar.update_state(active_item=section)
    z.cli.navigation.navigate_to(f"{section}.menu")

# Bad: Navbar state out of sync
z.cli.navigation.navigate_to("users.menu")  # Navbar not updated
```

### Panel Lifecycle

```python
# Good: Clean panel state on close
def close_panel(panel_id):
    z.cli.navigation.handlers.panels.hide(panel_id)
    # Clear panel data
    z.session.pop(f"panel_{panel_id}_data", None)

# Bad: Panel data persists after close
z.cli.navigation.handlers.panels.hide(panel_id)
```

### History Maintenance

```python
# Good: Regular history cleanup
def cleanup_old_history():
    # Remove entries older than 30 days
    z.cli.navigation.handlers.history.cleanup(older_than_days=30)

# Bad: History grows indefinitely
# (No cleanup, memory issues)
```

---

## Related Modules

- [menu_system_GUIDE.md](menu_system_GUIDE.md) - Menu creation and interaction
- [breadcrumbs_GUIDE.md](breadcrumbs_GUIDE.md) - Breadcrumb trail management
- [navigation_state_GUIDE.md](navigation_state_GUIDE.md) - Navigation state tracking

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**
