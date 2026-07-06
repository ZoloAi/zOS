**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**

---

# Dispatch Constants

**Centralized constants** for zDispatch subsystem, providing consistent keys, modifiers, and configuration values across all dispatch modules.

## Overview

Constants are organized by category:

| Category | Purpose | Count |
|----------|---------|-------|
| **Subsystem Identity** | Name and color | 2 |
| **Command Prefixes** | String parsing patterns | 5 |
| **Dict Keys** | Command and data keys | 30+ |
| **Modifiers** | Flow control symbols | 7 |
| **Modes** | Execution modes | 3 |
| **Navigation** | Navigation constants | 1 |
| **Plugins** | Plugin prefix | 1 |
| **Internal** | Implementation details | 50+ |

---

## Subsystem Identity

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    SUBSYSTEM_NAME,    # "zDispatch"
    SUBSYSTEM_COLOR,   # "DISPATCH"
)

# Usage
logger.info(f"{SUBSYSTEM_NAME} initialized")
display.zDeclare("Message", color=SUBSYSTEM_COLOR)
```

---

## Command Prefixes (String Format)

**Used for parsing string commands like `"zFunc(...)"`.** 

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    CMD_PREFIX_ZFUNC,     # "zFunc("
    CMD_PREFIX_ZLINK,     # "zLink("
    CMD_PREFIX_ZOPEN,     # "zOpen("
    CMD_PREFIX_ZWIZARD,   # "zWizard("
    CMD_PREFIX_ZREAD,     # "zRead("
)

# Usage
if command_str.startswith(CMD_PREFIX_ZFUNC):
    # Parse zFunc command
    pass
```

### Examples

```python
# Detect command type
def detect_command_type(command_str):
    if command_str.startswith(CMD_PREFIX_ZFUNC):
        return "zFunc"
    elif command_str.startswith(CMD_PREFIX_ZWIZARD):
        return "zWizard"
    elif command_str.startswith(CMD_PREFIX_ZREAD):
        return "zRead"
    return None
```

---

## Dict Keys - Subsystem Commands

**Used to build dict-format commands.**

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    KEY_ZFUNC,      # "zFunc"
    KEY_ZLINK,      # "zLink"
    KEY_ZDELTA,     # "zDelta"
    KEY_ZOPEN,      # "zOpen"
    KEY_ZWIZARD,    # "zWizard"
    KEY_ZREAD,      # "zRead"
    KEY_ZDATA,      # "zData"
    KEY_ZDIALOG,    # "zDialog"
    KEY_ZDISPLAY,   # "zDisplay"
    KEY_ZLOGIN,     # "zLogin"
    KEY_ZLOGOUT,    # "zLogout"
    KEY_ZDELEGATE,  # "zDelegate" — in-place activation rewiring (routeless, AJAX-like)
    KEY_ZEXPORT,    # "zExport"   — model|inline → response (see transfer_GUIDE)
    KEY_ZIMPORT,    # "zImport"   — file → model     (see transfer_GUIDE)
    KEY_ZTRANSFER,  # "zTransfer" — explicit source→target (see transfer_GUIDE)
    KEY_ZDASH,      # "zDash"
    KEY_ZVAR,       # "zVar"
    KEY_ZLIST,      # "zList"
)

# Usage
command = {
    KEY_ZFUNC: "my_function",
    "args": [arg1, arg2]
}
```

> **Event-binding keys (inert):** `EVENT_BINDING_KEYS` (`onChange`, `onClick`,
> `onSubmit`, `onLoad`, `onInput`, `onFocus`, `onBlur`) is a `frozenset` of
> declarative bindings. The dispatch/walker treats them as **inert during
> render** — never recursed into, never executed inline.

### Examples

```python
# Build command
command = {
    KEY_ZDATA: {
        KEY_ACTION: "read",
        KEY_MODEL: "users",
        KEY_WHERE: {"id": 1}
    }
}

# Check command type
if KEY_ZFUNC in command:
    # Handle function command
    pass
elif KEY_ZWIZARD in command:
    # Handle wizard command
    pass
```

---

## Dict Keys - Data Operations

**Used for CRUD operations with zData.**

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    KEY_ACTION,     # "action"
    KEY_MODEL,      # "model"
    KEY_TABLE,      # "table"
    KEY_TABLES,     # "tables"
    KEY_FIELDS,     # "fields"
    KEY_VALUES,     # "values"
    KEY_FILTERS,    # "filters"
    KEY_WHERE,      # "where"
    KEY_ORDER_BY,   # "order_by"
    KEY_LIMIT,      # "limit"
    KEY_OFFSET,     # "offset"
)

# Usage
crud_command = {
    KEY_ACTION: "read",
    KEY_MODEL: "users",
    KEY_WHERE: {"active": True},
    KEY_LIMIT: 10
}
```

