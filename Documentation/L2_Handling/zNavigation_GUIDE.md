**[← Back to g_zDispatch Guide](zDispatch_GUIDE.md) | [Home](../../README.md) | [Next: i_zFunc Guide →](zFunc_GUIDE.md)**

---

# h_zNavigation

**h_zNavigation** is the **fifth Layer 2 subsystem** in **zOS** (Layer 2: Handling) - providing navigation infrastructure.
> Located at: `zOS/core/L2_Handling/h_zNavigation/`
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

It provides comprehensive navigation functionality for zOS applications - interactive menus, breadcrumb trails, navigation state tracking, and inter-file linking through one unified interface.

You get:

- **Zero boilerplate**  
- **No manual menu rendering**
- **No breadcrumb management**  
- **Interactive menus** (single/multi-select, search)
- **Breadcrumb trails** ("Back" functionality, navigation history)
- **Navigation state** (location tracking, history management)  
- **Inter-file linking** (zLink expressions with RBAC)

## Architecture Overview

**h_zNavigation** is composed of specialized modules, each handling a specific aspect of navigation:

| Module | Purpose | Guide |
|--------|---------|-------|
| **menu** | Menu creation, rendering, and interaction | [menu_system_GUIDE.md](zNavigation_Guides/menu_system_GUIDE.md) |
| **breadcrumbs** | Navigation trail management and "Back" functionality | [breadcrumbs_GUIDE.md](zNavigation_Guides/breadcrumbs_GUIDE.md) |
| **state** | Location tracking and navigation history | [navigation_state_GUIDE.md](zNavigation_Guides/navigation_state_GUIDE.md) |
| **linking** | Inter-file navigation with zLink expressions | [linking_GUIDE.md](zNavigation_Guides/linking_GUIDE.md) |
| **handlers** | Specialized handlers (navbar, panels, breadcrumb ops, history, zback) | [handlers_GUIDE.md](zNavigation_Guides/handlers_GUIDE.md) |
| **resolvers** | Link resolution and expression evaluation | [resolvers_GUIDE.md](zNavigation_Guides/resolvers_GUIDE.md) |
| **helpers** | Utility functions and validation | *(coming soon)* |

This guide provides a **facade overview** of h_zNavigation. For deep dives into specific modules, see the guides in `zNavigation_Guides/`.

---

## Initialization Order

When you call `zOS()`, h_zNavigation initializes as part of the Layer 2 (Handling) subsystems:

**Layer 1 (Foundation):**
1. **zConfig** - Configuration management
2. **zComm** - Communication infrastructure
3. **zLoader** - Dynamic module loading

**Layer 2 (Handling):**
1. **d_zParser** - Command and file parsing
2. **e_zDisplay** - Display and UI rendering
3. **f_zAuth** - Authentication and authorization
4. **g_zDispatch** - Command dispatch and routing
5. **h_zNavigation** - Navigation infrastructure:
   - Create Navigation component (state tracking)
   - Create Breadcrumbs component (trail management)
   - Create Linking component (inter-file navigation)
   - Create MenuSystem component (menu orchestration)
   - Log ready state
6. **i_zFunc** and other L2 subsystems...

This order ensures h_zNavigation has access to display (e_zDisplay), authentication (f_zAuth), and dispatch (g_zDispatch) subsystems before initializing navigation components.

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

> All h_zNavigation demos are in: `Demos/Layer_2/zNavigation_Demo/`

---

# **h_zNavigation - Level 1** (Menu Basics)

### **i. Create Simple Menu**

Start with the simplest navigation - creating an interactive menu with options.

```python
from zOS import zOS

z = zOS()

# Create a simple menu
options = ["Settings", "Profile", "Logout"]
choice = z.cli.navigation.create(
    options,
    title="Main Menu",
    walker=z.cli.walker
)

print(f"You selected: {choice}")
```

**🎯 Run the demo to see for yourself**

```bash
python3 Demos/Layer_2/zNavigation_Demo/lvl1_menus/1_simple_menu.py
```

[View demo source →](../../Demos/Layer_2/zNavigation_Demo/lvl1_menus/1_simple_menu.py)

**What you'll discover:**
- Create interactive menus with one method call
- Options can be strings or dictionaries
- zNavigation handles rendering and input automatically
- User sees numbered options and selects by number
- Returns the selected option

---

### **ii. Menu with Back Button**

