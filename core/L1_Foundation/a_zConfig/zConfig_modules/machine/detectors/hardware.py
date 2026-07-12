# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/detectors/hardware.py
"""Hardware detection (CPU, GPU, memory, network) for zCLI machine configuration."""

from zOS import os, platform, subprocess, importlib, Dict, Any, Optional
from .shared import BYTES_PER_GB, KB_PER_MB, MB_PER_GB


def detect_memory_gb() -> Optional[int]:
    """Detect system memory in GB via psutil or platform-specific methods."""
    # Try psutil first (most reliable, cross-platform)
    try:
        psutil = importlib.import_module("psutil")
        memory_bytes = psutil.virtual_memory().total
        return int(memory_bytes / BYTES_PER_GB)
    except Exception:
        pass  # Fall through to platform-specific methods

    # Platform-specific fallbacks
    try:
        system = platform.system()

        # Linux: read from /proc/meminfo
        if system == "Linux":
            with open("/proc/meminfo", encoding='utf-8') as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return int(kb / (KB_PER_MB * MB_PER_GB))

        # macOS: use sysctl
        elif system == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                memory_bytes = int(result.stdout.strip())
                return int(memory_bytes / BYTES_PER_GB)
    except Exception:
        pass  # Silent fail - memory detection is optional

    # Couldn't detect
    return None


def detect_cpu_architecture() -> Dict[str, Any]:
    """Detect detailed CPU architecture (physical, logical, P-cores, E-cores)."""
    result: Dict[str, Any] = {
        "cpu_physical": None,
        "cpu_logical": None,
        "cpu_performance": None,
        "cpu_efficiency": None,
    }

    system = platform.system()

    try:
        # Try psutil first (cross-platform)
        psutil = importlib.import_module("psutil")
        result["cpu_logical"] = psutil.cpu_count(logical=True)
        result["cpu_physical"] = psutil.cpu_count(logical=False)
    except Exception:
        pass

    # Fallback to os.cpu_count() for logical
    if result["cpu_logical"] is None:
        result["cpu_logical"] = os.cpu_count() or 1

    # Platform-specific detection
    try:
        if system == "Darwin":
            # macOS: use sysctl for detailed info
            phys_result = subprocess.run(
                ["sysctl", "-n", "hw.physicalcpu"],
                capture_output=True, text=True, check=False, timeout=2
            )
            if phys_result.returncode == 0:
                result["cpu_physical"] = int(phys_result.stdout.strip())

            # Fallback for physical cores (needed before Apple Silicon detection)
            if result["cpu_physical"] is None:
                result["cpu_physical"] = result["cpu_logical"]

            # Apple Silicon: try to detect P-cores and E-cores.
            # Normalized arch — platform.machine() can report "aarch64" too.
            from zSys.platform_identity import normalized_arch
            if normalized_arch() == "arm64" and result["cpu_physical"]:
                detected = False
                try:
                    # Try to get performance level counts (macOS 12+)
                    perf0_result = subprocess.run(
                        ["sysctl", "-n", "hw.perflevel0.logicalcpu"],
                        capture_output=True, text=True, check=False, timeout=2
                    )
                    perf1_result = subprocess.run(
                        ["sysctl", "-n", "hw.perflevel1.logicalcpu"],
                        capture_output=True, text=True, check=False, timeout=2
                    )

                    if perf0_result.returncode == 0 and perf1_result.returncode == 0:
                        perf0 = int(perf0_result.stdout.strip())
                        perf1 = int(perf1_result.stdout.strip())
                        # Higher count is typically P-cores
                        result["cpu_performance"] = max(perf0, perf1)
                        result["cpu_efficiency"] = min(perf0, perf1)
                        detected = True
                except Exception:
                    pass

                # Fallback: Known Apple Silicon configurations
                if not detected:
                    total = result["cpu_physical"]
                    if total == 8:
                        # M1, M2: 4 P-cores + 4 E-cores
                        result["cpu_performance"] = 4
                        result["cpu_efficiency"] = 4
                    elif total == 10:
                        # M1 Pro, M2 Pro (10-core): 8 P-cores + 2 E-cores
                        result["cpu_performance"] = 8
                        result["cpu_efficiency"] = 2
                    elif total == 12:
                        # M2 Pro (12-core): 8 P-cores + 4 E-cores
                        result["cpu_performance"] = 8
                        result["cpu_efficiency"] = 4

        elif system == "Linux":
            # Linux: read from /sys or lscpu
            if result["cpu_physical"] is None:
                try:
                    lscpu_result = subprocess.run(
                        ["lscpu", "-p=cpu"],
                        capture_output=True, text=True, check=False, timeout=2
                    )
                    if lscpu_result.returncode == 0:
                        cores = [line for line in lscpu_result.stdout.split('\n') if line and not line.startswith('#')]
                        result["cpu_physical"] = len(cores)
                except Exception:
                    pass

    except Exception:
        pass  # Silent fail

    # Final fallback if still None (for non-Darwin systems)
    if result["cpu_physical"] is None:
        result["cpu_physical"] = result["cpu_logical"]

    return result


