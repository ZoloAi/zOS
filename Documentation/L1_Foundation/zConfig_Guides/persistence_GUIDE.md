# zConfig Persistence Module Guide

> **Module:** `zOS/core/L1_Foundation/a_zConfig/zConfig_modules/persistence/`  
> **Purpose:** Configuration persistence for saving/loading user-editable configuration changes.

---

## Overview

The `persistence` module manages saving and loading configuration changes to disk. It handles **only editable zOS config parts** (user preferences, tool selections, resource limits) while protecting auto-detected characteristics from accidental modification.

---

## Architecture

The persistence module consists of one main component:

| Component | File | Purpose |
|---|---|---|
| `ConfigPersistence` | `config_persistence.py` | Save/load configuration changes |

---

## `ConfigPersistence`

Manages configuration persistence to files with validation and safety checks.

### Initialization

```python
from zConfig_modules.persistence import ConfigPersistence

persistence = ConfigPersistence(
    machine_config=machine_config,
    environment_config=env_config,
    paths=paths_instance,
    zos=zos_instance
)
```

| Parameter | Type | Description |
|---|---|---|
| `machine_config` | `MachineConfig` | Machine configuration instance |
| `environment_config` | `EnvironmentConfig` | Environment configuration instance |
| `paths` | `zConfigPaths` | Path resolver instance |
| `zos` | `zOS\|None` | Optional zOS instance (for session updates) |

**Note:** Usually accessed via `z.config.persistence` (lazy-loaded).

---

## Machine Config Persistence

### Editable Keys

