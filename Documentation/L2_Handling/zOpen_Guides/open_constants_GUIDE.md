# zOpen Constants Module Guide

> **Module:** `zOS/core/L2_Handling/k_zOpen/open_modules/open_constants.py`  
> **Purpose:** Centralized constants, configuration values, and message strings for zOpen subsystem.

---

## Overview

The `constants` module provides a single source of truth for all zOpen-local constants, message strings, and configuration values.

> **Root vocabulary (SSOT):** cross-subsystem protocol literals are **not** redeclared here — they are imported from `core/zVocabulary.py` and kept as thin aliases so they can't drift from zLoader / zParser / zNavigation:
>
> ```python
> from zOS.zVocabulary import (
>     PATH_SYMBOL_AT, PATH_SYMBOL_TILDE,        # @ / ~
>     SESSION_KEY_IDE, SESSION_KEY_BROWSER,     # ide / browser
>     FILE_EXT_HTML, FILE_EXT_TXT, FILE_EXT_MD, # extension atoms
>     FILE_EXT_PY, FILE_EXT_JS, FILE_EXT_JSON,
>     FILE_EXT_YAML, FILE_EXT_YML,
>     CONTROL_RETURN_ZBACK, CONTROL_RETURN_STOP,  # zBack / stop
> )
> ```

---

## Public Constants

### Command/Request Keys

Used for parsing zOpen command dictionaries:

```python
DICT_KEY_ZOPEN = "zOpen"          # Root key
DICT_KEY_PATH = "path"            # Path to open
DICT_KEY_ON_SUCCESS = "onSuccess" # Success hook
DICT_KEY_ON_FAIL = "onFail"       # Failure hook
```

**Usage:**
```python
# Parse command dictionary
if DICT_KEY_ZOPEN in command_dict:
    path = command_dict[DICT_KEY_ZOPEN][DICT_KEY_PATH]
    on_success = command_dict[DICT_KEY_ZOPEN].get(DICT_KEY_ON_SUCCESS)
    on_fail = command_dict[DICT_KEY_ZOPEN].get(DICT_KEY_ON_FAIL)
```

---

### zPath Symbols

Used for zPath notation parsing and validation:

```python
ZPATH_SYMBOL_WORKSPACE = PATH_SYMBOL_AT     # "@"  (alias: zVocabulary)
ZPATH_SYMBOL_ABSOLUTE  = PATH_SYMBOL_TILDE  # "~"  (alias: zVocabulary)
ZPATH_SEPARATOR = "."                        # zOpen-local separator
```

**Usage:**
```python
# Validate zPath
if path.startswith(ZPATH_SYMBOL_WORKSPACE):
    # Workspace-relative path
    parts = path.split(ZPATH_SEPARATOR)
elif path.startswith(ZPATH_SYMBOL_ABSOLUTE):
    # Absolute path
    parts = path.split(ZPATH_SEPARATOR)
```

---

### URL Schemes

Used for URL detection and processing:

```python
URL_SCHEME_HTTP = "http"
URL_SCHEME_HTTPS = "https"
URL_SCHEMES_SUPPORTED = ("http", "https")
URL_PREFIX_WWW = "www."
URL_SCHEME_HTTPS_DEFAULT = "https://"
```

**Usage:**
```python
# Detect URL
if any(path.startswith(f"{scheme}://") for scheme in URL_SCHEMES_SUPPORTED):
    # Valid URL
    return open_url(path, ...)

# Handle www prefix
if path.startswith(URL_PREFIX_WWW):
    path = URL_SCHEME_HTTPS_DEFAULT + path
    return open_url(path, ...)
```

---

### File Extensions

Used for file type detection and routing:

```python
# Composed from zVocabulary FILE_EXT_* atoms (SSOT). ".htm" has no shared
# atom — it is a zOpen-local variant and stays a literal.
EXTENSIONS_HTML = (FILE_EXT_HTML, '.htm')                 # ('.html', '.htm')
EXTENSIONS_TEXT = (FILE_EXT_TXT, FILE_EXT_MD, FILE_EXT_PY,
                   FILE_EXT_JS, FILE_EXT_JSON,
                   FILE_EXT_YAML, FILE_EXT_YML)            # ('.txt','.md','.py','.js','.json','.yaml','.yml')
```

