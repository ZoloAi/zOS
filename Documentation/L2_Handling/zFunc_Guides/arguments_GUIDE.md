# zFunc Argument Processing Module Guide

> **Module:** `zOS/core/L2_Handling/i_zFunc/zFunc_modules/arg_processing/`  
> **Purpose:** Argument parsing and zCLI-specific context injection for zFunc subsystem.

---

## Overview

The `arg_processing` module provides argument parsing with support for 5 special zCLI argument types. It orchestrates argument splitting (delegated to zParser) and context injection (zCLI semantics).

| Module | File | Purpose |
|---|---|---|
| `argument_processor` | `argument_processor.py` | Main orchestrator (zCLI-specific business logic) |
| `argument_splitter` | `argument_splitter.py` | Delegates splitting to zParser (universal syntax) |
| `context_injector` | `context_injector.py` | Special argument type injection (5 zCLI types) |

---

## Clear Separation: zParser vs zFunc

**zParser (Universal Syntax):**
- `split_arguments()`: Split on commas, respect nested brackets
- `parse_json_expr()`: Safely evaluate JSON expressions
- No knowledge of zCLI semantics (zContext, zHat, etc.)

**zFunc (zCLI Semantics):**
- `process_arguments()`: Orchestrate splitting + injection
- `inject_special_argument()`: Handle zContext, zHat, zConv, this.key
- Delegates syntax to zParser, adds business logic

---

## `argument_processor`

Main orchestrator combining splitting and injection with zCLI-specific business logic.

### Functions

#### `process_arguments(arg_str, zContext, split_fn, logger_instance, zparser=None) -> List[Any]`

Process function arguments from string with zCLI-specific context injection.

```python
context = {"user_id": 42, "zHat": {"step1": "data"}}

# Mixed argument types
args = process_arguments(
    "zContext, this.user_id, 'hello', 123",
    context,
    split_arguments,
    logger,
    zparser
)
# Returns: [context, 42, "hello", 123]
```

**Parameters:**
- `arg_str` (str): Comma-separated argument string
- `zContext` (Any): Context dict for injection
- `split_fn` (Callable): Function to split arguments (delegates to zParser)
- `logger_instance` (Any): Logger for debug messages
- `zparser` (Any): Optional zParser instance for JSON evaluation

**Process Flow:**
1. **Empty check**: Return empty list if arg_str is None/empty
2. **Split**: Use split_fn to split on commas (respects brackets)
3. **Process each arg**:
   - Check if special type (zContext, zHat, zConv, zConv.field, this.key)
   - If special: Inject from context
   - If regular: Evaluate via zParser.parse_json_expr()
   - Fallback: Treat as string literal
4. **Return**: List of processed values

**Special Argument Types:**
1. **zContext**: Full context dict
2. **zHat**: Wizard context (zWizard integration)
3. **zConv**: Dialog context (zDialog integration)
4. **zConv.field**: Specific dialog field
5. **this.key**: Specific context key

**Returns:** `List[Any]` - Processed argument values

**Raises:** `ValueError` if arg_str is not string or split_fn is not callable

---

## `argument_splitter`

Delegates argument splitting to zParser's universal syntax primitive.

### Functions

#### `split_arguments(arg_str: str) -> List[str]`

Split comma-separated arguments while respecting nested brackets.

```python
# Simple arguments
split_arguments("'hello', 42, true")
# Returns: ["'hello'", "42", "true"]

# Nested structures
split_arguments("{'name': 'Alice'}, [1, 2, 3], func(a, b)")
# Returns: ["{'name': 'Alice'}", "[1, 2, 3]", "func(a, b)"]

# Special types mixed with regular
split_arguments("zContext, this.user_id, 'hello'")
# Returns: ["zContext", "this.user_id", "'hello'"]
```

**Delegates to:** `zParser.split_arguments()` (universal syntax primitive)

**Validation:**
- Checks bracket matching (parentheses, square brackets, curly braces)
- Respects quoted strings
- Handles nested structures

**Returns:** `List[str]` - Raw argument strings (unprocessed)

**Raises:** `ValueError` if bracket mismatch detected

---

## `context_injector`

Handles injection of 5 special zCLI argument types from context.

### Functions

#### `inject_special_argument(arg: str, zContext: Any, logger_instance: Any) -> Any`

Inject special argument type from context.

```python
context = {
    "user_id": 42,
    "zHat": {"step1": "wizard_data"},
    "zConv": {"input": "dialog_data", "state": "active"}
}

# Type 1: zContext
inject_special_argument("zContext", context, logger)
# Returns: entire context dict

# Type 2: zHat
inject_special_argument("zHat", context, logger)
# Returns: {"step1": "wizard_data"}

# Type 3: zConv
inject_special_argument("zConv", context, logger)
# Returns: {"input": "dialog_data", "state": "active"}

# Type 4: zConv.field
inject_special_argument("zConv.input", context, logger)
# Returns: "dialog_data"

# Type 5: this.key
inject_special_argument("this.user_id", context, logger)
# Returns: 42

# Not special: returns None
inject_special_argument("'hello'", context, logger)
# Returns: None
```

