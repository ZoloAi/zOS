# zParser Commands Module Guide

**[← Back to zParser Guide](../zParser_GUIDE.md)**

---

## Overview

The **commands module** provides comprehensive command parsing capabilities:

- **20+ command types** (zFunc, zLink, zOpen, zFile, zData, etc.)
- **Argument extraction** (flags, options, values)
- **Quote handling** (preserve quoted strings)
- **Command routing** (dispatch to type-specific parsers)
- **Validation** (check command syntax)

## Module Structure

The commands module is organized into specialized submodules:

```
commands/
├── command_router.py       # Main routing logic
├── command_utils.py        # Parsing utilities
├── config_commands.py      # zConfig command parser
├── data_commands.py        # zData command parser
├── file_commands.py        # zFile command parser
├── function_commands.py    # zFunc command parser
├── session_commands.py     # zSession command parser
├── system_commands.py      # System command parser
└── ui_commands.py          # zUI command parser
```

---

## Main Function

### `parse_command(command_str: str, logger) -> Dict[str, Any]`

Parse command string into structured format.

**Returns:**
```python
{
    "type": str,           # Command type (zFunc, zLink, etc.)
    "path": str,           # Command path (e.g., "users.list")
    "arguments": dict,     # Parsed arguments
    "raw": str,            # Original command string
    "valid": bool          # Whether command is valid
}
```

**Examples:**
```python
# zFunc command
cmd = z.parser.parse_command("zFunc users.list --limit 10 --active true")
# Returns:
# {
#     "type": "zFunc",
#     "path": "users.list",
#     "arguments": {"limit": "10", "active": "true"},
#     "raw": "zFunc users.list --limit 10 --active true",
#     "valid": True
# }

# zFile command
cmd = z.parser.parse_command("zFile read @data/users.json")
# Returns:
# {
#     "type": "zFile",
#     "path": "read",
#     "arguments": {"file": "@data/users.json"},
#     "raw": "zFile read @data/users.json",
#     "valid": True
# }
```

---

## Supported Command Types

### 1. zFunc - Function Invocation

Execute functions from loaded modules.

**Format:** `zFunc <module>.<function> [--arg value]`

**Examples:**
```python
cmd = z.parser.parse_command("zFunc users.list")
cmd = z.parser.parse_command("zFunc users.get --id 123")
cmd = z.parser.parse_command("zFunc auth.login --username alice --password secret")
```

---

### 2. zLink - Navigation Linking

Navigate to UI elements or pages.

**Format:** `zLink <target> [--mode <mode>]`

**Examples:**
```python
cmd = z.parser.parse_command("zLink users.table")
cmd = z.parser.parse_command("zLink dashboard --mode overlay")
cmd = z.parser.parse_command("zLink @users/profile.yaml")
```

---

### 3. zOpen - File/UI Opening

Open files or UI definitions.

**Format:** `zOpen <path> [--mode <mode>]`

**Examples:**
```python
cmd = z.parser.parse_command("zOpen @data/config.yaml")
cmd = z.parser.parse_command("zOpen zUI.users --mode edit")
cmd = z.parser.parse_command("zOpen ~.zMachine.Config")
```

---

### 4. zFile - File Operations

Perform file operations (read, write, delete, etc.).

**Format:** `zFile <operation> <path> [--options]`

**Examples:**
```python
cmd = z.parser.parse_command("zFile read @data/users.json")
cmd = z.parser.parse_command("zFile write @data/output.json --data '{}'")
cmd = z.parser.parse_command("zFile delete @temp/cache.json")
cmd = z.parser.parse_command("zFile list @data/ --pattern *.yaml")
```

---

### 5. zConfig - Configuration Access

Access or modify configuration values.

**Format:** `zConfig <action> [<key>] [<value>]`

**Examples:**
```python
cmd = z.parser.parse_command("zConfig get deployment")
cmd = z.parser.parse_command("zConfig set logger DEBUG")
cmd = z.parser.parse_command("zConfig list")
cmd = z.parser.parse_command("zConfig machine cpu_cores")
```

---

### 6. zData - Data Operations

Perform database/data operations.

**Format:** `zData <operation> <target> [--options]`

**Examples:**
```python
cmd = z.parser.parse_command("zData query users --limit 10")
cmd = z.parser.parse_command("zData insert users --data '{}'")
cmd = z.parser.parse_command("zData update users --id 123 --data '{}'")
cmd = z.parser.parse_command("zData delete users --id 123")
```

---

### 7. zSession - Session Management

Manage session state and variables.

**Format:** `zSession <action> [<key>] [<value>]`

**Examples:**
```python
cmd = z.parser.parse_command("zSession get user_id")
cmd = z.parser.parse_command("zSession set theme dark")
cmd = z.parser.parse_command("zSession clear")
cmd = z.parser.parse_command("zSession list")
```

---

### 8. zUI - UI Rendering

Render UI elements or components.

**Format:** `zUI <component> [--props]`

**Examples:**
```python
cmd = z.parser.parse_command("zUI header --label Users")
cmd = z.parser.parse_command("zUI table --columns name,email,role")
cmd = z.parser.parse_command("zUI button --text Submit --action save")
```

