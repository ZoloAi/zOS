# zParser File Module Guide

**[← Back to zParser Guide](../zParser_GUIDE.md)**

---

## Overview

The **file module** provides comprehensive file content parsing capabilities:

- **YAML parsing** (safe loading)
- **JSON parsing** (built-in support)
- **Format detection** (automatic YAML/JSON recognition)
- **RBAC transformation** (extract security rules from UI files)
- **File-by-path parsing** (load + parse in one call)

## Module Structure

The file module is organized into specialized submodules:

```
file/
├── file_parser.py              # Main file parsing logic
├── file_utils.py               # File utilities
├── format_parsers/
│   ├── yaml_parser.py         # YAML-specific parsing
│   ├── json_parser.py         # JSON-specific parsing
│   ├── format_detector.py     # Format auto-detection
│   ├── expr_parser.py         # Expression parsing
│   └── zlsp_parser.py         # ZLSP format parsing
└── transformers/
    ├── file_type_detector.py  # File type detection
    └── rbac_transformer.py    # RBAC extraction for UI files
```

---

## Main Functions

### `parse_file_content(content: str, logger, extension: str = None, file_path: str = None) -> Any`

Main file parser with automatic format detection and RBAC transformation.

**Features:**
- Auto-detects YAML vs JSON
- Safe YAML loading (prevents code injection)
- RBAC extraction for UI files
- Returns `None` on parse failure

**Examples:**
```python
# Auto-detect format
data = z.parser.parse_file_content(content)

# Specify extension
data = z.parser.parse_file_content(yaml_content, extension=".yaml")

# UI file with RBAC extraction
data = z.parser.parse_file_content(
    ui_content,
    extension=".yaml",
    file_path="zUI.users.yaml"  # Triggers RBAC extraction
)
```

---

### `parse_yaml(yaml_str: str, logger) -> Any`

Parse YAML content with safe loading.

**Examples:**
```python
yaml_content = """
name: John Doe
age: 30
skills:
  - Python
  - JavaScript
"""

data = z.parser.parse_yaml(yaml_content)
# Returns: {"name": "John Doe", "age": 30, "skills": ["Python", "JavaScript"]}
```

---

### `parse_json(json_str: str, logger) -> Any`

Parse JSON content with error handling.

**Examples:**
```python
json_content = '{"name": "Jane", "age": 28}'

data = z.parser.parse_json(json_content)
# Returns: {"name": "Jane", "age": 28}
```

---

### `detect_format(content: str, logger) -> str`

Auto-detect file format (JSON vs YAML).

**Returns:**
- `"json"` - JSON format detected
- `"yaml"` - YAML format detected
- `"unknown"` - Format unclear

**Examples:**
```python
# JSON content
format = z.parser.detect_format('{"key": "value"}')
# → "json"

# YAML content
format = z.parser.detect_format('key: value')
# → "yaml"
```

---

### `parse_file_by_path(file_path: str, logger) -> Any`

Convenience method: load file from disk + parse content.

**Examples:**
```python
# Load and parse in one call
data = z.parser.parse_file_by_path("/path/to/config.yaml")
```

---

### `parse_json_expr(expr: str, logger) -> Any`

Parse JSON expressions (for zExpr_eval compatibility).

**Examples:**
```python
# Parse JSON-like expressions
data = z.parser.parse_json_expr('{"name": "Alice", "age": 30}')
```

---

## Format Detection Algorithm

The format detector uses these heuristics:

1. **Check for JSON markers** - `{`, `[`, `"` at start
2. **Check for YAML markers** - `:`, `-`, indentation
3. **Attempt JSON parse** - Try JSON first (stricter format)
4. **Fallback to YAML** - YAML is more forgiving
5. **Return unknown** - If both fail

---

## RBAC Transformation

When parsing UI files (`zUI.*.yaml`), the file parser automatically extracts RBAC sections:

**Input (UI file with RBAC):**
```yaml
UI:
  header:
    label: "Users"
  table:
    columns: ["name", "email"]

RBAC:
  roles: ["admin", "user"]
  permissions: ["read", "write"]
```

**Output (RBAC extracted):**
```python
{
    "UI": {
        "header": {"label": "Users"},
        "table": {"columns": ["name", "email"]}
    },
    "RBAC": {
        "roles": ["admin", "user"],
        "permissions": ["read", "write"]
    }
}
```

**Why RBAC Extraction?**
- Separates security rules from UI structure
- Enables zAuth to process RBAC independently
- Keeps UI parsing clean
- Supports role-based access control

---

## Error Handling

All parsing functions handle errors gracefully:

```python
# Parse invalid YAML
data = z.parser.parse_yaml("invalid: yaml: content:")
# Returns: None (logged error)

# Parse invalid JSON
data = z.parser.parse_json('{invalid json}')
# Returns: None (logged error)
```

---

## Use Cases

### 1. Parse Configuration Files

```python
# Load and parse config
config_content = """
database:
  host: localhost
  port: 5432
  name: myapp
"""

config = z.parser.parse_yaml(config_content)
print(f"DB Host: {config['database']['host']}")
```

### 2. Parse UI Files with RBAC

```python
# UI file content
ui_content = """
UI:
  header:
    label: "Dashboard"
RBAC:
  roles: ["admin"]
"""

ui_data = z.parser.parse_file_content(
    ui_content,
    extension=".yaml",
    file_path="zUI.dashboard.yaml"
)

# Access UI and RBAC separately
ui_section = ui_data['UI']
rbac_section = ui_data['RBAC']
```

### 3. Auto-Detect and Parse

```python
# Unknown format - let parser detect
unknown_content = '{"key": "value"}'

data = z.parser.parse_file_content(unknown_content)
# Auto-detects JSON and parses
```

---

## Best Practices

1. **Use `parse_file_content` for flexibility** - Auto-detection works great
2. **Specify extension when known** - Slightly faster parsing
3. **Check for `None` return** - Parse failures return `None`
4. **Use file_path for UI files** - Enables RBAC extraction
5. **Prefer YAML for declarative files** - More readable than JSON

---

## Integration

The file module integrates with:

- **zLoader** - Uses file parsing for UI/Schema loading
- **zAuth** - Uses RBAC extraction for security
- **zConfig** - Uses YAML parsing for config files
- **zData** - Uses schema file parsing
- **vafile module** - Uses file parsing for zVaFile processing

---

**[← Back to zParser Guide](../zParser_GUIDE.md)**
