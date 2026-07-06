# zConfig Paths Module Guide

> **Module:** `zOS/core/L1_Foundation/a_zConfig/zConfig_modules/paths/`  
> **Purpose:** Cross-platform path resolution for zOS configuration, workspaces, user data, and environment files.

---

## Overview

The `paths` module provides unified, OS-native path resolution across Linux, macOS, and Windows. It is composed of two public classes exposed via `__init__.py`:

| Class | File | Purpose |
|---|---|---|
| `zConfigPaths` | `config_paths.py` | Main path resolver (mixin composition) |
| `StoragePathManager` | `config_storage_paths.py` | User/service storage path management |

---

## Architecture: Mixin Composition

`zConfigPaths` is assembled from five focused mixin classes using multiple inheritance:

```
zConfigPaths
├── zConfigPathsConstants   (_paths_constants.py)   — App constants & type declarations
├── zConfigPathsLogging     (_paths_logging.py)      — Deployment-aware logging helpers
├── zConfigPathsWorkspace   (_paths_workspace.py)    — Workspace & dotenv detection + load_dotenv()
├── zConfigPathsOsDirs      (_paths_os_dirs.py)      — OS-native directory @properties
└── zConfigPathsConfigFiles (_paths_config_files.py) — Config hierarchy, system paths, dir utilities
```

**Design rationale:** Each mixin handles a single responsibility, making the codebase maintainable and testable. The main `zConfigPaths` class simply composes these mixins without adding logic.

---

## `zConfigPaths`

### Initialization

```python
from zConfig_modules.paths import zConfigPaths

paths = zConfigPaths(zSpark_obj=None, verbose=False)
```

| Parameter | Type | Description |
|---|---|---|
| `zSpark_obj` | `dict \| None` | Optional config overrides (workspace, dotenv path, deployment mode) |
| `verbose` | `bool` | Show preboot/bootstrap output (default: `False`) |

**Raises:** `UnsupportedOSError` if OS is not Linux, Darwin (macOS), or Windows.

**On init, automatically:**
- Validates OS type (Linux, Darwin, Windows only)
- Extracts log level and deployment mode from zSpark
- Resolves `self.workspace_dir` (from zSpark["zSpace"] or cwd)
- Detects `self._dotenv_path` (.zEnv or .env)
- Logs initialization details (if verbose=True)

---

## OS-Native Directories

All directory properties use `platformdirs` for native OS conventions.

### System Directories

| Property | Linux/macOS | Windows |
|---|---|---|
| `system_config_dir` | `/etc/zOS` | `C:\ProgramData\zOS` |

### User Directories

| Property | Linux | macOS | Windows |
|---|---|---|---|
| `user_config_dir` | `~/.local/share/zOS` | `~/Library/Application Support/zOS` | `%LOCALAPPDATA%\zOS` |
| `user_data_dir` | `~/.local/share/zOS` | `~/Library/Application Support/zOS` | `%LOCALAPPDATA%\zOS` |
| `user_cache_dir` | `~/.cache/zOS` | `~/Library/Caches/zOS` | `%LOCALAPPDATA%\zOS\Cache` |
| `user_logs_dir` | `~/.local/share/zOS/logs` | `~/Library/Application Support/zOS/logs` | `%LOCALAPPDATA%\zOS\logs` |

### Sub-directories

| Property | Path | Purpose |
|---|---|---|
| `user_zconfigs_dir` | `user_config_dir/zConfigs/` | Configuration files (machine, environment) |
| `user_zuis_dir` | `user_config_dir/zUIs/` | UI definition files for commands/walkers |
| `user_zschemas_dir` | `user_config_dir/zSchemas/` | System schema templates (migrations) |

> **Design note:** `user_config_dir` and `user_data_dir` return the same path intentionally — this simplifies backup, uninstall, and user management. All user data lives in one location.

---

## Config File Hierarchy