def detect_gpu(system_memory_gb: Optional[int] = None) -> Dict[str, Any]:
    """Detect GPU information (type, vendor, memory, compute APIs).
    
    Args:
        system_memory_gb: Total system RAM (for Apple Silicon unified memory)
    """
    result: Dict[str, Any] = {
        "gpu_available": False,
        "gpu_type": None,
        "gpu_vendor": None,
        "gpu_memory_gb": None,
        "gpu_compute": [],
    }

    system = platform.system()

    try:
        if system == "Darwin":
            # macOS: use system_profiler
            profiler_result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True, text=True, check=False, timeout=5
            )

            if profiler_result.returncode == 0:
                output = profiler_result.stdout

                # Look for GPU info
                if "Chipset Model:" in output:
                    result["gpu_available"] = True

                    # Extract GPU model
                    for line in output.split('\n'):
                        if "Chipset Model:" in line:
                            result["gpu_type"] = line.split(":", 1)[1].strip()
                        elif "Vendor:" in line:
                            vendor = line.split(":", 1)[1].strip()
                            # Clean up vendor name
                            if "Apple" in vendor or "Apple" in result.get("gpu_type", ""):
                                result["gpu_vendor"] = "Apple"
                            elif "NVIDIA" in vendor:
                                result["gpu_vendor"] = "NVIDIA"
                            elif "AMD" in vendor or "ATI" in vendor:
                                result["gpu_vendor"] = "AMD"
                            elif "Intel" in vendor:
                                result["gpu_vendor"] = "Intel"
                        elif "VRAM (Dynamic, Max):" in line or "VRAM (Total):" in line:
                            # Discrete GPU VRAM
                            memory_str = line.split(":", 1)[1].strip()
                            if "GB" in memory_str:
                                result["gpu_memory_gb"] = int(memory_str.split()[0])
                            elif "MB" in memory_str:
                                result["gpu_memory_gb"] = int(memory_str.split()[0]) // 1024

                # Apple Silicon: unified memory (GPU can access all system RAM)
                if result["gpu_vendor"] == "Apple" and result["gpu_memory_gb"] is None:
                    if system_memory_gb:
                        # Use provided system memory (from detect_memory_gb())
                        result["gpu_memory_gb"] = system_memory_gb
                    else:
                        # Fallback: try sysctl if system_memory_gb not provided
                        try:
                            mem_result = subprocess.run(
                                ["sysctl", "-n", "hw.memsize"],
                                capture_output=True, text=True, check=False, timeout=2
                            )
                            if mem_result.returncode == 0:
                                total_ram_gb = int(mem_result.stdout.strip()) // BYTES_PER_GB
                                result["gpu_memory_gb"] = total_ram_gb
                        except Exception:
                            pass

                # Detect compute APIs
                if result["gpu_available"]:
                    # Metal is available on all modern macOS GPUs
                    result["gpu_compute"].append("Metal")

        elif system == "Linux":
            # Linux: try nvidia-smi for NVIDIA, rocm-smi for AMD

            # Check NVIDIA
            nvidia_result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, check=False, timeout=3
            )
            if nvidia_result.returncode == 0 and nvidia_result.stdout.strip():
                result["gpu_available"] = True
                result["gpu_vendor"] = "NVIDIA"
                parts = nvidia_result.stdout.strip().split(',')
                result["gpu_type"] = parts[0].strip()
                if len(parts) > 1:
                    memory_str = parts[1].strip()
                    result["gpu_memory_gb"] = int(memory_str.split()[0]) // 1024
                result["gpu_compute"].append("CUDA")

            # Check AMD ROCm
            if not result["gpu_available"]:
                rocm_result = subprocess.run(
                    ["rocm-smi", "--showproductname"],
                    capture_output=True, text=True, check=False, timeout=3
                )
                if rocm_result.returncode == 0 and "GPU" in rocm_result.stdout:
                    result["gpu_available"] = True
                    result["gpu_vendor"] = "AMD"
                    result["gpu_compute"].append("ROCm")

        elif system == "Windows":
            # Windows: CIM via PowerShell (wmic was removed in Windows 11 24H2+);
            # fall back to wmic for older systems.
            gpu_name, gpu_ram_bytes = _detect_windows_gpu()
            if gpu_name:
                result["gpu_available"] = True
                result["gpu_type"] = gpu_name
                if gpu_ram_bytes:
                    result["gpu_memory_gb"] = gpu_ram_bytes // BYTES_PER_GB

                if "NVIDIA" in gpu_name:
                    result["gpu_vendor"] = "NVIDIA"
                    result["gpu_compute"].append("CUDA")
                elif "AMD" in gpu_name or "Radeon" in gpu_name:
                    result["gpu_vendor"] = "AMD"
                elif "Intel" in gpu_name:
                    result["gpu_vendor"] = "Intel"

    except Exception:
        pass  # Silent fail - GPU detection is optional

    return result