### Examples

```python
# Read operation
read_cmd = {
    KEY_ACTION: "read",
    KEY_MODEL: "users",
    KEY_WHERE: {"id": 1}
}

# List operation
list_cmd = {
    KEY_ACTION: "list",
    KEY_MODEL: "products",
    KEY_FILTERS: {"category": "electronics"},
    KEY_ORDER_BY: "price",
    KEY_LIMIT: 20,
    KEY_OFFSET: 0
}

# Create operation
create_cmd = {
    KEY_ACTION: "create",
    KEY_MODEL: "orders",
    KEY_VALUES: {
        "user_id": 123,
        "total": 99.99
    }
}

# Update operation
update_cmd = {
    KEY_ACTION: "update",
    KEY_MODEL: "users",
    KEY_VALUES: {"status": "active"},
    KEY_WHERE: {"id": 1}
}
```

---

## Dict Keys - Context & Session

**Used for context passing and session management.**

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    KEY_ZVAFILE,    # "zVaFile"
    KEY_ZBLOCK,     # "zBlock"
)

# Usage
context = {
    KEY_ZVAFILE: "admin.zui",
    KEY_ZBLOCK: "main_menu"
}
```

---

## Dict Keys - Display & UI

**Used for UI operations.**

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    KEY_CONTENT,    # "content"
    KEY_INDENT,     # "indent"
    KEY_EVENT,      # "event"
    KEY_LABEL,      # "label"
    KEY_COLOR,      # "color"
    KEY_STYLE,      # "style"
    KEY_MESSAGE,    # "message"
)

# Usage
display_event = {
    KEY_EVENT: "text",
    KEY_CONTENT: "Hello World",
    KEY_COLOR: "SUCCESS",
    KEY_INDENT: 2
}
```

---

## Modifiers

**Flow control symbols.**

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    MOD_CARET,         # "^" - Bounce back
    MOD_TILDE,         # "~" - Anchor (no back)
    MOD_ASTERISK,      # "*" - Menu
    MOD_EXCLAMATION,   # "!" - Required
    PREFIX_MODIFIERS,  # ["^", "~"]
    SUFFIX_MODIFIERS,  # ["!", "*"]
    ALL_MODIFIERS,     # ["^", "~", "!", "*"]
)

# Usage
def check_modifiers(zKey):
    prefix_mods = [mod for mod in PREFIX_MODIFIERS if zKey.startswith(mod)]
    suffix_mods = [mod for mod in SUFFIX_MODIFIERS if zKey.endswith(mod)]
    return prefix_mods + suffix_mods
```

### Examples

```python
# Check for bounce modifier
if zKey.startswith(MOD_CARET):
    # Execute and return
    pass

# Check for menu modifier
if zKey.endswith(MOD_ASTERISK):
    # Create menu
    pass

# Check for required modifier
if zKey.endswith(MOD_EXCLAMATION):
    # Retry until success
    pass

# Check for anchor modifier
if zKey.startswith(MOD_TILDE):
    # Disable back navigation
    pass
```

---

## Mode Values

**Execution mode detection.**

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    MODE_BIFROST,   # "zBifrost"
    MODE_ZCLI,      # "zCLI"
    MODE_WALKER,    # "Walker"
)

# Usage
from zOS.L1_Foundation.a_zConfig.zConfig_modules import SESSION_KEY_ZMODE

mode = z.session.get(SESSION_KEY_ZMODE)
is_bifrost = (mode == MODE_BIFROST)
is_zcli = (mode == MODE_ZCLI)
```

> **SSOT:** `MODE_BIFROST` / `MODE_ZCLI` are thin **aliases of
> `zVocabulary.ZMODE_ZBIFROST` / `ZMODE_ZCLI`** — the run-mode literals are
> single-sourced in `core/zVocabulary.py`, not redefined here. `MODE_WALKER`
> (`"Walker"`) is dispatch-internal (a traversal mode, not a session `zMode`).
> Likewise `KEY_ZVAFILE` / `KEY_ZBLOCK` alias `SESSION_KEY_ZVAFILE` /
> `SESSION_KEY_ZBLOCK`.

### Examples

```python
# Mode-aware return
def process_bounce(result, mode):
    if mode == MODE_BIFROST:
        return result  # Return actual result
    elif mode == MODE_ZCLI:
        return NAV_ZBACK  # Return navigation signal
    return result
```

