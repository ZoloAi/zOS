# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/detectors/system.py
"""Main orchestrator for machine detection and configuration file generation."""

from zOS import logging, sys, os, platform, socket, Path, Dict, Any, Optional, distribution, PackageNotFoundError
from .shared import (
    _log_config, _log_error, _safe_getcwd,
    DEFAULT_SHELL, DEFAULT_TIMEZONE,
    DEFAULT_TIME_FORMAT, DEFAULT_DATE_FORMAT, DEFAULT_DATETIME_FORMAT,
)
from .browser import detect_browser
from .ide import detect_ide
from .media_apps import (
    detect_image_viewer,
    detect_video_player,
    detect_audio_player,
)
from .hardware import (
    detect_memory_gb,
    detect_cpu_architecture,
    detect_gpu,
    detect_network,
)

# Module-level logger
logger = logging.getLogger(__name__)



def detect_zcli_install_info() -> Dict[str, str]:
    """Detect zOS installation path and type."""
    try:
        dist = distribution("zOS")

        # Get installation path
        if dist.files:
            # Get the first file's parent to find site-packages location
            first_file = next(iter(dist.files))
            install_path = str(first_file.locate().parent.parent.resolve())
        else:
            install_path = "unknown"

        # Determine install type (editable vs standard)
        try:
            direct_url = dist.read_text('direct_url.json')
            install_type = "editable" if direct_url and "editable" in direct_url else "standard"
        except (FileNotFoundError, KeyError):
            # Alternative check: if install path contains the package name at root level
            install_type = "editable" if "zOS" in install_path and "site-packages" not in install_path else "standard"

        return {
            "python_executable": sys.executable,
            "zcli_install_path": install_path,
            "zcli_install_type": install_type
        }
    except (PackageNotFoundError, Exception):
        # zCLI not installed or error detecting
        return {
            "python_executable": sys.executable,
            "zcli_install_path": "not_installed",
            "zcli_install_type": "unknown"
        }


def create_user_machine_config(path: Path, machine: Dict[str, Any], verbose: bool = False) -> None:
    """Create zConfig.machine.zolo with auto-detected values and user-editable preferences.
    
    Args:
        path: Path to create config file at
        machine: Machine data dictionary
        verbose: If True, show creation messages (default: False)
    """
    try:
        from zlsp.parser.basic.serializer import dumps as zolo_dumps

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        content = zolo_dumps({"zMachine": machine}) + '\n'
        path.write_text(content, encoding="utf-8")
        _log_config(f"Created user machine config: {path}", verbose=verbose)
        _log_config("You can edit this file to customize tool preferences", verbose=verbose)

    except Exception as e:
        if verbose:
            _log_error(f"Failed to create user machine config: {e}")


def detect_supports_emoji() -> bool:
    """Detect whether the terminal can safely render emoji / pictographs.

    Drives the SSOT emoji gate (zSys.accessibility.terminal_gate). Conservative:
    requires a UTF-8 stdout encoding, then trusts macOS/Linux; on Windows only
    modern terminals (Windows Terminal / VS Code) are trusted. User-overridable
    via ``supports_emoji`` in zConfig.machine.zolo.
    """
    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    if "utf" not in enc:
        return False
    osname = platform.system()
    if osname in ("Darwin", "Linux"):
        return True
    if osname == "Windows":
        return bool(
            os.environ.get("WT_SESSION")
            or os.environ.get("WT_PROFILE_ID")
            or os.environ.get("TERM_PROGRAM") == "vscode"
        )
    return False


