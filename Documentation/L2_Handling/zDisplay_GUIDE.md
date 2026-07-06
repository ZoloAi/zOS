**[← Back to d_zParser Guide](zParser_GUIDE.md) | [Home](../../README.md) | [Next: f_zAuth Guide →](zAuth_GUIDE.md)**

---

# e_zDisplay

**e_zDisplay** is the **second Layer 2 subsystem** in **zOS** (Layer 2: Handling).
> Located at: `zOS/core/L2_Handling/e_zDisplay/`
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

It provides professional terminal output and input through one unified interface - progress bars, tables, menus, interactive widgets, and more.

You get:

- **Zero configuration**
- **No curses library**
- **No ANSI escape sequences**
- **30+ display events** (text, headers, tables, progress bars, spinners, inputs)
- **Multi-mode support** (Terminal, WebSocket/Browser)
- **Event-driven architecture** (declarative display operations)
- **Backward-compatible API** (convenience methods + event dictionaries)

> **Need GUI rendering?** All these display methods also work in Browser mode. See [zBifrost Guide](../L3_Abstraction/zBifrost_GUIDE.md) for real-time Terminal ↔ Web rendering.

## Architecture Overview

**e_zDisplay** is composed of specialized modules, each handling a specific aspect of display:

| Module | Purpose | Guide |
|--------|---------|-------|
| **io** | Terminal I/O primitives (raw, line, block, input) | [io_GUIDE.md](zDisplay_Guides/io_GUIDE.md) |
| **basic** | Core event logic (outputs, inputs, signals) | [basic_GUIDE.md](zDisplay_Guides/basic_GUIDE.md) |
| **compounds** | Complex interactive widgets (selection, buttons, links) | [compounds_GUIDE.md](zDisplay_Guides/compounds_GUIDE.md) |
| **advanced** | Markdown, progress bars, spinners, tables | [advanced_GUIDE.md](zDisplay_Guides/advanced_GUIDE.md) |
| **system** | System UI (zDeclare, zMenu, zDialog, zSession) | [system_GUIDE.md](zDisplay_Guides/system_GUIDE.md) |
| **api** | Convenience methods (backward compatibility) | [api_GUIDE.md](zDisplay_Guides/api_GUIDE.md) |
| **utils** | Pure utilities + **mode-detection SSOT** (`mode_helper`) | [utils_GUIDE.md](zDisplay_Guides/utils_GUIDE.md) |
| **sandbox** | `zTerminal` local execution + `display_trust` (zGuard seam) | *(below → [zTerminal & Trust](#zterminal--trust-model))* |

This guide provides a **facade overview** of e_zDisplay. For deep dives into specific modules, see the guides in `zDisplay_Guides/`.

---

## Initialization Order

When you call `zOS()`, e_zDisplay initializes as part of the Layer 2 (Handling) subsystems:

**Layer 1 (Foundation):**
1. **zConfig** - Configuration management
2. **zComm** - Communication infrastructure
3. **zLoader** - Dynamic module loading

**Layer 2 (Handling):**
1. **d_zParser** - Command and file parsing
2. **e_zDisplay** - Display and UI rendering:
   - Validate zOS instance (session + logger required)
   - Detect mode from session (zCLI vs zBifrost)
   - Initialize I/O layer (terminal or WebSocket)
   - Create event orchestrator with 10 event packages
   - Wire up convenience methods (backward compatibility)
   - Print ready message (using e_zDisplay itself)
   - Log ready state
3. **f_zAuth** and other L2 subsystems...

This order ensures e_zDisplay has access to configuration (from zConfig) and communication (from zComm) before initializing display components.

---

## zTerminal & Trust Model

`zTerminal` is a display event that can **execute code on the operator's local machine** (zCLI mode). It is intentionally powerful and is **not a security sandbox** — do not treat the restricted-builtins Python path as a boundary against hostile code. The real protection is a **fail-closed config gate**.

**Execution policy — `ZTERMINAL_MODE` (declared in `zEnv`):**

| `ZTERMINAL_MODE` | Local zCLI behavior |
|------------------|---------------------|
| *unset / empty / `disabled` / unknown* | **No execution** (fail-closed). zTerminal blocks render as code, nothing runs. |
| `sandboxed` | Python only, restricted builtins (best-effort, **not** a hard boundary). |
| `trusted` | Operator fully trusts the content (local desktop). Python runs; bash is not implemented in open-core (sealed path only). |

Because execution requires an **explicit operator declaration**, a checked-out repository containing foreign `zTerminal` content **cannot auto-run** on a machine the operator did not opt in on. This removes the "undeclared/silent-auto-run" risk class.

**Bifrost mode** short-circuits the local executor entirely; remote execution is handled by the sealed WebSocket `execute_code` path and gated by zGuard.

**Proprietary seam — `sandbox/display_trust.verify_terminal_exec()`:** a hook layered on top of the config gate. **Open-core ships only the permissive fallback** (`try: from zguard.display.terminal_trust… / except ImportError → return True`), so the seam is a no-op without zGuard and zTerminal stays fully functional. When zGuard is installed it **seals this seam** and a denial raises `TerminalTrustError` (propagated unwrapped, never swallowed). What the sealed policy actually enforces (executor integrity/attestation, code provenance, tamper detection) and how it resists hostile forks is **proprietary — see the private zGuard documentation** (requires zGuard; contact your zOS admin / `z patch`).

**Code:** `zDisplay_modules/sandbox/terminal_executor.py` (gate + executor), `zDisplay_modules/sandbox/display_trust.py` (zGuard seam).

---

## Constants & Mode SSOT

- **Mode protocol values** (`zCLI`, `zBifrost`) are single-sourced in root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md) (`ZMODE_ZCLI`/`ZMODE_ZBIFROST`). `display_constants.MODE_ZCLI`/`MODE_BIFROST`/`DEFAULT_MODE` are thin aliases; `MODE_WALKER`/empty stay zDisplay-local.
- **Mode detection is centralized** in `utils/mode_helper.py` — `is_bifrost_mode()`, `is_terminal_mode()`, `get_mode()`, and the `TERMINAL_MODES` tuple. Call sites use these (or the constants) instead of hardcoded `"zCLI"`/`"zBifrost"` literals.
- **Event names** are single-sourced: `_EVENT_NAME_*` alias the base `_EVENT_*` constants (no duplicate string literals).
- **Optional `zlsp`**: escape-sequence decoding in rich-text/text/header renderers is guarded with `try/except ImportError`; if `zlsp` is absent, rendering degrades gracefully (escapes left literal) rather than crashing.

**Auto-Initialization:**
```python
from zOS import zOS

z = zOS()  # L1 (zConfig → zComm → zLoader) → L2 (d_zParser → e_zDisplay) → other subsystems

# e_zDisplay is now ready:
z.display.line("Hello World!")                    # Primitives
z.display.success("Operation complete")           # Signals
z.display.zTable(title="Users", columns=[], rows=[])  # Advanced
z.display.handle({"event": "text", "content": "..."})  # Event API
```

---

## Best Practices & Import Patterns

### <span style="color:#8FBE6D">Centralized Imports</span>

zOS provides a **unified import namespace** for all standard library modules and typing helpers. Instead of importing directly from `typing`, `asyncio`, `json`, etc., use the centralized pattern:

**✅ Recommended (Centralized):**
```python
from zOS import zOS, Any, Dict, Optional, asyncio, json, uuid
```

**❌ Avoid (Direct Imports):**
```python
import asyncio
import json
import uuid
from typing import Any, Dict, Optional
```

**Why Centralized Imports?**
- **Single source of truth** - All imports defined in `zOS/__init__.py`
- **Consistency** - All modules use the same pattern
- **Future-proof** - Easy to add polyfills or compatibility layers
- **Type safety** - Centralized typing helpers ensure consistency
- **Cleaner code** - One import line instead of multiple

**Available Centralized Imports:**
- **Standard Library**: `asyncio`, `json`, `logging`, `os`, `re`, `sys`, `traceback`, `uuid`, `datetime`, `Path`, and more
- **Typing Helpers**: `Any`, `Callable`, `Dict`, `List`, `Optional`, `Tuple`, `Union`
- **Third-Party**: `yaml`, `requests`, `websockets`
- **Utils**: `Colors`, `safe_json_dumps`

**Example:**
```python
from zOS import zOS, Dict, List, json

z = zOS()

# Use centralized imports throughout your code
data: Dict[str, List[str]] = {"users": ["alice", "bob"]}
json_str = json.dumps(data)
z.display.text(f"Data: {json_str}", color="CYAN")
```

> **Note:** This pattern is used internally by all e_zDisplay modules for consistency and maintainability.

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

> All e_zDisplay demos are in: `Demos/Layer_1/zDisplay_Demo/`

---

# **e_zDisplay - Level 1** (Primitives)

### <span style="color:#8FBE6D">Level 1A: raw() - No Newline</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# All on one line - raw() never adds newlines
z.display.raw("First")
z.display.raw(" + ")
z.display.raw("Second")
z.display.raw(" + ")
z.display.raw("Third")
z.display.raw("\n")  # You control when to break

# Use case: Building status messages
z.display.raw("Status: ")
z.display.raw("[ok] Connected")
z.display.raw("\n")
```

The most primitive display operation—**write text with no automatic newline**. You get complete control over when lines break. Perfect for building output piece by piece: progress indicators, inline status updates, or combining text fragments. `raw()` is the foundation—all other display methods build on this.

> **Try it:** [`output/Level_1_Primitives/write_raw.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_1_Primitives/write_raw.py)

