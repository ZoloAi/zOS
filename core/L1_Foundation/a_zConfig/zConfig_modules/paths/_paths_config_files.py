"""Config file hierarchy, system paths, and directory utilities for zConfigPaths."""

from zOS import Path, Dict, List, Tuple


class zConfigPathsConfigFiles:  # pylint: disable=no-member
    """System config file paths, config hierarchy resolution, and directory utilities."""

    # ─── System Config Files ─────────────────────────────────────────────────

    @property
    def system_config_defaults(self) -> Path:
        """
        System default configuration file.

        Location: system_config_dir/zConfig.defaults.yaml
        Created on first run with base configuration.
        """
        return self.system_config_dir / self.ZCONFIG_DEFAULTS_FILENAME

    @property
    def system_machine_config(self) -> Path:
        """
        System machine configuration file (zMachine zVaFile).

        Location: system_config_dir/zMachine.yaml
        Contains machine identity and capabilities.
        """
        return self.system_config_dir / self.ZMACHINE_FILENAME

    # ─── Config File Hierarchy ────────────────────────────────────────────────

    def get_config_file_hierarchy(self) -> List[Tuple[Path, int, str]]:
        """
        Get list of config file paths to check, in priority order.

        Returns:
            List of (Path, priority, description) tuples

        Config Hierarchy (lowest to highest priority):
        1. System defaults (zConfig.defaults.yaml) - Base configuration
        2. User config (OS-native) - Per-user overrides
        3. Environment variables (.zEnv or .env) - Workspace-specific runtime config
        4. Session runtime - In-memory overrides (handled by zSession subsystem)

        Note: Dotenv detection auto-discovers .zEnv (primary) or .env (compat).
        """
        configs = []

        if self.system_config_defaults.exists():
            configs.append((self.system_config_defaults, 1, "system-defaults"))

        user_config = self.user_config_dir / self.ZCONFIGS_DIRNAME / self.ZCONFIG_FILENAME
        if user_config.exists():
            configs.append((user_config, 2, "user"))

        dotenv_path = self.get_dotenv_path()
        if dotenv_path:
            if dotenv_path.exists():
                configs.append((dotenv_path, 3, "env-dotenv"))
            else:
                self._log_warning(f"Dotenv path resolved but file missing: {dotenv_path}")
        else:
            self._log_info("No dotenv path detected for hierarchy")

        # Note: Session runtime overrides (highest priority) are handled
        # in-memory by zSession subsystem, not in this file hierarchy

        configs.sort(key=lambda x: x[1])
        return configs

    # ─── Directory Utilities ─────────────────────────────────────────────────

    def ensure_user_config_dir(self) -> Path:
        """Ensure user config directory exists, creating it if needed.

        Returns:
            Path to the user config directory
        """
        config_dir = self.user_config_dir
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            self._log_info(f"Created user config directory: {config_dir}")
        return config_dir

    def get_app_path(self, app_name: str, subpath: str = "") -> Path:
        """
        Get path for app-specific storage.

        Args:
            app_name: Application name (e.g., "zCloud")
            subpath: Optional subpath within app directory (e.g., "storage/users")

        Returns:
            Path: ~/Library/Application Support/zOS/Apps/{app_name}/{subpath}

        Example:
            >>> paths.get_app_path("zCloud")
            Path("~/Library/Application Support/zOS/Apps/zCloud")

            >>> paths.get_app_path("zCloud", "storage/users")
            Path("~/Library/Application Support/zOS/Apps/zCloud/storage/users")

        Note:
            - Does NOT create directories (use ensure_app_directory for that)
            - Returns path even if directory doesn't exist
            - Used by app code to construct storage paths
        """
        app_root = self.user_data_dir / "Apps" / app_name
        if subpath:
            return app_root / subpath
        return app_root

    def get_info(self) -> Dict[str, str]:
        """
        Get path information for debugging.

        Returns:
            Dict with all path information
        """
        return {
            "os": self.os_type,
            "system_config_dir": str(self.system_config_dir),
            "system_config_defaults": str(self.system_config_defaults),
            "system_machine_config": str(self.system_machine_config),
            "user_config_dir": str(self.user_config_dir),
            "user_zconfigs_dir": str(self.user_zconfigs_dir),
            "user_zuis_dir": str(self.user_zuis_dir),
            "user_data_dir": str(self.user_data_dir),
            "user_cache_dir": str(self.user_cache_dir),
            "user_logs_dir": str(self.user_logs_dir),
        }
