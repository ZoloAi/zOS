# zFunc Function Resolution Module Guide

> **Module:** `zOS/core/L2_Handling/i_zFunc/zFunc_modules/func_resolver.py`  
> **Purpose:** Dynamic Python/JS function resolution for zFunc — **routed through zLoader's plugin-trust gate**.

---

## Overview

The `func_resolver` module provides the foundation for dynamically loading Python functions from external files using importlib. It enables runtime function resolution without requiring modules to be pre-imported.

**Key Functionality:**
- Dynamic module loading from Python files
- Function extraction from loaded modules
- Robust validation (file existence, module spec, loader, function existence)
- Comprehensive error handling (FileNotFoundError, ImportError, AttributeError)
- Automatic logging of resolution steps

---

## Security Considerations

⚠️ **IMPORTANT**: This module loads and executes arbitrary Python/JS files.

**Single trust door.** Loading does **not** happen via a bare `importlib` call.
When a `zos` instance is available (the normal case — `zFunc` passes `self.zos`),
the Python load is delegated to `zos.loader.load_python_module`, which runs
`verify_plugin_trust(file_path, zos, logger)` — the same zGuard seam that gates
the `&plugin` syntax path — **before any code executes**. JavaScript files are
routed to `func_js_executor`, which gates the same way before spawning Node.
Standalone callers that pass no `zos` still hit the gate directly before
`exec_module`.

**Posture:**
- **Open-core:** `verify_plugin_trust` is a permissive no-op — loads from any path.
- **With zGuard:** the seam is sealed (allowed dirs / signatures); a denied path
  raises `PluginTrustError`, which propagates unwrapped (code never runs — fails
  closed). The policy is **proprietary — see the private zGuard docs**.

This is why callers should always thread `zos` through: it keeps every
code-loading path behind one gate instead of around it.

---

## Caching Behavior

Python's importlib automatically caches loaded modules in `sys.modules`. This means:

- **First call**: Module is loaded from disk and cached
- **Subsequent calls**: Cached module is reused (fast)
- **Cache key**: Based on module_name (derived from file basename)
- **Implication**: Changes to the file require Python restart or manual cache invalidation

**Cache invalidation:**
```python
import sys
import importlib

# Remove from cache
module_name = "my_module"
if module_name in sys.modules:
    del sys.modules[module_name]
    
# Reload module
importlib.reload(module)
```

---

## Functions

### `resolve_callable(file_path: str, func_name: str, logger_instance: Any, zos: Optional[Any] = None) -> Callable`

Dynamically load a Python (or JavaScript) function from an external file, through the trust gate.

```python
import logging

logger = logging.getLogger(__name__)

# Load function from script (pass zos so loading is gated via zLoader)
func = resolve_callable("/path/to/script.py", "my_function", logger, zos)

# Execute function
result = func(arg1, arg2)
```

**Parameters:**
- `file_path` (str): Absolute path to Python/JS file
- `func_name` (str): Name of function to extract
- `logger_instance` (Any): Logger for debug messages
- `zos` (Optional[Any]): zOS instance — when provided, Python loading is routed through the gated `zos.loader.load_python_module`; threaded into the JS executor for its trust gate too

**Process Flow:**
1. **Validate File**: Check if file exists
2. **Route by type**: `.js` → `func_js_executor` (gated); otherwise Python
3. **Gate + Load (Python)**: with `zos`, call `zos.loader.load_python_module` (runs `verify_plugin_trust` before `exec_module`); without `zos`, call `verify_plugin_trust` directly, then `importlib` spec → module → `exec_module`
4. **Extract Function**: Get function from module via `getattr`
5. **Validate Function**: Ensure attribute exists/callable
6. **Return**: Return callable function

**Returns:** `Callable` - Loaded function object

**Raises:**
- `FileNotFoundError`: If file_path doesn't exist
- `ImportError`: If module spec creation or loading fails
- `AttributeError`: If function not found in module
- `ValueError`: If attribute exists but is not callable

**Debug Logging:**
```
DEBUG - File path: /path/to/script.py
DEBUG - Function name: my_function
DEBUG - Resolved callable: <function my_function at 0x...>
```

---

## Constants Reference

Imported from the subsystem SSOT (`func_constants.py`) — not re-declared in `func_resolver.py`:

| Constant | Value | Purpose |
|---|---|---|
| `DEBUG_MSG_FILE_PATH` | `"File path: %s"` | Log template for file path |
| `DEBUG_MSG_FUNCTION_NAME` | `"Function name: %s"` | Log template for function name |
| `DEBUG_MSG_RESOLVED` | `"Resolved callable: %s"` | Log template for resolved function |
| `ERROR_MSG_FILE_NOT_FOUND` | `"No such file: {file_path}"` | Error for missing file |
| `ERROR_MSG_SPEC_NONE` | `"Failed to create module spec from: {file_path}"` | Error for spec creation failure |
| `ERROR_MSG_LOADER_NONE` | `"Module spec has no loader for: {file_path}"` | Error for missing loader |
| `ERROR_MSG_MISSING_FUNCTION` | `"Function '{func_name}' not found in module '{module_path}'"` | Error for missing function |
| `ERROR_MSG_RESOLUTION_FAILED` | `"Failed to resolve callable from '%s > %s': %s"` | General resolution error |

