**[← Back to zNavigation Guide](zNavigation_GUIDE.md) | [Home](../../README.md) | [Next: zDialog Guide →](zDialog_GUIDE.md)**

---

# zFunc

**zFunc** is the **function execution subsystem** in **Layer 2 (Handling)** of **zOS**.
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

It provides dynamic loading and execution of Python functions, JavaScript/Node.js functions, and plugin modules through one unified interface.

You get:

- **Zero boilerplate**  
- **Dynamic function loading**  
- **Auto-injection** (zos, session, context)
- **Async support** (transparent coroutine handling)
- **Plugin system** (cached, collision-safe)
- **Argument processing** (zContext, zHat, zConv, this.key)
- **JavaScript execution** (Node.js/Deno integration)

## Architecture Overview

**zFunc** is composed of specialized modules, each handling a specific aspect of function execution:

| Module | Purpose | Guide |
|--------|---------|-------|
| **executors** | Function execution (Python/JS) with auto-injection | [execution_GUIDE.md](zFunc_Guides/execution_GUIDE.md) |
| **arg_processing** | Argument parsing and context injection | [arguments_GUIDE.md](zFunc_Guides/arguments_GUIDE.md) |
| **func_resolver** | Dynamic Python/JS loading — **routed through zLoader's trust gate** | [resolution_GUIDE.md](zFunc_Guides/resolution_GUIDE.md) |
| **plugin_system** | Plugin loading, caching, and execution | [plugins_GUIDE.md](zFunc_Guides/plugins_GUIDE.md) |
| **builtin_functions** | Built-in utilities (zNow, etc.) | [builtins_GUIDE.md](zFunc_Guides/builtins_GUIDE.md) |
| **func_js_executor** | JavaScript/Node.js execution | [javascript_GUIDE.md](zFunc_Guides/javascript_GUIDE.md) |

This guide provides a **facade overview** of zFunc. For deep dives into specific modules, see the guides in `zFunc_Guides/`.

---

## Initialization Order

When you call `zOS()`, zFunc initializes automatically after zParser (Layer 2 subsystem):

