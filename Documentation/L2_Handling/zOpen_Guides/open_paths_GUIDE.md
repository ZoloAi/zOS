# zOpen Paths Module Guide

> **Module:** `zOS/core/L2_Handling/k_zOpen/open_modules/open_paths.py`  
> **Purpose:** zPath notation resolution for workspace-relative and absolute file references.

---

## Overview

The `paths` module provides declarative path notation (**zPath**) using symbols to reference files relative to workspace or filesystem root. It eliminates hardcoded paths and makes file references portable across machines.

---

## zPath Notation

### Symbols

| Symbol | Meaning | Example | Resolves To |
|--------|---------|---------|-------------|
| `@` | Workspace-relative | `@.README.md` | `/workspace/README.md` |
| `~` | Absolute from root | `~.Users.alice.notes.txt` | `/Users/alice/notes.txt` |
| `.` | Path separator | `@.docs.setup.md` | `/workspace/docs/setup.md` |

**Why zPath?**
- **Portable:** Works across machines regardless of actual workspace path
- **Declarative:** References intent (workspace file) not implementation (hardcoded path)
- **Type-safe:** Validated before resolution
- **Clear intent:** @ means workspace, ~ means absolute

---

## API Reference

### `resolve_zpath(zpath, session, logger)`

Resolves a zPath string to an actual filesystem path.

**Parameters:**
- `zpath` (str): zPath string starting with @ or ~
- `session` (dict): zOS session containing workspace directory
- `logger` (Logger): Logger for debug output

**Returns:**
- `str | None`: Resolved absolute filesystem path string, or `None` if validation fails / workspace missing

**Examples:**
```python
from zOS.L2_Handling.k_zOpen.open_modules import resolve_zpath

# Workspace-relative
path = resolve_zpath("@.README.md", session, logger)
# Returns: "/workspace/README.md"  (absolute path string)

# Nested workspace path
path = resolve_zpath("@.docs.setup.md", session, logger)
# Returns: "/workspace/docs/setup.md"

# Absolute path
path = resolve_zpath("~.Users.alice.notes.txt", session, logger)
# Returns: "/Users/alice/notes.txt"
```

**Validation:**
- Must start with @ or ~ (or no symbol → treated as a normal relative path)
- After removing the symbol, must have **at least 2 parts** (filename + extension)
- Logs error and returns `None` for invalid paths / missing workspace

**Resolution Process:**
1. Strips leading dots, splits by `.` separator
2. `@` → base = `session["zSpace"]` (returns `None` if unset)
3. `~` → base = `os.path.sep` (filesystem root)
4. no symbol → base = `""` (resolved relative to CWD via `os.path.abspath`)
5. Treats the **last two** components as `filename` + `extension`
6. Returns `os.path.abspath(os.path.join(base, *dirs, "filename.ext"))` — an **absolute path string** (not a `Path`)

---

### `validate_zpath(zpath)`

Validates zPath format before resolution.

**Parameters:**
- `zpath` (str): zPath string to validate

**Returns:**
- `bool`: True if valid, False otherwise

**Validation Rules:**
- Must start with `@` or `~` (after stripping leading dots)
- After the symbol, must have **at least 2 parts** (name + extension) — i.e. ≥ 3 dot-parts total
- Format-only (does **not** check workspace availability)

**Examples:**
```python
from zOS.L2_Handling.k_zOpen.open_modules import validate_zpath

# Valid zPaths
validate_zpath("@.README.md")        # True
validate_zpath("~.Users.alice.file") # True (4 parts)
validate_zpath("@.docs.api.md")      # True

# Invalid zPaths
validate_zpath("README.md")          # False (no symbol)
validate_zpath("@")                  # False (no path)
validate_zpath("@.file")             # False (name but no extension → only 2 parts)
```

---

## Workspace Context

`@` resolution requires workspace context from the zOS session:

**Workspace source:**
- `session["zSpace"]` (the `SESSION_KEY_ZSPACE` constant) — a path string

```python
# From session
workspace = session.get("zSpace")  # str, e.g. "/Users/alice/projects/myapp"
```

**No workspace:**
- If `zSpace` is unset/empty, `@` paths **cannot** resolve → returns `None` with error log (`resolve_zpath` does **not** fall back to CWD/home for `@`)
- `~` paths still work (rooted at `os.path.sep`)
- No-symbol paths resolve relative to the current directory via `os.path.abspath`

---

## Path Resolution Examples

### Workspace-Relative (@)

Assuming workspace is `/Users/alice/projects/myapp`:

```python
# Simple file
"@.README.md"
→ /Users/alice/projects/myapp/README.md

# Nested directory
"@.docs.setup.md"
→ /Users/alice/projects/myapp/docs/setup.md

# Deep nesting
"@.src.components.button.tsx"
→ /Users/alice/projects/myapp/src/components/button.tsx

# Hidden file
"@..gitignore"
→ /Users/alice/projects/myapp/.gitignore
```

### Absolute Paths (~)

```python
# User directory
"~.Users.alice.notes.txt"
→ /Users/alice/notes.txt

# System directory
"~.etc.config.yaml"
→ /etc/config.yaml

# Temp directory
"~.tmp.test.log"
→ /tmp/test.log

# Deep nesting
"~.Users.alice.Documents.notes.personal.diary.txt"
→ /Users/alice/Documents/notes/personal/diary.txt
```