def _detect_windows_gpu() -> tuple:
    """(name, adapter_ram_bytes) of the first video controller, via CIM then wmic."""
    # PowerShell CIM — present on every supported Windows; wmic is not (24H2+).
    try:
        ps_result = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                "(Get-CimInstance Win32_VideoController | "
                "Select-Object -First 1 Name,AdapterRAM | "
                "ForEach-Object { \"$($_.Name)|$($_.AdapterRAM)\" })",
            ],
            capture_output=True, text=True, check=False, timeout=10
        )
        if ps_result.returncode == 0 and "|" in ps_result.stdout:
            name, _, ram = ps_result.stdout.strip().partition("|")
            try:
                return name.strip(), int(ram.strip())
            except ValueError:
                return name.strip(), None
    except Exception:
        pass

    try:
        wmic_result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name,AdapterRAM"],
            capture_output=True, text=True, check=False, timeout=3
        )
        if wmic_result.returncode == 0:
            lines = [line.strip() for line in wmic_result.stdout.split('\n') if line.strip()]
            if len(lines) > 1:  # skip header
                parts = lines[1].rsplit(None, 1)
                if len(parts) == 2:
                    try:
                        return parts[0], int(parts[1])
                    except ValueError:
                        return parts[0], None
                return lines[1], None
    except Exception:
        pass
    return None, None


def _socket_local_ip() -> Optional[str]:
    """Local IP of the default-route interface via a no-traffic UDP connect.

    Cross-platform and subprocess-free: connect() on a UDP socket only does a
    route lookup — no packet is sent. Returns None when there is no route
    (fully offline machine).
    """
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None


