# zParser VaFile Module Guide

**[← Back to zParser Guide](../zParser_GUIDE.md)**

---

## Overview

The **vafile module** (zVacuum File) provides comprehensive declarative file parsing:

- **zUI files** (User interface definitions with RBAC)
- **zSchema files** (Database schemas)
- **zConfig files** (Application configurations)
- **zGeneric files** (Generic declarative files)
- **Structure validation** (ensure valid file structure)
- **Metadata extraction** (extract file metadata)

## Module Structure

The vafile module is organized into specialized submodules:

```
vafile/
├── vafile_ui.py           # UI file entry point
├── vafile_schema.py       # Schema file parser
├── vafile_config.py       # Config file parser
├── vafile_generic.py      # Generic file parser
├── vafile_server.py       # Server config parser
└── ui/
    ├── ui_parser.py       # UI file parser
    ├── ui_validator.py    # UI validation
    ├── ui_zblock_processor.py      # zBlock processing
    └── ui_construct_validators.py  # Construct validation
```

---

## File Types

### zUI Files (User Interfaces)

Declarative UI definitions with RBAC support.

**Format:** `zUI.<name>.yaml`

**Structure:**
```yaml
UI:
  header:
    label: "Users"
    icon: "users"
  table:
    columns: ["name", "email", "role"]
    actions: ["edit", "delete"]

RBAC:
  roles: ["admin", "user"]
  permissions: ["read", "write"]
```

---

### zSchema Files (Database Schemas)

Database table schemas with column definitions.

**Format:** `zSchema.<name>.yaml`

**Structure:**
```yaml
table: users
columns:
  id:
    type: integer
    primary_key: true
  name:
    type: string
    required: true
  email:
    type: string
    unique: true
  created_at:
    type: timestamp
    default: now()
```

---

### zConfig Files (Configurations)

Application configuration files.

**Format:** `zConfig.<name>.yaml`

**Structure:**
```yaml
app_name: "MyApp"
version: "1.0.0"
features:
  auth: true
  api: true
  ui: true
database:
  host: localhost
  port: 5432
```

---

## Main Functions

### `parse_ui_file(data: dict, logger, file_path: str = None) -> dict`

Parse UI file with RBAC extraction and validation.

**Features:**
- Extracts UI structure
- Separates RBAC section
- Validates UI constructs
- Processes zBlocks
- Returns structured UI data

**Examples:**
```python
# UI file data
ui_data = {
    "UI": {
        "header": {"label": "Dashboard"},
        "table": {"columns": ["name", "email"]}
    },
    "RBAC": {
        "roles": ["admin"],
        "permissions": ["read", "write"]
    }
}

# Parse UI file
parsed = z.parser.parse_ui_file(ui_data, file_path="zUI.dashboard.yaml")

# Access sections
ui_section = parsed["UI"]           # Clean UI structure
rbac_section = parsed["RBAC"]       # Security rules
metadata = parsed["__metadata__"]   # File metadata
```

---

### `parse_schema_file(data: dict, logger, file_path: str = None) -> dict`

Parse database schema file with validation.

**Examples:**
```python
# Schema file data
schema_data = {
    "table": "users",
    "columns": {
        "id": {"type": "integer", "primary_key": True},
        "name": {"type": "string", "required": True}
    }
}

# Parse schema file
parsed = z.parser.parse_schema_file(schema_data, file_path="zSchema.users.yaml")

# Access schema
table_name = parsed["table"]
columns = parsed["columns"]
```

---

### `parse_config_file(data: dict, logger, file_path: str = None) -> dict`

Parse configuration file with validation.

**Examples:**
```python
# Config file data
config_data = {
    "app_name": "MyApp",
    "version": "1.0.0",
    "features": {"auth": True, "api": True}
}

# Parse config file
parsed = z.parser.parse_config_file(config_data, file_path="zConfig.app.yaml")

# Access config
app_name = parsed["app_name"]
features = parsed["features"]
```

---

### `parse_generic_file(data: dict, logger, file_path: str = None) -> dict`

Parse generic declarative file (fallback parser).

**Examples:**
```python
# Generic file data
generic_data = {
    "key1": "value1",
    "key2": {"nested": "value"}
}

# Parse generic file
parsed = z.parser.parse_generic_file(generic_data, file_path="file.yaml")
```

---

## Validation Functions

### `validate_ui_structure(data: dict, logger) -> bool`

Validate UI file structure.

**Checks:**
- Has `UI` section
- UI constructs are valid (header, table, form, etc.)
- RBAC section (if present) is valid
- No unknown top-level keys

**Examples:**
```python
# Valid UI structure
ui_data = {"UI": {"header": {"label": "Test"}}}
is_valid = z.parser.validate_ui_structure(ui_data)
# → True

# Invalid UI structure (missing UI key)
bad_data = {"header": {"label": "Test"}}
is_valid = z.parser.validate_ui_structure(bad_data)
# → False
```

---

### `validate_schema_structure(data: dict, logger) -> bool`

Validate schema file structure.