---

## Error Handling

### Invalid Format

```python
# Missing symbol
resolve_zpath("README.md", session, logger)
→ None + error log

# Missing path component
resolve_zpath("@", session, logger)
→ None + error log

# Empty path
resolve_zpath("@.", session, logger)
→ None + error log
```

### Missing Workspace

```python
# Workspace not set in session
session = {}  # No zSpace

resolve_zpath("@.README.md", session, logger)
→ None + error log: "No workspace set for relative path"

# Absolute paths still work
resolve_zpath("~.tmp.test.log", session, logger)
→ "/tmp/test.log"
```

---

## Integration with zOpen

zPath resolution is called automatically by zOpen:

```python
# From zOpen.handle()
result = z.open.handle("zOpen(@.README.md)")

# Internal flow:
# 1. Detect @ symbol
# 2. Call resolve_zpath("@.README.md", session, logger)
# 3. Get "/workspace/README.md" (absolute string)
# 4. Call open_file(path, zos, ...)  ← path-trust gate runs here
# 5. Open in appropriate application
```

**No manual resolution needed** - zOpen detects zPath notation and resolves automatically.

---

## Best Practices

### When to Use @

Use workspace-relative (@) for:
- Project documentation (README, GUIDE)
- Source code files within project
- Configuration files in project
- Test files in project
- Any file that moves with the workspace

**Benefits:**
- Portable across machines
- Works in different workspace locations
- No hardcoded paths
- Clear intent (project file)

### When to Use ~

Use absolute paths (~) for:
- System configuration files (/etc/*)
- User home directory files
- System logs (/var/log/*)
- Temp files (/tmp/*)
- Files outside workspace

**Benefits:**
- Explicit filesystem location
- No workspace dependency
- System-level references
- Clear intent (absolute)

### When NOT to Use zPath

Don't use zPath for:
- User input (let them type normal paths)
- URLs (use http:// or https://)
- Already resolved paths (from Path objects)
- Dynamic paths (use Path operations)

**Use normal paths when:**
- Accepting user input
- Building paths dynamically
- Working with Path objects directly
- Interacting with APIs

---

## Constants Reference

From `open_constants.py`:

```python
# zPath symbols — alias the root zVocabulary atoms (SSOT)
ZPATH_SYMBOL_WORKSPACE = zVocabulary.PATH_SYMBOL_AT     # "@"
ZPATH_SYMBOL_ABSOLUTE  = zVocabulary.PATH_SYMBOL_TILDE  # "~"
ZPATH_SEPARATOR = "."

# Validation
_ZPATH_MIN_PARTS = 2  # name + extension (after the symbol is removed)
```

> The `@`/`~` symbol literals are single-sourced in `core/zVocabulary.py`; `open_constants` keeps the historical names as thin aliases. The resolution *algorithm* stays local to zOpen (its contract differs from `zParser.zPath_decoder`).

---

## Logging

The module logs at different levels:

**DEBUG:**
- `"Resolving zPath: @.README.md"`
- `"Resolved zPath '@.README.md' to: /workspace/README.md"`

**ERROR:**
- `"Invalid zPath format: README.md"`
- `"Workspace context missing for path: @.README.md"`
- `"Failed to resolve zPath"`

**Usage:**
```python
# Enable debug logging
z = zOS({
    "logger": "DEBUG",
    "logger_path": "./logs",
})

# See zPath resolution in logs
result = z.open.handle("zOpen(@.README.md)")
```

---

## Testing zPath Resolution

Test zPath validation:
```python
from zOS.L2_Handling.k_zOpen.open_modules import validate_zpath

# Valid
assert validate_zpath("@.README.md") == True
assert validate_zpath("~.Users.file.txt") == True

# Invalid
assert validate_zpath("README.md") == False
assert validate_zpath("@") == False
```

Test zPath resolution:
```python
from zOS.L2_Handling.k_zOpen.open_modules import resolve_zpath

# Mock session with workspace (string path)
session = {"zSpace": "/workspace"}

# Test workspace-relative (returns an absolute path string)
path = resolve_zpath("@.README.md", session, logger)
assert path == "/workspace/README.md"

# Test absolute
path = resolve_zpath("~.tmp.test.log", session, logger)
assert path == "/tmp/test.log"
```

---

## Common Patterns

### Project Documentation

```python
# Open project README
z.open.handle("zOpen(@.README.md)")

# Open API docs
z.open.handle("zOpen(@.docs.api.md)")

# Open setup guide
z.open.handle("zOpen(@.docs.setup.md)")
```

### Source Code

```python
# Open main app file
z.open.handle("zOpen(@.src.app.py)")

# Open component
z.open.handle("zOpen(@.src.components.button.tsx)")

# Open test file
z.open.handle("zOpen(@.tests.test_app.py)")
```

### Configuration Files

```python
# Project config
z.open.handle("zOpen(@.config.settings.yaml)")

# Environment variables
z.open.handle("zOpen(@..env)")

# Package config
z.open.handle("zOpen(@.package.json)")
```

### System Files

```python
# System config
z.open.handle("zOpen(~.etc.hosts)")

# User config
z.open.handle("zOpen(~.Users.alice.bashrc)")

# System log
z.open.handle("zOpen(~.var.log.system.log)")
```

---

**[← Back to zOpen Guide](../zOpen_GUIDE.md)**