### <span style="color:#8FBE6D">Level 1B: line() - Automatic Newline</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# Each call becomes its own line
z.display.line("1) Each call becomes its own line")
z.display.line("2) No need to append \\n manually")
z.display.line("3) Perfect for log-style output")
```

Single-line output with automatic newline handling. No need to manually add `\n`—`line()` does it for you. Perfect for log-style output, simple messages, or any content where each call should start on a new line. Cleaner than `raw()` when you want the newline every time.

> **Try it:** [`output/Level_1_Primitives/write_line.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_1_Primitives/write_line.py)

### <span style="color:#8FBE6D">Level 1C: block() - Multi-Line Output</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# Multi-line string, formatting preserved
block = """Deployment Summary
- Host: localhost
- Mode: Terminal
- Status: Ready to render"""

z.display.block(block)
```

Send multiple lines at once while preserving your formatting. `block()` handles the trailing newline automatically. Great for banners, status summaries, or any preformatted text. Your line breaks stay intact, terminal spacing stays clean.

> **Try it:** [`output/Level_1_Primitives/write_block.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_1_Primitives/write_block.py)

### <span style="color:#8FBE6D">Level 1D: read_string() - Collect Text Input</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# Simple prompt
name = z.display.read_string("What's your name? ")
z.display.line(f"Hello, {name}!")

# Configuration input with defaults
host = z.display.read_string("Database host [localhost]: ")
if not host:
    host = "localhost"
port = z.display.read_string("Database port [5432]: ")
if not port:
    port = "5432"

z.display.line(f"[ok] Configuration: {host}:{port}")
```

The most basic input primitive—**collect user text input**. Prompts the user, waits for their response, and returns what they typed (without the newline). Perfect for interactive CLIs, configuration wizards, or any situation where you need to ask the user a question.

> **Try it:** [`input/Level_1_Primitives/read_string.py`](../../Demos/Layer_1/zDisplay_Demo/input/Level_1_Primitives/read_string.py)

### <span style="color:#8FBE6D">Level 1E: read_password() - Masked Input</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# Secure password input
password = z.display.read_password("Password: ")
z.display.line(f"[ok] Password captured ({len(password)} characters)")

# Login flow
username = z.display.read_string("Username: ")
password = z.display.read_password("Password: ")

if username and password:
    z.display.line(f"[ok] Credentials collected for: {username}")
```

