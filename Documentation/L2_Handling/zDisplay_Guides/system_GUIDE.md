# zDisplay System Layer

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**

---

## Overview

The **System layer** provides system-level UI components including system announcements, session display, navigation breadcrumbs, menus, and dialogs.

**Location:** `zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/system/`

**Purpose:**
- System announcements (zDeclare)
- Session state display (zSession)
- Configuration display (zConfig)
- Navigation breadcrumbs (zCrumbs)
- Interactive menus (zMenu)
- Modal dialogs (zDialog)

---

## Module Structure

| Module | Purpose |
|--------|---------|
| `display_event_system.py` | System event orchestration |
| `system_event_declare.py` | zDeclare implementation |
| `system_event_session.py` | zSession display |
| `system_event_dialog.py` | zDialog implementation |
| `system_event_navigation.py` | zCrumbs/zMenu navigation |

---

## System Announcements

### zDeclare() - System Status

Professional system announcements with color-coded status.

**Parameters:**
- `label` (str): Announcement text
- `color` (str): Status color (GREEN, YELLOW, RED, BLUE, CYAN, MAGENTA)
- `indent` (int): Indentation level

**Example:**
```python
# Startup sequence
z.display.zDeclare("System Initialization", color="CYAN")
z.display.info("Loading configuration", indent=1)
z.display.info("Connecting to database", indent=1)
z.display.zDeclare("Services Ready", color="GREEN")

# Status updates
z.display.zDeclare("Processing Data", color="BLUE")
z.display.zDeclare("Warning: Low Memory", color="YELLOW")
z.display.zDeclare("Error: Connection Lost", color="RED")
```

**Color Meanings:**
- **GREEN** - Success, ready, operational
- **YELLOW** - Warning, caution
- **RED** - Error, failure, critical
- **BLUE** - Information, processing
- **CYAN** - Initialization, starting
- **MAGENTA** - Special status

**Implementation:** `system_event_declare.py`

---

## Session Display

### zSession() - Display Session State

Display current session state including ID, mode, logger, and configuration.

**Parameters:**
- `session` (dict): Session dictionary from `z.session`

**Example:**
```python
z.display.zSession(z.session)
```

**Output:**
```
════════════════════ Session State ════════════════════
Session ID: abc123def456
Mode: zCLI
Logger: INFO
Deployment: Production
═══════════════════════════════════════════════════════
```

**Implementation:** `system_event_session.py`

---

### zConfig() - Display Configuration

Display machine and environment configuration.

**Parameters:**
- `config_data` (dict): Configuration dictionary

**Example:**
```python
config_data = {
    "machine": {
        "os": z.config.get_machine("os"),
        "hostname": z.config.get_machine("hostname"),
        "cpu_cores": z.config.get_machine("cpu_cores"),
        "memory_gb": z.config.get_machine("memory_gb")
    },
    "environment": {
        "deployment": "Production",
        "mode": "zCLI",
        "logger": "INFO"
    }
}

z.display.zConfig(config_data)
```

**Output:**
```
════════════════════ Configuration ════════════════════
Machine:
  OS: Darwin
  Hostname: macbook-pro
  CPU Cores: 8
  Memory: 16 GB

Environment:
  Deployment: Production
  Mode: zCLI
  Logger: INFO
═══════════════════════════════════════════════════════
```

**Implementation:** `system_event_session.py`

---

## Navigation

### zCrumbs() - Breadcrumb Navigation

Display navigation breadcrumbs showing current location in hierarchy.

**Parameters:**
- `path` (list): List of breadcrumb items
- `separator` (str): Separator between items (default: " → ")

**Example:**
```python
z.display.zCrumbs(["Home", "Settings", "Profile"])
# Output: Home → Settings → Profile

z.display.zCrumbs(["Projects", "ZoloMedia", "zOS", "Documentation"], separator=" / ")
# Output: Projects / ZoloMedia / zOS / Documentation
```

**Implementation:** `system_event_navigation.py`

---

### zMenu() - Interactive Menu

Display interactive menu with keyboard navigation.

**Parameters:**
- `title` (str): Menu title
- `items` (list): List of menu items (strings or dicts)
- `allow_back` (bool): Show "Back" option (default: False)

**Returns:** Selected item or None (if back/cancelled)

**Example:**
```python
# Simple menu
choice = z.display.zMenu(
    title="Main Menu",
    items=["View Profile", "Settings", "Logout"]
)

if choice == "View Profile":
    show_profile()
elif choice == "Settings":
    show_settings()
elif choice == "Logout":
    logout()

# Menu with back option
choice = z.display.zMenu(
    title="Settings",
    items=["Account", "Privacy", "Notifications"],
    allow_back=True
)

if choice is None:
    # User selected "Back"
    return_to_main_menu()
```

**Implementation:** `system_event_navigation.py`

---

## Dialogs

### zDialog() - Modal Dialog

Display modal dialog with title, message, and buttons.

**Parameters:**
- `title` (str): Dialog title
- `message` (str): Dialog message
- `buttons` (list): List of button labels
- `default` (str): Default button (optional)

**Returns:** Selected button label

