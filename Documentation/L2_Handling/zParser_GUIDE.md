**[← Back to zComm Guide](../L1_Foundation/zComm_GUIDE.md) | [Home](../../README.md) | [Next: zLoader Guide →](../L1_Foundation/zLoader_GUIDE.md)**

---

# zParser

**zParser** is a **Layer 2 subsystem** (Handling Layer) in **zOS**.
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

It provides comprehensive parsing capabilities - path resolution, command parsing, file content parsing, plugin syntax parsing, expression evaluation, and declarative file parsing - through one unified interface.

You get:

- **Zero configuration**  
- **No regex sprawl**
- **No path juggling**  
- **zPath notation** (`@workspace`, `~.zMachine`, `zUI.users.yaml`)
- **Command parsing** (20+ command types: zFunc, zLink, zOpen, etc.)
- **File parsing** (YAML, JSON, auto-detection with RBAC)
- **Plugin syntax parsing** (detect and parse `&PluginName.function(args)`)
- **Expression evaluation** (JSON expressions, dotted paths, references)
- **Declarative file parsing** (zUI, zSchema, zConfig, zGeneric)
- **Argument splitting** (universal bracket + quote aware parsing)

## Architecture Overview

**zParser** is composed of specialized modules, each handling a specific aspect of parsing:

| Module | Purpose | Guide |
|--------|---------|-------|
| **path** | Path resolution (zPath, zMachine, symbols, file identification) | [path_GUIDE.md](zParser_Guides/path_GUIDE.md) |
| **file** | File parsing (YAML, JSON, format detection, RBAC transformation) | [file_GUIDE.md](zParser_Guides/file_GUIDE.md) |
| **plugin** | Plugin invocation (detection, resolution, execution, caching) | [plugin_GUIDE.md](zParser_Guides/plugin_GUIDE.md) |
| **commands** | Command parsing (20+ types with routing and validation) | [commands_GUIDE.md](zParser_Guides/commands_GUIDE.md) |
| **vafile** | zVaFile parsing (UI, Schema, Config, Generic with validation) | [vafile_GUIDE.md](zParser_Guides/vafile_GUIDE.md) |
| **utils** | Expression evaluation (JSON, dotted paths, references) | [utils_GUIDE.md](zParser_Guides/utils_GUIDE.md) |
| **functions** | Function path parsing (for zFunc integration) | [utils_GUIDE.md](zParser_Guides/utils_GUIDE.md) |
| **trust** | Path-trust gate (zGuard seam for resolved-path enforcement) | *(built-in — see [Security & trust](#security--trust-zguard-seam))* |
| **shared** | Argument splitting + constants (cross-subsystem vocab single-sourced in root `zVocabulary`) | *(built-in)* |

This guide provides a **facade overview** of zParser. For deep dives into specific modules, see the guides in `zParser_Guides/`.

---

## Initialization Order

When you call `zOS()`, zParser initializes after the foundation layers:

1. **zConfig Ready** - Configuration subsystem initialized
2. **zComm Ready** - Communication subsystem initialized
3. **zDisplay Ready** - Display subsystem initialized
4. **zParser Initialization** - Parser subsystem starts:
   - Validate zOS instance (session + logger + display required)
   - Initialize path resolution modules
   - Initialize file parsing modules
   - Initialize command parsing modules
   - Initialize plugin resolution modules
   - Initialize expression evaluation modules
   - Initialize zVaFile parsing modules
   - Declare readiness via display
   - Log ready state
5. **zParser Ready** - Parser infrastructure available

This order ensures zParser has access to configuration, display, and logging before parsing operations begin.

**Auto-Initialization:**
```python
from zOS import zOS

z = zOS()  # zConfig → zComm → zDisplay → zParser → other subsystems

# zParser is now ready:
z.parser.zPath_decoder("@workspace/data.yaml")           # Path resolution
z.parser.parse_command("zFunc users.list --limit 10")    # Command parsing
z.parser.parse_file_content(yaml_str, ".yaml")           # File parsing
z.parser.is_plugin_invocation("&MyPlugin.func()")        # Plugin detection
z.parser.parse_plugin_invocation("&MyPlugin.func()")     # Plugin syntax parsing
z.parser.zExpr_eval('{"key": "value"}')                  # Expression evaluation
z.parser.parse_ui_file(ui_data, file_path="zUI.users")   # zVaFile parsing
```

---

## What's in This Guide

This guide covers the **main zParser facade** - the unified interface to all parsing features. Like the zConfig and zComm guides, we focus on:

1. **Architecture Overview** - Module structure and design patterns
2. **Initialization** - How zParser auto-initializes in the framework
3. **Tutorials** - Hands-on demos (Level 0-4) for learning by doing
4. **API Reference** - Complete method signatures and usage patterns
5. **Advanced Features** - RBAC transformation, plugin caching, path resolution

**What's NOT in this guide:**
- Deep dives into individual modules (see `zParser_Guides/` folder)
- zLoader integration patterns (see [zLoader Guide](../L1_Foundation/zLoader_GUIDE.md))
- zFunc function resolution (see [zFunc Guide](zFunc_GUIDE.md))
- zShell command execution (see [zShell Guide](../L3_Abstraction/zShell_GUIDE.md))

**Current Implementation Status:**
- ✅ Path Resolution (zPath, zMachine, symbols, file identification)
- ✅ File Parsing (YAML, JSON, format detection, RBAC transformation)
- ✅ Command Parsing (20+ command types with routing)
- ✅ Plugin Syntax Parsing (detection, regex parsing, argument parsing primitives)
- ✅ Expression Evaluation (JSON expressions, dotted paths, references)
- ✅ zVaFile Parsing (UI, Schema, Config, Generic with validation)
- ✅ Function Path Parsing (for zFunc integration)
- ✅ Argument Splitting (universal bracket + quote aware parsing)
- ✅ Path-Trust Gate (zGuard seam; permissive in open-core, sealed with zGuard)
- ✅ SSOT Vocabulary (shared protocol literals drawn from root `zVocabulary`)

---

## Tutorials

**Learn by doing!** 

The tutorials below are organized in a bottom-up fashion. Every tutorial below has a working demo you can run and modify.

**A Note on Learning zOS:**  
Each tutorial (lvl1, lvl2, lvl3...) progressively introduces more complex features of **this subsystem**. The early tutorials start with familiar imperative patterns (think Django-style conventions) to meet you where you are as a developer.

As you progress through zOS's subsystems, you'll notice a gradual shift from imperative to declarative patterns. This intentional journey helps reshape your mental model from imperative to declarative thinking. Only when you reach **Layer 3 (Orchestration)** will you see subsystems used **fully declaratively** as intended in production. By then, the true magic of declarative coding will reveal itself, and you'll understand why we started this way.

Get the demos:

```bash
# Clone only the Demos folder
git clone --depth 1 --filter=blob:none --sparse https://github.com/ZoloAi/zolo-zcli.git
cd zolo-zcli
git sparse-checkout set Demos
```

> All zParser demos are in: `Demos/Layer_2/zParser_Demo/`

---

# **zParser - Level 0** (Hello zParser)

After exploring Layer 0 (zConfig, zComm) and Layer 1 (zDisplay), you're ready for Layer 2 parsing capabilities. The same familiar pattern continues!

**The same zSpark pattern** from previous subsystems unlocks zParser's capabilities:

```python
from zOS import zOS

# Familiar zSpark pattern from previous guides
zSpark = {
    "deployment": "Development",  # Show subsystem banners
    "title": "hello-parser",      # Session identifier
    "logger": "INFO",             # Console + file logging
    "logger_path": "./logs",      # Where logs go
}

# Watch the initialization order in the output:
# [zConfig Ready] → [zComm Ready] → [zDisplay Ready] → [zParser Ready]

z = zOS(zSpark)

# zParser is now ready to use!
```

**Key Discovery**: zParser auto-initializes after Layer 0 (zConfig, zComm) and Layer 1 (zDisplay) when you call `zOS()`. It's a Layer 2 subsystem - part of the Handling layer that processes and transforms data.

**🎯 Try it yourself:**

Run the demo to see zParser in action:

```bash
python3 Demos/Layer_2/zParser_Demo/lvl0_hello/1_hello_parser.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl0_hello/1_hello_parser.py)

**What you'll discover:**
- Watch the initialization order: [zConfig] → [zComm] → [zDisplay] → [zParser]
- Layer 2 subsystem (Handling layer)
- Same zSpark pattern as previous guides
- Parser ready with zero configuration

---

# **zParser - Level 1** (Path Resolution)

### **i. Workspace Paths (@)**

In Level 0, you watched zParser initialize. Now let's actually **use** it.  
The simplest zParser action? Resolving workspace paths with `@` notation.

**Think of `@` as "my project folder"**. Instead of writing absolute paths like `/Users/you/Projects/MyApp/data.json`, you write `@data.json`. zParser automatically resolves it to the correct path on any machine.

> **Why `@` notation?** Cross-platform portability! Your code works identically on macOS, Linux, and Windows without path changes. The `@` symbol represents your workspace root (current working directory).

Let's resolve a few workspace paths:

```python
from zOS import zOS

# Consistent zSpark pattern
zSpark = {
    "deployment": "Production",
    "title": "path-workspace",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Resolve workspace paths
paths = [
    "@data.json",                    # Root file
    "@configs/settings.yaml",        # Subdirectory
    "@users/alice/profile.json",     # Nested path
    "@.",                            # Workspace root itself
]

for path_notation in paths:
    resolved = z.parser.zPath_decoder(path_notation)
    print(f"{path_notation:30} → {resolved}")
```

> **Returns:** Absolute OS-specific path for the given workspace-relative notation.

**🎯 Resolve workspace paths on your machine:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl1_paths/1_path_workspace.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl1_paths/1_path_workspace.py)

**What you'll discover:**
- `@` represents your workspace root (current working directory)
- Cross-platform path resolution (macOS, Linux, Windows)
- No manual `os.path.join()` or `Path()` imports needed
- Clean, declarative path notation

---

### **ii. zMachine Paths (~.zMachine)**

Remember from the **zConfig Guide** how zOS creates an OS-native application support folder? That's where machine and environment configs live:

- **macOS**: `~/Library/Application Support/zOS/`
- **Linux**: `~/.local/share/zOS/`
- **Windows**: `%APPDATA%/zOS/`

**zMachine paths** (`~.zMachine.*`) are shortcuts to these system folders. Instead of hardcoding paths, you use declarative notation that works everywhere!

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "path-zmachine",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Resolve zMachine paths (system folders)
paths = {
    "~.zMachine.Config": "Machine config file",
    "~.zMachine.zConfigs": "Config directory",
    "~.zMachine.zUIs": "UI definitions directory",
    "~.zMachine.zSchemas": "Schema directory",
    "~.zMachine.Logs": "Logs directory",
    "~.zMachine.users": "User storage directory",
}

for notation, description in paths.items():
    resolved = z.parser.zPath_decoder(notation)
    print(f"{notation:25} → {description}")
    print(f"{'':25}   {resolved}\n")
```

**🎯 See where zOS stores system files on your machine:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl1_paths/2_path_zmachine.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl1_paths/2_path_zmachine.py)

**What you'll discover:**
- `~.zMachine.*` shortcuts to OS-native folders
- Cross-platform system paths (no manual OS detection)
- Access machine configs, UIs, schemas, logs declaratively
- Works identically on macOS, Linux, Windows

**Available zMachine Keywords:**
- `Config` - Machine/environment config file
- `zConfigs` - Config directory
- `zUIs` - UI definitions directory
- `zSchemas` - Database schema directory
- `Logs` - Logs directory
- `users` - User storage directory
- `Apps` - App-specific storage (if enabled)

---

### **iii. File Type Identification**

Now that you can resolve paths, let's identify what **type** of file you're dealing with. zOS has special file types:

- **zUI** - User interface definitions (`zUI.users.yaml`)
- **zSchema** - Database schemas (`zSchema.users.yaml`)
- **zConfig** - Configuration files (`zConfig.app.yaml`)
- **zOther** - Everything else

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "file-identification",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Identify file types
files = [
    "zUI.users.yaml",
    "zSchema.users.yaml",
    "zConfig.app.yaml",
    "data.json",
    "settings.yaml",
]

for filename in files:
    file_type = z.parser.identify_zFile(filename)
    print(f"{filename:25} → Type: {file_type}")
```

**🎯 Try file type identification:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl1_paths/3_file_identification.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl1_paths/3_file_identification.py)

**What you'll discover:**
- Automatic file type detection from filename
- Recognize zUI, zSchema, zConfig prefixes
- Distinguish declarative zOS files from regular files
- Foundation for smart file loading (see zLoader Guide)

---

**🎯 Level 1 Complete!**

You've learned path resolution fundamentals:
- ✅ **Workspace paths** - `@` notation for project files
- ✅ **zMachine paths** - `~.zMachine.*` for system folders
- ✅ **File identification** - Detect zUI, zSchema, zConfig types

**These are the path essentials. Most applications only need these.**

---

# **zParser - Level 2** (File Parsing)

### **i. YAML Parsing**

Time to parse file content! Let's start with YAML - the most common format in zOS for configuration and declarative files.

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "parse-yaml",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# YAML string to parse
yaml_content = """
name: John Doe
age: 30
skills:
  - Python
  - JavaScript
  - Docker
active: true
"""

# Parse YAML
data = z.parser.parse_yaml(yaml_content)

print(f"Name: {data['name']}")
print(f"Age: {data['age']}")
print(f"Skills: {', '.join(data['skills'])}")
print(f"Active: {data['active']}")
```

> One line to parse YAML. No `import yaml` needed. Safe loading by default.

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl2_files/1_parse_yaml.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl2_files/1_parse_yaml.py)

**What you'll discover:**
- One line: `z.parser.parse_yaml(content)`
- Safe YAML loading (prevents code injection)
- Returns Python dict/list structures
- Built-in error handling (returns `None` on failure)

---

### **ii. JSON Parsing**

JSON works just as easily:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "parse-json",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# JSON string to parse
json_content = """
{
  "name": "Jane Smith",
  "age": 28,
  "skills": ["Python", "Go", "Kubernetes"],
  "active": true
}
"""

# Parse JSON
data = z.parser.parse_json(json_content)

print(f"Name: {data['name']}")
print(f"Age: {data['age']}")
print(f"Skills: {', '.join(data['skills'])}")
print(f"Active: {data['active']}")
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl2_files/2_parse_json.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl2_files/2_parse_json.py)