**Detection Logic:**
1. **zContext**: Exact match → Return full context
2. **zHat**: Exact match → Extract zHat from context
3. **zConv**: Exact match → Extract zConv from context
4. **zConv.field**: Starts with "zConv." → Extract field from zConv
5. **this.key**: Starts with "this." → Extract key from context
6. **Not special**: Return None (caller handles as regular arg)

**Parameters:**
- `arg` (str): Raw argument string
- `zContext` (Any): Context dict for extraction
- `logger_instance` (Any): Logger for debug messages

**Returns:** 
- Injected value if special type
- `None` if not special type (signals to caller)

**Raises:** Does not raise (returns None on errors, logs warning)

---

## Special Argument Types

### 1. zContext - Full Context Dict

**Purpose:** Pass entire context dict to function

**Syntax:** `zContext` (exact match, case-sensitive)

**Use Case:** Function needs access to all context data

```python
def my_function(data, zContext):
    """Process data with full context."""
    user_id = zContext.get("user_id")
    settings = zContext.get("settings", {})
    return f"Processing {data} for user {user_id}"

# Call via zFunc
z.zfunc.handle("@script.py > my_function('data', zContext)", context)
```

---

### 2. zHat - Wizard Context

**Purpose:** Pass wizard context from zWizard to function

**Syntax:** `zHat` (exact match, case-sensitive)

**Use Case:** Wizard step functions need previous step data

```python
def wizard_step(zHat, zos):
    """Process wizard step with previous data."""
    previous_result = zHat.get("step1")
    return {"step2": f"Processed {previous_result}"}

# zWizard provides zHat in context
context = {"zHat": {"step1": "previous_step_data"}}
z.zfunc.handle("@script.py > wizard_step(zHat)", context)
```

---

### 3. zConv - Dialog Context

**Purpose:** Pass dialog context from zDialog to function

**Syntax:** `zConv` (exact match, case-sensitive)

**Use Case:** Dialog handler needs all dialog state

```python
def dialog_handler(zConv, zos):
    """Handle dialog with full state."""
    user_input = zConv.get("input")
    current_state = zConv.get("state")
    return {"response": f"Received {user_input} in {current_state}"}

# zDialog provides zConv in context
context = {"zConv": {"input": "user_response", "state": "active"}}
z.zfunc.handle("@script.py > dialog_handler(zConv)", context)
```

---

### 4. zConv.field - Specific Dialog Field

**Purpose:** Extract specific field from zConv dict

**Syntax:** `zConv.{field_name}` (dot notation)

**Use Case:** Function only needs one dialog value

```python
def process_input(user_input, zos):
    """Process just the user input."""
    return f"Processing: {user_input}"

# Extract specific field
context = {"zConv": {"input": "user_response", "state": "active"}}
z.zfunc.handle("@script.py > process_input(zConv.input)", context)
# Function receives: "user_response"
```

---

### 5. this.key - Specific Context Key

**Purpose:** Extract specific value from context dict

**Syntax:** `this.{key_name}` (dot notation)

**Use Case:** Function needs one specific context value

```python
def get_user_data(user_id, zos):
    """Fetch user data by ID."""
    return zos.database.get_user(user_id)

# Extract specific key
context = {"user_id": 42, "other_data": "..."}
z.zfunc.handle("@script.py > get_user_data(this.user_id)", context)
# Function receives: 42
```

---

## Regular Argument Evaluation

For arguments that aren't special types, `process_arguments()` uses zParser for safe evaluation:

```python
# JSON primitives
args = process_arguments("'hello', 42, true, null", context, split_fn, logger, zparser)
# Returns: ["hello", 42, True, None]

# JSON structures
args = process_arguments("{'name': 'Alice'}, [1, 2, 3]", context, split_fn, logger, zparser)
# Returns: [{"name": "Alice"}, [1, 2, 3]]

# Mixed with special types
args = process_arguments("this.user_id, 'hello', 42", context, split_fn, logger, zparser)
# Returns: [42, "hello", 42]
```

**Evaluation Strategy:**
1. Try `zparser.parse_json_expr()` if zparser available
2. Fallback to string literal if parsing fails
3. Log evaluation result for debugging

---

## Constants Reference

Defined in `func_constants.py`:

| Constant | Value | Purpose |
|---|---|---|
| `SPECIAL_ARG_ZCONTEXT` | `"zContext"` | Full context dict keyword |
| `SPECIAL_ARG_ZHAT` | `"zHat"` | Wizard context keyword |
| `SPECIAL_ARG_ZCONV` | `"zConv"` | Dialog context keyword |
| `PREFIX_ZCONV_FIELD` | `"zConv."` | Dialog field prefix |
| `PREFIX_THIS_KEY` | `"this."` | Context key prefix |

---

## Practical Examples

### Example 1: Mixed Argument Types

