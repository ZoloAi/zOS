# zConfig Loggers Module Guide

> **Module:** `zOS/core/L1_Foundation/a_zConfig/zConfig_modules/loggers/`  
> **Purpose:** Three-tier logging system with framework, session framework, and application loggers.

---

## Overview

The `loggers` module implements a sophisticated three-tier logging architecture that separates concerns between framework internals, session execution traces, and user application code. Each tier has its own logger, log file, and purpose, providing complete transparency and control.

---

## Architecture

The loggers module consists of four main components:

| Component | File | Purpose |
|---|---|---|
| `LoggerConfig` | `logger_config.py` | Main facade (manages all three loggers) |
| `FrameworkLogger` | `framework_logger.py` | Global framework internals (session-agnostic) |
| `SessionFrameworkLogger` | `session_framework_logger.py` | Per-execution trace (bootstrap, flow) |
| `AppLogger` | `app_logger.py` | User application code |
| `AppLog` / `emit_app_log` | `app_emit.py` | App-level emit handle exposed as `zos.log` |

**Supporting modules:**
- `constants.py` - Logger constants and configuration keys
- `utils.py` - Shared utilities (path resolution, validation, formatting)
- `app_emit.py` - The `zos.log(...)` public surface + emit orchestrator (PROD bypass, zRaven capture, zBifrost broadcast). Re-homed here from the former `b_zApp` L1 tier so all logging lives in one subsystem (SSOT).

---

## Three-Tier Logging System

### Tier 1: Framework Logger

**Purpose:** Pure zOS framework internals (global, session-agnostic)

**File:** `zos-framework.log` (fixed path, shared across all sessions)

**Logger name:** `"zOS.framework"`

**Level:** Always DEBUG (for rare cases when used)

**Console:** Disabled in Production/Testing, ERROR+ in Development, respects logger level in Debug

**Use cases:**
- System-level errors (import failures, critical bugs)
- Framework implementation details (rarely used)
- Global framework concerns (NOT session-specific)

**Note:** Most logs should go to session_framework instead! This logger is MINIMAL.

---

### Tier 2: Session Framework Logger

**Purpose:** Complete execution trace for THIS session

**File:** `{session_title}.framework.log` (e.g., `my_script.framework.log`)

**Logger name:** `"zOS.session.framework"`

**Level:** DEBUG (captures everything for this session)

**Console:** WARNING+ in Development, respects logger level in Debug, disabled in Production/Testing

**Use cases:**
- Bootstrap logs (initialization sequence)
- Ready banners (zMachine Ready, zEnv Ready, etc.)
- SESSION logs (zSpark values, configuration)
- Framework execution flow (dispatch, navigation)

**This is the primary framework log** - contains complete audit trail for each execution.

---

### Tier 3: Application Logger

**Purpose:** User application code

**File:** `{session_title}.log` (e.g., `my_script.log`)

**Logger name:** `"zOS.app"`

**Level:** Configurable (default: INFO)

**Console:** Always enabled (respects level), disabled in PROD mode

**Path:** Customizable via zSpark `zLogPath`

**Use cases:**
- User application logs
- Business logic events
- Custom application messages

**This is what users primarily interact with** via `z.logger.info()`, `z.logger.debug()`, etc.

---

## App-Level Emit Handle (`zos.log`)

Beyond the configured `AppLogger`, the loggers subsystem exposes a small, ergonomic
**emit handle** for plugin / zApp developers, bound on the instance as `zos.log`.
It lives in `app_emit.py` (`AppLog` + `emit_app_log`) and was re-homed here from the
former `b_zApp` tier so that *all* logging is owned by one subsystem (SSOT).

`zos.log` is callable, with `.log` / `.event` aliases:

```python
@zfunc
def save_order(zos=None):
    zos.log("Order saved", tag="crm.orders")          # callable form
    zos.log.event("Email queued", tag="crm.mail")      # always INFO, PROD-safe
    zos.log("Low stock", level="WARNING", tag="crm")   # explicit level
    return True
```

