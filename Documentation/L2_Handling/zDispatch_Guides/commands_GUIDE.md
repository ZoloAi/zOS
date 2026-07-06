**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**

---

# Command Parsing

**Command modules** parse string-based commands (like `"zFunc(...)"`) and array commands, converting them to structured formats for subsystem routing.

## Overview

| Module | Purpose | Example |
|--------|---------|---------|
| **StringCommandHandler** | Parse function-call syntax | `"zFunc(my_function, arg1, arg2)"` |
| **ListCommandHandler** | Process array commands | `[{cmd1}, {cmd2}, {cmd3}]` |
| **WizardDetector** | Detect wizard invocations | `"zWizard(setup)"` |

---

## StringCommandHandler

**Parses string commands using function-call syntax.**

### Purpose

Convert imperative string commands (`"zFunc(...)"`) into structured dict commands that can be routed to subsystems.

### Supported Formats

```python
# Function invocation
"zFunc(my_function)"
"zFunc(calculate, x=10, y=5)"
"zFunc(&plugin.func, arg1, arg2)"

# Link navigation
"zLink(/dashboard)"
"zLink(/users/123)"

# Open resource
"zOpen(file.txt)"
"zOpen(https://example.com)"

# Wizard invocation
"zWizard(setup_wizard)"
"zWizard(onboarding, user_id=123)"

# Read operation
"zRead(users, where={'id': 1})"
```

### Parsing Logic

```python
class StringCommandHandler:
    PREFIXES = {
        "zFunc(": "zFunc",
        "zLink(": "zLink",
        "zOpen(": "zOpen",
        "zWizard(": "zWizard",
        "zRead(": "zRead",
    }
    
    def parse_string_command(self, command_str):
        """Parse string command into dict format."""
        # Detect command type
        cmd_type = None
        for prefix, type_name in self.PREFIXES.items():
            if command_str.startswith(prefix):
                cmd_type = type_name
                break
        
        if not cmd_type:
            return None
        
        # Extract content between parentheses
        content = command_str[len(prefix):-1]  # Remove prefix and trailing )
        
        # Parse arguments
        func_name, args, kwargs = self._parse_arguments(content)
        
        # Build structured command
        return {
            cmd_type: func_name,
            "args": args,
            "kwargs": kwargs
        }
    
    def _parse_arguments(self, content):
        """Parse function name and arguments."""
        # Split on first comma (if exists)
        parts = content.split(",", 1)
        func_name = parts[0].strip()
        
        if len(parts) == 1:
            return func_name, [], {}
        
        # Parse args and kwargs from remaining string
        arg_str = parts[1].strip()
        args, kwargs = self._eval_arguments(arg_str)
        
        return func_name, args, kwargs
```

### Examples

#### Simple Function

```python
# Input
"zFunc(greet)"

# Parsed
{
    "zFunc": "greet",
    "args": [],
    "kwargs": {}
}
```

#### Function with Arguments

```python
# Input
"zFunc(calculate, 10, 5, operation='add')"

# Parsed
{
    "zFunc": "calculate",
    "args": [10, 5],
    "kwargs": {"operation": "add"}
}
```

#### Plugin Invocation

```python
# Input
"zFunc(&analytics.generate_report, 'monthly')"

# Parsed
{
    "zFunc": "&analytics.generate_report",
    "args": ["monthly"],
    "kwargs": {}
}
```

#### Wizard with Context

```python
# Input
"zWizard(onboarding, user_id=123, step='welcome')"

# Parsed
{
    "zWizard": "onboarding",
    "args": [],
    "kwargs": {"user_id": 123, "step": "welcome"}
}
```

### Integration

```python
# In CommandLauncher._launch_string()
if command_str.startswith(("zFunc(", "zWizard(", ...)):
    parsed = self.string_handler.parse_string_command(command_str)
    if parsed:
        # Route to _launch_dict() with parsed structure
        return self._launch_dict(parsed, context, walker)
```

---

## ListCommandHandler

**Processes array commands by iterating and dispatching each item.**

### Purpose

Handle batch operations where multiple commands are provided as a list.

### Supported Formats

```python
# Array of dict commands
[
    {"zFunc": "action1"},
    {"zFunc": "action2"},
    {"zData": {"action": "read", "model": "users"}}
]

# Array of string commands
[
    "zFunc(action1)",
    "zFunc(action2)",
    "zRead(users)"
]

# Mixed array
[
    {"zFunc": "action1"},
    "zFunc(action2)",
    {"zData": {...}}
]
```

### Processing Logic

```python
class ListCommandHandler:
    def process_list(self, command_list, context=None, walker=None):
        """Process array of commands sequentially."""
        results = []
        
        for item in command_list:
            # Dispatch each item
            result = self.launcher.launch(item, context=context, walker=walker)
            results.append(result)
        
        return results
```

### Examples

#### Batch Actions

```python
# Input
commands = [
    {"zFunc": "validate_user"},
    {"zFunc": "process_payment"},
    {"zFunc": "send_confirmation"}
]

# Execute
result = z.dispatch.handle("batch", commands)

# Returns
[
    True,  # validate_user result
    {"transaction_id": "abc123"},  # process_payment result
    None   # send_confirmation result
]
```

#### Mixed Commands

```python
# Input
commands = [
    "zFunc(step1)",
    {"zData": {"action": "create", "model": "log", "values": {...}}},
    "zFunc(step3)"
]

# Execute sequentially
results = z.dispatch.handle("workflow", commands)
```

