# zDisplay API Layer

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**

---

## Overview

The **API layer** provides convenience methods for backward compatibility. These methods build event dictionaries and route through the `handle()` method, maintaining a clean separation between the public API and internal implementation.

**Location:** `zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/api/`

**Purpose:**
- Backward-compatible convenience methods
- Thin wrappers around event dictionaries
- Familiar imperative API
- Smooth migration path to declarative patterns

---

## Module Structure

| Module | Purpose |
|--------|---------|
| `delegate_primitives.py` | Convenience methods for I/O primitives |
| `delegate_outputs.py` | Convenience methods for output events |
| `delegate_signals.py` | Convenience methods for signal events |
| `delegate_data.py` | Convenience methods for data display |
| `delegate_system.py` | Convenience methods for system events |

---

## Design Pattern

All convenience methods follow the same pattern:

```python
# Convenience method (public API)
def success(self, content: str, indent: int = 0):
    """Display success message."""
    self.handle({
        "event": "success",
        "content": content,
        "indent": indent
    })

# Internally routes to:
# display_events.Signals.success(event_dict)
# → basic/display_basic_outputs.py renders output
# → io/display_primitives_outputs.py handles terminal/WebSocket
```

**Benefits:**
- **Backward compatibility** - Old code still works
- **Familiar API** - Imperative style for quick use
- **Internal consistency** - All routes through handle()
- **Future-proof** - Easy to add features without breaking API

---

## Primitives Delegates

From `delegate_primitives.py`:

### Output Primitives

```python
def raw(self, content: str):
    """Write text without newline."""
    self.handle({"event": "write_raw", "content": content})

def line(self, content: str):
    """Write text with newline."""
    self.handle({"event": "write_line", "content": content})

def block(self, content: str):
    """Write multi-line block."""
    self.handle({"event": "write_block", "content": content})

# Legacy aliases (backward compatible)
def write_raw(self, content: str):
    """Alias for raw()."""
    return self.raw(content)

def write_line(self, content: str):
    """Alias for line()."""
    return self.line(content)

def write_block(self, content: str):
    """Alias for block()."""
    return self.block(content)
```

### Input Primitives

```python
def read_string(self, prompt: str = "") -> str:
    """Collect text input from user."""
    return self.handle({
        "event": "read_string",
        "prompt": prompt
    })

def read_password(self, prompt: str = "Password: ") -> str:
    """Collect password input (masked)."""
    return self.handle({
        "event": "read_password",
        "prompt": prompt
    })
```

---

## Outputs Delegates

From `delegate_outputs.py`:

```python
def header(self, label: str, color: str = "CYAN", style: str = "full", indent: int = 0):
    """Display formatted header."""
    self.handle({
        "event": "header",
        "label": label,
        "color": color,
        "style": style,
        "indent": indent
    })

def text(self, content: str, indent: int = 0, pause: bool = False, color: str = None):
    """Display text with control."""
    self.handle({
        "event": "text",
        "content": content,
        "indent": indent,
        "pause": pause,
        "color": color
    })
```

---

## Signals Delegates

From `delegate_signals.py`:

```python
def success(self, content: str, indent: int = 0):
    """Display success message (green)."""
    self.handle({
        "event": "success",
        "content": content,
        "indent": indent
    })

def error(self, content: str, indent: int = 0):
    """Display error message (red)."""
    self.handle({
        "event": "error",
        "content": content,
        "indent": indent
    })

def warning(self, content: str, indent: int = 0):
    """Display warning message (yellow)."""
    self.handle({
        "event": "warning",
        "content": content,
        "indent": indent
    })

def info(self, content: str, indent: int = 0):
    """Display info message (cyan)."""
    self.handle({
        "event": "info",
        "content": content,
        "indent": indent
    })

def zMarker(self, label: str, color: str = "MAGENTA"):
    """Display workflow separator."""
    self.handle({
        "event": "zMarker",
        "label": label,
        "color": color
    })
```

---

## Data Delegates

From `delegate_data.py`:

```python
def list(self, items: list, style: str = "bullet", indent: int = 0):
    """Display formatted list."""
    self.handle({
        "event": "list",
        "items": items,
        "style": style,
        "indent": indent
    })

def outline(self, structure: list, indent: int = 0):
    """Display hierarchical outline."""
    self.handle({
        "event": "outline",
        "structure": structure,
        "indent": indent
    })

def json_data(self, data: dict, color: bool = False, indent: int = 2):
    """Display JSON with optional syntax highlighting."""
    self.handle({
        "event": "json_data",
        "data": data,
        "color": color,
        "indent": indent
    })

def zTable(self, title: str, columns: list, rows: list, limit: int = None, 
           offset: int = 0, interactive: bool = False):
    """Display table with pagination."""
    self.handle({
        "event": "zTable",
        "title": title,
        "columns": columns,
        "rows": rows,
        "limit": limit,
        "offset": offset,
        "interactive": interactive
    })
```