**What the handle adds over `z.logger.*`:** it is an *emit orchestrator*, routing one
call across every transport so app logs behave correctly in any mode:

| Concern | Behavior |
|---|---|
| **PROD bypass** | When `zLog: PROD`, always prints to console even though framework logs are silenced |
| **Standard levels** | Otherwise routes through the configured app logger at the requested level |
| **zRaven capture** | If a capture buffer is active, appends instead of printing |
| **zBifrost mode** | Broadcasts an `app_log` WebSocket event (for live capture) |
| **CLI mode** | Emits a NUL-prefixed machine-readable line for the zRaven CLI runner |
| **File** | Honors `zLogPath` via the app logger |

**Arguments:** `zos.log(message, level="INFO", tag=None)` — `tag` is a dot-namespaced
prefix shown as `[tag] message`.

### Inside `@zfunc` plugins

Plugins can also receive the handle by declaring a `log` parameter (dependency
injection); it resolves to `zos.log` (falling back to the raw logger if unset):

```python
@zfunc
def process(log=None):
    log("processing started", tag="jobs")
```

> Use `zos.log(...)` for **app/business events** (the public, PROD-safe surface).
> Use `z.logger.*` for **framework/diagnostic** logging with semantic routing.

---

## `LoggerConfig`

Main facade for three-tier logging system. Manages all three loggers and provides unified API.

### Initialization

```python
from zConfig_modules.loggers import LoggerConfig

logger_config = LoggerConfig(
    environment_config=env_config,
    zos=zos_instance,
    session_data=session_dict,
    verbose=False
)
```

| Parameter | Type | Description |
|---|---|---|
| `environment_config` | `EnvironmentConfig` | Environment configuration instance |
| `zos` | `zOS` | zOS framework instance |
| `session_data` | `dict` | Session dictionary |
| `verbose` | `bool` | Show initialization output (default: False) |

**On init, automatically:**
1. Validates zOS instance and session_data
2. Gets log level from session (already processed hierarchy)
3. Initializes all three loggers (framework, session framework, app)
4. Prints ready message (if verbose or Development mode)
5. Logs ready message to session framework

---

### Properties

#### `logger` (property)

Get the application logger instance (user code).

```python
# Primary API surface (backward compatibility)
z.logger.info("Application message")
z.logger.debug("Debug message")
```

**Returns:** `logging.Logger` - The application logger instance

---

#### `framework` (property)

Get the pure framework logger (global, session-agnostic).

```python
# Rarely used - for system-level errors only
z.logger.framework.error("Import failed: %s", error)
```

**Returns:** `logging.Logger` - The pure framework logger instance

**Use sparingly** - most logs should go to `session_framework` instead.

---

#### `session_framework` (property)

Get the session framework logger (execution trace for THIS session).

```python
# Bootstrap and framework flow
z.logger.session_framework.info("zParser Ready")
z.logger.session_framework.session("Python %s on %s", version, platform)
```

**Returns:** `logging.Logger` - The session framework logger instance

---

### Methods

#### `set_level(level: str) -> None`

Set logger level dynamically.

```python
z.logger.set_level("DEBUG")
z.logger.set_level("WARNING")
```

**Args:**
- `level`: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)

**Note:** To control production behaviors (silent console, no banners), use deployment mode instead of log level.

---

#### `get_level() -> str`

Get current logger level.

```python
current_level = z.logger.get_level()
# "INFO"
```

**Returns:** Current log level string

---

#### `should_show_sysmsg() -> bool`

Check if system messages should be displayed based on deployment mode.

```python
if z.logger.should_show_sysmsg():
    print_ready_message("zParser Ready")
```

**Returns:** `True` if sysmsg should be shown (Development mode only)

