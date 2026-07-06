# zFunc Built-in Functions Module Guide

> **Module:** `zOS/core/L2_Handling/i_zFunc/zFunc_modules/builtin_functions.py`  
> **Purpose:** Built-in utility functions for zFunc subsystem.

---

## Overview

The `builtin_functions` module provides utility functions that are available across all zOS applications. Currently, it includes date/time formatting functions that respect zConfig machine settings.

---

## Functions

### `zNow(format_type="datetime", custom_format=None, zos=None) -> str`

Get current date/time formatted according to zConfig machine settings.

```python
from zOS import zOS

z = zOS()

# Default: datetime format
now = z.zfunc.zNow()
# Returns: "19122025 14:30:00" (ddmmyyyy HH:MM:SS)

# Date only
date = z.zfunc.zNow('date')
# Returns: "19122025" (ddmmyyyy)

# Time only
time = z.zfunc.zNow('time')
# Returns: "14:30:00" (HH:MM:SS)

# Custom format
custom = z.zfunc.zNow(custom_format='yyyy-mm-dd')
# Returns: "2025-12-19"
```

**Parameters:**
- `format_type` (str): Format type - "date", "time", or "datetime" (default: "datetime")
- `custom_format` (str): Override config format with custom pattern (optional)
- `zos` (Any): zOS instance for config access (auto-injected if None)

**Returns:** Formatted date/time string

**Raises:** `ValueError` if format_type is invalid (not "date", "time", or "datetime")

---

## Format Patterns

### Default Formats (from zConfig)

Format strings are read from zConfig machine settings:

```python
# Machine config (zConfig.machine.zolo)
zMachine:
  date_format: "ddmmyyyy"       # Default date format
  time_format: "HH:MM:SS"       # Default time format
  datetime_format: "ddmmyyyy HH:MM:SS"  # Default datetime format
```

**Access via zConfig:**
```python
z.config.get_machine("date_format")      # "ddmmyyyy"
z.config.get_machine("time_format")      # "HH:MM:SS"
z.config.get_machine("datetime_format")  # "ddmmyyyy HH:MM:SS"
```

---

### Pattern Symbols

| Symbol | Meaning | Example |
|--------|---------|---------|
| `yyyy` | 4-digit year | 2025 |
| `yy` | 2-digit year | 25 |
| `mm` | 2-digit month | 12 |
| `dd` | 2-digit day | 19 |
| `HH` | 2-digit hour (24h) | 14 |
| `MM` | 2-digit minute | 30 |
| `SS` | 2-digit second | 00 |

**Pattern examples:**
- `"ddmmyyyy"` → `"19122025"`
- `"yyyy-mm-dd"` → `"2025-12-19"`
- `"dd/mm/yyyy"` → `"19/12/2025"`
- `"HH:MM:SS"` → `"14:30:00"`
- `"HH:MM"` → `"14:30"`

---

## Practical Examples

### Example 1: Basic Usage

```python
from zOS import zOS

z = zOS()

# Get current datetime
now = z.zfunc.zNow()
print(f"Current time: {now}")
# Output: Current time: 19122025 14:30:00

# Get just date
today = z.zfunc.zNow('date')
print(f"Today: {today}")
# Output: Today: 19122025

# Get just time
time = z.zfunc.zNow('time')
print(f"Time: {time}")
# Output: Time: 14:30:00
```

---

### Example 2: Custom Formats

```python
# ISO 8601 format
iso_date = z.zfunc.zNow(custom_format='yyyy-mm-dd')
# Returns: "2025-12-19"

# US date format
us_date = z.zfunc.zNow(custom_format='mm/dd/yyyy')
# Returns: "12/19/2025"

# European format
eu_date = z.zfunc.zNow(custom_format='dd.mm.yyyy')
# Returns: "19.12.2025"

# 12-hour time format (requires manual AM/PM handling)
hour = datetime.datetime.now().hour
period = "AM" if hour < 12 else "PM"
time_12h = z.zfunc.zNow(custom_format='HH:MM')  # Still 24h
# Need custom logic for 12h conversion
```

---

### Example 3: Logging Timestamps

```python
# Add timestamp to log messages
def log_message(message):
    timestamp = z.zfunc.zNow()
    z.logger.info(f"[{timestamp}] {message}")

log_message("Application started")
# Logs: [19122025 14:30:00] Application started

log_message("Processing request")
# Logs: [19122025 14:30:05] Processing request
```

---

### Example 4: File Naming with Timestamps

```python
import os

# Create timestamped filename
date = z.zfunc.zNow('date')
time = z.zfunc.zNow('time').replace(':', '')  # Remove colons for filename

filename = f"report_{date}_{time}.csv"
# Result: report_19122025_143000.csv

# Create file
with open(filename, 'w') as f:
    f.write("data")
```

---

### Example 5: Session Duration Tracking

```python
import datetime

# Track session start
session_start = datetime.datetime.now()
session_start_str = z.zfunc.zNow()

# ... application logic ...

# Calculate duration
duration = datetime.datetime.now() - session_start
session_end_str = z.zfunc.zNow()

print(f"Session: {session_start_str} to {session_end_str}")
print(f"Duration: {duration.total_seconds():.2f} seconds")
```

---

### Example 6: Direct Function Call (without zFunc facade)