`get_config_file_hierarchy()` returns all existing config files in priority order:

| Priority | Source | Path |
|---|---|---|
| 1 | System defaults | `system_config_dir/zConfig.defaults.yaml` |
| 2 | User config (OS-native) | `user_config_dir/zConfigs/zConfig.yaml` |
| 3 | Dotenv / zEnv | `.zEnv` or `.env` in workspace |
| 4 | Session runtime | In-memory (handled by zSession, not in this module) |

```python
hierarchy = paths.get_config_file_hierarchy()
# Returns: [(Path, priority_int, description_str), ...]
```

---

## Workspace Detection

`_detect_workspace_dir()` resolves the workspace directory in this priority:

1. **Explicit path** from `zSpark["zSpace"]` (if provided)
2. **Current directory** via `Path.cwd()` (default)
3. **Home directory** via `Path.home()` (fallback if cwd fails)

```python
# Access resolved workspace
paths.workspace_dir  # Path | None

# Example: Override workspace via zSpark
zSpark = {"zSpace": "/path/to/project"}
paths = zConfigPaths(zSpark_obj=zSpark)
```

**Error handling:** If zSpark["zSpace"] is invalid, logs warning and falls back to cwd.

---

## Environment File (dotenv / zEnv) Detection

### Detection Priority

`_detect_dotenv_file()` scans in this order:

1. **Explicit path** from `zSpark` via any `DOTENV_KEY_ALIASES` key
2. **`.zEnv`** in workspace directory *(primary convention)*
3. **`.env`** in workspace directory *(backward compatibility)*
4. Returns `.zEnv` path even if neither exists (for potential creation)

**Supported `zSpark` key aliases:**
```python
DOTENV_KEY_ALIASES = (
    "env_file", "envFile", "dotenv", "dotenv_file", 
    "dotenvFile", "dotenv_path", "dotenvPath"
)
```

**Access dotenv path:**
```python
dotenv_path = paths.get_dotenv_path()  # Path | None

# Example: Override dotenv path via zSpark
zSpark = {"dotenv_path": "/custom/.env"}
paths = zConfigPaths(zSpark_obj=zSpark)
```

**Logging:** Warns if `.env` is used (suggests migrating to `.zEnv`).

### Loading Environment Variables

`load_dotenv()` uses a **strict zEnv priority** system (v2.0):

**Priority 1 — THE zOS WAY (declarative ZOLO/YAML files):**
- Looks for `zEnv.base.{zolo|yaml}` + `zEnv.{deployment}.{zolo|yaml}`
- If ANY of these exist, dotenv fallback is **skipped entirely**
- Deployment is resolved from:
  1. `zSpark["deployment"]` (case-insensitive: deployment, Deployment, DEPLOYMENT)
  2. `$DEPLOYMENT` or `$ZOLO_DEPLOYMENT` environment variable
  3. Defaults to `"development"`

**Priority 2 — Dotenv-only mode:**
- Only runs if NO ZOLO/YAML config files are found
- Loads `.zEnv` (or `.env`) and optionally cascades `.zEnv.{deployment}`
- Cascading support (v1.5.10): Loads base + deployment-specific overrides

```python
# Load environment variables
loaded_path = paths.load_dotenv(override=True)  # Path | None

# Returns:
# - Path to loaded file (base or env-specific)
# - None if no files found or loading failed
```

**Example zOS WAY structure:**
```
workspace/
├── zEnv.base.zolo           # Shared base config (all environments)
├── zEnv.development.zolo    # Dev overrides
├── zEnv.testing.zolo        # Testing overrides
└── zEnv.production.zolo     # Production overrides
```

**Example dotenv-only structure:**
```
workspace/
├── .zEnv                    # Base environment variables
├── .zEnv.development        # Dev-specific overrides (optional)
└── .zEnv.production         # Prod-specific overrides (optional)
```

