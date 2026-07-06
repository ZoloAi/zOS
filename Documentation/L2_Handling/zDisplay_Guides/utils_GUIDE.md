# zDisplay Utils Layer

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**

---

## Overview

The **Utils layer** provides pure stateless utilities with no I/O or display dependencies. These are helper functions for formatting, validation, and data manipulation used throughout zDisplay.

**Location:** `zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/utils/`

**Purpose:**
- Pure stateless utilities
- Value formatting and conversion
- System message filtering
- Nested data access (WIP)
- No I/O, no display reference

---

## Module Structure

| Module | Purpose |
|--------|---------|
| `display_utilities.py` | General display utilities |
| `value_formatter.py` | Value formatting helpers |
| `system_message_filter.py` | System message filtering |
| `nested_accessor_wip.py` | Nested data access (WIP) |

---

## Value Formatting

From `value_formatter.py`:

### format_value()

Format values for display with type-aware rendering.

**Parameters:**
- `value` (any): Value to format
- `max_length` (int): Maximum string length (default: None)
- `precision` (int): Float precision (default: 2)

**Returns:** Formatted string

**Example:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.value_formatter import format_value

# Strings
format_value("Hello World")  # "Hello World"
format_value("Very long string...", max_length=10)  # "Very lon..."

# Numbers
format_value(42)  # "42"
format_value(3.14159, precision=2)  # "3.14"
format_value(1000000)  # "1,000,000"

# Booleans
format_value(True)  # "True"
format_value(False)  # "False"

# None
format_value(None)  # "None"

# Lists
format_value([1, 2, 3])  # "[1, 2, 3]"
format_value(["a", "b", "c"], max_length=10)  # "[a, b, ..."

# Dicts
format_value({"key": "value"})  # "{'key': 'value'}"
```

---

### truncate_string()

Truncate string to maximum length with ellipsis.

**Parameters:**
- `text` (str): Text to truncate
- `max_length` (int): Maximum length
- `ellipsis` (str): Ellipsis string (default: "...")

**Returns:** Truncated string

**Example:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.value_formatter import truncate_string

truncate_string("Hello World", 8)  # "Hello..."
truncate_string("Short", 10)  # "Short"
truncate_string("Very long text", 10, ellipsis="…")  # "Very long…"
```

---

### format_number()

Format number with thousands separators and precision.

**Parameters:**
- `value` (int/float): Number to format
- `precision` (int): Decimal places (default: 2)
- `thousands_sep` (str): Thousands separator (default: ",")

**Returns:** Formatted string

**Example:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.value_formatter import format_number

format_number(1000)  # "1,000"
format_number(1234567)  # "1,234,567"
format_number(3.14159, precision=2)  # "3.14"
format_number(1000000, thousands_sep=" ")  # "1 000 000"
```

---

## System Message Filtering

From `system_message_filter.py`:

### is_system_message()

Check if message is a system message (should be filtered in certain modes).

**Parameters:**
- `message` (str): Message to check

**Returns:** Boolean

**Example:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.system_message_filter import is_system_message

is_system_message("[zConfig Ready]")  # True
is_system_message("[zComm Ready]")  # True
is_system_message("User message")  # False
```

---

### filter_system_messages()

Filter out system messages from list of messages.

**Parameters:**
- `messages` (list): List of messages

**Returns:** Filtered list

**Example:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.system_message_filter import filter_system_messages

messages = [
    "[zConfig Ready]",
    "User message 1",
    "[zComm Ready]",
    "User message 2"
]

filtered = filter_system_messages(messages)
# ["User message 1", "User message 2"]
```

---

## Display Utilities

From `display_utilities.py`:

### calculate_column_widths()

Calculate optimal column widths for table display.

**Parameters:**
- `columns` (list): Column names
- `rows` (list): List of row dicts
- `max_width` (int): Maximum total width

**Returns:** Dict of column widths

**Example:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.display_utilities import calculate_column_widths

columns = ["id", "name", "email"]
rows = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"}
]

widths = calculate_column_widths(columns, rows, max_width=80)
# {"id": 5, "name": 10, "email": 25}
```

---

### wrap_text_to_width()

Wrap text to specified width preserving word boundaries.

