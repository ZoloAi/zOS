**[← Back to f_zAuth Guide](zAuth_GUIDE.md) | [Home](../../README.md) | [Next: h_zNavigation Guide →](zNavigation_GUIDE.md)**

---

# g_zDispatch

**g_zDispatch** is the **fourth Layer 2 subsystem** in **zOS** (Layer 2: Handling) - providing command dispatch and routing.
> Located at: `zOS/core/L2_Handling/g_zDispatch/`
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

It routes commands to appropriate subsystems with flexible modifier support, enabling powerful declarative patterns for UI navigation, data operations, and workflow orchestration.

You get:

- **Zero boilerplate**  
- **Unified command interface**
- **Modifier support** (^, ~, *, !)  
- **Mode-aware routing** (zCLI vs. zBifrost)
- **Automatic CRUD detection**
- **Plugin integration** (&prefix)
- **Shorthand expansion**

## Architecture Overview

**g_zDispatch** is composed of specialized modules, each handling a specific aspect of command dispatch:

| Module | Purpose | Guide |
|--------|---------|-------|
| **dispatch_launcher** | Command routing (zFunc, zWizard, zData, etc.) | [launcher_GUIDE.md](zDispatch_Guides/launcher_GUIDE.md) |
| **dispatch_modifiers** | Modifier detection and processing (^ ~ * !) | [modifiers_GUIDE.md](zDispatch_Guides/modifiers_GUIDE.md) |
| **handlers** | Subsystem integration (auth, CRUD, navigation, routing) | [handlers_GUIDE.md](zDispatch_Guides/handlers_GUIDE.md) |
| **commands** | String command parsing (zFunc(), zWizard(), etc.) | [commands_GUIDE.md](zDispatch_Guides/commands_GUIDE.md) |
| **expansion** | Shorthand and organizational expansion | [expansion_GUIDE.md](zDispatch_Guides/expansion_GUIDE.md) |
| **resolvers** | Data and UI resolution | [resolvers_GUIDE.md](zDispatch_Guides/resolvers_GUIDE.md) |
| **modifiers** | Domain-specific modifiers (menu, anchor, crumbs-rewind) | [modifiers_GUIDE.md](zDispatch_Guides/modifiers_GUIDE.md) |
| **transfer** | zTransfer/zExport/zImport — backend-agnostic data movement | [transfer_GUIDE.md](zDispatch_Guides/transfer_GUIDE.md) |
| **dispatch_constants** | Shared constants and configuration | [constants_GUIDE.md](zDispatch_Guides/constants_GUIDE.md) |

This guide provides a **facade overview** of g_zDispatch. For deep dives into specific modules, see the guides in `zDispatch_Guides/`.

---

## Initialization Order

When you call `zOS()`, g_zDispatch initializes as part of the Layer 2 (Handling) subsystems:

**Layer 1 (Foundation):**
1. **zConfig** - Configuration management
2. **zComm** - Communication infrastructure
3. **zLoader** - Dynamic module loading

**Layer 2 (Handling):**
1. **d_zParser** - Command and file parsing
2. **e_zDisplay** - Display and UI rendering
3. **f_zAuth** - Authentication and authorization
4. **g_zDispatch** - Command dispatch and routing:
   - Validate zOS instance (session + logger required)
   - Create ModifierProcessor for prefix (^~) and suffix (*!) modifiers
   - Create CommandLauncher for command routing
   - Display ready message via e_zDisplay
   - Log ready state to framework logger
5. **h_zNavigation** and other L2 subsystems...

This order ensures g_zDispatch has access to configuration (zConfig), communication (zComm), and display (e_zDisplay) before routing commands.

---

## Tutorials

**Learn by doing!** 

The tutorials below are organized in a bottom-up fashion. Every tutorial below has a working demo you can run and modify.

**A Note on Learning zOS:**  
Each tutorial (lvl1, lvl2, lvl3...) progressively introduces more complex features of **this subsystem**. The early tutorials start with familiar imperative patterns (think Django-style conventions) to meet you where you are as a developer.

