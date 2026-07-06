# zConfig Environment Module Guide

> **Module:** `zOS/core/L1_Foundation/a_zConfig/zConfig_modules/environment/`  
> **Purpose:** Deployment settings, environment configuration, and declarative environment variable management.

---

## Overview

The `environment` module manages deployment-specific settings (Development, Testing, Production), environment variables, and declarative configuration loading. It provides a modern alternative to `.env` files through declarative ZOLO/YAML configs while maintaining backward compatibility.

---

## Architecture

The environment module consists of three main components:

| Component | File | Purpose |
|---|---|---|
| `EnvironmentConfig` | `config_environment.py` | Main configuration class (facade) |
| `zEnv` | `config_zenv.py` | Declarative environment loader (THE zOS WAY) |
| Helpers | `environment_helpers.py` | Default config generation |

---

## `EnvironmentConfig`

Main facade for environment configuration. Manages deployment modes, virtual environment detection, and configuration hierarchy.

### Initialization

```python
from zConfig_modules.environment import EnvironmentConfig
from zConfig_modules.paths import zConfigPaths

paths = zConfigPaths()
env_config = EnvironmentConfig(paths, zSpark_obj=None, verbose=False)
```

| Parameter | Type | Description |
|---|---|---|
| `paths` | `zConfigPaths` | Path resolver instance |
| `zSpark_obj` | `dict\|None` | Optional runtime overrides (highest priority) |
| `verbose` | `bool` | Show preboot/bootstrap output (default: False) |

**On init, automatically:**
1. Detects virtual environment and system environment
2. Loads dotenv files (`.zEnv` or `.env`)
3. Gets minimal hardcoded defaults
4. Loads user config from `zConfig.environment.zolo`
5. Writes current state to `.zolo` config file
6. Applies zSpark overrides (Layer 5 - highest priority)
7. Prints ready message (if verbose or Development mode)

---

### Configuration Hierarchy

EnvironmentConfig implements a 5-layer hierarchy (lowest to highest priority):

| Priority | Layer | Source | Example |
|---|---|---|---|
| 1 (lowest) | Hardcoded defaults | Code | `deployment: "Production"` |
| 2 | Environment variables | `$ZOLO_DEPLOYMENT` | `export ZOLO_DEPLOYMENT=Testing` |
| 3 | Config file | `zConfig.environment.zolo` | `deployment: Development` |
| 4 | Dotenv | `.zEnv` / `zEnv.*.zolo` | `DEPLOYMENT=Testing` |
| 5 (highest) | zSpark | Runtime dict | `zOS({"deployment": "Debug"})` |

**Important:** Layer 5 (zSpark) always wins. This allows runtime overrides without modifying persistent config files.

---

### Methods

#### `get(key: str, default=None) -> Any`

Get environment config value by key. Supports **dotted keys** for nested lookups.

```python
deployment = env_config.get("deployment")
datacenter = env_config.get("datacenter", "local")

# Dotted keys walk nested dicts
host = env_config.get("network.host")          # -> "127.0.0.1"
ws_auth = env_config.get("websocket.require_auth", False)
```

If any segment of a dotted key is missing, `default` is returned.

---

#### `update(key: str, value: Any) -> None`

Set an environment config value (runtime). Supports **dotted keys**, creating
intermediate dicts as needed. This is the correct way to set nested values —
a plain `env_config.env["network.host"] = ...` would create a bogus flat key.

```python
env_config.update("deployment", "Testing")          # top-level
env_config.update("network.port", 9000)              # nested (creates path)
env_config.update("logging.app.level", "DEBUG")      # deep nested
```

**Note:** `update()` changes runtime state only — call `save_user_config()` to
persist. The persistence layer (`persist_environment`) uses `update()` internally
so nested keys round-trip correctly.

---

#### `get_all() -> Dict[str, Any]`

Get all environment configuration values (copy).

```python
env = env_config.get_all()
print(f"Deployment: {env['deployment']}")
print(f"Role: {env['role']}")
```

---

#### `get_env_var(key: str, default=None) -> Optional[str]`

Get environment variable with fallback to default.

```python
api_key = env_config.get_env_var("API_KEY", "default_key")
debug_mode = env_config.get_env_var("DEBUG", "false")
```

