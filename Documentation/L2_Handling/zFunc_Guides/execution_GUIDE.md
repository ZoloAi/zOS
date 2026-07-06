# zFunc Execution Module Guide

> **Module:** `zOS/core/L2_Handling/i_zFunc/zFunc_modules/executors/`  
> **Purpose:** Function execution with auto-injection and async support for zFunc subsystem.

---

## Overview

The `executors` module provides execution logic for Python functions with automatic dependency injection and transparent async handling. It is composed of two classes:

| Class | File | Purpose |
|---|---|---|
| `ExecutionMixin` | `base_executor.py` | Shared execution logic (async handling, inspection) |
| `PythonExecutor` | `python_executor.py` | Python function executor (auto-injection) |

---

## Architecture: Mixin Composition

`PythonExecutor` inherits from `ExecutionMixin` using single inheritance:

```
PythonExecutor(ExecutionMixin)
├── execute()           # Main entry point
├── _inject_kwargs()    # Auto-injection logic
└── _handle_coroutine() # Async handling (inherited)
```

**Design rationale:** Mixin provides reusable async handling logic that can be shared across multiple executor types (Python, JavaScript, Plugin).

---

## `ExecutionMixin`

Base mixin providing shared execution logic for all executor types.

### Key Features

**1. Async Detection:**
- Detects if function returns coroutine (async function)
- Uses `inspect.iscoroutinefunction()` for reliable detection

**2. Async Execution:**
- CLI mode: `asyncio.run()` for standalone execution
- Bifrost mode: `run_coroutine_threadsafe()` for event loop integration
- 300-second timeout for async operations

**3. Error Handling:**
- Graceful fallback if async execution fails
- Comprehensive logging of execution flow

### Methods

#### `_handle_coroutine(coroutine: Any, zos: Any) -> Any`

Handle async function execution with mode-aware strategy.

```python
async def fetch_data(url):
    return await http_get(url)

# Coroutine automatically handled
result = mixin._handle_coroutine(fetch_data("http://api.com"), zos)
```

**Strategy:**
- **CLI mode** (`zMode == "zCLI"`): Uses `asyncio.run()`
- **Bifrost mode** (`zMode == "zBifrost"`): Uses `run_coroutine_threadsafe()`
- **Timeout**: 300 seconds (5 minutes)

**Returns:** Coroutine result (any type)

**Raises:** 
- `TimeoutError`: If execution exceeds 300 seconds
- `Exception`: Any exception raised by coroutine

---

#### `_is_async_function(func: Callable) -> bool`

Check if function is async (returns coroutine).

```python
async def async_func():
    pass

def sync_func():
    pass

mixin._is_async_function(async_func)  # True
mixin._is_async_function(sync_func)   # False
```

**Uses:** `inspect.iscoroutinefunction()` for reliable detection

---

## `PythonExecutor`

Python function executor with automatic dependency injection.

### Initialization

```python
from zFunc_modules.executors import PythonExecutor

executor = PythonExecutor(zos)
```

| Parameter | Type | Description |
|---|---|---|
| `zos` | `Any` | zOS framework instance providing session, logger, etc. |

**On init:**
- Stores zos instance for injection
- Stores logger for debug messages
- Stores session for session injection

---

### Methods

#### `execute(func: Callable, args: List[Any], context: Optional[Any] = None) -> Any`

Execute Python function with auto-injection and async support.

```python
def my_func(arg1, zos, session):
    return zos.config.get(arg1)

# Auto-injects zos and session
executor = PythonExecutor(zos)
result = executor.execute(my_func, ["setting"], context=None)
```

**Process:**
1. **Inspect Signature**: Check function parameters
2. **Inject Dependencies**: Add zos, session, context as kwargs
3. **Call Function**: Execute with args + injected kwargs
4. **Handle Async**: If coroutine returned, await it
5. **Return Result**: Return function result

**Auto-Injection:**
- `zos`: Injected if parameter exists in signature
- `session`: Injected if parameter exists in signature
- `context`: Injected if parameter exists AND context provided

**Async Handling:**
- Detects coroutines automatically
- Delegates to `_handle_coroutine()` from mixin
- Transparent to caller

**Returns:** Function result (any type)

**Raises:** Any exception raised by function

---

#### `_inject_kwargs(func: Callable, context: Optional[Any]) -> Dict[str, Any]`

Build kwargs dict with available dependencies based on function signature.

```python
def func_with_deps(arg, zos, session, context):
    pass

# Inspects signature and builds kwargs
kwargs = executor._inject_kwargs(func_with_deps, context={"key": "value"})
# Returns: {"zos": zos_instance, "session": session_instance, "context": {"key": "value"}}
```

**Injection Logic:**
1. Inspect function signature using `inspect.signature()`
2. Check if 'zos' parameter exists → Add `zos` instance
3. Check if 'session' parameter exists → Add `session` instance
4. Check if 'context' parameter exists AND context provided → Add `context` dict

**Returns:** Dict of injectable kwargs

**Error Handling:** Gracefully handles inspection failures (logs warning, returns empty dict)

---

## Constants Reference

Defined in `func_constants.py`:

| Constant | Value | Purpose |
|---|---|---|
| `PARAM_NAME_ZOS` | `"zos"` | Parameter name for zOS instance injection |
| `PARAM_NAME_SESSION` | `"session"` | Parameter name for session injection |
| `PARAM_NAME_CONTEXT` | `"context"` | Parameter name for context injection |
| `ASYNC_TIMEOUT_SECONDS` | `300` | Async execution timeout (5 minutes) |

