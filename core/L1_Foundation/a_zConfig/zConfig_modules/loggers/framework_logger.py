# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/loggers/framework_logger.py
"""Pure framework logger for global, session-agnostic operations."""

from zOS import logging, Path, Colors
from zSys.logger import UnifiedFormatter
from .constants import (
    LOG_LEVEL_DEBUG,
    LOG_FILENAME_FRAMEWORK,
    LOG_PREFIX,
    is_zos_log_level,
    get_base_log_level,
)
from .utils import get_logs_directory, make_rotating_file_handler


class FrameworkLogger:
    """
    Pure framework logger for global, session-agnostic operations.
    
    Characteristics:
        - Logger name: "zOS.framework"
        - Purpose: Global zOS framework concerns (NOT session-specific)
        - Use: System-level errors, import failures, critical bugs
        - Level: Always DEBUG (for rare cases when used)
        - File: zos-framework.log (fixed path, shared across sessions)
        - Console: Disabled in Production/Testing, ERROR+ otherwise
        - Path: Non-configurable (always zOS support folder)
    
    NOTE: Most logs should go to session_framework instead!
    This logger is MINIMAL and should rarely be used.
    """

    def __init__(self, environment_config, zos, log_level: str):
        """
        Initialize pure framework logger.
        
        Args:
            environment_config: EnvironmentConfig instance
            zos: zOS framework instance
            log_level: User's configured log level (for console filtering)
        """
        self.environment = environment_config
        self.zos = zos
        self.log_level = log_level
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup the pure framework logger."""
        # Framework logger fixed to DEBUG level
        framework_level = LOG_LEVEL_DEBUG

        # Check deployment mode for console output
        is_production = self.environment.is_production()
        is_testing = self.environment.is_testing()
        is_debug = self.environment.is_debug()

        # Resolve z-prefix (e.g. "ZDEBUG"): map to a Python-safe base level so
        # getattr(logging, ...) never explodes on a custom zOS level name.
        zos_mode = is_zos_log_level(self.log_level)
        base_level = get_base_log_level(self.log_level)

        # Framework log file path (fixed to zOS support folder)
        logs_dir = get_logs_directory(self.zos)
        file_path = str(logs_dir / LOG_FILENAME_FRAMEWORK)

        # Create framework logger
        logger = logging.getLogger("zOS.framework")
        logger.setLevel(getattr(logging, framework_level))

        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()

        # Use unified formatter from zSys (consistent with bootstrap logger)
        console_formatter = UnifiedFormatter("Framework", include_details=False, console_colors=True)
        file_formatter = UnifiedFormatter("Framework", include_details=True, console_colors=False)

        # Console handler for framework logs: Development (ERROR+), Debug (respects logger level)
        if not (is_production or is_testing):
            console_handler = logging.StreamHandler()
            # Debug / z-prefixed level: show framework logs at the user's base level.
            # Development deployment: show only errors (minimal).
            if is_debug or zos_mode:
                console_handler.setLevel(getattr(logging, base_level))  # Respect logger level
            else:
                console_handler.setLevel(logging.ERROR)  # Minimal (Development mode)
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        # File handler (always enabled for framework logs)
        try:
            # Ensure log directory exists
            log_file = Path(file_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            # Create file handler (rotating — this path is global/shared, see utils)
            file_handler = make_rotating_file_handler(log_file)
            file_handler.setLevel(getattr(logging, framework_level))
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # Silent setup (framework logs are transparent)
        except Exception as e:
            print(f"{Colors.ERROR}{LOG_PREFIX} Failed to setup framework logging: {e}{Colors.RESET}")

        return logger

    @property
    def logger(self) -> logging.Logger:
        """Get the underlying logging.Logger instance."""
        return self._logger

    def debug(self, message: str, *args, **kwargs) -> None:
        """Log debug message."""
        self._logger.debug(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning message."""
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """Log error message."""
        self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        """Log critical message."""
        self._logger.critical(message, *args, **kwargs)
