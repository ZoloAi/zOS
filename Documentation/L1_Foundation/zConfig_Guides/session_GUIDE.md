# zConfig Session Module Guide

> **Module:** `zOS/core/L1_Foundation/a_zConfig/zConfig_modules/session/`  
> **Purpose:** Runtime session creation, authentication architecture, and session state management.

---

## Overview

The `session` module manages runtime session creation with a three-tier authentication architecture, isolated session instances, and comprehensive state management. It provides the foundation for all runtime state in zOS, including authentication, caching, wizard mode, and custom variables.

---

## Architecture

The session module consists of one main component:

| Component | File | Purpose |
|---|---|---|
| `SessionConfig` | `config_session.py` | Session creation and management |

---

## Three-Tier Authentication Architecture

zOS implements a sophisticated three-tier authentication system supporting multiple authentication contexts simultaneously:

### Layer 1: zSession Auth (Internal)

**Purpose:** Internal zOS/Zolo users

**Storage:** `session["zAuth"]["zSession"]`

**Use cases:**
- zOS features
- Premium plugins
- Zolo cloud services

**Authentication:** `zos.auth.login()`

**Structure:**
```python
session["zAuth"]["zSession"] = {
    "authenticated": False,
    "id": None,
    "username": None,
    "role": None,
    "api_key": None
}
```

---

### Layer 2: Application Auth (External)

**Purpose:** External application users (multi-app support)

**Storage:** `session["zAuth"]["applications"]` (dict of app-specific credentials)

**Use cases:**
- Applications BUILT on zOS (eCommerce stores, SaaS apps)
- Multiple apps authenticated simultaneously
- Configurable user model (developer defines schema)

**Authentication:** `zos.auth.authenticate_app_user(app_name, token, config)`

**Structure:**
```python
session["zAuth"]["applications"] = {
    "ecommerce_store": {
        "authenticated": True,
        "id": 456,
        "username": "customer_bob",
        "role": "customer",
        "api_key": "store_token_xyz"
    },
    "analytics_dashboard": {
        "authenticated": True,
        "id": 789,
        "username": "analyst_alice",
        "role": "analyst",
        "api_key": "analytics_token_abc"
    }
}
```

**Active app tracking:**
```python
session["zAuth"]["active_app"] = "ecommerce_store"  # Which app is currently focused?
```

---

### Layer 3: Dual-Auth (Both Contexts)

**Purpose:** Both zSession and Application auth active simultaneously

**Storage:** `session["zAuth"]["active_context"]` and `session["zAuth"]["dual_mode"]`

**Use cases:**
- Store owner using zOS analytics on their store
- Admin managing multiple applications
- Developer testing with multiple auth contexts

**Structure:**
```python
session["zAuth"]["active_context"] = "dual"
session["zAuth"]["dual_mode"] = True
```

---

## `SessionConfig`

Main class for session creation and management. Creates isolated session instances with machine config, environment settings, logger initialization, and zSpark integration.

### Initialization

```python
from zConfig_modules.session import SessionConfig
from zConfig_modules.machine import MachineConfig
from zConfig_modules.environment import EnvironmentConfig
from zConfig_modules.paths import zConfigPaths

paths = zConfigPaths()
machine_config = MachineConfig(paths)
env_config = EnvironmentConfig(paths)

session_config = SessionConfig(
    machine_config=machine_config,
    environment_config=env_config,
    zos=zos_instance,
    zSpark_obj=None,
    zconfig=zconfig_instance,
    verbose=False
)
```

| Parameter | Type | Description |
|---|---|---|
| `machine_config` | `MachineConfig` | Machine configuration instance |
| `environment_config` | `EnvironmentConfig` | Environment configuration instance |
| `zos` | `zOS` | zOS framework instance (required for validation) |
| `zSpark_obj` | `dict\|None` | Optional runtime overrides |
| `zconfig` | `zConfig` | zConfig instance (required for logger creation) |
| `verbose` | `bool` | Show initialization output (default: False) |