> File extensions (`FILE_EXT_PY`/`FILE_EXT_JS`) used for routing are themselves drawn from the root `zVocabulary` via `func_constants`.

---

## Practical Examples

### Example 1: Basic Function Loading

```python
# External script: calculator.py
def add(a, b):
    """Add two numbers."""
    return a + b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b

# Load and execute
from zFunc_modules.func_resolver import resolve_callable
import logging

logger = logging.getLogger(__name__)

add_func = resolve_callable("/path/to/calculator.py", "add", logger)
result = add_func(5, 3)
# Returns: 8

multiply_func = resolve_callable("/path/to/calculator.py", "multiply", logger)
result = multiply_func(5, 3)
# Returns: 15
```

---

### Example 2: Function with Dependencies

```python
# External script: api_client.py
import requests

def fetch_user(user_id):
    """Fetch user from API."""
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()

# Load and execute (dependencies automatically loaded)
func = resolve_callable("/path/to/api_client.py", "fetch_user", logger)
user = func(42)
# Dependencies (requests) loaded during module execution
```

---

### Example 3: Error Handling - File Not Found

```python
try:
    func = resolve_callable("/invalid/path.py", "my_function", logger)
except FileNotFoundError as e:
    print(f"File not found: {e}")
    # Output: File not found: No such file: /invalid/path.py
```

---

### Example 4: Error Handling - Function Not Found

```python
# External script: script.py
def existing_function():
    return "exists"

try:
    func = resolve_callable("/path/to/script.py", "missing_function", logger)
except AttributeError as e:
    print(f"Function not found: {e}")
    # Output: Function not found: Function 'missing_function' not found in module: /path/to/script.py
```

---

### Example 5: Error Handling - Import Error

```python
# External script: broken_script.py (has syntax error)
def broken_function(:  # Syntax error
    return "broken"

try:
    func = resolve_callable("/path/to/broken_script.py", "broken_function", logger)
except ImportError as e:
    print(f"Import failed: {e}")
    # Output: Import failed: Failed to resolve callable from '/path/to/broken_script.py > broken_function': ...
```

---

### Example 6: Loading Multiple Functions from Same Module

```python
# External script: utils.py
def format_name(name):
    return name.title()

def format_email(email):
    return email.lower()

def format_phone(phone):
    return phone.replace("-", "")

# Load all functions (module cached after first call)
format_name_func = resolve_callable("/path/to/utils.py", "format_name", logger)
format_email_func = resolve_callable("/path/to/utils.py", "format_email", logger)
format_phone_func = resolve_callable("/path/to/utils.py", "format_phone", logger)

# Second and third calls are faster (cached module)
name = format_name_func("alice")        # Fast
email = format_email_func("Alice@EXAMPLE.COM")  # Fast
phone = format_phone_func("555-1234")   # Fast
```

---

### Example 7: Integration with zFunc

```python
# zFunc uses resolve_callable internally
from zOS import zOS

z = zOS()

# zFunc.handle() uses resolve_callable:
# 1. Parse zHorizontal → func_path, func_name
# 2. resolve_callable(func_path, func_name) → func
# 3. execute(func, args) → result

result = z.zfunc.handle("@/path/to/script.py > my_function('arg')", context)
```

**Flow:**
```python
# Inside zFunc.handle():
func_path, arg_str, func_name = z.zparser.parse_function_path(zHorizontal, context)
# func_path = "/path/to/script.py"
# func_name = "my_function"

func = resolve_callable(func_path, func_name, logger)
# func = <function my_function at 0x...>

result = executor.execute(func, args, context)
```

---

### Example 8: Manual Cache Invalidation

```python
import sys
import importlib

# Load function
func = resolve_callable("/path/to/script.py", "my_function", logger)
result1 = func()

# Modify script.py externally...

# Invalidate cache
module_name = "script"  # Derived from "script.py"
if module_name in sys.modules:
    del sys.modules[module_name]

# Reload function (picks up changes)
func = resolve_callable("/path/to/script.py", "my_function", logger)
result2 = func()  # Uses updated code
```

---

### Example 9: Loading from Different Directories

```python
# Project structure:
# /project/scripts/script1.py
# /project/utils/script2.py
# /project/handlers/script3.py

# Load from different directories
func1 = resolve_callable("/project/scripts/script1.py", "process", logger)
func2 = resolve_callable("/project/utils/script2.py", "helper", logger)
func3 = resolve_callable("/project/handlers/script3.py", "handler", logger)

# All loaded independently
result1 = func1()
result2 = func2()
result3 = func3()
```

---

## importlib Module Workflow (no-`zos` fallback)