**Parameters:**
- `text` (str): Text to wrap
- `width` (int): Maximum width
- `indent` (int): Indentation for wrapped lines

**Returns:** List of wrapped lines

**Example:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.display_utilities import wrap_text_to_width

text = "This is a very long line that needs to be wrapped to fit within the specified width"
lines = wrap_text_to_width(text, width=40, indent=0)
# [
#   "This is a very long line that needs to",
#   "be wrapped to fit within the specified",
#   "width"
# ]
```

---

### align_text()

Align text within specified width.

**Parameters:**
- `text` (str): Text to align
- `width` (int): Target width
- `align` (str): Alignment (left, center, right)

**Returns:** Aligned string

**Example:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.display_utilities import align_text

align_text("Hello", 20, "left")    # "Hello               "
align_text("Hello", 20, "center")  # "       Hello        "
align_text("Hello", 20, "right")   # "               Hello"
```

---

## Nested Data Access (WIP)

From `nested_accessor_wip.py`:

> **Note:** This module is work-in-progress and may change in future releases.

### get_nested_value()

Access nested dictionary values using dot notation.

**Parameters:**
- `data` (dict): Data dictionary
- `path` (str): Dot-notation path (e.g., "user.profile.name")
- `default` (any): Default value if path not found

**Returns:** Value at path or default

**Example:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.nested_accessor_wip import get_nested_value

data = {
    "user": {
        "profile": {
            "name": "Alice",
            "age": 30
        }
    }
}

get_nested_value(data, "user.profile.name")  # "Alice"
get_nested_value(data, "user.profile.age")   # 30
get_nested_value(data, "user.email", default="N/A")  # "N/A"
```

---

## Design Principles

**1. Pure Functions**
- No side effects
- No I/O operations
- No display dependencies
- Testable in isolation

**2. Stateless**
- No internal state
- Same input = same output
- Thread-safe

**3. Reusable**
- Used across all display layers
- Generic implementations
- Well-documented

**4. Type-Aware**
- Handle different data types
- Graceful degradation
- Sensible defaults

---

## Usage Examples

**Value Formatting:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.value_formatter import (
    format_value,
    truncate_string,
    format_number
)

# Format various types
print(format_value(42))  # "42"
print(format_value(3.14159, precision=2))  # "3.14"
print(format_value(True))  # "True"
print(format_value([1, 2, 3]))  # "[1, 2, 3]"

# Truncate strings
long_text = "This is a very long string that needs truncation"
print(truncate_string(long_text, 20))  # "This is a very lo..."

# Format numbers
print(format_number(1234567))  # "1,234,567"
print(format_number(3.14159, precision=3))  # "3.142"
```

**System Message Filtering:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.system_message_filter import (
    is_system_message,
    filter_system_messages
)

# Check messages
print(is_system_message("[zConfig Ready]"))  # True
print(is_system_message("User message"))  # False

# Filter list
messages = ["[zConfig Ready]", "Hello", "[zComm Ready]", "World"]
user_messages = filter_system_messages(messages)
print(user_messages)  # ["Hello", "World"]
```

**Display Utilities:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.display_utilities import (
    calculate_column_widths,
    wrap_text_to_width,
    align_text
)

# Calculate table column widths
columns = ["id", "name", "email"]
rows = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"}
]
widths = calculate_column_widths(columns, rows, max_width=80)

# Wrap text
text = "Long text that needs wrapping"
lines = wrap_text_to_width(text, width=15)

# Align text
print(align_text("Title", 30, "center"))
```

**Nested Data Access:**
```python
from zOS.core.L2_Handling.c_zDisplay.zDisplay_modules.utils.nested_accessor_wip import get_nested_value

config = {
    "database": {
        "host": "localhost",
        "port": 5432,
        "credentials": {
            "user": "admin",
            "password": "secret"
        }
    }
}

# Access nested values
host = get_nested_value(config, "database.host")  # "localhost"
port = get_nested_value(config, "database.port")  # 5432
user = get_nested_value(config, "database.credentials.user")  # "admin"

# With default
ssl = get_nested_value(config, "database.ssl", default=False)  # False
```

---

## What's Next

You've completed the zDisplay module guides! Return to:

- **[zDisplay Guide ←](../zDisplay_GUIDE.md)** - Main facade overview

---

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**
