# zDisplay Basic Layer

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**

---

## Overview

The **Basic layer** provides core event logic and formatting that all other display layers build upon. This layer handles output rendering, input collection, semantic colors, and JSON formatting.

**Location:** `zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/basic/`

**Purpose:**
- Core output event logic (text, headers, signals)
- Core input event logic (boolean confirmation)
- Semantic color mapping and constants
- Rendering utilities (indentation, line wrapping)
- JSON formatting and syntax highlighting

---

## Module Structure

| Module | Purpose |
|--------|---------|
| `display_basic_outputs.py` | Core output event logic |
| `display_basic_inputs.py` | Core input event logic |
| `outputs/semantic_colors.py` | Color constants and semantic mapping |
| `outputs/rendering_utilities.py` | Output rendering helpers |
| `outputs/json_renderer.py` | JSON formatting and syntax highlighting |
| `inputs/boolean_input.py` | Yes/no confirmation logic |

---

## Output Events

### text() - Display with Control

Display text with indentation and pause control.

**Parameters:**
- `content` (str): Text to display
- `indent` (int): Indentation level (0-3+, 2 spaces each)
- `pause` (bool): Wait for user to press Enter
- `color` (str): Optional color name

**Example:**
```python
z.display.text("Configuration:", indent=0)
z.display.text("Database: PostgreSQL", indent=1)
z.display.text("Host: localhost", indent=2)
z.display.text("Press Enter to continue", pause=True)
```

**Implementation:** `display_basic_outputs.py`

---

### header() - Formatted Headers

Create visual structure with formatted section headers.

**Parameters:**
- `label` (str): Header text
- `color` (str): Color name (CYAN, GREEN, YELLOW, MAGENTA, BLUE, RED)
- `style` (str): Border style (full=═, single=─, wave=~)
- `indent` (int): Indentation level

**Example:**
```python
z.display.header("System Initialization", color="CYAN", style="full")
z.display.header("Loading Configuration", color="GREEN", style="single")
z.display.header("Processing Data", color="YELLOW", style="wave")
```

**Implementation:** `display_basic_outputs.py`

---

## Signal Events

### success() - Green Confirmation

Display success message with green color and [ok] indicator.

**Example:**
```python
z.display.success("Operation completed successfully")
z.display.success("Database connected", indent=1)
```

---

### error() - Red Failure

Display error message with red color and ✗ indicator.

**Example:**
```python
z.display.error("Connection failed")
z.display.error("Invalid credentials", indent=1)
```

---

### warning() - Yellow Caution

Display warning message with yellow color and ⚠ indicator.

**Example:**
```python
z.display.warning("Deprecated feature in use")
z.display.warning("Low disk space", indent=1)
```

---

### info() - Cyan Information

Display info message with cyan color and ℹ indicator.

**Example:**
```python
z.display.info("Processing 10 records...")
z.display.info("Host: localhost", indent=1)
```

---

### zMarker() - Workflow Separator

Visual separator for workflow stages.

**Example:**
```python
z.display.zMarker("Checkpoint 1")
z.display.info("Stage 1 complete")
z.display.zMarker("Checkpoint 2", color="CYAN")
```

**Implementation:** All signals in `display_basic_outputs.py`

---

## Semantic Colors

The basic layer defines semantic color mapping for consistent styling.

**Color Constants:**
```python
# From outputs/semantic_colors.py
COLOR_SUCCESS = "GREEN"
COLOR_ERROR = "RED"
COLOR_WARNING = "YELLOW"
COLOR_INFO = "CYAN"
COLOR_MARKER = "MAGENTA"
COLOR_SYSTEM = "BLUE"
```

**Semantic Mapping:**
- **Success** → Green → [ok] indicator
- **Error** → Red → ✗ indicator
- **Warning** → Yellow → ⚠ indicator
- **Info** → Cyan → ℹ indicator
- **Marker** → Magenta → Workflow separator
- **System** → Blue → System events

**Usage:**
```python
# Colors are applied automatically based on event type
z.display.success("Done!")  # Automatically green
z.display.error("Failed!")  # Automatically red
```

---

## Rendering Utilities

The basic layer provides rendering helpers for consistent formatting.

**Indentation:**
```python
# From outputs/rendering_utilities.py
def apply_indent(text: str, indent: int) -> str:
    """Apply indentation (2 spaces per level)."""
    spaces = "  " * indent
    return f"{spaces}{text}"
```

