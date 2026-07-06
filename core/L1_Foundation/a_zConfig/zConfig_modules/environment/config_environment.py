# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/config_environment.py
"""Environment-level configuration management for deployment and runtime settings."""

from zOS import os, sys, Any, Dict, Optional, Colors
from zSys.Utils import print_ready_message
from ..helpers import load_config_with_override
from .environment_helpers import create_default_env_config
from ..paths.config_paths import zConfigPaths
from zlsp.parser.basic.serializer import dumps as zolo_dumps

# Module constants
LOG_PREFIX = "[EnvironmentConfig]"
READY_MESSAGE = "zEnv Ready"
YAML_KEY = "zEnv"
SUBSYSTEM_NAME = "EnvironmentConfig"

# Environment variable names
ENV_VAR_DEPLOYMENT = "ZOLO_DEPLOYMENT"
ENV_VAR_DEPLOYMENT_ALT = "ZOLO_ENV"

# Config keys
KEY_DEPLOYMENT = "deployment"
KEY_ROLE = "role"

# Default values
DEFAULT_DEPLOYMENT = "Production"  # Changed in v1.5.9: Clean UI for most users (Development is opt-in for demos)
DEFAULT_ROLE = "production"

# Deprecated deployment mode mappings (for backward compatibility)
DEPRECATED_DEPLOYMENTS = {
    "Info": "Testing"
}