As you progress through zOS's subsystems, you'll notice a gradual shift from imperative to declarative patterns. This intentional journey helps reshape your mental model from imperative to declarative thinking. Only when you reach **Layer 3 (Orchestration)** will you see subsystems used **fully declaratively** as intended in production. By then, the true magic of declarative coding will reveal itself, and you'll understand why we started this way.

Get the demos:

```bash
# Clone only the Demos folder
git clone --depth 1 --filter=blob:none --sparse https://github.com/ZoloAi/zolo-zcli.git
cd zolo-zcli
git sparse-checkout set Demos
```

> All g_zDispatch demos are in: `Demos/Layer_1/zDispatch_Demo/`

---

# **g_zDispatch - Level 0** (Hello zDispatch)

After mastering e_zDisplay's event-driven architecture, you're ready to explore g_zDispatch - zOS's command routing layer. The same zSpark pattern from previous guides unlocks g_zDispatch's capabilities:

```python
from zOS import zOS

# Familiar zSpark pattern from previous guides
zSpark = {
    "deployment": "Development",  # Show subsystem banners
    "title": "hello-dispatch",    # Session identifier
    "logger": "INFO",             # Console + file logging
    "logger_path": "./logs",      # Where logs go
}

# Watch the initialization order in the output:
# [L1: zConfig → zComm → zLoader] → [L2: d_zParser → e_zDisplay → f_zAuth → g_zDispatch Ready]

z = zOS(zSpark)

# g_zDispatch is now ready to use!
```

**Key Discovery**: g_zDispatch auto-initializes as part of Layer 2 (Handling) when you call `zOS()`. It's a Layer 2 subsystem - providing command routing infrastructure for applications and higher-layer subsystems.

**🎯 Try it yourself:**

Run the demo to see zDispatch in action:

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl0_hello/1_hello_dispatch.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl0_hello/1_hello_dispatch.py)

**What you'll discover:**
- Watch the initialization order: [L1] → [L2: d_zParser → e_zDisplay → f_zAuth → g_zDispatch Ready]
- Layer 2 (Handling) subsystem (built on Layer 1 foundation)
- Same zSpark pattern as previous guides
- Command routing ready with zero configuration

---

# **g_zDispatch - Level 1** (Simple Commands)

### **i. Basic Function Dispatch**

In Level 0, you watched zDispatch initialize. Now let's actually **use** it.  
The simplest zDispatch action? Calling a Python function.

**Two ways to dispatch functions:**

1. **String format**: `"zFunc(function_name)"`
2. **Dict format**: `{"zFunc": "function_name"}`

Let's start with the string format:

```python
from zOS import zOS

def greet(name="World"):
    """Simple greeting function."""
    return f"Hello, {name}!"

zSpark = {
    "deployment": "Production",
    "title": "func-dispatch",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Dispatch function via zDispatch
result = z.dispatch.handle("action", "zFunc(greet)")
print(result)  # Output: Hello, World!

# Pass arguments
result = z.dispatch.handle("action", "zFunc(greet, name='Alice')")
print(result)  # Output: Hello, Alice!
```

> **How it works:** zDispatch parses the string `"zFunc(greet)"`, finds the function in your module's scope, executes it, and returns the result.

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl1_commands/1_func_dispatch.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl1_commands/1_func_dispatch.py)

**What you'll discover:**
- Simple function dispatch via zDispatch
- String and dict command formats
- Automatic function resolution
- Argument passing support

---

### **ii. Dict Command Format**

In the previous demo you used string format (`"zFunc(greet)"`). Now let's use the **dict format** - more powerful and flexible.

```python
from zOS import zOS

def calculate(x, y, operation="add"):
    """Perform calculation."""
    if operation == "add":
        return x + y
    elif operation == "multiply":
        return x * y
    return 0

zSpark = {
    "deployment": "Production",
    "title": "dict-commands",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Dict format with arguments
command = {
    "zFunc": "calculate",
    "args": [10, 5],
    "kwargs": {"operation": "multiply"}
}

result = z.dispatch.handle("calc", command)
print(result)  # Output: 50
```

