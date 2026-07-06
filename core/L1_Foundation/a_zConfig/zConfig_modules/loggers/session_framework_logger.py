# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/loggers/session_framework_logger.py
"""Session framework logger for per-execution trace."""

from zOS import logging, Path, Colors
from zSys.logger import UnifiedFormatter
from .constants import LOG_PREFIX, is_zos_log_level, get_base_log_level
from .utils import get_logs_directory


class SessionFrameworkLogger:
    """
    Session framework logger for THIS execution.
    
    Characteristics:
        - Logger name: "zOS.session.framework"
        - File: {session_title}.framework.log (e.g., zCloud.framework.log)
        - Location: Fixed at ~/Library/.../zolo-zos/logs/ (no override)
        - Level: DEBUG (capture everything for this session)
        - Console: WARNING+ in Development only
        - Content: Bootstrap, Ready banners, SESSION logs, framework flow
    
    This logger contains the complete execution trace for THIS session,
    making it easy to audit and debug specific runs.
    """

    def __init__(self, environment_config, zos, session_data: dict, log_level: str):
        """
        Initialize session framework logger.
        
        Args:
            environment_config: EnvironmentConfig instance
            zos: zOS framework instance
            session_data: Session dictionary with title
            log_level: User's configured log level (for console filtering)
        """
        self.environment = environment_config
        self.zos = zos
        self.session_data = session_data
        self.log_level = log_level
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup the session framework logger."""
        # Get session title for filename
        from ..session.config_session import SESSION_KEY_TITLE
        session_title = self.session_data.get(SESSION_KEY_TITLE, "session")
        log_filename = f"{session_title}.framework.log"

        # Resolve z-prefix: z-prefixed level enables framework console in any environment
        zos_mode = is_zos_log_level(self.log_level)
        base_level = get_base_log_level(self.log_level)  # Python-safe (e.g. "DEBUG")

        # Check deployment mode
        is_production = self.environment.is_production()
        is_testing = self.environment.is_testing()
        is_debug = self.environment.is_debug()

        # Get fixed log directory (no override for session framework)
        logs_dir = get_logs_directory(self.zos)
        file_path = str(logs_dir / log_filename)

        # Create session framework logger
        logger = logging.getLogger("zOS.session.framework")
        logger.setLevel(logging.DEBUG)  # Capture everything

        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()

        # Use unified formatter from zSys (consistent with bootstrap and framework)
        console_formatter = UnifiedFormatter("SessionFramework", include_details=False, console_colors=True)
        file_formatter = UnifiedFormatter("SessionFramework", include_details=True, console_colors=False)

        # Console handler decision:
        #   z-prefix level → always show framework trace at the base level (any environment)
        #   Debug deployment → show at user's base level
        #   Development → WARNING+ only (minimal noise)
        #   Production / Testing → no console (file only)
        show_console = zos_mode or (not (is_production or is_testing))
        if show_console:
            console_handler = logging.StreamHandler()
            if zos_mode or is_debug:
                console_handler.setLevel(getattr(logging, base_level))
            else:
                console_handler.setLevel(logging.WARNING)  # Development: minimal
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        # File handler (always enabled for session framework logs)
        try:
            # Ensure log directory exists
            log_file = Path(file_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            # Create file handler
            file_handler = logging.FileHandler(str(log_file))
            file_handler.setLevel(logging.DEBUG)  # Capture everything to file
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # Log session framework initialization
            logger.debug(f"Session framework logging enabled: {log_filename}")
        except Exception as e:
            print(f"{Colors.ERROR}{LOG_PREFIX} Failed to setup session framework logging: {e}{Colors.RESET}")

        return logger

    @property
    def logger(self) -> logging.Logger:
        """Get the underlying logging.Logger instance."""
        return self._logger

    def debug(self, message: str, *args, **kwargs) -> None:
        """Log debug message."""
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        """Log info message."""
        self._logger.info(message, *args, **kwargs)

    def session(self, message: str, *args, **kwargs) -> None:
        """Log session-level message."""
        self._logger.log(logging.SESSION, message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning message."""
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """Log error message."""
        self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        """Log critical message."""
        self._logger.critical(message, *args, **kwargs)
