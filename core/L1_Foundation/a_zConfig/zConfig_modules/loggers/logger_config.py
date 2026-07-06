# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/loggers/logger_config.py
"""
Logger configuration and management as part of zConfig.

Uses unified logging format from zSys.logger for consistency
across all logging systems (bootstrap, framework, app).
"""

from zOS import logging, Any, Dict
from zSys.Utils import print_ready_message, validate_zos_instance
from ..session.config_session import SESSION_KEY_ZLOGGER
from .constants import (
    READY_MESSAGE,
    SUBSYSTEM_NAME,
    DEFAULT_LOG_LEVEL,
)
from .utils import normalize_log_level, validate_log_level
from .constants import is_zos_log_level, get_base_log_level
from .framework_logger import FrameworkLogger
from .session_framework_logger import SessionFrameworkLogger
from .app_logger import AppLogger


class LoggerConfig:
    """Manages three-tier logging configuration: framework, session framework, and app logs."""

    # Type hints for instance attributes
    environment: Any  # EnvironmentConfig
    zos: Any  # zOS framework instance
    session_data: Dict[str, Any]
    log_level: str  # App log level (backward compatibility)
    _framework_logger: FrameworkLogger
    _session_framework_logger: SessionFrameworkLogger
    _app_logger: AppLogger
    _verbose: bool

    def __init__(self, environment_config: Any, zos: Any, session_data: Dict[str, Any], verbose: bool = False) -> None:
        """Initialize three-tier logger system with framework, session framework, and application loggers.
        
        Creates three separate loggers:
        1. Framework logger: Pure zOS framework internals → zos-framework.log (global, minimal)
        2. Session framework logger: Session execution trace → {session}.framework.log (bootstrap, flow)
        3. Application logger: User code → {session}.log (optional, customizable)
        
        Args:
            environment_config: EnvironmentConfig instance
            zos: zOS framework instance
            session_data: Session dictionary
            verbose: If True, show initialization output (default: False)
        """
        # Validate required parameters
        validate_zos_instance(zos, SUBSYSTEM_NAME, require_session=False)
        if session_data is None:
            raise ValueError("session_data parameter is required and cannot be None")

        self.environment = environment_config
        self.zos = zos
        self.session_data = session_data
        self._verbose = verbose

        # Get logger configuration from session (which uses environment detection)
        self.log_level = self._get_log_level()  # may be z-prefixed (e.g. "ZDEBUG")
        self._base_log_level = get_base_log_level(self.log_level)  # Python-safe level ("DEBUG")

        # Initialize three-tier logging system
        # Pass raw log_level so sub-loggers can detect z-prefix for framework visibility
        self._framework_logger = FrameworkLogger(environment_config, zos, self.log_level)
        self._session_framework_logger = SessionFrameworkLogger(environment_config, zos, session_data, self.log_level)
        self._app_logger = AppLogger(environment_config, zos, session_data, self.log_level)

        # Print ready message (shown in Development mode or when verbose=True)
        if verbose or self.environment.is_development():
            print_ready_message(READY_MESSAGE, color="CONFIG")

        # Log ready message to session framework
        self._session_framework_logger.info("zLogger Ready")

    def _get_log_level(self) -> str:
        """
        Get log level from session data.
        Session has already processed the full hierarchy:
        zSpark → virtual env → system env → config file → default
        
        Returns:
            str: Valid log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        """
        # Session data has already done all the hierarchy detection
        # Just get the final value from session data
        level = self.session_data.get(SESSION_KEY_ZLOGGER, DEFAULT_LOG_LEVEL)

        # Normalize and validate
        level = normalize_log_level(level)
        return validate_log_level(level)

    @property
    def logger(self) -> logging.Logger:
        """
        Get the application logger instance (user code).
        
        This is the logger for user application code. Returns the app logger
        for backward compatibility and primary API surface.
        
        Returns:
            logging.Logger: The application logger instance
        """
        return self._app_logger.logger

    @property
    def framework(self) -> logging.Logger:
        """
        Get the pure framework logger (global, session-agnostic).
        
        This logger is for PURE zOS framework internals that are NOT
        session-specific (e.g., import errors, system-level failures).
        
        Use sparingly - most logs should go to session_framework instead.
        
        File: zos-framework.log (fixed, global)
        
        Returns:
            logging.Logger: The pure framework logger instance
        """
        return self._framework_logger.logger

    @property
    def session_framework(self) -> logging.Logger:
        """
        Get the session framework logger (execution trace for THIS session).
        
        This logger contains the complete execution trace for THIS specific
        session, including bootstrap, ready banners, SESSION logs, and
        framework flow.
        
        Use for:
            - Bootstrap logs
            - Ready banners (zMachine, zEnv, zParser, etc.)
            - SESSION level logs (zSpark values, config)
            - Framework execution flow (dispatch, navigation)
        
        File: {session_title}.framework.log (e.g., zCloud.framework.log)
        
        Returns:
            logging.Logger: The session framework logger instance
        """
        return self._session_framework_logger.logger

    def set_level(self, level: Any) -> None:
        """
        Set logger level dynamically.
        
        Args:
            level: Log level string ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        
        Note:
            To control production behaviors (silent console, no banners),
            use deployment mode instead of log level.
        """
        self._app_logger.set_level(level)
        self.log_level = self._app_logger.log_level

    def get_level(self) -> str:
        """
        Get current logger level.
        
        Returns:
            str: Current log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        """
        return self.log_level

    def should_show_sysmsg(self) -> bool:
        """
        Check if system messages (ASCII boxes, framework trace) should be displayed.

        Rules (in priority order):
          1. z-prefixed zLog (e.g. zDEBUG, zINFO, zWARNING) → always show framework
             trace regardless of zEnv.  The 'z' prefix is the explicit opt-in for
             full zOS observability at any deployment tier.
          2. zEnv: Development → show (normal dev experience).
          3. zEnv: Testing / Production → hide (clean output).

        Returns:
            bool: True if zOS framework trace should be printed to stdout.
        """
        # z-prefixed level → operator explicitly requested framework visibility
        if is_zos_log_level(self.log_level):
            return True
        # Otherwise respect deployment environment
        return not (self.environment.is_production() or self.environment.is_testing())

    # ═══════════════════════════════════════════════════════════
    # Logging Interface (Semantic Routing)
    # ═══════════════════════════════════════════════════════════

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """
        Log debug message → framework logger ONLY.
        
        Routes to: framework logger (zos-framework.log)
        Audience: zOS framework developers debugging internals
        
        Use for:
            - Implementation details (path resolution, cache hits)
            - Performance metrics for optimization
            - Internal algorithm debugging
            - Framework bug diagnosis
        
        Args:
            message: Log message (supports % formatting with args)
            *args: Positional arguments for message formatting
            **kwargs: Keyword arguments passed to logger
        
        Examples:
            z.logger.debug("zParser path resolution: @.UI → /Users/.../UI")
            z.logger.debug("Cache hit: 3/5 files")
        """
        self._framework_logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """
        Log info message → session framework logger ONLY.
        
        Routes to: session framework logger ({title}.framework.log)
        Audience: Users debugging their application flow
        
        Use for:
            - User-facing events (zParser Ready, subsystem loaded)
            - High-level flow (loading zVaFile, processing request)
            - Ready banners (zMachine, zEnv, zParser)
            - Configuration summary (non-detailed)
        
        Args:
            message: Log message (supports % formatting with args)
            *args: Positional arguments for message formatting
            **kwargs: Keyword arguments passed to logger
        
        Examples:
            z.logger.info("zParser Ready")
            z.logger.info("Loading zVaFile: @.UI.zProducts")
        """
        self._session_framework_logger.info(message, *args, **kwargs)

    def session(self, message: str, *args: Any, **kwargs: Any) -> None:
        """
        Log session/environment/system information → session framework logger ONLY.
        
        Routes to: session framework logger ({title}.framework.log)
        Audience: Users understanding session configuration and context
        
        SESSION level (15) sits between INFO (20) and DEBUG (10).
        
        Use for:
            - Session initialization details (Python version, OS)
            - Configuration detection (zSpark values, deployment, mode)
            - Environment setup (installation type, paths)
            - Session-specific context (dry information)
        
        Args:
            message: Log message (supports % formatting with args)
            *args: Positional arguments for message formatting
            **kwargs: Keyword arguments passed to logger
        
        Examples:
            z.logger.session("Python %s on %s", version, platform)
            z.logger.session("zSpark configuration loaded: %d keys", len(config))
            z.logger.session("Deployment: %s, Mode: %s", deployment, mode)
        """
        self._session_framework_logger.session(message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """
        Log warning message → BOTH framework and session framework loggers.
        
        Routes to: BOTH zos-framework.log AND {title}.framework.log
        Audience: Both developers (might be bug) and users (needs attention)
        
        Use for:
            - Potential issues (file not found, deprecated usage)
            - Configuration problems (invalid setting, missing key)
            - Non-critical failures (fallback used, retry succeeded)
        
        Args:
            message: Log message (supports % formatting with args)
            *args: Positional arguments for message formatting
            **kwargs: Keyword arguments passed to logger
        
        Examples:
            z.logger.warning("zVaFile not found: @.UI.Missing")
            z.logger.warning("Deprecated usage: PROD log level")
        """
        self._framework_logger.warning(message, *args, **kwargs)
        self._session_framework_logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """
        Log error message → BOTH framework and session framework loggers.
        
        Routes to: BOTH zos-framework.log AND {title}.framework.log
        Audience: Both developers (framework bug?) and users (what failed?)
        
        Use for:
            - Critical failures (initialization failed, cannot proceed)
            - Runtime errors (database connection failed, API error)
            - System-level problems (permission denied, disk full)
        
        Args:
            message: Log message (supports % formatting with args)
            *args: Positional arguments for message formatting
            **kwargs: Keyword arguments passed to logger
        
        Examples:
            z.logger.error("zParser initialization failed: %s", error)
            z.logger.error("Database connection failed")
        """
        self._framework_logger.error(message, *args, **kwargs)
        self._session_framework_logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """
        Log critical message → BOTH framework and session framework loggers.
        
        Routes to: BOTH zos-framework.log AND {title}.framework.log
        Audience: Both developers (system failure) and users (cannot continue)
        
        Use for:
            - System-level failures (cannot load core subsystem)
            - Unrecoverable errors (corruption detected, out of memory)
            - Emergency shutdowns (data integrity at risk)
        
        Args:
            message: Log message (supports % formatting with args)
            *args: Positional arguments for message formatting
            **kwargs: Keyword arguments passed to logger
        
        Examples:
            z.logger.critical("Core subsystem failed to load")
            z.logger.critical("Data corruption detected in config")
        """
        self._framework_logger.critical(message, *args, **kwargs)
        self._session_framework_logger.critical(message, *args, **kwargs)

    def dev(self, message: str, *args: Any, **kwargs: Any) -> None:
        """
        Development log - shown in development modes but hidden in Production.
        
        Use for development diagnostics and internal debugging messages that
        should not appear in production deployments.
        
        Args:
            message: Log message (supports % formatting with args)
            *args: Positional arguments for message formatting
            **kwargs: Keyword arguments passed to logger
        
        Example:
            z.logger.dev("Cache hit rate: %d%%", 87)
            z.logger.dev("Development diagnostic message")
        """
        if self.environment.is_production():
            return  # Suppressed in Production deployment

        # Show in development modes (application logger)
        self._app_logger.info(message, *args, **kwargs)

    def user(self, message: str, *args: Any, **kwargs: Any) -> None:
        """
        User application log - shown in ALL modes including PROD.
        
        Use for important application messages that should always be visible,
        even in production deployments. These go to both console and log file.
        
        Args:
            message: Log message (supports % formatting with args)
            *args: Positional arguments for message formatting
            **kwargs: Keyword arguments passed to logger
        
        Example:
            z.logger.user("Application started successfully")
            z.logger.user("Processing %d records...", 1247)
        """
        # Format message if args provided
        formatted_msg = message % args if args else message

        # Always print to console, even in PROD mode
        print(formatted_msg)

        # Also log to file (application logger)
        self._app_logger.info(message, *args, **kwargs)
