# zParser Plugin Module Guide

**[← Back to zParser Guide](../zParser_GUIDE.md)**

---

## Overview

The **plugin module** provides comprehensive plugin invocation capabilities:

- **Plugin detection** (`&PluginName.function()` syntax)
- **Plugin resolution** (execute plugin functions)
- **Argument parsing** (extract and parse plugin arguments)
- **Caching** (cache plugin results for performance)
- **Async support** (handle async plugin functions)

## Module Structure

The plugin module is organized into specialized submodules:

```
plugin/
├── plugin_detection.py    # Detect plugin invocations
├── plugin_syntax.py       # Parse plugin syntax
├── plugin_args.py         # Extract and parse arguments
├── plugin_resolver.py     # Resolve plugin references
├── plugin_executor.py     # Execute plugin functions
└── plugin_discovery.py    # Discover and load plugins
```

---

## Main Functions

### `is_plugin_invocation(text: str) -> bool`

Check if a string is a plugin invocation.

**Plugin Syntax:**
- Starts with `&` (ampersand)
- Format: `&PluginName.function(arg1, arg2, key=value)`

**Examples:**
```python
# Valid plugin invocations
z.parser.is_plugin_invocation("&MyPlugin.do_something()")
# → True

z.parser.is_plugin_invocation("&Users.list(limit=10)")
# → True

# Not plugin invocations
z.parser.is_plugin_invocation("regular_function()")
# → False

z.parser.is_plugin_invocation("some text")
# → False
```

---

### `resolve_plugin_invocation(invocation: str, logger, session, display) -> Any`

Resolve and execute a plugin invocation.

**Features:**
- Parses plugin name and function
- Extracts and validates arguments
- Executes plugin function
- Caches results (if plugin supports caching)
- Handles async plugin functions
- Auto-injects dependencies (logger, session, display)

**Examples:**
```python
# Simple plugin invocation
result = z.parser.resolve_plugin_invocation("&MyPlugin.greet()")

# Plugin with arguments
result = z.parser.resolve_plugin_invocation("&Users.list(limit=10, active=true)")

# Plugin with positional arguments
result = z.parser.resolve_plugin_invocation("&Math.add(5, 3)")
```

---

## Plugin Syntax

### Basic Format

```
&PluginName.function_name(arguments)
```

### Argument Types

**Positional arguments:**
```python
&Math.add(5, 3)
```

**Keyword arguments:**
```python
&Users.list(limit=10, active=true)
```

**Mixed arguments:**
```python
&Users.filter("admin", active=true, limit=5)
```

**String arguments:**
```python
&Users.search("John Doe")
&Users.filter('admin')
```

---

## Plugin Discovery

Plugins are discovered from configured plugin directories:

1. **Check workspace** - `./plugins/` directory
2. **Check system plugins** - `~.zMachine.plugins/` directory
3. **Check installed packages** - `zOS.plugins.*` namespace

**Plugin Structure:**
```python
# plugins/my_plugin.py

class MyPlugin:
    """Plugin class must match filename (my_plugin.py → MyPlugin)"""
    
    def __init__(self, logger, session, display):
        """Optional: Auto-injected dependencies"""
        self.logger = logger
        self.session = session
        self.display = display
    
    def greet(self, name="World"):
        """Plugin function"""
        return f"Hello, {name}!"
    
    async def async_function(self):
        """Async plugin functions supported"""
        await asyncio.sleep(1)
        return "Done"
```

---

## Argument Parsing

The plugin args parser supports various argument formats:

### Simple Arguments
```python
&Plugin.func(arg1, arg2)
# Parsed: ["arg1", "arg2"]
```

### Quoted Strings
```python
&Plugin.func("John Doe", 'Jane Smith')
# Parsed: ["John Doe", "Jane Smith"]
```

### Keyword Arguments
```python
&Plugin.func(name="Alice", age=30)
# Parsed: {"name": "Alice", "age": 30}
```

### Mixed Arguments
```python
&Plugin.func("Alice", age=30, active=true)
# Parsed: ["Alice"], {"age": 30, "active": true}
```

### Boolean/Number Values
```python
&Plugin.func(active=true, count=42, ratio=3.14)
# Parsed: {"active": True, "count": 42, "ratio": 3.14}
```