**Raises:** `ValueError` if `zconfig` is None (required for logger initialization)

**On init, automatically:**
1. Validates zOS instance
2. Extracts log level from zSpark
3. Prints ready message (if verbose or Development mode)

---

### Methods

#### `create_session(machine_config=None) -> Dict[str, Any]`

Create isolated session instance with complete runtime state.

```python
session = session_config.create_session()

# Access session properties
print(f"Session ID: {session['zS_id']}")
print(f"Title: {session['title']}")
print(f"Workspace: {session['zSpace']}")
print(f"Logger level: {session['zLogger']}")
```

**Args:**
- `machine_config`: Optional machine config dict (uses `self.machine` if None)

**Returns:** Dict containing complete session configuration with all runtime state.

**Session structure:**
```python
{
    "zS_id": "zS_a1b2c3d4",                  # Unique session ID
    "title": "my_script",                    # Session title (for log naming)
    "zSpace": "/path/to/workspace",          # Workspace directory
    "zVaFolder": None,                       # Optional VA folder
    "zVaFile": None,                         # Optional VA file
    "zBlock": None,                          # Optional block identifier
    "zMode": "zCLI",                         # Execution mode (zCLI, zBifrost)
    "zLogger": "INFO",                       # Logger level
    "logger_path": None,                     # Custom logger path (or None)
    "zTraceback": False,                     # Exception handling enabled
    "zMachine": {...},                       # Machine config dict
    "browser": None,                         # Optional browser override
    "ide": None,                             # Optional IDE override
    "session_hash": "a1b2c3d4",             # Cache invalidation token (v1.6.0)
    "zAuth": {...},                          # Three-tier auth structure
    "zCrumbs": {},                           # Breadcrumb navigation
    "zCache": {...},                         # Multi-tier cache
    "wizard_mode": {...},                    # Wizard mode state
    "zSpark": {...},                         # Original zSpark dict
    "virtual_env": "/path/to/venv",         # Virtual env path (or None)
    "system_env": "...",                     # System PATH
    "logger_instance": <LoggerConfig>,       # Logger instance
    "zVars": {},                             # Custom runtime variables
    "zShortcuts": {}                         # Keyboard shortcuts
}
```

---

#### `generate_id(prefix="zS") -> str`

Generate random session ID with prefix.

```python
session_id = session_config.generate_id()
# "zS_a1b2c3d4"

custom_id = session_config.generate_id(prefix="custom")
# "custom_a1b2c3d4"
```

**Args:**
- `prefix`: ID prefix (default: "zS")

**Returns:** Session ID string with format `{prefix}_{hex}`

---

#### `regenerate_session_hash(session) -> str` (static)

Regenerate session_hash in existing session (called on login/logout).

```python
# In zAuth after login/logout
new_hash = SessionConfig.regenerate_session_hash(zos.session)
print(f"New session hash: {new_hash}")
```

**Purpose:** Invalidate frontend caches when authentication state changes.

**Args:**
- `session`: zOS session dict

**Returns:** New session hash (8-character hex)

**Use case:** Frontend detects hash change and clears stale caches.

---

#### `detect_zMode() -> str`

Detect zMode based on zSpark override, fallback to zCLI.

```python
zMode = session_config.detect_zMode()
# "zCLI" or "zBifrost"
```

**Returns:** "zCLI" or "zBifrost" based on zSpark or default.

---

### Session Title Detection

Session title is used for log file naming. Detection priority:

1. **zSpark["title"]** - Explicit user override
2. **Script filename** (`sys.argv[0]`) - Automatic detection
3. **zS_id** - Fallback for edge cases

**Examples:**

```python
# Explicit title
zSpark = {"title": "my_api_server"}
# → title: "my_api_server"

# Script filename
# Running: python my_script.py
# → title: "my_script"

# Interactive mode
# Running: python -c "code"
# → title: "zcli-interactive"

# Module execution
# Running: python -m mymodule
# → title: "mymodule"
```

---

### Logger Level Detection