> **Why dict format?** More structured, easier to build programmatically, supports complex argument passing, and integrates better with data-driven workflows.

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl1_commands/2_dict_commands.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl1_commands/2_dict_commands.py)

**What you'll discover:**
- Dict command format vs. string format
- Structured argument passing
- Programmatic command building
- Better for data-driven workflows

---

### **iii. Multiple Command Types**

zDispatch routes to multiple subsystems, not just functions. Let's explore the complete command vocabulary:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "command-types",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# zFunc: Execute Python function
z.dispatch.handle("func", {"zFunc": "my_function"})

# zData: Database CRUD operations
z.dispatch.handle("read", {"zData": {"action": "read", "model": "users"}})

# zWizard: Multi-step workflows
z.dispatch.handle("wizard", {"zWizard": "onboarding_wizard"})

# zDialog: Interactive forms
z.dispatch.handle("form", {"zDialog": "contact_form"})

# zLogin/zLogout: Authentication
z.dispatch.handle("auth", {"zLogin": True})
```

> **Integration:** zDispatch routes to 7+ subsystems: zFunc, zData, zWizard, zDialog, zParser, zLoader, zNavigation. Each subsystem handles its domain (functions, data, workflows, forms, etc.).

**Command Types:**

| Command | Purpose | Subsystem |
|---------|---------|-----------|
| `zFunc` | Execute Python function | zFunc |
| `zData` | Database CRUD operations | zData |
| `zWizard` | Multi-step workflows | zWizard |
| `zDialog` | Interactive forms | zDialog |
| `zLogin/zLogout` | Authentication | zAuth |
| `zRead` | Data reading operations | zData |
| `zLink` | Navigation links | zNavigation |
| `zDelta` | State updates | zDisplay |
| `zDelegate` | In-place activation rewiring (routeless, AJAX-like) | zDispatch |
| `zTransfer` | Move data between file/model/storage/bytes endpoints | zDispatch (transfer) |
| `zExport` | Export model rows → file/response | zDispatch (transfer) |
| `zImport` | Import file/storage bytes → model | zDispatch (transfer) |

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl1_commands/3_command_types.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl1_commands/3_command_types.py)

**What you'll discover:**
- Complete command vocabulary
- Multi-subsystem routing
- Domain-specific command handlers
- Unified dispatch interface

---

**🎯 Level 1 Complete!**

You've learned the core command dispatch fundamentals:
- ✅ **Basic Function Dispatch** - Call Python functions via zDispatch
- ✅ **Dict Command Format** - Structured command building
- ✅ **Multiple Command Types** - Route to 7+ subsystems

**These are the essentials. Most applications only need these.**

---

# **g_zDispatch - Level 2** (Modifiers)

### **i. Bounce Modifier (^)**

So far you've dispatched commands directly. But what if you want to **execute an action and then return to a menu**?

**The Bounce Modifier (^)**: Execute action → return based on mode

```python
from zOS import zOS

def save_data():
    """Save data to database."""
    print("Data saved!")
    return True