def _detect_network_ip_cmd(result: Dict[str, Any]) -> None:
    """Linux: fill interfaces/primary/ip/mac from iproute2's `ip` command."""
    ip_result = subprocess.run(
        ["ip", "-o", "addr", "show", "up"],
        capture_output=True, text=True, check=False, timeout=3
    )
    if ip_result.returncode != 0:
        return
    # One line per address: "2: eth0    inet 10.0.0.5/24 brd ... scope global ..."
    for line in ip_result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[2] != "inet":
            continue
        iface = parts[1].split("@")[0]  # veth pairs report eth0@if12
        if iface.startswith("lo"):
            continue
        if iface not in result["network_interfaces"]:
            result["network_interfaces"].append(iface)
        if result["network_primary"] is None:
            result["network_primary"] = iface
            result["network_ip_local"] = parts[3].split("/")[0]
            # MAC for the chosen interface
            mac_result = subprocess.run(
                ["ip", "-o", "link", "show", iface],
                capture_output=True, text=True, check=False, timeout=3
            )
            if mac_result.returncode == 0 and "link/ether" in mac_result.stdout:
                tokens = mac_result.stdout.split()
                result["network_mac_address"] = tokens[tokens.index("link/ether") + 1]


def _detect_network_windows(result: Dict[str, Any]) -> None:
    """Windows: fill interfaces/primary/ip/mac/gateway by parsing `ipconfig /all`."""
    ipconfig_result = subprocess.run(
        ["ipconfig", "/all"],
        capture_output=True, text=True, check=False, timeout=5
    )
    if ipconfig_result.returncode != 0:
        return

    current_iface = None
    current_ip = None
    current_mac = None
    current_gateway = None

    def _flush():
        if not current_iface:
            return
        result["network_interfaces"].append(current_iface)
        if result["network_primary"] is None and current_ip:
            result["network_primary"] = current_iface
            result["network_ip_local"] = current_ip
            result["network_mac_address"] = current_mac
            if current_gateway:
                result["network_gateway"] = current_gateway

    for raw in ipconfig_result.stdout.splitlines():
        line = raw.rstrip()
        # Adapter headers are unindented: "Ethernet adapter Ethernet:"
        if line and not line[0].isspace() and line.endswith(":") and "adapter" in line.lower():
            _flush()
            current_iface = line.rstrip(":").split("adapter", 1)[-1].strip()
            current_ip = current_mac = current_gateway = None
            continue
        stripped = line.strip()
        if ":" not in stripped or current_iface is None:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip(". ").lower()
        value = value.strip().replace("(Preferred)", "").strip()
        if key.startswith("ipv4 address") and value:
            current_ip = value
        elif key == "physical address" and value:
            current_mac = value.replace("-", ":").lower()
        elif key == "default gateway" and value and "." in value:
            current_gateway = value
    _flush()