Only **user preferences** are editable. Auto-detected characteristics are protected
— and only these editable keys are ever written to `zConfig.machine.zolo` (the file
is prefs-only; see [machine guide → Persistence model](machine_GUIDE.md#persistence-model)).

**Editable machine keys:**
- **User tools:** browser, ide, terminal, shell
- **Media apps:** image_viewer, video_player, audio_player
- **Time/date:** time_format, date_format, datetime_format
- **Resource limits:** cpu_cores_limit, memory_gb_limit

**Protected (read-only):**
- **Hardware:** os, hostname, architecture, cpu_cores, memory_gb, gpu_*, network_*
- **Python:** python_version, python_impl, python_executable
- **System:** username, home, cwd, path

---

### Methods

#### `persist_machine(key=None, value=None, show=False, reset=False) -> bool`

Persist machine configuration changes to `zConfig.machine.zolo`.

```python
# Update single value
success = persistence.persist_machine("browser", "Firefox")

# Show current values
persistence.persist_machine(show=True)

# Reset to auto-detected defaults
persistence.persist_machine("browser", reset=True)
```

**Args:**
- `key`: Machine config key (e.g., "browser", "ide")
- `value`: New value
- `show`: If True, show current values
- `reset`: If True, reset to auto-detected defaults

**Returns:** `True` if successful, `False` on error

**Behavior:**
1. Validates key is editable
2. Validates value (if applicable)
3. Updates runtime config
4. Updates session (if available)
5. Persists to disk
6. Shows success/error message

---

#### `show_machine_config() -> bool`

Display current machine configuration with dynamic field discovery.

```python
persistence.show_machine_config()
```

**Output example:**
```
======================================================================
Machine Configuration
======================================================================

Identity (Auto-detected):
  [LOCK] os: Darwin
  [LOCK] hostname: MacBook-Pro
  [LOCK] architecture: arm64
  [LOCK] python_version: 3.12.0

User Tools & Preferences (Editable):
  [EDIT] browser: Chrome
  [EDIT] ide: cursor
  [EDIT] terminal: xterm-256color
  [EDIT] shell: /bin/zsh
  [EDIT] image_viewer: Preview
  [EDIT] video_player: VLC
  [EDIT] audio_player: iTunes

Hardware Capabilities (Auto-detected):
  [LOCK] cpu_cores: 8
  [LOCK] cpu_physical: 8
  [LOCK] cpu_performance: 4
  [LOCK] cpu_efficiency: 4
  [LOCK] memory_gb: 16
  [LOCK] gpu_available: true
  [LOCK] gpu_type: Apple M1

Network Configuration (Auto-detected):
  [LOCK] network_interfaces: en0, en1
  [LOCK] network_primary: en0
  [LOCK] network_ip_local: 192.168.1.100

Config file: ~/.../zOS/zConfigs/zConfig.machine.zolo
======================================================================
```

**Features:**
- Dynamic field discovery (new detector fields appear automatically)
- Pattern-based categorization (intelligent grouping)
- Editable vs locked markers (`[EDIT]` vs `[LOCK]`)
- Complete visibility (shows ALL fields)

**Returns:** `True` (always succeeds)

---

## Environment Config Persistence

### Editable Keys

All environment config keys are editable (user-defined settings).

**Editable environment keys:**
- **Basic:** deployment, role, datacenter, cluster, node_id
- **Network:** network.host, network.port, network.external_host, network.external_port
- **Security:** security.require_auth, security.allow_anonymous, security.ssl_enabled
- **Logging:** logging.level, logging.format, logging.file_enabled, logging.file_path
- **Performance:** performance.max_workers, performance.cache_size, performance.cache_ttl, performance.timeout

---

### Methods

#### `persist_environment(key=None, value=None, show=False, reset=False) -> bool`

Persist environment configuration changes to `zConfig.environment.zolo`.

```python
# Update single value
success = persistence.persist_environment("deployment", "Testing")

# Update nested value
success = persistence.persist_environment("logging.level", "DEBUG")

# Show current values
persistence.persist_environment(show=True)

# Reset to defaults
persistence.persist_environment("deployment", reset=True)
```

**Args:**
- `key`: Environment config key (e.g., "deployment", "logging.level")
- `value`: New value
- `show`: If True, show current values
- `reset`: If True, reset to defaults

**Returns:** `True` if successful, `False` on error

**Behavior:**
1. Validates key is editable
2. Validates value (deployment, role, log level, numeric values)
3. Updates runtime config
4. Persists to disk
5. Shows success/error message

---

#### `show_environment_config() -> bool`

Display current environment configuration.

```python
persistence.show_environment_config()
```

**Output example:**
```
======================================================================
Environment Configuration
======================================================================

zOS Environment Settings:
  [EDIT] deployment: Production
  [EDIT] role: production
  [EDIT] datacenter: local
  [EDIT] cluster: single-node
  [EDIT] node_id: node-001
  [EDIT] network: {...}
  [EDIT] websocket: {...}
  [EDIT] security: {...}
  [EDIT] logging: {...}
  [EDIT] performance: {...}

Config file: ~/.../zOS/zConfigs/zConfig.environment.zolo
======================================================================
```

**Returns:** `True` (always succeeds)

---

## Validation

ConfigPersistence validates values before saving:

### Machine Value Validation

```python
# Numeric validation (cpu_cores, memory_gb)
persistence.persist_machine("cpu_cores_limit", 4)     # Valid
persistence.persist_machine("cpu_cores_limit", -1)    # Error: must be positive
persistence.persist_machine("cpu_cores_limit", "abc") # Error: must be number
```

---

### Environment Value Validation

```python
# Deployment validation
persistence.persist_environment("deployment", "Production")  # Valid
persistence.persist_environment("deployment", "Prod")        # Error: invalid

# Role validation
persistence.persist_environment("role", "production")  # Valid
persistence.persist_environment("role", "invalid")     # Error: invalid

# Log level validation
persistence.persist_environment("logging.level", "DEBUG")  # Valid
persistence.persist_environment("logging.level", "TRACE")  # Error: invalid

# Numeric validation
persistence.persist_environment("performance.max_workers", 8)   # Valid
persistence.persist_environment("performance.max_workers", -1)  # Error: must be positive
```

---

## Valid Values

### Deployment Modes

| Value | Description |
|---|---|
| Debug | Maximum verbosity for troubleshooting |
| Development | Full output (banners, system messages, detailed logs) |
| Testing | Clean logs only (no banners/system messages) |
| Production | Minimal (silent console, no banners) |

**Deprecated:** "Info" (mapped to "Testing")

---

### Roles

| Value | Description |
|---|---|
| development | Development environment |
| testing | Testing environment |
| staging | Staging environment |
| production | Production environment |

---

### Log Levels

| Value | Description |
|---|---|
| DEBUG | Detailed diagnostic information |
| INFO | General informational messages |
| WARNING | Warning messages |
| ERROR | Error messages |
| CRITICAL | Critical messages |

---

## Practical Examples

### Example 1: Update Browser

```python
from zOS import zOS

z = zOS()

# Update browser preference
success = z.config.persistence.persist_machine("browser", "Firefox")

if success:
    print("Browser updated to Firefox")
    
# Verify change
print(f"Current browser: {z.config.get_machine('browser')}")
```

---

### Example 2: Update Deployment Mode

```python
# Update deployment mode
success = z.config.persistence.persist_environment("deployment", "Testing")

if success:
    print("Deployment mode updated to Testing")
    
# Verify change
print(f"Current deployment: {z.config.get_environment('deployment')}")
```

---

### Example 3: Show Current Configuration

```python
# Show machine config
z.config.persistence.show_machine_config()

# Show environment config
z.config.persistence.show_environment_config()
```

---

### Example 4: Reset to Defaults

```python
# Reset browser to auto-detected default
success = z.config.persistence.persist_machine("browser", reset=True)

# Reset deployment to default
success = z.config.persistence.persist_environment("deployment", reset=True)
```

---

### Example 5: Update Resource Limits

```python
# Set CPU limit
success = z.config.persistence.persist_machine("cpu_cores_limit", 4)

# Set memory limit
success = z.config.persistence.persist_machine("memory_gb_limit", 8)

# Verify limits
print(f"CPU limit: {z.config.get_cpu_limit()}")
print(f"Memory limit: {z.config.get_memory_limit_gb()} GB")
```

---

### Example 6: Update Nested Environment Values

```python
# Update nested logging level
success = z.config.persistence.persist_environment("logging.level", "DEBUG")

# Update nested network settings
success = z.config.persistence.persist_environment("network.port", 9000)

# Update nested performance settings
success = z.config.persistence.persist_environment("performance.max_workers", 8)
```

---

### Example 7: Validation Errors

```python
# Invalid deployment mode
success = z.config.persistence.persist_environment("deployment", "Prod")
# Output: [ERROR] Invalid deployment: Prod. Must be one of: Debug, Development, Testing, Production

# Invalid log level
success = z.config.persistence.persist_environment("logging.level", "TRACE")
# Output: [ERROR] Invalid log level: TRACE. Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL

# Invalid numeric value
success = z.config.persistence.persist_machine("cpu_cores_limit", -1)
# Output: [ERROR] cpu_cores_limit must be positive
```

---

### Example 8: Protected Keys

```python
# Try to update protected key
success = z.config.persistence.persist_machine("os", "Windows")
# Output: [ERROR] Invalid machine config key: os
#         Editable keys: browser, ide, terminal, shell, ...

# Try to update auto-detected value
success = z.config.persistence.persist_machine("cpu_cores", 16)
# Output: [ERROR] Invalid machine config key: cpu_cores
```

---

### Example 9: Batch Updates

```python
# Update multiple machine preferences
z.config.persistence.persist_machine("browser", "Firefox")
z.config.persistence.persist_machine("ide", "cursor")
z.config.persistence.persist_machine("video_player", "VLC")

# Update multiple environment settings
z.config.persistence.persist_environment("deployment", "Development")
z.config.persistence.persist_environment("logging.level", "DEBUG")
z.config.persistence.persist_environment("performance.max_workers", 8)
```

---

### Example 10: Media App Preferences

```python
# Update media application preferences
z.config.persistence.persist_machine("audio_player", "Spotify")
z.config.persistence.persist_machine("video_player", "IINA")
z.config.persistence.persist_machine("image_viewer", "Preview")

# Verify changes
machine = z.config.get_machine()
print(f"Audio: {machine['audio_player']}")
print(f"Video: {machine['video_player']}")
print(f"Image: {machine['image_viewer']}")
```

---

## Dynamic Field Categorization

ConfigPersistence uses pattern-based categorization to automatically organize fields:

### Categories

| Category | Pattern | Examples |
|---|---|---|
| **Identity** | `os*`, `hostname`, `architecture`, `python*`, `zos*`, `processor`, `username` | os, hostname, python_version |
| **User Tools** | `browser`, `ide`, `terminal`, `shell`, `*_viewer`, `*_player`, `*_format` | browser, ide, video_player |
| **Hardware** | `cpu_*`, `memory_*`, `gpu_*` | cpu_cores, memory_gb, gpu_type |
| **Network** | `network_*` | network_primary, network_ip_local |
| **Environment** | `home`, `lang`, `timezone` | home, lang, timezone |

**Benefits:**
- Zero maintenance (new detector fields appear automatically)
- Complete visibility (shows ALL fields, not just hardcoded subset)
- Smart grouping (uses prefix patterns for logical organization)

---

## File Locations

### Machine Config

**File:** `zConfig.machine.zolo`

**Location:** 
- **macOS:** `~/Library/Application Support/zOS/zConfigs/zConfig.machine.zolo`
- **Linux:** `~/.local/share/zOS/zConfigs/zConfig.machine.zolo`
- **Windows:** `%LOCALAPPDATA%\zOS\zConfigs\zConfig.machine.zolo`

**Format:** ZOLO (string-first, type hints)

---

### Environment Config

**File:** `zConfig.environment.zolo`

**Location:**
- **macOS:** `~/Library/Application Support/zOS/zConfigs/zConfig.environment.zolo`
- **Linux:** `~/.local/share/zOS/zConfigs/zConfig.environment.zolo`
- **Windows:** `%LOCALAPPDATA%\zOS\zConfigs\zConfig.environment.zolo`

**Format:** ZOLO (string-first, type hints)

---

## Error Handling

ConfigPersistence provides clear error messages with actionable guidance:

### Invalid Key Error

```
[ERROR] Invalid machine config key: os
   Editable keys: browser, ide, terminal, shell, image_viewer, video_player, audio_player, time_format, date_format, datetime_format, cpu_cores_limit, memory_gb_limit
```

### Invalid Value Error

```
[ERROR] Invalid deployment: Prod. Must be one of: Debug, Development, Testing, Production
```

### Validation Error

```
[ERROR] cpu_cores_limit must be positive
```

### Reset Confirmation Error

```
[ERROR] Full reset requires explicit confirmation
   Use: config machine --reset [key] to reset specific key
```

---

## Success Messages

ConfigPersistence provides detailed success feedback:

```
[OK] Updated machine config: browser
   Chrome → Firefox
   Saved to: ~/.../zOS/zConfigs/zConfig.machine.zolo
```

---

## Best Practices

1. **Use Recommended Methods:**
   - **zShell commands** (recommended): `config set machine browser Firefox`
   - **Manual editing:** Edit `.zolo` files directly
   - **Programmatic API** (advanced): Use `persist_machine()` / `persist_environment()`

2. **Validation:**
   - Always validate before saving (automatic)
   - Check return value for success/failure
   - Read error messages for guidance

3. **Protected Keys:**
   - Don't try to modify auto-detected values (os, cpu_cores, etc.)
   - Use `show=True` to see which keys are editable
   - Markers: `[EDIT]` = editable, `[LOCK]` = protected

4. **Reset Safety:**
   - Reset requires explicit key (no full reset)
   - Resets to auto-detected defaults
   - Use for fixing incorrect manual edits

5. **Session Updates:**
   - Persistence updates runtime config AND session
   - Changes take effect immediately
   - No need to restart application

6. **Nested Keys:**
   - Use dot notation for nested values (e.g., "logging.level")
   - Validation works for nested keys
   - Reset works for nested keys

7. **Resource Limits:**
   - Set limits before starting resource-intensive operations
   - Validate limits are reasonable (positive integers)
   - Test limits in development before production

8. **File Format:**
   - ZOLO format (string-first, type hints)
   - Human-readable and editable
   - Consistent with zOS declarative philosophy

---

## Constants Reference

### Editable Machine Keys

Canonical SSOT: `config_constants.EDITABLE_MACHINE_KEYS` (a tuple). The persistence
module re-exports it as `_EDITABLE_MACHINE_KEYS`, and the machine module uses the
same list to decide what gets written to disk.

```python
EDITABLE_MACHINE_KEYS = (
    # User tool preferences
    "browser", "ide", "terminal", "shell",
    "image_viewer", "video_player", "audio_player",
    # Time/date preferences
    "time_format", "date_format", "datetime_format",
    # Resource allocation limits
    "cpu_cores_limit", "memory_gb_limit",
)
```

---

### Editable Environment Keys

```python
EDITABLE_ENVIRONMENT_KEYS = [
    # Basic environment settings
    "deployment", "role", "datacenter", "cluster", "node_id",
    # Network settings
    "network.host", "network.port", "network.external_host", "network.external_port",
    # Security settings
    "security.require_auth", "security.allow_anonymous", "security.ssl_enabled",
    # Logging settings
    "logging.level", "logging.format", "logging.file_enabled", "logging.file_path",
    # Performance settings
    "performance.max_workers", "performance.cache_size", "performance.cache_ttl", "performance.timeout",
]
```

---

### Valid Values

```python
VALID_DEPLOYMENTS = ["Debug", "Development", "Testing", "Production"]
DEPRECATED_DEPLOYMENTS = ["Info"]  # Mapped to Testing

VALID_ROLES = ["development", "production", "testing", "staging"]

VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
```

---

## Integration with zShell

ConfigPersistence is the backend for zShell config commands:

```bash
# zShell commands (recommended) — typed inside the zShell prompt
config set machine browser Firefox
config set env deployment Testing
config set env logging.level DEBUG

# Show current config
config show machine
config show environment
config show machine os          # single key
config show env deployment      # single key
```

Resetting to defaults is currently exposed via the programmatic API only
(`persist_machine(key, reset=True)` / `persist_environment(key, reset=True)`).

**See:** [zShell Guide](../../L3_Abstraction/zShell_GUIDE.md) for complete command reference.

---

## Advanced Usage

### Programmatic Configuration Management

```python
from zConfig_modules.config_constants import EDITABLE_MACHINE_KEYS

# Editable machine keys come from the SSOT constant
print(f"Editable machine keys: {len(EDITABLE_MACHINE_KEYS)}")
# Editable environment keys are the module-level _EDITABLE_ENVIRONMENT_KEYS list

# Validate before saving
validation = persistence._validate_machine_value("cpu_cores_limit", 4)
if validation["valid"]:
    persistence.persist_machine("cpu_cores_limit", 4)
else:
    print(f"Validation error: {validation['error']}")
```

> **Note:** the former `_get_editable_machine_keys()` / `_get_editable_environment_keys()`
> helper methods were removed — read `config_constants.EDITABLE_MACHINE_KEYS` directly.

---

### Session Integration

```python
# Persistence automatically updates session
z.config.persistence.persist_machine("browser", "Firefox")

# Session is updated immediately
print(f"Session browser: {z.session['zMachine']['browser']}")
# Output: Session browser: Firefox
```

---

### Error Handling

```python
# Check return value
success = z.config.persistence.persist_machine("browser", "Firefox")

if not success:
    print("Failed to update browser")
    # Error message already printed by persistence
else:
    print("Browser updated successfully")
```