Secure input collection with **masked typing**—just like `read_string()`, but the user's input is hidden from view. Essential for passwords, API keys, tokens, or any sensitive data. The terminal shows nothing (or asterisks) while the user types, preventing shoulder-surfing and accidental exposure.

> **Try it:** [`input/Level_1_Primitives/read_password.py`](../../Demos/Layer_1/zDisplay_Demo/input/Level_1_Primitives/read_password.py)

---

### <span style="color:#8FBE6D">Level 2A: header() - Formatted Headers</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# Style: full (═══)
z.display.header("System Initialization", color="CYAN", style="full")

# Style: single (───)
z.display.header("Loading Configuration", color="GREEN", style="single")

# Style: wave (~~~)
z.display.header("Processing Data", color="YELLOW", style="wave")

# With indentation
z.display.header("Main Section", color="MAGENTA", indent=0, style="full")
z.display.header("Subsection", color="BLUE", indent=1, style="single")
```

Create **visual structure** with formatted section headers. Three styles: `full` (═), `single` (─), `wave` (~). Multiple colors (CYAN, GREEN, YELLOW, MAGENTA, BLUE, RED). Use indentation to show hierarchy. Headers organize your output into clear sections.

> **Try it:** [`output/Level_2_Foundation/header.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_2_Foundation/header.py)

### <span style="color:#8FBE6D">Level 2B: text() - Display with Control</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# Simple text output
z.display.text("Configuration loaded successfully")

# With indentation (each level = 2 spaces)
z.display.text("Configuration:", indent=0)
z.display.text("Database: PostgreSQL", indent=1)
z.display.text("Host: localhost", indent=2)

# With pause for user acknowledgment
z.display.text("⚠️  About to delete data...", pause=True)
z.display.text("Data deleted", indent=1)
```

Display text with **indent and pause control**. Indent creates hierarchy (0-3+ levels, 2 spaces each). Pause waits for user to press Enter before continuing. Perfect for nested content, step-by-step workflows, or confirmations. Builds on `line()` by adding control features.

> **Try it:** [`output/Level_2_Foundation/text.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_2_Foundation/text.py)

### <span style="color:#8FBE6D">Level 2C: signals() - Color-Coded Feedback</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# Success (green [ok])
z.display.success("Operation completed successfully")

# Error (red ✗)
z.display.error("Connection failed")

# Warning (yellow ⚠)
z.display.warning("Deprecated feature in use")

# Info (cyan ℹ)
z.display.info("Processing 10 records...")

# With indentation
z.display.success("Database connected", indent=0)
z.display.info("Host: localhost", indent=1)
z.display.info("Port: 5432", indent=1)

# zMarker - visual separator for workflow stages
z.display.zMarker("Checkpoint 1")
z.display.info("Stage 1 complete")
z.display.zMarker("Checkpoint 2", color="CYAN")
```

**Semantic feedback with automatic colors.** Four core signals (success=green, error=red, warning=yellow, info=cyan) plus `zMarker()` for workflow separators. Colors and icons apply automatically based on message type. Perfect for operation feedback, validation results, and user notifications. All signals support indentation for hierarchical feedback.

> **Try it:** [`output/Level_2_Foundation/signals.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_2_Foundation/signals.py)

### <span style="color:#8FBE6D">Level 2D: system() - System Display Events</span>

> **💡 Note:** These system display events build on concepts from **[zConfig Guide](../L1_Foundation/zConfig_GUIDE.md)**. If you've worked through the early zConfig demos, you've already seen `z.session`, `z.config.get_machine()`, and `z.config.get_environment()`. This tutorial shows how to **display** that configuration data professionally. For more on reading and managing config values, see the [zConfig Guide](../L1_Foundation/zConfig_GUIDE.md).

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# System announcements with zDeclare()
z.display.zDeclare("System Initialization")
z.display.zDeclare("Loading Configuration", indent=1)
z.display.zDeclare("Services Ready", color="GREEN")

# Display session state
z.display.zSession(z.session)

# Display configuration info
config_data = {
    "machine": {
        "os": z.config.get_machine("os"),
        "hostname": z.config.get_machine("hostname")
    },
    "environment": {
        "deployment": "Debug",
        "mode": "zCLI"
    }
}
z.display.zConfig(config_data)

# Real-world startup sequence
z.display.zDeclare("Application Starting", color="CYAN")
z.display.info("Loading environment", indent=1)
z.display.success("Configuration complete", indent=1)
z.display.zDeclare("Application Ready", color="GREEN")
```

**Professional system status reporting.** Three specialized methods: `zDeclare()` for system announcements with colors (GREEN/YELLOW/RED/BLUE), `zSession()` for displaying current session state, and `zConfig()` for machine/environment configuration. Perfect for startup sequences, system monitoring, and professional status displays. All support indentation for hierarchical output.

> **Try it:** [`output/Level_2_Foundation/system.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_2_Foundation/system.py)

### <span style="color:#8FBE6D">Level 2E: button() - Action Confirmation</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# Safe action confirmation
if z.display.button("Save Profile", color="success"):
    z.display.success("✅ Profile saved!")
else:
    z.display.info("Profile not saved")

# Dangerous action warning
if z.display.button("Delete Account", color="danger"):
    z.display.warning("⚠️ Account marked for deletion!")
else:
    z.display.info("Account deletion cancelled")

# Multi-step workflow
if z.display.button("Start Backup", color="info"):
    z.display.info("Preparing backup...", indent=1)
    if z.display.button("Confirm Backup", color="success"):
        z.display.success("[ok] Backup completed!", indent=1)