**Behavior:**
- **Shown in:** Development deployment
- **Hidden in:** Testing, Production deployments

System messages are aesthetic "Ready" banners (visual indicators only, not logged to file).

---

## Logging Interface (Semantic Routing)

LoggerConfig provides a semantic logging interface that routes messages to appropriate loggers based on purpose:

### `debug(message, *args, **kwargs)`

**Routes to:** Framework logger ONLY

**File:** `zos-framework.log`

**Audience:** zOS framework developers debugging internals

**Use for:**
- Implementation details (path resolution, cache hits)
- Performance metrics for optimization
- Internal algorithm debugging
- Framework bug diagnosis

```python
z.logger.debug("zParser path resolution: @.UI → /Users/.../UI")
z.logger.debug("Cache hit: 3/5 files")
```

---

### `info(message, *args, **kwargs)`

**Routes to:** Session framework logger ONLY

**File:** `{session}.framework.log`

**Audience:** Users debugging their application flow

**Use for:**
- User-facing events (zParser Ready, subsystem loaded)
- High-level flow (loading zVaFile, processing request)
- Ready banners (zMachine, zEnv, zParser)
- Configuration summary (non-detailed)

```python
z.logger.info("zParser Ready")
z.logger.info("Loading zVaFile: @.UI.zProducts")
```

---

### `session(message, *args, **kwargs)`

**Routes to:** Session framework logger ONLY

**File:** `{session}.framework.log`

**Audience:** Users understanding session configuration and context

**Level:** SESSION (15) - between INFO (20) and DEBUG (10)

**Use for:**
- Session initialization details (Python version, OS)
- Configuration detection (zSpark values, deployment, mode)
- Environment setup (installation type, paths)
- Session-specific context (dry information)

```python
z.logger.session("Python %s on %s", version, platform)
z.logger.session("zSpark configuration loaded: %d keys", len(config))
z.logger.session("Deployment: %s, Mode: %s", deployment, mode)
```

---

### `warning(message, *args, **kwargs)`

**Routes to:** BOTH framework and session framework loggers

**Files:** `zos-framework.log` AND `{session}.framework.log`

**Audience:** Both developers (might be bug) and users (needs attention)

**Use for:**
- Potential issues (file not found, deprecated usage)
- Configuration problems (invalid setting, missing key)
- Non-critical failures (fallback used, retry succeeded)

```python
z.logger.warning("zVaFile not found: @.UI.Missing")
z.logger.warning("Deprecated usage: PROD log level")
```

---

### `error(message, *args, **kwargs)`

**Routes to:** BOTH framework and session framework loggers

**Files:** `zos-framework.log` AND `{session}.framework.log`

**Audience:** Both developers (framework bug?) and users (what failed?)

**Use for:**
- Critical failures (initialization failed, cannot proceed)
- Runtime errors (database connection failed, API error)
- System-level problems (permission denied, disk full)

```python
z.logger.error("zParser initialization failed: %s", error)
z.logger.error("Database connection failed")
```

---

### `critical(message, *args, **kwargs)`

**Routes to:** BOTH framework and session framework loggers

**Files:** `zos-framework.log` AND `{session}.framework.log`

**Audience:** Both developers (system failure) and users (cannot continue)

**Use for:**
- System-level failures (cannot load core subsystem)
- Unrecoverable errors (corruption detected, out of memory)
- Emergency shutdowns (data integrity at risk)

```python
z.logger.critical("Core subsystem failed to load")
z.logger.critical("Data corruption detected in config")
```

---

### `dev(message, *args, **kwargs)`

**Routes to:** Application logger (if not Production)

**File:** `{session}.log`

**Audience:** Developers (suppressed in Production)

**Use for:**
- Development diagnostics
- Internal debugging messages
- Messages that should not appear in production

```python
z.logger.dev("Cache hit rate: %d%%", 87)
z.logger.dev("Development diagnostic message")
```

