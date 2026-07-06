# zDisplay Advanced Layer

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**

---

## Overview

The **Advanced layer** provides specialized components including markdown rendering, progress tracking, spinners, tables with pagination, and interactive slideshows.

**Location:** `zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/advanced/`

**Purpose:**
- Markdown rendering with syntax highlighting
- Progress bars (deterministic and indeterminate)
- Table display with three pagination modes
- Interactive slideshow carousel
- Time-based animations

---

## Module Structure

| Module | Purpose |
|--------|---------|
| `display_event_advanced.py` | Advanced display events orchestration |
| `display_event_outputs.py` | Advanced output events |
| `display_event_timebased.py` | Time-based events (progress, spinner, swiper) |
| `advanced_table.py` | Table rendering with pagination |
| `advanced_pagination.py` | Pagination logic |
| `timebased_progress.py` | Progress bar implementation |
| `timebased_spinner.py` | Spinner animation |
| `timebased_swiper.py` | Slideshow carousel |
| `timebased_utilities.py` | Time-based utilities |
| `event_id_utils.py` | Event ID generation |
| `markdown/` | Markdown rendering subsystem (8 modules) |

---

## Table Display

### zTable() - Advanced Tables with Pagination

Display tables with three pagination modes: basic (no pagination), simple truncation, and interactive navigation.

**Parameters:**
- `title` (str): Table title
- `columns` (list): Column names
- `rows` (list): List of dicts (one per row)
- `limit` (int): Rows per page (optional)
- `offset` (int): Starting row (optional)
- `interactive` (bool): Enable keyboard navigation (default: False)

**Three Pagination Modes:**

**Type 1: Basic (No Pagination)**
```python
users = [
    {"ID": 1, "Name": "Alice", "Email": "alice@example.com"},
    {"ID": 2, "Name": "Bob", "Email": "bob@example.com"},
    {"ID": 3, "Name": "Charlie", "Email": "charlie@example.com"},
]

z.display.zTable(
    title="All Users",
    columns=["ID", "Name", "Email"],
    rows=users
)
# Shows all rows, no pagination
```

**Type 2: Simple Truncation**
```python
z.display.zTable(
    title="Users (Limited)",
    columns=["ID", "Name", "Email"],
    rows=users,
    limit=2  # Shows first 2 rows + "... N more rows" footer
)
```

**Type 3: Interactive Navigation**
```python
z.display.zTable(
    title="Users - Interactive",
    columns=["ID", "Name", "Email"],
    rows=users,
    limit=2,
    offset=0,
    interactive=True  # Keyboard controls: [n]ext, [p]revious, [f]irst, [l]ast, [#] jump, [q]uit
)
```

**Implementation:** `advanced_table.py` + `advanced_pagination.py`

---

## Progress Tracking

### progress_bar() - Deterministic Progress

Visual progress tracking with percentage and ETA.

**Parameters:**
- `current` (int): Current progress value
- `total` (int): Total progress value
- `label` (str): Progress label
- `show_percentage` (bool): Show percentage (default: True)
- `show_eta` (bool): Show estimated time (default: True)
- `start_time` (float): Start timestamp for ETA calculation
- `color` (str): Progress bar color

**Example:**
```python
import time

total = 100
start_time = time.time()

for i in range(total + 1):
    z.display.progress_bar(
        current=i,
        total=total,
        label="Processing files",
        show_percentage=True,
        show_eta=True,
        start_time=start_time,
        color="GREEN"
    )
    time.sleep(0.05)
```

**Implementation:** `timebased_progress.py`

---

### progress_iterator() - Automatic Progress

Wrapper for iterables with automatic progress tracking.

**Parameters:**
- `iterable` (iterable): Items to iterate over
- `label` (str): Progress label
- `color` (str): Progress bar color

**Example:**
```python
files = [f"file_{i}.txt" for i in range(1, 26)]

for filename in z.display.progress_iterator(files, "Processing files"):
    process_file(filename)  # progress_iterator manages counters automatically
```

**Implementation:** `timebased_progress.py`

---

### spinner() - Indeterminate Progress (Context Manager)

Animated loading indicator with automatic animation.

**Parameters:**
- `label` (str): Spinner label
- `style` (str): Animation style (dots, arc, line, etc.)

**Example:**
```python
with z.display.spinner("Loading data", style="dots"):
    time.sleep(2)  # Animates automatically in background

with z.display.spinner("Processing", style="arc"):
    fetch_data()
```

**Implementation:** `timebased_spinner.py`

---

### indeterminate_progress() - Manual Spinner Control

Returns an update function for fine-grained control over spinner frames.

**Parameters:**
- `label` (str): Spinner label
- `style` (str): Animation style

**Returns:** Update function to call in your loop

**Example:**
```python
update_progress = z.display.indeterminate_progress("Processing data")
for i in range(30):
    update_progress()  # You control when frames update
    time.sleep(0.1)
z.display.raw("\n")  # Add newline when done
```

**Implementation:** `timebased_spinner.py`

---

## Interactive Slideshow

### swiper() - Carousel with Navigation

Interactive content carousel with auto-advance or manual navigation.

**Parameters:**
- `slides` (list): List of slide content (strings)
- `title` (str): Slideshow title
- `auto_advance` (bool): Auto-advance slides (default: False)
- `delay` (int): Delay between slides in seconds (auto-advance only)

**Keyboard Controls:**
- `→` / `n` - Next slide
- `←` / `p` - Previous slide
- `f` - First slide
- `l` - Last slide
- `1-9` - Jump to slide number
- `p` - Pause/resume (auto-advance mode)
- `q` - Quit