```

**Action confirmation with yes/no prompts.** Requires explicit user confirmation (y/n) to prevent accidental actions. Color-coded by action type: `success` (green), `danger` (red), `warning` (yellow), `info` (blue). Returns `True` (confirmed) or `False` (cancelled). Perfect for destructive operations, important decisions, or multi-step workflows requiring validation.

> **Try it:** [`input/Level_2_Foundation/button.py`](../../Demos/Layer_1/zDisplay_Demo/input/Level_2_Foundation/button.py)

### <span style="color:#8FBE6D">Level 2F: selection() - Choose from List</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# Single selection
role = z.display.selection(
    "Select your role:",
    ["Developer", "Designer", "Manager"]
)
z.display.success(f"Selected: {role}")

# Multiple selections
skills = z.display.selection(
    "Select your skills:",
    ["Python", "JavaScript", "React", "Django"],
    multi=True
)
z.display.success(f"Selected: {', '.join(skills)}")

# Selection with default
theme = z.display.selection(
    "Choose theme:",
    ["Light", "Dark", "Auto"],
    default="Dark"
)
z.display.success(f"Selected: {theme}")
```

**User choice from numbered list.** Displays options with numbers (1, 2, 3...), user types number(s) to select. Single selection returns one item, multi-selection (`multi=True`) returns a list. Optional `default` parameter for pre-selected values. Perfect for menus, configuration wizards, or any scenario where users need to choose from predefined options.

> **Try it:** [`input/Level_2_Foundation/selection.py`](../../Demos/Layer_1/zDisplay_Demo/input/Level_2_Foundation/selection.py)

---

### <span style="color:#8FBE6D">Level 3: Data - Structured Data Display</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# List - Bullet/Number/Letter styles
z.display.list(["Fast", "Simple", "Multi-mode"], style="bullet")
z.display.list(["Initialize", "Configure", "Deploy"], style="number")
z.display.list(["Option A", "Option B", "Option C"], style="letter")

# Outline - Hierarchical multi-level (1→a→i→•)
z.display.outline([
    {
        "content": "Backend Architecture",
        "children": [
            {
                "content": "Python Runtime",
                "children": ["zOS initialization", "Event handling"]
            },
            "Data Processing Layer"
        ]
    },
    {
        "content": "Frontend Architecture",
        "children": ["Rendering Engine", "User Interaction"]
    }
])

# JSON Data - With syntax coloring
config = {"version": "1.5.5", "mode": "zCLI", "ready": True}
z.display.json_data(config, color=True)
```

**Professional structured data display.** Three display types: `list()` for bullet/number/letter lists, `outline()` for hierarchical multi-level documents (1→a→i→• pattern), and `json_data()` for pretty-printed JSON with optional syntax coloring. Perfect for options, menu items, config display, and nested structures.

> **Try it:** [`output/Level_3_Data/data.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_3_Data/data.py)

### <span style="color:#8FBE6D">Level 3: Data - Tables (zTable)</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

users = [
    {"ID": 1, "Name": "Alice", "Email": "alice@example.com"},
    {"ID": 2, "Name": "Bob", "Email": "bob@example.com"},
    {"ID": 3, "Name": "Charlie", "Email": "charlie@example.com"},
    {"ID": 4, "Name": "Diana", "Email": "diana@example.com"},
    {"ID": 5, "Name": "Eve", "Email": "eve@example.com"},
]

# Type 1: Basic - No Pagination (all rows)
z.display.zTable(
    title="All Users",
    columns=["ID", "Name", "Email"],
    rows=users
)

# Type 2: Simple Truncation (limit only → "... N more rows" footer)
z.display.zTable(
    title="Users (Limited to 3)",
    columns=["ID", "Name", "Email"],
    rows=users,
    limit=3  # Shows first 3 with footer
)

# Type 3: Interactive Navigation (limit + interactive=True)
z.display.zTable(
    title="Users - Interactive",
    columns=["ID", "Name", "Email"],
    rows=users,
    limit=2,
    offset=0,
    interactive=True  # Keyboard navigation: [n]ext, [p]revious, [f]irst, [l]ast, [#] jump, [q]uit
)
```

**Advanced table display with THREE pagination modes.** Type 1: Basic (no pagination, shows all rows). Type 2: Simple truncation (limit only, shows "... N more rows" footer). Type 3: Interactive navigation (limit + interactive=True, full keyboard controls). Perfect for database query results from `zData`. Automatic column alignment and mixed data type support (strings, numbers, booleans).

> **Try it:** [`output/Level_3_Data/table.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_3_Data/table.py)

---

## Level 4: Progress Tracking

> **💡 Consolidated Demos:** Level 4 uses a streamlined demo structure where related methods are combined into single files. Each demo shows both automatic and manual modes for the same visual output, helping you choose the right control level for your use case.

### <span style="color:#8FBE6D">Level 4A: progress_bar() & progress_iterator() - Deterministic Progress</span>

```python
import time
from zOS import zOS

z = zOS({"logger": "PROD"})

# Manual mode: Full control over progress
total = 50
start_time = time.time()

for i in range(total + 1):
    z.display.progress_bar(
        current=i,
        total=total,
        label="Processing files",
        show_percentage=True,
        show_eta=True,
        start_time=start_time,
        color="GREEN"
    )
    time.sleep(0.05)  # Simulate work

# Automatic mode: Zero manual updates
files = [f"file_{i}.txt" for i in range(1, 26)]

for filename in z.display.progress_iterator(files, "Processing files"):
    time.sleep(0.08)  # progress_iterator() manages current/total/start_time
```

**Visual progress tracking with TWO modes.** Manual mode (`progress_bar`) gives full control over current/total/start_time. Automatic mode (`progress_iterator`) wraps iterables for zero-config progress tracking. Both display identical visual output with percentage completion and ETA. Choose based on your use case: manual for flexibility, automatic for simplicity.

> **💡 Cross-Terminal Support:** Progress bars automatically adapt to your terminal's capabilities. Modern terminals (iTerm2, Alacritty, Kitty, Cursor) use smooth in-place updates with `\r`. macOS Terminal.app uses cursor-up rendering for the same visual effect. Same code, optimized rendering everywhere.