**What you'll discover:**
- One line: `z.parser.parse_json(content)`
- Built-in JSON parsing (no `import json`)
- Returns Python dict/list structures
- Graceful error handling

---

### **iii. Auto-Detection**

Don't know if a file is YAML or JSON? Let zParser detect it automatically:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "parse-auto",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Unknown format - could be YAML or JSON
unknown_content = """
{
  "name": "Auto Detect",
  "format": "JSON"
}
"""

# Auto-detect format and parse
data = z.parser.parse_file_content(unknown_content, extension=".json")

# Or let it detect from content
data = z.parser.parse_file_content(unknown_content)

print(f"Name: {data['name']}")
print(f"Format: {data['format']}")
```

**🎯 Try auto-detection:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl2_files/3_parse_auto.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl2_files/3_parse_auto.py)

**What you'll discover:**
- Automatic format detection (JSON vs YAML)
- One method: `parse_file_content(content, extension?)`
- Extension hint optional (detects from content if omitted)
- Works with both JSON and YAML seamlessly

---

**🎯 Level 2 Complete!**

You've mastered file content parsing:
- ✅ **YAML parsing** - Safe, one-line parsing
- ✅ **JSON parsing** - Built-in JSON support
- ✅ **Auto-detection** - Smart format detection

**These are the file parsing essentials. Most applications only need these.**

---

# **zParser - Level 3** (Commands & Expressions)

### **i. Command Parsing**

zOS uses a command syntax for declarative operations: `zFunc users.list --limit 10`. Let's parse these commands:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "parse-command",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Parse zFunc command
command_str = "zFunc users.list --limit 10 --active true"
cmd = z.parser.parse_command(command_str)

print(f"Type: {cmd['type']}")           # 'zFunc'
print(f"Path: {cmd['path']}")           # 'users.list'
print(f"Args: {cmd.get('arguments')}")  # {'limit': '10', 'active': 'true'}
```

