# zParser Utils Module Guide

**[← Back to zParser Guide](../zParser_GUIDE.md)**

---

## Overview

The **utils module** provides comprehensive expression evaluation and utility parsing:

- **Expression evaluation** (JSON expressions, safe evaluation)
- **Dotted path parsing** (`user.profile.name`)
- **Reference handling** (zRef: `{{variable}}`)
- **Parser directives** (zParser: `{{@directive}}`)
- **Function path parsing** (for zFunc integration)

## Module Structure

The utils module includes:

```
parser_utils.py      # Expression evaluation, dotted paths, references
parser_functions.py  # Function path parsing (for zFunc)
parser_constants.py  # Shared constants
```

---

## Main Functions

### `zExpr_eval(expr: str, logger, session=None) -> Any`

Evaluate JSON-like expressions safely.

**Features:**
- Safe evaluation (no `eval()` risks)
- Supports JSON objects, arrays, primitives
- Handles nested structures
- Returns parsed Python objects

**Examples:**
```python
# JSON objects
result = z.parser.zExpr_eval('{"name": "Alice", "age": 30}')
# → {"name": "Alice", "age": 30}

# JSON arrays
result = z.parser.zExpr_eval('[1, 2, 3, 4, 5]')
# → [1, 2, 3, 4, 5]

# Nested structures
result = z.parser.zExpr_eval('{"users": [{"name": "Alice"}, {"name": "Bob"}]}')
# → {"users": [{"name": "Alice"}, {"name": "Bob"}]}

# Primitives
result = z.parser.zExpr_eval('42')
# → 42

result = z.parser.zExpr_eval('"Hello World"')
# → "Hello World"

result = z.parser.zExpr_eval('true')
# → True
```

**Why Not Use `eval()`?**
- `eval()` is dangerous - can execute arbitrary code
- `zExpr_eval()` only parses JSON-like expressions
- No code execution, only data structures
- Safe for user input

---

### `parse_dotted_path(path: str, logger) -> List[str]`

Parse dotted notation paths into components.

**Examples:**
```python
# Simple path
parts = z.parser.parse_dotted_path("user.name")
# → ["user", "name"]

# Nested path
parts = z.parser.parse_dotted_path("user.profile.settings.theme")
# → ["user", "profile", "settings", "theme"]

# Array access (future feature)
parts = z.parser.parse_dotted_path("users.0.name")
# → ["users", "0", "name"]
```

**Use Cases:**
- Navigate nested dictionaries
- Access nested configuration values
- Parse data paths in templates
- Dynamic property access

---

### `handle_zRef(expr: str, logger, context: dict) -> Any`

Handle zRef YAML reference expressions.

**zRef Format:** `{{variable_name}}`

**Examples:**
```python
# Context with variables
context = {
    "user_name": "Alice",
    "user_email": "alice@example.com",
    "app_title": "Dashboard"
}

# Resolve zRef
result = z.parser.handle_zRef("{{user_name}}", context)
# → "Alice"

result = z.parser.handle_zRef("{{app_title}}", context)
# → "Dashboard"

# Nested resolution
context = {
    "settings": {"theme": "dark", "language": "en"}
}
result = z.parser.handle_zRef("{{settings.theme}}", context)
# → "dark"
```

**Where zRef is Used:**
- UI templates (variable substitution)
- Configuration files (dynamic values)
- Wizard steps (form data references)
- Navigation linking (dynamic targets)

---

### `handle_zParser(expr: str, logger, session: dict) -> Any`

Handle zParser directive expressions.

**zParser Format:** `{{@directive}}`

**Supported Directives:**
- `{{@session.key}}` - Access session values
- `{{@config.key}}` - Access config values
- `{{@env.VAR}}` - Access environment variables