> **Try it:** [`output/Level_4_Progress/bar.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_4_Progress/bar.py)

### <span style="color:#8FBE6D">Level 4B: spinner() & indeterminate_progress() - Unknown Duration</span>

```python
import time
from zOS import zOS

z = zOS({"logger": "PROD"})

# Automatic mode: Context manager with auto-animation
with z.display.spinner("Loading data", style="dots"):
    time.sleep(2)  # Animates automatically in background

with z.display.spinner("Processing", style="arc"):
    time.sleep(2)

# Manual mode: Fine-grained control over updates
update_progress = z.display.indeterminate_progress("Processing data")
for i in range(30):
    update_progress()  # You control when frames update
    time.sleep(0.1)
z.display.raw("\n")  # Add newline when done
```

**Animated loading indicator with TWO control modes.** Automatic mode (`spinner`) uses context manager for background animation and auto-cleanup. Manual mode (`indeterminate_progress`) returns an update function you call in your loop for fine-grained control. Both produce identical visual output (animated spinner frames). Perfect for API calls, database queries, file I/O, or any operation where duration is unpredictable.

> **Try it:** [`output/Level_4_Progress/spinner.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_4_Progress/spinner.py)

### <span style="color:#8FBE6D">Level 4C: swiper() - Interactive Slideshow</span>

```python
from zOS import zOS

z = zOS({"logger": "PROD"})

# Simple auto-advancing slideshow
intro_slides = [
    "Welcome to zOS!",
    "zOS is a declarative CLI framework",
    "Professional terminal UI with one API",
    "Let's explore the features..."
]

z.display.zEvents.TimeBased.swiper(
    intro_slides, 
    "Introduction", 
    auto_advance=True, 
    delay=3
)

# Manual navigation tutorial
tutorial_slides = [
    "Step 1: Initialize zOS\n\n  from zOS import zOS\n  z = zOS()",
    "Step 2: Display Progress\n\n  z.display.progress_bar(50, 100)",
    "Step 3: Show Spinners\n\n  with z.display.spinner('Loading'):\n      time.sleep(2)"
]

z.display.zEvents.TimeBased.swiper(
    tutorial_slides, 
    "Tutorial", 
    auto_advance=False  # User navigates with arrow keys
)
```

**Interactive content carousel with beautiful box-drawn UI.** Auto-advancing slides with configurable delay, or manual navigation with arrow keys (◀ ▶), number keys (1-N jump to slide), pause/resume ('p' key), and quit ('q' key). Multi-line content support with proper formatting. Perfect for tutorials, onboarding flows, feature showcases, and presentations.

> **💡 Note:** Swiper is accessed via `z.display.zEvents.TimeBased.swiper()` - a powerful interactive component for guided experiences.

> **Try it:** [`output/Level_4_Progress/swiper.py`](../../Demos/Layer_1/zDisplay_Demo/output/Level_4_Progress/swiper.py)

---

## Summary

You've learned e_zDisplay's **<span style="color:#8FBE6D">complete rendering capabilities</span>**:

✅ **Primitives (Layer 1)**
- `raw()` - Write without newline (full control)
- `line()` - Write with automatic newline
- `block()` - Multi-line output with preserved formatting
- `read_string()` - Collect text input from user
- `read_password()` - Masked password input

✅ **Foundation (Layer 2)**
- `header()` - Formatted section headers (═/─/~) with colors
- `text()` - Display text with indentation control and pause support
- `success()` - Green [ok] confirmations
- `error()` - Red ✗ failures
- `warning()` - Yellow ⚠ cautions
- `info()` - Cyan ℹ information
- `zMarker()` - Magenta workflow separators
- `zDeclare()` - System announcements with colors
- `zSession()` - Session state display
- `zConfig()` - Configuration display
- `button()` - Action confirmation with yes/no prompts
- `selection()` - Choose from numbered list (single or multi-select)

✅ **Data (Layer 3)**
- `list()` - Bullet/number/letter lists
- `outline()` - Hierarchical multi-level (1→a→i→•)
- `json_data()` - Pretty-printed JSON with syntax coloring
- `zTable()` - Tables with THREE pagination modes:
  - Type 1: Basic (no pagination, all rows)
  - Type 2: Simple truncation (limit only, "... N more rows" footer)
  - Type 3: Interactive navigation (limit + interactive=True, keyboard controls)

✅ **Progress Tracking (Layer 4)**
- `progress_bar()` + `progress_iterator()` - Deterministic progress (manual + automatic modes)
- `spinner()` + `indeterminate_progress()` - Indeterminate loading (automatic + manual modes)
- `swiper()` - Interactive slideshow carousel with navigation

**<span style="color:#F8961F">16 micro-step demos</span>** organized by function:

**Output Demos** (`output/` folder):
- Level 1: Primitives (3) - `raw`, `line`, `block`
- Level 2: Foundation (4) - `header`, `text`, `signals`, `system`
- Level 3: Data (2) - `data` (list/outline/json), `table`
- Level 4: Progress (3) - `bar`, `spinner`, `swiper`

**Input Demos** (`input/` folder):
- Level 1: Primitives (2) - `read_string`, `read_password`
- Level 2: Foundation (2) - `button`, `selection`

## You've Mastered Dual-Mode Display

You now have the complete **<span style="color:#F8961F">rendering toolkit</span>**:
- ✅ Output primitives (raw, line, block) for full control
- ✅ Input primitives (read_string, read_password) for user interaction
- ✅ Foundation events (header, text, signals, system, button, selection)
- ✅ Data display (list, outline, json_data, zTable with pagination)
- ✅ Progress tracking (bar, spinner, swiper with auto/manual modes)

**<span style="color:#8FBE6D">e_zDisplay gives you professional UI for Terminal and Browser—same code, automatic adaptation.</span>**

---

## Module Structure

e_zDisplay follows a modular architecture with specialized components organized in layers:

**Location:** `zOS/core/L2_Handling/e_zDisplay/`

**Core Modules:**
- `zDisplay.py` - Main facade class providing unified interface
- `__init__.py` - Package exports and public API
- `zDisplay_modules/` - Specialized components directory

**Layer Architecture (top → bottom):**

**API Layer** (`api/`):
- `delegate_primitives.py` - Convenience methods for I/O primitives
- `delegate_outputs.py` - Convenience methods for output events
- `delegate_signals.py` - Convenience methods for signal events
- `delegate_data.py` - Convenience methods for data display
- `delegate_system.py` - Convenience methods for system events