---

## Navigation

**Navigation constants.**

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    NAV_ZBACK,      # "zBack"
)

# Usage
if result == NAV_ZBACK:
    # Return to previous menu
    pass
```

### Examples

```python
# Bounce modifier return
def execute_bounce(action):
    result = action()
    if is_terminal_mode:
        return NAV_ZBACK
    return result
```

---

## Plugins

**Plugin system constants.**

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    PLUGIN_PREFIX,  # "&"
)

# Usage
if func_name.startswith(PLUGIN_PREFIX):
    # Route to plugin system
    pass
```

### Examples

```python
# Detect plugin invocation
def is_plugin(func_name):
    return isinstance(func_name, str) and func_name.startswith(PLUGIN_PREFIX)

# Extract plugin path
def extract_plugin_path(func_name):
    if is_plugin(func_name):
        return func_name[1:]  # Remove & prefix
    return func_name
```

---

## Error Messages

**Public error messages.**

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    ERR_NO_ZOS_INSTANCE,    # "zDispatch requires a zOS instance"
    ERR_NO_ZOS_OR_WALKER,   # "handle_zDispatch requires either zos or walker parameter"
)

# Usage
if not zos and not walker:
    raise ValueError(ERR_NO_ZOS_OR_WALKER)
```

---

## Internal Constants

**Internal constants (not exported) used within zDispatch modules:**

### Display Labels (INTERNAL)
```python
# Used by zDisplay for internal messaging
_LABEL_LAUNCHER
_LABEL_HANDLE_ZFUNC
_LABEL_HANDLE_ZDATA_DICT
_LABEL_PROCESS_MODIFIERS
_LABEL_ZBOUNCE
_LABEL_ZREQUIRED
# ... 17 total labels
```

### Display Events (INTERNAL)
```python
# Legacy zDisplay event types
_EVENT_TEXT
_EVENT_SYSMSG
_EVENT_HEADER
_EVENT_SUCCESS
_EVENT_ERROR
# ... 9 total event types
```

### Default Values (INTERNAL)
```python
# Implementation defaults
_DEFAULT_ACTION_READ
_DEFAULT_ZBLOCK
_DEFAULT_CONTENT
_DEFAULT_INDENT
# ... 10 total defaults
```

### Styles & Indentation (INTERNAL)
```python
# Display styling
_STYLE_FULL
_STYLE_SINGLE
_STYLE_WAVY
_INDENT_ROOT
_INDENT_HANDLE
# ... 5 total style constants
```

### Log Messages (INTERNAL)
```python
# Framework logging
_LOG_PREFIX
_LOG_MSG_READY
_LOG_MSG_HORIZONTAL
_LOG_MSG_HANDLE_KEY
# ... 32 total log messages
```

---

## Usage Patterns

### Building Commands

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    KEY_ZFUNC, KEY_ACTION, KEY_MODEL, KEY_WHERE
)

# Function command
func_cmd = {
    KEY_ZFUNC: "calculate",
    "args": [10, 5]
}

# Data command
data_cmd = {
    KEY_ACTION: "read",
    KEY_MODEL: "users",
    KEY_WHERE: {"id": 1}
}
```

### Checking Modifiers

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    PREFIX_MODIFIERS, SUFFIX_MODIFIERS
)

def parse_modifiers(zKey):
    prefix = [m for m in PREFIX_MODIFIERS if zKey.startswith(m)]
    suffix = [m for m in SUFFIX_MODIFIERS if zKey.endswith(m)]
    return prefix, suffix
```

### Mode Detection

```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import MODE_BIFROST
from zOS.L1_Foundation.a_zConfig.zConfig_modules import SESSION_KEY_ZMODE

def is_bifrost_mode(zos):
    return zos.session.get(SESSION_KEY_ZMODE) == MODE_BIFROST
```

---

## Best Practices

### Always Use Constants

```python
# ✅ Good: Use constants
command = {
    KEY_ZFUNC: "my_function"
}

# ❌ Bad: Hardcode strings
command = {
    "zFunc": "my_function"  # Typo risk!
}
```

### Import What You Need

```python
# ✅ Good: Import specific constants
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    KEY_ZFUNC,
    KEY_ACTION,
    MOD_CARET
)

# ❌ Bad: Import everything
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import *
```

### Use Type-Safe Keys

```python
# ✅ Good: Constants prevent typos
if KEY_ZFUNC in command:
    pass

# ❌ Bad: String literals can have typos
if "zFunc" in command:  # Works
if "zfunc" in command:  # Fails silently!
```

---

**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**
