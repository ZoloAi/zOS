# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/persistence/config_persistence.py
"""Configuration persistence for saving/loading zOS config changes."""

from zOS import Colors, Any, Dict, List, Optional
from ..session.config_session import SESSION_KEY_ZMACHINE
from ..config_constants import EDITABLE_MACHINE_KEYS

# Module Constants

# Display Markers
_MARK_EDITABLE = "*"  # row is user-editable via `z config <type> <key> <value>`
_LEGEND = "* editable    -    unmarked = auto-detected / locked"

# Category Names
_CATEGORY_IDENTITY = "Identity (Auto-detected)"
_CATEGORY_USER_PREFS = "User Preferences (Editable)"
_CATEGORY_SYSTEM_INFO = "System Info (Auto-detected)"

# Valid Configuration Values
_VALID_DEPLOYMENTS = ["Debug", "Development", "Testing", "Production"]
_DEPRECATED_DEPLOYMENTS = ["Info"]  # Mapped to Testing (see EnvironmentConfig.DEPRECATED_DEPLOYMENTS)
_VALID_ROLES = ["development", "production", "testing", "staging"]
_VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Machine Config Keys (Editable) — SSOT in config_constants.EDITABLE_MACHINE_KEYS
_EDITABLE_MACHINE_KEYS = list(EDITABLE_MACHINE_KEYS)

