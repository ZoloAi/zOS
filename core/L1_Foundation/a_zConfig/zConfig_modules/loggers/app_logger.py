# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/loggers/app_logger.py
"""Application logger for user code."""

from zOS import logging, Path, Colors
from zSys.logger import UnifiedFormatter
from .constants import (
    LOG_PREFIX,
    LOG_FILENAME_APP,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_PROD,
    DEFAULT_FILE_ENABLED,
    CONFIG_KEY_LOGGING,
    CONFIG_KEY_APP,
    CONFIG_KEY_FILE_ENABLED,
    is_zos_log_level,
    get_base_log_level,
)
from .utils import get_logs_directory, resolve_logger_path


class AppLogger:
    """
    Application logger for user code.
    
    Characteristics:
        - Logger name: "zOS.app"
        - Level: Configurable (default: INFO, smart defaults per deployment)
        - File: zos-app.log (customizable path)
        - Console: Always enabled (respects level)
        - Path: Defaults to zOS support folder, user-configurable via config
    """

    def __init__(self, environment_config, zos, session_data: dict, log_level: str):
        """
        Initialize application logger.
        
        Args:
            environment_config: EnvironmentConfig instance
            zos: zOS framework instance
            session_data: Session dictionary with optional zLogPath
            log_level: User's configured log level
        """
        self.environment = environment_config
        self.zos = zos
        self.session_data = session_data
        self.log_level = log_level
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup the application logger."""
        # Get logging configuration
        logging_config = self.environment.get(CONFIG_KEY_LOGGING, {})
        app_config = logging_config.get(CONFIG_KEY_APP, {})

        # Check deployment mode
        is_production = self.environment.is_production()

        # File logging always enabled in Production, otherwise configurable
        file_enabled = is_production or app_config.get(CONFIG_KEY_FILE_ENABLED, DEFAULT_FILE_ENABLED)

        # Get log file path - check zSpark first, then fall back to system default
        from ..session.config_session import SESSION_KEY_TITLE, SESSION_KEY_LOGGER_PATH

        # Get session title for log filename
        session_title = self.session_data.get(SESSION_KEY_TITLE)
        log_filename = f"{session_title}.log" if session_title else LOG_FILENAME_APP

        # Priority 1: Check for custom zLogPath (directory) from zSpark
        custom_logger_path = self.session_data.get(SESSION_KEY_LOGGER_PATH)
        if custom_logger_path:
            # User specified custom directory - append title-based filename
            # Support zPath notation (@. for workspace-relative, ~. for home)
            logs_dir = resolve_logger_path(custom_logger_path, self.zos)
            file_path = str(logs_dir / log_filename)
        else:
            # Priority 2: Use system support directory with session title
            logs_dir = get_logs_directory(self.zos)
            file_path = str(logs_dir / log_filename)

        # Use configured log level (from session detection)
        app_log_level = self.log_level
        # z-prefixed levels (e.g. ZDEBUG, ZINFO) behave identically to their base level
        # for app logging; the z-prefix only unlocks framework trace visibility.
        base_level = get_base_log_level(app_log_level)  # Python-safe level string

        # PROD: silent console, file captures everything at DEBUG
        is_prod_mode = app_log_level == LOG_LEVEL_PROD
        effective_log_level = LOG_LEVEL_DEBUG if is_prod_mode else base_level

        logger = logging.getLogger("zOS.app")
        logger.setLevel(getattr(logging, effective_log_level))

        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()

        # Use unified formatter from zSys (consistent with bootstrap and framework)
        console_formatter = UnifiedFormatter("App", include_details=False, console_colors=True)
        file_formatter = UnifiedFormatter("App", include_details=True, console_colors=False)

        # Console handler (disabled only in PROD mode)
        if not is_prod_mode:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, base_level))
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        # File handler (enabled based on config)
        if file_enabled:
            try:
                log_file = Path(file_path)
                log_file.parent.mkdir(parents=True, exist_ok=True)

                file_log_level = LOG_LEVEL_DEBUG if is_prod_mode else base_level
                file_handler = logging.FileHandler(str(log_file))
                file_handler.setLevel(getattr(logging, file_log_level))
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                print(f"{Colors.ERROR}{LOG_PREFIX} Failed to setup app logging: {e}{Colors.RESET}")

        return logger

    @property
    def logger(self) -> logging.Logger:
        """Get the underlying logging.Logger instance."""
        return self._logger

    def set_level(self, level: str) -> None:
        """
        Set logger level dynamically.
        
        Args:
            level: Log level string ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        """
        from .utils import normalize_log_level, validate_log_level
        from .constants import LOG_LEVEL_PROD as PROD_LEVEL, LOG_LEVEL_INFO

        level = normalize_log_level(level)

        level = validate_log_level(level)
        self._logger.setLevel(getattr(logging, level))
        self.log_level = level

        # Update all handlers
        for handler in self._logger.handlers:
            handler.setLevel(getattr(logging, level))

    def info(self, message: str, *args, **kwargs) -> None:
        """Log info message."""
        self._logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning message."""
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """Log error message."""
        self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        """Log critical message."""
        self._logger.critical(message, *args, **kwargs)