1. **zParser Ready** - Parsing subsystem initialized
2. **zFunc Initialization** - Function execution subsystem starts:
   - Validate zOS instance (logger, session, display, zparser required)
   - Create PythonExecutor for Python function execution
   - Initialize plugin system (delegates to zLoader's plugin cache)
   - Print ready message
   - Log ready state
3. **zFunc Ready** - Function execution infrastructure available

This order ensures zFunc has access to zParser (for argument parsing) and zLoader (for module caching).

**Auto-Initialization:**
```python
from zOS import zOS

z = zOS()  # zParser → zFunc → other subsystems

# zFunc is now ready:
z.zfunc.handle("@script.py > function(args)", context)  # Python functions
z.zfunc.execute_plugin("&plugin.func(args)", context)   # Plugin functions
z.zfunc.zNow()                                          # Built-in functions
```

---

## What's in This Guide

This guide covers the **main zFunc facade** - the unified interface to all function execution features. Like other Layer 2 guides, we focus on:

1. **Architecture Overview** - Module structure and design patterns
2. **Initialization** - How zFunc auto-initializes after zParser
3. **Usage Patterns** - Common workflows for function execution
4. **API Reference** - Complete method signatures and usage patterns
5. **Integration** - How zFunc integrates with zParser, zLoader, zWizard

**What's NOT in this guide:**
- Deep dives into individual modules (see `zFunc_Guides/` folder)
- Plugin development patterns (see [plugins_GUIDE.md](zFunc_Guides/plugins_GUIDE.md))
- JavaScript execution details (see [javascript_GUIDE.md](zFunc_Guides/javascript_GUIDE.md))

**Current Implementation Status:**
- ✅ Python function execution (dynamic loading, auto-injection, async support)
- ✅ Plugin system (filename-based caching, collision detection)
- ✅ Argument processing (5 special types: zContext, zHat, zConv, zConv.field, this.key)
- ✅ Built-in functions (zNow with format support)
- ✅ JavaScript execution (Node.js/Deno integration)
- ✅ Module caching (unified with zLoader)

---

## Quick Start

### Basic Python Function Execution

```python
from zOS import zOS

z = zOS()

# Execute external Python function
zHorizontal = "@/path/to/script.py > my_function('arg1', 42)"
result = z.zfunc.handle(zHorizontal, context=None)
```

**What happens:**
1. **Parse**: zParser extracts function path, function name, arguments
2. **Resolve**: load the module **through `zos.loader.load_python_module`** (the gated SSOT loader — `verify_plugin_trust` runs before any code executes), then retrieve the function
3. **Process Args**: Evaluate arguments (with zContext/zHat/zConv support)
4. **Inject**: Auto-inject `zos`, `session`, `context` if function signature requires
5. **Execute**: Call function (handles sync/async transparently)
6. **Return**: Return result to caller

---

### Plugin Execution

```python
# Execute plugin function
result = z.zfunc.execute_plugin("&math_utils.add(5, 3)", context=None)
# Returns: 8

# Load plugin module
module = z.zfunc.load_plugin("math_utils")
result = module.add(5, 3)
```

**Plugin advantages:**
- Filename-based caching (O(1) lookups)
- Collision detection (prevents duplicate plugin names)
- Auto-injection (zos, context)
- Async support (transparent coroutine handling)

---

### Built-in Functions

```python
# Get current date/time (formatted per zConfig)
now = z.zfunc.zNow()                    # "19122025 14:30:00"
date = z.zfunc.zNow('date')             # "19122025"
time = z.zfunc.zNow('time')             # "14:30:00"
custom = z.zfunc.zNow(custom_format='yyyy-mm-dd')  # "2025-12-19"
```

---

## Module Structure

zFunc follows a modular architecture with specialized components:

**Core Modules:**
- `zFunc.py` - Main facade class providing unified interface
- `__init__.py` - Package exports and public API

**Execution Modules:**
- `executors/base_executor.py` - ExecutionMixin (shared async/injection logic)
- `executors/python_executor.py` - PythonExecutor (Python function execution)

**Argument Processing:**
- `arg_processing/argument_processor.py` - Main orchestrator (zCLI-specific)
- `arg_processing/argument_splitter.py` - Delegates to zParser
- `arg_processing/context_injector.py` - Special argument types (zContext, zHat, etc.)

**Resolution:**
- `func_resolver.py` - Dynamic Python/JS function loading; Python loads delegate to `zos.loader.load_python_module` (gated), JS routes to `func_js_executor` (also gated)

**Plugin System:**
- `plugin_resolver.py` - Plugin invocation orchestrator
- `plugin_loader.py` - Module loading and caching
- `plugin_executor.py` - Plugin execution with async support

**Utilities:**
- `builtin_functions.py` - Built-in utilities (zNow)
- `func_js_executor.py` - JavaScript/Node.js execution
- `func_constants.py` - Shared constants and configuration
- `func_args.py` - Legacy argument utilities (deprecated)
- `exceptions.py` - zFunc-specific exceptions
- `protocols.py` - Type protocols and interfaces

**Architecture Pattern:**
zFunc uses the **Facade pattern** with **Mixin composition** - a unified interface (`zFunc` class) delegates to specialized managers:
- `z.zfunc.handle()` → `PythonExecutor.execute()`
- `z.zfunc.execute_plugin()` → `resolve_plugin_invocation()`
- `z.zfunc.load_plugin()` → `load_plugin_module()`
- `z.zfunc.zNow()` → `builtin_functions.zNow()`

This separation allows each component to be tested and evolved independently while maintaining a stable public API.

---

## Security & Trust

zFunc **loads and executes arbitrary code** (Python via `importlib`, JavaScript via a Node subprocess). That makes it one of the highest-value trust surfaces in zOS, so every code-loading path goes through a **single door** — the same `verify_plugin_trust` gate that c_zLoader exposes.

**One gate, every path:**

| Entry | Path | Gate |
|-------|------|------|
| `z.zfunc.handle("@script.py > fn(...)")` | `func_resolver` → `zos.loader.load_python_module` | `verify_plugin_trust` (before `exec_module`) |
| `z.zfunc.execute_plugin("&plugin.fn(...)")` | `plugin_loader` → `zos.loader.load_python_module` | `verify_plugin_trust` |
| `@script.js > fn(...)` | `func_resolver` → `func_js_executor` | `verify_plugin_trust` (before spawning Node) |

- **Open-core posture (permissive):** without zGuard, `verify_plugin_trust` is a no-op — open-core stays fully functional and loads plugins/functions from any path. This is the same Type-B "protect the user from tampered forks" seam used by zParser/zDisplay/zLoader.
- **Sealed posture:** installing **zGuard** seals the seam (allowed directories / signature / hash policy) with **no call-site changes**; a denied path raises `PluginTrustError`, which propagates **before any code runs** (fails closed). The sealed policy itself is **proprietary — see the private zGuard docs** (contact admin / `z patch`).
- **JS is injection-safe:** the Node wrapper receives `module_path` / `func_name` / `args` as a JSON payload via an environment variable — never string-interpolated into executable JS — so a crafted path or function name cannot inject code.

> **Why this matters:** a checked-out (or forked) repo can ship foreign `.py`/`.js` referenced by a `.zolo` file. The gate is what lets zGuard refuse to auto-run untrusted code; zFunc's job is simply to route *every* load through it, never around it.

---

## Constants & SSOT

- **File extensions** (`.py`, `.js`) alias the root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md) atoms (`FILE_EXT_PY` / `FILE_EXT_JS`) via `func_constants` — no per-module re-declaration.
- **Messages, timeouts, parameter names, plugin search paths** are single-sourced in `func_constants.py`; the resolver and JS executor import from it rather than defining local copies.
- **Module cache** is owned by zLoader (`zos.loader.cache.python_module_cache`); `zFunc.module_cache` is a deprecated shim that delegates there.