---

## Argument Parsing

### Flag Arguments

Flags start with `--` and have values:

```python
cmd = z.parser.parse_command("zFunc users.list --limit 10 --active true")
# arguments: {"limit": "10", "active": "true"}
```

### Quoted Arguments

Preserve spaces in quoted strings:

```python
cmd = z.parser.parse_command('zFunc users.search --query "John Doe"')
# arguments: {"query": "John Doe"}

cmd = z.parser.parse_command("zFunc users.create --name 'Jane Smith'")
# arguments: {"name": "Jane Smith"}
```

### Boolean Flags

Flags without values default to `True`:

```python
cmd = z.parser.parse_command("zFunc users.list --active")
# arguments: {"active": True}
```

### Multiple Values

Space-separated values:

```python
cmd = z.parser.parse_command("zUI table --columns name email role")
# arguments: {"columns": "name email role"}
```

---

## Command Routing

The command router dispatches to type-specific parsers:

```
parse_command()
    ↓
command_router.route()
    ↓
├─ zFunc → function_commands.parse_zfunc()
├─ zFile → file_commands.parse_zfile()
├─ zConfig → config_commands.parse_zconfig()
├─ zData → data_commands.parse_zdata()
├─ zSession → session_commands.parse_zsession()
└─ zUI → ui_commands.parse_zui()
```

Each type-specific parser:
1. Validates command syntax
2. Extracts command path
3. Parses arguments
4. Returns structured dict

---

## Command Validation

Commands are validated for:

1. **Type recognition** - Is command type supported?
2. **Syntax validity** - Proper format for command type?
3. **Required arguments** - Are required args present?
4. **Argument types** - Are arg values valid?

**Example:**
```python
# Valid command
cmd = z.parser.parse_command("zFunc users.list --limit 10")
# cmd["valid"] = True

# Invalid command (missing path)
cmd = z.parser.parse_command("zFunc")
# cmd["valid"] = False
```

---

## Complex Examples

### Multi-Argument Commands

```python
cmd = z.parser.parse_command("""
zFunc users.create
  --name "John Doe"
  --email john@example.com
  --role admin
  --active true
""")
# arguments: {
#     "name": "John Doe",
#     "email": "john@example.com",
#     "role": "admin",
#     "active": "true"
# }
```

### Path with Arguments

```python
cmd = z.parser.parse_command("zOpen @configs/app.yaml --mode edit --readonly false")
# {
#     "type": "zOpen",
#     "path": "@configs/app.yaml",
#     "arguments": {"mode": "edit", "readonly": "false"}
# }
```

### Complex Queries

```python
cmd = z.parser.parse_command('zData query users --filter "role=admin" --sort created_at --limit 50')
# arguments: {
#     "filter": "role=admin",
#     "sort": "created_at",
#     "limit": "50"
# }
```

---

## Error Handling

Command parsing handles errors gracefully:

```python
# Unknown command type
cmd = z.parser.parse_command("zUnknown something")
# Returns: {"type": None, "valid": False, "error": "Unknown command type"}

# Invalid syntax
cmd = z.parser.parse_command("zFunc")
# Returns: {"type": "zFunc", "valid": False, "error": "Missing function path"}

# Malformed arguments
cmd = z.parser.parse_command("zFunc users.list --limit")
# Returns: {"type": "zFunc", "valid": False, "error": "Flag missing value"}
```

---

## Use Cases

### 1. Shell Command Execution

```python
# User input from shell
command_str = input("zOS> ")

# Parse command
cmd = z.parser.parse_command(command_str)

# Route to executor
if cmd["type"] == "zFunc":
    result = execute_zfunc(cmd["path"], cmd["arguments"])
elif cmd["type"] == "zFile":
    result = execute_zfile(cmd["path"], cmd["arguments"])
```

### 2. UI Action Handling

```python
# Button click action
button_action = "zFunc users.delete --id 123"

# Parse and execute
cmd = z.parser.parse_command(button_action)
if cmd["valid"]:
    execute_command(cmd)
```

### 3. Wizard Step Execution

```python
# Wizard step command
step_command = "zData insert users --data '{{form_data}}'"

# Parse command
cmd = z.parser.parse_command(step_command)

# Replace placeholders and execute
cmd["arguments"]["data"] = form_data
execute_command(cmd)
```

---

## Best Practices

1. **Use clear command names** - Follow zOS conventions (zFunc, zFile, etc.)
2. **Quote complex values** - Use quotes for strings with spaces
3. **Validate before execution** - Check `cmd["valid"]` before executing
4. **Handle errors gracefully** - Commands may fail parsing
5. **Use consistent argument names** - `--limit`, `--id`, `--active` (not `--l`, `--i`, `--a`)

---

## Integration

The commands module integrates with:

- **zShell** - Uses command parsing for interactive shell
- **zWalker** - Uses command parsing for UI actions
- **zDispatch** - Routes parsed commands to executors
- **zWizard** - Uses command parsing for wizard steps
- **zFunc** - Executes zFunc commands

---

**[← Back to zParser Guide](../zParser_GUIDE.md)**