def auto_detect_machine(log_level: Optional[str] = None, is_production: bool = False) -> Dict[str, Any]:
    """Auto-detect machine identity, Python runtime, tools, and capabilities."""
    if not is_production:
        logger.debug("[MachineConfig] Auto-detecting machine information...")

    # Detect zCLI installation info
    zcli_info = detect_zcli_install_info()

    # Detect CPU architecture details
    cpu_arch = detect_cpu_architecture()

    # Detect memory first (needed for Apple Silicon GPU unified memory)
    system_memory_gb = detect_memory_gb()

    # Detect GPU information (pass system memory for unified memory calculation)
    gpu_info = detect_gpu(system_memory_gb=system_memory_gb)

    # Detect network interfaces and IPs
    network_info = detect_network()

    # Detect libc version (Linux-specific, handle Windows Store Python edge case)
    try:
        libc_ver = platform.libc_ver()[0]
    except (OSError, PermissionError):
        # Windows Store Python or other restricted environments
        libc_ver = ""

    # Canonical OS/arch identity — one vocabulary across the whole codebase
    from zSys.platform_identity import current_os, normalized_arch, zguard_platform_tag

    machine = {
        # Identity
        "os": platform.system(),                    # Linux, Darwin, Windows
        "os_family": current_os(),                  # canonical: darwin, linux, windows
        "os_version": platform.release(),           # Kernel version
        "os_name": platform.platform(),             # Full OS name with version
        "hostname": socket.gethostname(),           # Machine name
        "architecture": platform.machine(),         # raw: x86_64, arm64, AMD64, aarch64...
        "arch": normalized_arch(),                  # canonical: arm64, x86_64, i686
        "platform_tag": zguard_platform_tag() or "unsupported",  # e.g. darwin-arm64
        "processor": platform.processor(),          # CPU type
        "python_version": platform.python_version(), # 3.12.0
        "python_impl": platform.python_implementation(), # CPython, PyPy, etc.
        "python_build": platform.python_build()[0],  # Build info
        "python_compiler": platform.python_compiler(), # Compiler used
        "libc_ver": libc_ver,                       # libc version (Linux-specific)
        "python_executable": zcli_info["python_executable"],  # Path to Python executable
        "zcli_install_path": zcli_info["zcli_install_path"],  # Where zCLI is installed
        "zcli_install_type": zcli_info["zcli_install_type"],  # editable vs standard

        # User tools (system defaults, user can override)
        "browser": detect_browser(log_level, is_production),
        "ide": detect_ide(log_level, is_production),
        "image_viewer": detect_image_viewer(log_level, is_production),
        "video_player": detect_video_player(log_level, is_production),
        "audio_player": detect_audio_player(log_level, is_production),
        "terminal": os.getenv("TERM", "unknown"),
        "supports_emoji": detect_supports_emoji(),   # SSOT for the emoji output gate
        "shell": os.getenv("SHELL", DEFAULT_SHELL),
        "lang": os.getenv("LANG", "unknown"),       # System language
        "timezone": os.getenv("TZ", DEFAULT_TIMEZONE),      # Timezone if set
        "time_format": DEFAULT_TIME_FORMAT,         # Time format default
        "date_format": DEFAULT_DATE_FORMAT,         # Date format default
        "datetime_format": DEFAULT_DATETIME_FORMAT, # DateTime format default
        "home": str(Path.home()),                   # User's home directory

        # System capabilities
        "cpu_cores": os.cpu_count() or 1,           # Total logical CPUs (backward compatibility)
        "cpu_physical": cpu_arch["cpu_physical"],   # Physical cores
        "cpu_logical": cpu_arch["cpu_logical"],     # Logical cores (with hyperthreading)
        "cpu_performance": cpu_arch["cpu_performance"],  # P-cores (Apple Silicon)
        "cpu_efficiency": cpu_arch["cpu_efficiency"],    # E-cores (Apple Silicon)
        "memory_gb": system_memory_gb,              # Total system RAM (already detected)

        # GPU capabilities
        "gpu_available": gpu_info["gpu_available"],
        "gpu_type": gpu_info["gpu_type"],
        "gpu_vendor": gpu_info["gpu_vendor"],
        "gpu_memory_gb": gpu_info["gpu_memory_gb"],
        "gpu_compute": gpu_info["gpu_compute"],

        # Network interfaces
        "network_interfaces": network_info["network_interfaces"],
        "network_primary": network_info["network_primary"],
        "network_ip_local": network_info["network_ip_local"],
        "network_mac_address": network_info["network_mac_address"],
        "network_gateway": network_info["network_gateway"],
        "network_ip_public": network_info["network_ip_public"],

        "cwd": _safe_getcwd(),                     # Current working directory (safe)
        "username": os.getenv("USER") or os.getenv("USERNAME", "unknown"),
        "path": os.getenv("PATH", ""),             # System PATH
    }

    if not is_production:
        logger.debug(
            "[MachineConfig] Identity: %s (%s) on %s",
            machine['hostname'], machine['username'], machine['os_name']
        )
        cpu_info = f"{machine['cpu_physical']} physical, {machine['cpu_logical']} logical"
        if machine['cpu_performance'] and machine['cpu_efficiency']:
            cpu_info += f" ({machine['cpu_performance']} P-cores, {machine['cpu_efficiency']} E-cores)"
        logger.debug("[MachineConfig] CPU: %s, %s cores", machine['processor'], cpu_info)
        logger.debug("[MachineConfig] RAM: %sGB", machine['memory_gb'])
        if machine['gpu_available']:
            gpu_mem = f", {machine['gpu_memory_gb']}GB" if machine['gpu_memory_gb'] else ""
            gpu_compute = f", {', '.join(machine['gpu_compute'])}" if machine['gpu_compute'] else ""
            logger.debug("[MachineConfig] GPU: %s%s%s", machine['gpu_type'], gpu_mem, gpu_compute)
        if machine['network_primary']:
            network_ip = machine['network_ip_local'] or "no IP"
            logger.debug("[MachineConfig] Network: %s (%s)", machine['network_primary'], network_ip)
        logger.debug(
            "[MachineConfig] Python: %s %s on %s",
            machine['python_impl'], machine['python_version'], machine['architecture']
        )

    return machine