**Checks:**
- Has `table` key
- Has `columns` key
- Column definitions are valid
- Types are recognized

**Examples:**
```python
# Valid schema
schema_data = {
    "table": "users",
    "columns": {"id": {"type": "integer"}}
}
is_valid = z.parser.validate_schema_structure(schema_data)
# → True
```

---

### `validate_config_structure(data: dict, logger) -> bool`

Validate config file structure.

**Checks:**
- Has required config keys
- Values are appropriate types
- No syntax errors

**Examples:**
```python
# Valid config
config_data = {"app_name": "MyApp", "version": "1.0.0"}
is_valid = z.parser.validate_config_structure(config_data)
# → True
```

---

## RBAC Extraction

UI files support RBAC (Role-Based Access Control) sections:

**Why Separate RBAC?**
- Security rules independent from UI structure
- zAuth can process RBAC separately
- UI rendering doesn't need security context
- Clear separation of concerns

**RBAC Structure:**
```yaml
RBAC:
  roles: ["admin", "user", "guest"]
  permissions:
    - read
    - write
    - delete
  allow:
    admin: ["read", "write", "delete"]
    user: ["read", "write"]
    guest: ["read"]
```

**Extraction Example:**
```python
ui_data = {
    "UI": {"header": {"label": "Users"}},
    "RBAC": {
        "roles": ["admin", "user"],
        "permissions": ["read", "write"]
    }
}

parsed = z.parser.parse_ui_file(ui_data)

# RBAC is extracted
ui = parsed["UI"]       # {"header": {"label": "Users"}}
rbac = parsed["RBAC"]   # {"roles": [...], "permissions": [...]}

# zAuth can now process RBAC independently
z.auth.apply_rbac(rbac)
```

---

## UI Constructs

Supported UI constructs in zUI files:

### Header
```yaml
UI:
  header:
    label: "Dashboard"
    icon: "dashboard"
    subtitle: "Overview"
```

### Table
```yaml
UI:
  table:
    columns: ["name", "email", "role"]
    actions: ["edit", "delete"]
    sortable: true
    filterable: true
```

### Form
```yaml
UI:
  form:
    fields:
      - name: username
        type: text
        required: true
      - name: email
        type: email
        required: true
      - name: role
        type: select
        options: ["admin", "user"]
```

### Button
```yaml
UI:
  button:
    label: "Submit"
    action: "zFunc users.create"
    variant: "primary"
```

### Navigation
```yaml
UI:
  navigation:
    items:
      - label: "Users"
        link: "zLink users.table"
      - label: "Settings"
        link: "zLink settings"
```

---

## Metadata Extraction

All parsed files include metadata:

```python
parsed = z.parser.parse_ui_file(ui_data, file_path="zUI.users.yaml")

metadata = parsed["__metadata__"]
# {
#     "file_path": "zUI.users.yaml",
#     "file_type": "zUI",
#     "parsed_at": "2025-03-10T10:30:00",
#     "version": "1.0.0"
# }
```

**Metadata Fields:**
- `file_path` - Original file path
- `file_type` - File type (zUI, zSchema, zConfig)
- `parsed_at` - Timestamp of parsing
- `version` - zOS version used for parsing

---

## Use Cases

### 1. Load and Render UI

```python
# Load UI file
with open("zUI.users.yaml") as f:
    ui_data = yaml.safe_load(f)

# Parse UI file
parsed = z.parser.parse_ui_file(ui_data, file_path="zUI.users.yaml")

# Render UI
z.walker.render_ui(parsed["UI"])

# Apply RBAC
z.auth.apply_rbac(parsed["RBAC"])
```

### 2. Database Schema Migration

```python
# Load schema file
with open("zSchema.users.yaml") as f:
    schema_data = yaml.safe_load(f)

# Parse schema
parsed = z.parser.parse_schema_file(schema_data, file_path="zSchema.users.yaml")

# Create table
z.data.create_table(parsed["table"], parsed["columns"])
```

### 3. Application Configuration

```python
# Load config file
with open("zConfig.app.yaml") as f:
    config_data = yaml.safe_load(f)

# Parse config
parsed = z.parser.parse_config_file(config_data, file_path="zConfig.app.yaml")

# Apply config
app_config.update(parsed)
```

---

## Best Practices

1. **Use zUI for interfaces** - Keep UI definitions declarative
2. **Separate RBAC from UI** - Security rules independent
3. **Validate before parsing** - Use validation functions
4. **Include metadata** - Track file origins and versions
5. **Follow naming conventions** - `zUI.*`, `zSchema.*`, `zConfig.*`
6. **Version your files** - Include version in file metadata

---

## Integration

The vafile module integrates with:

- **zLoader** - Uses vafile parsing for file loading
- **zWalker** - Uses UI file parsing for navigation
- **zAuth** - Uses RBAC extraction for security
- **zData** - Uses schema file parsing for database operations
- **zConfig** - Uses config file parsing for application settings

---

**[← Back to zParser Guide](../zParser_GUIDE.md)**