---

## Layer 2 Design Philosophy

As a **Layer 2 (Handling) subsystem**, zFunc has special design considerations:

**Depends on zParser:**
- Uses `zParser.parse_function_path()` for function path parsing
- Uses `zParser.parse_json_expr()` for argument evaluation
- Clear separation: zParser = syntax, zFunc = semantics

**Automatic Initialization:**
- Validates zOS instance (logger, session, display, zparser required)
- Creates PythonExecutor automatically
- Prints ready message via zDisplay
- Logs ready state to framework logger

**Pure Function Execution Layer:**
- No direct HTTP/file operations (use zComm/zParser for that)
- No UI rendering (use zDisplay for that)
- No orchestration (use zWizard/zWalker for that)
- Focuses solely on function loading and execution

**Integration Points:**
- **Depends on:** zParser (parsing), zLoader (caching), zConfig (session/logger)
- **Used by:** zWizard (steps), zWalker (commands), zDialog (handlers), user applications
- **Provides:** Dynamic function loading, plugin system, argument processing

---

## Advanced Features

### Auto-Injection

zFunc automatically injects framework dependencies based on function signature:

```python
# Function signature inspection
def my_function(arg1, zos, session, context):
    # zos: Automatically injected
    # session: Automatically injected
    # context: Automatically injected from caller
    return zos.config.get(arg1)

# Call without manual injection
result = z.zfunc.handle("@script.py > my_function('setting')", context)
```

**Supported injections:**
- `zos`: Full zOS framework instance
- `session`: Current session instance
- `context`: Caller-provided context (zHat, zConv, custom)

---

### Async Function Support

zFunc handles async functions transparently:

```python
# Async function in external file
async def fetch_data(url, zos):
    return await zos.comm.http_get(url)

# Execute normally - coroutine automatically awaited
result = z.zfunc.handle("@script.py > fetch_data('http://api.com')", context)
```

**Async handling:**
- CLI mode: Uses `asyncio.run()`
- Bifrost mode: Uses `run_coroutine_threadsafe()`
- 300-second timeout for async execution
- Graceful error handling

---

### Special Argument Types