Logger level follows a 5-layer hierarchy (highest to lowest priority):

1. **zSpark override** - Explicit user choice
2. **Virtual environment variable** - `$ZOLO_LOGGER` (if in venv)
3. **System environment variable** - `$ZOLO_LOGGER`
4. **zConfig.environment.zolo** - `logging.app.level`
5. **Default** - "INFO"

**Examples:**

```python
# zSpark override
zSpark = {"logger": "DEBUG"}
# → zLogger: "DEBUG"

# Environment variable
export ZOLO_LOGGER=WARNING
# → zLogger: "WARNING"

# Config file (zConfig.environment.zolo)
logging:
  app:
    level: ERROR
# → zLogger: "ERROR"

# Default
# → zLogger: "INFO"
```

**Note:** Logger level is independent of deployment mode. All deployment modes default to INFO.

---

### Logger Path Detection

Custom logger path can be specified via zSpark (authoring key **`zLogPath`**;
the session dict stores it internally as `logger_path`):

```python
zSpark = {"zLogPath": "./logs"}
# → session["logger_path"]: "./logs"

# Default (no custom path)
# → session["logger_path"]: None (uses system path)
```

---

## Session Properties

The session dict contains comprehensive runtime state organized by category:

### Identity

| Property | Type | Description |
|---|---|---|
| `zS_id` | str | Unique session identifier (e.g., "zS_a1b2c3d4") |
| `title` | str | Session title (for log naming) |
| `session_hash` | str | Cache invalidation token (v1.6.0) |

### Workspace

| Property | Type | Description |
|---|---|---|
| `zSpace` | str | Workspace directory path |
| `zVaFolder` | str\|None | Optional VA folder |
| `zVaFile` | str\|None | Optional VA file |
| `zBlock` | str\|None | Optional block identifier |

### Runtime Configuration

| Property | Type | Description |
|---|---|---|
| `zMode` | str | Execution mode (zCLI, zBifrost) |
| `zLogger` | str | Logger level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `logger_path` | str\|None | Custom logger path (or None for system path) |
| `logger_instance` | LoggerConfig | Logger instance (proxies to Python logger) |
| `zTraceback` | bool | Exception handling enabled |

### Machine & Environment

| Property | Type | Description |
|---|---|---|
| `zMachine` | dict | Complete machine config (42+ properties) |
| `browser` | str\|None | Optional browser override |
| `ide` | str\|None | Optional IDE override |
| `virtual_env` | str\|None | Virtual environment path (if in venv) |
| `system_env` | str | System PATH environment variable |

### Authentication (Three-Tier)

| Property | Type | Description |
|---|---|---|
| `zAuth.zSession` | dict | Internal zOS user auth |
| `zAuth.applications` | dict | External app users (multi-app support) |
| `zAuth.active_app` | str\|None | Currently focused app |
| `zAuth.active_context` | str\|None | "zSession", "application", or "dual" |
| `zAuth.dual_mode` | bool | Both contexts active simultaneously |

### State Management

| Property | Type | Description |
|---|---|---|
| `zCrumbs` | dict | Breadcrumb navigation state |
| `zCache` | dict | Multi-tier cache (system, pinned, schema, plugin) |
| `wizard_mode` | dict | Wizard mode state (active, lines, format, transaction) |
| `zVars` | dict | Custom runtime variables |
| `zShortcuts` | dict | Keyboard shortcuts |

### Original Configuration

| Property | Type | Description |
|---|---|---|
| `zSpark` | dict\|None | Original zSpark dict (for reference) |

---

## zAuth Structure (Three-Tier)

Complete authentication structure:

```python
session["zAuth"] = {
    # Layer 1: zSession Auth (Internal)
    "zSession": {
        "authenticated": False,
        "id": None,
        "username": None,
        "role": None,
        "api_key": None
    },
    
    # Layer 2: Application Auth (External, Multi-App)
    "applications": {
        "ecommerce_store": {
            "authenticated": True,
            "id": 456,
            "username": "customer_bob",
            "role": "customer",
            "api_key": "store_token_xyz"
        },
        "analytics_dashboard": {
            "authenticated": True,
            "id": 789,
            "username": "analyst_alice",
            "role": "analyst",
            "api_key": "analytics_token_abc"
        }
    },
    
    # Layer 3: Dual-Auth Tracking
    "active_app": "ecommerce_store",  # Which app is focused?
    "active_context": "application",  # "zSession", "application", or "dual"
    "dual_mode": False                # Both contexts active?
}
```

---

## zCache Structure (Multi-Tier)

Session includes a multi-tier cache system:

```python
session["zCache"] = {
    "system_cache": {},   # System-level cache
    "pinned_cache": {},   # Pinned items cache
    "schema_cache": {},   # Schema definitions cache
    "plugin_cache": {}    # Plugin data cache
}
```

---

## Wizard Mode Structure

Session includes wizard mode state:

```python
session["wizard_mode"] = {
    "active": False,       # Wizard mode enabled?
    "lines": [],           # Wizard input lines
    "format": None,        # Output format
    "transaction": False   # Transaction mode enabled?
}
```

---

## Session Hash (Cache Invalidation)

**Version:** v1.6.0+

**Purpose:** Frontend cache invalidation on auth state changes.

**Behavior:**
- Generated on session creation (8-character hex)
- Regenerated on login/logout via `regenerate_session_hash()`
- Frontend detects hash change and clears stale caches

**Example:**

```python
# Initial session creation
session["session_hash"] = "a1b2c3d4"

# After login
new_hash = SessionConfig.regenerate_session_hash(session)
# session["session_hash"] = "e5f6g7h8"

# Frontend detects change
if current_hash != session["session_hash"]:
    clear_frontend_cache()
```

---

## Practical Examples

### Example 1: Basic Session Creation

```python
from zConfig_modules.session import SessionConfig

session_config = SessionConfig(
    machine_config=machine_config,
    environment_config=env_config,
    zos=zos,
    zconfig=zconfig
)

session = session_config.create_session()

print(f"Session ID: {session['zS_id']}")
print(f"Title: {session['title']}")
print(f"Logger: {session['zLogger']}")
```

---

### Example 2: Custom Session Title

```python
# Explicit title via zSpark
zSpark = {"title": "api_server"}
session_config = SessionConfig(
    machine_config=machine_config,
    environment_config=env_config,
    zos=zos,
    zSpark_obj=zSpark,
    zconfig=zconfig
)

session = session_config.create_session()
print(f"Title: {session['title']}")  # "api_server"
```

---

### Example 3: Custom Logger Configuration

```python
# Custom logger level and path
zSpark = {
    "logger": "DEBUG",
    "logger_path": "./logs"
}

session = session_config.create_session()
print(f"Logger level: {session['zLogger']}")    # "DEBUG"
print(f"Logger path: {session['logger_path']}")  # "./logs"
```

---

### Example 4: zSession Authentication

```python
# Access zSession auth
zauth = session["zAuth"]["zSession"]

# Check authentication status
if zauth["authenticated"]:
    print(f"Logged in as: {zauth['username']}")
    print(f"Role: {zauth['role']}")
else:
    print("Not authenticated")

# After login (handled by zAuth subsystem)
# zauth["authenticated"] = True
# zauth["id"] = 123
# zauth["username"] = "john_doe"
# zauth["role"] = "admin"
```

---

### Example 5: Multi-App Authentication

```python
# Access application auth
apps = session["zAuth"]["applications"]

# Check if specific app is authenticated
if "ecommerce_store" in apps:
    store_auth = apps["ecommerce_store"]
    if store_auth["authenticated"]:
        print(f"Store user: {store_auth['username']}")
        print(f"Role: {store_auth['role']}")

# Check active app
active_app = session["zAuth"]["active_app"]
print(f"Currently focused on: {active_app}")

# Check active context
context = session["zAuth"]["active_context"]
print(f"Auth context: {context}")  # "zSession", "application", or "dual"
```

---

