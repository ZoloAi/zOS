# zOpen Files Module Guide

> **Module:** `zOS/core/L2_Handling/k_zOpen/open_modules/open_files.py`  
> **Purpose:** Local file opening based on extension with IDE/browser routing and interactive fallbacks.

---

## Overview

The `files` module handles opening local files by detecting their extension and routing to the appropriate application. It provides interactive prompts for missing files and IDE selection, with content display fallbacks.

---

## Supported File Types

### HTML Files

**Extensions:** `.html`, `.htm`

**Opens in:** Browser (preferred or default)

**Examples:**
```python
# Open HTML documentation
z.open.handle("zOpen(/path/to/docs.html)")

# Open local web page
z.open.handle("zOpen(./index.htm)")

# Open workspace HTML
z.open.handle("zOpen(@.build.index.html)")
```

**Opening Process:**
1. Detects .html or .htm extension
2. Creates file:// URL
3. Opens in browser (preferred or default)
4. Falls back to URL info display if browser fails

### Text Files

**Extensions:** `.txt`, `.md`, `.py`, `.js`, `.json`, `.yaml`, `.yml`

**Opens in:** IDE (configured or selected)

**Examples:**
```python
# Open Python file
z.open.handle("zOpen(/path/to/script.py)")

# Open Markdown documentation
z.open.handle("zOpen(./README.md)")

# Open JSON config
z.open.handle("zOpen(./config.json)")

# Open YAML file
z.open.handle("zOpen(@.settings.yaml)")
```

**Opening Process:**
1. Detects text extension
2. Gets IDE from zMachine or prompts user
3. Opens file in IDE
4. Falls back to content display if IDE fails

---

## API Reference

### `open_file(path, session, display, dialog, logger, zos=None)`

Opens a local file based on its extension.

**Parameters:**
- `path` (str): Absolute filesystem path to open
- `session` (dict): zOS session containing IDE preferences
- `display` (zDisplay): Display instance for output
- `dialog` (zDialog): Dialog instance for prompts (may be `None`)
- `logger` (Logger): Logger for debug output
- `zos` (Any, optional): Main zOS instance, threaded to the **path-trust seam** for workspace context (`None` on the open-core permissive path)

**Returns:**
- `str`: "zBack" on success, "stop" on failure/cancellation

**Raises:**
- `PathTrustError`: when zGuard's sealed path-trust policy denies the path (never raised in open-core; propagated unwrapped)

**Examples:**
```python
from zOS.L2_Handling.k_zOpen.open_modules import open_file

# Open text file
result = open_file("/path/to/notes.txt", session, display, dialog, logger, zos)
# Returns: "zBack" (opened in IDE, or content display fallback)

# Open HTML file
result = open_file("/abs/index.html", session, display, None, logger, zos)
# Returns: "zBack" (opened in browser)

# Open non-existent file (prompts for creation)
result = open_file("/abs/new.txt", session, display, dialog, logger, zos)
# Returns: "zBack" if created and opened, "stop" if cancelled
```

**Opening Flow:**
1. **Path-trust gate** — `verify_path_trust(path, zos, logger)` runs first (permissive in open-core; raises `PathTrustError` if zGuard denies)
2. If the file exists, display file info JSON (`path`/`exists`/`size`/`type`)
3. If it doesn't exist:
   - With a dialog → prompt `Create file` / `Cancel`; create empty file & continue, or return "stop"
   - Without a dialog → return "stop"
4. Detect extension via `os.path.splitext(path.lower())`:
   - `.html`/`.htm` → `_open_html()` → browser
   - text extensions → `_open_text()` → IDE (or content fallback)
   - other → unsupported message → "stop"
5. Return "zBack" on success, "stop" on failure

---

## File Type Detection

### HTML Files

```python
# Extensions
EXTENSIONS_HTML = ('.html', '.htm')

# Detection
_, ext = os.path.splitext(path.lower())
if ext in EXTENSIONS_HTML:
    return _open_html(path, display, logger)
```

**HTML Opening Process (`_open_html`):**
1. Build `f"file://{path}"`
2. `webbrowser.open(url)` (system default browser)
3. Success → "Opened {filename} in browser"; failure → error message + "stop"

### Text Files

```python
# Extensions
EXTENSIONS_TEXT = ('.txt', '.md', '.py', '.js', '.json', '.yaml', '.yml')

# Detection
if ext in EXTENSIONS_TEXT:
    return _open_text(path, session, display, dialog, logger)
```

