**[← Back to zDialog Guide](zDialog_GUIDE.md) | [Home](../../README.md) | [Next: zWizard Guide →](../L3_Abstraction/zWizard_GUIDE.md)**

---

# zOpen

**zOpen** is a **Layer 2 subsystem** in **zOS** (Position 11).
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

It provides unified file and URL opening functionality - automatically detecting content types, resolving zPath notation, and opening resources in appropriate applications.

You get:

- **Zero manual commands** — no `os.system()`, list-form `subprocess` only
- **zPath resolution** (@ workspace, ~ absolute)
- **URL opening** (http, https, www prefix)
- **Smart file routing** (HTML → browser, text → IDE)
- **Media opening** (`open_image` / `open_video` / `open_audio`)
- **Interactive fallbacks** (file creation, IDE selection)
- **Hook execution** (onSuccess/onFail callbacks)
- **Local-first & trust-gated** — fail-closed off zCLI; path-trust seam before any read/launch (see [Security & Trust](#security--trust))

## Architecture Overview

**zOpen** is composed of specialized modules, each handling a specific aspect of opening operations:

| Module | Purpose | Guide |
|--------|---------|-------|
| **open_paths** | zPath notation resolution (@ and ~ symbols) | [open_paths_GUIDE.md](zOpen_Guides/open_paths_GUIDE.md) |
| **open_urls** | URL opening in browsers | [open_urls_GUIDE.md](zOpen_Guides/open_urls_GUIDE.md) |
| **open_files** | File opening by extension (HTML, text) + IDE launch | [open_files_GUIDE.md](zOpen_Guides/open_files_GUIDE.md) |
| **open_constants** | Shared constants and configuration (vocab from root `zVocabulary`) | [open_constants_GUIDE.md](zOpen_Guides/open_constants_GUIDE.md) |
| **open_trust** | Path-trust gate (zGuard seam) | *(in this guide → [Security & Trust](#security--trust))* |

This guide provides a **facade overview** of zOpen. For deep dives into specific modules, see the guides in `zOpen_Guides/`.

---

## Initialization Order

When you call `zOS()`, zOpen initializes automatically in Layer 2:

1. **Layer 0 Ready** - zConfig and zComm initialized
2. **Layer 1 Ready** - zDisplay, zAuth, zDispatch initialized
3. **Layer 2 Initialization** - zOpen starts:
   - Validate zOS instance (requires session, display, dialog, func, logger)
   - Store references to zOS subsystems
   - Log ready state
4. **zOpen Ready** - File and URL opening available

This order ensures zOpen has access to all required subsystems (display for output, dialog for prompts, func for hooks).

**Auto-Initialization:**
```python
from zOS import zOS

z = zOS()  # zConfig → zComm → zDisplay → ... → zOpen

# zOpen is now ready:
z.open.handle("zOpen(/path/to/file.txt)")         # File opening
z.open.handle("zOpen(https://github.com)")        # URL opening
z.open.handle("zOpen(@.README.md)")                # zPath resolution
```

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

> All zOpen demos are in: `Demos/Layer_2/zOpen_Demo/`

---

# **zOpen - Level 1** (Basic Opening)

### **i. Open Local Files**

Let's start with the simplest operation - opening a local file. zOpen automatically detects the file type and opens it in the appropriate application.

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "file-open",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Open a Python file - opens in your IDE
result = z.open.handle("zOpen(/path/to/script.py)")

# Open an HTML file - opens in your browser
result = z.open.handle("zOpen(/path/to/page.html)")

# Open a text file - opens in your IDE
result = z.open.handle("zOpen(/path/to/notes.txt)")
```

**What happens:**
- Python files (.py) → Opens in your IDE (Cursor, VS Code, nano, etc.)
- HTML files (.html, .htm) → Opens in your browser
- Text files (.txt, .md, .json, .yaml, etc.) → Opens in your IDE

**IDE Selection:**
- Uses your configured IDE from zMachine preferences
- If not configured, prompts you to select (one-time setup)
- Supports: Cursor, VS Code, Sublime, Vim, Nano, Fleet, Zed, PyCharm, WebStorm

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zOpen_Demo/lvl1_basic/1_open_file.py
```

[View demo source →](../../Demos/Layer_2/zOpen_Demo/lvl1_basic/1_open_file.py)

**What you'll discover:**
- Automatic file type detection
- Opens in appropriate application
- IDE preference from zMachine config
- Interactive IDE selection if needed
- Clean error handling for missing files

---

### **ii. Open URLs**

Opening URLs is just as simple - zOpen detects URL patterns and opens them in your browser.

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "url-open",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Open HTTPS URL
result = z.open.handle("zOpen(https://github.com)")

# Open HTTP URL
result = z.open.handle("zOpen(http://example.com)")

# Open URL with www prefix (auto-adds https://)
result = z.open.handle("zOpen(www.google.com)")
```

**What happens:**
- HTTPS URLs → Opens directly in browser
- HTTP URLs → Opens directly in browser
- www.* URLs → Adds https:// prefix automatically
- Uses your preferred browser from zMachine config
- Falls back to system default browser if needed

**Browser Selection:**
- Uses configured browser from zMachine preferences
- Supports: Chrome, Firefox, Safari, Arc, Brave, Edge, Opera
- Automatic fallback to system default

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zOpen_Demo/lvl1_basic/2_open_url.py
```

[View demo source →](../../Demos/Layer_2/zOpen_Demo/lvl1_basic/2_open_url.py)

**What you'll discover:**
- URL pattern detection (http, https, www)
- Opens in preferred or default browser
- Automatic https:// prefix for www URLs
- Fallback info display if browser fails
- Clean error handling

---

### **iii. zPath Resolution**

zOpen introduces **zPath notation** - a declarative way to reference files using symbols:

**Symbols:**
- `@` - Workspace-relative path
- `~` - Absolute path from filesystem root
- `.` - Path component separator

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "zpath-open",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Open workspace-relative file
# @.README.md → /workspace/README.md
result = z.open.handle("zOpen(@.README.md)")

# Open nested workspace file
# @.docs.setup.md → /workspace/docs/setup.md
result = z.open.handle("zOpen(@.docs.setup.md)")

# Open absolute file
# ~.Users.alice.notes.txt → /Users/alice/notes.txt
result = z.open.handle("zOpen(~.Users.alice.notes.txt)")
```

**Why zPath?**
- **Portable:** Works across machines regardless of actual path
- **Declarative:** References relative to workspace, not hardcoded paths
- **Type-safe:** Validated before resolution
- **Clear intent:** @ means workspace, ~ means absolute

**Resolution:**
1. Validates zPath format (must start with @ or ~)
2. Splits path by . separator
3. Resolves to filesystem path using workspace context
4. Opens resolved file based on extension

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zOpen_Demo/lvl1_basic/3_zpath.py
```

[View demo source →](../../Demos/Layer_2/zOpen_Demo/lvl1_basic/3_zpath.py)

**What you'll discover:**
- zPath notation (@ and ~ symbols)
- Automatic workspace resolution
- Path validation before opening
- Clear error messages for invalid paths
- Opens resolved files correctly

---

# **zOpen - Level 2** (Interactive Features)

### **i. File Creation Prompt**

What happens when you try to open a file that doesn't exist? Traditional approaches crash or silently fail. zOpen prompts you interactively.

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "file-create",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Try to open non-existent file
result = z.open.handle("zOpen(/path/to/new_file.txt)")

# zDialog prompt appears:
# "File not found: /path/to/new_file.txt"
# Options:
#   - Create file
#   - Cancel
```

**What happens:**
1. zOpen detects file doesn't exist
2. zDialog displays interactive prompt
3. User chooses: Create file or Cancel
4. If Create: File created, then opened in IDE
5. If Cancel: Returns "stop"

**Integration with zDialog:**
- Uses zDialog for interactive prompts
- Clean yes/no options
- Handles user cancellation gracefully
- Logs all actions

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zOpen_Demo/lvl2_interactive/1_file_create.py
```

[View demo source →](../../Demos/Layer_2/zOpen_Demo/lvl2_interactive/1_file_create.py)

**What you'll discover:**
- Interactive file creation prompt
- zDialog integration for choices
- Graceful cancellation handling
- Automatic IDE opening after creation
- Clean logging of actions

---

### **ii. IDE Selection Prompt**

If no IDE is configured in zMachine, zOpen prompts you to select one. This is a one-time setup that persists.

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "ide-select",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Try to open text file (no IDE configured)
result = z.open.handle("zOpen(/path/to/notes.txt)")

# zDialog prompt appears (only when the configured IDE is "unknown"):
# "Select your preferred IDE:"
# Options (from _AVAILABLE_IDES):
#   - cursor
#   - code
#   - nano
#   - vim
```

**What happens:**
1. zOpen reads the IDE from `session["ide"]` → `session["zMachine"]["ide"]` (default `nano`)
2. If it is `"unknown"` and a dialog is available, zDialog prompts from `_AVAILABLE_IDES`
3. User selects preferred IDE (falls back to `nano` if selection fails)
4. The chosen IDE is launched **only if** the platform detector resolves it to a real, validated command
5. Otherwise zOpen degrades to safe content display (it never execs an unvalidated binary name)

**IDE prompt choices (`_AVAILABLE_IDES`):** `cursor`, `code`, `nano`, `vim`.

**Detector-supported launch targets** (resolved by `get_ide_launch_command`, beyond the prompt list): also `subl`/`sublime`, `atom`, `webstorm`, `pycharm`, `idea`, `fleet`, `zed`, `nvim`, `vi`, `emacs`, `xed` — each validated via `shutil.which` / macOS `open -a`. An editor the detector can't resolve is **not** launched (content display instead).

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zOpen_Demo/lvl2_interactive/2_ide_select.py
```

[View demo source →](../../Demos/Layer_2/zOpen_Demo/lvl2_interactive/2_ide_select.py)

**What you'll discover:**
- Interactive IDE selection
- Persistent preference (one-time setup)
- Supports all major IDEs
- Falls back to nano if selection fails
- Clean error handling

---

### **iii. Content Display Fallback**

If IDE opening fails (IDE not installed, permission issues, etc.), zOpen displays the file content directly in the terminal.

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "content-display",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Open file (IDE might fail)
result = z.open.handle("zOpen(/path/to/notes.txt)")

# If IDE fails, content displayed:
# ════════════════════════════════════
# File Content: notes.txt
# ════════════════════════════════════
# [file contents here]
# [Content truncated if > 1000 chars]
```

**What happens:**
1. Attempts to open in IDE
2. If the IDE launch fails **or** the editor isn't resolved by the detector allowlist (security hardening):
   - Reads file content
   - Displays in terminal via zDisplay
   - Truncates if content > 1000 characters
   - Shows truncation notice
3. Returns "zBack" (success with fallback)

**Fallback Features:**
- Reads up to 1000 characters
- Shows truncation notice if needed
- Uses zDisplay for formatted output
- Handles encoding errors gracefully
- Logs fallback action

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zOpen_Demo/lvl2_interactive/3_content_fallback.py
```

[View demo source →](../../Demos/Layer_2/zOpen_Demo/lvl2_interactive/3_content_fallback.py)

**What you'll discover:**
- Automatic fallback to content display
- Truncation for large files
- Clean terminal formatting
- Graceful error handling
- Never crashes on IDE failure

---

# **zOpen - Level 3** (Hook Integration)

### **i. Success Hooks**

Execute custom code when opening succeeds using `onSuccess` hooks. Hooks are executed via zFunc subsystem.

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "success-hook",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Open with success callback
result = z.open.handle({
    "zOpen": {
        "path": "/path/to/file.txt",
        "onSuccess": "log_success()"
    }
})

# Custom success handler (registered in zFunc)
def log_success():
    print("✅ File opened successfully!")
    # Log to database, send notification, etc.
```

**Hook Execution:**
1. File opens successfully
2. zOpen detects `onSuccess` hook
3. Passes hook to zFunc for execution
4. Returns hook result to caller

**Use Cases:**
- Logging successful opens
- Tracking file access
- Sending notifications
- Incrementing counters
- Recording analytics

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zOpen_Demo/lvl3_hooks/1_success_hook.py
```

[View demo source →](../../Demos/Layer_2/zOpen_Demo/lvl3_hooks/1_success_hook.py)

**What you'll discover:**
- Register success callbacks
- Execute via zFunc
- Access to full zOS context
- Clean hook registration
- Flexible callback patterns

---

### **ii. Failure Hooks**

Execute custom code when opening fails using `onFail` hooks.

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "fail-hook",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Open with failure callback
result = z.open.handle({
    "zOpen": {
        "path": "/path/to/missing.txt",
        "onFail": "log_error()"
    }
})

# Custom failure handler
def log_error():
    print("❌ Failed to open file")
    # Send error notification, log to Sentry, etc.
```

**Hook Execution:**
1. File opening fails (missing, permissions, etc.)
2. zOpen detects `onFail` hook
3. Passes hook to zFunc for execution
4. Returns hook result to caller

**Use Cases:**
- Error logging and tracking
- Alerting administrators
- Recording failed access attempts
- Fallback actions (create file, notify user)
- Error analytics

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zOpen_Demo/lvl3_hooks/2_fail_hook.py
```

[View demo source →](../../Demos/Layer_2/zOpen_Demo/lvl3_hooks/2_fail_hook.py)

**What you'll discover:**
- Register failure callbacks
- Execute via zFunc
- Handle errors declaratively
- Clean error handling
- Flexible failure patterns

---

### **iii. Combined Hooks**

Use both `onSuccess` and `onFail` hooks for complete lifecycle handling.

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "combined-hooks",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Open with both callbacks
result = z.open.handle({
    "zOpen": {
        "path": "/path/to/file.txt",
        "onSuccess": "track_success()",
        "onFail": "track_failure()"
    }
})

# Complete lifecycle tracking
def track_success():
    print("✅ Successfully opened file")
    # Log success, update stats

def track_failure():
    print("❌ Failed to open file")
    # Log error, send alert
```

**Use Cases:**
- Complete audit trails
- Analytics tracking (success/failure rates)
- User behavior tracking
- System monitoring
- Declarative error handling

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zOpen_Demo/lvl3_hooks/3_combined_hooks.py
```

[View demo source →](../../Demos/Layer_2/zOpen_Demo/lvl3_hooks/3_combined_hooks.py)

**What you'll discover:**
- Register both hooks simultaneously
- Complete lifecycle coverage
- Declarative success/failure handling
- Clean separation of concerns
- Production-ready patterns

---

# **zOpen - Level 4** (Use Case)

### **Documentation Viewer - Real-World Application**

Let's build a practical documentation viewer that opens different file types correctly.

```python
from zOS import zOS

z = zOS({
    "deployment": "Production",
    "title": "doc-viewer",
    "logger": "INFO",
    "logger_path": "./logs",
})

# Documentation files
docs = [
    "@.README.md",           # Workspace README
    "@.docs.api.md",         # API documentation
    "@.docs.guide.html",     # HTML guide
    "https://docs.example.com",  # Online docs
]

# Open each document
for doc in docs:
    print(f"Opening: {doc}")
    result = z.open.handle(f"zOpen({doc})")
    
    if result == "zBack":
        print("✅ Opened successfully\n")
    else:
        print("❌ Failed to open\n")
```

**What it demonstrates:**
- Mixed content types (Markdown, HTML, URLs)
- zPath notation for workspace files
- Automatic routing to correct application
- Error handling for each open
- Real-world documentation workflow

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_2/zOpen_Demo/lvl4_usecase/1_doc_viewer.py
```

[View demo source →](../../Demos/Layer_2/zOpen_Demo/lvl4_usecase/1_doc_viewer.py)

**What you'll discover:**
- Handle multiple file types
- Mix local files and URLs
- Use zPath for portability
- Track success/failure
- Production-ready patterns

---

**🎯 Level 4 Complete!**

You've completed the entire zOpen tutorial journey:
- ✅ **Level 1**: Basic file and URL opening
- ✅ **Level 2**: Interactive features (file creation, IDE selection, fallbacks)
- ✅ **Level 3**: Hook integration (onSuccess, onFail)
- ✅ **Level 4**: Real-world application (documentation viewer)

**You now understand the complete zOpen subsystem for file and URL opening!**

---

## Advanced Features

### Supported File Types

zOpen currently supports:

**HTML Files:**
- Extensions: .html, .htm
- Opens in: Browser (preferred or default)
- Fallback: Displays URL info

**Text Files:**
- Extensions: .txt, .md, .py, .js, .json, .yaml, .yml
- Opens in: IDE (configured or selected)
- Fallback: Displays content in terminal

**URLs:**
- Patterns: http://, https://, www.*
- Opens in: Browser (preferred or default)
- Fallback: Displays URL info

**Media (via dedicated methods, not `handle()`):**
- `open_image(src)` — local image → system viewer; URL/served `/static` path → browser
- `open_video(src)` — local video → detected player
- `open_audio(src)` — local audio → detected player
- Players/viewers are **detector-resolved** from `zMachine`; an unresolved one fails closed (`stop`)

---

### zPath Notation

**Workspace-Relative (@):**
```python
# Current workspace: /Users/alice/projects/myapp

"@.README.md"              → /Users/alice/projects/myapp/README.md
"@.docs.setup.md"          → /Users/alice/projects/myapp/docs/setup.md
"@.src.app.py"             → /Users/alice/projects/myapp/src/app.py
```

**Absolute Paths (~):**
```python
# Root filesystem
"~.Users.alice.notes.txt"  → /Users/alice/notes.txt
"~.etc.config.yaml"        → /etc/config.yaml
"~.tmp.test.log"           → /tmp/test.log
```

**Validation:**
- Must start with @ or ~
- Must have at least 2 parts (symbol + name)
- Uses . as separator
- Clear error messages for invalid paths

---

### Return Values

zOpen methods return string codes:

| Return Value | Meaning | When |
|--------------|---------|------|
| `"zBack"` | Success | File/URL opened successfully |
| `"stop"` | Failure | Opening failed or user cancelled |
| Hook result | Custom | onSuccess/onFail hook executed |

**Usage:**
```python
result = z.open.handle("zOpen(/path/to/file.txt)")

if result == "zBack":
    print("Success!")
elif result == "stop":
    print("Failed or cancelled")
else:
    print(f"Hook returned: {result}")
```

---

### Facade API Reference

The `zOpen` class provides these methods:

**Main Interface:**
```python
# Handle opening request (string or dict)
result = z.open.handle("zOpen(/path/to/file.txt)")
result = z.open.handle("zOpen(https://example.com)")
result = z.open.handle("zOpen(@.README.md)")

# With hooks
result = z.open.handle({
    "zOpen": {
        "path": "/path/to/file.txt",
        "onSuccess": "success_handler()",
        "onFail": "error_handler()"
    }
})
```

**Request Formats:**

String format:
```python
"zOpen(/path/to/file)"
"zOpen(https://url.com)"
"zOpen(@.workspace.file)"
```

Dictionary format:
```python
{
    "zOpen": {
        "path": "/path/to/file",
        "onSuccess": "callback()",  # Optional
        "onFail": "error_callback()"  # Optional
    }
}
```

**Media Methods:**
```python
# Dedicated openers (separate from handle()); each is gated to zCLI mode
z.open.open_image("logo.png")                  # local → system viewer
z.open.open_image("https://example.com/x.png") # URL → browser
z.open.open_image("/static/brand/logo.png")    # served path → browser (via zServer)
z.open.open_video("clip.mp4")                  # local → detected video player
z.open.open_audio("song.mp3")                  # local → detected audio player
```

> All methods return `"zBack"`/`"stop"`. They perform **local-machine** actions and therefore fail closed outside zCLI mode (see [Security & Trust](#security--trust)).

---

### Module Structure

zOpen follows a 3-tier modular architecture:

**Core Modules:**
- `zOpen.py` - Main facade class (Tier 2)
- `__init__.py` - Package exports (Tier 3)

**Foundation Modules (Tier 1):**
- `open_paths.py` - zPath resolution (@ and ~ symbols)
- `open_urls.py` - URL opening in browsers
- `open_files.py` - File opening by extension + IDE launch
- `open_constants.py` - Shared constants and configuration
- `open_trust.py` - Path-trust gate (zGuard seam; permissive in open-core)

**Architecture Pattern:**
zOpen uses the **Facade pattern** - a unified interface delegates to specialized handlers:
- `z.open.handle()` → Request parsing and routing
- → `resolve_zpath()` → Path resolution
- → `open_url()` → URL opening
- → `open_file()` → File opening
- → `z.func.handle()` → Hook execution

This separation allows each handler to be tested and evolved independently while maintaining a stable public API.

---

## Integration with zOS

### Dependencies

zOpen requires these subsystems:

**Required:**
- `zConfig` - Session access (workspace, IDE, browser preferences)
- `zDisplay` - Mode-agnostic output and status messages
- `zFunc` - Hook callback execution (onSuccess/onFail)
- `zDialog` - Interactive prompts (file creation, IDE selection)

**Used By:**
- `zDispatch` - Command routing (detects zOpen() commands)
- `zWalker` - Navigation context (open files from menus)
- User applications - Direct handle() calls

### zDispatch Integration

zOpen is invoked from zDispatch when `zOpen()` commands are detected:

```python
# In zDispatch command parsing
if zHorizontal.startswith("zOpen("):
    return self.zos.open.handle(zHorizontal)
```

This allows declarative opening from any context:
- Walker navigation
- Dialog buttons
- Custom commands
- API responses

---

## Layer 2 Design Philosophy

As a **Layer 2 subsystem**, zOpen has specific design considerations:

**Depends On:**
- Layer 0: zConfig (configuration), zComm (optional for future extensions)
- Layer 1: zDisplay (output), zAuth (optional), zDispatch (routing)
- Layer 2: zFunc (hooks), zDialog (prompts)

**Provides For:**
- Layer 3: zWalker (navigation), zData (file access), zShell (command execution)
- User applications: Direct opening operations

**Design Principles:**
- Local-first, fail-closed off the terminal: every zOpen action runs on the local machine, so it is enabled in **zCLI** mode and **disabled (fail-closed)** in zBifrost/Web (see Security & Trust)
- Type detection: Automatic URL vs file vs zPath identification
- Interactive fallbacks: Never crashes, always provides alternatives
- Hook support: Declarative success/failure handling
- Session integration: Uses workspace and machine preferences

---

## Security & Trust

zOpen acts only on the **local machine** — it reads/displays local files, launches local IDEs/viewers/players via `subprocess`, and opens URLs in the *server's* webbrowser. Two open-core gates keep that safe (both work with **zGuard absent**):

**1. Mode gate (fail-closed off zCLI).** Because foreign content can reach this surface implicitly (a served `.zolo` containing `zOpen(~.Users.you.secret.txt)`), every public entry (`handle`, `open_image`, `open_video`, `open_audio`) first calls `_local_mode_allowed()`. Outside `zCLI` mode it returns `stop` and performs no action — so a remote Bifrost client can neither disclose server files nor trigger server-side app launches. This is the open-core baseline; any richer client-side open policy is owned by the zGuard-sealed network runtime.

**2. Path-trust seam.** Before any read/launch, `open_file()` and `_launch_media_player()` call `verify_path_trust(path, zos, logger)` (from `open_modules/open_trust.py`). This is the single door for path access. With **zGuard installed** it enforces the same sealed policy as zParser (workspace containment, allowed roots, `..` rejection) and raises `PathTrustError` (propagated unwrapped) on denial. **Without zGuard** the gate is permissive — open-core resolves any path the operator's workspace points at. *Mechanism is sealed by zGuard — contact admin / `z patch`.*

**Command execution is allowlisted.** IDE/viewer/player launches use list-form `subprocess` (no shell) and only run **detector-resolved** commands (`get_*_launch_command`, which allowlists + `shutil.which`-validates). An unknown editor no longer execs a raw binary name — it degrades to safe content display (Windows uses the OS default handler). Workspace config is trusted (Flask/direnv model); see `TRUST_MODEL` §7b.

---

## What's Next?

You've mastered **zOpen** (Layer 2 file and URL opening). Continue to the next Layer 2 subsystem:

**→ Continue to [zWizard Guide](../L3_Abstraction/zWizard_GUIDE.md)**

Layer 2 continues with:
- **zWizard** - Multi-step workflows and guided processes
- **zData** - Data operations and transformations
- **zShell** - Command-line interface and shell integration

> **Note:** For advanced file operations (parsing, loading, transforming), see [zParser Guide](zParser_GUIDE.md) and [zLoader Guide](../L1_Foundation/zLoader_GUIDE.md).

---

**[← Back to zDialog Guide](zDialog_GUIDE.md) | [Home](../../README.md) | [Next: zWizard Guide →](../L3_Abstraction/zWizard_GUIDE.md)**
