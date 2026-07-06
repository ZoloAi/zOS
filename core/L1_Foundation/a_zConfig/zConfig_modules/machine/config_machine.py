# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/config_machine.py
"""Machine-level configuration management for system identity and preferences."""

from zOS import Any, Dict
from zSys.Utils import print_ready_message
from ..helpers import load_config_with_override
from .detectors import auto_detect_machine, create_user_machine_config
from ..paths.config_paths import zConfigPaths
from ..config_constants import EDITABLE_MACHINE_KEYS
from zlsp.parser.basic.serializer import dumps as zolo_dumps

# Module constants
LOG_PREFIX = "[MachineConfig]"
READY_MESSAGE = "zMachine Ready"
YAML_KEY = "zMachine"
SUBSYSTEM_NAME = "MachineConfig"

class MachineConfig:
    """Machine-level configuration for system identity and user preferences.
    
    Auto-detects capabilities (browser, IDE, shell, memory, CPU) and loads user 
    overrides from zConfig.machine.zolo. Persisted via config_persistence.py.
    """

    # Type hints for instance attributes
    paths: zConfigPaths
    machine: Dict[str, Any]
    _verbose: bool

    def __init__(self, paths: zConfigPaths, verbose: bool = False) -> None:
        """Initialize with auto-detection and load user preferences from zConfig.machine.zolo.
        
        Args:
            paths: zConfigPaths instance for file resolution
            verbose: If True, show initialization output (default: False)
        """
        self.paths = paths
        self._verbose = verbose

        # Auto-detect machine information (verbose controls preboot output)
        self.machine = auto_detect_machine(log_level=paths._log_level, is_production=not verbose)

        # Add user_data_dir from paths (needed for zPath display formatting)
        self.machine["user_data_dir"] = str(paths.user_data_dir)

        # Load and override from config file (check exists, create if missing)
        load_config_with_override(
            self.paths,
            YAML_KEY,
            create_user_machine_config,
            self.machine,
            self.paths.ZMACHINE_USER_ZOLO_FILENAME,
            SUBSYSTEM_NAME,
            verbose=self._verbose
        )

        # Pin the SSOT emoji output gate from the resolved capability (detected +
        # user override). The gate (zSys.accessibility) is installed at boot and
        # reads this lazily; pinning it here makes zMachine the single source.
        from zSys.accessibility import set_supports_emoji
        set_supports_emoji(self.machine.get("supports_emoji"))

        # Write current state to .zolo config file
        self._write_zolo_config()

        # Print ready message (shown in Development mode only, not Testing or Production).
        # Pass explicit flags so print_ready_message doesn't self-resolve and override
        # the verbose force-show path (verbose => treat as non-prod for this banner).
        if verbose or not (paths._is_production or paths._is_testing):
            print_ready_message(
                READY_MESSAGE, color="CONFIG",
                is_production=False if verbose else paths._is_production,
                is_testing=False if verbose else paths._is_testing,
            )

    def get(self, key: str, default: Any = None) -> Any:
        """Get machine config value by key, returning default if not found."""
        return self.machine.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Get complete machine configuration."""
        return self.machine.copy()

    def update(self, key: str, value: Any) -> None:
        """Update machine config value (runtime only)."""
        self.machine[key] = value

    def _persistable_view(self) -> Dict[str, Any]:
        """Prefs-only slice written to disk.

        Only user-editable preferences are persisted (see EDITABLE_MACHINE_KEYS).
        Auto-detected identity (os, hostname, MAC, IP, username, cpu/memory, …) is
        re-detected fresh each boot and never written, so the on-disk file stays a
        small prefs file rather than a stale machine fingerprint.
        """
        return {k: self.machine[k] for k in EDITABLE_MACHINE_KEYS if k in self.machine}

    def _write_zolo_config(self) -> None:
        """Write user preferences to zConfig.machine.zolo (prefs-only)."""
        try:
            zolo_path = self.paths.user_zconfigs_dir / self.paths.ZMACHINE_USER_ZOLO_FILENAME
            zolo_path.parent.mkdir(parents=True, exist_ok=True)
            with open(zolo_path, 'w', encoding='utf-8') as f:
                f.write(zolo_dumps({YAML_KEY: self._persistable_view()}))
                f.write('\n')
        except Exception as e:
            print(f"{LOG_PREFIX} Failed to write .zolo config: {e}")

    def save_user_config(self) -> bool:
        """Save user preferences to zConfig.machine.zolo (prefs-only)."""
        try:
            base_dir = self.paths.user_zconfigs_dir
            base_dir.mkdir(parents=True, exist_ok=True)

            zolo_path = base_dir / self.paths.ZMACHINE_USER_ZOLO_FILENAME
            with open(zolo_path, 'w', encoding='utf-8') as f:
                f.write(zolo_dumps({YAML_KEY: self._persistable_view()}))
                f.write('\n')

            print(f"{LOG_PREFIX} Saved machine config to: {zolo_path}")
            return True

        except Exception as e:
            print(f"{LOG_PREFIX} Failed to save machine config: {e}")
            return False