> Parse 20+ command types: zFunc, zLink, zOpen, zFile, zConfig, zData, zSession, and more!

**🎯 Try command parsing:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl3_advanced/1_parse_command.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl3_advanced/1_parse_command.py)

**What you'll discover:**
- Parse 20+ command types (zFunc, zLink, zOpen, etc.)
- Extract command type, path, and arguments
- Handle complex quoting and escaping
- Foundation for zShell command execution

**Supported Command Types:**
- `zFunc` - Function invocation
- `zLink` - Navigation linking
- `zOpen` - File/UI opening
- `zFile` - File operations
- `zConfig` - Configuration access
- `zData` - Data operations
- `zSession` - Session management
- `zUI` - UI rendering
- And 12+ more!

---

### **ii. Expression Evaluation**

Evaluate JSON expressions dynamically:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "eval-expression",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Evaluate JSON expressions
expressions = [
    '{"name": "Alice", "age": 30}',
    '[1, 2, 3, 4, 5]',
    '{"active": true, "count": 42}',
]

for expr in expressions:
    result = z.parser.zExpr_eval(expr)
    print(f"Expression: {expr}")
    print(f"Result: {result}\n")
```

**🎯 Try expression evaluation:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl3_advanced/2_eval_expression.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl3_advanced/2_eval_expression.py)

**What you'll discover:**
- Evaluate JSON-like expressions
- Safe evaluation (no `eval()` risks)
- Parse complex nested structures
- Foundation for dynamic configuration

---

### **iii. Plugin Syntax Detection**

Detect plugin syntax and parse invocations (`&PluginName.function()`):

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "plugin-detection",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Test strings
test_strings = [
    "&MyPlugin.do_something()",
    "&Users.list(limit=10)",
    "regular_function()",
    "&Plugin.func()",
]

for test in test_strings:
    is_plugin = z.parser.is_plugin_invocation(test)
    status = "✓ Plugin" if is_plugin else "✗ Not plugin"
    print(f"{test:30} → {status}")
    
    # If it's a plugin, parse the syntax
    if is_plugin:
        plugin_name, func_name, args_str = z.parser.parse_plugin_invocation(test)
        print(f"  → Plugin: {plugin_name}, Function: {func_name}, Args: {args_str}")
```

