# zDisplay Compounds Layer

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**

---

## Overview

The **Compounds layer** provides complex interactive widgets built on the basic layer. This includes selection menus, media handling, link interactions, and slider widgets.

**Location:** `zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/compounds/`

**Purpose:**
- Complex interactive widgets (selection, buttons, links)
- Input validation and collection
- Media display events
- Multi-step input flows

---

## Module Structure

| Module | Purpose |
|--------|---------|
| `display_compounds_outputs.py` | Complex output widgets |
| `display_compounds_inputs.py` | Complex input widgets |
| `inputs/selection_collector.py` | Selection menu logic |
| `inputs/selection_renderer.py` | Selection menu rendering |
| `inputs/input_validators.py` | Input validation utilities |
| `inputs/link_handler.py` | Link interaction handling |
| `inputs/slider_widget.py` | Slider input widget |
| `outputs/display_event_data.py` | Data structure rendering (list, outline) |
| `outputs/display_event_links.py` | Link display events |

---

## Selection Events

### selection() - Choose from List

User choice from numbered list with single or multi-select.

**Parameters:**
- `prompt` (str): Selection prompt
- `options` (list): List of options to choose from
- `multi` (bool): Allow multiple selections (default: False)
- `default` (str/list): Default selection(s)

**Returns:** Single item (str) or list of items (multi=True)

**Example:**
```python
# Single selection
role = z.display.selection(
    "Select your role:",
    ["Developer", "Designer", "Manager"]
)
z.display.success(f"Selected: {role}")

# Multiple selections
skills = z.display.selection(
    "Select your skills:",
    ["Python", "JavaScript", "React", "Django"],
    multi=True
)
z.display.success(f"Selected: {', '.join(skills)}")

# With default
theme = z.display.selection(
    "Choose theme:",
    ["Light", "Dark", "Auto"],
    default="Dark"
)
```

**Implementation:** `inputs/selection_collector.py` + `inputs/selection_renderer.py`

---

## Data Display Events

### list() - Bullet/Number/Letter Lists

Display items as formatted lists with different styles.

**Parameters:**
- `items` (list): List of items to display
- `style` (str): List style (bullet, number, letter)
- `indent` (int): Indentation level

**Example:**
```python
# Bullet list (•)
z.display.list(["Fast", "Simple", "Multi-mode"], style="bullet")

# Numbered list (1, 2, 3)
z.display.list(["Initialize", "Configure", "Deploy"], style="number")

# Letter list (a, b, c)
z.display.list(["Option A", "Option B", "Option C"], style="letter")
```

**Implementation:** `outputs/display_event_data.py`

---

### outline() - Hierarchical Display

Display nested structures with hierarchical numbering (1→a→i→•).

**Parameters:**
- `structure` (list): Nested list/dict structure
- `indent` (int): Base indentation level

**Example:**
```python
z.display.outline([
    {
        "content": "Backend Architecture",
        "children": [
            {
                "content": "Python Runtime",
                "children": ["zOS initialization", "Event handling"]
            },
            "Data Processing Layer"
        ]
    },
    {
        "content": "Frontend Architecture",
        "children": ["Rendering Engine", "User Interaction"]
    }
])
```

**Output:**
```
1. Backend Architecture
   a. Python Runtime
      i. zOS initialization
      ii. Event handling
   b. Data Processing Layer
2. Frontend Architecture
   a. Rendering Engine
   b. User Interaction
```

**Implementation:** `outputs/display_event_data.py`

---

## Link Events

### link() - Display Clickable Links

Display links with optional descriptions (Terminal: plain text, Browser: clickable).

**Parameters:**
- `url` (str): Link URL
- `label` (str): Link label/text
- `description` (str): Optional description

**Example:**
```python
z.display.link(
    url="https://docs.zos.ai",
    label="Documentation",
    description="Complete zOS documentation"
)
```

**Implementation:** `outputs/display_event_links.py`

---

## Input Validation

The compounds layer provides input validation utilities.

**Validators:**
```python
# From inputs/input_validators.py

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_number(value: str, min_val=None, max_val=None) -> bool:
    """Validate numeric input with optional range."""
    try:
        num = float(value)
        if min_val is not None and num < min_val:
            return False
        if max_val is not None and num > max_val:
            return False
        return True
    except ValueError:
        return False

def validate_choice(value: str, options: list) -> bool:
    """Validate choice is in options list."""
    return value in options
```