```python
def process_request(user_id, data, settings, zos):
    """Process request with mixed arguments."""
    return {
        "user": user_id,
        "data": data,
        "settings": settings,
        "config": zos.config.get("mode")
    }

# Context with values
context = {
    "user_id": 42,
    "settings": {"mode": "fast"}
}

# Mixed special types and literals
zHorizontal = "@script.py > process_request(this.user_id, 'hello', this.settings)"
result = z.zfunc.handle(zHorizontal, context)
# Function receives: (42, "hello", {"mode": "fast"})
```

---

### Example 2: Wizard Step Chain

```python
# Step 1
def wizard_step1(user_input, zos):
    return {"step1_result": f"Processed {user_input}"}

# Step 2 (uses zHat)
def wizard_step2(zHat, zos):
    previous = zHat.get("step1_result")
    return {"step2_result": f"Built on {previous}"}

# Execute in wizard
context = {"zHat": {}}
result1 = z.zfunc.handle("@script.py > wizard_step1('input')", context)
context["zHat"].update(result1)

result2 = z.zfunc.handle("@script.py > wizard_step2(zHat)", context)
# Step 2 receives: {"step1_result": "Processed input"}
```

---

### Example 3: Dialog Handler with Fields

```python
def validate_and_respond(input_text, state, zos):
    """Validate input and respond based on state."""
    if state == "awaiting_name":
        return {"response": f"Hello, {input_text}!", "next_state": "complete"}
    return {"response": "Invalid state", "next_state": "error"}

# Dialog context
context = {
    "zConv": {
        "input": "Alice",
        "state": "awaiting_name"
    }
}

# Extract specific fields
zHorizontal = "@script.py > validate_and_respond(zConv.input, zConv.state)"
result = z.zfunc.handle(zHorizontal, context)
# Function receives: ("Alice", "awaiting_name")
```

---

### Example 4: JSON Structure Arguments

```python
def create_user(user_data, config, zos):
    """Create user with structured data."""
    return zos.database.insert("users", user_data, config)

# JSON structures in arguments
zHorizontal = """@script.py > create_user(
    {'name': 'Alice', 'email': 'alice@example.com'},
    {'validate': true, 'send_email': false}
)"""

result = z.zfunc.handle(zHorizontal, context)
# Function receives: ({"name": "Alice", "email": "alice@example.com"}, {"validate": True, "send_email": False})
```

---

### Example 5: Nested Context Access

```python
def get_nested_value(user_settings, zos):
    """Process nested settings."""
    theme = user_settings.get("ui", {}).get("theme", "default")
    return f"Using theme: {theme}"

# Nested context structure
context = {
    "user": {
        "settings": {
            "ui": {"theme": "dark"}
        }
    }
}

# Extract nested value
zHorizontal = "@script.py > get_nested_value(this.user)"
result = z.zfunc.handle(zHorizontal, context)
# Function receives: {"settings": {"ui": {"theme": "dark"}}}
```

---

### Example 6: Error Handling

```python
# Missing special argument
context = {}  # No zHat

try:
    args = process_arguments("zHat", context, split_arguments, logger, zparser)
    # Returns: [None] (zHat not in context)
except Exception as e:
    print(f"Error: {e}")

# Invalid this.key
context = {"user_id": 42}
args = process_arguments("this.invalid_key", context, split_arguments, logger, zparser)
# Returns: [None] (key not found, logs warning)
```

---

## Integration with zFunc

**zFunc._parse_args_with_display() uses argument_processor:**

```python
# zFunc.py
def _parse_args_with_display(self, arg_str, zContext):
    from .zFunc_modules.arg_processing import process_arguments, split_arguments
    return process_arguments(arg_str, zContext, split_arguments, self.logger, self.zparser)
```

**Flow:**
1. `zFunc.handle()` extracts arg_str from zHorizontal
2. `_parse_args_with_display()` orchestrates processing
3. `process_arguments()` splits and injects
4. Processed args passed to executor

---

## Best Practices

1. **Special Argument Usage:**
   - Use zContext sparingly (exposes full context)
   - Prefer this.key for specific values
   - Use zHat only in wizard steps
   - Use zConv only in dialog handlers

2. **Function Design:**
   - Document special arguments in docstrings
   - Validate injected values in function
   - Provide defaults for optional special args

3. **Context Structure:**
   - Keep context flat when possible
   - Use clear key names
   - Document context requirements

4. **Testing:**
   - Test with missing context keys
   - Test with None/empty context
   - Test mixed special and regular args
   - Test nested JSON structures

5. **Error Handling:**
   - Validate context structure before use
   - Handle missing keys gracefully
   - Log warnings for debugging
   - Provide meaningful error messages

---

## Version History

- **v1.6.1**: Renamed argument_parser.py to argument_processor.py
- **v1.6.0**: Extracted from func_args.py during refactoring
  - Created arg_processing/ subpackage
  - Split into processor, splitter, injector
  - Clear separation from zParser