class EnvironmentConfig:
    """Manages environment-specific settings and deployment configuration."""

    # Type hints for instance attributes
    paths: zConfigPaths
    env: Dict[str, Any]
    in_venv: bool
    venv_path: Optional[str]
    system_env: Dict[str, str]
    zSpark: Optional[Dict[str, Any]]
    _verbose: bool

    def __init__(self, paths: zConfigPaths, zSpark_obj: Optional[Dict[str, Any]] = None, verbose: bool = False) -> None:
        """Initialize environment configuration with paths and optional zSpark override.
        
        Args:
            paths: zConfigPaths instance for file resolution
            zSpark_obj: Optional zSpark configuration dict (highest priority)
            verbose: If True, show preboot/bootstrap initialization output (default: False)
        """
        self.paths = paths
        self.zSpark = zSpark_obj
        self._verbose = verbose

        # Detect environment types
        self._detect_environments()

        # Get minimal defaults first
        self.env = self._get_defaults()

        # Load and override from config file (check exists, create if missing)
        load_config_with_override(
            self.paths,
            YAML_KEY,
            create_default_env_config,
            self.env,
            self.paths.ZENVIRONMENT_ZOLO_FILENAME,
            SUBSYSTEM_NAME,
            verbose=self._verbose
        )

        # Write current state to .zolo config file
        self._write_zolo_config()

        # LAYER 5: zSpark override (runtime only, not persisted to disk)
        self._apply_zspark_overrides()

        # Print ready message (shown in Development mode or when verbose=True)
        if verbose or self.is_development():
            print_ready_message(READY_MESSAGE, color="CONFIG")

    def _detect_environments(self) -> None:
        """Detect virtual environment and system environment."""
        # Load dotenv file (if available) before capturing environment snapshot
        dotenv_path = self.paths.load_dotenv()
        if dotenv_path and self._verbose:
            print(f"{LOG_PREFIX} Dotenv loaded from: {dotenv_path}")

        # Detect if running in virtual environment
        self.in_venv = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )

        # Store environment info
        self.venv_path = sys.prefix if self.in_venv else None
        self.system_env = dict(os.environ)

        # Print detection results (preboot verbose mode only)
        if self._verbose:
            if self.in_venv:
                print(f"{LOG_PREFIX} Virtual environment detected: {self.venv_path}")
            else:
                print(f"{LOG_PREFIX} Running in system environment")

    def _get_defaults(self) -> Dict[str, Any]:
        """Get minimal hardcoded default environment values (first run fallback).
        
        Hierarchy (lowest to highest priority):
        1. Hardcoded defaults
        2. Environment variables (ZOLO_DEPLOYMENT, ZOLO_ENV)
        """
        if self._verbose:
            print(f"{LOG_PREFIX} Loading environment defaults...")

        env = {
            # Minimal defaults - comprehensive config is in zConfig.environment.zolo
            KEY_DEPLOYMENT: os.getenv(ENV_VAR_DEPLOYMENT) or os.getenv(ENV_VAR_DEPLOYMENT_ALT) or DEFAULT_DEPLOYMENT,
            KEY_ROLE: DEFAULT_ROLE,
        }

        if self._verbose:
            print(f"{LOG_PREFIX} Environment: {env[KEY_DEPLOYMENT]} ({env[KEY_ROLE]})")

        return env

    def _apply_zspark_overrides(self) -> None:
        """Apply zSpark overrides (Layer 5 - highest priority in hierarchy).
        
        Checks zSpark for deployment and other environment overrides.
        This is called AFTER loading from file, so zSpark has final say.
        """
        if not self.zSpark or not isinstance(self.zSpark, dict):
            return

        # Check for zEnv/zState/deployment override (zEnv is canonical; zState is deprecated)
        _DEPRECATED_SPARK_KEYS = {"zState": "zEnv"}
        for key in ["zEnv", "zState", "deployment", "Deployment", "DEPLOYMENT"]:
            if key in self.zSpark:
                deployment_value = str(self.zSpark[key]) if self.zSpark[key] else None
                if deployment_value:
                    # Warn on deprecated zSpark key
                    if key in _DEPRECATED_SPARK_KEYS:
                        print(
                            f"{Colors.WARNING}⚠️  Deprecated zSpark key "
                            f"'{key}' → use '{_DEPRECATED_SPARK_KEYS[key]}' instead{Colors.RESET}"
                        )
                    # Handle deprecated deployment values with migration
                    if deployment_value in DEPRECATED_DEPLOYMENTS:
                        new_value = DEPRECATED_DEPLOYMENTS[deployment_value]
                        if not self.is_production():
                            print(
                                f"{Colors.WARNING}⚠️  Deprecated deployment: "
                                f"'{deployment_value}' → Use '{new_value}' instead{Colors.RESET}"
                            )
                        deployment_value = new_value

                    self.env[KEY_DEPLOYMENT] = deployment_value
                    if not self.is_production():
                        print(
                            f"{Colors.CYAN}{LOG_PREFIX} zEnv overridden by zSpark: "
                            f"{deployment_value}{Colors.RESET}"
                        )
                break

    def get(self, key: str, default: Any = None) -> Any:
        """Get environment config value by key (supports dotted nested keys).

        e.g. get("deployment") or get("network.host"). Returns default if any
        path segment is missing.
        """
        if "." in key:
            node: Any = self.env
            for part in key.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    return default
            return node
        return self.env.get(key, default)

    def update(self, key: str, value: Any) -> None:
        """Set an env value (supports dotted nested keys).

        Mirrors get(): "network.host" writes into the nested dict, creating
        intermediate dicts as needed. Single source for set + reset so they
        round-trip identically.
        """
        if "." in key:
            parts = key.split(".")
            node = self.env
            for part in parts[:-1]:
                nxt = node.get(part)
                if not isinstance(nxt, dict):
                    nxt = {}
                    node[part] = nxt
                node = nxt
            node[parts[-1]] = value
        else:
            self.env[key] = value

    def get_all(self) -> Dict[str, Any]:
        """Get all environment configuration values."""
        return self.env.copy()

    def get_env_var(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get an environment variable (zEnv-backed), preferring the LIVE process
        environment over the boot-time snapshot.

        zEnv injects values into os.environ after this object snapshots it, and
        later code may inject more. Reading os.environ first makes this accessor
        the SSOT for zEnv values; the snapshot is only a fallback.
        """
        live = os.environ.get(key)
        if live is not None:
            return live
        return self.system_env.get(key, default)

    def get_struct(self, key: str, default: Any = None) -> Any:
        """Get a STRUCTURED zEnv value (nested dict/list) by key.

        zEnv injects nested structures into os.environ as JSON strings (see
        config_zenv._inject_to_environ). ``get_env_var`` returns that raw string;
        this returns the parsed structure instead, so callers get a dict/list
        back. Parsing is delegated to the zEnv format module (loads_env_value) —
        no json import here (file-agnosticism: format parsing stays in config).

        Scalars round-trip as their string value; missing keys return ``default``.
        """
        raw = self.get_env_var(key)
        if raw is None:
            return default
        from .config_zenv import loads_env_value
        return loads_env_value(raw)

    def is_in_venv(self) -> bool:
        """Check if running in virtual environment."""
        return self.in_venv

    def get_venv_path(self) -> Optional[str]:
        """Get virtual environment path if running in venv."""
        return self.venv_path

    def is_production(self) -> bool:
        """Check if running in Production deployment mode.
        
        Returns:
            bool: True if deployment is "Production", False otherwise
        """
        deployment = self.env.get(KEY_DEPLOYMENT, "")
        return deployment.lower() == "production"

    def is_testing(self) -> bool:
        """Check if running in Testing deployment mode.
        
        Returns:
            bool: True if deployment is "Testing", False otherwise
        """
        deployment = self.env.get(KEY_DEPLOYMENT, "")
        return deployment.lower() in ["testing", "info"]  # Include deprecated "Info"

    def is_debug(self) -> bool:
        """Check if running in Debug deployment mode.
        
        Returns:
            bool: True if deployment is "Debug", False otherwise
        """
        deployment = self.env.get(KEY_DEPLOYMENT, "")
        return deployment.lower() == "debug"

    def is_development(self) -> bool:
        """Check if running in Development or Testing deployment mode.
        
        Returns:
            bool: True if deployment is "Development" or "Testing", False otherwise
        """
        deployment = self.env.get(KEY_DEPLOYMENT, "")
        return deployment.lower() in ["development", "testing", "debug", "info"]  # Include deprecated modes

    def _write_zolo_config(self) -> None:
        """Write current environment state to zConfig.environment.zolo."""
        try:
            zolo_path = self.paths.user_zconfigs_dir / self.paths.ZENVIRONMENT_ZOLO_FILENAME
            zolo_path.parent.mkdir(parents=True, exist_ok=True)
            with open(zolo_path, 'w', encoding='utf-8') as f:
                f.write(zolo_dumps({YAML_KEY: self.env}))
                f.write('\n')
        except Exception as e:
            print(f"{LOG_PREFIX} Failed to write .zolo config: {e}")

    def save_user_config(self) -> bool:
        """Save current environment config to zConfig.environment.zolo."""
        try:
            base_dir = self.paths.user_zconfigs_dir
            base_dir.mkdir(parents=True, exist_ok=True)

            zolo_path = base_dir / self.paths.ZENVIRONMENT_ZOLO_FILENAME
            with open(zolo_path, 'w', encoding='utf-8') as f:
                f.write(zolo_dumps({YAML_KEY: self.env}))
                f.write('\n')

            print(f"{LOG_PREFIX} Saved environment config to: {zolo_path}")
            return True

        except Exception as e:
            print(f"{LOG_PREFIX} Failed to save environment config: {e}")
            return False