**Important behavior:**
- If `zEnv.base.zolo` exists (even if empty), `.zEnv` is **never loaded**
- This ensures declarative files always take precedence
- Prevents accidental mixing of YAML and dotenv configurations

---

## System Config File Properties

| Property | Path | Purpose |
|---|---|---|
| `system_config_defaults` | `system_config_dir/zConfig.defaults.yaml` | System default configuration (base) |
| `system_machine_config` | `system_config_dir/zMachine.yaml` | Machine identity and capabilities |

**Note:** These are **discovery-only** properties. The system config directory is not created automatically (requires admin/root privileges).

---

## Directory Utilities

### `ensure_user_config_dir()`
Creates `user_config_dir` if it doesn't exist.

```python
config_dir = paths.ensure_user_config_dir()  # Path
# Returns: Path to user config directory (created if needed)
```

**Use case:** Ensure config directory exists before writing files.

---

### `get_app_path(app_name, subpath="")`
Returns path for app-specific storage (does **not** create directories).

```python
# Get app root directory
paths.get_app_path("zCloud")
# ~/Library/Application Support/zOS/Apps/zCloud

# Get app subdirectory
paths.get_app_path("zCloud", "storage/users")
# ~/Library/Application Support/zOS/Apps/zCloud/storage/users
```

**Important:** This method only **constructs** paths, it does not create them. Use `os.makedirs()` or helper functions to create directories.

**Use case:** App-specific storage isolation (e.g., zCloud, zBifrost, custom apps).

---

### `get_info()`
Returns a debug dict of all resolved paths.

```python
info = paths.get_info()
# {
#     "os": "Darwin",
#     "system_config_dir": "/etc/zOS",
#     "system_config_defaults": "/etc/zOS/zConfig.defaults.yaml",
#     "system_machine_config": "/etc/zOS/zMachine.yaml",
#     "user_config_dir": "~/Library/Application Support/zOS",
#     "user_zconfigs_dir": "~/Library/Application Support/zOS/zConfigs",
#     "user_zuis_dir": "~/Library/Application Support/zOS/zUIs",
#     "user_data_dir": "~/Library/Application Support/zOS",
#     "user_cache_dir": "~/Library/Caches/zOS",
#     "user_logs_dir": "~/Library/Application Support/zOS/logs"
# }
```

**Use case:** Debugging, diagnostics, config check commands.

---

## `StoragePathManager`

Manages per-user and per-service storage paths. Integrates with `zConfig` for base path resolution.

### Initialization

```python
from zConfig_modules.paths import StoragePathManager

# Initialize with zConfig instance
storage = StoragePathManager(config=zconfig_instance)
```

**Integration:** Accesses `config.paths.user_data_dir` for base directory and `config.logger` for debug logging.

---

### Methods

#### `get_user_storage_path(user_id: int) -> str`

Returns (and **creates**) the user's storage directory.

```python
user_path = storage.get_user_storage_path(user_id=42)
# macOS:   ~/Library/Application Support/zOS/users/42/
# Linux:   ~/.local/share/zOS/users/42/
# Windows: %LOCALAPPDATA%\zOS\users\42\
```

**Behavior:**
- Creates directory if it doesn't exist (`os.makedirs(exist_ok=True)`)
- Logs creation to debug logger (if available)
- Returns path as string (not Path object)

**Use case:** Multi-user applications, per-user data isolation.

---

#### `get_service_storage_path(user_id: int, service_name: str) -> str`

Returns (and **creates**) a service-specific subdirectory within the user's storage.

```python
service_path = storage.get_service_storage_path(42, "zvideo")
# ~/Library/Application Support/zOS/users/42/zvideo/
```

**Behavior:**
- Calls `get_user_storage_path()` first (ensures parent exists)
- Creates service subdirectory (lowercase service name)
- Logs creation to debug logger (if available)
- Returns path as string (not Path object)

**Use case:** Service isolation (zvideo, zaudio, zcloud), quota management.

