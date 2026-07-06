"""OS-native directory properties for zConfigPaths."""

from zOS import Path, platformdirs


class zConfigPathsOsDirs:
    """Cross-platform OS directory properties (system + user locations)."""

    # Mixin attributes — defined in zConfigPathsConstants / zConfigPaths.__init__
    APP_NAME: str
    ZCONFIGS_DIRNAME: str
    ZUIS_DIRNAME: str
    app_name: str
    app_author: str
    os_type: str

    @property
    def system_config_dir(self) -> Path:
        r"""
        System config location (discovery only; not created).

        Linux/macOS: /etc/zOS
        Windows:     C:\\ProgramData\\zOS
        """
        if self.os_type in ("Linux", "Darwin"):
            return Path(f"/etc/{self.APP_NAME}")
        return Path(platformdirs.site_config_dir(self.app_name, self.app_author))

    @property
    def user_config_dir(self) -> Path:
        r"""
        User config location (unified with data for simplicity).

        Linux:   ~/.local/share/zOS
        macOS:   ~/Library/Application Support/zOS
        Windows: %LOCALAPPDATA%\zOS

        Note: Returns same directory as user_data_dir to keep everything in one place.
        This simplifies backup, uninstall, and user management.
        """
        return Path(platformdirs.user_data_dir(self.app_name, self.app_author))

    @property
    def user_zconfigs_dir(self) -> Path:
        """
        User zConfigs directory for configuration files.

        Location: user_config_dir/zConfigs/
        Contains: zConfig.default.yaml, zConfig.dev.yaml, etc.
        """
        return self.user_config_dir / self.ZCONFIGS_DIRNAME

    @property
    def user_zuis_dir(self) -> Path:
        """
        User zUIs directory for UI definition files.

        Location: user_config_dir/zUIs/
        Contains: User-customized UI files for commands and walkers.
        """
        return self.user_config_dir / self.ZUIS_DIRNAME

    @property
    def user_zschemas_dir(self) -> Path:
        """
        User zSchemas directory for system schema files.

        Location: user_config_dir/zSchemas/
        Contains: User-provided schema templates (if any).
        """
        return self.user_config_dir / "zSchemas"

    @property
    def user_data_dir(self) -> Path:
        r"""
        User data directory (unified with config for simplicity).

        Linux:   ~/.local/share/zOS
        macOS:   ~/Library/Application Support/zOS
        Windows: %LOCALAPPDATA%\zOS

        Note: Returns same directory as user_config_dir to keep everything in one place.
        This simplifies backup, uninstall, and user management.
        """
        return Path(platformdirs.user_data_dir(self.app_name, self.app_author))

    @property
    def user_cache_dir(self) -> Path:
        r"""
        User cache directory (temporary data).

        Linux:   ~/.cache/zOS
        macOS:   ~/Library/Caches/zOS
        Windows: %LOCALAPPDATA%\zOS\Cache
        """
        return Path(platformdirs.user_cache_dir(self.app_name, self.app_author))

    @property
    def user_logs_dir(self) -> Path:
        r"""
        User logs directory for application logs.

        Linux:   ~/.local/share/zOS/logs
        macOS:   ~/Library/Application Support/zOS/logs
        Windows: %LOCALAPPDATA%\zOS\logs
        """
        return self.user_data_dir / "logs"
