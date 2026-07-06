# zOpen URLs Module Guide

> **Module:** `zOS/core/L2_Handling/k_zOpen/open_modules/open_urls.py`  
> **Purpose:** URL opening in user's preferred or system default browser.

---

## Overview

The `urls` module handles opening HTTP/HTTPS URLs in browsers. It automatically detects URL patterns, adds missing protocols, and uses browser preferences from zMachine configuration.

---

## Supported URL Patterns

### HTTP URLs

```python
# Plain HTTP
z.open.handle("zOpen(http://example.com)")

# HTTP with path
z.open.handle("zOpen(http://example.com/page)")

# HTTP with query params
z.open.handle("zOpen(http://example.com/search?q=test)")
```

### HTTPS URLs

```python
# Plain HTTPS
z.open.handle("zOpen(https://example.com)")

# HTTPS with subdomain
z.open.handle("zOpen(https://api.example.com)")

# HTTPS with path and params
z.open.handle("zOpen(https://github.com/user/repo?tab=readme)")
```

### WWW Prefix

```python
# Auto-adds https://
z.open.handle("zOpen(www.google.com)")
→ Opens: https://www.google.com

# With path
z.open.handle("zOpen(www.github.com/explore)")
→ Opens: https://www.github.com/explore
```

---

## API Reference

### `open_url(url, session, display, logger)`

Opens a URL in the user's browser.