---

#### `get_storage_info(path: str) -> dict`

Returns disk usage information for a path.

```python
info = storage.get_storage_info("/some/path")
# {
#     "total_bytes": 1000000000000,
#     "used_bytes": 500000000000,
#     "free_bytes": 500000000000
# }
```

**Implementation:** Uses `shutil.disk_usage()` for cross-platform disk stats.

**Use case:** Quota enforcement, storage monitoring, cleanup decisions.

---

## Constants Reference

Defined in `_paths_constants.py` / `zConfigPathsConstants`:

| Constant | Value | Purpose |
|---|---|---|
| `APP_NAME` | `"zOS"` | Application name (from config_constants) |
| `APP_AUTHOR` | `"zolo"` | Application author (from config_constants) |
| `VALID_OS_TYPES` | `("Linux", "Darwin", "Windows")` | Supported operating systems |
| `DOTENV_FILENAME` | `".zEnv"` | Primary dotenv filename |
| `ZCONFIGS_DIRNAME` | `"zConfigs"` | Config files subdirectory |
| `ZUIS_DIRNAME` | `"zUIs"` | UI definitions subdirectory |
| `ZCONFIG_FILENAME` | `"zConfig.yaml"` | Main config filename |
| `ZMACHINE_FILENAME` | `"zMachine.yaml"` | System machine config (read-only) |
| `ZMACHINE_USER_FILENAME` | `"zConfig.machine.yaml"` | User machine config — legacy YAML fallback (read only) |
| `ZMACHINE_USER_ZOLO_FILENAME` | `"zConfig.machine.zolo"` | **User machine config — active format (read + written)** |
| `ZENVIRONMENT_FILENAME` | `"zConfig.environment.yaml"` | Environment config — legacy YAML fallback (read only) |
| `ZENVIRONMENT_ZOLO_FILENAME` | `"zConfig.environment.zolo"` | **Environment config — active format (read + written)** |
| `ZCONFIG_DEFAULTS_FILENAME` | `"zConfig.defaults.yaml"` | System defaults |
| `ZENV_EXTENSIONS` | `[".zolo", ".yaml"]` | zEnv file extensions (`.zolo` preferred, `.yaml` fallback) |
| `DOTENV_KEY_ALIASES` | `("env_file", "envFile", ...)` | zSpark keys for dotenv path |

**Note:** These live in `_paths_constants.py` (`zConfigPathsConstants`); the
identity values (`APP_NAME`, `APP_AUTHOR`, `DOTENV_FILENAME`) are imported from
`config_constants.py`. zOS **writes the `.zolo` files**; the `.yaml` names are kept
only as a read-time fallback for older installs.

---

## Logging Helpers

The `_paths_logging.py` mixin provides deployment-aware logging during preboot initialization:

### Methods

```python
# Internal logging methods (used by mixins)
_log_info(message: str)      # Shown only if verbose=True
_log_warning(message: str)   # Shown only if verbose=True
_log_error(message: str)     # Always shown

# Deployment checks (called during __init__)
_check_production_from_zspark(zSpark_obj)  # Returns bool
_check_testing_from_zspark(zSpark_obj)     # Returns bool
```

**Behavior:**
- Info/warning logs respect `verbose` flag (preboot initialization)
- Error logs always shown (critical failures)
- Deployment checks extract mode from zSpark before environment config exists

**Use case:** Early initialization logging before full logger is available.

---

## File Reference

```
paths/
├── __init__.py                  # Exports: zConfigPaths, StoragePathManager
├── config_paths.py              # zConfigPaths (assembled mixin class)
├── config_storage_paths.py      # StoragePathManager (user/service storage)
├── _paths_constants.py          # App constants & type declarations
├── _paths_logging.py            # Deployment-aware logging helpers
├── _paths_workspace.py          # Workspace & dotenv detection + load_dotenv()
├── _paths_os_dirs.py            # OS-native directory @properties
└── _paths_config_files.py       # Config hierarchy, system paths, dir utilities
```