---

## Practical Examples

### Example 1: Sync Function with Auto-Injection

```python
# External script: script.py
def process_data(data, zos):
    """Process data using zConfig."""
    setting = zos.config.get("processing_mode")
    return f"Processed {data} in {setting} mode"

# Execute via zFunc
from zFunc_modules.executors import PythonExecutor

executor = PythonExecutor(zos)
func = load_function("script.py", "process_data")  # Use func_resolver
result = executor.execute(func, ["input"], context=None)
# "Processed input in production mode"
```

---

### Example 2: Async Function with Auto-Injection

```python
# External script: api_script.py
async def fetch_api_data(endpoint, zos):
    """Fetch data from API using zComm."""
    url = f"https://api.example.com/{endpoint}"
    response = await zos.comm.http_get(url)
    return response.json()

# Execute via zFunc (async transparently handled)
executor = PythonExecutor(zos)
func = load_function("api_script.py", "fetch_api_data")
result = executor.execute(func, ["users"], context=None)
# Coroutine automatically awaited
```

---

### Example 3: Context Injection for Wizard Integration

```python
# External script: wizard_step.py
def process_wizard_step(zHat, zos, context):
    """Process wizard step with previous data."""
    previous_data = context.get("zHat", {})
    step_result = zos.zparser.parse(previous_data.get("step1"))
    return {"step2": step_result}

# Execute with wizard context
context = {"zHat": {"step1": "previous_step_data"}}
executor = PythonExecutor(zos)
func = load_function("wizard_step.py", "process_wizard_step")
result = executor.execute(func, [context["zHat"]], context=context)
# Context automatically injected as kwarg
```

---

### Example 4: Manual Executor Usage (No zFunc Facade)

```python
from zFunc_modules.executors import PythonExecutor
from zFunc_modules.func_resolver import resolve_callable

# Load function
func = resolve_callable("/path/to/script.py", "my_function", logger)

# Create executor
executor = PythonExecutor(zos)

# Execute with auto-injection
result = executor.execute(
    func,
    args=["arg1", "arg2"],
    context={"key": "value"}
)
```

---

### Example 5: Async Timeout Handling

```python
async def slow_operation(zos):
    """Operation that takes too long."""
    await asyncio.sleep(400)  # Exceeds 300s timeout
    return "Done"

try:
    executor = PythonExecutor(zos)
    func = load_function("script.py", "slow_operation")
    result = executor.execute(func, [], context=None)
except TimeoutError:
    print("Operation timed out after 300 seconds")
```

---

### Example 6: Selective Injection

```python
# Function 1: Only needs zos
def func1(arg, zos):
    return zos.config.get(arg)

# Function 2: Needs zos and session
def func2(arg, zos, session):
    return f"{session.get('title')}: {zos.config.get(arg)}"

# Function 3: Needs all three
def func3(arg, zos, session, context):
    hat = context.get("zHat", {})
    return f"{session.get('title')}: {zos.config.get(arg)}: {hat}"

# Executor inspects and injects only what's needed
executor = PythonExecutor(zos)

result1 = executor.execute(func1, ["setting"], None)        # Injects: zos
result2 = executor.execute(func2, ["setting"], None)        # Injects: zos, session
result3 = executor.execute(func3, ["setting"], context)     # Injects: zos, session, context
```

---

## Integration with zFunc

**zFunc.handle() uses PythonExecutor:**

```python
# zFunc.py
def handle(self, zHorizontal, zContext=None):
    # ... parse and resolve ...
    
    # Delegate to PythonExecutor
    result = self._python_executor.execute(func, args, zContext)
    return result
```

**Flow:**
1. `zFunc.handle()` parses zHorizontal → `func_path, args, func_name`
2. `resolve_callable()` loads function → `func`
3. `PythonExecutor.execute()` runs function with auto-injection
4. Result returned to caller

---

## Design Patterns

**1. Mixin Composition:**
- `ExecutionMixin` provides reusable async handling
- `PythonExecutor` adds Python-specific injection logic
- Clean separation of concerns

**2. Dependency Injection:**
- Automatic detection via signature inspection
- Optional dependencies (only inject if needed)
- No manual wiring required

**3. Async Transparency:**
- Caller doesn't need to know if function is async
- Executor handles both sync and async uniformly
- Event loop management abstracted away

**4. Error Resilience:**
- Graceful handling of inspection failures
- Comprehensive logging for debugging
- Clear error messages for users

---

## Best Practices

1. **Function Signatures:**
   - Use type hints: `def func(arg: str, zos: Any) -> dict`
   - Only request needed dependencies
   - Document injected parameters in docstrings

2. **Async Functions:**
   - Prefer async for I/O operations
   - Use sync for CPU-bound operations
   - Test timeout behavior (300s limit)

3. **Context Usage:**
   - Request `context` parameter only if needed
   - Validate context structure in function
   - Document expected context format

4. **Error Handling:**
   - Validate inputs before processing
   - Catch exceptions in async functions
   - Log errors for debugging

5. **Testing:**
   - Mock zos instance for unit tests
   - Test both sync and async paths
   - Test timeout scenarios
   - Test injection with/without context

---

## Version History

- **v1.6.0**: Extracted from zFunc._execute_function() during refactoring
  - Created `ExecutionMixin` for shared async handling
  - Created `PythonExecutor` for Python-specific injection
  - Followed `b_zComm` manager pattern
