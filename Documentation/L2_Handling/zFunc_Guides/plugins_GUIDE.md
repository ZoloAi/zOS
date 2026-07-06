# zFunc Plugin System Module Guide

> **Module:** `zOS/core/L2_Handling/i_zFunc/zFunc_modules/plugin_*`  
> **Purpose:** Plugin loading, caching, and execution for zFunc subsystem.

---

## Overview

The plugin system provides a unified, cached approach to loading and executing plugin functions. It consists of three modules working together:

| Module | File | Purpose |
|---|---|---|
| `plugin_resolver` | `plugin_resolver.py` | Main orchestrator for plugin lifecycle |
| `plugin_loader` | `plugin_loader.py` | Module loading and caching |
| `plugin_executor` | `plugin_executor.py` | Function execution with async support |

---

## Architecture Flow

```
resolve_plugin_invocation()              # Main entry point
    ↓
1. Parse syntax → zParser                 # "&plugin.func(args)"
    ↓
2. Load module → plugin_loader            # Filename-based cache lookup
    ↓
3. Get function → plugin_loader           # Extract callable from module
    ↓
4. Execute function → plugin_executor     # Sync/async execution with auto-injection
    ↓
5. Return result                          # Function return value
```

---

## `plugin_resolver`

Main orchestrator coordinating all plugin concerns: loading, parsing, and execution.

### Functions

#### `resolve_plugin_invocation(value: str, zos: Any, context: Optional[Any] = None) -> Any`

Resolve plugin function invocation with unified filename-based syntax.

⚠️ **CRITICAL**: This function is used externally by dispatch_launcher.py for ALL plugin invocations. Signature must remain stable.

```python
from zOS import zOS

z = zOS()

# Simple function call
result = resolve_plugin_invocation("&test_plugin.hello('Alice')", z)
# Returns: "Hello, Alice!"

# Function with integer argument
result = resolve_plugin_invocation("&math_utils.square(5)", z)
# Returns: 25

# Function with context (wizard integration)
context = {"zHat": {"step1": "data"}}
result = resolve_plugin_invocation("&wizard_plugin.process(context)", z, context)
```

**Parameters:**
- `value` (str): Plugin invocation string (e.g., "&test_plugin.hello('Alice')")
- `zos` (Any): zOS instance with zfunc.module_cache, parser, logger
- `context` (Optional[Any]): Optional context for wizard/hat access

**Process Flow:**
1. **Parse Syntax**: Delegate to zParser for syntax parsing
   - Extract plugin_name, function_name, args_str
2. **Load Module**: Load plugin module (with caching)
   - Filename-based cache lookup (O(1))
   - Search standard plugin paths if cache miss
3. **Get Function**: Retrieve callable from loaded module
4. **Parse Arguments**: Parse argument string
5. **Execute Function**: Call function (handles sync/async)
   - Auto-inject zos, context if needed
6. **Return Result**: Return function result

**Cache Strategy:**
- Filename-based caching for O(1) lookups via `zos.loader.cache.plugin_cache`
- Cache hit: Immediate function retrieval
- Cache miss: Search → Load → Cache → Execute
- Collision detection prevents duplicate filenames

**Async Support:**
- Automatically detects async functions (coroutines)
- CLI mode: Uses `asyncio.run()`
- Bifrost mode: Uses `run_coroutine_threadsafe()`
- 300-second timeout for async execution

**zOS Auto-Injection:**
- Inspects function signature for 'zos' parameter
- Automatically injects zos instance as kwarg
- Transparent to caller (no manual injection needed)

**Context Auto-Injection:**
- Inspects function signature for 'context' parameter
- Automatically injects context as kwarg
- Used for zWizard/zHat-specific plugins

**Returns:** Function result (type depends on function)

**Raises:** `ValueError` if syntax invalid, plugin not found, or execution fails

**Syntax:** `&PluginName.function_name(args)`

---

## `plugin_loader`

Handles plugin module discovery, loading, and caching.

### Functions

#### `load_plugin_module(plugin_name: str, zos: Any) -> Any`

Load plugin module by filename with caching.

```python
# Load plugin module
module = load_plugin_module("math_utils", zos)

# Access module functions
result = module.add(5, 3)
# Returns: 8
```

**Parameters:**
- `plugin_name` (str): Plugin filename (without .py), e.g., "test_plugin"
- `zos` (Any): zOS instance with loader.cache.plugin_cache

**Process Flow:**
1. **Check Cache**: Look up in `zos.loader.cache.plugin_cache`
   - Key: plugin_name (filename without .py)
