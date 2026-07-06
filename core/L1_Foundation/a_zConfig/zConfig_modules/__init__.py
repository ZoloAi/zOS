# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/__init__.py
"""
zConfig modules - Configuration management components
"""

from .helpers.config_validator import ConfigValidator, ConfigValidationError
from .paths.config_paths import zConfigPaths
from .machine.config_machine import MachineConfig
from .environment.config_environment import EnvironmentConfig
from .persistence.config_persistence import ConfigPersistence
from .loggers import LoggerConfig
from .session.config_session import SessionConfig
from .network.config_websocket import WebSocketConfig
from .network.config_http_server import HttpServerConfig
from .network.config_raven import zRavenConfig

# Import all public constants from centralized constants module
from .config_constants import (
    # Application identity
    APP_NAME,
    APP_AUTHOR,
    DOTENV_FILENAME,
    # zMode values
    ZMODE_ZCLI,
    ZMODE_ZBIFROST,
    ZMODE_WEB,
    # Action routing
    ACTION_PLACEHOLDER,
    # Session keys
    SESSION_KEY_ZS_ID,
    SESSION_KEY_TITLE,
    SESSION_KEY_ZSPACE,
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZBLOCK,
    SESSION_KEY_ZMODE,
    SESSION_KEY_ZLOGGER,
    SESSION_KEY_LOGGER_PATH,
    SESSION_KEY_ZPAGINATE,
    SESSION_KEY_ZMACHINE,
    SESSION_KEY_ZVISITOR,
    SESSION_KEY_ZCRUMBS,
    SESSION_KEY_ZCACHE,
    SESSION_KEY_WIZARD_MODE,
    SESSION_KEY_ZSPARK,
    SESSION_KEY_VIRTUAL_ENV,
    SESSION_KEY_SYSTEM_ENV,
    SESSION_KEY_LOGGER_INSTANCE,
    SESSION_KEY_ZVARS,
    SESSION_KEY_ZSHORTCUTS,
    SESSION_KEY_BROWSER,
    SESSION_KEY_IDE,
    SESSION_KEY_SESSION_HASH,
    # zSpark configuration keys
    ZSPARK_KEY_TITLE,
    ZSPARK_KEY_ZSPACE,
    ZSPARK_KEY_ZVAFOLDER,
    ZSPARK_KEY_ZVAFILE,
    ZSPARK_KEY_ZBLOCK,
    ZSPARK_KEY_ZPAGINATE,
    ZSPARK_KEY_ZMODE,
    ZSPARK_KEY_LOGGER,
    ZSPARK_KEY_LOGGER_PATH,
    # zAuth keys (single signed-in identity: session["zVisitor"])
    ZAUTH_KEY_APPLICATIONS,
    ZAUTH_KEY_ACTIVE_APP,
    ZAUTH_KEY_ACTIVE_CONTEXT,
    ZAUTH_KEY_DUAL_MODE,
    ZAUTH_KEY_AUTHENTICATED,
    ZAUTH_KEY_ID,
    ZAUTH_KEY_USERNAME,
    ZAUTH_KEY_ROLE,
    ZAUTH_KEY_API_KEY,
    CONTEXT_ZSESSION,
    CONTEXT_APPLICATION,
    CONTEXT_DUAL,
    # zCache keys
    ZCACHE_KEY_SYSTEM,
    ZCACHE_KEY_PINNED,
    ZCACHE_KEY_SCHEMA,
    ZCACHE_KEY_PLUGIN,
    # Wizard keys
    WIZARD_KEY_ACTIVE,
    WIZARD_KEY_LINES,
    WIZARD_KEY_FORMAT,
    WIZARD_KEY_TRANSACTION,
)

__all__ = [
    "ConfigValidator",
    "ConfigValidationError",
    "zConfigPaths",
    "MachineConfig",
    "EnvironmentConfig",
    "ConfigPersistence",
    "LoggerConfig",
    "SessionConfig",
    "WebSocketConfig",
    "HttpServerConfig",
    "zRavenConfig",
    # Application identity
    "APP_NAME",
    "APP_AUTHOR",
    "DOTENV_FILENAME",
    # zMode values
    "ZMODE_ZCLI",
    "ZMODE_ZBIFROST",
    "ZMODE_WEB",
    # Action routing
    "ACTION_PLACEHOLDER",
    # Session dict keys
    "SESSION_KEY_ZS_ID",
    "SESSION_KEY_TITLE",
    "SESSION_KEY_ZSPACE",
    "SESSION_KEY_ZVAFOLDER",
    "SESSION_KEY_ZVAFILE",
    "SESSION_KEY_ZBLOCK",
    "SESSION_KEY_ZMODE",
    "SESSION_KEY_ZLOGGER",
    "SESSION_KEY_LOGGER_PATH",
    "SESSION_KEY_ZPAGINATE",
    "SESSION_KEY_ZMACHINE",
    "SESSION_KEY_ZVISITOR",
    "SESSION_KEY_ZCRUMBS",
    "SESSION_KEY_ZCACHE",
    "SESSION_KEY_WIZARD_MODE",
    "SESSION_KEY_ZSPARK",
    "SESSION_KEY_VIRTUAL_ENV",
    "SESSION_KEY_SYSTEM_ENV",
    "SESSION_KEY_LOGGER_INSTANCE",
    "SESSION_KEY_ZVARS",
    "SESSION_KEY_ZSHORTCUTS",
    "SESSION_KEY_BROWSER",
    "SESSION_KEY_IDE",
    "SESSION_KEY_SESSION_HASH",
    # zSpark configuration keys
    "ZSPARK_KEY_TITLE",
    "ZSPARK_KEY_ZSPACE",
    "ZSPARK_KEY_ZVAFOLDER",
    "ZSPARK_KEY_ZVAFILE",
    "ZSPARK_KEY_ZBLOCK",
    "ZSPARK_KEY_ZPAGINATE",
    "ZSPARK_KEY_ZMODE",
    "ZSPARK_KEY_LOGGER",
    "ZSPARK_KEY_LOGGER_PATH",
    # zAuth constants (three-tier architecture with multi-app support)
    "ZAUTH_KEY_APPLICATIONS",
    "ZAUTH_KEY_ACTIVE_APP",
    "ZAUTH_KEY_ACTIVE_CONTEXT",
    "ZAUTH_KEY_DUAL_MODE",
    "ZAUTH_KEY_AUTHENTICATED",
    "ZAUTH_KEY_ID",
    "ZAUTH_KEY_USERNAME",
    "ZAUTH_KEY_ROLE",
    "ZAUTH_KEY_API_KEY",
    "CONTEXT_ZSESSION",
    "CONTEXT_APPLICATION",
    "CONTEXT_DUAL",
    # zCache constants
    "ZCACHE_KEY_SYSTEM",
    "ZCACHE_KEY_PINNED",
    "ZCACHE_KEY_SCHEMA",
    "ZCACHE_KEY_PLUGIN",
    # Wizard keys
    "WIZARD_KEY_ACTIVE",
    "WIZARD_KEY_LINES",
    "WIZARD_KEY_FORMAT",
    "WIZARD_KEY_TRANSACTION",
]