Enable "Back" functionality to let users navigate backwards through your menu hierarchy.

```python
from zOS import zOS

z = zOS()

# Create menu with automatic "Back" option
choice = z.cli.navigation.create(
    ["Settings", "Profile", "Logout"],
    title="Main Menu",
    allow_back=True,  # Adds automatic "Back" option
    walker=z.cli.walker
)

if choice == "Back":
    print("User went back")
else:
    print(f"You selected: {choice}")
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zNavigation_Demo/lvl1_menus/2_menu_with_back.py
```

[View demo source →](../../Demos/Layer_2/zNavigation_Demo/lvl1_menus/2_menu_with_back.py)

**What you discover:**
- Enable "Back" with `allow_back=True`
- "Back" option appears automatically at the bottom
- Returns string "Back" when user selects it
- Integrates with breadcrumb system (Level 2)

---

### **iii. Dynamic Menu from Function**

Generate menu options dynamically using a function - perfect for data-driven menus.

```python
from zOS import zOS

z = zOS()

# Function that generates menu options
def get_user_options():
    """Fetch users from database/API and create menu options."""
    users = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Charlie"}
    ]
    return [f"{u['name']} (ID: {u['id']})" for u in users]

# Create menu from function
choice = z.cli.navigation.create(
    get_user_options,  # Pass function (not function call!)
    title="Select User",
    walker=z.cli.walker
)

print(f"You selected: {choice}")
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zNavigation_Demo/lvl1_menus/3_dynamic_menu.py
```

[View demo source →](../../Demos/Layer_2/zNavigation_Demo/lvl1_menus/3_dynamic_menu.py)

**What you discover:**
- Pass function reference (not function call)
- Function called when menu is displayed
- Perfect for database queries, API calls, dynamic content
- Options refresh each time menu is shown

---

**🎯 Level 1 Complete!**

You've mastered the menu basics:
- ✅ **Simple menus** - Create interactive option lists
- ✅ **Back functionality** - Enable navigation backwards
- ✅ **Dynamic menus** - Generate options from functions

---

# **h_zNavigation - Level 2** (Breadcrumbs)

### **i. Navigation Trails**

Track where users have been with automatic breadcrumb trails.

```python
from zOS import zOS

z = zOS()

# Add breadcrumb when navigating to a section
z.cli.navigation.handle_zCrumbs(
    zBlock="users.menu",
    zKey="list_users",
    walker=z.cli.walker
)

# Later, user can navigate back through the trail
result = z.cli.navigation.handle_zBack(
    show_banner=True,
    walker=z.cli.walker
)

print(f"Navigated back to: {result}")
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zNavigation_Demo/lvl2_breadcrumbs/1_breadcrumb_trail.py
```

[View demo source →](../../Demos/Layer_2/zNavigation_Demo/lvl2_breadcrumbs/1_breadcrumb_trail.py)

**What you discover:**
- Add breadcrumbs with `handle_zCrumbs()`
- Navigate backwards with `handle_zBack()`
- Breadcrumbs stored in session automatically
- UI files reload based on breadcrumb state

---

### **ii. Menu with Breadcrumb Integration**

Combine menus with breadcrumb trails for complete navigation hierarchies.

```python
from zOS import zOS

z = zOS()

# Create menu and add to breadcrumb trail
choice = z.cli.navigation.create(
    ["Settings", "Profile", "Logout"],
    title="Main Menu",
    allow_back=True,
    walker=z.cli.walker
)

# Breadcrumb automatically added
# User can navigate back through menu hierarchy
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zNavigation_Demo/lvl2_breadcrumbs/2_menu_breadcrumbs.py
```

[View demo source →](../../Demos/Layer_2/zNavigation_Demo/lvl2_breadcrumbs/2_menu_breadcrumbs.py)

**What you discover:**
- Menus automatically integrate with breadcrumb system
- Each menu selection adds breadcrumb
- "Back" option navigates through breadcrumb trail
- Complete navigation hierarchy management

---

**🎯 Level 2 Complete!**

You've mastered breadcrumb navigation:
- ✅ **Navigation trails** - Track user navigation path
- ✅ **Back functionality** - Navigate backwards through history
- ✅ **Menu integration** - Automatic breadcrumb management

---

# **h_zNavigation - Level 3** (Navigation State)

### **i. Track Current Location**

Track where users are in your application with navigation state management.

