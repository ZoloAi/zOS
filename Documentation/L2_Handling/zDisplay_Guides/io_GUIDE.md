# zDisplay I/O Layer

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**

---

## Overview

The **I/O layer** is the lowest level of zDisplay, handling all terminal and WebSocket I/O operations. This layer enforces exclusive mode behavior - terminal syscalls OR WebSocket delegation, never both.

**Location:** `zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/io/`

**Purpose:** 
- Terminal I/O syscall wrappers (print, input, getpass)
- WebSocket event emission for zBifrost mode
- Mode-switching logic (zCLI vs zBifrost)
- Primitive operations that all other layers build upon

---

## Module Structure

| Module | Purpose |
|--------|---------|
| `display_primitives.py` | Primitive I/O coordination and mode detection |
| `display_primitives_outputs.py` | Output primitives (raw, line, block) |
| `display_primitives_inputs.py` | Input primitives (read_string, read_password) |
| `outputs/output_raw.py` | Raw output implementation (no newline) |
| `outputs/output_line.py` | Line output implementation (with newline) |
| `outputs/output_block.py` | Block output implementation (multi-line) |
| `inputs/input_string.py` | String input implementation |
| `inputs/input_password.py` | Password input implementation (masked) |

---

## Exclusive Mode Operation

The I/O layer enforces **exclusive mode behavior**:

**zCLI Mode (Terminal):**
- Direct console I/O using `print()`, `input()`, `getpass.getpass()`
- ANSI color codes for styling
- Blocking input methods
- Immediate visual feedback

**zBifrost Mode (GUI):**
- WebSocket event broadcasting via `z.comm.websocket_events`
- JSON event objects
- Non-blocking (async) operations
- Browser-rendered UI

Mode is resolved **once at initialization** from `session[SESSION_KEY_ZMODE]`. The `_is_bifrost` flag is computed and cached - no per-event mode switching occurs.

---

## Output Primitives

### raw() - No Newline

Write text without automatic newline. You control when lines break.

**Terminal Mode:**
```python
z.display.raw("Loading")
z.display.raw("...")
z.display.raw("\n")  # Manual newline
```

**WebSocket Mode:**
```python
# Emits: {"event": "write_raw", "content": "Loading"}
# Emits: {"event": "write_raw", "content": "..."}
# Emits: {"event": "write_raw", "content": "\n"}
```

**Implementation:** `outputs/output_raw.py`

---

### line() - Automatic Newline

Write text with automatic newline. Each call starts a new line.

**Terminal Mode:**
```python
z.display.line("Processing complete")
# Prints: "Processing complete\n"
```

**WebSocket Mode:**
```python
# Emits: {"event": "write_line", "content": "Processing complete"}
```

**Implementation:** `outputs/output_line.py`

---

### block() - Multi-Line Output

Write multi-line text block with preserved formatting.

**Terminal Mode:**
```python
block = """Line 1
Line 2
Line 3"""
z.display.block(block)
# Prints: "Line 1\nLine 2\nLine 3\n"
```

**WebSocket Mode:**
```python
# Emits: {"event": "write_block", "content": "Line 1\nLine 2\nLine 3"}
```

**Implementation:** `outputs/output_block.py`

---

## Input Primitives

### read_string() - Text Input

Collect text input from user with prompt.

**Terminal Mode:**
```python
name = z.display.read_string("What's your name? ")
# Uses input() - blocking
# Returns: user's text input
```

**WebSocket Mode:**
```python
# Emits: {"event": "read_string", "prompt": "What's your name? ", "request_id": "..."}
# Waits for client response via WebSocket
# Returns: user's text input (async)
```

**Implementation:** `inputs/input_string.py`

---

### read_password() - Masked Input

Collect password input with masked typing.

**Terminal Mode:**
```python
password = z.display.read_password("Password: ")
# Uses getpass.getpass() - blocking, hidden input
# Returns: password string
```

