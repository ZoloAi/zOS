"""Cross-platform configuration path resolution with platformdirs."""

from zOS import logging, platform, Any, Dict, Optional

from ._paths_constants import zConfigPathsConstants
from ._paths_logging import zConfigPathsLogging
from ._paths_workspace import zConfigPathsWorkspace
from ._paths_os_dirs import zConfigPathsOsDirs
from ._paths_config_files import zConfigPathsConfigFiles

logger = logging.getLogger(__name__)


class zConfigPaths(
    zConfigPathsConstants,
    zConfigPathsLogging,
    zConfigPathsWorkspace,
    zConfigPathsOsDirs,
    zConfigPathsConfigFiles,
):
    """Cross-platform path resolver for zOS configuration using native OS conventions."""

    def __init__(self, zSpark_obj: Optional[Dict[str, Any]] = None, verbose: bool = False) -> None:
        """Initialize cross-platform path resolver.

        Auto-detects OS type, validates platform support, and resolves
        workspace and dotenv paths for configuration hierarchy.

        Args:
            zSpark_obj: Optional configuration dictionary with path overrides
            verbose: If True, show preboot/bootstrap initialization output (default: False)

        Raises:
            UnsupportedOSError: If OS type is unsupported (Linux/Darwin/Windows only)
        """
        self.app_name = self.APP_NAME
        self.app_author = self.APP_AUTHOR
        self.os_type = platform.system()  # 'Linux', 'Darwin', 'Windows'
        self.zSpark = zSpark_obj if isinstance(zSpark_obj, dict) else None
        self._verbose = verbose

        from zSys.Utils import get_log_level_from_zspark
        self._log_level = get_log_level_from_zspark(zSpark_obj)
        self._is_production = self._check_production_from_zspark(zSpark_obj)
        self._is_testing = self._check_testing_from_zspark(zSpark_obj)

        if self.os_type not in self.VALID_OS_TYPES:
            from zSys.errors import UnsupportedOSError
            self._log_error(f"Unsupported OS type '{self.os_type}'")
            self._log_warning(f"Supported OS types: {', '.join(self.VALID_OS_TYPES)}")
            self._log_warning("Please report this issue or add support for your OS")
            raise UnsupportedOSError(self.os_type, self.VALID_OS_TYPES)

        logger.debug("[zConfigPaths] Initialized for OS: %s", self.os_type)

        self.workspace_dir = self._detect_workspace_dir()
        self._dotenv_path = self._detect_dotenv_file()

        if self.workspace_dir:
            logger.debug("[zConfigPaths] Workspace directory: %s", self.workspace_dir)
        if self._dotenv_path:
            logger.debug("[zConfigPaths] Dotenv path resolved: %s", self._dotenv_path)