---

## System Delegates

From `delegate_system.py`:

```python
def zDeclare(self, label: str, color: str = "CYAN", indent: int = 0):
    """Display system announcement."""
    self.handle({
        "event": "zDeclare",
        "label": label,
        "color": color,
        "indent": indent
    })

def zSession(self, session: dict):
    """Display session state."""
    self.handle({
        "event": "zSession",
        "session": session
    })

def zConfig(self, config_data: dict):
    """Display configuration."""
    self.handle({
        "event": "zConfig",
        "config_data": config_data
    })

def zCrumbs(self, path: list, separator: str = " → "):
    """Display breadcrumb navigation."""
    self.handle({
        "event": "zCrumbs",
        "path": path,
        "separator": separator
    })

def zMenu(self, title: str, items: list, allow_back: bool = False):
    """Display interactive menu."""
    return self.handle({
        "event": "zMenu",
        "title": title,
        "items": items,
        "allow_back": allow_back
    })

def zDialog(self, title: str, message: str, buttons: list, default: str = None):
    """Display modal dialog."""
    return self.handle({
        "event": "zDialog",
        "title": title,
        "message": message,
        "buttons": buttons,
        "default": default
    })
```

---

## Migration Path

The API layer provides a smooth migration path from imperative to declarative patterns.

**Current (Imperative):**
```python
z.display.success("Operation complete")
z.display.header("Section Title", color="CYAN", style="full")
z.display.text("Content", indent=1)
```

**Future (Declarative):**
```python
z.display.handle({"event": "success", "content": "Operation complete"})
z.display.handle({"event": "header", "label": "Section Title", "color": "CYAN", "style": "full"})
z.display.handle({"event": "text", "content": "Content", "indent": 1})
```

**Both work identically** - they route through the same `handle()` method internally.

---

## Backward Compatibility

The API layer ensures backward compatibility:

**Legacy Aliases:**
```python
# Old names still work
z.display.write_raw("text")   # → raw()
z.display.write_line("text")  # → line()
z.display.write_block("text") # → block()
```

**Legacy Parameters:**
```python
# Old parameter names still work
z.display.text("Content", break_after=False)  # → pause=True
```

**Gradual Migration:**
- Old code continues to work
- New code can use event dictionaries
- No breaking changes
- Smooth transition path

---

## Usage Examples

**All API Methods:**
```python
from zOS import zOS

z = zOS()

# Primitives
z.display.raw("Loading")
z.display.line("Processing complete")
z.display.block("Line 1\nLine 2")
name = z.display.read_string("Name: ")
password = z.display.read_password("Password: ")

# Outputs
z.display.header("Section", color="CYAN", style="full")
z.display.text("Content", indent=1, pause=False)

# Signals
z.display.success("Done!")
z.display.error("Failed!")
z.display.warning("Warning!")
z.display.info("Info...")
z.display.zMarker("Stage 1")

# Data
z.display.list(["A", "B", "C"], style="bullet")
z.display.outline([{"content": "A", "children": ["B"]}])
z.display.json_data({"key": "value"}, color=True)
z.display.zTable("Users", ["id", "name"], [{"id": 1, "name": "Alice"}])

# System
z.display.zDeclare("System Ready", color="GREEN")
z.display.zSession(z.session)
z.display.zConfig(config_dict)
z.display.zCrumbs(["Home", "Settings"])
choice = z.display.zMenu("Menu", ["Option 1", "Option 2"])
result = z.display.zDialog("Title", "Message", ["OK", "Cancel"])
```

**Event Dictionary Equivalents:**
```python
# Same operations using event API
z.display.handle({"event": "write_raw", "content": "Loading"})
z.display.handle({"event": "write_line", "content": "Processing complete"})
z.display.handle({"event": "success", "content": "Done!"})
z.display.handle({"event": "header", "label": "Section", "color": "CYAN"})
z.display.handle({"event": "list", "items": ["A", "B", "C"], "style": "bullet"})
```

---

## Design Principles

**1. Thin Wrappers**
- Minimal logic in API layer
- Build event dict and call handle()
- No business logic

**2. Backward Compatibility**
- Support old method names
- Support old parameter names
- No breaking changes

**3. Consistent Patterns**
- All methods follow same pattern
- Predictable API surface
- Easy to learn and use

**4. Future-Proof**
- Event-driven architecture
- Declarative patterns ready
- Smooth migration path

---

## What's Next

The API layer provides convenience methods. Complete your knowledge with:

- **[Utils Layer →](utils_GUIDE.md)** - Pure utilities and helpers

---

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**