**Note:** Accesses captured `system_env` snapshot (taken during initialization).

---

#### `is_in_venv() -> bool`

Check if running in virtual environment.

```python
if env_config.is_in_venv():
    print(f"Virtual env: {env_config.get_venv_path()}")
else:
    print("Running in system environment")
```

---

#### `get_venv_path() -> Optional[str]`

Get virtual environment path if running in venv.

```python
venv_path = env_config.get_venv_path()
# "/path/to/venv" or None
```

---

#### `is_production() -> bool`

Check if running in Production deployment mode.

```python
if env_config.is_production():
    # Disable debug features
    pass
```

**Returns:** `True` if deployment is "Production", `False` otherwise.

---

#### `is_testing() -> bool`

Check if running in Testing deployment mode.

```python
if env_config.is_testing():
    # Enable test fixtures
    pass
```

**Returns:** `True` if deployment is "Testing" or "Info" (deprecated), `False` otherwise.

---

#### `is_debug() -> bool`

Check if running in Debug deployment mode.

```python
if env_config.is_debug():
    # Enable verbose logging
    pass
```

**Returns:** `True` if deployment is "Debug", `False` otherwise.

---

#### `is_development() -> bool`

Check if running in Development or Testing deployment mode.

```python
if env_config.is_development():
    # Show banners and system messages
    pass
```

**Returns:** `True` if deployment is "Development", "Testing", "Debug", or "Info", `False` otherwise.

---

#### `save_user_config() -> bool`

Save current environment config to `zConfig.environment.zolo`.

```python
env_config.update("deployment", "Testing")   # use update() (handles nested keys)
success = env_config.save_user_config()
```

**Returns:** `True` if saved successfully, `False` on error.

---

## Environment Properties

The environment config contains deployment settings, network config, logging, security, and performance settings:

### Core Settings

| Property | Type | Description | Default |
|---|---|---|---|
| `deployment` | str | Deployment mode (Development, Testing, Production) | "Production" |
| `role` | str | Node role (development, staging, production) | "production" |
| `datacenter` | str | Datacenter identifier | "local" |
| `cluster` | str | Cluster type (single-node, multi-node, k8s-cluster) | "single-node" |
| `node_id` | str | Unique node identifier | "node-001" |

### Network Settings

| Property | Type | Description | Default |
|---|---|---|---|
| `network.host` | str | Bind address | "127.0.0.1" |
| `network.port` | int | Service port | 56891 |
| `network.external_host` | str | External access hostname | "localhost" |
| `network.external_port` | int | External access port | 56891 |

### WebSocket Settings

| Property | Type | Description | Default |
|---|---|---|---|
| `websocket.host` | str | WebSocket bind address | "127.0.0.1" |
| `websocket.port` | int | WebSocket port | 8765 |
| `websocket.require_auth` | bool | Require authentication | False |
| `websocket.allowed_origins` | list | Allowed CORS origins | [] |
| `websocket.token` | str | Authentication token | "" |
| `websocket.max_connections` | int | Maximum concurrent connections | 100 |
| `websocket.ping_interval` | int | Ping interval in seconds | 20 |
| `websocket.ping_timeout` | int | Ping timeout in seconds | 10 |
| `websocket.ssl_enabled` | bool | Enable SSL/TLS | False |
| `websocket.ssl_cert` | str\|None | Path to SSL certificate | None |
| `websocket.ssl_key` | str\|None | Path to SSL private key | None |

### Security Settings

| Property | Type | Description | Default |
|---|---|---|---|
| `security.require_auth` | bool | Require authentication | True |
| `security.allow_anonymous` | bool | Allow anonymous access | False |
| `security.ssl_enabled` | bool | Enable SSL/TLS | False |
| `security.ssl_cert_path` | str | Path to SSL certificate | "" |
| `security.ssl_key_path` | str | Path to SSL private key | "" |

### Logging Settings

| Property | Type | Description | Default |
|---|---|---|---|
| `logging.app.level` | str | App logger level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | "INFO" |
| `logging.app.format` | str | Log format (simple, detailed, json) | "detailed" |
| `logging.app.file_enabled` | bool | Enable file logging | True |
| `logging.app.file_path` | str | Log file path (empty = auto) | "" |
| `logging.framework.level` | str | Framework logger level | "DEBUG" |
| `logging.framework.format` | str | Framework log format | "detailed" |

