# Resolvers Module

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**

---

## Overview

The Resolvers module provides link resolution and expression evaluation for navigation. It parses zLink expressions, resolves navigation targets, and integrates with zParser for dynamic expression evaluation.

**Module:** `navigation_modules/resolvers/`

## Purpose

- **Expression Parsing**: Parse zLink expression syntax
- **Target Resolution**: Resolve navigation targets to file paths
- **Variable Evaluation**: Evaluate variables in navigation expressions
- **Path Construction**: Build file paths from navigation targets

## Resolver Components

### resolver_zlink.py

**Purpose:** zLink expression resolution and target parsing

**Key Responsibilities:**
- Parse zLink expression syntax
- Extract folder, file, and block components
- Validate expression structure
- Construct file paths from targets

**Public API:**
```python
# Parse zLink expression
parsed = z.cli.navigation.resolvers.zlink.parse(
    expression="zLink(users.menu.list_users)"
)
# Returns: {'folder': 'users', 'file': 'menu', 'block': 'list_users'}

# Resolve to file path
path = z.cli.navigation.resolvers.zlink.resolve_path(
    folder="users",
    file="menu"
)
# Returns: "users/menu.yaml"

# Validate expression
is_valid = z.cli.navigation.resolvers.zlink.validate(
    expression="zLink(users.menu)"
)
# Returns: True or False
```

---

## Expression Syntax

### Basic zLink Format

```
zLink(folder.file.block)
```

**Components:**
- `folder`: Directory containing UI file
- `file`: UI file name (without extension)
- `block`: Block identifier within file (optional)

**Examples:**
```python
# File-level navigation (no specific block)
"zLink(users.menu)"

# Block-level navigation
"zLink(users.menu.list_users)"

# Nested folders
"zLink(admin.settings.security)"
```

---

### Variable Substitution

zLink expressions support variable substitution via zParser:

```python
# Set variables in session
z.session['zVars']['current_section'] = 'users'
z.session['zVars']['current_file'] = 'menu'

# Use variables in expression
expression = "zLink({current_section}.{current_file})"

# Resolved to: "zLink(users.menu)"
```

**Variable Syntax:**
- Single braces: `{variable_name}`
- Supports nested variables: `{section.{subsection}}`

---

### Dynamic Expressions

Build zLink expressions dynamically:

```python
# Construct from data
user_id = 42
expression = f"zLink(users.edit.{user_id})"

# Construct from function
def get_navigation_target(user_role):
    if user_role == 'admin':
        return "zLink(admin.dashboard)"
    else:
        return "zLink(user.dashboard)"

expression = get_navigation_target(z.session.get('user_role'))
```

---

## Usage Examples

### Parse Expression

```python
# Parse zLink expression into components
expression = "zLink(users.menu.list_users)"
parsed = z.cli.navigation.resolvers.zlink.parse(expression)

print(f"Folder: {parsed['folder']}")    # users
print(f"File: {parsed['file']}")        # menu
print(f"Block: {parsed['block']}")      # list_users
```

### Resolve File Path

```python
# Convert components to file path
path = z.cli.navigation.resolvers.zlink.resolve_path(
    folder="users",
    file="menu"
)

print(f"File path: {path}")  # users/menu.yaml

# With nested folders
path = z.cli.navigation.resolvers.zlink.resolve_path(
    folder="admin/settings",
    file="security"
)

print(f"File path: {path}")  # admin/settings/security.yaml
```

### Validate Expression

```python
# Validate before parsing
expressions = [
    "zLink(users.menu)",           # Valid
    "zLink(users.menu.list)",      # Valid
    "zLink(invalid)",              # Invalid (missing file)
    "users.menu",                  # Invalid (missing zLink wrapper)
]

for expr in expressions:
    is_valid = z.cli.navigation.resolvers.zlink.validate(expr)
    status = "✓" if is_valid else "✗"
    print(f"{status} {expr}")
```

### Variable Substitution

```python
# Set navigation variables
z.session['zVars']['section'] = 'users'
z.session['zVars']['action'] = 'list'

# Build expression with variables
expression = "zLink({section}.menu.{action})"

# Parse with variable evaluation
parsed = z.cli.navigation.resolvers.zlink.parse(
    expression,
    evaluate_variables=True
)

# Result: {'folder': 'users', 'file': 'menu', 'block': 'list'}
```

---

## Advanced Features

### Custom Path Resolvers

Register custom path resolution logic:

```python
# Define custom resolver
def custom_resolver(folder, file):
    """Custom path resolution with prefix."""
    return f"custom_prefix/{folder}/{file}.yaml"

# Register resolver
z.cli.navigation.resolvers.zlink.register_resolver(custom_resolver)

# Use in resolution
path = z.cli.navigation.resolvers.zlink.resolve_path("users", "menu")
# Returns: "custom_prefix/users/menu.yaml"
```