**Example:**
```python
# Confirmation dialog
result = z.display.zDialog(
    title="Confirm Delete",
    message="Are you sure you want to delete this item?",
    buttons=["Delete", "Cancel"],
    default="Cancel"
)

if result == "Delete":
    delete_item()

# Multi-option dialog
action = z.display.zDialog(
    title="Save Changes",
    message="You have unsaved changes. What would you like to do?",
    buttons=["Save", "Discard", "Cancel"],
    default="Save"
)

if action == "Save":
    save_changes()
elif action == "Discard":
    discard_changes()
# Cancel: do nothing
```

**Implementation:** `system_event_dialog.py`

---

## Design Principles

**1. System-Level UI**
- Professional status reporting
- Session and configuration display
- Navigation and menu systems
- Modal interactions

**2. Consistent Styling**
- Box-drawn borders (═══)
- Color-coded status
- Hierarchical display
- Clear visual separation

**3. Interactive Components**
- Keyboard navigation
- Default selections
- Back/cancel options
- Modal behavior

**4. Integration with zConfig**
- Display session state
- Show configuration values
- System status reporting
- Startup sequences

---

## Usage Examples

**System Announcements:**
```python
# Application startup
z.display.zDeclare("Application Starting", color="CYAN")
z.display.info("Loading modules", indent=1)
z.display.info("Initializing services", indent=1)
z.display.zDeclare("Application Ready", color="GREEN")

# Processing workflow
z.display.zDeclare("Data Processing Started", color="BLUE")
z.display.info("Reading input files", indent=1)
z.display.info("Validating data", indent=1)
z.display.info("Transforming records", indent=1)
z.display.zDeclare("Processing Complete", color="GREEN")

# Error handling
z.display.zDeclare("Warning: Resource Limit", color="YELLOW")
z.display.warning("Memory usage: 85%", indent=1)
z.display.zDeclare("Error: Connection Failed", color="RED")
z.display.error("Unable to reach database", indent=1)
```

**Session and Configuration:**
```python
# Display current session
z.display.header("Current Session", color="CYAN")
z.display.zSession(z.session)

# Display machine configuration
machine_config = {
    "machine": {
        "os": z.config.get_machine("os"),
        "hostname": z.config.get_machine("hostname"),
        "cpu_cores": z.config.get_machine("cpu_cores"),
        "memory_gb": z.config.get_machine("memory_gb"),
        "python_version": z.config.get_machine("python_version")
    }
}
z.display.zConfig(machine_config)

# Display environment configuration
env_config = {
    "environment": {
        "deployment": z.config.get_environment("deployment"),
        "datacenter": z.config.get_environment("datacenter"),
        "cluster": z.config.get_environment("cluster")
    }
}
z.display.zConfig(env_config)
```

**Navigation:**
```python
# Breadcrumbs for file browser
z.display.zCrumbs(["Home", "Documents", "Projects", "ZoloMedia"])

# Breadcrumbs for settings
z.display.zCrumbs(["Settings", "Account", "Security", "Two-Factor Auth"])

# Custom separator
z.display.zCrumbs(["Users", "Alice", "Profile"], separator=" > ")
```

**Menus:**
```python
# Main menu
while True:
    choice = z.display.zMenu(
        title="Main Menu",
        items=["View Data", "Settings", "Help", "Exit"]
    )
    
    if choice == "View Data":
        view_data()
    elif choice == "Settings":
        settings_menu()
    elif choice == "Help":
        show_help()
    elif choice == "Exit":
        break

# Settings submenu
def settings_menu():
    choice = z.display.zMenu(
        title="Settings",
        items=["Account", "Privacy", "Notifications", "Advanced"],
        allow_back=True
    )
    
    if choice is None:
        return  # Back to main menu
    elif choice == "Account":
        account_settings()
    elif choice == "Privacy":
        privacy_settings()
    # ... etc
```

**Dialogs:**
```python
# Save confirmation
if has_unsaved_changes():
    result = z.display.zDialog(
        title="Unsaved Changes",
        message="You have unsaved changes. Save before exiting?",
        buttons=["Save", "Don't Save", "Cancel"],
        default="Save"
    )
    
    if result == "Save":
        save_changes()
        exit_app()
    elif result == "Don't Save":
        exit_app()
    # Cancel: stay in app

# Delete confirmation
result = z.display.zDialog(
    title="Confirm Delete",
    message=f"Delete '{item_name}'? This cannot be undone.",
    buttons=["Delete", "Cancel"],
    default="Cancel"
)

if result == "Delete":
    delete_item(item_name)
    z.display.success(f"Deleted: {item_name}")

# Error dialog
z.display.zDialog(
    title="Error",
    message="Failed to connect to database. Check your connection and try again.",
    buttons=["OK"]
)
```

---

## What's Next

The system layer provides system-level UI. Complete your knowledge with:

- **[API Layer →](api_GUIDE.md)** - Convenience methods and backward compatibility
- **[Utils Layer →](utils_GUIDE.md)** - Pure utilities and helpers

---

**[← Back to zDisplay Guide](../zDisplay_GUIDE.md)**