zFunc supports 5 special zCLI argument types for context injection:

```python
context = {
    "user_id": 42,
    "zHat": {"step1": "wizard_data"},
    "zConv": {"input": "dialog_data"}
}

# 1. zContext - Full context dict
z.zfunc.handle("@script.py > func(zContext)", context)

# 2. zHat - Wizard context
z.zfunc.handle("@script.py > func(zHat)", context)

# 3. zConv - Dialog context
z.zfunc.handle("@script.py > func(zConv)", context)

# 4. zConv.field - Specific dialog field
z.zfunc.handle("@script.py > func(zConv.input)", context)

# 5. this.key - Specific context key
z.zfunc.handle("@script.py > func(this.user_id)", context)
```

For detailed documentation, see [arguments_GUIDE.md](zFunc_Guides/arguments_GUIDE.md).

---

### Plugin Caching

zFunc uses filename-based caching for fast plugin lookups:

```python
# First call: Load from disk and cache
result1 = z.zfunc.execute_plugin("&math_utils.add(5, 3)", context)  # ~50ms

# Subsequent calls: O(1) cache lookup
result2 = z.zfunc.execute_plugin("&math_utils.add(10, 20)", context)  # ~1ms
```

**Cache features:**
- Filename-based keys (not full path)
- Collision detection (prevents duplicate plugin names)
- Unified with zLoader's PythonModuleCache
- Automatic invalidation on module changes (dev mode)

For detailed documentation, see [plugins_GUIDE.md](zFunc_Guides/plugins_GUIDE.md).

---

## Facade API Reference

The `zFunc` class provides these convenience methods:

**Python Function Execution:**
```python
# Main entry point for external Python functions
result = z.zfunc.handle(zHorizontal, zContext=None)
# zHorizontal: "@/path/to/script.py > function('arg1', 42)"
# zContext: Optional dict with zHat, zConv, custom data
```

**Plugin Execution:**
```python
# Execute plugin function
result = z.zfunc.execute_plugin(value, context=None)
# value: "&plugin_name.function('arg')"
# context: Optional context for wizard/hat access

# Load plugin module
module = z.zfunc.load_plugin(plugin_name)
# plugin_name: Plugin filename (without .py)
```

**Built-in Functions:**
```python
# Get current date/time formatted per zConfig
now = z.zfunc.zNow(format_type="datetime", custom_format=None)
# format_type: "date", "time", or "datetime"
# custom_format: Override config format (e.g., "yyyy-mm-dd")
```

**Legacy Access (Deprecated):**
```python
# Module cache (deprecated - use zos.loader.cache instead)
cache = z.zfunc.module_cache  # Deprecated warning
# Use: z.zos.loader.cache.python_module_cache
```

**Internal Methods (Not Public API):**
```python
# These are used internally by handle() - not for direct use
z.zfunc._parse_args_with_display(arg_str, zContext)
z.zfunc._resolve_callable_with_display(func_path, function_name)
z.zfunc._display_result(result)
```

---

## Integration with zParser

zFunc and zParser have clear separation of concerns:

**zParser (Syntax):**
- `parse_function_path()`: Extract function path, args, name
- `parse_json_expr()`: Safely evaluate JSON expressions
- `split_arguments()`: Split on commas, respecting brackets

**zFunc (Semantics):**
- `handle()`: Orchestrate parsing → resolution → execution
- `process_arguments()`: Inject zContext, zHat, zConv
- `resolve_callable()`: Load modules via importlib
- `execute()`: Call functions with auto-injection

**Example flow:**
```python
zHorizontal = "@script.py > func(zContext, this.user_id, 'hello')"

# 1. zParser: Extract syntax
func_path, arg_str, func_name = z.zparser.parse_function_path(zHorizontal)
# func_path = "script.py"
# arg_str = "zContext, this.user_id, 'hello'"
# func_name = "func"

# 2. zFunc: Process arguments (semantics)
args = z.zfunc._parse_args_with_display(arg_str, context)
# args = [context, 42, "hello"]

# 3. zFunc: Resolve and execute
func = z.zfunc._resolve_callable_with_display(func_path, func_name)
result = z._python_executor.execute(func, args, context)
```