### Expression Caching

Cache parsed expressions for performance:

```python
# Enable expression caching
z.cli.navigation.resolvers.zlink.enable_cache()

# First parse (cache miss)
parsed1 = z.cli.navigation.resolvers.zlink.parse("zLink(users.menu)")

# Second parse (cache hit - faster)
parsed2 = z.cli.navigation.resolvers.zlink.parse("zLink(users.menu)")

# Clear cache
z.cli.navigation.resolvers.zlink.clear_cache()
```

### Expression Validation Rules

Add custom validation rules:

```python
# Define custom validation
def validate_admin_access(parsed_expression):
    """Ensure admin sections require admin role."""
    if parsed_expression['folder'] == 'admin':
        user_role = z.session.get('user_role')
        return user_role == 'admin'
    return True

# Register validation rule
z.cli.navigation.resolvers.zlink.add_validation_rule(validate_admin_access)

# Validate with custom rules
is_valid = z.cli.navigation.resolvers.zlink.validate(
    "zLink(admin.settings)",
    apply_custom_rules=True
)
```

---

## Error Handling

### Invalid Expression Format

```python
# Malformed expression
expression = "zLink(invalid)"  # Missing file component

try:
    parsed = z.cli.navigation.resolvers.zlink.parse(expression)
except ValueError as e:
    print(f"Parse error: {e}")
    # Output: Parse error: Invalid expression format - missing file component
```

### Missing Variables

```python
# Expression with undefined variable
expression = "zLink({undefined_var}.menu)"

try:
    parsed = z.cli.navigation.resolvers.zlink.parse(
        expression,
        evaluate_variables=True
    )
except KeyError as e:
    print(f"Variable error: {e}")
    # Output: Variable error: Undefined variable 'undefined_var'
```

### Invalid Path Resolution

```python
# Path with invalid characters
try:
    path = z.cli.navigation.resolvers.zlink.resolve_path(
        folder="../../../etc",  # Path traversal attempt
        file="passwd"
    )
except ValueError as e:
    print(f"Security error: {e}")
    # Output: Security error: Invalid path - contains path traversal
```

---

## Integration Points

**Depends on:**
- zParser: Variable evaluation
- zSession: Variable storage (zVars)

**Used by:**
- Linking: zLink navigation
- Menu System: Navigation actions
- zWalker: File loading and navigation

---

## Best Practices

### Expression Format

```python
# Good: Clear, hierarchical
"zLink(users.menu.list)"
"zLink(admin.settings.security)"

# Bad: Unclear, flat
"zLink(page1)"
"zLink(screen)"
```

### Variable Naming

```python
# Good: Descriptive variable names
z.session['zVars']['current_section'] = 'users'
z.session['zVars']['current_action'] = 'edit'

# Bad: Cryptic variable names
z.session['zVars']['cs'] = 'users'
z.session['zVars']['a'] = 'edit'
```

### Validation

```python
# Good: Always validate before use
if z.cli.navigation.resolvers.zlink.validate(expression):
    parsed = z.cli.navigation.resolvers.zlink.parse(expression)
    # Process parsed expression
else:
    print("Invalid expression")

# Bad: No validation
parsed = z.cli.navigation.resolvers.zlink.parse(untrusted_input)
```

### Error Handling

```python
# Good: Handle parse errors gracefully
try:
    parsed = z.cli.navigation.resolvers.zlink.parse(expression)
    # Use parsed result
except ValueError as e:
    print(f"Parse error: {e}")
    # Fallback to default navigation
    parsed = {'folder': 'home', 'file': 'menu', 'block': None}

# Bad: No error handling
parsed = z.cli.navigation.resolvers.zlink.parse(expression)
# Crash if expression invalid
```

---

## Performance Considerations

### Expression Caching

Enable caching for frequently used expressions:

```python
# Enable caching (recommended for production)
z.cli.navigation.resolvers.zlink.enable_cache()

# Cache configuration
z.cli.navigation.resolvers.zlink.configure_cache(
    max_size=1000,       # Maximum cached expressions
    ttl_seconds=3600     # Cache expiration (1 hour)
)
```

### Batch Resolution

Resolve multiple expressions efficiently:

```python
# Batch parse multiple expressions
expressions = [
    "zLink(users.menu)",
    "zLink(settings.profile)",
    "zLink(admin.dashboard)"
]

parsed_batch = z.cli.navigation.resolvers.zlink.parse_batch(expressions)

for expr, result in zip(expressions, parsed_batch):
    print(f"{expr} → {result}")
```

---

## Related Modules

- [linking_GUIDE.md](linking_GUIDE.md) - Inter-file navigation with zLink
- [navigation_state_GUIDE.md](navigation_state_GUIDE.md) - Navigation state tracking

**[← Back to zNavigation Guide](../zNavigation_GUIDE.md)**