# Environment Config Keys (Editable)
_EDITABLE_ENVIRONMENT_KEYS = [
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

# Error Messages
_ERROR_INVALID_KEY = "Invalid {config_type} config key: {key}"
_ERROR_EDITABLE_KEYS = "Editable keys: {keys}"
_ERROR_FAILED_TO_SAVE = "Failed to save {config_type} config"
_ERROR_MUST_BE_POSITIVE = "{key} must be positive"
_ERROR_MUST_BE_NUMBER = "{key} must be a number"
_ERROR_INVALID_DEPLOYMENT = "Invalid deployment: {value}. Must be one of: {valid_values}"
_ERROR_INVALID_ROLE = "Invalid role: {value}. Must be one of: {valid_values}"
_ERROR_INVALID_LOG_LEVEL = "Invalid log level: {value}. Must be one of: {valid_values}"
_ERROR_RESET_REQUIRES_CONFIRMATION = "Full reset requires explicit confirmation"
_ERROR_RESET_USE_KEY = "Use: config machine --reset [key] to reset specific key"
_ERROR_RESET_NOT_IMPLEMENTED = "{config_type} config reset not yet implemented"

# Success Messages
_SUCCESS_UPDATED = "Updated {config_type} config: {key}"
_SUCCESS_RESET = "Reset {config_type} config: {key}"
_SUCCESS_CHANGE_DETAIL = "{old_value} → {new_value}"
_SUCCESS_RESET_DETAIL = "{old_value} → {new_value} (auto-detected)"
_SUCCESS_SAVED_TO = "Saved to: {file_path}"

# Display Headers
_HEADER_MACHINE_CONFIG = "Machine Configuration"
_HEADER_ENVIRONMENT_CONFIG = "Environment Configuration"
_HEADER_ZC_ENV_SETTINGS = "zOS Environment Settings:"
_HEADER_CONFIG_FILE = "Config file: {file_path}"


class ConfigPersistence:
    """Manages configuration persistence to files - handles only editable zOS config parts."""

    def __init__(self, machine_config: Any, environment_config: Any, paths: Any, zos: Optional[Any] = None) -> None:
        """Initialize config persistence with dependencies."""
        self.machine = machine_config
        self.environment = environment_config
        self.paths = paths
        self.zos = zos

    # ═══════════════════════════════════════════════════════════
    # Machine Config Persistence (User Preferences Only)
    # ═══════════════════════════════════════════════════════════

    def persist_machine(self, key: Optional[str] = None, value: Optional[Any] = None,
                       show: bool = False, reset: bool = False) -> bool:
        """
        Persist machine configuration changes to user's zConfig.machine.zolo.
        
        Only handles USER-EDITABLE preferences, not auto-detected characteristics.
        
        Args:
            key: Machine config key (e.g., 'browser', 'ide', 'terminal')
            value: New value
            show: If True, show current values
            reset: If True, reset to auto-detected defaults
            
        Returns:
            bool: Success status
        """
        # Reset to defaults
        if reset:
            return self._reset_machine_config(key)

        # Show current values
        if show or (key is None and value is None):
            return self.show_machine_config()

        # Validate key is user-editable
        if key not in _EDITABLE_MACHINE_KEYS:
            self._handle_error(
                _ERROR_INVALID_KEY.format(config_type="machine", key=key),
                _ERROR_EDITABLE_KEYS.format(keys=', '.join(_EDITABLE_MACHINE_KEYS))
            )
            return False

        # Get current value
        current_value = self.machine.get(key)

        # Validate value (if applicable)
        validation_result = self._validate_machine_value(key, value)
        if not validation_result["valid"]:
            self._handle_error(validation_result['error'])
            return False

        # Update runtime config
        self.machine.update(key, value)
        self._update_session_machine(key, value)

        # Persist to disk
        success = self.machine.save_user_config()

        if success:
            # Show success message
            user_config_path = self.paths.user_zconfigs_dir / self.paths.ZMACHINE_USER_ZOLO_FILENAME
            self._handle_success(
                _SUCCESS_UPDATED.format(config_type="machine", key=key),
                _SUCCESS_CHANGE_DETAIL.format(old_value=current_value, new_value=value),
                str(user_config_path)
            )
        else:
            self._handle_error(_ERROR_FAILED_TO_SAVE.format(config_type="machine"))

        return success

    # ═══════════════════════════════════════════════════════════
    # Environment Config Persistence (zCLI Environment Settings)
    # ═══════════════════════════════════════════════════════════

    def persist_environment(self, key: Optional[str] = None, value: Optional[Any] = None,
                           show: bool = False, reset: bool = False) -> bool:
        """
        Persist environment configuration changes to user's zConfig.environment.zolo.
        
        Handles zOS-specific environment settings (deployment, logging, etc.).
        Does NOT handle system environment variables or virtual environments.
        
        Args:
            key: Environment config key (e.g., 'deployment', 'logging.level')
            value: New value
            show: If True, show current values
            reset: If True, reset to defaults
            
        Returns:
            bool: Success status
        """
        # Reset to defaults
        if reset:
            return self._reset_environment_config(key)

        # Show current values
        if show or (key is None and value is None):
            return self.show_environment_config()

        # Validate key is user-editable
        if key not in _EDITABLE_ENVIRONMENT_KEYS:
            self._handle_error(
                _ERROR_INVALID_KEY.format(config_type="environment", key=key),
                _ERROR_EDITABLE_KEYS.format(keys=', '.join(_EDITABLE_ENVIRONMENT_KEYS))
            )
            return False

        # Get current value
        current_value = self.environment.get(key)

        # Validate value (if applicable)
        validation_result = self._validate_environment_value(key, value)
        if not validation_result["valid"]:
            self._handle_error(validation_result['error'])
            return False

        # Update runtime config (nested-aware: handles "network.host" etc.)
        self.environment.update(key, value)

        # Persist to disk
        success = self.environment.save_user_config()

        if success:
            # Show success message (show the .zolo path actually written)
            user_config_path = self.paths.user_zconfigs_dir / self.paths.ZENVIRONMENT_ZOLO_FILENAME
            self._handle_success(
                _SUCCESS_UPDATED.format(config_type="environment", key=key),
                _SUCCESS_CHANGE_DETAIL.format(old_value=current_value, new_value=value),
                str(user_config_path)
            )
        else:
            self._handle_error(_ERROR_FAILED_TO_SAVE.format(config_type="environment"))

        return success

    # ═══════════════════════════════════════════════════════════
    # Machine Config Helpers
    # ═══════════════════════════════════════════════════════════

    def _reset_machine_config(self, key: Optional[str] = None) -> bool:
        """
        Reset machine configuration to auto-detected defaults.
        
        Args:
            key: Specific key to reset, or None to reset all
            
        Returns:
            bool: Success status
        """
        from ..machine.detectors import auto_detect_machine

        # Get fresh auto-detected values
        auto_detected = auto_detect_machine()

        user_config_path = self.paths.user_zconfigs_dir / self.paths.ZMACHINE_USER_ZOLO_FILENAME

        if key:
            # Reset specific key
            if key not in _EDITABLE_MACHINE_KEYS:
                self._handle_error(_ERROR_INVALID_KEY.format(config_type="machine", key=key))
                return False

            current_value = self.machine.get(key)
            default_value = auto_detected.get(key)

            # Update runtime and persist
            self.machine.update(key, default_value)
            self._update_session_machine(key, default_value)
            success = self.machine.save_user_config()

            if success:
                self._handle_success(
                    _SUCCESS_RESET.format(config_type="machine", key=key),
                    _SUCCESS_RESET_DETAIL.format(old_value=current_value, new_value=default_value),
                    str(user_config_path)
                )
            else:
                self._handle_error(_ERROR_FAILED_TO_SAVE.format(config_type="machine"))

            return success
        else:
            # Reset ALL keys - require explicit confirmation
            self._handle_error(
                _ERROR_RESET_REQUIRES_CONFIRMATION,
                _ERROR_RESET_USE_KEY
            )
            return False

    def _categorize_machine_fields(self, machine: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Dynamically categorize machine config fields based on patterns.
        
        Auto-discovers all fields and groups them intelligently by:
        - Identity: os, hostname, architecture, python*, zos*, username
        - User Tools: browser, ide, *_viewer, *_player, terminal, shell, *_format
        - Hardware: cpu_*, memory_*, gpu_*
        - Network: network_*
        - Paths: home, lang, timezone
        
        Args:
            machine: Machine configuration dictionary
            
        Returns:
            Dict mapping category names to lists of field keys
            
        Benefits:
            - Zero maintenance: New detector fields automatically appear
            - Complete visibility: Shows ALL fields, not just hardcoded subset
            - Smart grouping: Uses prefix patterns for logical organization
        """
        categories = {
            "Identity (Auto-detected)": [],
            "User Tools & Preferences (Editable)": [],
            "Hardware Capabilities (Auto-detected)": [],
            "Network Configuration (Auto-detected)": [],
            "Environment & Paths (Auto-detected)": [],
        }

        for key in sorted(machine.keys()):
            # Skip verbose/internal fields that clutter display
            if key in ['path', 'cwd', 'python_build', 'python_compiler', 'libc_ver']:
                continue

            # Categorize by prefix/suffix patterns
            if (key.startswith(('os', 'hostname', 'architecture', 'python', 'zos', 'processor'))
                or key == 'username'):
                categories["Identity (Auto-detected)"].append(key)

            elif (key in ['browser', 'ide', 'terminal', 'shell']
                  or key.endswith(('_viewer', '_player', '_format'))):
                categories["User Tools & Preferences (Editable)"].append(key)

            elif key.startswith(('cpu_', 'memory_', 'gpu_')):
                categories["Hardware Capabilities (Auto-detected)"].append(key)

            elif key.startswith('network_'):
                categories["Network Configuration (Auto-detected)"].append(key)

            elif key in ['home', 'lang', 'timezone']:
                categories["Environment & Paths (Auto-detected)"].append(key)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    # ═══════════════════════════════════════════════════════════
    # Display helpers (Layer 0 — print + Colors SSOT only)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _fmt_scalar(value: Any) -> str:
        """Render a single config value for display."""
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        if isinstance(value, list):
            return "[]" if not value else ", ".join(str(v) for v in value)
        return str(value)

    @staticmethod
    def _cfg_title(title: str) -> None:
        """Print a section title with a thin underline (brand color)."""
        print(f"\n{Colors.BOLD}{Colors.PRIMARY}{title}{Colors.RESET}")
        print(f"{Colors.DIM}{'-' * len(title)}{Colors.RESET}")

    @staticmethod
    def _cfg_group(name: str) -> None:
        """Print a category header; dims the trailing '(…)' qualifier."""
        label, sep, tag = name.partition(" (")
        suffix = f" {Colors.DIM}({tag}{Colors.RESET}" if sep else ""
        print(f"\n{Colors.BOLD}{Colors.zInfo}{label}{Colors.RESET}{suffix}")

    @staticmethod
    def _cfg_row(key: str, value_str: str, editable: bool, width: int) -> None:
        """Print one aligned key/value row; editable rows get the * marker."""
        mark = f"{Colors.zWarning}{_MARK_EDITABLE}{Colors.RESET} " if editable else "  "
        pad = " " * max(0, width - len(str(key)))
        print(f"  {mark}{Colors.zInfo}{key}{Colors.RESET}{pad}   {value_str}")

    @classmethod
    def _cfg_subtree(cls, mapping: Dict[str, Any], indent: int) -> None:
        """Recursively print a nested mapping as dimmed, aligned key/value lines."""
        pad = " " * indent
        width = max((len(str(k)) for k in mapping), default=0)
        for sub_key, sub_value in mapping.items():
            key_pad = " " * max(0, width - len(str(sub_key)))
            if isinstance(sub_value, dict):
                print(f"{pad}{Colors.DIM}{sub_key}{Colors.RESET}")
                cls._cfg_subtree(sub_value, indent + 4)
            else:
                print(f"{pad}{Colors.DIM}{sub_key}{Colors.RESET}{key_pad}   {cls._fmt_scalar(sub_value)}")

    def show_machine_config(self) -> bool:
        """
        Display current machine configuration with dynamic field discovery.
        
        Uses pattern-based categorization to automatically show ALL detected fields,
        not just a hardcoded subset. New detector fields appear automatically.
        """
        machine = self.machine.get_all()

        # Layer 0: Always use print (zDisplay not available yet)
        self._cfg_title(_HEADER_MACHINE_CONFIG)
        print(f"{Colors.DIM}{_LEGEND}{Colors.RESET}")

        categories = self._categorize_machine_fields(machine)
        for category, keys in categories.items():
            self._cfg_group(category)
            width = max((len(k) for k in keys), default=0)
            for key in keys:
                value = machine.get(key, "N/A")
                editable = key in _EDITABLE_MACHINE_KEYS
                self._cfg_row(key, self._fmt_scalar(value), editable, width)

        # Show file location
        user_config_path = self.paths.user_zconfigs_dir / self.paths.ZMACHINE_USER_ZOLO_FILENAME
        print(f"\n{Colors.DIM}{_HEADER_CONFIG_FILE.format(file_path=user_config_path)}{Colors.RESET}\n")

        return True

    def _validate_machine_value(self, key: str, value: Any) -> Dict[str, Any]:
        """
        Validate machine config value.
        
        Args:
            key: Config key being validated
            value: Value to validate
            
        Returns:
            Dict with 'valid' (bool) and 'error' (str or None) keys
        """
        # Numeric validation — editable keys are the *_limit overrides
        if key in ["cpu_cores_limit", "memory_gb_limit"]:
            try:
                int_value = int(value)
                if int_value <= 0:
                    return {"valid": False, "error": _ERROR_MUST_BE_POSITIVE.format(key=key)}
            except ValueError:
                return {"valid": False, "error": _ERROR_MUST_BE_NUMBER.format(key=key)}

        # All validations passed
        return {"valid": True, "error": None}

    # ═══════════════════════════════════════════════════════════
    # Environment Config Helpers
    # ═══════════════════════════════════════════════════════════

    def _reset_environment_config(self, key: Optional[str] = None) -> bool:
        """
        Reset environment configuration to defaults.
        
        Args:
            key: Specific key to reset, or None to reset all
            
        Returns:
            bool: Success status
        """
        from ..environment.environment_helpers import create_default_env_config
        from zlsp.parser.parser import loads as zolo_loads

        # Get default environment values
        default_env_path = self.paths.user_zconfigs_dir / self.paths.ZENVIRONMENT_ZOLO_FILENAME

        # Load defaults from helper (creates temp structure)
        temp_defaults_path = default_env_path.parent / ".temp_defaults.zolo"
        create_default_env_config(temp_defaults_path, {}, verbose=False)

        try:
            defaults_content = temp_defaults_path.read_text(encoding="utf-8")
            defaults_data = zolo_loads(defaults_content)
            default_env = defaults_data.get("zEnv", {})
        finally:
            # Clean up temp file
            if temp_defaults_path.exists():
                temp_defaults_path.unlink()

        if key:
            # Reset specific key (including nested keys like "network.host")
            if key not in _EDITABLE_ENVIRONMENT_KEYS:
                self._handle_error(_ERROR_INVALID_KEY.format(config_type="environment", key=key))
                return False

            current_value = self.environment.get(key)

            # Handle nested keys
            if "." in key:
                parts = key.split(".")
                default_value = default_env
                for part in parts:
                    default_value = default_value.get(part, None)
                    if default_value is None:
                        break
            else:
                default_value = default_env.get(key)

            # Update runtime and persist
            self.environment.update(key, default_value)
            success = self.environment.save_user_config()

            if success:
                self._handle_success(
                    _SUCCESS_RESET.format(config_type="environment", key=key),
                    _SUCCESS_RESET_DETAIL.format(old_value=current_value, new_value=default_value),
                    str(default_env_path)
                )
            else:
                self._handle_error(_ERROR_FAILED_TO_SAVE.format(config_type="environment"))

            return success
        else:
            # Reset ALL keys - require explicit confirmation
            self._handle_error(
                _ERROR_RESET_REQUIRES_CONFIRMATION,
                _ERROR_RESET_USE_KEY
            )
            return False

    def show_environment_config(self) -> bool:
        """Display current environment configuration."""
        env = self.environment.get_all()

        # Layer 0: Always use print (zDisplay not available yet)
        self._cfg_title(_HEADER_ENVIRONMENT_CONFIG)
        print(f"{Colors.DIM}{_LEGEND}{Colors.RESET}")

        self._cfg_group(_HEADER_ZC_ENV_SETTINGS.rstrip(":"))
        width = max((len(str(k)) for k in env), default=0)
        for key, value in env.items():
            editable = key in _EDITABLE_ENVIRONMENT_KEYS
            if isinstance(value, dict):
                # Parent key, then indented sub-key/value lines (no raw dict repr)
                self._cfg_row(key, "", editable, width)
                self._cfg_subtree(value, 8)
            else:
                self._cfg_row(key, self._fmt_scalar(value), editable, width)

        # Show file location (the .zolo path actually written)
        user_config_path = self.paths.user_zconfigs_dir / self.paths.ZENVIRONMENT_ZOLO_FILENAME
        print(f"\n{Colors.DIM}{_HEADER_CONFIG_FILE.format(file_path=user_config_path)}{Colors.RESET}\n")

        return True

    def _validate_environment_value(self, key: str, value: Any) -> Dict[str, Any]:
        """
        Validate environment config value.
        
        Args:
            key: Config key being validated
            value: Value to validate
            
        Returns:
            Dict with 'valid' (bool) and 'error' (str or None) keys
        """
        # Deployment validation
        if key == "deployment":
            if value not in _VALID_DEPLOYMENTS:
                return {
                    "valid": False,
                    "error": _ERROR_INVALID_DEPLOYMENT.format(
                        value=value,
                        valid_values=', '.join(_VALID_DEPLOYMENTS)
                    )
                }

        # Role validation
        elif key == "role":
            if value not in _VALID_ROLES:
                return {
                    "valid": False,
                    "error": _ERROR_INVALID_ROLE.format(
                        value=value,
                        valid_values=', '.join(_VALID_ROLES)
                    )
                }

        # Logging level validation
        elif key == "logging.level":
            if value.upper() not in _VALID_LOG_LEVELS:
                return {
                    "valid": False,
                    "error": _ERROR_INVALID_LOG_LEVEL.format(
                        value=value,
                        valid_values=', '.join(_VALID_LOG_LEVELS)
                    )
                }

        # Numeric validation for performance settings
        elif key in [
            "performance.max_workers", "performance.cache_size",
            "performance.cache_ttl", "performance.timeout"
        ]:
            try:
                int_value = int(value)
                if int_value <= 0:
                    return {"valid": False, "error": _ERROR_MUST_BE_POSITIVE.format(key=key)}
            except ValueError:
                return {"valid": False, "error": _ERROR_MUST_BE_NUMBER.format(key=key)}

        # All validations passed
        return {"valid": True, "error": None}

    # ═══════════════════════════════════════════════════════════
    # Session Update Helper - Week 6.2.10
    # ═══════════════════════════════════════════════════════════

    def _update_session_machine(self, key: str, value: Any) -> None:
        """
        Update machine config in session dict if available.
        
        Args:
            key: Machine config key
            value: New value
        """
        if self.zos and hasattr(self.zos, 'session'):
            self.zos.session[SESSION_KEY_ZMACHINE][key] = value

    # ═══════════════════════════════════════════════════════════
    # Utility Methods
    # ═══════════════════════════════════════════════════════════

    def _handle_error(self, message: str, details: Optional[str] = None) -> None:
        """
        Handle error messages.
        
        Args:
            message: Error message
            details: Optional details
        """
        # Layer 0: Always use print (zDisplay not available yet)
        print(f"\n{Colors.ERROR}[ERROR] {message}{Colors.RESET}")
        if details:
            print(f"   {details}")
        print()

    def _handle_success(self, message: str, details: Optional[str] = None, file_path: Optional[str] = None) -> None:
        """
        Handle success messages.
        
        Args:
            message: Success message
            details: Optional change details
            file_path: Optional file path where changes were saved
        """
        # Layer 0: Always use print (zDisplay not available yet)
        print(f"\n{Colors.CONFIG}[OK] {message}{Colors.RESET}")
        if details:
            print(f"   {details}")
        if file_path:
            print(f"   {_SUCCESS_SAVED_TO.format(file_path=file_path)}")
        print()