2. **If Cache Hit**: Return cached module (fast path)
3. **If Cache Miss**:
   - Search standard plugin paths
   - Load module via importlib
   - Add to cache
   - Return module

**Standard Plugin Paths (search order):**
1. `zSpace/plugins/` - Project-specific plugins
2. `~/.config/zOS/plugins/` - User plugins (OS-native)
3. `zOS/plugins/` - Built-in plugins

**Returns:** Loaded module object

**Raises:** 
- `ValueError`: If plugin file not found in any search path
- `ImportError`: If module loading fails

**Caching:** Module cached in `zos.loader.cache.plugin_cache` with filename as key

---

#### `get_plugin_function(module: Any, func_name: str) -> Callable`

Extract callable function from loaded plugin module.

```python
# Load module
module = load_plugin_module("math_utils", zos)

# Get specific function
add_func = get_plugin_function(module, "add")

# Execute function
result = add_func(5, 3)
# Returns: 8
```

**Parameters:**
- `module` (Any): Loaded plugin module
- `func_name` (str): Name of function to extract

**Returns:** Callable function object

**Raises:** 
- `AttributeError`: If function not found in module
- `ValueError`: If attribute exists but is not callable

**Validation:** Checks `hasattr()` and `callable()` before returning

---

## `plugin_executor`

Executes plugin functions with auto-injection and async support.

### Functions

#### `execute_plugin_function(func: Callable, args: List[Any], zos: Any, context: Optional[Any] = None) -> Any`

Execute plugin function with auto-injection and async handling.

```python
# Get function
func = get_plugin_function(module, "process_data")

# Execute with auto-injection
result = execute_plugin_function(
    func,
    args=["input_data"],
    zos=zos,
    context={"key": "value"}
)
```

**Parameters:**
- `func` (Callable): Plugin function to execute
- `args` (List[Any]): Positional arguments
- `zos` (Any): zOS instance for auto-injection
- `context` (Optional[Any]): Optional context for auto-injection

**Process Flow:**
1. **Inspect Signature**: Check function parameters
2. **Build Kwargs**: Add zos, context if needed
3. **Call Function**: Execute with args + kwargs
4. **Check Async**: If coroutine returned, await it
5. **Return Result**: Return function result

**Auto-Injection:**
- `zos`: Injected if 'zos' parameter exists in signature
- `context`: Injected if 'context' parameter exists AND context provided

**Async Handling:**
- Detects coroutines via `inspect.iscoroutine()`
- CLI mode: `asyncio.run()` for standalone execution
- Bifrost mode: `run_coroutine_threadsafe()` for event loop integration
- 300-second timeout

**Returns:** Function result (type depends on function)

**Raises:** Any exception raised by function

---

## Plugin Caching Strategy

### Filename-Based Cache Keys

**Cache Key:** Plugin filename (without .py extension)

```python
# Plugin file: /path/to/plugins/math_utils.py
# Cache key: "math_utils"

# First call: Load from disk and cache
module1 = load_plugin_module("math_utils", zos)  # ~50ms (disk I/O)

# Subsequent calls: O(1) cache lookup
module2 = load_plugin_module("math_utils", zos)  # ~1ms (memory lookup)

# Same module object
assert module1 is module2  # True
```

**Advantages:**
- Fast lookups: O(1) dictionary access
- Path-independent: Works regardless of plugin location
- Simple API: Just use plugin name, not full path

---

### Collision Detection

**Problem:** Multiple plugins with same filename in different directories

```python
# /project1/plugins/utils.py
def func1(): return "project1"

# /project2/plugins/utils.py
def func2(): return "project2"
```

**Solution:** Collision detection prevents ambiguity

```python
# First load: OK
module1 = load_plugin_module("utils", zos)  # Loaded from /project1/plugins/utils.py

# Second load from different path: Warning + returns cached
module2 = load_plugin_module("utils", zos)  # Returns cached, logs collision warning
```

**Recommendation:** Use unique plugin filenames across all projects

---

### Cache Invalidation

**Development Mode:**
```python
# Clear cache entry
del zos.loader.cache.plugin_cache["math_utils"]

# Reload plugin
module = load_plugin_module("math_utils", zos)  # Fresh load from disk
```

**Production Mode:**
- Plugins loaded once at startup
- Changes require application restart
- Cache persists for application lifetime

---

## Standard Plugin Paths

Plugins searched in this order:

### 1. Project Plugins (Highest Priority)

**Path:** `{zSpace}/plugins/`
- `zSpace`: Current workspace directory (from zConfig)
- **Use case:** Project-specific plugins
- **Example:** `/home/user/my_project/plugins/project_utils.py`