zSpark = {
    "deployment": "Production",
    "title": "bounce-modifier",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Without bounce: executes and continues
result = z.dispatch.handle("save", {"zFunc": "save_data"})
# Returns: True

# With bounce: executes then returns to menu (zCLI mode)
result = z.dispatch.handle("^save", {"zFunc": "save_data"})
# zCLI mode: Returns "zBack" (triggers menu navigation)
# zBifrost mode: Returns True (actual result for web client)
```

> **Mode-aware behavior:** The `^` modifier changes return values based on execution mode:
> - **zCLI** (terminal): Returns `"zBack"` to trigger menu navigation
> - **zBifrost** (web): Returns actual result for client-side handling

**Use cases:**
- Menu actions that should return to menu after execution
- Form submissions that should show menu again
- Any action where you want automatic "back to menu" behavior

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl2_modifiers/1_bounce_modifier.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl2_modifiers/1_bounce_modifier.py)

**What you'll discover:**
- Bounce modifier (^) for "execute and return"
- Mode-aware return values (zCLI vs. zBifrost)
- Automatic menu navigation
- Declarative flow control

---

### **ii. Menu Modifier (*)**

The Bounce modifier returns to an existing menu. But what if you want to **create a menu from data**?

**The Menu Modifier (*)**: Create menu from horizontal data

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "menu-modifier",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Define menu data
menu_data = {
    "title": "Main Menu",
    "items": {
        "option1": {"zFunc": "action1", "label": "Action 1"},
        "option2": {"zFunc": "action2", "label": "Action 2"},
        "option3": {"zFunc": "action3", "label": "Action 3"},
    }
}

# Create menu with * modifier
result = z.dispatch.handle("menu*", menu_data)
# zNavigation.create() is called automatically
# Menu is displayed and user can select options
```

> **How it works:** The `*` modifier routes to `zNavigation.create()`, which builds an interactive menu from your data structure.

**Menu features:**
- **Automatic numbering** - Items are numbered 1, 2, 3...
- **Back button** - Built-in "0: Back" option
- **Interactive selection** - User chooses via number input
- **Recursive dispatch** - Selected action is dispatched automatically

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl2_modifiers/2_menu_modifier.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl2_modifiers/2_menu_modifier.py)

**What you'll discover:**
- Menu modifier (*) for automatic menu creation
- zNavigation integration
- Interactive menu navigation
- Declarative UI patterns

---

### **iii. Anchor Modifier (~)**

Menus have a "Back" button by default. But what if you want a **menu without back navigation**?

**The Anchor Modifier (~)**: Disable back navigation

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "anchor-modifier",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Define menu data
main_menu = {
    "title": "Welcome (No Back)",
    "items": {
        "start": {"zFunc": "start_app", "label": "Start Application"},
        "exit": {"zFunc": "exit_app", "label": "Exit"},
    }
}

# Create anchored menu (no back button)
result = z.dispatch.handle("~menu*", main_menu)
# No "0: Back" option - user must choose from available actions
```

> **Use cases:** Welcome screens, login menus, confirmation dialogs, or any menu where going back doesn't make sense.

**Combining modifiers:**
- `menu*` - Menu with back button
- `~menu*` - Menu without back button (anchored)

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl2_modifiers/3_anchor_modifier.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl2_modifiers/3_anchor_modifier.py)

**What you'll discover:**
- Anchor modifier (~) for disabling back navigation
- Combined modifiers (~*)
- Control flow at menu level
- Welcome screens and entry points

---

### **iv. Required Modifier (!) — RETIRED**

> **Removed in 2026-06.** `!` is no longer a modifier — `RequiredModifier` and
> `modifier_required.py` were deleted and `!` dropped from `SUFFIX_MODIFIERS`.

The "must land first / retry until valid" need is now expressed as an **event**, not a
glyph. Gate the flow with a `zBtn type: submit` or a `zDialog`: the walk holds at the
event until the user acts, and the step's own return (zForce) decides pass/fail — there
is no built-in retry-until-success loop. See the zWizard grammar leaf for the model.

---

### **v. Combined Modifiers**

You've learned 4 modifiers individually. Now let's **combine them** for powerful declarative patterns:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "combined-modifiers",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Anchor + Menu: Welcome screen without back
welcome_menu = {
    "title": "Welcome",
    "items": {
        "login": {"zFunc": "login", "label": "Login"},
        "register": {"zFunc": "register", "label": "Register"},
    }
}
result = z.dispatch.handle("~menu*", welcome_menu)
# Displays welcome menu with no back option

```

**Modifier combinations:**

| Pattern | Modifiers | Meaning |
|---------|-----------|---------|
| `menu*` | Menu | Create menu with back button |
| `~menu*` | Anchor + Menu | Create menu without back |
| `<key>^` | Crumbs-rewind | Mint the bulk-back signal to a zPath |