```python
from zOS import zOS

z = zOS()

# Navigate to a location
z.cli.navigation.navigate_to(
    target="users.menu.list_users",
    context={"section": "users"}
)

# Get current location
location = z.cli.navigation.get_current_location()
print(f"Current location: {location}")

# Get navigation history
history = z.cli.navigation.get_navigation_history()
print(f"Navigation history: {history}")
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zNavigation_Demo/lvl3_state/1_location_tracking.py
```

[View demo source →](../../Demos/Layer_2/zNavigation_Demo/lvl3_state/1_location_tracking.py)

**What you discover:**
- Navigate to specific locations with `navigate_to()`
- Track current location with `get_current_location()`
- Access navigation history with `get_navigation_history()`
- Session state storage with timestamps

---

### **ii. Navigation History Management**

Manage navigation history with automatic FIFO overflow handling.

```python
from zOS import zOS

z = zOS()

# Navigate to multiple locations
locations = [
    "users.menu",
    "users.list",
    "users.edit",
    "settings.menu",
    "settings.profile"
]

for loc in locations:
    z.cli.navigation.navigate_to(loc)

# History automatically managed (FIFO with configurable limit)
history = z.cli.navigation.get_navigation_history()
print(f"History entries: {len(history)}")
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zNavigation_Demo/lvl3_state/2_history_management.py
```

[View demo source →](../../Demos/Layer_2/zNavigation_Demo/lvl3_state/2_history_management.py)

**What you discover:**
- Navigation history stored in session
- Automatic FIFO overflow (oldest entries removed)
- Configurable history limit
- Timestamp metadata for each navigation event

---

**🎯 Level 3 Complete!**

You've mastered navigation state management:
- ✅ **Location tracking** - Know where users are
- ✅ **Navigation history** - Track where users have been
- ✅ **State management** - Session storage with metadata

---

# **h_zNavigation - Level 4** (Inter-file Linking)

### **i. zLink Expressions**

Navigate between files and blocks using zLink expressions.

```python
from zOS import zOS

z = zOS()

# Navigate to file/block with zLink expression
result = z.cli.navigation.handle_zLink(
    zHorizontal="zLink(users.menu.list_users)",
    walker=z.cli.walker
)

print(f"Navigation result: {result}")
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zNavigation_Demo/lvl4_linking/1_zlink_basic.py
```

[View demo source →](../../Demos/Layer_2/zNavigation_Demo/lvl4_linking/1_zlink_basic.py)

**What you discover:**
- Navigate between files with zLink expressions
- Format: `zLink(folder.file.block)`
- Integrates with zParser for expression evaluation
- Updates session context (zVaFolder, zVaFile, zBlock)

---

### **ii. zLink with RBAC Permissions**

Control access to navigation targets with RBAC permission checking.

```python
from zOS import zOS

z = zOS()

# Navigate with RBAC permission check
result = z.cli.navigation.handle_zLink(
    zHorizontal="zLink(admin.settings.security)",
    walker=z.cli.walker
)

# If user lacks permissions, navigation is blocked
# Error message displayed automatically
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zNavigation_Demo/lvl4_linking/2_zlink_rbac.py
```

[View demo source →](../../Demos/Layer_2/zNavigation_Demo/lvl4_linking/2_zlink_rbac.py)

**What you discover:**
- Declarative permission requirements on navigation targets (`{"role": "admin"}`)
- Automatic permission denial handling (the target block does not render)
- Reads the caller's attributes from `session[zAuth]` (exact-match)

> **Security note — this is a *presentational* gate, not the security boundary.**
> The zLink permission check decides **which block renders**; it is a UX/defense-in-depth
> layer, not enforcement. The authoritative authorization for sensitive **actions** and
> **data** is `f_zAuth` (`z.auth.has_role` / `has_permission`) and the sealed zGuard
> `wizard_rbac`. Never rely on a zLink gate as the sole protection for a privileged
> operation — gate the action itself at the f_zAuth layer.

---

**🎯 Level 4 Complete!**

You've completed the entire h_zNavigation tutorial journey:
- ✅ **Level 1**: Menu basics (simple, back, dynamic)
- ✅ **Level 2**: Breadcrumbs (trails, integration)
- ✅ **Level 3**: Navigation state (location, history)
- ✅ **Level 4**: Inter-file linking (zLink, RBAC)

**You now understand the complete h_zNavigation subsystem!**

---

## Advanced Features

### Multi-Select Menus

Create menus that allow selecting multiple options:

```python
# Multi-select menu
selected = z.cli.navigation.select(
    ["Option A", "Option B", "Option C", "Option D"],
    prompt="Select multiple options (space-separated):",
    walker=z.cli.walker
)

print(f"Selected: {selected}")
```

**Use cases:** Batch operations, filter selection, configuration options.

---

### Search Functionality

Enable search in large menus for quick option finding:

```python
# Menu with search enabled
choice = z.cli.navigation.create(
    large_option_list,  # 100+ options
    title="Search Menu",
    enable_search=True,
    walker=z.cli.walker
)
```

**Use cases:** User selection, file navigation, command palettes.

---

### Display Formats

Control menu rendering with different display formats:

```python
# Compact format (minimal spacing)
choice = z.cli.navigation.create(
    options,
    title="Compact Menu",
    display_format="compact",
    walker=z.cli.walker
)

# Full format (with descriptions)
choice = z.cli.navigation.create(
    [
        {"label": "Settings", "description": "Configure app settings"},
        {"label": "Profile", "description": "Edit your profile"},
    ],
    title="Full Menu",
    display_format="full",
    walker=z.cli.walker
)
```

**Formats:** `full`, `simple`, `compact`

---

### Facade API Reference

The `zNavigation` class provides these convenience methods:

**Menu System:**
```python
# Create navigation menu
choice = z.cli.navigation.create(
    options=["A", "B", "C"],
    title="Menu Title",
    allow_back=False,
    walker=walker
)

# Simple selection (no breadcrumbs)
choice = z.cli.navigation.select(
    options=["A", "B", "C"],
    prompt="Select option:",
    walker=walker
)
```

**Breadcrumbs:**
```python
# Add breadcrumb
z.cli.navigation.handle_zCrumbs(
    zBlock="users.menu",
    zKey="option_key",
    walker=walker
)

# Navigate back
result = z.cli.navigation.handle_zBack(
    show_banner=True,
    walker=walker
)
```

**Navigation State:**
```python
# Navigate to location
z.cli.navigation.navigate_to(
    target="users.menu.list_users",
    context={"section": "users"}
)

# Get current location
location = z.cli.navigation.get_current_location()

# Get navigation history
history = z.cli.navigation.get_navigation_history()
```

**Inter-file Linking:**
```python
# Handle zLink expression
result = z.cli.navigation.handle_zLink(
    zHorizontal="zLink(path.to.file.block)",
    walker=walker
)
```

**Direct Module Access:**
```python
# Access components directly
z.cli.navigation.menu_system      # MenuSystem instance
z.cli.navigation.breadcrumbs      # Breadcrumbs instance
z.cli.navigation.navigation       # Navigation instance
z.cli.navigation.linking          # Linking instance
```

---

## Module Structure

h_zNavigation follows a modular architecture with specialized components:

**Location:** `zOS/core/L2_Handling/h_zNavigation/`

**Core Modules:**
- `zNavigation.py` - Main facade class providing unified interface
- `__init__.py` - Package exports and public API
- `navigation_modules/` - Specialized components directory

**Foundation Modules:**
- `navigation_breadcrumbs.py` - Breadcrumbs component (trail management)
- `navigation_state.py` - Navigation component (location tracking)
- `navigation_linking.py` - Linking component (inter-file navigation)
- `navigation_helpers.py` - Utility functions and validation
- `navigation_constants.py` - Shared constants and configuration

**Menu Modules:**
- `menu/navigation_menu_system.py` - MenuSystem orchestrator
- `menu/navigation_menu_builder.py` - MenuBuilder (construction)
- `menu/navigation_menu_renderer.py` - MenuRenderer (display)
- `menu/navigation_menu_interaction.py` - MenuInteraction (input)
- `menu/menu_search.py` - Search functionality

**Handler Modules:**
- `handlers/handler_navbar.py` - Navbar handler
- `handlers/handler_panels.py` - Panel handler
- `handlers/handler_breadcrumbs_ops.py` - Breadcrumb operations
- `handlers/handler_history.py` - History handler
- `handlers/handler_zback.py` - Back navigation handler

**Resolver Modules:**
- `resolvers/resolver_zlink.py` - zLink expression resolver

