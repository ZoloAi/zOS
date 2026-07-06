# Menu System Module

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**

---

## Overview

The Menu System module provides comprehensive menu creation, rendering, and interaction functionality. It orchestrates three specialized components (MenuBuilder, MenuRenderer, MenuInteraction) to deliver a complete menu experience.

**Module:** `navigation_modules/menu/navigation_menu_system.py`

## Purpose

- **Menu Creation**: Build menus from various sources (static, dynamic, functions)
- **Menu Rendering**: Display menus in multiple formats (full, simple, compact)
- **User Interaction**: Handle single/multi-select and search functionality
- **Breadcrumb Integration**: Automatic breadcrumb management for navigation

## Architecture

The Menu System follows a **composition pattern** with three specialized components:

```
MenuSystem (Orchestrator)
  ├─→ MenuBuilder (Construction)
  ├─→ MenuRenderer (Display)
  └─→ MenuInteraction (Input)
```

**Key Responsibilities:**
- MenuBuilder: Construct menu objects from various sources
- MenuRenderer: Render menus in different formats
- MenuInteraction: Handle user input and validation

## Public API

### create()

Create and display a navigation menu with full breadcrumb integration.

```python
choice = z.cli.navigation.create(
    options=["Settings", "Profile", "Logout"],
    title="Main Menu",
    allow_back=True,
    walker=walker
)
```

**Parameters:**
- `options` (list|callable): Menu options or function that returns options
- `title` (str): Menu title (optional)
- `allow_back` (bool): Add automatic "Back" option (default: False)
- `walker` (Walker): Walker instance for orchestration

**Returns:** Selected option (str) or "Back"

---

### select()

Simple option selection without breadcrumb integration.

```python
choice = z.cli.navigation.select(
    options=["Option A", "Option B", "Option C"],
    prompt="Choose an option:",
    walker=walker
)
```

**Parameters:**
- `options` (list): Menu options
- `prompt` (str): Selection prompt
- `walker` (Walker): Walker instance

**Returns:** Selected option (str)

---

## Component Details

### MenuBuilder

Constructs menu objects from various sources:

**Supported Formats:**
- **Static lists**: `["A", "B", "C"]`
- **Dictionary options**: `[{"label": "A", "value": "a"}, ...]`
- **Function-based**: `lambda: fetch_options()`
- **zFunc integration**: Dynamic menu generation

**Features:**
- "Back" option injection management
- Option validation and normalization
- Integration with zFunc for dynamic menus

---

### MenuRenderer

Handles menu presentation with multiple display formats:

**Display Formats:**
- **full**: Complete with descriptions and metadata
- **simple**: Clean numbered list (default)
- **compact**: Minimal spacing

**Features:**
- Mode-agnostic rendering (zCLI/Bifrost)
- Breadcrumb integration in display
- zDisplay delegation for output

---

### MenuInteraction

Manages user input and validation:

**Interaction Types:**
- **Single choice**: Select one option by number
- **Multiple choices**: Space-separated numbers
- **Search**: Filter options by text

**Features:**
- Input validation and error handling
- Search functionality for large menus
- zDisplay delegation for input

---

## Usage Examples

### Static Menu

```python
# Simple static menu
options = ["Settings", "Profile", "Logout"]
choice = z.cli.navigation.create(options, title="Main Menu", walker=walker)
```

### Dynamic Menu from Function

```python
def get_users():
    """Fetch users from database."""
    return ["Alice", "Bob", "Charlie"]

# Menu options generated when displayed
choice = z.cli.navigation.create(get_users, title="Select User", walker=walker)
```

### Multi-Select Menu

```python
# Allow multiple selections
selected = z.cli.navigation.select(
    ["Feature A", "Feature B", "Feature C"],
    prompt="Select features (space-separated):",
    walker=walker
)
```

### Menu with Search

```python
# Large menu with search enabled
choice = z.cli.navigation.create(
    large_option_list,
    title="Search Menu",
    enable_search=True,
    walker=walker
)
```

### Custom Display Format

```python
# Menu with descriptions (full format)
options = [
    {"label": "Settings", "description": "Configure app settings"},
    {"label": "Profile", "description": "Edit your profile"},
]

choice = z.cli.navigation.create(
    options,
    title="Full Menu",
    display_format="full",
    walker=walker
)
```

---

## Integration Points

**Depends on:**
- zDisplay: Menu rendering and user input
- zFunc: Dynamic menu generation
- zSession: Breadcrumb storage

**Used by:**
- zWalker: UI file orchestration
- zDispatch: Menu modifier (`*` prefix)
- User applications: Direct menu creation

---

## Related Modules

- [breadcrumbs_GUIDE.md](breadcrumbs_GUIDE.md) - Breadcrumb trail management
- [navigation_state_GUIDE.md](navigation_state_GUIDE.md) - Navigation state tracking

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**