*(Retired: `!` required and prefix-`^` bounce.)*

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl2_modifiers/5_combined_modifiers.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl2_modifiers/5_combined_modifiers.py)

**What you'll discover:**
- Combining multiple modifiers
- Declarative flow control patterns
- Complex navigation scenarios
- Expressive command syntax

---

**🎯 Level 2 Complete!**

You've mastered command modifiers for declarative flow control:
- ✅ **Menu Modifier (*)** - Create menus from data
- ✅ **Anchor Modifier (~)** - Disable back navigation
- ✅ **Crumbs-rewind (`<key>^`)** - Bulk-back to a zPath
- ✅ **Combined Modifiers** - Powerful declarative patterns
- *(Retired: `!` required and prefix-`^` bounce — gating is an event now)*

**This is where g_zDispatch's declarative power emerges. You're controlling application flow through simple symbols!**

---

# **g_zDispatch - Level 3** (Advanced Routing)

### **i. CRUD Auto-Detection**

So far you've explicitly used `{"zData": {...}}` for database operations. But zDispatch can **automatically detect CRUD operations**:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "crud-auto",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Explicit zData format
result = z.dispatch.handle("read", {
    "zData": {
        "action": "read",
        "model": "users",
        "where": {"id": 1}
    }
})

# Auto-detected CRUD (no zData key needed!)
result = z.dispatch.handle("read", {
    "action": "read",
    "model": "users",
    "where": {"id": 1}
})
# g_zDispatch detects: action + model keys → routes to zData automatically
```

> **How it works:** g_zDispatch checks for CRUD keywords (`action`, `model`, `table`) and routes to zData automatically. This reduces boilerplate in data-driven applications.

**Auto-detection rules:**
- Has `action` key? → CRUD
- Has `model` or `table` key? → CRUD
- Routes to zData.crud() automatically

**CRUD actions supported:**
- `read` - Query records
- `create` - Insert new record
- `update` - Modify existing record
- `delete` - Remove record
- `list` - Query multiple records

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl3_routing/1_crud_auto.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl3_routing/1_crud_auto.py)

**What you'll discover:**
- Automatic CRUD detection
- Reduced boilerplate
- Unified data operations
- Smart command routing

---

### **ii. Plugin Invocation**

Commands can invoke **plugins** using the `&` prefix:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "plugins",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Call plugin function
result = z.dispatch.handle("action", "zFunc(&my_plugin.calculate)")
# zParser resolves plugin path → executes plugin function

# Dict format with plugin
result = z.dispatch.handle("action", {
    "zFunc": "&analytics.generate_report",
    "args": ["monthly"]
})
```

> **Plugin system:** The `&` prefix triggers zParser to resolve plugin paths. Plugins are external modules that extend zOS functionality without modifying core code.

**Use cases:**
- External integrations
- Third-party modules
- Custom extensions
- Modular architecture

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl3_routing/2_plugins.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl3_routing/2_plugins.py)

**What you'll discover:**
- Plugin invocation with & prefix
- zParser integration
- External module execution
- Extensible architecture

---

### **iii. Shorthand Expansion**

zDispatch supports **shorthand keys** that expand to full command structures:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "shorthand",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Shorthand: UI element keys auto-expand
command = {
    "zTerminal": {
        "command": "ls -la",
        "capture": True
    }
}
result = z.dispatch.handle("exec", command)
# Auto-expands to proper zDisplay event structure

# Shorthand: Plural keys auto-expand
command = {
    "zItems": [
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"}
    ]
}
result = z.dispatch.handle("display", command)
# Auto-expands to list display format
```

> **Shorthand keys:** g_zDispatch recognizes special keys (zTerminal, zImage, zVideo, zItems, etc.) and expands them to proper command structures. This reduces verbosity in UI-heavy applications.

**Supported shorthands:**
- **UI elements**: zTerminal, zImage, zVideo, zAudio, zCode, zMarkdown
- **Plurals**: zItems, zTables, zForms (auto-expand to list handling)
- **Organizational**: Hierarchical structures with auto-expansion

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zDispatch_Demo/lvl3_routing/3_shorthand.py
```

