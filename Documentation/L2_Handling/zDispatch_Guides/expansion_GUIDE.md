**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**

---

# Expansion System

**Expansion modules** transform shorthand notation into full command structures, reducing verbosity in UI-heavy and data-driven applications.

## Overview

Expansion handles three categories:

| Module | Purpose | Examples |
|--------|---------|----------|
| **ShorthandExpander** | UI element shorthands | zTerminal, zImage, zVideo |
| **OrganizationalHandler** | Hierarchical structures | Nested dicts with auto-expansion |
| **PluralExpander** | Collection shorthands | zItems, zTables, zForms |

---

## ShorthandExpander

**Expands UI element shorthands to full zDisplay event structures.**

### Purpose

Reduce verbosity for common UI elements by recognizing special keys and expanding them automatically.

### Supported Shorthands

```python
UI_ELEMENT_KEYS = [
    "zTerminal",    # Terminal command execution
    "zImage",       # Image display
    "zVideo",       # Video playback
    "zAudio",       # Audio playback
    "zCode",        # Code block display
    "zMarkdown",    # Markdown rendering
    "zChart",       # Chart/graph display
    "zTable",       # Table display
    "zForm",        # Form display
]
```

### Examples

#### zTerminal Shorthand

```python
# Shorthand
command = {
    "zTerminal": {
        "command": "ls -la",
        "capture": True
    }
}

# Expands to
{
    "zDisplay": {
        "event": "terminal",
        "data": {
            "command": "ls -la",
            "capture": True
        }
    }
}
```

#### zImage Shorthand

```python
# Shorthand
command = {
    "zImage": {
        "path": "logo.png",
        "width": 200
    }
}

# Expands to
{
    "zDisplay": {
        "event": "image",
        "data": {
            "path": "logo.png",
            "width": 200
        }
    }
}
```

#### zCode Shorthand

```python
# Shorthand
command = {
    "zCode": {
        "language": "python",
        "content": "def hello():\n    print('Hello')"
    }
}

# Expands to
{
    "zDisplay": {
        "event": "code",
        "data": {
            "language": "python",
            "content": "def hello():\n    print('Hello')"
        }
    }
}
```

### Implementation

```python
class ShorthandExpander:
    UI_ELEMENT_KEYS = ["zTerminal", "zImage", "zVideo", ...]
    
    def expand_ui_element(self, key, value):
        """Expand UI element shorthand to full zDisplay structure."""
        if key in self.UI_ELEMENT_KEYS:
            event_type = key.replace("z", "").lower()  # zTerminal → terminal
            return {
                "zDisplay": {
                    "event": event_type,
                    "data": value
                }
            }
        return {key: value}
    
    def expand_dict(self, horizontal):
        """Recursively expand all UI elements in dict."""
        if not isinstance(horizontal, dict):
            return horizontal
        
        expanded = {}
        for key, value in horizontal.items():
            if key in self.UI_ELEMENT_KEYS:
                expanded.update(self.expand_ui_element(key, value))
            else:
                expanded[key] = self.expand_dict(value) if isinstance(value, dict) else value
        
        return expanded
```

### Usage

```python
# Automatic expansion in CommandLauncher
clean_key = zKey.split('__dup')[0] if '__dup' in zKey else zKey

if clean_key in ShorthandExpander.UI_ELEMENT_KEYS and isinstance(zHorizontal, dict):
    # Wrap key-value so expansion can see the key
    wrapped = {zKey: zHorizontal}
    result = launcher.launch(wrapped, context=context, walker=walker)
```

---

## OrganizationalHandler

**Handles hierarchical and nested command structures with auto-expansion.**

### Purpose

Support complex organizational patterns where commands are nested in hierarchical structures.

### Patterns

#### Nested Commands

```python
# Organizational structure
command = {
    "section1": {
        "subsection1": {
            "zFunc": "action1"
        },
        "subsection2": {
            "zFunc": "action2"
        }
    },
    "section2": {
        "zData": {
            "action": "read",
            "model": "users"
        }
    }
}
```

#### Hierarchical Expansion

```python
# Expands to flat execution sequence
[
    {"zFunc": "action1"},
    {"zFunc": "action2"},
    {"zData": {"action": "read", "model": "users"}}
]
```

### Implementation

```python
class OrganizationalHandler:
    def __init__(self, shorthand_expander, logger):
        self.shorthand_expander = shorthand_expander
        self.logger = logger
    
    def expand_hierarchical(self, horizontal):
        """Recursively expand hierarchical structures."""
        if not isinstance(horizontal, dict):
            return horizontal
        
        # Check if this level has command keys
        has_command = any(k in COMMAND_KEYS for k in horizontal.keys())
        
        if has_command:
            # This is a command level - expand shorthands
            return self.shorthand_expander.expand_dict(horizontal)
        else:
            # This is organizational level - recurse
            expanded = {}
            for key, value in horizontal.items():
                expanded[key] = self.expand_hierarchical(value)
            return expanded
```

