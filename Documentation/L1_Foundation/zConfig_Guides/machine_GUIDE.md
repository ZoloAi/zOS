# zConfig Machine Module Guide

> **Module:** `zOS/core/L1_Foundation/a_zConfig/zConfig_modules/machine/`  
> **Purpose:** Hardware detection, tool preferences, and resource limit management for zOS configuration.

---

## Overview

The `machine` module provides comprehensive machine capability detection and configuration management. It auto-detects hardware (CPU, GPU, memory, network), discovers installed tools (browser, IDE, media players), and manages resource limits (CPU cores, memory).

---

## Architecture

The machine module consists of two main components and a detection subsystem:

| Component | File | Purpose |
|---|---|---|
| `MachineConfig` | `config_machine.py` | Main configuration class (facade) |
| `ResourceLimits` | `config_resource_limits.py` | CPU/memory limit enforcement |
| **Detectors** | `detectors/` | Hardware and tool detection subsystem |

### Detection Subsystem

```
detectors/
├── __init__.py           # Public API exports
├── system.py             # Orchestration (auto_detect_machine)
├── hardware.py           # CPU, GPU, memory, network
├── browser.py            # Browser detection + launch commands
├── ide.py                # IDE/editor detection + launch commands
├── media_apps.py         # Media app orchestration
├── shared.py             # Shared utilities and constants
└── media/
    ├── audio_player.py   # Audio player detection
    ├── video_player.py   # Video player detection
    └── image_viewer.py   # Image viewer detection
```

---

## `MachineConfig`

Main facade for machine configuration. Auto-detects capabilities and loads user preferences from `zConfig.machine.zolo`.

### Initialization

```python
from zConfig_modules.machine import MachineConfig
from zConfig_modules.paths import zConfigPaths

paths = zConfigPaths()
machine_config = MachineConfig(paths, verbose=False)
```

| Parameter | Type | Description |
|---|---|---|
| `paths` | `zConfigPaths` | Path resolver instance |
| `verbose` | `bool` | Show initialization output (default: False) |