**Architecture Pattern:**
h_zNavigation uses the **Facade pattern** - a unified interface (`zNavigation` class) delegates to specialized components:
- `z.cli.navigation.create()` → `MenuSystem.create()`
- `z.cli.navigation.handle_zCrumbs()` → `Breadcrumbs.handle_zCrumbs()`
- `z.cli.navigation.navigate_to()` → `Navigation.navigate_to()`
- `z.cli.navigation.handle_zLink()` → `Linking.handle()`

This separation allows each component to be tested and evolved independently while maintaining a stable public API.

---

## Constants & SSOT

h_zNavigation follows the zOS single-source-of-truth discipline:

- **Session keys** (`zVaFolder`/`zVaFile`/`zBlock`/`zCrumbs`/`zAuth`/`zMode`) are drawn from `a_zConfig` → root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md); `navigation_constants` keeps only navigation-internal keys (`current_location`, `navigation_history`) as locals.
- **Run-mode literals** alias `zVocabulary` `ZMODE_ZCLI` / `ZMODE_ZBIFROST` / `ZMODE_WEB` (Web mode is now a first-class vocabulary value) — no raw `"zCLI"`/`"Web"` strings.
- **`ZLinkResolver.classify_href`** is the **Python SSOT for href classification** (internal-delta / internal-zpath / external / anchor / placeholder), imported by `e_zDisplay` (`display_event_links`, `inline_transformer`, `rich_text_renderer`) so link-type detection stays identical across zLink and zURL.
- **Trust:** zNavigation has no code-exec surface; zLink permission dicts are parsed via `zParser.zExpr_eval` (JSON, not `eval`). Nothing is sealed in zGuard — it is generic UI-flow infrastructure (see the zLink security note above).

---

## Layer 2 Design Philosophy

As a **Layer 2 (Handling) subsystem**, h_zNavigation has special design considerations:

**zCLI Integration:**
- Accessed via `z.cli.navigation` (not `z.navigation`)
- Initialized as part of zCLI subsystem
- Provides navigation infrastructure for Walker orchestration
- Mode-agnostic (supports zCLI and Bifrost modes)

**Depends on Layer 1 (Foundation):**
- **zConfig**: Session constants, configuration management
- **zComm**: Communication infrastructure
- **zLoader**: File loading and caching

**Depends on L2 Siblings:**
- **e_zDisplay**: UI rendering and output
- **d_zParser**: Expression parsing and evaluation
- **f_zAuth**: RBAC permission checking
- **g_zDispatch**: Menu modifier integration

**Component Orchestration:**
- MenuSystem orchestrates builder, renderer, and interaction
- Each component has single responsibility
- Components communicate via clean interfaces
- Walker integration for UI file orchestration

**Declarative Navigation:**
- Menu definitions in UI files (YAML)
- zLink expressions for declarative linking
- Breadcrumb trails managed automatically
- Navigation state tracked in session

**Integration Points:**
- **Depends on:** e_zDisplay (rendering), zConfig (state), d_zParser (expressions), zLoader (files), f_zAuth (RBAC), g_zDispatch (menu modifier)
- **Used by:** Layer 3+ subsystems (zWalker orchestration), user applications
- **Provides for:** Interactive navigation, menu systems, breadcrumb trails, inter-file linking

---

## What's Next?

You've mastered **h_zNavigation** (Layer 2 navigation infrastructure). Continue exploring Layer 2 subsystems:

**Layer 2 (Handling) Subsystems:**
- **[d_zParser Guide ←](zParser_GUIDE.md)** - Command and file parsing (previous)
- **[e_zDisplay Guide ←](zDisplay_GUIDE.md)** - Display and UI rendering (previous)
- **[f_zAuth Guide ←](zAuth_GUIDE.md)** - Authentication and authorization (previous)
- **[g_zDispatch Guide ←](zDispatch_GUIDE.md)** - Command dispatch and routing (previous)
- **[i_zFunc Guide →](zFunc_GUIDE.md)** - Function execution and plugin integration (next)
- **[j_zDialog Guide](zDialog_GUIDE.md)** - Interactive forms and input collection
- **[k_zOpen Guide](zOpen_GUIDE.md)** - File and resource opening

> **Note:** For complete application orchestration using h_zNavigation declaratively, see [zWalker Guide](../L4_Orchestration/zWalker_GUIDE.md) - a Layer 4 orchestration subsystem that showcases navigation patterns in production.

---

**[← Back to g_zDispatch Guide](zDispatch_GUIDE.md) | [Home](../../README.md) | [Next: i_zFunc Guide →](zFunc_GUIDE.md)**