### Integration

```python
# In CommandLauncher.launch()
if isinstance(zHorizontal, list):
    return self._launch_list(zHorizontal, context, walker)

def _launch_list(self, horizontal, context, walker):
    return self.list_handler.process_list(horizontal, context, walker)
```

---

## WizardDetector

**Detects wizard invocations in string and dict formats.**

### Purpose

Identify wizard commands and extract wizard name and context for routing to zWizard subsystem.

### Detection Patterns

```python
# String format
"zWizard(setup_wizard)"
"zWizard(onboarding, user_id=123)"

# Dict format
{"zWizard": "setup_wizard"}
{"zWizard": "setup_wizard", "context": {"user_id": 123}}

# Auto-detected wizard dict
{
    "wizard": "setup_wizard",
    "steps": [...]
}
```

### Detection Logic

```python
class WizardDetector:
    def is_wizard_string(self, command_str):
        """Check if string is wizard invocation."""
        return isinstance(command_str, str) and command_str.startswith("zWizard(")
    
    def is_wizard_dict(self, command_dict):
        """Check if dict is wizard invocation."""
        if not isinstance(command_dict, dict):
            return False
        
        # Explicit zWizard key
        if "zWizard" in command_dict:
            return True
        
        # Auto-detected wizard structure
        if "wizard" in command_dict and "steps" in command_dict:
            return True
        
        return False
    
    def extract_wizard_info(self, command):
        """Extract wizard name and context."""
        if isinstance(command, str):
            # Parse string: "zWizard(name, key=val)"
            return self._parse_wizard_string(command)
        elif isinstance(command, dict):
            # Extract from dict
            wizard_name = command.get("zWizard") or command.get("wizard")
            context = command.get("context", {})
            return wizard_name, context
        
        return None, {}
```

### Examples

#### String Detection

```python
# Input
"zWizard(setup_wizard)"

# Detected
is_wizard = detector.is_wizard_string(command)  # True
wizard_name, context = detector.extract_wizard_info(command)
# wizard_name: "setup_wizard"
# context: {}
```

#### Dict Detection

```python
# Input
{
    "zWizard": "onboarding",
    "context": {"user_id": 123}
}

# Detected
is_wizard = detector.is_wizard_dict(command)  # True
wizard_name, context = detector.extract_wizard_info(command)
# wizard_name: "onboarding"
# context: {"user_id": 123}
```

#### Auto-Detected Structure

```python
# Input
{
    "wizard": "setup_wizard",
    "steps": [
        {"name": "step1", "action": {...}},
        {"name": "step2", "action": {...}}
    ]
}

# Detected
is_wizard = detector.is_wizard_dict(command)  # True
```

### Integration

```python
# In CommandLauncher._launch_string()
if self.wizard_detector.is_wizard_string(command_str):
    wizard_name, context = self.wizard_detector.extract_wizard_info(command_str)
    return self.subsystem_router.route_zwizard(wizard_name, context, walker)

# In CommandLauncher._launch_dict()
if self.wizard_detector.is_wizard_dict(command_dict):
    wizard_name, context = self.wizard_detector.extract_wizard_info(command_dict)
    return self.subsystem_router.route_zwizard(wizard_name, context, walker)
```

---

## Parsing Flow

```
String Command
    ↓
StringCommandHandler.parse_string_command()
    ↓
[Detect Prefix]
    ├─ zFunc( → Parse function name + args
    ├─ zWizard( → WizardDetector.extract_wizard_info()
    ├─ zLink( → Parse link path
    └─ zRead( → Parse model + query
    ↓
Structured Dict Command
    ↓
Route to _launch_dict()
    ↓
Subsystem Routing
```

---

## Error Handling

All parsers handle errors gracefully:

```python
# Invalid syntax
command = "zFunc(incomplete"
result = parser.parse_string_command(command)
# Returns: None (logs error)

# Unknown prefix
command = "zUnknown(action)"
result = parser.parse_string_command(command)
# Returns: None

# Empty list
commands = []
result = list_handler.process_list(commands)
# Returns: [] (empty results)

# Non-command in list
commands = [{"invalid": "data"}, {"zFunc": "valid"}]
results = list_handler.process_list(commands)
# Returns: [None, <valid result>]
```

---

## Best Practices

### Use Structured Dicts

```python
# ✅ Good: Structured dict (easier to build programmatically)
command = {
    "zFunc": "calculate",
    "args": [10, 5],
    "kwargs": {"operation": "add"}
}

# ❌ Bad: String with complex args (harder to construct)
command = "zFunc(calculate, 10, 5, operation='add')"
```

### Batch Related Actions

```python
# ✅ Good: Use list for related actions
commands = [
    {"zFunc": "validate"},
    {"zFunc": "process"},
    {"zFunc": "notify"}
]
z.dispatch.handle("workflow", commands)

# ❌ Bad: Separate dispatch calls
z.dispatch.handle("validate", {"zFunc": "validate"})
z.dispatch.handle("process", {"zFunc": "process"})
z.dispatch.handle("notify", {"zFunc": "notify"})
```

### Wizard Detection

```python
# ✅ Good: Explicit zWizard key
{"zWizard": "setup", "context": {...}}

# ✅ Also Good: Auto-detected structure
{"wizard": "setup", "steps": [...]}

# ❌ Bad: Ambiguous structure
{"name": "setup", "data": [...]}  # Not detected as wizard
```

---

**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**