**Line Wrapping:**
```python
def wrap_text(text: str, width: int, indent: int = 0) -> str:
    """Wrap text to specified width with indentation."""
    # Implementation handles word boundaries
    # Preserves indentation on wrapped lines
```

**Border Generation:**
```python
def generate_border(width: int, style: str) -> str:
    """Generate border line for headers."""
    if style == "full":
        return "═" * width
    elif style == "single":
        return "─" * width
    elif style == "wave":
        return "~" * width
```

**Implementation:** `outputs/rendering_utilities.py`

---

## JSON Formatting

The basic layer provides JSON rendering with syntax highlighting.

**JSON Renderer:**
```python
# From outputs/json_renderer.py
def format_json(data: dict, color: bool = False, indent: int = 2) -> str:
    """Format JSON with optional syntax highlighting."""
    if color:
        # Apply ANSI color codes:
        # - Keys: cyan
        # - Strings: green
        # - Numbers: yellow
        # - Booleans: magenta
        # - Null: red
    else:
        # Plain formatting
    return formatted_json
```

**Usage:**
```python
config = {"version": "1.5.5", "mode": "zCLI", "ready": True}
z.display.json_data(config, color=True)
```

**Implementation:** `outputs/json_renderer.py`

---

## Input Events

### button() - Boolean Confirmation

Action confirmation with yes/no prompts.

**Parameters:**
- `label` (str): Button label/question
- `color` (str): Color type (success, danger, warning, info)

**Returns:** `True` (confirmed) or `False` (cancelled)

**Example:**
```python
if z.display.button("Save Profile", color="success"):
    z.display.success("Profile saved!")
else:
    z.display.info("Profile not saved")

if z.display.button("Delete Account", color="danger"):
    z.display.warning("Account marked for deletion!")
```

**Color Mapping:**
- `success` → Green → Safe action
- `danger` → Red → Destructive action
- `warning` → Yellow → Caution required
- `info` → Blue → Informational

**Implementation:** `inputs/boolean_input.py`

---

## Design Principles

**1. Foundation Layer**
- Provides core logic for all display operations
- All higher layers build on basic events
- No dependencies on compounds/advanced layers

**2. Semantic Consistency**
- Colors map to meaning (success=green, error=red)
- Indicators reinforce message type ([ok], ✗, ⚠, ℹ)
- Consistent styling across all events

**3. Rendering Helpers**
- Reusable utilities for formatting
- Consistent indentation (2 spaces per level)
- Border generation for headers
- Line wrapping with word boundaries

**4. JSON Support**
- Syntax highlighting for readability
- Configurable indentation
- Color-coded by data type

---

## Usage Examples

**Text Output:**
```python
# Simple text
z.display.text("Hello World!")

# With indentation
z.display.text("Main Section", indent=0)
z.display.text("Subsection", indent=1)
z.display.text("Detail", indent=2)

# With pause
z.display.text("Press Enter to continue", pause=True)
```

**Headers:**
```python
# Full border (═══)
z.display.header("System Initialization", color="CYAN", style="full")

# Single border (───)
z.display.header("Loading Configuration", color="GREEN", style="single")

# Wave border (~~~)
z.display.header("Processing Data", color="YELLOW", style="wave")
```

**Signals:**
```python
# Success (green)
z.display.success("Operation complete")

# Error (red)
z.display.error("Connection failed")

# Warning (yellow)
z.display.warning("Low disk space")

# Info (cyan)
z.display.info("Processing...")

# Marker (magenta)
z.display.zMarker("Checkpoint 1")
```

**JSON Display:**
```python
config = {
    "version": "1.5.5",
    "mode": "zCLI",
    "ready": True,
    "features": ["display", "auth", "data"]
}

# With syntax highlighting
z.display.json_data(config, color=True)

# Plain formatting
z.display.json_data(config, color=False)
```

**Boolean Confirmation:**
```python
# Safe action
if z.display.button("Save Changes", color="success"):
    save_changes()

# Dangerous action
if z.display.button("Delete All", color="danger"):
    delete_all()

# Warning action
if z.display.button("Proceed Anyway", color="warning"):
    proceed()
```

---

## What's Next

The basic layer provides core logic. Build on it with:

- **[Compounds Layer →](compounds_GUIDE.md)** - Complex interactive widgets
- **[Advanced Layer →](advanced_GUIDE.md)** - Specialized components
- **[System Layer →](system_GUIDE.md)** - System UI events

---

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**
