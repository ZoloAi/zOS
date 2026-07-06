# zFunc JavaScript Execution Module Guide

> **Module:** `zOS/core/L2_Handling/i_zFunc/zFunc_modules/func_js_executor.py`  
> **Purpose:** JavaScript and Node.js function execution for zFunc subsystem.

---

## Overview

The `func_js_executor` module enables execution of JavaScript functions from Python via a **Node.js** subprocess. It provides interoperability between Python and JavaScript codebases.

**Key Features:**
- Execute JavaScript functions from Python code (Node.js)
- Automatic JSON serialization/deserialization
- Error handling and logging
- **Trust-gated** (same zGuard seam as Python plugin loading)
- **Injection-safe** invocation (payload passed via env, never interpolated)

> **Runtime note:** the current implementation runs **Node.js only** (`node -e`). Deno is not wired in; treat any Deno reference in older examples as aspirational.

---

## Security & Trust

⚠️ JavaScript runs as **arbitrary code** in a Node subprocess, so it is gated exactly like Python plugin loading.

- **Trust gate:** before spawning Node, `execute_js_function` calls `verify_plugin_trust(file_path, zos, logger)` — the c_zLoader zGuard seam. Open-core: permissive no-op. With zGuard: sealed (allowed dirs / signatures); denial raises `PluginTrustError` **before Node is spawned** (fails closed). Sealed policy is **proprietary — see the private zGuard docs**.
- **Injection-safe:** `module_path`, `func_name`, and `args` are passed to a **static** Node wrapper as a single JSON payload via the `ZFUNC_JS_PAYLOAD` environment variable. Nothing is string-interpolated into the executable script, so a crafted file path or function name **cannot inject JavaScript**.
- **Timeout:** execution is bounded by `TIMEOUT_JS_EXECUTION` (`func_constants`, 30s).

---

## Functions

### `execute_js_function(file_path, func_name, args, logger_instance, zos=None) -> Any`

Execute a JavaScript function via Node.js, through the trust gate.

```python
# Execute Node.js function (pass zos so the load is gated)
result = execute_js_function(
    file_path="/path/to/script.js",
    func_name="processData",
    args=["input", 42],
    logger_instance=logger,
    zos=z,
)
```

**Parameters:**
- `file_path` (str): Path to JavaScript file
- `func_name` (str): Name of exported function to execute
- `args` (list): Function arguments (JSON-serializable)
- `logger_instance` (Any): Logger instance for debug messages
- `zos` (Optional[Any]): zOS instance, threaded into `verify_plugin_trust`

**Returns:** Function result (deserialized from JSON)

**Raises:**
- `FileNotFoundError`: If Node.js or the JavaScript file isn't found
- `RuntimeError` / `subprocess.CalledProcessError`: If execution fails or times out
- `ValueError`: If the named function isn't found in the module
- `PluginTrustError`: If a sealed zGuard policy denies the path

---

## Runtime Requirements

### Node.js

**Installation:**
```bash
# macOS
brew install node

# Linux (Debian/Ubuntu)
sudo apt-get install nodejs npm

# Linux (Fedora)
sudo dnf install nodejs npm

# Windows
# Download from https://nodejs.org/
```

**Check installation:**
```bash
node --version
# v18.0.0 or higher
```

---

### Deno

**Installation:**
```bash
# macOS/Linux
curl -fsSL https://deno.land/install.sh | sh

# Windows
irm https://deno.land/install.ps1 | iex
```

**Check installation:**
```bash
deno --version
# deno 1.30.0 or higher
```

---

## JavaScript Function Format

JavaScript functions must be exported and follow this structure:

### Node.js Format

```javascript
// script.js
function processData(input, number) {
    return {
        result: `Processed ${input} with ${number}`,
        timestamp: Date.now()
    };
}

// Export function
module.exports = { processData };
```

---

### Deno Format

```javascript
// script.js
export function processData(input, number) {
    return {
        result: `Processed ${input} with ${number}`,
        timestamp: Date.now()
    };
}
```

---

## Practical Examples

### Example 1: Basic JavaScript Execution

```python
from zFunc_modules.func_js_executor import execute_js_function

# JavaScript file: utils.js
# function add(a, b) { return a + b; }
# module.exports = { add };

result = execute_js_function(
    js_file_path="/path/to/utils.js",
    function_name="add",
    args=[5, 3],
    runtime="node"
)
# Returns: 8
```

---

### Example 2: Complex Data Structures

```python
# JavaScript file: data_processor.js
# function processUser(user) {
#     return {
#         fullName: `${user.firstName} ${user.lastName}`,
#         email: user.email.toLowerCase(),
#         created: Date.now()
#     };
# }
# module.exports = { processUser };

user_data = {
    "firstName": "Alice",
    "lastName": "Smith",
    "email": "Alice@EXAMPLE.COM"
}

result = execute_js_function(
    js_file_path="/path/to/data_processor.js",
    function_name="processUser",
    args=[user_data],
    runtime="node"
)
# Returns: {"fullName": "Alice Smith", "email": "alice@example.com", "created": 1703001234567}
```