**Text Opening Process (`_open_text`):**
1. Resolve IDE: `session["ide"]` → `session["zMachine"]["ide"]` → default `nano`
2. If IDE is `"unknown"` and a dialog exists → prompt from `_AVAILABLE_IDES`
3. Resolve a **validated** launch command via `get_ide_launch_command(editor)`
4. If resolved → `subprocess.run([cmd, *args, path], check=False, timeout=10)`; else → content display (no raw exec)

### Unsupported Files

```python
# Extension not in EXTENSIONS_HTML or EXTENSIONS_TEXT
display.zDeclare(_MSG_UNSUPPORTED_TYPE.format(ext=ext), color=COLOR_ERROR, ...)
return RETURN_STOP
```

---

## Interactive Features

### File Creation Prompt

When file doesn't exist, prompts user:

```python
# File not found
→ zDialog prompt:
   "File not found: /path/to/file.txt"
   Options:
     - Create file
     - Cancel

# User selects "Create file"
→ Create empty file
→ Open in IDE
→ Return "zBack"

# User selects "Cancel"
→ Return "stop"
```

**zDialog Integration:**
```python
result = dialog.handle({
    "zDialog": {
        "model": None,
        "fields": [{"name": "action", "type": "enum", "options": _FILE_ACTIONS}],
    }
})

if result.get("action") == _FILE_ACTION_CREATE:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding=_FILE_ENCODING) as f:
        f.write("")
    # Continue opening the newly created file
else:
    return RETURN_STOP
```

### IDE Selection Prompt

When the configured IDE is `"unknown"` (and a dialog is available), prompts the user:

```python
# editor == "unknown"
→ zDialog prompt (options = _AVAILABLE_IDES):
     - cursor
     - code
     - nano
     - vim

# User selects IDE (falls back to nano if the dialog fails)
→ Launch only if get_ide_launch_command() resolves it; else content display
```

**zDialog Integration:**
```python
result = dialog.handle({
    "zDialog": {
        "model": None,
        "fields": [{"name": "ide", "type": "enum", "options": _AVAILABLE_IDES}],
    }
})
editor = result.get("ide", _DEFAULT_IDE)  # "nano" fallback
```

> The IDE prompt does **not** itself persist the choice — it is used for this open. The detector (`get_ide_launch_command`) decides whether `editor` resolves to a real, validated command.

---

## IDE Support

### How an editor becomes a command

zOpen does **not** hardcode `ide → command`. It asks `zConfig`'s platform detector
`get_ide_launch_command(editor)`, which returns `(cmd, args)` only for editors it can
**resolve and validate** (via `shutil.which` / macOS `open -a`). The prompt offers
`_AVAILABLE_IDES` = `cursor`, `code`, `nano`, `vim`; the detector additionally
resolves common editors like `subl`/`sublime`, `webstorm`, `pycharm`, `idea`, `fleet`,
`zed`, `nvim`, `vi`, `emacs`, `atom`, `xed`.

### IDE Command Execution (security-hardened)

```python
cmd, args = get_ide_launch_command(editor)

if cmd:
    # Detector-resolved (allowlisted + which()-validated upstream)
    subprocess.run([cmd, *args, path], check=False, timeout=10)
elif os.name == "nt":
    # Windows: hand off to OS default handler (no arbitrary binary exec)
    os.startfile(path)            # falls back to content display if unavailable
else:
    # V2 hardening: editor not resolved → never exec a raw binary name
    return _display_file_content(path, display, logger)
```

**Error Handling / fallbacks (all degrade to content display, returning "zBack"):**
- Editor not resolved by the detector allowlist → content display (V2 hardening)
- IDE launch raises / not installed / permission denied → content display
- Subprocess hangs → bounded by `timeout=10`

### Default IDE

If no IDE is configured (or the selection dialog fails), `editor` defaults to `nano`.

---

## Content Display Fallback

If IDE opening fails, displays file content in terminal:

```python
# IDE failed
→ Read file content
→ Display via zDisplay
→ Truncate if > 1000 characters
→ Show truncation notice
→ Return "zBack" (success with fallback)
```

**Display Format:**
```
════════════════════════════════════
File Content: notes.txt
════════════════════════════════════
[file content here]

[Content truncated - showing first 1000 of 5000 characters]
════════════════════════════════════
```