The gated path delegates to `zos.loader.load_python_module`. The raw `importlib`
sequence below is only the **fallback** taken when `resolve_callable` is called
without a `zos` instance — and even then it is preceded by a `verify_plugin_trust`
call so the trust gate still applies. Understanding it helps debug loading issues:

```python
import importlib.util
import os
from zOS.L1_Foundation.c_zLoader.loader_modules.loader_trust import verify_plugin_trust

file_path = "/path/to/script.py"
func_name = "my_function"

# 1. Check file exists
if not os.path.isfile(file_path):
    raise FileNotFoundError(f"No such file: {file_path}")

# 1b. Trust gate (permissive in open-core; raises PluginTrustError when sealed)
verify_plugin_trust(file_path, None, logger)

# 2. Create module spec from file
spec = importlib.util.spec_from_file_location("script", file_path)
if spec is None:
    raise ImportError(f"Failed to create module spec from: {file_path}")

# 3. Validate spec has loader
if spec.loader is None:
    raise ImportError(f"Module spec has no loader for: {file_path}")

# 4. Create module object from spec
module = importlib.util.module_from_spec(spec)

# 5. Execute module (loads code into module namespace)
spec.loader.exec_module(module)

# 6. Extract function from module
if not hasattr(module, func_name):
    raise AttributeError(f"Function '{func_name}' not found in module: {file_path}")

func = getattr(module, func_name)

# 7. Validate callable
if not callable(func):
    raise ValueError(f"Attribute '{func_name}' is not callable")

# 8. Return function
return func
```

---

## Integration with zFunc

**zFunc._resolve_callable() uses resolve_callable (and threads `zos` for the gate):**

```python
# zFunc.py
def _resolve_callable(self, func_path, function_name):
    """Resolve callable (gated: routes Python/JS loading through zLoader's trust seam)."""
    from .zFunc_modules.func_resolver import resolve_callable
    return resolve_callable(func_path, function_name, self.logger, self.zos)
```

**Complete flow in zFunc.handle():**
```python
# 1. Parse function path (zParser)
func_path, arg_str, func_name = z.zparser.parse_function_path(zHorizontal, context)

# 2. Resolve callable (func_resolver)
func = resolve_callable(func_path, func_name, logger)

# 3. Parse arguments (arg_processing)
args = process_arguments(arg_str, context, split_arguments, logger, zparser)

# 4. Execute function (executors)
result = executor.execute(func, args, context)
```

---

## Best Practices

1. **File Paths:**
   - Use absolute paths for reliability
   - Validate file existence before calling
   - Consider path whitelisting for security
   - Document expected file locations

2. **Function Names:**
   - Use clear, descriptive function names
   - Follow Python naming conventions (snake_case)
   - Document function signatures
   - Avoid name collisions

3. **Error Handling:**
   - Catch FileNotFoundError for missing files
   - Catch ImportError for loading failures
   - Catch AttributeError for missing functions
   - Log errors for debugging

4. **Caching:**
   - Be aware of module caching behavior
   - Invalidate cache when needed (dev mode)
   - Use unique module names to avoid collisions
   - Document cache implications

5. **Security:**
   - Only load trusted Python files
   - Validate file paths before loading
   - Consider sandboxing for untrusted code
   - Document security assumptions

6. **Testing:**
   - Test with valid and invalid file paths
   - Test with missing functions
   - Test with syntax errors in modules
   - Test with missing dependencies
   - Test cache behavior

---

## Comparison with Other Loading Methods

### vs. `__import__()`

```python
# __import__() - requires module in sys.path
module = __import__("my_module")
func = getattr(module, "my_function")

# resolve_callable() - loads from arbitrary path
func = resolve_callable("/any/path/to/script.py", "my_function", logger)
```

**resolve_callable() advantages:**
- Works with arbitrary file paths
- No sys.path manipulation needed
- Explicit error handling
- Built-in validation

---

### vs. `exec()` with `open()`

```python
# exec() - requires string manipulation
with open("/path/to/script.py") as f:
    code = f.read()
namespace = {}
exec(code, namespace)
func = namespace["my_function"]

# resolve_callable() - clean API
func = resolve_callable("/path/to/script.py", "my_function", logger)
```

**resolve_callable() advantages:**
- Cleaner API
- Automatic namespace management
- Better error messages
- Caching via sys.modules

---

### vs. Manual `importlib` Usage

```python
# Manual importlib - verbose
import importlib.util
spec = importlib.util.spec_from_file_location("module", file_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
func = getattr(module, func_name)

# resolve_callable() - one line
func = resolve_callable(file_path, func_name, logger)
```

**resolve_callable() advantages:**
- Single function call
- Built-in validation
- Comprehensive error handling
- Automatic logging

---

## Version History

- **v1.5.4+**: Industry-grade upgrade
  - Added type hints
  - Comprehensive documentation
  - Validation and error handling
  - Constants extracted
- **v1.5.x**: Initial implementation (basic function loading)