**WebSocket Mode:**
```python
# Emits: {"event": "read_password", "prompt": "Password: ", "request_id": "..."}
# Waits for client response via WebSocket
# Returns: password string (async)
```

**Implementation:** `inputs/input_password.py`

---

## Mode Detection

Mode is detected once at initialization:

```python
# In display_primitives.py
def __init__(self, zos_instance):
    self.session = zos_instance.session
    self._is_bifrost = self.session.get(SESSION_KEY_ZMODE) == "zBifrost"
    
    if self._is_bifrost:
        self.comm = zos_instance.comm
    else:
        self.comm = None
```

**Mode Resolution:**
1. Read `session[SESSION_KEY_ZMODE]` once
2. Set `_is_bifrost` flag (cached)
3. Initialize appropriate I/O backend
4. All subsequent operations use cached mode

**No Per-Event Mode Switching:**
- Mode is exclusive (zCLI OR zBifrost)
- Determined at initialization
- Never changes during execution
- Enforced at I/O layer

---

## WebSocket Integration

In zBifrost mode, the I/O layer uses `z.comm.websocket_events` for communication:

**Event Emission:**
```python
# In output_raw.py (zBifrost mode)
self.comm.websocket_events.send_display_event("write_raw", {
    "content": text
})
```

**Input Coordination:**
```python
# In input_string.py (zBifrost mode)
future = self.comm.websocket_input.create_request("string", prompt)
if future:
    result = await future  # Wait for client response
    return result
```

**Event Types:**
- `write_raw` - Raw output
- `write_line` - Line output
- `write_block` - Block output
- `read_string` - String input request
- `read_password` - Password input request

---

## Terminal Rendering

In zCLI mode, the I/O layer uses standard Python syscalls:

**Output:**
```python
# In output_line.py (zCLI mode)
print(content, end="\n", flush=True)
```

**Input:**
```python
# In input_string.py (zCLI mode)
result = input(prompt)
return result

# In input_password.py (zCLI mode)
import getpass
result = getpass.getpass(prompt)
return result
```

**ANSI Color Codes:**
Colors are applied at higher layers (basic/outputs/semantic_colors.py) before reaching the I/O layer.

---

## Design Principles

**1. Exclusive Mode Behavior**
- Terminal syscalls OR WebSocket delegation
- Never both simultaneously
- Mode resolved once at initialization

**2. Primitive Operations**
- Minimal, atomic operations
- All higher layers build on these
- No business logic at I/O layer

**3. Transparent Mode Switching**
- Higher layers don't know about mode
- Same API for both modes
- I/O layer handles implementation

**4. Separation of Concerns**
- I/O layer: Terminal/WebSocket operations
- Basic layer: Event logic and formatting
- Compounds layer: Complex widgets
- Advanced layer: Specialized components

---

## Usage Examples

**Direct I/O Layer Access (Advanced):**
```python
# Access I/O primitives directly
z.display.zPrimitives.write_raw("text")
z.display.zPrimitives.write_line("text")
z.display.zPrimitives.write_block("text")

text = z.display.zPrimitives.read_string("Prompt: ")
password = z.display.zPrimitives.read_password("Password: ")
```

**Mode Detection:**
```python
# Check current mode
is_bifrost = z.display.zPrimitives._is_bifrost

if is_bifrost:
    print("Running in WebSocket/Browser mode")
else:
    print("Running in Terminal mode")
```

**Typical Usage (Convenience API):**
```python
# Use convenience methods (recommended)
z.display.raw("text")
z.display.line("text")
z.display.block("text")

text = z.display.read_string("Prompt: ")
password = z.display.read_password("Password: ")
```

---

## What's Next

The I/O layer provides the foundation. Build on it with:

- **[Basic Layer →](basic_GUIDE.md)** - Core event logic and formatting
- **[Compounds Layer →](compounds_GUIDE.md)** - Complex interactive widgets
- **[Advanced Layer →](advanced_GUIDE.md)** - Specialized components

---

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**