[View demo source →](../../Demos/Layer_1/zDispatch_Demo/lvl3_routing/3_shorthand.py)

**What you'll discover:**
- Shorthand key expansion
- Reduced verbosity
- UI-focused shorthands
- Organizational patterns

---

**🎯 Level 3 Complete!**

You've completed advanced routing capabilities:
- ✅ **CRUD Auto-Detection** - Automatic database operation routing
- ✅ **Plugin Invocation** - External module integration
- ✅ **Shorthand Expansion** - Reduced verbosity for common patterns

**You now understand the complete g_zDispatch subsystem for command routing!**

---

## Module Structure

g_zDispatch follows a modular architecture with specialized components:

**Location:** `zOS/core/L2_Handling/g_zDispatch/`

**Core Modules:**
- `zDispatch.py` - Main facade class providing unified dispatch interface
- `__init__.py` - Package exports and public API
- `dispatch_modules/` - Specialized components directory

**Command Routing:**
- `dispatch_launcher.py` - CommandLauncher for routing to subsystems
- `dispatch_modifiers.py` - ModifierProcessor for detecting and processing modifiers
- `dispatch_helpers.py` - Helper utilities for command processing

**Handlers (Domain Logic):**
- `handler_auth.py` - AuthHandler for zLogin/zLogout
- `handler_crud.py` - CRUDHandler for automatic CRUD detection
- `handler_data.py` - DataHandler for zData operations
- `handler_navigation.py` - NavigationHandler for menu creation
- `handler_routing.py` - RoutingHandlers for subsystem delegation
- `handler_subsystems.py` - SubsystemRouter for zFunc/zWizard/zDialog
- `handler_wizard_data.py` - WizardDataHandlers for wizard-specific routing
- `handler_export.py` - ExportHandler for zExport (model rows → file/response)
- `handler_import.py` - ImportHandler for zImport (file/storage → model)

**Modifiers (Behavior):**
- `modifier_bounce.py` - BounceModifier for ^ modifier
- `modifier_menu.py` - MenuModifier for * modifier
- *(removed: `modifier_required.py` / RequiredModifier — `!` retired, gating is an event)*

**Commands (Parsing):**
- `command_list.py` - ListCommandHandler for array commands
- `command_string_parser.py` - StringCommandHandler for "zFunc(...)" parsing
- `command_wizard_detector.py` - WizardDetector for wizard invocations

**Expansion (Shorthands):**
- `shorthand_expander.py` - ShorthandExpander for UI element keys
- `expander_organizational.py` - OrganizationalHandler for hierarchical structures
- `expander_plurals.py` - PluralExpander for zItems/zTables/etc.
- `shorthand_element_expanders.py` - Element-specific expansion logic

**Resolvers (Data/UI):**
- `resolver_data.py` - DataResolver for data operations
- `resolver_ui.py` - UIResolver for UI block resolution

**Transfer (zTransfer/zExport/zImport):**
- `transfer_engine.py` - TransferEngine: orchestrates source → (codec) → target
- `transfer_adapters.py` - Backend-agnostic endpoints (file, model, storage, bytes, inline, response)
- `transfer_codec.py` - Format boundary (csv/tsv/json/txt) between blob ⇄ rows
- `transfer_payload.py` - TransferPayload wrapper (blob/rows nature)
- `transfer_paths.py` - Path/output-dir resolution for file endpoints
- `transfer_handler.py` - Dispatch entry point for zTransfer/zExport/zImport

**Utilities:**
- `dispatch_constants.py` - Shared constants and configuration
- `launcher_utils.py` - Utility functions for command launching