### Performance Settings

| Property | Type | Description | Default |
|---|---|---|---|
| `performance.max_workers` | int | Maximum concurrent workers | 4 |
| `performance.cache_size` | int | Cache size limit | 1000 |
| `performance.cache_ttl` | int | Cache time-to-live in seconds | 3600 |
| `performance.timeout` | int | Default timeout in seconds | 30 |

### Custom Fields

| Property | Type | Description | Default |
|---|---|---|---|
| `custom_field_1` | str | User-defined value | "value" |
| `custom_field_2` | int | User-defined value | 42 |
| `custom_field_3` | list | User-defined value | ["item1", "item2"] |

**Note:** All environment settings are user-configurable. Add custom fields as needed.

---

## Deployment Modes

EnvironmentConfig supports three primary deployment modes:

### Development

**Behavior:**
- Full output: banners, system messages, detailed logs
- Default logger level: INFO
- Framework logs shown
- Ready messages displayed

**Use case:** Local development, debugging, learning demos

**Set via:**
```python
# zSpark
z = zOS({"deployment": "Development"})

# Environment variable
export ZOLO_DEPLOYMENT=Development

# Config file (zConfig.environment.zolo)
deployment: Development
```

---

### Testing

**Behavior:**
- Clean logs only: no banners/system messages
- Default logger level: INFO
- Framework logs shown
- No ready messages

**Use case:** Staging, QA, CI/CD pipelines

**Set via:**
```python
z = zOS({"deployment": "Testing"})
```

---

### Production

**Behavior:**
- Minimal: silent console, no banners
- Default logger level: INFO
- Framework logs suppressed
- Clean UI for end users

**Use case:** Production deployments, end-user applications

**Set via:**
```python
z = zOS({"deployment": "Production"})
```

**Note:** Production is the default mode (v1.5.9+). Development is opt-in for demos and learning.

---

### Debug (Special Mode)

**Behavior:**
- Similar to Development but with DEBUG logger level
- Maximum verbosity for troubleshooting

**Use case:** Deep debugging, framework development

**Set via:**
```python
z = zOS({"deployment": "Debug"})
```

---

## `zEnv` - Declarative Environment Loader

THE zOS WAY: Replace traditional `.env` files with declarative ZOLO/YAML configs.

### Overview

`zEnv` provides a secure, declarative alternative to `python-dotenv` while maintaining backward compatibility. It parses declarative config files and injects values into `os.environ` (standard practice).

**Key features:**
- Parse ZOLO/YAML/JSON declarative config files
- Auto-detect file format (`.zolo` preferred, `.yaml` fallback)
- Flatten nested structures to JSON strings
- Priority-based loading (base → environment-specific)
- Secure: Values injected into `os.environ` (process-isolated)
- Backward compatible: Falls back to dotenv if no config files found

---

### Trust model — zEnv is *trusted operator config*

`zEnv` is workspace configuration owned by the operator, and zOS treats it as
**trusted** — the same contract as `.env` in Flask, `direnv`, a `Makefile`, or
`npm` scripts. All declared keys (including operator switches like
`ZTERMINAL_MODE`) are honored and injected into `os.environ` **by design**.

What that means in practice:

- **Parsing is safe regardless of trust.** zEnv files are parsed with
  `yaml.safe_load` / JSON / the zolo parser — never `eval`/`exec`. A malformed or
  hostile file cannot execute code *through the loader itself*.
- **Loading it = trusting it.** Running a project whose `zEnv` you did not write
  or review is a dev-hygiene decision (just like cloning a repo and running its
  `Makefile`). zolomedia does not sandbox third-party workspace config, and is not
  responsible for a developer choosing to run an unverified workspace.
- **Config is trusted, content is still gated.** Trusting `zEnv` does *not* mean
  foreign `.zolo` *content* runs freely — the default-OFF `ZTERMINAL_MODE` gate
  (see zComm/zDisplay guides) still requires an explicit opt-in. Config-trust and
  content-gating are complementary.

> App-author's own responsibility: an app that sets `ZTERMINAL_MODE: trusted` and
> then renders foreign/remote content has opened that door itself — the same class
> of mistake as shipping a Flask app with `DEBUG=True` in production.