### Use Cases

- **Multi-section forms**: Grouped form fields
- **Wizard steps**: Nested step definitions
- **Menu hierarchies**: Multi-level menu structures
- **Configuration**: Nested config with commands

---

## PluralExpander

**Expands plural collection keys to proper list handling.**

### Purpose

Handle collections (arrays of items) with special plural keys that expand to list operations.

### Supported Plurals

```python
PLURAL_KEYS = [
    "zItems",       # Array of items
    "zTables",      # Array of table defs
    "zForms",       # Array of form defs
    "zUsers",       # Array of user records
    "zProducts",    # Array of product records
]
```

### Examples

#### zItems Expansion

```python
# Shorthand
command = {
    "zItems": [
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"},
        {"id": 3, "name": "Item 3"}
    ]
}

# Expands to
{
    "zDisplay": {
        "event": "list",
        "data": {
            "items": [
                {"id": 1, "name": "Item 1"},
                {"id": 2, "name": "Item 2"},
                {"id": 3, "name": "Item 3"}
            ]
        }
    }
}
```

#### zTables Expansion

```python
# Shorthand
command = {
    "zTables": [
        {
            "name": "Users",
            "columns": ["ID", "Name", "Email"],
            "rows": [...]
        },
        {
            "name": "Products",
            "columns": ["ID", "Name", "Price"],
            "rows": [...]
        }
    ]
}

# Expands to multiple table display events
```

### Implementation

```python
class PluralExpander:
    PLURAL_KEYS = ["zItems", "zTables", "zForms", ...]
    
    def expand_plural(self, key, value):
        """Expand plural key to list operation."""
        if not isinstance(value, list):
            return {key: value}
        
        # Remove 'z' prefix and singularize
        singular = key.replace("z", "").rstrip("s").lower()
        
        return {
            "zDisplay": {
                "event": "list",
                "data": {
                    "type": singular,
                    "items": value
                }
            }
        }
    
    def expand_dict(self, horizontal):
        """Recursively expand all plural keys."""
        if not isinstance(horizontal, dict):
            return horizontal
        
        expanded = {}
        for key, value in horizontal.items():
            if key in self.PLURAL_KEYS:
                expanded.update(self.expand_plural(key, value))
            else:
                expanded[key] = value
        
        return expanded
```

### Use Cases

- **List display**: Show array of items
- **Table rendering**: Display multiple tables
- **Form arrays**: Multiple form instances
- **Data collections**: Any array of records

---

## Expansion Flow

```
Command Dict
    ↓
[Check for UI element keys]
    ├─ Has zTerminal? → ShorthandExpander.expand_ui_element()
    ├─ Has zImage?    → ShorthandExpander.expand_ui_element()
    └─ Has zCode?     → ShorthandExpander.expand_ui_element()
    ↓
[Check for organizational structure]
    └─ Nested dicts?  → OrganizationalHandler.expand_hierarchical()
    ↓
[Check for plural keys]
    ├─ Has zItems?    → PluralExpander.expand_plural()
    └─ Has zTables?   → PluralExpander.expand_plural()
    ↓
Fully Expanded Command
    ↓
Route to Subsystem
```

---

## Combined Expansion

All expansion modules can work together:

```python
# Original command (compact!)
command = {
    "display": {
        "zTerminal": {
            "command": "ls -la"
        }
    },
    "data": {
        "zItems": [
            {"id": 1, "name": "File1"},
            {"id": 2, "name": "File2"}
        ]
    }
}

# After expansion
{
    "display": {
        "zDisplay": {
            "event": "terminal",
            "data": {"command": "ls -la"}
        }
    },
    "data": {
        "zDisplay": {
            "event": "list",
            "data": {
                "type": "item",
                "items": [
                    {"id": 1, "name": "File1"},
                    {"id": 2, "name": "File2"}
                ]
            }
        }
    }
}
```

---

## Best Practices

### Use Shorthands for UI

```python
# ✅ Good: Compact shorthand
{"zImage": {"path": "logo.png"}}

# ❌ Bad: Verbose full structure
{"zDisplay": {"event": "image", "data": {"path": "logo.png"}}}
```

### Use Plurals for Collections

```python
# ✅ Good: Plural shorthand
{"zItems": user_list}

# ❌ Bad: Manual iteration
for user in user_list:
    z.display.show_item(user)
```

### Organizational Nesting

```python
# ✅ Good: Semantic grouping
{
    "profile": {
        "personal": {"zFunc": "edit_personal"},
        "settings": {"zFunc": "edit_settings"}
    }
}

# ❌ Bad: Flat structure loses meaning
{
    "profile_personal": {"zFunc": "edit_personal"},
    "profile_settings": {"zFunc": "edit_settings"}
}
```

---

**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**