### Example 6: Dual-Auth Mode

```python
# Check if dual-auth is active
zauth = session["zAuth"]

if zauth["dual_mode"]:
    print("Dual-auth active!")
    print(f"zSession user: {zauth['zSession']['username']}")
    print(f"Active app: {zauth['active_app']}")
    
    if zauth["active_app"]:
        app_auth = zauth["applications"][zauth["active_app"]]
        print(f"App user: {app_auth['username']}")
```

---

### Example 7: Custom Runtime Variables

```python
# Store custom variables in session
session["zVars"]["api_endpoint"] = "https://api.example.com"
session["zVars"]["max_retries"] = 3
session["zVars"]["timeout"] = 30

# Access later
api_endpoint = session["zVars"].get("api_endpoint")
max_retries = session["zVars"].get("max_retries", 1)
```

---

### Example 8: Cache Management

```python
# Access multi-tier cache
cache = session["zCache"]

# System cache
cache["system_cache"]["user_preferences"] = {...}

# Pinned cache (high priority)
cache["pinned_cache"]["important_data"] = {...}

# Schema cache
cache["schema_cache"]["user_schema"] = {...}

# Plugin cache
cache["plugin_cache"]["plugin_data"] = {...}
```

---

### Example 9: Wizard Mode

```python
# Enable wizard mode
session["wizard_mode"]["active"] = True
session["wizard_mode"]["format"] = "json"
session["wizard_mode"]["transaction"] = True

# Add wizard lines
session["wizard_mode"]["lines"].append("command 1")
session["wizard_mode"]["lines"].append("command 2")

# Check wizard state
if session["wizard_mode"]["active"]:
    print("Wizard mode enabled")
    print(f"Lines: {len(session['wizard_mode']['lines'])}")
```

---

### Example 10: Session Hash Regeneration

```python
# Initial hash
initial_hash = session["session_hash"]
print(f"Initial hash: {initial_hash}")

# After login (in zAuth subsystem)
new_hash = SessionConfig.regenerate_session_hash(session)
print(f"New hash: {new_hash}")

# Frontend cache invalidation
if initial_hash != session["session_hash"]:
    print("Session hash changed - invalidate frontend cache")
```

---

### Example 11: Virtual Environment Detection

```python
# Check virtual environment
venv_path = session["virtual_env"]

if venv_path:
    print(f"Running in virtual env: {venv_path}")
else:
    print("Running in system environment")

# Access system PATH
system_path = session["system_env"]
print(f"System PATH: {system_path}")
```

---

### Example 12: Machine Config Access

```python
# Access machine config from session
machine = session["zMachine"]

print(f"OS: {machine['os']}")
print(f"CPU cores: {machine['cpu_cores']}")
print(f"Memory: {machine['memory_gb']} GB")
print(f"Browser: {machine['browser']}")
print(f"IDE: {machine['ide']}")
```

---

## Constants Reference

Session module uses centralized constants from `config_constants.py`:

### zMode Values

| Constant | Value | Description |
|---|---|---|
| `ZMODE_ZCLI` | "zCLI" | CLI execution mode |
| `ZMODE_ZBIFROST` | "zBifrost" | Bifrost execution mode |

### Session Keys