**Usage:**
```python
email = z.display.read_string("Email: ")
while not validate_email(email):
    z.display.error("Invalid email format")
    email = z.display.read_string("Email: ")
```

---

## Slider Widget

Interactive slider for numeric input (Terminal: text-based, Browser: visual slider).

**Parameters:**
- `label` (str): Slider label
- `min_val` (int/float): Minimum value
- `max_val` (int/float): Maximum value
- `default` (int/float): Default value
- `step` (int/float): Step increment

**Example:**
```python
volume = z.display.slider(
    label="Volume",
    min_val=0,
    max_val=100,
    default=50,
    step=5
)
z.display.success(f"Volume set to: {volume}")
```

**Implementation:** `inputs/slider_widget.py`

---

## Design Principles

**1. Built on Basic Layer**
- Uses basic events for rendering
- Composes simple events into complex widgets
- No direct I/O layer access

**2. Input Validation**
- Reusable validation utilities
- Consistent error handling
- Type-safe input collection

**3. Multi-Mode Support**
- Terminal: Text-based interactions
- Browser: Rich UI components
- Same API for both modes

**4. Progressive Enhancement**
- Basic functionality in Terminal
- Enhanced UI in Browser
- Graceful degradation

---

## Usage Examples

**Selection Menu:**
```python
# Single selection
role = z.display.selection(
    "Select your role:",
    ["Developer", "Designer", "Manager", "Admin"]
)

# Multi-selection
languages = z.display.selection(
    "Select languages you know:",
    ["Python", "JavaScript", "Go", "Rust", "Java"],
    multi=True
)

# With default
editor = z.display.selection(
    "Choose your editor:",
    ["Cursor", "VS Code", "Vim", "Emacs"],
    default="Cursor"
)
```

**Lists:**
```python
# Bullet list
features = ["Fast", "Simple", "Powerful", "Declarative"]
z.display.list(features, style="bullet")

# Numbered steps
steps = ["Initialize", "Configure", "Deploy", "Monitor"]
z.display.list(steps, style="number")

# Letter options
options = ["Option A", "Option B", "Option C"]
z.display.list(options, style="letter")
```

**Outline:**
```python
architecture = [
    {
        "content": "Frontend",
        "children": [
            "React Components",
            {
                "content": "State Management",
                "children": ["Redux", "Context API"]
            }
        ]
    },
    {
        "content": "Backend",
        "children": ["API Routes", "Database", "Authentication"]
    }
]
z.display.outline(architecture)
```

**Links:**
```python
z.display.link(
    url="https://github.com/ZoloAi/zolo-zcli",
    label="GitHub Repository",
    description="Source code and examples"
)

z.display.link(
    url="https://docs.zos.ai",
    label="Documentation"
)
```

**Input Validation:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.compounds.inputs.input_validators import (
    validate_email,
    validate_number,
    validate_choice
)

# Email validation
email = z.display.read_string("Email: ")
while not validate_email(email):
    z.display.error("Invalid email format")
    email = z.display.read_string("Email: ")

# Number validation
age = z.display.read_string("Age (18-120): ")
while not validate_number(age, min_val=18, max_val=120):
    z.display.error("Age must be between 18 and 120")
    age = z.display.read_string("Age (18-120): ")

# Choice validation
role = z.display.read_string("Role (admin/user): ")
while not validate_choice(role, ["admin", "user"]):
    z.display.error("Role must be 'admin' or 'user'")
    role = z.display.read_string("Role (admin/user): ")
```

**Slider:**
```python
# Volume control
volume = z.display.slider("Volume", 0, 100, default=50, step=5)

# Temperature
temp = z.display.slider("Temperature", 60, 80, default=72, step=1)

# Opacity
opacity = z.display.slider("Opacity", 0.0, 1.0, default=1.0, step=0.1)
```

---

## What's Next

The compounds layer provides complex widgets. Build on it with:

- **[Advanced Layer →](advanced_GUIDE.md)** - Specialized components (tables, progress, markdown)
- **[System Layer →](system_GUIDE.md)** - System UI events (menus, dialogs)

---

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**