**Parameters:**
- `url` (str): URL to open (http://, https://, or www.)
- `session` (dict): zOS session containing browser preferences
- `display` (zDisplay): Display instance for output messages
- `logger` (Logger): Logger for debug output

**Returns:**
- `str`: "zBack" on success; also "zBack" when all browsers fail but the URL is shown for manual copy-paste (graceful degradation)

**Examples:**
```python
from zOS.L2_Handling.k_zOpen.open_modules import open_url

# Open HTTPS URL
result = open_url("https://github.com", session, display, logger)
# Returns: "zBack"

# Open HTTP URL
result = open_url("http://example.com", session, display, logger)
# Returns: "zBack"
```

> `open_url` expects a **full URL with a scheme**. The `www.` → `https://` prepend
> happens earlier in `zOpen.handle()` (the facade) before `open_url` is called.

**Opening Process:**
1. Display URL info JSON (`url`/`scheme`/`domain`/`path`) via `display.json_data()`
2. Resolve browser: `session["browser"]` → `session["zMachine"]["browser"]`
3. If a browser is set (and not in `_BROWSERS_SKIP`), resolve a launch command via `get_browser_launch_command()` and `subprocess.run([cmd, *args, url], timeout=5)`
4. Otherwise / on failure → `webbrowser.open(url)` (system default)
5. If that also fails → display URL info for manual copy-paste (graceful, returns "zBack")

---

## Browser Selection

### Preferred Browser

Browser preference comes from zMachine configuration:

```python
# From session
browser = session.get("browser")  # "chrome", "firefox", "safari", etc.

# Example flow:
# 1. Check session["browser"]
# 2. Try to open in that browser
# 3. If fails, try default browser
# 4. If both fail, show URL info
```

**Supported browsers** are whatever `zConfig`'s `get_browser_launch_command()` can
resolve on the platform (e.g. chrome, firefox, brave, arc, opera, edge). A browser the
detector can't resolve, or one in `_BROWSERS_SKIP` (`"unknown"`), is skipped in favor of
the system default (`webbrowser.open`).

### Default Browser

If preferred browser fails, falls back to system default:

```python
# Browser preference: "chrome"
# Chrome not installed or fails
→ Try system default browser
→ If that works: "zBack"
→ If that fails: Display URL info
```

**Default browser detection:**
- macOS: Uses open command
- Linux: Uses xdg-open
- Windows: Uses start command

### Unknown Browser

If browser is "unknown" or not recognized:

```python
# Session browser: "unknown"
→ Skip preferred browser
→ Try system default directly
→ If that fails: Display URL info
```

---

## URL Processing

### WWW Prefix Handling

URLs starting with www. automatically get https:// prepended:

```python
# Input: www.google.com
# Processed: https://www.google.com

# Input: www.github.com/explore
# Processed: https://www.github.com/explore
```

**Why https://?**
- Modern web standard
- Most sites require HTTPS
- Secure by default
- Browser automatically redirects if needed

### URL Validation

URLs are validated before opening:

```python
# Valid URLs
"http://example.com"          # ✓
"https://example.com"         # ✓
"www.example.com"             # ✓
"https://api.example.com/v1"  # ✓

# Invalid URLs (not handled by this module)
"example.com"                 # ✗ (no protocol or www)
"/path/to/file"               # ✗ (local path)
"@.README.md"                 # ✗ (zPath)
```

---

## Browser Opening Methods

### Preferred Browser

Uses the detector-resolved launch command + `subprocess` (not `webbrowser.get`):

```python
cmd, args = get_browser_launch_command(browser)   # zConfig detector
if cmd:
    subprocess.run([cmd, *args, url], check=False, timeout=5)
```

**Advantages:**
- Respects user preference
- Consistent with zMachine config
- Command is validated by the detector (no raw `webbrowser.get` registry lookup)

**Error Handling:**
- Unresolved browser (`cmd is None`) → fall through to system default
- Launch raises / times out (5s) → fall through to system default

### Default Browser

Uses `webbrowser.open(url)`:

```python
import webbrowser

# Opens in system default browser
webbrowser.open("https://example.com")
```

**Advantages:**
- Always available (fallback)
- Uses system preference
- No configuration needed

**Error Handling:**
- Catches all webbrowser errors
- Falls back to URL info display

---

## Fallback Display

If both browser methods fail, displays URL information:

```python
# Browser failed
→ Display URL info via zDisplay

# Output:
# ════════════════════════════════════
# URL Information
# ════════════════════════════════════
# Unable to open in browser. Please copy and paste into your browser:
# 
# https://example.com
# ════════════════════════════════════
```

**What's displayed:**
- Section header
- Helpful message
- Full URL (for copy/paste)
- Clean formatting via zDisplay

**User action:**
- Copy URL from terminal
- Paste into browser manually
- Graceful degradation (no crash)

---

## Success Messages

### Preferred Browser

```python
# Opened in configured browser
display.zDeclare(_MSG_OPENED_BROWSER_URL.format(browser=browser),
                 color=COLOR_SUCCESS, indent=_INDENT_URL_INFO, style=_STYLE_SINGLE)
```

### Default Browser

```python
# Opened in system default
display.zDeclare(_MSG_OPENED_DEFAULT,
                 color=COLOR_SUCCESS, indent=_INDENT_URL_INFO, style=_STYLE_SINGLE)
```

---

## Error Handling

### Browser Launch Errors

```python
try:
    subprocess.run([cmd, *args, url], check=False, timeout=5)
except Exception as e:
    logger.warning("Browser launch failed for %s: %s", browser, e)
    # → fall through to webbrowser.open(url)
    # → then URL info display
```

### Browser Not Resolved

```python
cmd, args = get_browser_launch_command(browser)
if not cmd:
    # Detector couldn't resolve the browser
    # → webbrowser.open(url) (system default)
    # → then URL info display
```

### All Methods Failed

```python
# Preferred browser failed
# Default browser failed
→ _display_url_fallback() shows the URL for manual copy-paste
→ Returns "zBack" (graceful degradation — the user still gets the URL)
```

---

## Integration with zOpen

URL opening is called automatically by zOpen:

```python
# From zOpen.handle()
result = z.open.handle("zOpen(https://example.com)")

# Internal flow:
# 1. Detect URL pattern (http/https/www)
# 2. Call open_url(url, session, display, logger)
# 3. Try preferred browser
# 4. Try default browser
# 5. Display URL info if both fail
# 6. Return result
```

**No manual calls needed** - zOpen detects URLs and routes automatically.

---

## Constants Reference

From `open_constants.py`:

```python
# URL schemes
URL_SCHEME_HTTP = "http"
URL_SCHEME_HTTPS = "https"
URL_SCHEMES_SUPPORTED = ("http", "https")
URL_PREFIX_WWW = "www."
URL_SCHEME_HTTPS_DEFAULT = "https://"

# Machine keys
ZMACHINE_KEY_BROWSER = "browser"

# Browser configuration
_BROWSERS_SKIP = ("unknown",)

# Messages
_MSG_OPENED_BROWSER_URL = "Opened URL in {browser}"
_MSG_OPENED_DEFAULT = "Opened URL in default browser"
_MSG_URL_INFO_TITLE = "URL Information"
_MSG_URL_MANUAL = "Unable to open in browser. Please copy and paste into your browser."

# Errors
_ERR_BROWSER_FAILED_URL = "Browser failed to open URL"
_ERR_BROWSER_ERROR = "Browser error: %s"
_ERR_URL_OPEN_FAILED = "Unable to open URL. Displaying information instead."
```

---

## Logging

The module logs at different levels:

**DEBUG:**
- `"Opening URL: https://example.com"`
- `"Using browser: chrome"`

**INFO:**
- `"Successfully opened URL in chrome"`
- `"Successfully opened URL in system default browser"`

**ERROR:**
- `"Browser failed to open URL"`
- `"Browser error: <error details>"`

**Usage:**
```python
# Enable debug logging
z = zOS({
    "logger": "DEBUG",
    "logger_path": "./logs",
})

# See URL opening in logs
result = z.open.handle("zOpen(https://github.com)")
```

---

## Common Patterns

### Opening Documentation

```python
# GitHub repository
z.open.handle("zOpen(https://github.com/user/repo)")

# API documentation
z.open.handle("zOpen(https://api.example.com/docs)")

# Package documentation
z.open.handle("zOpen(https://docs.python.org/3/)")
```

### Opening Web Apps

```python
# Gmail
z.open.handle("zOpen(https://mail.google.com)")

# GitHub Issues
z.open.handle("zOpen(https://github.com/user/repo/issues)")

# Slack workspace
z.open.handle("zOpen(https://workspace.slack.com)")
```

### Opening Search Results

```python
# Google search
z.open.handle("zOpen(https://google.com/search?q=python)")

# Stack Overflow
z.open.handle("zOpen(https://stackoverflow.com/questions)")

# GitHub search
z.open.handle("zOpen(https://github.com/search?q=zos)")
```

### Opening with WWW

```python
# Will auto-add https://
z.open.handle("zOpen(www.google.com)")
z.open.handle("zOpen(www.github.com)")
z.open.handle("zOpen(www.python.org)")
```

---

## Platform-Specific Behavior

### macOS

```python
# Uses 'open' command for default browser
# Supports all major browsers
# Clean integration with system preferences
```

### Linux

```python
# Uses 'xdg-open' command for default browser
# Supports all major browsers
# Respects BROWSER environment variable
```

### Windows

```python
# Uses 'start' command for default browser
# Supports all major browsers
# Integrated with Windows default apps
```

---

## Best Practices

### When to Use URL Opening

Use for:
- External documentation links
- Web applications
- API documentation
- Online resources
- GitHub repositories
- Stack Overflow questions

### When NOT to Use

Don't use for:
- Local files (use file opening)
- File:// URLs (use HTML file opening)
- zPath references (use path resolution)
- API calls (use zComm)

### Browser Configuration

**Set preferred browser:**
```python
# Via zMachine config
z.config.persistence.persist_machine("browser", "chrome")

# Via zSpark
z = zOS({"browser": "firefox"})

# Via environment
# ZOLO_BROWSER=safari
```

**Browser priority:**
1. zSpark override (highest)
2. zMachine configuration
3. System default browser (fallback)

---

**[← Back to zOpen Guide](../zOpen_GUIDE.md)**