**Truncation:**
- Limit: 1000 characters
- Shows truncation notice if exceeded
- Displays total character count

**zDisplay Integration (`_display_file_content`):**
```python
display.zDeclare(_MSG_FILE_CONTENT_TITLE.format(filename=os.path.basename(path)),
                 color=COLOR_INFO, indent=_INDENT_FILE_INFO, style=_STYLE_SECTION)

with open(path, "r", encoding=_FILE_ENCODING) as f:
    content = f.read()

if len(content) > _CONTENT_TRUNCATE_LIMIT:           # 1000
    display.write_block(content[:_CONTENT_TRUNCATE_LIMIT] + "...")
    display.write_line(_MSG_CONTENT_TRUNCATED.format(
        limit=_CONTENT_TRUNCATE_LIMIT, total=len(content)))
else:
    display.write_block(content)

return RETURN_ZBACK   # read failure → logs _ERR_READ_FAILED, returns "stop"
```

---

## HTML File Opening

### file:// URL Creation

```python
# Build a file:// URL (string concatenation, not Path.as_uri())
url = f"file://{path}"
# /path/to/page.html → file:///path/to/page.html
```

### Browser Opening

`_open_html` uses `webbrowser.open(url)` (system default). For full browser-preference
handling, see [open_urls_GUIDE.md](open_urls_GUIDE.md).

**Success Messages:**
```python
# Opened in browser
display.print_message(
    f"Opened {path.name} in browser",
    color="SUCCESS"
)
```

---

## Error Handling

### File Not Found

```python
if not path.exists():
    # Prompt for creation via zDialog
    # If cancelled: return "stop"
    # If created: continue opening
```

### Unsupported Extension

```python
if ext not in (EXTENSIONS_HTML + EXTENSIONS_TEXT):
    display.print_message(
        f"Unsupported file type: {ext}",
        color="ERROR"
    )
    return "stop"
```

### IDE Opening Failed

```python
try:
    cmd, args = get_ide_launch_command(editor)
    subprocess.run([cmd, *args, path], check=False, timeout=10)
except Exception as e:
    logger.warning(_ERR_IDE_FAILED, editor, e)
    # Fall back to content display
    return _display_file_content(path, display, logger)  # returns "zBack"
```

### File Read Failed

```python
try:
    content = path.read_text(encoding='utf-8')
except Exception as e:
    logger.error(f"Failed to read file: {e}")
    display.print_message(
        f"Failed to read file: {e}",
        color="ERROR"
    )
    return "stop"
```

---

## Integration with zOpen

File opening is called automatically by zOpen:

```python
# From zOpen.handle()
result = z.open.handle("zOpen(/path/to/file.txt)")

# Internal flow:
# 1. Detect local path (not URL, not zPath)
# 2. Call open_file(path, session, display, dialog, logger, zos)
# 3. Path-trust gate → verify_path_trust(path, zos, logger)
# 4. Detect extension → route to _open_html / _open_text
# 5. Open or display content
# 6. Return result
```

**No manual calls needed** - zOpen detects file paths and routes automatically. The
`handle()` facade also enforces a **fail-closed mode gate** (zCLI only) before reaching
`open_file` — see the main guide's *Security & Trust* section.

---

## Constants Reference

From `open_constants.py`:

```python
# File extensions
EXTENSIONS_HTML = ('.html', '.htm')
EXTENSIONS_TEXT = ('.txt', '.md', '.py', '.js', '.json', '.yaml', '.yml')

# IDE configuration
_DEFAULT_IDE = "nano"
_IDE_UNKNOWN = "unknown"
_AVAILABLE_IDES = ["cursor", "code", "nano", "vim"]

# File actions
_FILE_ACTION_CREATE = "Create file"
_FILE_ACTION_CANCEL = "Cancel"
_FILE_ACTIONS = [_FILE_ACTION_CREATE, _FILE_ACTION_CANCEL]

# Content truncation
_CONTENT_TRUNCATE_LIMIT = 1000  # Characters
_FILE_ENCODING = 'utf-8'

# Messages
_MSG_CREATED_FILE = "Created {path}"
_MSG_OPENED_BROWSER = "Opened {filename} in browser"
_MSG_OPENED_IDE = "Opened {filename} in {ide}"
_MSG_FILE_CONTENT_TITLE = "File Content: {filename}"
_MSG_CONTENT_TRUNCATED = "[Content truncated - showing first {limit} of {total} characters]"
_MSG_UNSUPPORTED_TYPE = "Unsupported file type: {ext}"

# Errors
_ERR_FILE_NOT_FOUND = "File not found: %s"
_ERR_IDE_FAILED = "Failed to open with IDE %s: %s"
_ERR_READ_FAILED = "Failed to read file: %s"
```