---

### Example 3: Array Processing

```python
# JavaScript file: array_utils.js
# function filterEven(numbers) {
#     return numbers.filter(n => n % 2 === 0);
# }
# module.exports = { filterEven };

numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

result = execute_js_function(
    js_file_path="/path/to/array_utils.js",
    function_name="filterEven",
    args=[numbers],
    runtime="node"
)
# Returns: [2, 4, 6, 8, 10]
```

---

### Example 4: Async JavaScript Functions

```javascript
// async_api.js
async function fetchData(url) {
    const response = await fetch(url);
    return await response.json();
}

module.exports = { fetchData };
```

```python
# Execute async JavaScript (awaited by Node.js runtime)
result = execute_js_function(
    js_file_path="/path/to/async_api.js",
    function_name="fetchData",
    args=["https://api.example.com/users"],
    runtime="node"
)
# Returns: JSON response from API
```

---

### Example 5: Using Deno Runtime

```javascript
// deno_script.js
export function processText(text) {
    return text.toUpperCase();
}
```

```python
# Execute with Deno runtime
result = execute_js_function(
    js_file_path="/path/to/deno_script.js",
    function_name="processText",
    args=["hello world"],
    runtime="deno"
)
# Returns: "HELLO WORLD"
```

---

### Example 6: Error Handling

```python
# JavaScript file: error_demo.js
# function mayFail(value) {
#     if (value < 0) {
#         throw new Error("Value must be positive");
#     }
#     return value * 2;
# }
# module.exports = { mayFail };

try:
    result = execute_js_function(
        js_file_path="/path/to/error_demo.js",
        function_name="mayFail",
        args=[-5],
        runtime="node"
    )
except RuntimeError as e:
    print(f"JavaScript error: {e}")
    # Output: JavaScript error: Error: Value must be positive
```

---

### Example 7: Integration with zFunc

```python
from zOS import zOS

z = zOS()

# Preferred path: zFunc routes .js files automatically through the gated resolver
result = z.zfunc.handle("@/path/to/script.js > myFunction('arg1', 42)", context=None)

# Direct (internal) usage — pass zos so the load is gated:
from zFunc_modules.func_js_executor import execute_js_function

result = execute_js_function(
    file_path="/path/to/script.js",
    func_name="myFunction",
    args=["arg1", 42],
    logger_instance=z.logger,
    zos=z,
)
```

> The conceptual examples below use a simplified call shape for readability; the real signature is `execute_js_function(file_path, func_name, args, logger_instance, zos=None)` and the runtime is **Node.js only**.

---

### Example 8: NPM Package Usage (Node.js)

```javascript
// npm_example.js
const _ = require('lodash');

function sortNumbers(numbers) {
    return _.sortBy(numbers);
}

module.exports = { sortNumbers };
```

```bash
# Install dependencies first
cd /path/to/scripts
npm install lodash
```

```python
# Execute function using npm package
result = execute_js_function(
    js_file_path="/path/to/scripts/npm_example.js",
    function_name="sortNumbers",
    args=[[3, 1, 4, 1, 5, 9, 2, 6]],
    runtime="node"
)
# Returns: [1, 1, 2, 3, 4, 5, 6, 9]
```

---

## Implementation Details

### Execution Flow

1. **Validate Node**: Check `node --version` is available
2. **Validate File**: Check the JavaScript file exists
3. **Trust gate**: `verify_plugin_trust(file_path, zos, logger)` — denial raises before Node is spawned
4. **Build payload**: `json.dumps({"module_path", "func_name", "args"})`
5. **Execute**: run the **static** wrapper via `node -e`, passing the payload in the `ZFUNC_JS_PAYLOAD` env var (with a `TIMEOUT_JS_EXECUTION` cap)
6. **Capture Output**: read stdout (errors come back as JSON on stderr)
7. **Deserialize Result**: parse JSON output to Python
8. **Return**: return deserialized result

---

### Wrapper Script (static, injection-safe)

The wrapper is a **fixed string** — no path or function name is interpolated into
it. It reads the invocation payload from the environment, so untrusted input can
never become executable JS:

```javascript
const payload = JSON.parse(process.env.ZFUNC_JS_PAYLOAD);
const mod = require(payload.module_path);
const func = mod[payload.func_name];
if (typeof func !== 'function') {
    console.error(JSON.stringify({ __error__: true, message: `Function '${payload.func_name}' not found in module` }));
    process.exit(1);
}
try {
    const result = func(...payload.args);
    console.log(JSON.stringify(result));
} catch (error) {
    console.error(JSON.stringify({ __error__: true, message: error.message, stack: error.stack }));
    process.exit(1);
}
```