---

### File Format

```
workspace/
├── zEnv.base.zolo           # Base configuration (preferred)
├── zEnv.base.yaml           # Base configuration (fallback)
├── zEnv.development.zolo    # Development overrides
├── zEnv.testing.zolo        # Testing overrides
└── zEnv.production.zolo     # Production overrides
```

**Priority order (highest to lowest):**
1. `zEnv.{environment}.zolo` (environment-specific, preferred)
2. `zEnv.{environment}.yaml` (fallback if .zolo not found)
3. `zEnv.base.zolo` (base configuration, preferred)
4. `zEnv.base.yaml` (fallback if .zolo not found)
5. `.zEnv.{environment}` (legacy dotenv fallback)
6. `.zEnv` (legacy dotenv base)

---

### Example Config

**zEnv.base.zolo:**
```zolo
ZNAVBAR:
  zVaF:
  zAccount:
    zRBAC:
      require_role: [zAdmin]

AWS_SECRET_KEY: secret123  # No quotes needed (string-first default)
DEBUG(bool): true          # Explicit type hint
PORT(int): 8080
```

**After loading:**
```python
os.getenv("ZNAVBAR")  # '{"zVaF": null, "zAccount": {"zRBAC": {"require_role": ["zAdmin"]}}}'
os.getenv("AWS_SECRET_KEY")  # "secret123"
os.getenv("DEBUG")  # "true"
os.getenv("PORT")  # "8080"
```

---

### Initialization

```python
from zConfig_modules.environment import zEnv

loader = zEnv(
    workspace_dir="/path/to/project",
    environment="production",
    logger=None
)
```

| Parameter | Type | Description |
|---|---|---|
| `workspace_dir` | str | Path to workspace containing zEnv files |
| `environment` | str | Current environment (development, production, testing) |
| `logger` | Logger\|None | Optional logger for debug output |

---

### Methods

#### `load() -> bool`

Load environment configuration from config files into `os.environ`.

```python
success = loader.load()
# True if any config files were loaded
```

**Auto-detects file format:**
- Tries `.zolo` first (preferred)
- Falls back to `.yaml` if `.zolo` not found

**Priority order:**
1. `zEnv.base.{zolo|yaml}` (base configuration)
2. `zEnv.{environment}.{zolo|yaml}` (environment-specific overrides)

**Returns:** `True` if any config files were loaded, `False` if no files found.

**Note:** Does NOT fall back to dotenv - that's handled by `config_paths.load_dotenv()`.

---

#### `load_files(base_file, env_file) -> bool`

Load specified config files into `os.environ`.

```python
from pathlib import Path

base_file = Path("zEnv.base.zolo")
env_file = Path("zEnv.production.zolo")

success = loader.load_files(base_file, env_file)
```

**Args:**
- `base_file`: Path to base config file (or None)
- `env_file`: Path to environment config file (or None)

**Returns:** `True` if any files were loaded successfully.

**Use case:** When you want explicit control over which files to load.

---

### Value Injection

`zEnv` injects values into `os.environ` with smart type handling:

**Simple values:**
```zolo
API_KEY: secret123
PORT: 8080
DEBUG: true
```

**After injection:**
```python
os.getenv("API_KEY")  # "secret123"
os.getenv("PORT")     # "8080"
os.getenv("DEBUG")    # "true"
```

**Complex values (nested dicts/lists):**
```zolo
ZNAVBAR:
  zVaF:
  zAccount:
    zRBAC:
      require_role: [zAdmin]
```

**After injection:**
```python
os.getenv("ZNAVBAR")  # '{"zVaF": null, "zAccount": {"zRBAC": {"require_role": ["zAdmin"]}}}'

# Parse back to dict
import json
navbar = json.loads(os.getenv("ZNAVBAR"))
```

**Boolean values:**
```zolo
DEBUG: true
VERBOSE: false
```

**After injection:**
```python
os.getenv("DEBUG")    # "true" (lowercase string)
os.getenv("VERBOSE")  # "false" (lowercase string)
```

**None values:**
```zolo
OPTIONAL_KEY:  # None value
```

**After injection:**
```python
os.getenv("OPTIONAL_KEY")  # None (not set in environ)
```

---

### Security

`zEnv` maintains security through standard practices:

- **Process isolation:** Values stored in `os.environ` (standard practice)
- **No serialization risk:** Secrets not in Python objects
- **Docker/K8s compatible:** Works with container orchestration
- **Audit trail:** OS logging captures environment changes
- **Log redaction:** zEnv files behave like dotenv and may hold credentials, so
  values are **never logged verbatim**. Keys matching secret hints (`SECRET`,
  `TOKEN`, `KEY`, `PASSWORD`, `PASSWD`, `PRIVATE`, `CREDENTIAL`, `AUTH`) log as
  `<redacted>`, and nested dict/list values log as `<complex>` (content omitted).

> **Reminder:** `zEnv.*.zolo` files are loaded like `.env` and are **never served**
> by zServer. Keep them out of any static/public directory and add them to
> `.gitignore` if they contain secrets.

---

## Practical Examples

### Example 1: Basic Environment Config

```python
from zConfig_modules.environment import EnvironmentConfig
from zConfig_modules.paths import zConfigPaths

paths = zConfigPaths()
env_config = EnvironmentConfig(paths, verbose=True)

# Check deployment mode
if env_config.is_production():
    print("Running in Production mode")
elif env_config.is_development():
    print("Running in Development mode")

# Access settings
deployment = env_config.get("deployment")
datacenter = env_config.get("datacenter", "local")
```

---

### Example 2: Runtime Override with zSpark

```python
# Override deployment mode at runtime
zSpark = {"deployment": "Testing"}
env_config = EnvironmentConfig(paths, zSpark_obj=zSpark)

print(f"Deployment: {env_config.get('deployment')}")  # "Testing"
print(f"Is testing: {env_config.is_testing()}")       # True
```

---

### Example 3: Environment Variables

```python
# Access environment variables
api_key = env_config.get_env_var("API_KEY", "default_key")
debug_mode = env_config.get_env_var("DEBUG", "false")

# Check virtual environment
if env_config.is_in_venv():
    print(f"Virtual env: {env_config.get_venv_path()}")
```

---

### Example 4: Declarative zEnv Loading

```python
from zConfig_modules.environment import zEnv

# Create loader
loader = zEnv(
    workspace_dir="/path/to/project",
    environment="production"
)

# Load config files
success = loader.load()

if success:
    # Access loaded values
    api_key = os.getenv("API_KEY")
    port = int(os.getenv("PORT", "8080"))
    debug = os.getenv("DEBUG", "false") == "true"
```

---

### Example 5: Complex zEnv Values

**zEnv.base.zolo:**
```zolo
DATABASE:
  host: localhost
  port: 5432
  name: myapp
  credentials:
    username: admin
    password: secret

FEATURE_FLAGS:
  - feature_a
  - feature_b
  - feature_c
```

**Access in code:**
```python
import json
import os

# Parse complex values
db_config = json.loads(os.getenv("DATABASE"))
print(f"DB Host: {db_config['host']}")
print(f"DB Port: {db_config['port']}")

feature_flags = json.loads(os.getenv("FEATURE_FLAGS"))
if "feature_a" in feature_flags:
    print("Feature A enabled")
```

---

### Example 6: Environment-Specific Overrides

**zEnv.base.zolo:**
```zolo
API_URL: http://localhost:8000
DEBUG: false
LOG_LEVEL: INFO
```

**zEnv.production.zolo:**
```zolo
API_URL: https://api.example.com
DEBUG: false
LOG_LEVEL: WARNING
```

**Loading:**
```python
loader = zEnv("/path/to/project", environment="production")
loader.load()

# production values override base
print(os.getenv("API_URL"))    # "https://api.example.com"
print(os.getenv("LOG_LEVEL"))  # "WARNING"
```

---

### Example 7: Deployment Mode Behavior

```python
# Development mode
zSpark = {"deployment": "Development"}
env_config = EnvironmentConfig(paths, zSpark_obj=zSpark)

if env_config.is_development():
    # Show banners, system messages, detailed logs
    print("Development mode: Full output enabled")

# Production mode
zSpark = {"deployment": "Production"}
env_config = EnvironmentConfig(paths, zSpark_obj=zSpark)

if env_config.is_production():
    # Silent console, no banners, clean UI
    print("Production mode: Minimal output")
```

---