**Examples:**
```python
# Session directive
result = z.parser.handle_zParser("{{@session.user_id}}", session)
# → Resolves to session["user_id"]

# Config directive
result = z.parser.handle_zParser("{{@config.deployment}}")
# → Resolves to z.config.get_environment("deployment")

# Environment variable
result = z.parser.handle_zParser("{{@env.DATABASE_URL}}")
# → Resolves to os.getenv("DATABASE_URL")
```

---

### `parse_function_path(func_path: str, logger) -> Dict[str, str]`

Parse function path for zFunc integration.

**Format:** `<module>.<function>`

**Examples:**
```python
# Simple function path
result = z.parser.parse_function_path("users.list")
# → {"module": "users", "function": "list"}

# Nested module
result = z.parser.parse_function_path("api.users.get")
# → {"module": "api.users", "function": "get"}

# Single function (no module)
result = z.parser.parse_function_path("main")
# → {"module": None, "function": "main"}
```

**Used By:**
- zFunc (function module resolution)
- zDispatch (command routing)
- zLoader (module loading)

---

## Expression Evaluation Deep Dive

### JSON Object Expressions

```python
# Simple object
result = z.parser.zExpr_eval('{"key": "value"}')

# Nested object
result = z.parser.zExpr_eval('''
{
  "user": {
    "name": "Alice",
    "profile": {
      "age": 30,
      "location": "SF"
    }
  }
}
''')
```

### JSON Array Expressions

```python
# Simple array
result = z.parser.zExpr_eval('[1, 2, 3]')

# Mixed types
result = z.parser.zExpr_eval('[1, "two", true, null]')

# Nested arrays
result = z.parser.zExpr_eval('[[1, 2], [3, 4], [5, 6]]')
```

### Primitive Expressions

```python
# Numbers
result = z.parser.zExpr_eval('42')        # → 42
result = z.parser.zExpr_eval('3.14')      # → 3.14
result = z.parser.zExpr_eval('-10')       # → -10

# Strings
result = z.parser.zExpr_eval('"Hello"')   # → "Hello"
result = z.parser.zExpr_eval("'World'")   # → "World"

# Booleans
result = z.parser.zExpr_eval('true')      # → True
result = z.parser.zExpr_eval('false')     # → False

# Null
result = z.parser.zExpr_eval('null')      # → None
```

---

## Dotted Path Navigation

Use parsed dotted paths to navigate nested structures:

```python
# Parse path
path = "user.profile.settings.theme"
parts = z.parser.parse_dotted_path(path)
# → ["user", "profile", "settings", "theme"]

# Navigate data
data = {
    "user": {
        "profile": {
            "settings": {
                "theme": "dark",
                "language": "en"
            }
        }
    }
}

# Access nested value
value = data
for part in parts:
    value = value[part]
# → "dark"
```

**Helper Function:**
```python
def get_nested_value(data, dotted_path):
    """Get value from nested dict using dotted path."""
    parts = z.parser.parse_dotted_path(dotted_path)
    value = data
    for part in parts:
        value = value.get(part)
        if value is None:
            return None
    return value

# Usage
theme = get_nested_value(data, "user.profile.settings.theme")
# → "dark"
```

---

## Reference Resolution

### zRef (YAML References)

Used in UI templates and configuration files:

**Template:**
```yaml
UI:
  header:
    label: "{{app_title}}"
    subtitle: "Welcome, {{user_name}}"
  table:
    title: "{{section_title}}"
```

**Resolution:**
```python
context = {
    "app_title": "Dashboard",
    "user_name": "Alice",
    "section_title": "Users"
}

# Resolve all zRefs in template
def resolve_zrefs(template, context):
    """Recursively resolve zRefs in template."""
    if isinstance(template, str):
        if "{{" in template and "}}" in template:
            return z.parser.handle_zRef(template, context)
        return template
    elif isinstance(template, dict):
        return {k: resolve_zrefs(v, context) for k, v in template.items()}
    elif isinstance(template, list):
        return [resolve_zrefs(item, context) for item in template]
    return template

resolved = resolve_zrefs(template, context)
```

---

### zParser (Directives)

Access framework values dynamically:

**Examples in UI Files:**
```yaml
UI:
  header:
    label: "{{@session.page_title}}"
    user: "{{@session.user_name}}"
  config:
    mode: "{{@config.deployment}}"
    debug: "{{@config.logger}}"
  env:
    api_url: "{{@env.API_URL}}"
    db_host: "{{@env.DATABASE_HOST}}"
```

**Resolution:**
```python
# Resolve zParser directives
def resolve_zparser(template, session):
    """Recursively resolve zParser directives in template."""
    if isinstance(template, str):
        if "{{@" in template and "}}" in template:
            return z.parser.handle_zParser(template, session)
        return template
    elif isinstance(template, dict):
        return {k: resolve_zparser(v, session) for k, v in template.items()}
    elif isinstance(template, list):
        return [resolve_zparser(item, session) for item in template]
    return template

resolved = resolve_zparser(template, z.session)
```

---

## Function Path Resolution

Parse and resolve function paths for zFunc:

```python
# Parse function path
func_path = "users.list"
parsed = z.parser.parse_function_path(func_path)
# → {"module": "users", "function": "list"}

# Load module and get function
import importlib
module = importlib.import_module(parsed["module"])
func = getattr(module, parsed["function"])

# Call function
result = func(limit=10)
```

**Complex Paths:**
```python
# Nested modules
func_path = "api.v1.users.list"
parsed = z.parser.parse_function_path(func_path)
# → {"module": "api.v1.users", "function": "list"}

# Single-level function
func_path = "main"
parsed = z.parser.parse_function_path(func_path)
# → {"module": None, "function": "main"}
```

---

## Error Handling

All utils functions handle errors gracefully:

```python
# Invalid expression
result = z.parser.zExpr_eval('{invalid json}')
# Returns: None (logged error)

# Invalid dotted path
parts = z.parser.parse_dotted_path("")
# Returns: [] (empty list)

# Unknown zRef variable
result = z.parser.handle_zRef("{{unknown}}", context)
# Returns: "{{unknown}}" (unchanged, logged warning)

# Invalid function path
parsed = z.parser.parse_function_path("")
# Returns: {"module": None, "function": None}
```

---

## Use Cases

### 1. Dynamic UI Templates

```python
# UI template with variables
ui_template = {
    "header": {
        "label": "{{page_title}}",
        "user": "{{user_name}}"
    }
}

# Context from session
context = {
    "page_title": z.session.get("page_title", "Dashboard"),
    "user_name": z.session.get("user_name", "Guest")
}

# Resolve zRefs
resolved_ui = resolve_zrefs(ui_template, context)
```

### 2. Configuration Evaluation

```python
# Config with expressions
config_expr = '''
{
  "timeout": 30,
  "retries": 3,
  "endpoints": ["api1", "api2", "api3"]
}
'''

# Parse config
config = z.parser.zExpr_eval(config_expr)
```

### 3. Nested Data Access

```python
# Access nested config value
path = "database.postgres.host"
parts = z.parser.parse_dotted_path(path)

# Navigate config
value = config
for part in parts:
    value = value[part]
```

---

## Best Practices

1. **Use zExpr_eval for safe evaluation** - Never use `eval()` for user input
2. **Validate context before zRef resolution** - Ensure variables exist
3. **Handle missing values gracefully** - Return defaults for unknown variables
4. **Use dotted paths for nested access** - Cleaner than manual dict navigation
5. **Document zParser directives** - Make it clear what directives are supported

---

## Integration

The utils module integrates with:

- **zLoader** - Uses expression evaluation for dynamic loading
- **zWalker** - Uses zRef resolution for UI templates
- **zFunc** - Uses function path parsing for module resolution
- **zConfig** - Uses dotted path parsing for nested config access
- **zWizard** - Uses zRef resolution for form data
- **Navigation linking** - Uses expression evaluation for dynamic navigation

---

**[← Back to zParser Guide](../zParser_GUIDE.md)**
