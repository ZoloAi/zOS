# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/loggers/constants.py
"""Logger constants and configuration keys."""

from zSys.logger import LOG_LEVEL_SESSION, LOG_LEVEL_PROD, is_zos_log_level, get_base_log_level

# Logging prefixes
LOG_PREFIX = "[LoggerConfig]"
SUBSYSTEM_NAME = "LoggerConfig"
READY_MESSAGE = "zLogger Ready"
LOGGER_NAME = "zOS"

# Log filenames
LOG_FILENAME = "zos.log"  # Deprecated, kept for backward compatibility
LOG_FILENAME_FRAMEWORK = "zos-framework.log"
LOG_FILENAME_APP = "zos-app.log"

# Log Levels
LOG_LEVEL_DEBUG = "DEBUG"
# LOG_LEVEL_SESSION imported from zSys.logger
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"
LOG_LEVEL_CRITICAL = "CRITICAL"
# LOG_LEVEL_PROD imported from zSys.logger

VALID_LOG_LEVELS = (
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_SESSION,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARNING,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_CRITICAL,
    LOG_LEVEL_PROD,
)
DEFAULT_LOG_LEVEL = LOG_LEVEL_INFO

# Config Keys
CONFIG_KEY_LOGGING = "logging"
CONFIG_KEY_APP = "app"
CONFIG_KEY_FRAMEWORK = "framework"
CONFIG_KEY_FILE_ENABLED = "file_enabled"
CONFIG_KEY_FORMAT = "format"
CONFIG_KEY_FILE_PATH = "file_path"
CONFIG_KEY_LEVEL = "level"

# Format Types
FORMAT_JSON = "json"
FORMAT_SIMPLE = "simple"
FORMAT_DETAILED = "detailed"
DEFAULT_FORMAT = FORMAT_DETAILED

# Default Values
DEFAULT_FILE_ENABLED = True

# Path Markers (for caller info detection)
PATH_SUBSYSTEMS_MARKER = "zOS/subsystems/"
PATH_ZOS_MARKER = "zOS/"
PATH_SUBSYSTEMS_DIR = "subsystems"
PYTHON_EXTENSION = ".py"