```python
from zFunc_modules.builtin_functions import zNow

# Call directly (requires zos instance)
now = zNow(format_type="datetime", zos=z)
# Returns: "19122025 14:30:00"

# Date only
date = zNow(format_type="date", zos=z)
# Returns: "19122025"

# Custom format
custom = zNow(custom_format="yyyy-mm-dd", zos=z)
# Returns: "2025-12-19"
```

---

### Example 7: Error Handling

```python
# Invalid format type
try:
    result = z.zfunc.zNow('invalid')
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Invalid format_type: invalid. Must be 'date', 'time', or 'datetime'.

# Valid format types only
valid_types = ['date', 'time', 'datetime']
for format_type in valid_types:
    result = z.zfunc.zNow(format_type)
    print(f"{format_type}: {result}")
```

---

### Example 8: Custom Format Patterns

```python
# Different separator styles
dash = z.zfunc.zNow(custom_format='yyyy-mm-dd')  # "2025-12-19"
slash = z.zfunc.zNow(custom_format='dd/mm/yyyy')  # "19/12/2025"
dot = z.zfunc.zNow(custom_format='dd.mm.yyyy')    # "19.12.2025"
compact = z.zfunc.zNow(custom_format='yyyymmdd')  # "20251219"

# Time variations
time_24h = z.zfunc.zNow(custom_format='HH:MM:SS')  # "14:30:00"
time_hm = z.zfunc.zNow(custom_format='HH:MM')      # "14:30"

# Combined formats
timestamp = z.zfunc.zNow(custom_format='yyyy-mm-dd HH:MM:SS')
# "2025-12-19 14:30:00"
```

---

## Integration with zConfig

`zNow()` reads format settings from zConfig machine configuration:

```python
# Access machine config
machine = z.config.get_machine()

date_format = machine.get("date_format")         # "ddmmyyyy"
time_format = machine.get("time_format")         # "HH:MM:SS"
datetime_format = machine.get("datetime_format") # "ddmmyyyy HH:MM:SS"

# zNow uses these formats
now = z.zfunc.zNow()  # Uses datetime_format from config
```

**Override machine config:**
```python
# Edit zConfig.machine.zolo
# zMachine:
#   date_format: "yyyy-mm-dd"
#   time_format: "HH:MM:SS"
#   datetime_format: "yyyy-mm-dd HH:MM:SS"

# Reload zOS to pick up changes
z = zOS()

# Now uses new formats
now = z.zfunc.zNow()  # "2025-12-19 14:30:00"
```

---

## Use Cases

### 1. Logging

```python
def log_with_timestamp(level, message):
    timestamp = z.zfunc.zNow()
    z.logger.log(level, f"[{timestamp}] {message}")
```

---

### 2. File Naming

```python
def create_backup_filename(base_name):
    date = z.zfunc.zNow('date')
    return f"{base_name}_{date}.bak"
```

---

### 3. Report Generation

```python
def generate_report():
    timestamp = z.zfunc.zNow()
    report = {
        "generated_at": timestamp,
        "data": [...]
    }
    return report
```

---

### 4. Session Tracking

```python
class Session:
    def __init__(self, z):
        self.start_time = z.zfunc.zNow()
        
    def end(self, z):
        self.end_time = z.zfunc.zNow()
        return f"Session duration: {self.start_time} to {self.end_time}"
```

---

### 5. Data Timestamps

```python
def insert_record(data):
    record = {
        "data": data,
        "created_at": z.zfunc.zNow(),
        "updated_at": z.zfunc.zNow()
    }
    return record
```

---

## Implementation Details

### Pattern Parsing

`zNow()` uses Python's `datetime.strftime()` internally, but with custom pattern syntax:

```python
# Custom patterns → strftime patterns
pattern_map = {
    "yyyy": "%Y",  # 4-digit year
    "yy": "%y",    # 2-digit year
    "mm": "%m",    # Month
    "dd": "%d",    # Day
    "HH": "%H",    # Hour (24h)
    "MM": "%M",    # Minute
    "SS": "%S"     # Second
}

# Example conversion:
# "ddmmyyyy" → "%d%m%Y"
# "yyyy-mm-dd" → "%Y-%m-%d"
# "HH:MM:SS" → "%H:%M:%S"
```

---

## Best Practices

1. **Format Consistency:**
   - Use machine config defaults for consistency
   - Override only when needed
   - Document custom format requirements

2. **File Naming:**
   - Use compact formats without colons/slashes
   - Example: `"yyyymmdd_HHMMSS"` → `"20251219_143000"`
   - Avoid special characters in filenames

3. **Logging:**
   - Use datetime format for comprehensive timestamps
   - Consider timezone awareness for distributed systems

4. **Error Handling:**
   - Validate format_type parameter
   - Handle invalid custom format patterns gracefully

5. **Performance:**
   - Cache results if called frequently
   - Use date/time only if full datetime not needed

---

## Future Enhancements

Planned features for future versions:

- **Timezone support**: `z.zfunc.zNow(timezone="UTC")`
- **Relative times**: `z.zfunc.zNow(offset="-1d")` for yesterday
- **Parse dates**: `z.zfunc.zParse("19122025")` to datetime object
- **Format dates**: `z.zfunc.zFormat(date_obj, "yyyy-mm-dd")`
- **More built-ins**: `zRandom()`, `zUUID()`, `zHash()`, etc.

---

## Version History

- **v1.6.0**: Initial implementation
  - Added zNow() with format_type parameter
  - Support for custom format patterns
  - Integration with zConfig machine settings
  - Type validation and error handling