**Behavior:** Suppressed in Production deployment, shown in Development/Testing.

---

### `user(message, *args, **kwargs)`

**Routes to:** Console (always) + Application logger

**File:** `{session}.log`

**Audience:** End users (shown in ALL modes including PROD)

**Use for:**
- Important application messages (always visible)
- User-facing status updates
- Critical information that should never be suppressed

```python
z.logger.user("Application started successfully")
z.logger.user("Processing %d records...", 1247)
```

**Behavior:** Always prints to console (even in PROD mode) and logs to file.

---

## Log Files

### Framework Log

**File:** `zos-framework.log`

**Location:** Fixed at `~/Library/Application Support/zOS/logs/` (or OS equivalent)

**Purpose:** Global framework internals (session-agnostic)

**Content:**
- System-level errors
- Import failures
- Critical framework bugs

**Shared across all sessions** - rarely used.

---

### Session Framework Log

**File:** `{session_title}.framework.log`

**Location:** Honors zSpark `zLogPath` (zOS #6) — the session trace lands next
to your app logs. Default (no `zLogPath`): `~/Library/Application Support/zOS/logs/`
(or OS equivalent)

**Purpose:** Complete execution trace for THIS session

**Content:**
- Bootstrap logs (initialization sequence)
- Ready banners (zMachine Ready, zEnv Ready, etc.)
- SESSION logs (zSpark values, configuration)
- Framework execution flow (dispatch, navigation)
- Warnings and errors (duplicated from framework log)

**One file per session** - complete audit trail.

---

### Application Log

**File:** `{session_title}.log`

**Location:** Customizable via zSpark `zLogPath` (default: system logs dir)

**Purpose:** User application code

**Content:**
- User application logs
- Business logic events
- Custom application messages

**One file per session** - user-controlled.

---

## Log Levels

### Standard Levels

| Level | Value | Description | Use Case |
|---|---|---|---|
| DEBUG | 10 | Detailed diagnostic information | Development debugging |
| SESSION | 15 | Session/environment information | Configuration context |
| INFO | 20 | General informational messages | Normal operation |
| WARNING | 30 | Warning messages | Potential issues |
| ERROR | 40 | Error messages | Failures |
| CRITICAL | 50 | Critical messages | System failures |

### Deprecated Levels

| Level | Replacement | Notes |
|---|---|---|
| PROD | INFO | Deprecated in v1.5.9 - use deployment mode instead |

**Migration:** Use `deployment: "Production"` (clean UI) + `logger: "INFO"` (reasonable logs)

---

## Logger Level Hierarchy

Logger level follows a 5-layer hierarchy (highest to lowest priority):

1. **zSpark override** - Explicit user choice
2. **Virtual environment variable** - `$ZOLO_LOGGER` (if in venv)
3. **System environment variable** - `$ZOLO_LOGGER`
4. **zConfig.environment.zolo** - `logging.app.level`
5. **Default** - "INFO"

**Example:**

```python
# zSpark override (highest priority)
zSpark = {"logger": "DEBUG"}
z = zOS(zSpark)

# Environment variable
export ZOLO_LOGGER=WARNING

# Config file (zConfig.environment.zolo)
logging:
  app:
    level: ERROR

# Default
# → logger: "INFO"
```

---

## Console vs File Output

### Console Output

**Deployment-aware behavior:**

| Deployment | Framework | Session Framework | Application |
|---|---|---|---|
| **Development** | ERROR+ | WARNING+ | Respects level |
| **Testing** | Disabled | Disabled | Respects level |
| **Production** | Disabled | Disabled | Disabled |
| **Debug** | Respects level | Respects level | Respects level |

### File Output

**Always enabled** for all three loggers (framework, session framework, application).

**File levels:**
- Framework: DEBUG (captures everything)
- Session Framework: DEBUG (captures everything)
- Application: Respects user's configured level

---

## Custom Logger Path

Custom log directory via the zSpark key **`zLogPath`** (the old `zScrapath`
alias is deprecated and warns):

```python
# Custom directory
zSpark = {"zLogPath": "./logs"}
z = zOS(zSpark)

# zPath notation (workspace-relative)
zSpark = {"zLogPath": "@.logs"}
z = zOS(zSpark)

# Home-relative
zSpark = {"zLogPath": "~/logs"}
z = zOS(zSpark)
```

**Supported notations:**
- `@.path` - Workspace-relative (zPath convention)
- `~/path` - Home-relative
- `./path` - Current directory relative
- `/path` - Absolute path

**Note:** `zLogPath` moves both the **application log** and the **session
framework trace** (zOS #6) — your app's complete execution story lives next to
your project, not lost in a system directory. Only the global
`zos-framework.log` stays in the system location.

---

## Practical Examples

### Example 1: Basic Logging

```python
from zOS import zOS

z = zOS()

# Application logs (user code)
z.logger.info("Application started")
z.logger.debug("Debug information")
z.logger.warning("Warning message")
z.logger.error("Error occurred")
```

---

### Example 2: Three-Tier Logging

```python
# Framework log (rare - system-level only)
z.logger.framework.error("Import failed: %s", error)

# Session framework log (bootstrap, flow)
z.logger.session_framework.info("zParser Ready")
z.logger.session_framework.session("Python %s", version)

# Application log (user code)
z.logger.info("Processing data...")
```

---

### Example 3: Semantic Routing

```python
# Routes to framework logger only
z.logger.debug("Cache hit: 3/5 files")

# Routes to session framework logger only
z.logger.info("Loading zVaFile: @.UI.zProducts")
z.logger.session("Deployment: Production, Mode: zCLI")

# Routes to BOTH framework and session framework
z.logger.warning("Deprecated usage detected")
z.logger.error("Database connection failed")
```

---

### Example 4: Custom Logger Path

```python
# Custom log directory
zSpark = {
    "title": "api_server",
    "logger": "DEBUG",
    "zLogPath": "./logs"
}
z = zOS(zSpark)

# Logs go to:
# - ./logs/api_server.log (application)
# - ./logs/api_server.framework.log (session framework trace — follows zLogPath, zOS #6)
# - ~/Library/.../zOS/logs/zos-framework.log (framework)
```

---

### Example 5: Development vs Production

```python
# Development mode
zSpark = {"deployment": "Development", "logger": "DEBUG"}
z = zOS(zSpark)
z.logger.info("This appears in console and file")
z.logger.debug("This also appears in console and file")

# Production mode
zSpark = {"deployment": "Production", "logger": "INFO"}
z = zOS(zSpark)
z.logger.info("This appears in file only (no console)")
z.logger.debug("This appears in file only (no console)")
```

---

### Example 6: User Messages (Always Visible)

```python
# Production mode
zSpark = {"deployment": "Production"}
z = zOS(zSpark)

# Regular logs (suppressed in console)
z.logger.info("This goes to file only")

# User messages (always visible)
z.logger.user("Application started successfully")  # Prints to console + file
z.logger.user("Processing %d records...", 1247)    # Prints to console + file
```

---

### Example 7: Development Diagnostics

```python
# Development mode
zSpark = {"deployment": "Development"}
z = zOS(zSpark)

# Development logs (shown in Development, hidden in Production)
z.logger.dev("Cache hit rate: %d%%", 87)
z.logger.dev("Development diagnostic message")

# Production mode
zSpark = {"deployment": "Production"}
z = zOS(zSpark)

# Development logs (suppressed)
z.logger.dev("This is hidden in Production")
```

---

### Example 8: Dynamic Level Change

```python
z = zOS()

# Check current level
print(f"Current level: {z.logger.get_level()}")  # "INFO"

# Change level dynamically
z.logger.set_level("DEBUG")
print(f"New level: {z.logger.get_level()}")  # "DEBUG"

# Now debug messages appear
z.logger.debug("This now appears")
```

---

### Example 9: Session Context Logging

```python
# Log session initialization details
z.logger.session("Python %s on %s", python_version, os_name)
z.logger.session("zSpark configuration loaded: %d keys", len(zSpark))
z.logger.session("Deployment: %s, Mode: %s", deployment, mode)
z.logger.session("Installation: %s (%s)", install_path, install_type)
```

---

### Example 10: Error Handling

```python
try:
    # Application logic
    process_data()
except Exception as e:
    # Log error (goes to both framework and session framework)
    z.logger.error("Data processing failed: %s", str(e))
    
    # Log critical if unrecoverable
    if is_critical(e):
        z.logger.critical("System failure - cannot continue")
```

---

## Constants Reference

### Log Levels

| Constant | Value | Description |
|---|---|---|
| `LOG_LEVEL_DEBUG` | "DEBUG" | Debug level |
| `LOG_LEVEL_SESSION` | "SESSION" | Session level (15) |
| `LOG_LEVEL_INFO` | "INFO" | Info level |
| `LOG_LEVEL_WARNING` | "WARNING" | Warning level |
| `LOG_LEVEL_ERROR` | "ERROR" | Error level |
| `LOG_LEVEL_CRITICAL` | "CRITICAL" | Critical level |
| `LOG_LEVEL_PROD` | "PROD" | Deprecated (use deployment mode) |
| `DEFAULT_LOG_LEVEL` | "INFO" | Default level |

### Log Filenames

| Constant | Value | Description |
|---|---|---|
| `LOG_FILENAME_FRAMEWORK` | "zos-framework.log" | Framework log (global) |
| `LOG_FILENAME_APP` | "zos-app.log" | Application log (fallback) |

### Config Keys

| Constant | Value | Description |
|---|---|---|
| `CONFIG_KEY_LOGGING` | "logging" | Logging config key |
| `CONFIG_KEY_APP` | "app" | App logger config |
| `CONFIG_KEY_FRAMEWORK` | "framework" | Framework logger config |
| `CONFIG_KEY_FILE_ENABLED` | "file_enabled" | File logging enabled |
| `CONFIG_KEY_FORMAT` | "format" | Log format |
| `CONFIG_KEY_LEVEL` | "level" | Log level |

---

## Best Practices

1. **Use Semantic Routing:**
   - Use `debug()` for framework implementation details
   - Use `info()` for user-facing events and flow
   - Use `session()` for configuration and context
   - Use `warning()` / `error()` / `critical()` for issues

2. **Choose Appropriate Logger:**
   - Framework logger: Rarely (system-level errors only)
   - Session framework logger: Bootstrap, flow, ready banners
   - Application logger: User code (via semantic routing)

3. **Deployment Awareness:**
   - Use deployment mode for UI behavior (banners, console output)
   - Use logger level for log verbosity (independent of deployment)
   - Don't use PROD log level (deprecated - use deployment mode)

4. **Custom Paths:**
   - Use zPath notation (`@.logs`) for workspace-relative paths
   - Use custom paths for application logs only
   - Framework/session framework logs stay in system directory

5. **Console Output:**
   - Use `user()` for messages that should always be visible
   - Use `dev()` for development-only diagnostics
   - Regular logs respect deployment mode (silent in Production)

6. **Log Levels:**
   - DEBUG: Development debugging
   - SESSION: Configuration context
   - INFO: Normal operation
   - WARNING: Potential issues
   - ERROR: Failures
   - CRITICAL: System failures

7. **File Organization:**
   - One application log per session (user code)
   - One session framework log per session (execution trace)
   - One framework log shared across all sessions (rarely used)

8. **Performance:**
   - Logging is fast (buffered I/O)
   - File logging always enabled (negligible overhead)
   - Console output controlled by deployment mode