**Event Orchestration:**
- `display_events.py` - Event orchestrator that wires all packages together

**Event Implementation Layers:**

**Basic Layer** (`basic/`):
- `display_basic_outputs.py` - Core output event logic
- `display_basic_inputs.py` - Core input event logic
- `outputs/semantic_colors.py` - Color constants and semantic mapping
- `outputs/rendering_utilities.py` - Output rendering helpers
- `outputs/json_renderer.py` - JSON formatting and syntax highlighting
- `inputs/boolean_input.py` - Yes/no confirmation logic

**Compounds Layer** (`compounds/`):
- `display_compounds_outputs.py` - Complex output widgets
- `display_compounds_inputs.py` - Complex input widgets
- `inputs/selection_collector.py` - Selection menu logic
- `inputs/selection_renderer.py` - Selection menu rendering
- `inputs/input_validators.py` - Input validation utilities
- `inputs/link_handler.py` - Link interaction handling
- `inputs/slider_widget.py` - Slider input widget
- `outputs/display_event_data.py` - Data structure rendering
- `outputs/display_event_links.py` - Link display events

**Advanced Layer** (`advanced/`):
- `display_event_advanced.py` - Advanced display events
- `display_event_outputs.py` - Advanced output events
- `display_event_timebased.py` - Time-based events (progress, spinner)
- `advanced_table.py` - Table rendering with pagination
- `advanced_pagination.py` - Pagination logic
- `timebased_progress.py` - Progress bar implementation
- `timebased_spinner.py` - Spinner animation
- `timebased_swiper.py` - Slideshow carousel
- `timebased_utilities.py` - Time-based utilities
- `event_id_utils.py` - Event ID generation
- `markdown/` - Markdown rendering subsystem (8 modules)

**System Layer** (`system/`):
- `display_event_system.py` - System event orchestration
- `system_event_declare.py` - zDeclare implementation
- `system_event_session.py` - zSession display
- `system_event_dialog.py` - zDialog implementation
- `system_event_navigation.py` - zCrumbs/zMenu navigation

**I/O Layer** (`io/`):
- `display_primitives.py` - Primitive I/O coordination
- `display_primitives_outputs.py` - Output primitives (raw, line, block)
- `display_primitives_inputs.py` - Input primitives (read_string, read_password)
- `outputs/output_raw.py` - Raw output implementation
- `outputs/output_line.py` - Line output implementation
- `outputs/output_block.py` - Block output implementation
- `inputs/input_string.py` - String input implementation
- `inputs/input_password.py` - Password input implementation

**Utilities Layer** (`utils/`):
- `display_utilities.py` - Pure stateless utilities
- `value_formatter.py` - Value formatting helpers
- `system_message_filter.py` - System message filtering
- `nested_accessor_wip.py` - Nested data access (WIP)

**Constants:**
- `display_constants.py` - All event name strings and shared literals

**Architecture Pattern:**
e_zDisplay uses the **Facade + Event Orchestration pattern** - a unified interface (`zDisplay` class) provides convenience methods that build event dictionaries and route through `handle()`:

```python
# Convenience method (backward compatible)
z.display.success("Done!")

# Internally becomes:
z.display.handle({
    "event": "success",
    "content": "Done!"
})

# Event orchestrator routes to appropriate handler:
# → display_events.Signals.success(event_dict)
# → basic/display_basic_outputs.py renders output
# → io/display_primitives_outputs.py handles terminal/WebSocket
```

This separation allows:
- **Backward compatibility** - Old API still works
- **Event-driven architecture** - New declarative patterns
- **Mode transparency** - Terminal vs WebSocket handled at I/O layer
- **Independent testing** - Each layer tested separately

---

## Layer 2 Design Philosophy

As a **Layer 2 (Handling) subsystem**, e_zDisplay has special design considerations:

**Depends on Layer 1 (Foundation):**
- Uses zConfig for configuration (deployment mode, session state)
- Uses zComm for WebSocket communication (zBifrost mode)
- Uses zLoader for dynamic module loading
- Initialized after all Layer 1 subsystems

**Provides for Other L2 and Higher Layers:**
- f_zAuth uses e_zDisplay for authentication UI
- d_zParser uses e_zDisplay for parsing feedback
- g_zDispatch uses e_zDisplay for event feedback
- h_zNavigation uses e_zDisplay for interactive menus
- i_zFunc uses e_zDisplay for wizard interfaces
- Layer 3+ subsystems use e_zDisplay for query results and UI rendering

**Multi-Mode Operation:**
- **zCLI Mode (Terminal)**: Direct console I/O (print, input, getpass)
- **zBifrost Mode (GUI)**: WebSocket event broadcasting to browser

Mode is resolved once at initialization from `session[SESSION_KEY_ZMODE]`. The I/O layer enforces exclusive behavior - terminal syscalls OR WebSocket delegation, never both.

**Event-Driven Architecture:**
All display operations route through `handle()` with event dictionaries:

```python
z.display.handle({
    "event": "text",       # Event name (required)
    "content": "Hello",    # Event-specific parameters
    "color": "INFO"
})
```

The event map routes to appropriate handlers in the event orchestrator, which delegates to specialized modules.

---

## Advanced Features

### Event API

e_zDisplay provides both convenience methods (backward compatible) and event dictionaries (new declarative style):

**Convenience Methods:**
```python
# Output events
z.display.line("Hello World!")
z.display.header("Section Title", color="CYAN", style="full")
z.display.text("Content", indent=1, pause=False)

# Signal events
z.display.success("Operation complete")
z.display.error("Connection failed")
z.display.warning("Deprecated feature")
z.display.info("Processing...")

# Data events
z.display.list(["Item 1", "Item 2"], style="bullet")
z.display.json_data({"key": "value"}, color=True)
z.display.zTable(title="Users", columns=[], rows=[])

# System events
z.display.zDeclare("System Ready", color="GREEN")
z.display.zSession(z.session)

# Progress events
z.display.progress_bar(current=50, total=100, label="Processing")
with z.display.spinner("Loading"):
    time.sleep(2)

# Input events
name = z.display.read_string("Name: ")
password = z.display.read_password("Password: ")
choice = z.display.selection("Choose:", ["A", "B", "C"])
confirmed = z.display.button("Continue?", color="success")
```