**🎯 Try plugin detection:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl3_advanced/3_plugin_detection.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl3_advanced/3_plugin_detection.py)

**What you'll discover:**
- Detect plugin invocations (`&` prefix)
- Parse plugin syntax into components (name, function, args)
- Distinguish plugins from regular functions
- Foundation for plugin execution (see zFunc Guide)

> **Note:** zParser provides **parsing primitives only**. For plugin execution, loading, and caching, see the [zFunc Guide](zFunc_GUIDE.md). zParser detects and parses the syntax; zFunc loads and executes the plugins.

---

**🎯 Level 3 Complete!**

You've explored advanced parsing:
- ✅ **Command parsing** - Parse 20+ command types
- ✅ **Expression evaluation** - Safe JSON expression evaluation
- ✅ **Plugin syntax parsing** - Detect and parse plugin invocations

---

# **zParser - Level 4** (Declarative Files)

### **i. UI File Parsing**

Parse declarative UI files (zUI.*.yaml) with RBAC extraction:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "parse-ui",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# UI file data (YAML)
ui_data = {
    "UI": {
        "header": {
            "label": "Users",
            "icon": "users"
        },
        "table": {
            "columns": ["name", "email", "role"]
        }
    },
    "RBAC": {
        "roles": ["admin", "user"],
        "permissions": ["read", "write"]
    }
}

# Parse UI file
parsed = z.parser.parse_ui_file(ui_data, file_path="zUI.users.yaml")

print(f"UI Keys: {list(parsed['UI'].keys())}")
print(f"RBAC extracted: {'RBAC' in parsed}")
```

> **RBAC Extraction**: zParser automatically extracts RBAC sections from UI files for security processing. The UI and RBAC are separated cleanly.

**🎯 Try UI file parsing:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl4_declarative/1_parse_ui.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl4_declarative/1_parse_ui.py)

**What you'll discover:**
- Parse declarative UI files (zUI.*.yaml)
- Automatic RBAC extraction for security
- Validate UI structure
- Foundation for zLoader and zWalker

---

### **ii. Schema File Parsing**

Parse database schema files (zSchema.*.yaml):

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "parse-schema",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Schema file data
schema_data = {
    "table": "users",
    "columns": {
        "id": {"type": "integer", "primary_key": True},
        "name": {"type": "string", "required": True},
        "email": {"type": "string", "unique": True},
        "created_at": {"type": "timestamp"}
    }
}

# Parse schema file
parsed = z.parser.parse_schema_file(schema_data, file_path="zSchema.users.yaml")

print(f"Table: {parsed['table']}")
print(f"Columns: {list(parsed['columns'].keys())}")
```

**🎯 Try schema file parsing:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl4_declarative/2_parse_schema.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl4_declarative/2_parse_schema.py)

**What you'll discover:**
- Parse database schema files (zSchema.*.yaml)
- Validate schema structure
- Extract table and column definitions
- Foundation for zData subsystem

---

### **iii. Config File Parsing**

Parse configuration files (zConfig.*.yaml):

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "parse-config",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Config file data
config_data = {
    "app_name": "MyApp",
    "version": "1.0.0",
    "features": {
        "auth": True,
        "api": True,
        "ui": True
    }
}

# Parse config file
parsed = z.parser.parse_config_file(config_data, file_path="zConfig.app.yaml")