---

## Logging

The module logs at different levels:

**DEBUG:**
- `"Resolved path: /path/to/file.txt"`
- `"Opening text file: /path/to/file.txt"`
- `"Using IDE: cursor"`

**INFO:**
- `"Successfully opened file with cursor"`
- `"Created file: /path/to/new.txt"`

**ERROR:**
- `"File not found: /path/to/file.txt"`
- `"Failed to open with cursor: <error>"`
- `"Failed to read file: <error>"`

**Usage:**
```python
# Enable debug logging
z = zOS({
    "logger": "DEBUG",
    "logger_path": "./logs",
})

# See file opening in logs
result = z.open.handle("zOpen(/path/to/file.txt)")
```

---

## Common Patterns

### Opening Source Code

```python
# Python files
z.open.handle("zOpen(@.src.app.py)")
z.open.handle("zOpen(@.tests.test_app.py)")

# JavaScript files
z.open.handle("zOpen(@.src.components.button.js)")

# TypeScript files (need to add .ts to EXTENSIONS_TEXT)
z.open.handle("zOpen(@.src.app.ts)")
```

### Opening Documentation

```python
# Markdown files
z.open.handle("zOpen(@.README.md)")
z.open.handle("zOpen(@.docs.api.md)")

# HTML documentation
z.open.handle("zOpen(@.build.docs.html)")
```

### Opening Configuration

```python
# JSON config
z.open.handle("zOpen(@.package.json)")
z.open.handle("zOpen(@.tsconfig.json)")

# YAML config
z.open.handle("zOpen(@.config.yaml)")
z.open.handle("zOpen(@..github.workflows.ci.yml)")
```

### Creating New Files

```python
# Try to open non-existent file
z.open.handle("zOpen(@.new_feature.py)")

# Prompts:
# "File not found: /workspace/new_feature.py"
# Options: Create file | Cancel

# Select "Create file"
# → Creates empty file
# → Opens in IDE
# → Ready to start coding
```

---

## Best Practices

### When to Use File Opening

Use for:
- Source code files (.py, .js, .ts)
- Documentation files (.md, .txt)
- Configuration files (.json, .yaml)
- HTML documentation (.html)
- Any text-based files

### When NOT to Use

Don't use for:
- Binary files (images, videos, PDFs)
- Large files (> 100MB)
- Remote URLs (use URL opening)
- Directories (not supported)

### IDE Configuration

**Set preferred IDE:**
```python
# Via zMachine config
z.config.persistence.persist_machine("ide", "cursor")

# Via zSpark
z = zOS({"ide": "code"})

# Via environment
# ZOLO_IDE=nano
```

**IDE priority:**
1. zSpark override (highest)
2. zMachine configuration
3. Interactive selection prompt
4. Default (nano)

### File Creation

Always handle file creation prompts:
```python
# User might cancel
result = z.open.handle("zOpen(@.new_file.txt)")

if result == "stop":
    print("User cancelled file creation")
else:
    print("File created and opened")
```

---

## Future Extensions

The modular architecture supports easy addition of new file types:

**Documents:**
- PDF: Open in default PDF viewer
- Word/Excel: Open in appropriate app
- PowerPoint: Open in presentation app

**Images:**
- PNG, JPG: Open in image viewer
- SVG: Open in browser or editor
- With Bifrost: Display inline

**Archives:**
- ZIP, TAR: Extract or open in file manager
- GZ: Decompress and open contents

**Media (already shipped, via dedicated facade methods — not `open_file`):**
- Images: `z.open.open_image(src)` (local → viewer; URL/`/static` → browser)
- Video: `z.open.open_video(src)` (detected player)
- Audio: `z.open.open_audio(src)` (detected player)

**To add a new file type to `open_file`:**
1. Update EXTENSIONS_* tuples in open_constants.py (compose from `zVocabulary` atoms)
2. Add handler function in open_files.py
3. Update routing logic in open_file()
4. Document in this guide

---

**[← Back to zOpen Guide](../zOpen_GUIDE.md)**