**Architecture Pattern:**
g_zDispatch uses the **Facade pattern** - a unified interface (`zDispatch` class) delegates to specialized components:
- `z.dispatch.handle()` → `ModifierProcessor.process()` or `CommandLauncher.launch()`
- `CommandLauncher` → Domain handlers (auth, CRUD, navigation, subsystems)
- `ModifierProcessor` → Domain modifiers (menu, anchor, crumbs-rewind)

This separation allows each component to be tested and evolved independently while maintaining a stable public API.

---

## Layer 2 Design Philosophy

As a **Layer 2 (Handling) subsystem**, g_zDispatch has special design considerations:

**Depends on Layer 1 (Foundation):**
- **zConfig**: Session constants, mode detection
- **zComm**: Communication infrastructure (for zBifrost mode)
- **zLoader**: Dynamic module loading

**Depends on L2 Siblings:**
- **e_zDisplay**: UI output and event handling
- **d_zParser**: Plugin resolution and command parsing

**Provides for Other L2 and Higher Layers:**
- Command routing infrastructure
- Modifier system for declarative flow control
- Integration points for subsystems (i_zFunc, zWizard, zData, etc.)

**Pure Routing Layer:**
- No business logic in dispatch (delegates to subsystems)
- No UI rendering (uses e_zDisplay for that)
- No data operations (uses zData for that)
- Focuses solely on command routing and flow control

**Integration Points:**
- **Depends on:** zConfig (session, mode), zComm (WebSocket for zBifrost), e_zDisplay (UI output), d_zParser (plugin resolution)
- **Used by:** i_zFunc (Layer 2), h_zNavigation (Layer 2), j_zDialog (Layer 2), Layer 3+ subsystems, user applications
- **Provides for:** Command routing, modifier processing, subsystem integration

---

## Advanced Features

### Mode-Aware Routing

g_zDispatch automatically detects execution mode and adjusts behavior:

```python
# zCLI mode (terminal)
result = z.dispatch.handle("^action", {"zFunc": "save"})
# Returns: "zBack" (trigger menu navigation)

# zBifrost mode (web)
# (Set via zSpark: {"mode": "zBifrost"})
result = z.dispatch.handle("^action", {"zFunc": "save"})
# Returns: {result: <actual result>, events: [...]}
```

**Mode detection:**
- Reads from `session[SESSION_KEY_ZMODE]`
- zCLI: Terminal-based execution with print output
- zBifrost: Web-based execution with event buffering

---

### Event Buffering (zBifrost Mode)

In zBifrost mode, g_zDispatch collects display events for web clients:

```python
# Execute command (zBifrost mode)
result = handle_zDispatch("action", {"zFunc": "my_func"}, zos=z)

# Returns structured response with events:
{
    "result": <actual return value>,
    "events": [
        {"event": "text", "data": {"content": "Processing..."}},
        {"event": "header", "data": {"label": "Complete"}},
        # ... all zDisplay events during execution
    ]
}
```

**How it works:**
1. Clear event buffer before execution
2. Execute command (captures all zDisplay events)
3. Collect buffered events after execution
4. Return structured response with result + events

---

### Facade API Reference

The `zDispatch` class provides these convenience methods:

**Main Entry Point:**
```python
# Dispatch command with optional context and walker
result = z.dispatch.handle(
    zKey="action",              # Command key (may include modifiers)
    zHorizontal={"zFunc": ...}, # Command data
    context={"user_id": 1},     # Optional context dict
    walker=walker               # Optional walker instance
)
```

**Standalone Function:**
```python
from zOS.core.L2_Handling.g_zDispatch import handle_zDispatch

# Convenience function for external callers
result = handle_zDispatch(
    zKey="action",
    zHorizontal={"zFunc": "my_function"},
    zos=z                       # or walker=walker
)
```

**Direct Component Access:**
```python
# Access modifiers
z.dispatch.modifiers.check_prefix("^action")   # Returns ["^"]
z.dispatch.modifiers.check_suffix("menu*")     # Returns ["*"]

# Access launcher
z.dispatch.launcher.launch({"zFunc": "my_func"})
```