### Example 8: Network Configuration

```python
# Access network settings
env = env_config.get_all()

host = env.get("network", {}).get("host", "127.0.0.1")
port = env.get("network", {}).get("port", 56891)

print(f"Server: {host}:{port}")

# WebSocket settings
ws_config = env.get("websocket", {})
ws_host = ws_config.get("host", "127.0.0.1")
ws_port = ws_config.get("port", 8765)
ws_auth = ws_config.get("require_auth", False)

print(f"WebSocket: {ws_host}:{ws_port} (auth: {ws_auth})")
```

---

### Example 9: Custom Configuration Fields

```python
# Add custom fields to environment config
env_config.env["custom_api_endpoint"] = "https://api.custom.com"
env_config.env["custom_timeout"] = 60
env_config.env["custom_features"] = ["feature_x", "feature_y"]

# Save to config file
env_config.save_user_config()

# Access later
api_endpoint = env_config.get("custom_api_endpoint")
timeout = env_config.get("custom_timeout", 30)
```

---

### Example 10: Deprecated Deployment Modes

```python
# Backward compatibility for deprecated modes
zSpark = {"deployment": "Info"}  # Deprecated
env_config = EnvironmentConfig(paths, zSpark_obj=zSpark)

# Automatically migrated to "Testing"
print(f"Deployment: {env_config.get('deployment')}")  # "Testing"
print(f"Is testing: {env_config.is_testing()}")       # True

# Warning shown in non-production modes:
# ⚠️  Deprecated deployment: 'Info' → Use 'Testing' instead
```

---

## Configuration File Format

Environment configuration is stored in `zConfig.environment.zolo` (ZOLO format):

```zolo
zEnv:
  deployment: Production
  role: production
  datacenter: local
  cluster: single-node
  node_id: node-001
  network:
    host: 127.0.0.1
    port: 56891
    external_host: localhost
    external_port: 56891
  websocket:
    host: 127.0.0.1
    port: 8765
    require_auth: false
    allowed_origins: []
    max_connections: 100
    ping_interval: 20
    ping_timeout: 10
  security:
    require_auth: true
    allow_anonymous: false
    ssl_enabled: false
  logging:
    app:
      level: INFO
      format: detailed
      file_enabled: true
    framework:
      level: DEBUG
      format: detailed
  performance:
    max_workers: 4
    cache_size: 1000
    cache_ttl: 3600
    timeout: 30
```

**Editing:**
1. Manual: Edit `zConfig.environment.zolo` in your zConfigs dir (Linux: `~/.config/zOS/zConfigs/`; macOS: `~/Library/Application Support/zOS/zConfigs/`)
2. Programmatic: Use `env_config.update(key, value)` + `save_user_config()` (use `update()`, not `env[...]`, for nested keys)
3. zShell: `config set env deployment Testing` (recommended)

---

## Best Practices

1. **Deployment Modes:**
   - Use Production for end-user applications (clean UI)
   - Use Development for local debugging (full output)
   - Use Testing for CI/CD pipelines (clean logs, no banners)

2. **Configuration Hierarchy:**
   - Use config file for persistent settings
   - Use dotenv for secrets (add to `.gitignore`)
   - Use zSpark for runtime overrides (testing, experiments)

3. **zEnv Files:**
   - Prefer `.zolo` format over `.yaml` (string-first, type hints)
   - Use `zEnv.base.zolo` for shared settings
   - Use `zEnv.{environment}.zolo` for environment-specific overrides
   - Never commit secrets to version control

4. **Environment Variables:**
   - Use `get_env_var()` to access environment variables
   - Provide sensible defaults for optional values
   - Parse complex values with `json.loads()`

5. **Virtual Environments:**
   - Check `is_in_venv()` for environment-specific behavior
   - Use `get_venv_path()` for diagnostics

6. **Custom Fields:**
   - Add custom fields to environment config as needed
   - Use nested dicts for organized configuration
   - Save changes with `save_user_config()`

7. **Security:**
   - Store secrets in dotenv files (not config files)
   - Use `os.environ` for process isolation
   - Enable SSL/TLS in production (`security.ssl_enabled`)

8. **Performance:**
   - Environment config loaded once at initialization
   - Use `get()` for fast property access
   - Avoid calling `save_user_config()` frequently
