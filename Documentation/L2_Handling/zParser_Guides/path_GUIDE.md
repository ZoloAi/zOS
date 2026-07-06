# zParser Path Module Guide

**[← Back to zParser Guide](../zParser_GUIDE.md)**

---

## Overview

The **path module** provides comprehensive path resolution capabilities for zOS applications:

- **zPath notation** (`@workspace`, `~.zMachine.*`)
- **File type identification** (zUI, zSchema, zConfig)
- **Symbol resolution** (custom path symbols)
- **Cross-platform paths** (macOS, Linux, Windows)

## Module Structure

The path module is organized into specialized submodules:

```
path/
├── path_decoder.py          # Main path resolution
├── file_identifier.py       # File type identification
├── resolvers/
│   ├── zmachine_resolver.py # zMachine path resolution
│   ├── symbol_resolver.py   # Symbol path resolution
│   └── path_builder.py      # Path construction utilities
├── detection/
│   ├── zvafile_detector.py  # zVaFile detection
│   ├── extension_finder.py  # Extension detection
│   └── file_validator.py    # Path validation
└── extraction/
    ├── filename_extractor.py # Filename extraction
    └── ui_mode_handler.py    # UI mode handling
```

---

## Main Functions

### `zPath_decoder(path_notation: str, logger=None, session=None) -> str`

Resolves zOS path notation to absolute OS-specific paths.

**Supported Notations:**
- `@` - Workspace root (current working directory)
- `@file.yaml` - Workspace-relative file
- `@dir/file.yaml` - Workspace-relative subdirectory
- `~.zMachine.Config` - Machine config file
- `~.zMachine.zConfigs` - Config directory
- `~.zMachine.Logs` - Logs directory

**Examples:**
```python
# Workspace paths
path = z.parser.zPath_decoder("@data.json")
# → /Users/you/Projects/MyApp/data.json

# zMachine paths
path = z.parser.zPath_decoder("~.zMachine.Config")
# → ~/Library/Application Support/zOS/zConfigs/zConfig.machine.yaml (macOS)

# Workspace root
path = z.parser.zPath_decoder("@.")
# → /Users/you/Projects/MyApp
```

---

### `identify_zFile(filename: str, directory: str = None) -> str`

Identifies the type of zOS declarative file.

**Returns:**
- `"zUI"` - User interface file (`zUI.*.yaml`)
- `"zSchema"` - Database schema file (`zSchema.*.yaml`)
- `"zConfig"` - Configuration file (`zConfig.*.yaml`)
- `"zOther"` - Regular file (no zOS prefix)

**Examples:**
```python
# Identify file types
file_type = z.parser.identify_zFile("zUI.users.yaml")
# → "zUI"

file_type = z.parser.identify_zFile("zSchema.users.yaml")
# → "zSchema"

file_type = z.parser.identify_zFile("data.json")
# → "zOther"
```

---

### `resolve_zmachine_path(keyword: str, logger=None) -> str`

Resolves zMachine keywords to OS-specific paths.

**Available Keywords:**
- `Config` - Machine/environment config file
- `zConfigs` - Config directory
- `zUIs` - UI definitions directory
- `zSchemas` - Database schema directory
- `Logs` - Logs directory
- `users` - User storage directory
- `Apps` - App-specific storage (if enabled)

**Examples:**
```python
# Resolve zMachine keywords
path = z.parser.resolve_zmachine_path("zConfigs")
# → ~/Library/Application Support/zOS/zConfigs/ (macOS)

path = z.parser.resolve_zmachine_path("Logs")
# → ~/Library/Application Support/zOS/logs/ (macOS)
```

---

### `resolve_symbol_path(symbol_notation: str, logger=None, session=None) -> str`

Resolves custom symbol paths (future feature).

**Example:**
```python
# Resolve custom symbols
path = z.parser.resolve_symbol_path("$.my_custom_path")
```

---

## Path Resolution Algorithm

The path decoder follows this resolution order:

1. **Check for `@` prefix** → Workspace-relative path
2. **Check for `~.zMachine.`** → zMachine system path
3. **Check for symbol notation** → Custom symbol resolution
4. **Default** → Return path as-is (absolute or relative)

---

## Cross-Platform Compatibility

All path operations are cross-platform:

| Platform | zMachine Root |
|----------|--------------|
| **macOS** | `~/Library/Application Support/zOS/` |
| **Linux** | `~/.local/share/zOS/` |
| **Windows** | `%APPDATA%/zOS/` |

The path module automatically detects the OS and returns platform-appropriate paths.

---

## File Type Detection

The file identifier recognizes zOS file patterns:

| Pattern | Type | Description |
|---------|------|-------------|
| `zUI.*` | zUI | User interface definitions |
| `zSchema.*` | zSchema | Database schemas |
| `zConfig.*` | zConfig | Configuration files |
| Other | zOther | Regular files |

---

## Use Cases

### 1. Load Workspace Files

```python
# Resolve and load workspace file
path = z.parser.zPath_decoder("@configs/app.yaml")
with open(path, 'r') as f:
    config = yaml.safe_load(f)
```

### 2. Access System Configs

```python
# Access machine config
path = z.parser.zPath_decoder("~.zMachine.Config")
with open(path, 'r') as f:
    machine_config = yaml.safe_load(f)
```

### 3. Identify File Types for Smart Loading

```python
# Load file based on type
file_type = z.parser.identify_zFile(filename)

if file_type == "zUI":
    ui_data = z.parser.parse_ui_file(data, file_path=filename)
elif file_type == "zSchema":
    schema_data = z.parser.parse_schema_file(data, file_path=filename)
```

---

## Best Practices

1. **Always use `@` for workspace files** - Ensures portability
2. **Use `~.zMachine.*` for system paths** - Cross-platform compatibility
3. **Check file types before parsing** - Smart loading based on type
4. **Don't hardcode absolute paths** - Use zPath notation instead

---

## Integration

The path module integrates with:

- **zLoader** - Uses path resolution for file loading
- **zShell** - Uses path resolution for command execution
- **zConfig** - Provides zMachine path definitions
- **zFunc** - Uses path resolution for function module loading

---

**[← Back to zParser Guide](../zParser_GUIDE.md)**