**Usage:**
```python
# Detect HTML file
if path.suffix.lower() in EXTENSIONS_HTML:
    return _open_html_file(path, ...)

# Detect text file
if path.suffix.lower() in EXTENSIONS_TEXT:
    return _open_text_file(path, ...)
```

---

### Return Values

Used for operation status codes:

```python
RETURN_ZBACK = CONTROL_RETURN_ZBACK  # "zBack" — success (alias: zVocabulary)
RETURN_STOP  = CONTROL_RETURN_STOP   # "stop"  — failure (alias: zVocabulary)
```

**Usage:**
```python
# Success
return RETURN_ZBACK

# Failure
return RETURN_STOP

# Check result
if result == RETURN_ZBACK:
    print("Success!")
```

---

### Machine Configuration Keys

Used for accessing zMachine preferences:

```python
ZMACHINE_KEY_IDE = SESSION_KEY_IDE          # "ide"     (alias: zVocabulary)
ZMACHINE_KEY_BROWSER = SESSION_KEY_BROWSER  # "browser" (alias: zVocabulary)
```

**Usage:**
```python
# Get IDE from session
ide = session.get(ZMACHINE_KEY_IDE, _DEFAULT_IDE)

# Get browser from session
browser = session.get(ZMACHINE_KEY_BROWSER)
```

---

### Display Colors

Used for color-coded terminal output:

```python
COLOR_ZOPEN = "ZOPEN"      # zOpen-specific color
COLOR_SUCCESS = "GREEN"    # Success messages
COLOR_ERROR = "RED"        # Error messages
COLOR_INFO = "INFO"        # Info messages
```

**Usage:**
```python
# Success message
display.print_message("Opened successfully", color=COLOR_SUCCESS)

# Error message
display.print_message("Failed to open", color=COLOR_ERROR)
```

---

## Internal Constants

These constants are used internally and not typically exposed to users:

### IDE/Browser Configuration

```python
_DEFAULT_IDE = "nano"           # Fallback IDE
_IDE_UNKNOWN = "unknown"        # Unrecognized IDE
_AVAILABLE_IDES = [             # Supported IDEs
    "cursor", "code", "nano", "vim"
]
_BROWSERS_SKIP = ("unknown",)   # Skip these browsers
```

### File Actions

```python
_FILE_ACTION_CREATE = "Create file"  # Create file option
_FILE_ACTION_CANCEL = "Cancel"       # Cancel option
_FILE_ACTIONS = [                    # Dialog options
    _FILE_ACTION_CREATE,
    _FILE_ACTION_CANCEL
]
```

### Display Styles

```python
_STYLE_FULL = "full"       # Full section borders
_STYLE_SINGLE = "single"   # Single line borders
_STYLE_SECTION = "~"       # Section separator
```

### Indentation Levels

```python
_INDENT_INIT = 0          # Initialization messages
_INDENT_HANDLE = 1        # Handle method messages
_INDENT_HOOK = 2          # Hook execution messages
_INDENT_FILE_INFO = 1     # File info display
_INDENT_URL_INFO = 1      # URL info display
```

### zPath Configuration

```python
_ZPATH_MIN_PARTS = 2  # min parts after the symbol (filename + extension)
```

### File Handling

```python
_CONTENT_TRUNCATE_LIMIT = 1000  # Max characters before truncation
_FILE_ENCODING = 'utf-8'        # File encoding
```

### Operating System

```python
_OS_WINDOWS = 'nt'  # Windows OS identifier
```

### Dialog Fields

```python
_DIALOG_FIELD_ACTION = "action"  # Action field name
_DIALOG_FIELD_IDE = "ide"        # IDE field name
```

---

## Message Strings

### Success Messages

```python
_MSG_ZOPEN_READY = "zOpen Ready"
_MSG_HANDLE_ZOPEN = "Handle zOpen"
_MSG_HOOK_SUCCESS = "[HOOK] onSuccess"
_MSG_HOOK_FAIL = "[HOOK] onFail"
_MSG_CREATED_FILE = "Created {path}"
_MSG_OPENED_BROWSER = "Opened {filename} in browser"
_MSG_OPENED_BROWSER_URL = "Opened URL in {browser}"
_MSG_OPENED_DEFAULT = "Opened URL in default browser"
_MSG_OPENED_IDE = "Opened {filename} in {ide}"
_MSG_FILE_CONTENT_TITLE = "File Content: {filename}"
_MSG_CONTENT_TRUNCATED = "[Content truncated - showing first {limit} of {total} characters]"
_MSG_URL_INFO_TITLE = "URL Information"
_MSG_URL_MANUAL = "Unable to open in browser. Please copy and paste into your browser."
_MSG_UNSUPPORTED_TYPE = "Unsupported file type: {ext}"
_MSG_MODE_BLOCKED = "zOpen is a local (zCLI) operation and is disabled in this mode."
```