---

## Integration with zLoader

zFunc delegates module caching to zLoader for unified cache management:

**zLoader provides:**
- `PythonModuleCache`: Unified cache for Python modules
- `plugin_cache`: Specialized cache for plugins
- Cache invalidation strategies
- Thread-safe caching operations

**zFunc uses:**
```python
# Plugin caching (delegated to zLoader)
z.zfunc.load_plugin("math_utils")  # Uses z.loader.cache.plugin_cache

# Legacy access (deprecated)
z.zfunc.module_cache  # Warns: Use z.loader.cache.python_module_cache
```

For detailed documentation, see [zLoader Guide](../L1_Foundation/zLoader_GUIDE.md).

---

## Integration with zWizard

zFunc supports zWizard integration via special argument types:

**zHat Context:**
```python
# In zWizard step
context = {
    "zHat": {
        "step1": "data_from_previous_step",
        "user_input": "collected_input"
    }
}

# Function receives zHat automatically
zHorizontal = "@script.py > process_step(zHat)"
result = z.zfunc.handle(zHorizontal, context)
# Function receives: {"step1": "data_from_previous_step", "user_input": "collected_input"}
```

For detailed documentation, see [zWizard Guide](../L3_Abstraction/zWizard_GUIDE.md).

---

## Integration with zDialog

zFunc supports zDialog integration via zConv argument type:

**zConv Context:**
```python
# In zDialog handler
context = {
    "zConv": {
        "input": "user_response",
        "previous_state": "dialog_state"
    }
}

# Function receives zConv field
zHorizontal = "@script.py > handle_response(zConv.input)"
result = z.zfunc.handle(zHorizontal, context)
# Function receives: "user_response"
```

For detailed documentation, see [zDialog Guide](zDialog_GUIDE.md).

---

## Best Practices

1. **Function Signatures:**
   - Use type hints for clarity: `def func(arg: str, zos: Any) -> dict`
   - Request only needed dependencies: Don't add `zos` if not used
   - Document parameters in docstrings

2. **Plugin Development:**
   - Use unique plugin names (filename-based caching)
   - Avoid name collisions across projects
   - Implement error handling in plugin functions
   - Document plugin API in docstrings

3. **Async Functions:**
   - Prefer async for I/O operations (HTTP, file, database)
   - Use sync for CPU-bound operations
   - Test timeout behavior (300s limit)

4. **Argument Processing:**
   - Use zContext for full context dict
   - Use this.key for specific values
   - Use zHat for wizard integration
   - Use zConv for dialog integration

5. **Error Handling:**
   - Validate function inputs in external scripts
   - Catch exceptions in plugin functions
   - Log errors for debugging
   - Provide meaningful error messages

6. **Performance:**
   - Plugin caching provides O(1) lookups
   - Avoid repeated module loading in loops
   - Use async for concurrent operations
   - Profile functions for bottlenecks

---

## What's Next?

You've completed the **zFunc** guide (Layer 2 function execution). Continue along the Handling layer:

**→ Continue to [zDialog Guide](zDialog_GUIDE.md)** (conversational handlers)

zFunc builds on the Foundation layer (L0/L1) and its L2 siblings:
- **zParser** - Syntax parsing, symbol resolution, function-path parsing
- **zLoader** - Module caching and the **plugin-trust gate** zFunc delegates to
- **zNavigation** - Inter-file linking that can invoke zFunc
- **zFunc** - Function execution and plugin system (you are here)

> **Note:** For orchestration patterns using zFunc (wizards, walkers, dialogs), see Layer 3 guides: [zWizard Guide](../L3_Abstraction/zWizard_GUIDE.md), [zWalker Guide](../L4_Orchestration/zWalker_GUIDE.md), [zDialog Guide](zDialog_GUIDE.md).

---

**[← Back to zNavigation Guide](zNavigation_GUIDE.md) | [Home](../../README.md) | [Next: zDialog Guide →](zDialog_GUIDE.md)**