**Event Dictionaries:**
```python
# Same operations using event API
z.display.handle({"event": "line", "content": "Hello World!"})
z.display.handle({"event": "header", "label": "Section Title", "color": "CYAN", "style": "full"})
z.display.handle({"event": "text", "content": "Content", "indent": 1, "pause": False})

z.display.handle({"event": "success", "content": "Operation complete"})
z.display.handle({"event": "error", "content": "Connection failed"})

z.display.handle({"event": "list", "items": ["Item 1", "Item 2"], "style": "bullet"})
z.display.handle({"event": "json_data", "data": {"key": "value"}, "color": True})

z.display.handle({"event": "zDeclare", "label": "System Ready", "color": "GREEN"})
z.display.handle({"event": "progress_bar", "current": 50, "total": 100, "label": "Processing"})
```

**Why Both APIs?**
- **Convenience methods** - Familiar, imperative, backward compatible
- **Event dictionaries** - Declarative, composable, future-proof

Both route through the same `handle()` method internally.

---

### Mode Detection

e_zDisplay automatically detects execution mode from session state:

```python
# Mode is set during zOS initialization
z = zOS()  # Defaults to zCLI (Terminal) mode

# Or explicitly via zSpark
z = zOS({"mode": "zBifrost"})  # WebSocket/Browser mode

# Mode detection happens once at initialization
# zDisplay._is_bifrost flag is computed and cached
# No per-event mode switching
```

**Mode Behavior:**

**zCLI Mode (Terminal):**
- Direct console I/O (print, input, getpass)
- ANSI color codes for styling
- Blocking input methods
- Immediate visual feedback

**zBifrost Mode (GUI):**
- WebSocket event broadcasting
- JSON event objects
- Non-blocking (async) operations
- Browser-rendered UI

The I/O layer (`io/`) handles mode-specific implementation transparently.

---

### Facade API Reference

The `zDisplay` class provides these convenience methods:

**Primitives:**
```python
# Output primitives
z.display.raw("text")           # No newline
z.display.line("text")          # With newline
z.display.block("multi\nline")  # Multi-line block

# Input primitives
text = z.display.read_string("Prompt: ")
password = z.display.read_password("Password: ")

# Legacy aliases (backward compatible)
z.display.write_raw("text")     # → raw()
z.display.write_line("text")    # → line()
z.display.write_block("text")   # → block()
```

**Foundation:**
```python
# Formatted output
z.display.header("Title", color="CYAN", style="full")
z.display.text("Content", indent=1, pause=False)

# Signals
z.display.success("Done!")      # Green [ok]
z.display.error("Failed!")      # Red ✗
z.display.warning("Warning!")   # Yellow ⚠
z.display.info("Info...")       # Cyan ℹ
z.display.zMarker("Stage 1")    # Magenta separator

# System events
z.display.zDeclare("System Ready", color="GREEN")
z.display.zSession(z.session)
z.display.zConfig(config_dict)

# Input events
confirmed = z.display.button("Continue?", color="success")
choice = z.display.selection("Choose:", ["A", "B", "C"])
choices = z.display.selection("Choose:", ["A", "B"], multi=True)
```

**Data:**
```python
# Lists and outlines
z.display.list(["A", "B", "C"], style="bullet")
z.display.list(["1", "2", "3"], style="number")
z.display.outline([{"content": "A", "children": ["B", "C"]}])

# JSON
z.display.json_data({"key": "value"}, color=True)

# Tables
z.display.zTable(
    title="Users",
    columns=["id", "name"],
    rows=[{"id": 1, "name": "Alice"}],
    limit=10,
    offset=0,
    interactive=False
)
```

**Progress:**
```python
# Deterministic progress
z.display.progress_bar(
    current=50,
    total=100,
    label="Processing",
    show_percentage=True,
    show_eta=True,
    start_time=time.time()
)

# Automatic progress
for item in z.display.progress_iterator(items, "Processing"):
    process(item)

# Indeterminate progress
with z.display.spinner("Loading", style="dots"):
    time.sleep(2)

# Manual spinner
update = z.display.indeterminate_progress("Building")
for i in range(30):
    update()
    time.sleep(0.1)
z.display.raw("\n")

# Slideshow
z.display.zEvents.TimeBased.swiper(
    slides=["Slide 1", "Slide 2"],
    title="Tutorial",
    auto_advance=True,
    delay=3
)
```

**Event API:**
```python
# Generic event handler
z.display.handle({
    "event": "text",
    "content": "Hello",
    "color": "INFO"
})

# Access event orchestrator
z.display.zEvents.Outputs.text(event_dict)
z.display.zEvents.Signals.success(event_dict)
z.display.zEvents.Data.list(event_dict)
z.display.zEvents.Advanced.progress_bar(event_dict)
z.display.zEvents.System.zDeclare(event_dict)
z.display.zEvents.Inputs.selection(event_dict)
z.display.zEvents.TimeBased.swiper(slides, title)
```

**Direct Module Access:**
```python
# Access modules directly (advanced)
z.display.zEvents          # Event orchestrator
z.display.zPrimitives      # I/O primitives layer
z.display._event_map       # Event routing map
```

---

## Event Composition

Complex methods build on primitives—everything composes from the foundation:

```
zTable() → header() → text() → line() → raw()
```

When you call `z.display.zTable()`, it internally uses headers and text formatting, which ultimately call `raw()` or `line()`. **Everything builds on the primitives.**

**Composition Flow:**
1. **API Layer** - Convenience method builds event dict
2. **Event Orchestrator** - Routes to appropriate handler
3. **Event Implementation** - Composes from lower layers
4. **I/O Layer** - Terminal syscalls or WebSocket emission

---

## Quick Reference

**Primitives (Layer 1):**