---

## Caching

Plugin resolution supports intelligent caching:

**Cache Key:** `plugin_name.function_name(args_hash)`

**Cache Behavior:**
- Same function + same arguments → cached result
- Different arguments → new execution
- Cache TTL (time-to-live) configurable per plugin
- Async-aware caching

**Example:**
```python
# First call - executes plugin
result1 = z.parser.resolve_plugin_invocation("&Math.fibonacci(10)")

# Second call - returns cached result
result2 = z.parser.resolve_plugin_invocation("&Math.fibonacci(10)")

# Different arguments - new execution
result3 = z.parser.resolve_plugin_invocation("&Math.fibonacci(20)")
```

**Disable Caching:**
```python
# Plugin can disable caching by setting cache=False
class MyPlugin:
    cache = False  # Disable caching for this plugin
```

---

## Async Support

Plugin functions can be async:

```python
class MyPlugin:
    async def fetch_data(self, url):
        """Async plugin function"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.json()
```

**Usage:**
```python
# zParser handles async automatically
result = await z.parser.resolve_plugin_invocation("&MyPlugin.fetch_data('https://api.example.com')")
```

---

## Dependency Injection

Plugins can receive auto-injected dependencies:

**Available Dependencies:**
- `logger` - Logger instance from zOS
- `session` - Session dict from zOS
- `display` - zDisplay instance from zOS

**Example:**
```python
class MyPlugin:
    def __init__(self, logger, session, display):
        """Dependencies auto-injected"""
        self.logger = logger
        self.session = session
        self.display = display
    
    def log_message(self, message):
        """Use injected logger"""
        self.logger.info(f"Plugin: {message}")
        return f"Logged: {message}"
```

---

## Error Handling

Plugin resolution handles errors gracefully:

```python
# Plugin not found
result = z.parser.resolve_plugin_invocation("&NonExistent.func()")
# Returns: None (logged error)

# Function not found
result = z.parser.resolve_plugin_invocation("&MyPlugin.nonexistent()")
# Returns: None (logged error)

# Invalid arguments
result = z.parser.resolve_plugin_invocation("&MyPlugin.func(invalid syntax")
# Returns: None (logged error)
```

---

## Use Cases

### 1. Data Transformation

```python
# Plugin for data transformation
class DataPlugin:
    def transform(self, data, format="json"):
        if format == "json":
            return json.dumps(data)
        elif format == "yaml":
            return yaml.dump(data)

# Usage
result = z.parser.resolve_plugin_invocation("&DataPlugin.transform(data, format='yaml')")
```

### 2. External API Integration

```python
# Plugin for API calls
class APIPlugin:
    async def fetch_users(self, limit=10):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.example.com/users?limit={limit}") as response:
                return await response.json()

# Usage
users = await z.parser.resolve_plugin_invocation("&APIPlugin.fetch_users(limit=20)")
```

### 3. Custom Business Logic

```python
# Plugin for business logic
class BusinessPlugin:
    def calculate_discount(self, price, customer_type):
        if customer_type == "premium":
            return price * 0.8
        elif customer_type == "regular":
            return price * 0.9
        return price

# Usage
discounted = z.parser.resolve_plugin_invocation("&BusinessPlugin.calculate_discount(100, 'premium')")
```

---

## Best Practices

1. **Use clear plugin names** - `Users`, `Data`, `API` (not `u`, `d`, `a`)
2. **Document plugin functions** - Add docstrings for clarity
3. **Handle errors in plugins** - Return `None` or raise clear exceptions
4. **Use dependency injection** - Access logger, session, display when needed
5. **Consider caching** - Cache expensive operations, disable for real-time data
6. **Support both sync and async** - Provide async versions for I/O operations

---

## Integration

The plugin module integrates with:

- **zDispatch** - Uses plugin resolution for command execution
- **zFunc** - Can invoke plugins from function calls
- **zShell** - Supports plugin invocations in commands
- **zWalker** - Uses plugins for custom UI behaviors
- **zData** - Uses plugins for data transformations

---

**[← Back to zParser Guide](../zParser_GUIDE.md)**