> **Why env, not argv/interpolation:** an earlier version built the wrapper with
> f-string interpolation of `file_path`/`func_name`. A quote or newline in either
> could escape the JS string literal and inject code. Passing a single JSON
> payload through the environment closes that hole entirely.

---

### Data Serialization

**Python → JavaScript:**
- `dict` → JavaScript object
- `list` → JavaScript array
- `str` → JavaScript string
- `int/float` → JavaScript number
- `bool` → JavaScript boolean
- `None` → JavaScript null

**JavaScript → Python:**
- JavaScript object → `dict`
- JavaScript array → `list`
- JavaScript string → `str`
- JavaScript number → `int/float`
- JavaScript boolean → `bool`
- JavaScript null → `None`

---

## Use Cases

### 1. Frontend Code Reuse

```python
# Reuse frontend validation logic in backend
result = execute_js_function(
    js_file_path="/frontend/validators.js",
    function_name="validateEmail",
    args=["user@example.com"],
    runtime="node"
)
# Returns: True
```

---

### 2. Node.js Library Integration

```python
# Use Node.js libraries from Python
result = execute_js_function(
    js_file_path="/scripts/markdown_parser.js",
    function_name="parseMarkdown",
    args=["# Heading\n\nParagraph"],
    runtime="node"
)
# Returns: "<h1>Heading</h1><p>Paragraph</p>"
```

---

### 3. JavaScript-based Data Processing

```python
# Leverage JavaScript's JSON/string manipulation
result = execute_js_function(
    js_file_path="/scripts/data_transform.js",
    function_name="transformData",
    args=[complex_data_structure],
    runtime="node"
)
```

---

### 4. Web Scraping (with Deno)

```javascript
// scraper.js (Deno)
export async function scrapeWebsite(url) {
    const response = await fetch(url);
    const html = await response.text();
    // Parse HTML and extract data
    return extractedData;
}
```

```python
# Execute web scraper
result = execute_js_function(
    js_file_path="/scripts/scraper.js",
    function_name="scrapeWebsite",
    args=["https://example.com"],
    runtime="deno"
)
```

---

## Performance Considerations

### Overhead

JavaScript execution via subprocess has overhead:

- **Process spawn**: ~50-100ms
- **Module loading**: ~10-50ms (cached after first run)
- **JSON serialization**: ~1-10ms (depends on data size)

**Total overhead**: ~60-160ms per call

**Optimization strategies:**
1. **Batch operations**: Process multiple items in one call
2. **Minimize calls**: Cache results when possible
3. **Use native Python**: For simple operations, Python is faster
4. **Consider persistent process**: For high-frequency calls (future feature)

---

### When to Use JavaScript Execution

**Good use cases:**
- Reusing existing JavaScript code
- Leveraging JavaScript libraries (npm packages)
- Complex string/JSON manipulation (JavaScript's strength)
- Frontend/backend code sharing

**Poor use cases:**
- Simple calculations (use Python)
- High-frequency operations (overhead too high)
- CPU-intensive tasks (subprocess overhead)
- When Python library exists (use Python)

---

## Best Practices

1. **Function Design:**
   - Keep functions pure (no side effects)
   - Return serializable data (JSON-compatible)
   - Handle errors in JavaScript
   - Document expected arguments

2. **Error Handling:**
   - Validate inputs in JavaScript
   - Catch exceptions in Python
   - Log errors for debugging
   - Provide meaningful error messages

3. **Performance:**
   - Batch operations when possible
   - Cache results if reused
   - Minimize subprocess calls
   - Use native Python for simple tasks

4. **Dependencies:**
   - Document npm package requirements
   - Use package.json for Node.js projects
   - Consider bundle size for Deno

5. **Testing:**
   - Test JavaScript functions independently
   - Test Python-JavaScript integration
   - Test error conditions
   - Test with different runtimes

---

## Limitations

Current limitations:

1. **Subprocess Overhead**: Each call spawns new process (~50-100ms)
2. **No Shared State**: Functions can't maintain state between calls
3. **JSON Only**: Arguments/returns must be JSON-serializable
4. **No Callbacks**: Python can't pass callbacks to JavaScript
5. **No Streaming**: All data transferred at once (not streaming)

---

## Future Enhancements

Planned features for future versions:

- **Persistent Process**: Keep Node.js process alive for multiple calls
- **Bidirectional Communication**: Python ↔ JavaScript callbacks
- **Streaming Support**: Stream large datasets
- **Direct Integration**: Python ↔ JavaScript without subprocess
- **Type Validation**: Validate argument types before execution
- **zFunc Facade**: Public API via `z.zfunc.execute_js()`

---

## Version History

- **v1.6.0**: Initial implementation
  - Node.js runtime support
  - Deno runtime support
  - JSON serialization/deserialization
  - Error handling and logging
  - Subprocess-based execution