**Usage:**
```python
# Format and display
display.print_message(
    _MSG_OPENED_IDE.format(filename="app.py", ide="cursor")
)
# Output: "Opened app.py in cursor"
```

### Error Messages

```python
# zPath errors
_ERR_NO_WORKSPACE = "No workspace set for relative path"
_ERR_INVALID_ZPATH = "Invalid zPath format"
_ERR_RESOLUTION_FAILED = "Failed to resolve zPath"

# File errors
_ERR_FILE_NOT_FOUND = "File not found: %s"
_ERR_DIALOG_FAILED = "Dialog fallback failed: %s"
_ERR_READ_FAILED = "Failed to read file: %s"
_ERR_UNSUPPORTED_TYPE = "Unsupported file type: %s"

# Browser errors
_ERR_BROWSER_FAILED = "Browser failed to open HTML file"
_ERR_BROWSER_FAILED_URL = "Browser failed to open URL"
_ERR_BROWSER_ERROR = "Browser error: %s"
_ERR_URL_OPEN_FAILED = "Unable to open URL. Displaying information instead."

# IDE errors
_ERR_IDE_FAILED = "Failed to open with IDE %s: %s"
```

**Usage:**
```python
# Log error with formatting
logger.error(_ERR_FILE_NOT_FOUND % path)

# Display error message
display.print_message(
    _ERR_UNSUPPORTED_TYPE % ext,
    color=COLOR_ERROR
)
```

---

## Log Messages

### zOpen Handler

```python
_LOG_INCOMING_REQUEST = "Incoming zOpen request: %s"
_LOG_PARSED_PATH = "Parsed path: %s"
_LOG_EXEC_SUCCESS_HOOK = "Executing onSuccess hook: %s"
_LOG_EXEC_FAIL_HOOK = "Executing onFail hook: %s"
_LOG_MODE_BLOCKED = "zOpen blocked: local-only operation requested in mode '%s' (fail-closed)"
```