### 2. User Plugins

**Path:** `~/.config/zOS/plugins/` (Linux/macOS) or `%APPDATA%\zOS\plugins\` (Windows)
- OS-native user config directory
- **Use case:** Personal plugins shared across projects
- **Example:** `/home/user/.config/zOS/plugins/my_helpers.py`

### 3. Built-in Plugins (Lowest Priority)

**Path:** `{zOS_install}/plugins/`
- zOS installation directory
- **Use case:** Framework-provided plugins
- **Example:** `/usr/local/lib/python3.12/site-packages/zOS/plugins/system_utils.py`

**Search stops at first match.** If `utils.py` exists in both project and user directories, project version is used.

---

## Practical Examples

### Example 1: Basic Plugin Call

```python
# Plugin file: plugins/greetings.py
def hello(name):
    """Say hello to someone."""
    return f"Hello, {name}!"

# Execute plugin
from zOS import zOS
z = zOS()

result = z.zfunc.execute_plugin("&greetings.hello('Alice')")
# Returns: "Hello, Alice!"
```

---

### Example 2: Plugin with zOS Auto-Injection

```python
# Plugin file: plugins/config_reader.py
def get_setting(key, zos):
    """Read setting from zConfig."""
    return zos.config.get(key)

# Execute plugin (zos automatically injected)
result = z.zfunc.execute_plugin("&config_reader.get_setting('deployment')")
# Returns: "Production"
```

---

### Example 3: Async Plugin

```python
# Plugin file: plugins/api_client.py
async def fetch_user(user_id, zos):
    """Fetch user from API."""
    url = f"https://api.example.com/users/{user_id}"
    response = await zos.comm.http_get(url)
    return response.json()

# Execute plugin (async automatically handled)
result = z.zfunc.execute_plugin("&api_client.fetch_user(42)")
# Coroutine automatically awaited
# Returns: {"id": 42, "name": "Alice", ...}
```

---

### Example 4: Plugin with Context (Wizard Integration)

```python
# Plugin file: plugins/wizard_utils.py
def process_step(context):
    """Process wizard step with context."""
    hat = context.get("zHat", {})
    previous = hat.get("step1", "")
    return {"step2": f"Processed {previous}"}

# Execute in wizard
context = {"zHat": {"step1": "input_data"}}
result = z.zfunc.execute_plugin("&wizard_utils.process_step(context)", context)
# Returns: {"step2": "Processed input_data"}
```

---

### Example 5: Multiple Functions in One Plugin

```python
# Plugin file: plugins/math_utils.py
def add(a, b):
    """Add two numbers."""
    return a + b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b

def power(base, exp):
    """Raise base to exponent."""
    return base ** exp

# Use different functions from same plugin
result1 = z.zfunc.execute_plugin("&math_utils.add(5, 3)")        # 8
result2 = z.zfunc.execute_plugin("&math_utils.multiply(5, 3)")  # 15
result3 = z.zfunc.execute_plugin("&math_utils.power(2, 8)")     # 256

# Module loaded once, cached for subsequent calls
```

---

### Example 6: Direct Module Loading

```python
# Load plugin module directly
module = z.zfunc.load_plugin("math_utils")

# Access module functions
result1 = module.add(5, 3)
result2 = module.multiply(5, 3)
result3 = module.power(2, 8)

# No parsing overhead, direct function calls
```

---

### Example 7: Plugin Search Path Priority

```python
# Create plugins in different locations:

# 1. Project plugin (highest priority)
# /home/user/project/plugins/utils.py
def helper(): return "project"

# 2. User plugin
# ~/.config/zOS/plugins/utils.py
def helper(): return "user"

# 3. Built-in plugin (lowest priority)
# /usr/local/.../zOS/plugins/utils.py
def helper(): return "builtin"

# Execute plugin
result = z.zfunc.execute_plugin("&utils.helper()")
# Returns: "project" (highest priority wins)

# Remove project plugin
os.remove("/home/user/project/plugins/utils.py")
del zos.loader.cache.plugin_cache["utils"]  # Clear cache

# Execute again
result = z.zfunc.execute_plugin("&utils.helper()")
# Returns: "user" (next priority)
```

---

### Example 8: Error Handling

```python
# Plugin not found
try:
    result = z.zfunc.execute_plugin("&missing_plugin.func()")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Plugin file 'missing_plugin.py' not found in any search path

# Function not found
try:
    result = z.zfunc.execute_plugin("&math_utils.missing_func()")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Function 'missing_func' not found in module 'math_utils'