print(f"App: {parsed['app_name']}")
print(f"Version: {parsed['version']}")
print(f"Features: {list(parsed['features'].keys())}")
```

**🎯 Try config file parsing:**

```bash
python3 Demos/Layer_2/zParser_Demo/lvl4_declarative/3_parse_config.py
```

[View demo source →](../../Demos/Layer_2/zParser_Demo/lvl4_declarative/3_parse_config.py)

**What you'll discover:**
- Parse configuration files (zConfig.*.yaml)
- Validate config structure
- Extract application settings
- Declarative app configuration

---

**🎯 Level 4 Complete!**

You've completed the zParser tutorial journey:
- ✅ **Level 0**: Hello zParser (Initialize zOS)
- ✅ **Level 1**: Path resolution (@, ~.zMachine, file identification)
- ✅ **Level 2**: File parsing (YAML, JSON, auto-detection)
- ✅ **Level 3**: Commands & expressions (command parsing, expression eval, plugin detection)
- ✅ **Level 4**: Declarative files (UI, Schema, Config parsing with validation)

**You now understand the complete zParser subsystem for parsing operations!**

---

## Module Structure

zParser follows a modular architecture with specialized components:

**Core Modules:**
- `zParser.py` - Main facade class providing unified interface
- `__init__.py` - Package exports and public API

**Parsing Modules:**
- `parser_path.py` - Path resolution (wrapper for path/ package)
- `parser_file.py` - File parsing (wrapper for file/ package)
- `parser_commands.py` - Command parsing (wrapper for commands/ package)
- `parser_plugin.py` - Plugin operations (wrapper for plugin/ package)
- `parser_utils.py` - Expression evaluation and utilities
- `parser_functions.py` - Function path parsing (for zFunc)
- `parser_trust.py` - Path-trust gate (zGuard seam; `verify_path_trust` / `PathTrustError`)
- `parser_constants.py` - Parser-internal constants and configuration

**Package Modules:**
- `path/` - Path operations (decoders, resolvers, detection, extraction)
- `file/` - File operations (parsers, format detection, transformers)
- `commands/` - Command operations (router, type-specific parsers)
- `plugin/` - Plugin syntax parsing primitives (detection, syntax, arguments)
- `vafile/` - zVaFile operations (UI, Schema, Config, Generic parsers)
- `shared/` - Argument splitting + constants; cross-subsystem vocab is single-sourced in root `zVocabulary` (`file_constants` re-exports historical names as back-compat aliases)

**Architecture Pattern:**
zParser uses the **Facade pattern** - a unified interface (`zParser` class) delegates to specialized modules:
- `z.parser.zPath_decoder()` → `parser_path.zPath_decoder()` → `path/path_decoder.py`
- `z.parser.parse_file_content()` → `parser_file.parse_file_content()` → `file/file_parser.py`
- `z.parser.parse_command()` → `parser_commands.parse_command()` → `commands/command_router.py`
- `z.parser.is_plugin_invocation()` → `plugin/plugin_detection.py`
- `z.parser.parse_plugin_invocation()` → `plugin/plugin_syntax.py`
- `z.parser.parse_ui_file()` → `vafile/vafile_ui.py` → `vafile/ui/ui_parser.py`

This separation allows each module to be tested and evolved independently while maintaining a stable public API.

**Plugin Execution Flow:**
For plugin execution (not just syntax parsing), zParser delegates to zFunc:
- `z.parser.resolve_plugin_invocation()` → `z.zfunc.execute_plugin()` → zFunc subsystem
- zFunc uses zParser's parsing primitives (`is_plugin_invocation`, `parse_plugin_invocation`, `parse_plugin_arguments`)
- zFunc handles loading, caching, and execution; zParser handles syntax parsing only

---

## Layer 2 Design Philosophy

As a **Layer 2 subsystem** (Handling), zParser has special design considerations:

**Depends on Lower Layers:**
- Uses zConfig (Layer 0) for configuration
- Uses zDisplay (Layer 1) for output
- Initialized after foundation layers

**Provides for Upper Layers:**
- **zLoader (Layer 2)**: File loading and caching
- **zFunc (Layer 2)**: Function path resolution, plugin syntax parsing primitives
- **zAuth (Layer 1)**: RBAC extraction from UI files
- **zShell (Layer 3)**: Command parsing and execution
- **zWalker (Layer 3)**: UI file parsing for navigation
- **zData (Layer 2)**: Schema file parsing
- **zDispatch (Layer 1)**: Plugin detection (delegates execution to zFunc)

**Mostly-Pure Parsing Layer:**
- Primarily transforms string content into structures
- File reads are limited to path resolution (`parse_file_by_path`, `handle_zRef`) and pass through the path-trust gate (zGuard seam)
- No execution logic (just structure extraction)
- No authentication (just RBAC extraction)
- Focuses on parsing, transformation, and gated path resolution

**Integration Points:**
- **Depends on:** zConfig, zDisplay, zLogger, zSession
- **Used by:** zLoader, zFunc, zAuth, zShell, zWalker, zData, zDispatch
- **Provides:** Path resolution, file parsing, command parsing, plugin detection, expression evaluation

---

## Advanced Features

### RBAC Transformation

zParser automatically extracts RBAC (Role-Based Access Control) sections from UI files:

```python
# UI file with RBAC
ui_data = {
    "UI": {
        "header": {"label": "Users"}
    },
    "RBAC": {
        "roles": ["admin", "user"],
        "permissions": ["read", "write"]
    }
}