> **Security constants:** `_MSG_MODE_BLOCKED` / `_LOG_MODE_BLOCKED` back the **fail-closed mode gate** (zOpen runs only in zCLI mode); `_LOG_IDE_UNRESOLVED` backs the **V2 exec hardening** (an editor the detector can't resolve is never launched — content is displayed instead). See the main guide's *Security & Trust* section.

### zPath Resolution

```python
_LOG_RESOLVING_ZPATH = "Resolving zPath: %s"
_LOG_RESOLVED_SUCCESS = "Resolved zPath '%s' to: %s"
_LOG_INVALID_FORMAT = "Invalid zPath format: %s"
_LOG_WORKSPACE_MISSING = "Workspace context missing for path: %s"
```

### File Operations

```python
_LOG_RESOLVED_PATH = "Resolved path: %s"
_LOG_FILE_NOT_FOUND = "File not found: %s"
_LOG_PROMPTING_USER = "Prompting user for action on missing file"
_LOG_CREATED_FILE = "Created file: %s"
_LOG_OPENING_HTML = "Opening HTML file: %s"
_LOG_SUCCESS_HTML = "Successfully opened HTML file in browser"
_LOG_OPENING_TEXT = "Opening text file: %s"
_LOG_USING_IDE = "Using IDE: %s"
_LOG_SUCCESS_IDE = "Successfully opened file with %s"
_LOG_IDE_SELECTION_FAILED = "IDE selection dialog failed: %s"
_LOG_IDE_UNRESOLVED = "IDE '%s' not resolved by detector allowlist; showing content instead of launching an unvalidated command"
_LOG_DISPLAYING_CONTENT = "Displaying text file content"
```

### URL Operations

```python
_LOG_OPENING_URL = "Opening URL: %s"
_LOG_USING_BROWSER = "Using browser: %s"
_LOG_SUCCESS_SPECIFIC = "Successfully opened URL in %s"
_LOG_SUCCESS_DEFAULT = "Successfully opened URL in system default browser"
_LOG_BROWSER_FAILED = "Browser failed to open URL"
_LOG_BROWSER_ERROR = "Browser error: %s"
```

**Usage:**
```python
# Debug logging
logger.debug(_LOG_RESOLVING_ZPATH % zpath)

# Info logging
logger.info(_LOG_SUCCESS_IDE % ide)

# Error logging
logger.error(_LOG_BROWSER_ERROR % str(error))
```

---

## Command Prefix

```python
_CMD_PREFIX = "zOpen("  # Used for string command detection
```

**Usage:**
```python
# Detect zOpen command
if horizontal_string.startswith(_CMD_PREFIX):
    # Route to zOpen handler
    return z.open.handle(horizontal_string)
```

---

## Module Exports

The `__all__` list defines the public API:

```python
__all__ = [
    # Command/Request Keys
    "DICT_KEY_ZOPEN",
    "DICT_KEY_PATH",
    "DICT_KEY_ON_SUCCESS",
    "DICT_KEY_ON_FAIL",

    # zPath Symbols
    "ZPATH_SYMBOL_WORKSPACE",
    "ZPATH_SYMBOL_ABSOLUTE",
    "ZPATH_SEPARATOR",

    # URL Schemes
    "URL_SCHEME_HTTP",
    "URL_SCHEME_HTTPS",
    "URL_SCHEMES_SUPPORTED",
    "URL_PREFIX_WWW",
    "URL_SCHEME_HTTPS_DEFAULT",

    # File Extensions
    "EXTENSIONS_HTML",
    "EXTENSIONS_TEXT",

    # Return Values
    "RETURN_ZBACK",
    "RETURN_STOP",

    # Machine Keys
    "ZMACHINE_KEY_IDE",
    "ZMACHINE_KEY_BROWSER",

    # Colors (Display Integration)
    "COLOR_ZOPEN",
    "COLOR_SUCCESS",
    "COLOR_ERROR",
    "COLOR_INFO",
]
```

---

## Usage Patterns

### Import Public Constants

```python
from zOS.L2_Handling.k_zOpen.open_modules.open_constants import (
    DICT_KEY_ZOPEN,
    DICT_KEY_PATH,
    EXTENSIONS_HTML,
    EXTENSIONS_TEXT,
    RETURN_ZBACK,
    RETURN_STOP,
)
```

### Import All (Within Module)

```python
from .open_constants import *
```

### Access Internal Constants

```python
# Within zOpen modules only
from .open_constants import (
    _DEFAULT_IDE,
    _AVAILABLE_IDES,
    _MSG_OPENED_IDE,
    _ERR_FILE_NOT_FOUND,
)
```

---

## Best Practices

### Adding New Constants

When adding constants:
1. Choose appropriate category
2. Use descriptive names
3. Add docstring if complex
4. Export via `__all__` if public
5. Document in this guide

**Example:**
```python
# Add new file extension
EXTENSIONS_TYPESCRIPT = ('.ts', '.tsx')

# Export if public
__all__.append("EXTENSIONS_TYPESCRIPT")

# Document in guide
# ### TypeScript Files
# ```python
# EXTENSIONS_TYPESCRIPT = ('.ts', '.tsx')
# ```
```

### Using Message Strings

Always use constants for messages:

```python
# Good
display.print_message(_MSG_OPENED_IDE.format(...))

# Bad (hardcoded)
display.print_message(f"Opened {filename} in {ide}")
```

**Benefits:**
- Centralized updates
- Consistent messaging
- Easy i18n support
- Typo prevention

### Color Consistency

Always use color constants:

```python
# Good
display.print_message("Success!", color=COLOR_SUCCESS)

# Bad (hardcoded)
display.print_message("Success!", color="GREEN")
```

---

## Future Extensions

### Internationalization (i18n)

Constants structure supports easy i18n:

```python
# Current (English)
_MSG_OPENED_IDE = "Opened {filename} in {ide}"

# Future (with i18n)
def get_message(key, locale="en"):
    messages = {
        "en": {
            "opened_ide": "Opened {filename} in {ide}",
        },
        "es": {
            "opened_ide": "Abrió {filename} en {ide}",
        },
    }
    return messages[locale].get(key)
```

### Configuration Loading

Future: Load constants from config:

```python
# Load from zEnv or YAML
EXTENSIONS_CUSTOM = load_config("zopen.extensions.custom")
```

---

**[← Back to zOpen Guide](../zOpen_GUIDE.md)**