# Invalid syntax
try:
    result = z.zfunc.execute_plugin("math_utils.func()")  # Missing &
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Invalid plugin syntax
```

---

## Plugin Development Best Practices

### 1. Plugin Structure

```python
# Good: Clear function names, docstrings, type hints
def process_data(data: dict, zos) -> dict:
    """
    Process data using zOS configuration.
    
    Args:
        data: Input data dictionary
        zos: zOS instance (auto-injected)
        
    Returns:
        Processed data dictionary
    """
    setting = zos.config.get("processing_mode")
    return {"result": f"Processed in {setting} mode"}
```

---

### 2. Unique Names

```python
# Bad: Generic names (collision risk)
# plugins/utils.py

# Good: Specific names
# plugins/project_utils.py
# plugins/api_utils.py
# plugins/db_utils.py
```

---

### 3. Error Handling

```python
def safe_divide(a, b, zos):
    """Divide with error handling."""
    try:
        if b == 0:
            zos.logger.warning("Division by zero attempted")
            return None
        return a / b
    except Exception as e:
        zos.logger.error(f"Division failed: {e}")
        raise
```

---

### 4. Async When Appropriate

```python
# Sync for CPU-bound operations
def calculate(data):
    """Fast calculation."""
    return sum(data)

# Async for I/O-bound operations
async def fetch_data(url, zos):
    """Fetch from API."""
    return await zos.comm.http_get(url)
```

---

### 5. Context Validation

```python
def wizard_step(context):
    """Process wizard step."""
    # Validate context structure
    if not isinstance(context, dict):
        raise ValueError("Context must be dict")
    
    hat = context.get("zHat")
    if not hat:
        raise ValueError("zHat not found in context")
    
    # Process with validated context
    return {"result": hat.get("step1")}
```

---

## Integration with zFunc

**zFunc provides two entry points for plugins:**

```python
# Method 1: execute_plugin (parse + load + execute)
result = z.zfunc.execute_plugin("&plugin.func(args)", context)

# Method 2: load_plugin (manual execution)
module = z.zfunc.load_plugin("plugin")
result = module.func(*args)
```

**Complete flow in execute_plugin:**
```python
# zFunc.py
def execute_plugin(self, value: str, context=None):
    from .zFunc_modules.plugin_resolver import resolve_plugin_invocation
    return resolve_plugin_invocation(value, self.zos, context)

# plugin_resolver.py
def resolve_plugin_invocation(value, zos, context):
    # 1. Parse syntax
    plugin_name, func_name, args_str = parse(value)
    
    # 2. Load module
    module = load_plugin_module(plugin_name, zos)
    
    # 3. Get function
    func = get_plugin_function(module, func_name)
    
    # 4. Parse arguments
    args = parse_args(args_str)
    
    # 5. Execute function
    result = execute_plugin_function(func, args, zos, context)
    
    return result
```

---

## Integration with zLoader

Plugin caching delegates to zLoader's unified cache:

```python
# zFunc uses zLoader's plugin cache
cache = zos.loader.cache.plugin_cache

# Add to cache
cache["math_utils"] = module

# Retrieve from cache
module = cache.get("math_utils")

# Clear cache
del cache["math_utils"]
```

For detailed documentation, see [zLoader Guide](../../L1_Foundation/zLoader_GUIDE.md).

---

## Best Practices Summary

1. **Naming:**
   - Use unique, descriptive plugin names
   - Avoid generic names (utils, helpers, common)
   - Follow Python naming conventions (snake_case)

2. **Structure:**
   - One plugin per file
   - Related functions in same plugin
   - Clear function signatures with type hints
   - Comprehensive docstrings

3. **Dependencies:**
   - Request only needed dependencies (zos, context)
   - Document required context structure
   - Validate inputs in plugin functions

4. **Error Handling:**
   - Validate inputs before processing
   - Catch exceptions in plugin functions
   - Log errors using zos.logger
   - Provide meaningful error messages

5. **Performance:**
   - Leverage caching (functions called multiple times)
   - Use async for I/O operations
   - Avoid expensive imports in plugin global scope
   - Profile plugins for bottlenecks

6. **Testing:**
   - Test with valid and invalid arguments
   - Test with missing context
   - Test async timeout scenarios
   - Test error conditions
   - Mock zos instance for unit tests

---

## Version History

- **v1.6.0**: Plugin system consolidation
  - Moved from zParser to zFunc
  - Created plugin_resolver orchestrator
  - Integrated with zLoader's unified cache
  - Added collision detection
  - Standardized search paths