# Parse with RBAC extraction
parsed = z.parser.parse_ui_file(ui_data, file_path="zUI.users.yaml")

# RBAC is extracted separately
ui_section = parsed['UI']       # Clean UI structure
rbac_section = parsed['RBAC']   # Security rules
```

**Use cases:** Security enforcement, permission checking, role validation.

For detailed documentation, see [vafile_GUIDE.md](zParser_Guides/vafile_GUIDE.md).

---

### Argument Splitting (Universal Primitive)

zParser provides a universal argument splitter that handles both brackets and quotes:

```python
from zOS.L2_Handling.d_zParser.parser_modules.shared import split_arguments

# Handles brackets: (), [], {}
args = split_arguments("func(a, b), [1, 2], arg3")
# → ['func(a, b)', ' [1, 2]', ' arg3']

# Handles quotes: ", '
args = split_arguments('"text, with, commas", arg2')
# → ['"text, with, commas"', ' arg2']

# Handles both simultaneously
args = split_arguments('func("a, b"), [1, 2], \'text\'')
# → ['func("a, b")', ' [1, 2]', " 'text'"]
```

**Features:**
- Bracket tracking: `()`, `[]`, `{}`
- Quote tracking: `"`, `'`
- Nested structures supported
- Validation of mismatched brackets/quotes
- Single Source of Truth (SSOT) for all argument parsing

**Used by:**
- zFunc argument parsing (`parse_arguments`)
- Plugin argument parsing (`parse_plugin_arguments`)
- Any subsystem needing comma-separated argument splitting

---

### Path Resolution Strategies

zParser supports multiple path resolution strategies:

**Workspace Paths (@):**
```python
# Relative to workspace root
path = z.parser.zPath_decoder("@data/users.json")
# → /Users/you/Projects/MyApp/data/users.json
```

**zMachine Paths (~.zMachine):**
```python
# System-specific paths
path = z.parser.zPath_decoder("~.zMachine.zConfigs")
# → ~/Library/Application Support/zOS/zConfigs/ (macOS)
# → ~/.local/share/zOS/zConfigs/ (Linux)
# → %APPDATA%/zOS/zConfigs/ (Windows)
```

**Symbol Paths:**
```python
# Resolve custom symbols
path = z.parser.resolve_symbol_path("$.my_symbol")
```

For detailed documentation, see [path_GUIDE.md](zParser_Guides/path_GUIDE.md).

---

### Security & trust (zGuard seam)

zParser resolves declarative paths and reads files off disk. Two layers keep this safe:

**Safe content parsing (always on):**
- YAML is parsed with `yaml.safe_load` only — no object construction, no code execution.
- JSON uses the stdlib `json` parser. Expression evaluation (`zExpr_eval`) never uses Python `eval`/`exec`; it parses JSON-like structures only.

**Path-trust gate (zGuard seam):**
Every resolved path that gets read passes through `verify_path_trust(path, zos, logger)` (`parser_modules/parser_trust.py`) before the file is touched — wired into `parse_file_by_path` and `handle_zRef`.

- **Open-core:** the gate is permissive (`try: from zguard.parser.path_trust… / except ImportError: return True`), so the public repo resolves any path and stays fully functional.
- **With zGuard installed:** the same seam is sealed with the real policy (workspace containment, allowed roots, `..` rejection, signature checks). A denied path raises `PathTrustError`, which propagates unwrapped — never swallowed or re-wrapped.

This mirrors the `loader_trust` seam in zLoader and the zAuth shims: one isolated boundary, no call-site changes between open-core and sealed builds.

---