| Constant | Value | Description |
|---|---|---|
| `SESSION_KEY_ZS_ID` | "zS_id" | Session ID |
| `SESSION_KEY_TITLE` | "title" | Session title |
| `SESSION_KEY_ZSPACE` | "zSpace" | Workspace path |
| `SESSION_KEY_ZMODE` | "zMode" | Execution mode |
| `SESSION_KEY_ZLOGGER` | "zLogger" | Logger level |
| `SESSION_KEY_LOGGER_PATH` | "logger_path" | Custom logger path |
| `SESSION_KEY_LOGGER_INSTANCE` | "logger_instance" | Logger instance |
| `SESSION_KEY_ZTRACEBACK` | "zTraceback" | Exception handling |
| `SESSION_KEY_ZMACHINE` | "zMachine" | Machine config |
| `SESSION_KEY_ZAUTH` | "zAuth" | Authentication structure |
| `SESSION_KEY_ZCACHE` | "zCache" | Multi-tier cache |
| `SESSION_KEY_WIZARD_MODE` | "wizard_mode" | Wizard mode state |
| `SESSION_KEY_ZSPARK` | "zSpark" | Original zSpark dict |
| `SESSION_KEY_VIRTUAL_ENV` | "virtual_env" | Virtual env path |
| `SESSION_KEY_SYSTEM_ENV` | "system_env" | System PATH |
| `SESSION_KEY_ZVARS` | "zVars" | Custom variables |
| `SESSION_KEY_ZSHORTCUTS` | "zShortcuts" | Keyboard shortcuts |
| `SESSION_KEY_BROWSER` | "browser" | Browser override |
| `SESSION_KEY_IDE` | "ide" | IDE override |
| `SESSION_KEY_SESSION_HASH` | "session_hash" | Cache invalidation token |

### zAuth Keys

| Constant | Value | Description |
|---|---|---|
| `ZAUTH_KEY_ZSESSION` | "zSession" | Internal auth |
| `ZAUTH_KEY_APPLICATIONS` | "applications" | External app auth |
| `ZAUTH_KEY_ACTIVE_APP` | "active_app" | Focused app |
| `ZAUTH_KEY_ACTIVE_CONTEXT` | "active_context" | Auth context |
| `ZAUTH_KEY_DUAL_MODE` | "dual_mode" | Dual-auth flag |
| `ZAUTH_KEY_AUTHENTICATED` | "authenticated" | Auth status |
| `ZAUTH_KEY_ID` | "id" | User ID |
| `ZAUTH_KEY_USERNAME` | "username" | Username |
| `ZAUTH_KEY_ROLE` | "role" | User role |
| `ZAUTH_KEY_API_KEY` | "api_key" | API key/token |

### zCache Keys

| Constant | Value | Description |
|---|---|---|
| `ZCACHE_KEY_SYSTEM` | "system_cache" | System cache |
| `ZCACHE_KEY_PINNED` | "pinned_cache" | Pinned cache |
| `ZCACHE_KEY_SCHEMA` | "schema_cache" | Schema cache |
| `ZCACHE_KEY_PLUGIN` | "plugin_cache" | Plugin cache |

### Wizard Keys

| Constant | Value | Description |
|---|---|---|
| `WIZARD_KEY_ACTIVE` | "active" | Wizard enabled |
| `WIZARD_KEY_LINES` | "lines" | Wizard lines |
| `WIZARD_KEY_FORMAT` | "format" | Output format |
| `WIZARD_KEY_TRANSACTION` | "transaction" | Transaction mode |

---

## Best Practices

1. **Session Creation:**
   - Create session once at initialization
   - Store session in `zos.session` for global access
   - Avoid recreating sessions (expensive operation)

2. **Authentication:**
   - Use three-tier architecture for separation of concerns
   - Support multi-app authentication when building platforms
   - Regenerate session_hash on auth state changes

3. **Custom Variables:**
   - Use `zVars` for application-specific runtime state
   - Avoid polluting session with ad-hoc keys
   - Document custom variables in application code

4. **Cache Management:**
   - Use appropriate cache tier (system, pinned, schema, plugin)
   - Clear caches when session_hash changes
   - Implement cache expiration strategies

5. **Logger Configuration:**
   - Use zSpark for runtime overrides
   - Use environment variables for deployment-specific settings
   - Use config file for persistent preferences

6. **Session Hash:**
   - Regenerate on login/logout
   - Use for frontend cache invalidation
   - Monitor hash changes in frontend

7. **Virtual Environment:**
   - Check `virtual_env` for environment-specific behavior
   - Use for dependency isolation
   - Log venv path for diagnostics

8. **Machine Config:**
   - Access via `session["zMachine"]` for runtime queries
   - Avoid modifying machine config at runtime
   - Use for platform-specific behavior
