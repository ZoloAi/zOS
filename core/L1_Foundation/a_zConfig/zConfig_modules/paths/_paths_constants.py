"""Constants and type-hint declarations for zConfigPaths."""

from zOS import Path, Any, Dict, Optional
from ..config_constants import APP_NAME, APP_AUTHOR, DOTENV_FILENAME


class zConfigPathsConstants:
    """Class-level constants and type annotations for path resolution."""

    APP_NAME = APP_NAME
    APP_AUTHOR = APP_AUTHOR
    VALID_OS_TYPES = ("Linux", "Darwin", "Windows")
    DOTENV_FILENAME = DOTENV_FILENAME
    ZCONFIGS_DIRNAME = "zConfigs"
    ZUIS_DIRNAME = "zUIs"
    ZCONFIG_FILENAME = "zConfig.yaml"
    ZMACHINE_FILENAME = "zMachine.yaml"
    ZMACHINE_USER_FILENAME = "zConfig.machine.yaml"
    ZMACHINE_USER_ZOLO_FILENAME = "zConfig.machine.zolo"
    ZENVIRONMENT_FILENAME = "zConfig.environment.yaml"
    ZENVIRONMENT_ZOLO_FILENAME = "zConfig.environment.zolo"
    ZCONFIG_DEFAULTS_FILENAME = "zConfig.defaults.yaml"

    # zEnv file extensions (priority order - consistent with zParser and config_zenv)
    ZENV_EXTENSIONS = [".zolo", ".yaml"]

    # Dotenv key aliases for zSpark configuration
    DOTENV_KEY_ALIASES = (
        "env_file",
        "envFile",
        "dotenv",
        "dotenv_file",
        "dotenvFile",
        "dotenv_path",
        "dotenvPath",
    )

    # Type hints for instance attributes
    app_name: str
    app_author: str
    os_type: str
    zSpark: Optional[Dict[str, Any]]
    workspace_dir: Optional[Path]
    _dotenv_path: Optional[Path]
    _log_level: Optional[str]
    _is_production: bool
    _verbose: bool