### Constants & vocabulary (SSOT)

Parser-internal constants live in `parser_modules/shared/parser_constants.py` and the `vafile` package. **Cross-subsystem protocol vocabulary** — session-dict keys, file-type ids (`zUI`/`zSchema`/`zConfig`), path symbols (`@`, `~`), zMachine prefixes, and file-extension atoms — is single-sourced in the root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md) module. `shared/file_constants.py` imports these and re-exports its historical names (`SYMBOL_AT`, `FILE_TYPE_ZUI`, `ZMACHINE_PREFIX_SHORT`, …) as thin aliases, so existing call sites keep working while drift is eliminated.

---

## Facade API Reference

The `zParser` class provides these convenience methods:

**Path Resolution:**
```python
# Path operations
path = z.parser.zPath_decoder("@workspace/data.yaml")
path = z.parser.zPath_decoder("~.zMachine.Config")
file_type = z.parser.identify_zFile("zUI.users.yaml")
path = z.parser.resolve_zmachine_path("Config")
path = z.parser.resolve_symbol_path("$.symbol")
```

**File Parsing:**
```python
# File content parsing
data = z.parser.parse_file_content(content, extension=".yaml")
data = z.parser.parse_yaml(yaml_string)
data = z.parser.parse_json(json_string)
format = z.parser.detect_format(content)
data = z.parser.parse_file_by_path("/path/to/file.yaml")
data = z.parser.parse_json_expr('{"key": "value"}')
```

**Command Parsing:**
```python
# Command operations
cmd = z.parser.parse_command("zFunc users.list --limit 10")
# Returns: {"type": "zFunc", "path": "users.list", "arguments": {...}}
```

**Plugin Syntax Parsing:**
```python
# Plugin detection and syntax parsing
is_plugin = z.parser.is_plugin_invocation("&MyPlugin.func()")
plugin_name, func_name, args_str = z.parser.parse_plugin_invocation("&MyPlugin.func(arg=val)")
args, kwargs = z.parser.parse_plugin_arguments("arg1, key=val")

# For plugin execution (loading, caching), use zFunc:
result = z.parser.resolve_plugin_invocation("&MyPlugin.func()")  # Delegates to zFunc
# OR directly:
result = z.zfunc.execute_plugin("&MyPlugin.func()")
```

**Expression Evaluation:**
```python
# Expression operations
result = z.parser.zExpr_eval('{"key": "value"}')
parts = z.parser.parse_dotted_path("user.profile.name")
result = z.parser.handle_zRef("{{ref_key}}", context)
result = z.parser.handle_zParser("{{parser_directive}}", context)
```

**zVaFile Parsing:**
```python
# Declarative file parsing
ui = z.parser.parse_ui_file(ui_data, file_path="zUI.users.yaml")
schema = z.parser.parse_schema_file(schema_data, file_path="zSchema.users.yaml")
config = z.parser.parse_config_file(config_data, file_path="zConfig.app.yaml")
generic = z.parser.parse_generic_file(data, file_path="file.yaml")

# Validation and metadata
parsed = z.parser.parse_zva_file(data, file_path="file.yaml")
is_valid = z.parser.validate_zva_structure(data)
metadata = z.parser.extract_zva_metadata(data)
is_valid = z.parser.validate_ui_structure(ui_data)
is_valid = z.parser.validate_schema_structure(schema_data)
is_valid = z.parser.validate_config_structure(config_data)
```

**Function Path Parsing:**
```python
# Function path operations (for zFunc)
func_info = z.parser.parse_function_path("users.list")
# Returns: {"module": "users", "function": "list"}
```

---

## What's Next?

You've mastered **zParser** (Layer 2 parsing infrastructure). Now continue to other Layer 2 subsystems:

**→ Continue to [zLoader Guide](../L1_Foundation/zLoader_GUIDE.md)**

Layer 2 (Handling) includes:
- **zParser** - Parsing operations (path, file, command, plugin, expression)
- **zLoader** - File loading and caching (uses zParser)
- **zUtils** - Utility operations
- **zFunc** - Function execution (uses zParser for path resolution)

> **Note:** For command execution (not just parsing), see [zShell Guide](../L3_Abstraction/zShell_GUIDE.md) - a Layer 3 subsystem that uses zParser for command parsing before execution.

---

**[← Back to zComm Guide](../L1_Foundation/zComm_GUIDE.md) | [Home](../../README.md) | [Next: zLoader Guide →](../L1_Foundation/zLoader_GUIDE.md)**