def detect_network() -> Dict[str, Any]:
    """Detect network interfaces and IP addresses.
    
    Note: psutil.net_if_addrs() has known memory corruption bugs on some systems.
    We use platform-specific methods (ifconfig, netstat, ip) for reliability.
    
    Returns 6 essential properties:
      - network_interfaces: List of all interface names
      - network_primary: Active interface name
      - network_ip_local: Local IP of primary interface
      - network_mac_address: MAC address of primary interface
      - network_gateway: Default gateway/router IP
      - network_ip_public: Public IP (optional, may be None)
    """
    result = {
        "network_interfaces": [],
        "network_primary": None,
        "network_ip_local": None,
        "network_mac_address": None,
        "network_gateway": None,
        "network_ip_public": None,
    }

    system = platform.system()

    # Platform-specific detection (primary method - more reliable than psutil)
    try:
        if system == "Linux":
            # Modern distros ship `ip` (iproute2); ifconfig is often absent.
            _detect_network_ip_cmd(result)

        if system in ("Linux", "Darwin") and result["network_primary"] is None:
            # macOS primary path; Linux fallback when `ip` is unavailable.
            ifconfig_result = subprocess.run(
                ["ifconfig"],
                capture_output=True, text=True, check=False, timeout=3
            )
            if ifconfig_result.returncode == 0:
                output = ifconfig_result.stdout
                current_iface = None
                current_status = "down"
                current_ip = None
                current_mac = None

                for line in output.split('\n'):
                    # New interface (line starts without whitespace and has :)
                    if line and not line[0].isspace() and ':' in line:
                        # Save previous interface
                        if current_iface and current_iface != "lo0" and not current_iface.startswith("lo"):
                            result["network_interfaces"].append(current_iface)

                            # Determine primary (first up interface with IP)
                            if result["network_primary"] is None and current_status == "up" and current_ip:
                                result["network_primary"] = current_iface
                                result["network_ip_local"] = current_ip
                                result["network_mac_address"] = current_mac

                        # Start new interface
                        current_iface = line.split(':')[0].strip()
                        current_status = "down"
                        current_ip = None
                        current_mac = None

                        # Check if UP/RUNNING in the first line
                        if "UP" in line and "RUNNING" in line:
                            current_status = "up"

                    # Parse interface details (indented lines — macOS ifconfig
                    # uses tabs, Linux net-tools uses spaces)
                    elif current_iface and line and line[0].isspace():
                        line = line.strip()
                        # IPv4 address
                        if line.startswith("inet ") and not line.startswith("inet6"):
                            parts = line.split()
                            if len(parts) >= 2:
                                current_ip = parts[1]
                        # MAC address
                        elif line.startswith("ether "):
                            parts = line.split()
                            if len(parts) >= 2:
                                current_mac = parts[1]

                # Save last interface
                if current_iface and current_iface != "lo0" and not current_iface.startswith("lo"):
                    result["network_interfaces"].append(current_iface)
                    if result["network_primary"] is None and current_status == "up" and current_ip:
                        result["network_primary"] = current_iface
                        result["network_ip_local"] = current_ip
                        result["network_mac_address"] = current_mac

        elif system == "Windows":
            _detect_network_windows(result)

    except Exception:
        pass  # Silent fail

    # Last resort on every OS: route-lookup socket trick (subprocess-free).
    if result["network_ip_local"] is None:
        ip = _socket_local_ip()
        if ip:
            result["network_ip_local"] = ip
            if result["network_primary"] is None:
                result["network_primary"] = "default"

    # Detect default gateway (router IP)
    try:
        if system == "Linux" and result["network_gateway"] is None:
            # `ip route` — netstat needs the deprecated net-tools package
            route_result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, check=False, timeout=3
            )
            if route_result.returncode == 0:
                # "default via 192.168.1.1 dev eth0 ..."
                parts = route_result.stdout.split()
                if "via" in parts:
                    result["network_gateway"] = parts[parts.index("via") + 1]

        if system in ("Darwin", "Linux") and result["network_gateway"] is None:
            # macOS primary path; Linux fallback for net-tools-only systems
            netstat_result = subprocess.run(
                ["netstat", "-rn"],
                capture_output=True, text=True, check=False, timeout=3
            )
            if netstat_result.returncode == 0:
                for line in netstat_result.stdout.split('\n'):
                    # Look for default route
                    if line.startswith("default") or line.startswith("0.0.0.0"):
                        parts = line.split()
                        if len(parts) >= 2:
                            # Second column is usually the gateway
                            gateway = parts[1]
                            # Validate it's an IP address (not a hostname like "UGScg")
                            if '.' in gateway and not gateway[0].isalpha():
                                result["network_gateway"] = gateway
                                break

        elif system == "Windows" and result["network_gateway"] is None:
            # Use route print for Windows
            route_result = subprocess.run(
                ["route", "print", "0.0.0.0"],
                capture_output=True, text=True, check=False, timeout=3
            )
            if route_result.returncode == 0:
                for line in route_result.stdout.split('\n'):
                    if "0.0.0.0" in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            # Third column is typically the gateway
                            gateway = parts[2]
                            if '.' in gateway:
                                result["network_gateway"] = gateway
                                break

    except Exception:
        pass  # Silent fail

    # Public IP requires an outbound call to a third party — opt-in only.
    # OFF by default (privacy + offline-friendly + no boot-time network dependency).
    # Enable with env ZOS_PUBLIC_IP_LOOKUP in {1,true,yes,on}.
    if os.environ.get("ZOS_PUBLIC_IP_LOOKUP", "").strip().lower() in ("1", "true", "yes", "on"):
        try:
            import urllib.request
            # Use a fast, reliable service (timeout 2 seconds)
            response = urllib.request.urlopen('https://api.ipify.org', timeout=2)
            result["network_ip_public"] = response.read().decode('utf-8').strip()
        except Exception:
            pass  # Silent fail - public IP is optional

    return result