**Example:**
```python
# Auto-advancing slideshow
intro_slides = [
    "Welcome to zOS!",
    "zOS is a declarative CLI framework",
    "Professional terminal UI with one API",
    "Let's explore the features..."
]

z.display.zEvents.TimeBased.swiper(
    intro_slides, 
    "Introduction", 
    auto_advance=True, 
    delay=3
)

# Manual navigation
tutorial_slides = [
    "Step 1: Initialize zOS\n\n  from zOS import zOS\n  z = zOS()",
    "Step 2: Display Progress\n\n  z.display.progress_bar(50, 100)",
    "Step 3: Show Spinners\n\n  with z.display.spinner('Loading'):\n      time.sleep(2)"
]

z.display.zEvents.TimeBased.swiper(
    tutorial_slides, 
    "Tutorial", 
    auto_advance=False
)
```

**Implementation:** `timebased_swiper.py`

---

## Markdown Rendering

The advanced layer includes a complete markdown rendering subsystem.

**Markdown Modules:**
- `markdown_processor.py` - Main markdown processor
- `markdown_parser.py` - Markdown parsing
- `block_extractor.py` - Block-level element extraction
- `inline_transformer.py` - Inline element transformation
- `html_processor.py` - HTML tag processing
- `rich_text_renderer.py` - Rich text rendering
- `semantic_renderers.py` - Semantic element rendering
- `syntax_highlighter.py` - Code syntax highlighting

**Features:**
- Headers (H1-H6)
- Bold, italic, strikethrough
- Code blocks with syntax highlighting
- Inline code
- Lists (ordered, unordered)
- Links
- Blockquotes
- Horizontal rules
- Tables

**Usage:**
```python
markdown_text = """
# Welcome to zOS

zOS is a **declarative CLI framework** with:

- Professional terminal UI
- Multi-mode support (Terminal + Browser)
- Event-driven architecture

## Code Example

```python
from zOS import zOS
z = zOS()
z.display.success("Hello World!")
```

Visit [documentation](https://docs.zos.ai) for more.
"""

z.display.markdown(markdown_text)
```

**Implementation:** `markdown/` subsystem

---

## Design Principles

**1. Specialized Components**
- Advanced features beyond basic/compounds
- Production-ready table display
- Professional progress indicators
- Rich markdown rendering

**2. Time-Based Animations**
- Smooth progress bars
- Animated spinners
- Interactive slideshows
- Cross-terminal compatibility

**3. Pagination Strategies**
- Basic: No pagination (show all)
- Simple: Truncation with footer
- Interactive: Full keyboard navigation

**4. Performance**
- Efficient rendering
- Minimal redraws
- Optimized for large datasets

---

## Usage Examples

**Tables:**
```python
# Database query results
users = fetch_users_from_db()

# Basic table (all rows)
z.display.zTable(
    title="All Users",
    columns=["id", "name", "email", "role"],
    rows=users
)

# Limited display
z.display.zTable(
    title="Recent Users",
    columns=["id", "name", "email"],
    rows=users,
    limit=10
)

# Interactive navigation
z.display.zTable(
    title="Users - Navigate",
    columns=["id", "name", "email", "role", "created_at"],
    rows=users,
    limit=5,
    offset=0,
    interactive=True
)
```

**Progress Bars:**
```python
import time

# Manual control
total = 100
start = time.time()

for i in range(total + 1):
    z.display.progress_bar(
        current=i,
        total=total,
        label="Processing",
        show_percentage=True,
        show_eta=True,
        start_time=start,
        color="CYAN"
    )
    time.sleep(0.02)

# Automatic wrapper
files = ["file1.txt", "file2.txt", "file3.txt"]
for file in z.display.progress_iterator(files, "Processing files"):
    process_file(file)
```

**Spinners:**
```python
# Context manager (automatic)
with z.display.spinner("Loading data", style="dots"):
    data = fetch_data()

with z.display.spinner("Building index", style="arc"):
    build_index()

# Manual control
update = z.display.indeterminate_progress("Compiling")
for i in range(50):
    update()
    time.sleep(0.1)
z.display.raw("\n")
```

**Slideshow:**
```python
# Onboarding flow
onboarding = [
    "Welcome to MyApp!\n\nLet's get you started.",
    "Feature 1: Fast Processing\n\nProcess data in seconds.",
    "Feature 2: Easy Integration\n\nOne-line setup.",
    "Feature 3: Multi-Mode\n\nTerminal or Browser.",
    "Ready to begin?\n\nPress 'q' to exit."
]

z.display.zEvents.TimeBased.swiper(
    onboarding,
    "Onboarding",
    auto_advance=True,
    delay=4
)

# Tutorial
tutorial = [
    "Step 1: Install\n\n  pip install zolo-zcli",
    "Step 2: Import\n\n  from zOS import zOS",
    "Step 3: Initialize\n\n  z = zOS()",
    "Step 4: Display\n\n  z.display.success('Hello!')"
]

z.display.zEvents.TimeBased.swiper(
    tutorial,
    "Quick Start",
    auto_advance=False
)
```

**Markdown:**
```python
readme = """
# Project Documentation

## Overview

This project provides **professional CLI tools** with:

1. Display system
2. Authentication
3. Data management

## Quick Start

```python
from zOS import zOS
z = zOS()
z.display.header("Welcome", color="CYAN")
```

## Links

- [Documentation](https://docs.zos.ai)
- [GitHub](https://github.com/ZoloAi/zolo-zcli)
"""

z.display.markdown(readme)
```

---

## What's Next

The advanced layer provides specialized components. Complete your knowledge with:

- **[System Layer →](system_GUIDE.md)** - System UI events (menus, dialogs, navigation)
- **[API Layer →](api_GUIDE.md)** - Convenience methods and backward compatibility

---

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**