**Mode Detection:**
```python
from zOS.L1_Foundation.a_zConfig.zConfig_modules import SESSION_KEY_ZMODE, ZMODE_ZBIFROST

# Check current mode
is_bifrost = z.session.get(SESSION_KEY_ZMODE) == ZMODE_ZBIFROST
```

---

### Public Constants Reference

g_zDispatch exports public constants from `dispatch_constants.py` for use in applications:

**Command Prefixes (String Format):**
```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    CMD_PREFIX_ZFUNC,    # "zFunc("
    CMD_PREFIX_ZLINK,    # "zLink("
    CMD_PREFIX_ZOPEN,    # "zOpen("
    CMD_PREFIX_ZWIZARD,  # "zWizard("
    CMD_PREFIX_ZREAD,    # "zRead("
)
```

**Dict Keys - Subsystem Commands:**
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
    KEY_ZDELEGATE,  # "zDelegate"
    KEY_ZEXPORT,    # "zExport"
    KEY_ZIMPORT,    # "zImport"
    KEY_ZTRANSFER,  # "zTransfer"
    KEY_ZDASH,      # "zDash"
    KEY_ZVAR,       # "zVar"
    KEY_ZLIST,      # "zList"
)
```

**Dict Keys - Data Operations:**
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
```

**Modifiers:**
```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    MOD_CARET,         # "^" - Crumbs-rewind (suffix: <key>^)
    MOD_TILDE,         # "~" - Anchor (no back)
    MOD_ASTERISK,      # "*" - Menu
    # MOD_EXCLAMATION ("!") RETIRED — gating is an event, not a modifier
    PREFIX_MODIFIERS,  # ["~"]
    SUFFIX_MODIFIERS,  # ["*", "^"]
    ALL_MODIFIERS,     # ["~", "*", "^"]
)
```

**Mode Values:**
```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    MODE_BIFROST,   # "zBifrost"
    MODE_ZCLI,      # "zCLI"
    MODE_WALKER,    # "Walker"
)
```

**Navigation:**
```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    NAV_ZBACK,      # "zBack"
)
```

**Plugins:**
```python
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    PLUGIN_PREFIX,  # "&"
)
```

**Usage Example:**
```python
from zOS import zOS
from zOS.core.L2_Handling.g_zDispatch.dispatch_modules import (
    KEY_ZFUNC,
    KEY_ACTION,
    KEY_MODEL,
    MOD_CARET,
    NAV_ZBACK,
)

z = zOS()

# Build command using constants
command = {
    KEY_ZFUNC: "save_user",
    "args": [user_data]
}

# Dispatch with bounce modifier
result = z.dispatch.handle(f"{MOD_CARET}save", command)

# Check for back navigation
if result == NAV_ZBACK:
    print("Returning to menu...")
```

---

## What's Next?

You've mastered **g_zDispatch** (Layer 2 command routing). Continue exploring Layer 2 subsystems:

**Layer 2 (Handling) Subsystems:**
- **[d_zParser Guide ←](zParser_GUIDE.md)** - Command and file parsing (previous)
- **[e_zDisplay Guide ←](zDisplay_GUIDE.md)** - Display and UI rendering (previous)
- **[f_zAuth Guide ←](zAuth_GUIDE.md)** - Authentication and authorization (previous)
- **[h_zNavigation Guide →](zNavigation_GUIDE.md)** - Navigation and menu systems (next)
- **[i_zFunc Guide](zFunc_GUIDE.md)** - Function execution and plugin integration
- **[j_zDialog Guide](zDialog_GUIDE.md)** - Interactive forms and input collection
- **[k_zOpen Guide](zOpen_GUIDE.md)** - File and resource opening

**Layer 3+ subsystems** build on g_zDispatch's command routing foundation for orchestration and data operations.

---

**[← Back to f_zAuth Guide](zAuth_GUIDE.md) | [Home](../../README.md) | [Next: h_zNavigation Guide →](zNavigation_GUIDE.md)**