**Design pattern:** Main classes (`config_paths.py`, `config_storage_paths.py`) are public API. Underscore-prefixed files (`_paths_*.py`) are internal mixins.

---

## Practical Examples

### Example 1: Basic Initialization

```python
from zConfig_modules.paths import zConfigPaths

# Initialize with defaults
paths = zConfigPaths()

# Access directories
print(f"User config: {paths.user_config_dir}")
print(f"User logs: {paths.user_logs_dir}")
print(f"Workspace: {paths.workspace_dir}")
```

---

### Example 2: Custom Workspace and Dotenv

```python
# Override workspace and dotenv path
zSpark = {
    "zSpace": "/path/to/project",
    "dotenv_path": "/custom/.env"
}
paths = zConfigPaths(zSpark_obj=zSpark, verbose=True)

# Load environment variables
loaded = paths.load_dotenv(override=True)
if loaded:
    print(f"Loaded env from: {loaded}")
```

---

### Example 3: Config File Hierarchy

```python
# Get all config files in priority order
hierarchy = paths.get_config_file_hierarchy()

for path, priority, description in hierarchy:
    print(f"[{priority}] {description}: {path}")

# Output:
# [1] system-defaults: /etc/zOS/zConfig.defaults.yaml
# [2] user: ~/Library/Application Support/zOS/zConfigs/zConfig.yaml
# [3] env-dotenv: /path/to/project/.zEnv
```

---

### Example 4: App-Specific Storage

```python
# Get app storage path (does not create)
app_path = paths.get_app_path("zCloud", "storage/users")
print(f"App storage: {app_path}")

# Create directory manually
import os
os.makedirs(app_path, exist_ok=True)
```

---

### Example 5: Per-User Storage

```python
from zConfig_modules.paths import StoragePathManager

# Initialize storage manager (requires zConfig instance)
storage = StoragePathManager(config=zconfig_instance)

# Get user storage (creates directory)
user_path = storage.get_user_storage_path(user_id=42)
print(f"User 42 storage: {user_path}")

# Get service storage within user directory
video_path = storage.get_service_storage_path(42, "zvideo")
print(f"Video service: {video_path}")

# Check disk usage
info = storage.get_storage_info(user_path)
print(f"Free space: {info['free_bytes'] / (1024**3):.2f} GB")
```

---

### Example 6: zEnv Loading (THE zOS WAY)

```python
# Project structure:
# workspace/
# ├── zEnv.base.zolo           # Shared config
# ├── zEnv.development.zolo    # Dev overrides
# └── zEnv.production.zolo     # Prod overrides

zSpark = {"deployment": "production"}
paths = zConfigPaths(zSpark_obj=zSpark)

# Load zEnv files (priority: base + production)
loaded = paths.load_dotenv(override=True)
# Loads: zEnv.base.zolo + zEnv.production.zolo
# Skips: .zEnv (if exists) because YAML files take precedence
```

---

### Example 7: Dotenv Cascading

```python
# Project structure:
# workspace/
# ├── .zEnv                    # Base variables
# └── .zEnv.production         # Production overrides

zSpark = {"deployment": "production"}
paths = zConfigPaths(zSpark_obj=zSpark)

# Load dotenv with cascading
loaded = paths.load_dotenv(override=True)
# Loads: .zEnv + .zEnv.production
# Note: Only runs if NO zEnv.*.{zolo|yaml} files exist
```

---

### Example 8: Debugging Paths

```python
# Get all path information
info = paths.get_info()

for key, value in info.items():
    print(f"{key}: {value}")

# Output:
# os: Darwin
# system_config_dir: /etc/zOS
# user_config_dir: ~/Library/Application Support/zOS
# user_logs_dir: ~/Library/Application Support/zOS/logs
# ...
```