```python
# Raw output - you control newlines
z.display.raw("Loading")
z.display.raw("...")
z.display.raw("\n")

# Line output - automatic newline
z.display.line("Processing complete")

# Block output - multi-line with preserved formatting
z.display.block("Line 1\nLine 2\nLine 3")

# Input collection
name = z.display.read_string("What's your name? ")
password = z.display.read_password("Password: ")

# Legacy aliases (backward compatible)
z.display.write_raw("text")   # → raw()
z.display.write_line("text")  # → line()
z.display.write_block("text") # → block()
```

**Foundation (Layer 2):**

```python
# Formatted headers - visual structure
z.display.header("Section Title", color="CYAN", style="full")   # ═══
z.display.header("Subsection", color="GREEN", style="single")   # ───
z.display.header("Note", color="YELLOW", style="wave")          # ~~~

# Text with indentation - hierarchy
z.display.text("Main content", indent=0)
z.display.text("Nested content", indent=1)
z.display.text("Deeper content", indent=2)

# Optional pause for user acknowledgment
z.display.text("Press Enter to continue", pause=True)

# Legacy parameter still works (backward compatible)
z.display.text("Old API", break_after=False)

# Feedback signals - automatic color coding
z.display.success("✅ Done!")        # Green
z.display.error("❌ Failed!")        # Red
z.display.warning("⚠️  Watch out!")  # Yellow
z.display.info("ℹ️  FYI...")         # Cyan

# Visual workflow separator
z.display.zMarker("Stage 1")         # Magenta separator
z.display.zMarker("Stage 2", color="CYAN")  # Custom color

# System events - professional status reporting
z.display.zDeclare("System Initialization", color="GREEN")
z.display.zDeclare("Loading Configuration", indent=1)
z.display.zSession(z.session)        # Display session state
z.display.zConfig(config_data)       # Display configuration

# User input - action confirmation
if z.display.button("Save Profile", color="success"):
    z.display.success("Profile saved!")

# User input - selection
role = z.display.selection("Choose role:", ["Developer", "Designer", "Manager"])
skills = z.display.selection("Choose skills:", ["Python", "React"], multi=True)
```

**Data (Layer 3):**

```python
# Lists - bullet/number/letter styles
z.display.list(["Apple", "Banana", "Cherry"], style="bullet")
z.display.list(["Step 1", "Step 2", "Step 3"], style="number")
z.display.list(["Option A", "Option B", "Option C"], style="letter")

# Outline - hierarchical (1→a→i→•)
z.display.outline([
    {
        "content": "Backend",
        "children": ["Python", "Database"]
    },
    "Frontend"
])

# JSON - with syntax coloring
z.display.json_data({"version": "1.5.5", "ready": True}, color=True)

# Tables with THREE pagination modes
# Type 1: Basic (no pagination)
z.display.zTable(
    title="Users",
    columns=["id", "name", "email"],
    rows=user_data
)

# Type 2: Simple truncation (limit only)
z.display.zTable(
    title="Users (Limited)",
    columns=["id", "name", "email"],
    rows=user_data,
    limit=3  # Shows "... N more rows" footer
)

# Type 3: Interactive navigation (limit + interactive=True)
z.display.zTable(
    title="Users - Interactive",
    columns=["id", "name", "email"],
    rows=user_data,
    limit=2,
    offset=0,
    interactive=True  # Keyboard controls: [n]ext, [p]revious, [f]irst, [l]ast, [#] jump, [q]uit
)
```

**Progress Tracking (Layer 4):**

```python
import time

# Deterministic progress - Manual mode (full control)
for i in range(100):
    z.display.progress_bar(
        current=i,
        total=100,
        label="Processing",
        show_percentage=True,
        show_eta=True,
        start_time=time.time()
    )

# Deterministic progress - Automatic mode (wrapper)
files = ["file1.txt", "file2.txt", "file3.txt"]
for file in z.display.progress_iterator(files, "Processing files"):
    process(file)  # progress_iterator manages counters automatically

# Indeterminate spinner - Automatic mode (context manager)
with z.display.spinner("Loading data", style="dots"):
    time.sleep(2)  # Background animation

# Indeterminate spinner - Manual mode (fine control)
update = z.display.indeterminate_progress("Building index")
for i in range(30):
    update()  # You control frame updates
    time.sleep(0.1)
z.display.raw("\n")

# Interactive slideshow carousel
slides = ["Welcome!", "Feature 1", "Feature 2", "Thank you!"]
z.display.zEvents.TimeBased.swiper(slides, "Tutorial", auto_advance=True, delay=3)
```

---

## What's Next

**<span style="color:#8FBE6D">Continue the Layer 2 Journey</span>**

e_zDisplay is **<span style="color:#F8961F">Layer 2 (Handling)</span>**—the rendering engine that powers user interfaces. The natural progression continues with other **<span style="color:#8FBE6D">Layer 2 subsystems</span>**:

- **[d_zParser Guide ←](zParser_GUIDE.md)** - Command and file parsing (previous)
- **[f_zAuth Guide →](zAuth_GUIDE.md)** - Authentication and user management (next)
- **[g_zDispatch Guide](zDispatch_GUIDE.md)** - Event handling and routing
- **[h_zNavigation Guide](zNavigation_GUIDE.md)** - Navigation and menu systems
- **[i_zFunc Guide](zFunc_GUIDE.md)** - Function execution and plugins
- **[j_zDialog Guide](zDialog_GUIDE.md)** - Forms and validation
- **[k_zOpen Guide](zOpen_GUIDE.md)** - File and resource opening

**<span style="color:#8FBE6D">Want Browser Rendering?</span>**

All these display methods also work in real-time web browser mode. For Terminal ↔ Web rendering, see:

- **[zBifrost Guide](../L3_Abstraction/zBifrost_GUIDE.md)** - WebSocket server with GUI rendering support

---

**[← Back to d_zParser Guide](zParser_GUIDE.md) | [Home](../../README.md) | [Next: f_zAuth Guide →](zAuth_GUIDE.md)**