**On init, automatically:**
1. Auto-detects machine information (42+ properties)
2. Adds `user_data_dir` from paths
3. Loads user overrides from `zConfig.machine.zolo`
4. Writes **user preferences only** back to `zConfig.machine.zolo` (auto-detected
   identity is re-detected fresh each boot and never persisted — see
   [Persistence model](#persistence-model))
5. Prints ready message (if verbose or Development mode)

---

### Methods

#### `get(key: str, default=None) -> Any`

Get single machine config value by key.

```python
cpu_cores = machine_config.get("cpu_cores")
browser = machine_config.get("browser", "unknown")
```

---

#### `get_all() -> Dict[str, Any]`

Get complete machine configuration (copy).

```python
machine = machine_config.get_all()
print(f"OS: {machine['os']}")
print(f"CPU: {machine['cpu_cores']} cores")
```

---

#### `update(key: str, value: Any) -> None`

Update machine config value (runtime only, not persisted).

```python
machine_config.update("browser", "Firefox")
```

**Note:** Use `save_user_config()` to persist changes.

---

#### `save_user_config() -> bool`

Save **user preferences** to `zConfig.machine.zolo`. Only the editable keys are
written (see [Persistence model](#persistence-model)); auto-detected identity is
never persisted.

```python
machine_config.update("browser", "Firefox")
success = machine_config.save_user_config()
```

**Returns:** `True` if saved successfully, `False` on error.

---

### Persistence model

`zConfig.machine.zolo` is a **preferences file, not a machine fingerprint.** Only
the user-editable keys are ever written to disk:

```
browser, ide, terminal, shell,
image_viewer, video_player, audio_player,
time_format, date_format, datetime_format,
cpu_cores_limit, memory_gb_limit
```

> The canonical list lives in `config_constants.EDITABLE_MACHINE_KEYS` (SSOT,
> shared with `persistence/`). Both `_write_zolo_config()` (every boot) and
> `save_user_config()` write through this filter.

Everything else (`os`, `hostname`, `network_*`, `username`, `home`, `path`,
`cpu_*`, `memory_gb`, `gpu_*`, Python runtime, install info, …) is **auto-detected
fresh on every boot** and held in memory only. This means:

- The on-disk file stays tiny and stable across machines/reboots.
- No identifying fingerprint (MAC, IP, username, PATH) is committed to disk.
- Hardware changes (new RAM, GPU, network) are picked up automatically — no stale
  cached values to clear.

---

## Machine Properties

The machine config contains 42+ properties organized by category:

### System Identity

| Property | Type | Description | Editable |
|---|---|---|---|
| `os` | str | Operating system (Linux, Darwin, Windows) | 🔒 |
| `os_name` | str | Full OS name with version | 🔒 |
| `os_version` | str | Kernel release (e.g., 24.5.0) | 🔒 |
| `hostname` | str | Machine name | 🔒 |
| `architecture` | str | CPU architecture (x86_64, arm64, aarch64) | 🔒 |
| `processor` | str | CPU model/type | 🔒 |

### CPU Architecture

| Property | Type | Description | Editable |
|---|---|---|---|
| `cpu_cores` | int | Total logical CPUs (backward compatibility) | 🔒 |
| `cpu_physical` | int | Physical CPU cores | 🔒 |
| `cpu_logical` | int | Logical cores (with hyperthreading) | 🔒 |
| `cpu_performance` | int\|None | P-cores (Performance, Apple Silicon only) | 🔒 |
| `cpu_efficiency` | int\|None | E-cores (Efficiency, Apple Silicon only) | 🔒 |

### Memory

| Property | Type | Description | Editable |
|---|---|---|---|
| `memory_gb` | int\|None | Total system RAM in GB | 🔒 |

### GPU Capabilities

| Property | Type | Description | Editable |
|---|---|---|---|
| `gpu_available` | bool | GPU detected | 🔒 |
| `gpu_type` | str\|None | GPU model name | 🔒 |
| `gpu_vendor` | str\|None | GPU vendor (Apple, NVIDIA, AMD, Intel) | 🔒 |
| `gpu_memory_gb` | int\|None | GPU memory (VRAM) in GB | 🔒 |
| `gpu_compute` | list | Supported compute APIs (Metal, CUDA, ROCm) | 🔒 |

### Network

| Property | Type | Description | Editable |
|---|---|---|---|
| `network_interfaces` | list | All network interface names | 🔒 |
| `network_primary` | str\|None | Active/primary network interface | 🔒 |
| `network_ip_local` | str\|None | Local IP address (primary interface) | 🔒 |
| `network_mac_address` | str\|None | MAC address (primary interface) | 🔒 |
| `network_gateway` | str\|None | Default gateway/router IP | 🔒 |
| `network_ip_public` | str\|None | Public IP — **opt-in** via `ZOS_PUBLIC_IP_LOOKUP` (off by default); absent otherwise | 🔒 |

### User & Paths

| Property | Type | Description | Editable |
|---|---|---|---|
| `username` | str | From USER or USERNAME env var | 🔒 |
| `home` | str | User's home directory | 🔒 |
| `cwd` | str | Current working directory (safe) | 🔒 |
| `user_data_dir` | str | OS-native zOS support folder path | 🔒 |
| `path` | str | Full PATH environment variable | 🔒 |

### Development Tools

| Property | Type | Description | Editable |
|---|---|---|---|
| `browser` | str | Default browser | ✏️ |
| `ide` | str | Default IDE/editor | ✏️ |
| `terminal` | str | Terminal type (from TERM env var) | ✏️ |
| `shell` | str | Shell (bash, zsh, fish, sh) | ✏️ |

### Media Applications

| Property | Type | Description | Editable |
|---|---|---|---|
| `audio_player` | str | Default audio player | ✏️ |
| `video_player` | str | Default video player | ✏️ |
| `image_viewer` | str | Default image viewer | ✏️ |

### Python Runtime

| Property | Type | Description | Editable |
|---|---|---|---|
| `python_version` | str | Python version (3.12.0, etc.) | 🔒 |
| `python_impl` | str | Implementation (CPython, PyPy, Jython) | 🔒 |
| `python_build` | str | Build identifier | 🔒 |
| `python_compiler` | str | Compiler used to build Python | 🔒 |
| `python_executable` | str | Path to Python executable | 🔒 |
| `libc_ver` | str | System C library version (Linux-specific) | 🔒 |

### zOS Installation

| Property | Type | Description | Editable |
|---|---|---|---|
| `zcli_install_path` | str | Where zOS package is installed | 🔒 |
| `zcli_install_type` | str | editable (development) or standard | 🔒 |

### System Settings

| Property | Type | Description | Editable |
|---|---|---|---|
| `lang` | str | System locale (en_US.UTF-8, etc.) | 🔒 |
| `timezone` | str | Timezone (from TZ env var or default) | 🔒 |
| `time_format` | str | Time format default | ✏️ |
| `date_format` | str | Date format default | ✏️ |
| `datetime_format` | str | DateTime format default | ✏️ |

### Resource Limits

| Property | Type | Description | Editable |
|---|---|---|---|
| `cpu_cores_limit` | int\|None | Limit CPU cores for pools/threads | ✏️ |
| `memory_gb_limit` | int\|None | Limit RAM for caches/buffers | ✏️ |

**Legend:**
- 🔒 = Auto-detected (read-only)
- ✏️ = User-editable (tool preferences, resource limits)

---

## `ResourceLimits`

Manages CPU and memory resource limits with cross-platform support.

### Strategy

**Soft Limits (All Platforms):**
- Application voluntarily respects limits
- Queryable by multiprocessing pools, caches, etc.

**Hard Limits (Linux Only):**
- OS enforces memory limit (process killed if exceeded)
- OS binds process to specific CPU cores

### Initialization

```python
from zConfig_modules.machine import ResourceLimits

limits = ResourceLimits(machine_config.machine)
result = limits.apply()
```

**Returns:**
```python
{
    "cpu_limit": 4,
    "memory_limit_gb": 8,
    "soft_limits_applied": True,
    "hard_limits_applied": True,  # Linux only
    "platform": "Linux",
    "errors": []
}
```

---

### Methods

#### `apply() -> Dict[str, Any]`

Apply resource limits (soft on all platforms, hard on Linux).

```python
result = limits.apply()
print(f"CPU limit: {result['cpu_limit']} cores")
print(f"Memory limit: {result['memory_limit_gb']} GB")
```

---

#### `get_cpu_limit() -> int`

Get effective CPU core limit.

```python
max_workers = limits.get_cpu_limit()
pool = multiprocessing.Pool(processes=max_workers)
```

**Returns:** User-specified limit if set, otherwise detected cores.

---

#### `get_memory_limit_gb() -> int`

Get effective memory limit in GB.

```python
memory_limit_gb = limits.get_memory_limit_gb()
cache_size = int(memory_limit_gb * 0.25 * 1024**3)  # 25% of limit
```

**Returns:** User-specified limit if set, otherwise detected memory.

---

#### `get_memory_limit_bytes() -> int`

Get effective memory limit in bytes.

```python
memory_bytes = limits.get_memory_limit_bytes()
```

---

#### `get_status() -> Dict[str, Any]`

Get current resource limits status.

```python
status = limits.get_status()
# {
#     "cpu_cores_available": 8,
#     "cpu_cores_limit": 4,
#     "cpu_cores_effective": 4,
#     "memory_gb_available": 16,
#     "memory_gb_limit": 8,
#     "memory_gb_effective": 8,
#     "applied": True,
#     "platform": "Linux",
#     "hard_limits_supported": True,
#     "hard_limits_applied": True
# }
```

---

## Detection Subsystem

The `detectors/` package provides modular detection functions organized by category.

### System Orchestration (`system.py`)

#### `auto_detect_machine(log_level=None, is_production=False) -> Dict[str, Any]`

Main orchestration function. Detects all machine properties.

```python
from zConfig_modules.machine.detectors import auto_detect_machine

machine = auto_detect_machine(log_level="INFO", is_production=False)
```

**Returns:** Dictionary with 42+ machine properties.

---

#### `detect_zcli_install_info() -> Dict[str, str]`

Detect zOS installation path and type.

```python
info = detect_zcli_install_info()
# {
#     "python_executable": "/usr/bin/python3",
#     "zcli_install_path": "/usr/local/lib/python3.12/site-packages",
#     "zcli_install_type": "standard"  # or "editable"
# }
```

---

#### `create_user_machine_config(path, machine, verbose=False) -> None`

Create `zConfig.machine.zolo` with auto-detected values.

```python
from pathlib import Path

path = Path("~/.config/zOS/zConfigs/zConfig.machine.zolo").expanduser()
create_user_machine_config(path, machine, verbose=True)
```

---

### Hardware Detection (`hardware.py`)

#### `detect_memory_gb() -> Optional[int]`

Detect system memory in GB via psutil or platform-specific methods.

```python
memory_gb = detect_memory_gb()
# 16 (GB)
```

**Methods:** psutil → /proc/meminfo (Linux) → sysctl (macOS)

---

#### `detect_cpu_architecture() -> Dict[str, Any]`

Detect detailed CPU architecture.

```python
cpu_arch = detect_cpu_architecture()
# {
#     "cpu_physical": 8,
#     "cpu_logical": 8,
#     "cpu_performance": 4,  # P-cores (Apple Silicon)
#     "cpu_efficiency": 4    # E-cores (Apple Silicon)
# }
```

**Apple Silicon detection:**
- Tries `sysctl hw.perflevel0.logicalcpu` / `hw.perflevel1.logicalcpu`
- Falls back to known configurations (M1/M2: 4+4, M1 Pro: 8+2, M2 Pro: 8+4)

---

#### `detect_gpu(system_memory_gb=None) -> Dict[str, Any]`

Detect GPU information (type, vendor, memory, compute APIs).

```python
gpu_info = detect_gpu(system_memory_gb=16)
# {
#     "gpu_available": True,
#     "gpu_type": "Apple M1",
#     "gpu_vendor": "Apple",
#     "gpu_memory_gb": 16,  # Unified memory
#     "gpu_compute": ["Metal"]
# }
```

**Platform-specific:**
- **macOS:** `system_profiler SPDisplaysDataType`, unified memory for Apple Silicon
- **Linux:** `nvidia-smi` (NVIDIA), `rocm-smi` (AMD)
- **Windows:** `wmic path win32_VideoController`

---

#### `detect_network() -> Dict[str, Any]`

Detect network interfaces and IP addresses (6 essential properties).

```python
network_info = detect_network()
# {
#     "network_interfaces": ["en0", "en1"],
#     "network_primary": "en0",
#     "network_ip_local": "192.168.1.100",
#     "network_mac_address": "00:11:22:33:44:55",
#     "network_gateway": "192.168.1.1",
#     "network_ip_public": "203.0.113.1"  # only when ZOS_PUBLIC_IP_LOOKUP is enabled
# }
```

**Methods:**
- **macOS/Linux:** `ifconfig` for interfaces/IPs, `netstat -rn` for gateway
- **Windows:** `ipconfig /all`, `route print`
- **Public IP:** `https://api.ipify.org` — **opt-in only.** Skipped unless env
  `ZOS_PUBLIC_IP_LOOKUP` ∈ {`1`,`true`,`yes`,`on`}. Off by default (privacy +
  offline-friendly + no boot-time network dependency). 2s timeout when enabled.

**Note:** Avoids `psutil.net_if_addrs()` due to known memory corruption bugs.

---

### Browser Detection (`browser.py`)

#### `detect_browser(log_level=None, is_production=False) -> str`

Detect default browser via env var or platform-specific methods.

```python
browser = detect_browser()
# "Chrome", "Firefox", "Safari", "Arc", "Brave", "Edge", "Opera"
```

**Detection priority:**
1. `$BROWSER` environment variable
2. **macOS:** LaunchServices database (`defaults read`)
3. **Linux:** `xdg-settings` → PATH search
4. **Windows:** Default to "Edge"

---

#### `get_browser_launch_command(browser_name: str) -> tuple`

Get platform-specific command to launch a browser.

```python
cmd, args = get_browser_launch_command("Firefox")
# macOS: ("open", ["-a", "Firefox"])
# Linux: ("firefox", [])
# Windows: ("firefox", [])
```

---

### IDE Detection (`ide.py`)

#### `detect_ide(log_level=None, is_production=False) -> str`

Detect IDE/editor via env vars or PATH search.

```python
ide = detect_ide()
# "cursor", "code", "subl", "vim", "nano"
```

**Detection priority:**
1. Environment variables: `$IDE`, `$VISUAL_EDITOR`, `$EDITOR`, `$VISUAL`
2. Modern IDEs: cursor, code, fleet, zed
3. Classic IDEs: subl, atom, webstorm, pycharm, idea
4. Simple editors: nano, vim, nvim, vi
5. Fallback: "nano"

---

#### `get_ide_launch_command(ide_name: str) -> tuple`

Get platform-specific command to launch an IDE.

```python
cmd, args = get_ide_launch_command("cursor")
# macOS: ("open", ["-a", "Cursor"])
# Linux: ("cursor", [])
# Windows: ("cursor", [])
```

---

### Media Apps Detection (`media_apps.py`)

Orchestrates detection of audio players, video players, and image viewers.

#### `detect_audio_player(log_level=None, is_production=False) -> str`

Detect default audio player.

```python
audio_player = detect_audio_player()
# "VLC", "iTunes", "Spotify", "Rhythmbox", "Audacious"
```

---

#### `detect_video_player(log_level=None, is_production=False) -> str`

Detect default video player.

```python
video_player = detect_video_player()
# "VLC", "QuickTime Player", "mpv", "IINA", "Celluloid"
```

---

#### `detect_image_viewer(log_level=None, is_production=False) -> str`

Detect default image viewer.

```python
image_viewer = detect_image_viewer()
# "Preview", "Eye of GNOME", "Eye of MATE", "gThumb", "Gwenview"
```

---

## Practical Examples

### Example 1: Basic Machine Detection

```python
from zConfig_modules.machine import MachineConfig
from zConfig_modules.paths import zConfigPaths

paths = zConfigPaths()
machine_config = MachineConfig(paths, verbose=True)

# Access properties
print(f"OS: {machine_config.get('os')}")
print(f"CPU: {machine_config.get('cpu_cores')} cores")
print(f"RAM: {machine_config.get('memory_gb')} GB")
print(f"Browser: {machine_config.get('browser')}")
```

---

### Example 2: Resource Limits

```python
from zConfig_modules.machine import MachineConfig, ResourceLimits
from zConfig_modules.paths import zConfigPaths

# Initialize
paths = zConfigPaths()
machine_config = MachineConfig(paths)

# Set limits (edit zConfig.machine.zolo manually or via code)
machine_config.update("cpu_cores_limit", 4)
machine_config.update("memory_gb_limit", 8)
machine_config.save_user_config()

# Apply limits
limits = ResourceLimits(machine_config.machine)
result = limits.apply()

print(f"CPU limit: {result['cpu_limit']} cores")
print(f"Memory limit: {result['memory_limit_gb']} GB")
print(f"Hard limits applied: {result['hard_limits_applied']}")
```

---

### Example 3: Multiprocessing with Resource Limits

```python
import multiprocessing
from zConfig_modules.machine import ResourceLimits

limits = ResourceLimits(machine_config.machine)
limits.apply()

# Use effective CPU limit for pool
max_workers = limits.get_cpu_limit()
pool = multiprocessing.Pool(processes=max_workers)

# Use pool...
```

---

### Example 4: Custom Tool Preferences

```python
# Update tool preferences
machine_config.update("browser", "Firefox")
machine_config.update("ide", "cursor")
machine_config.update("video_player", "VLC")

# Save to zConfig.machine.zolo
machine_config.save_user_config()

# Verify
print(f"Browser: {machine_config.get('browser')}")
print(f"IDE: {machine_config.get('ide')}")
```

---

### Example 5: GPU Detection

```python
machine = machine_config.get_all()

if machine['gpu_available']:
    print(f"GPU: {machine['gpu_type']}")
    print(f"Vendor: {machine['gpu_vendor']}")
    print(f"Memory: {machine['gpu_memory_gb']} GB")
    print(f"Compute: {', '.join(machine['gpu_compute'])}")
else:
    print("No GPU detected")
```

---

### Example 6: Network Information

```python
machine = machine_config.get_all()

print(f"Primary interface: {machine['network_primary']}")
print(f"Local IP: {machine['network_ip_local']}")
print(f"MAC address: {machine['network_mac_address']}")
print(f"Gateway: {machine['network_gateway']}")
# network_ip_public is only present when ZOS_PUBLIC_IP_LOOKUP is enabled
print(f"Public IP: {machine.get('network_ip_public')}")
```

---

### Example 7: Launch Browser Programmatically

```python
import subprocess
from zConfig_modules.machine.detectors import get_browser_launch_command

browser = machine_config.get("browser")
cmd, args = get_browser_launch_command(browser)

if cmd:
    subprocess.run([cmd] + args + ["https://example.com"])
```

---

### Example 8: Apple Silicon Detection

```python
machine = machine_config.get_all()

if machine['architecture'] == 'arm64':
    print(f"Apple Silicon detected")
    print(f"P-cores: {machine['cpu_performance']}")
    print(f"E-cores: {machine['cpu_efficiency']}")
    print(f"Total: {machine['cpu_physical']} physical cores")
```

---

## Configuration File Format

`zConfig.machine.zolo` is a **preferences-only** file (ZOLO format). It contains
*only* the user-editable keys — auto-detected identity/hardware is never written
(see [Persistence model](#persistence-model)). A typical file looks like:

```zolo
zMachine:
    browser: Chrome
    ide: cursor
    terminal: xterm-256color
    shell: /bin/zsh
    image_viewer: Preview
    video_player: QuickTime Player
    audio_player: Music
    time_format: HH:MM:SS
    date_format: ddmmyyyy
    datetime_format: ddmmyyyy HH:MM:SS
    # optional resource caps (omit to use detected values)
    cpu_cores_limit: 4
    memory_gb_limit: 8
```

> Auto-detected fields (`os`, `cpu_*`, `memory_gb`, `gpu_*`, `network_*`, Python
> runtime, …) are available at runtime via `machine_config.get(...)` but do **not**
> appear in this file.

**Editing:**
1. Manual: Edit `zConfig.machine.zolo` in your zConfigs dir (Linux: `~/.config/zOS/zConfigs/`; macOS: `~/Library/Application Support/zOS/zConfigs/`)
2. Programmatic: Use `machine_config.update()` + `save_user_config()`
3. zShell: `config set machine browser Firefox` (recommended)

---

## Best Practices

1. **Resource Limits:**
   - Set `cpu_cores_limit` for containers/VMs to prevent oversubscription
   - Set `memory_gb_limit` for cache-heavy applications
   - Test limits in staging before production

2. **Tool Detection:**
   - Override auto-detected tools if needed (browser, IDE, media players)
   - Use launch command functions for cross-platform compatibility

3. **GPU Detection:**
   - Check `gpu_available` before GPU operations
   - Apple Silicon: `gpu_memory_gb` includes unified memory (all system RAM)
   - NVIDIA: Verify CUDA availability via `gpu_compute`

4. **Network Detection:**
   - `network_ip_public` is **off by default** — set `ZOS_PUBLIC_IP_LOOKUP=1` to
     enable the (optional, 2s-timeout) outbound lookup; otherwise the key is absent
   - Use `network_ip_local` for local network operations
   - `network_gateway` useful for network diagnostics

5. **Performance:**
   - Detection runs once at initialization (cached in memory)
   - Avoid calling `auto_detect_machine()` repeatedly
   - Use `machine_config.get()` for fast property access
