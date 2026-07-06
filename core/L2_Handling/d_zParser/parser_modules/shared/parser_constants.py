"""
parser_constants.py

Centralized constants for the zParser subsystem.

This module provides all constants used across parser modules, including command types,
VaFile parsing keys, route types, error messages, and configuration defaults.

Architecture:
- Single source of truth for all parser-related constants
- Organized by category for easy navigation
- PUBLIC vs PRIVATE constants distinguished via naming (will be done in 3.5.3)

Categories:
- Command types (CMD_TYPE_*)
- Command routing (COMMAND_ROUTER)
- VaFile server keys (KEY_*, FILE_TYPE_*, ROUTE_TYPE_*)
- Default values (DEFAULT_*)
- Error messages (ERROR_MSG_*)
- Log messages (LOG_MSG_*)
- Reserved keywords (RESERVED_*)

Dependencies:
- None (pure constants module)

Created: Phase 3.5.1 - Extract Constants
"""

# =============================================================================
# CHARACTER CONSTANTS (Used by command parsing)
# =============================================================================

CHAR_SPACE = " "
CHAR_QUOTE_DOUBLE = '"'
CHAR_QUOTE_SINGLE = "'"
CHAR_DASH_DOUBLE = "--"
CHAR_DASH_SINGLE = "-"

# =============================================================================
# COMMAND TYPES (PRIVATE - Internal command routing)
# =============================================================================

# Core command types for zParser command routing
_CMD_TYPE_DATA = "data"
_CMD_TYPE_FUNC = "func"
_CMD_TYPE_UTILS = "utils"
_CMD_TYPE_SESSION = "session"
_CMD_TYPE_WALKER = "walker"
_CMD_TYPE_OPEN = "open"
_CMD_TYPE_TEST = "test"
_CMD_TYPE_AUTH = "auth"
_CMD_TYPE_EXPORT = "export"
_CMD_TYPE_CONFIG = "config"
_CMD_TYPE_CONFIG_PERSISTENCE = "config_persistence"
_CMD_TYPE_LOAD = "load"
_CMD_TYPE_COMM = "comm"
_CMD_TYPE_WIZARD = "wizard"
_CMD_TYPE_PLUGIN = "plugin"
_CMD_TYPE_LS = "ls"
_CMD_TYPE_CD = "cd"
_CMD_TYPE_CWD = "cwd"
_CMD_TYPE_PWD = "pwd"
_CMD_TYPE_SHORTCUT = "shortcut"
_CMD_TYPE_WHERE = "where"
_CMD_TYPE_HELP = "help"


# =============================================================================
# VAFILE SERVER CONSTANTS (PRIVATE - Internal parsing keys)
# =============================================================================

# File type identifier
_FILE_TYPE_SERVER = "server"

# Top-level keys
_KEY_META = "zMeta"
_KEY_ROUTES = "routes"

# Meta keys
_KEY_BASE_PATH = "base_path"
_KEY_DEFAULT_ROUTE = "default_route"
_KEY_ERROR_PAGES = "error_pages"

# Route keys
_KEY_TYPE = "type"
_KEY_FILE = "file"
_KEY_CONTENT = "content"  # For inline HTML content (v1.5.4 Phase 2)
_KEY_TEMPLATE = "template"  # For Jinja2 templates (v1.5.4 Phase 2)
_KEY_CONTEXT = "context"  # For template variables (v1.5.4 Phase 2)
_KEY_HANDLER = "handler"
_KEY_TARGET = "target"
_KEY_STATUS = "status"
_KEY_DESCRIPTION = "description"
_KEY_RBAC = "zRBAC"
_KEY_ZVAFILE = "zVaFile"  # For dynamic routes (v1.5.4 Phase 3)
_KEY_ZBLOCK = "zBlock"    # For dynamic routes (v1.5.4 Phase 3)

# Route types (content/dynamic/redirect removed 2026-06)
_ROUTE_TYPE_STATIC = "static"
_ROUTE_TYPE_TEMPLATE = "template"  # For Jinja2 templates from the templates/ folder

# Default values
_DEFAULT_BASE_PATH = "."
_DEFAULT_DEFAULT_ROUTE = "index.html"
_DEFAULT_ERROR_PAGES = {403: "403.html", 404: "404.html"}


# =============================================================================
# LOG MESSAGES (PRIVATE - Internal logging)
# =============================================================================

# VaFile server log messages
_LOG_MSG_PARSING_SERVER = "[vafile_server] Parsing server routing file"
_LOG_MSG_FOUND_ROUTES = "[vafile_server] Found %d routes"
_LOG_MSG_ROUTE_WITH_RBAC = "[vafile_server] Route '%s' has RBAC: %s"
_LOG_MSG_NO_ROUTES = "[vafile_server] No routes defined"


# =============================================================================
# ERROR MESSAGES (PRIVATE - Internal error messages)
# =============================================================================

# Schema validation error messages
_ERROR_MSG_SCHEMA_EMPTY = "Schema file cannot be empty"
_ERROR_MSG_NO_TABLES = "Schema file must contain at least one table definition"
_ERROR_MSG_NO_FIELD_DEFS = "Table '%s' has no field definitions"
_ERROR_MSG_NO_FIELD_TYPE = "Field '%s' in table '%s' missing 'type' attribute"
_ERROR_MSG_INVALID_FIELD_TYPE = "Invalid field definition for '%s' in table '%s': expected dict or string"
_ERROR_MSG_UI_KEYS_IN_SCHEMA = "Schema file contains UI-specific keys that may be misplaced: %s"
_ERROR_MSG_INVALID_FIELD_FORMAT = "Invalid field definition format"


# =============================================================================
# RESERVED KEYWORDS
# =============================================================================

# Reserved schema keys that should not be used as table names
RESERVED_SCHEMA_KEYS = ["zFunc", "zLink", "zDialog", "zMenu", "zWizard"]


# =============================================================================
# COMMAND PARSING CONSTANTS (Used by command modules)
# =============================================================================

# Dictionary keys
DICT_KEY_ERROR = "error"
DICT_KEY_TYPE = "type"
DICT_KEY_ACTION = "action"
DICT_KEY_ARGS = "args"
DICT_KEY_OPTIONS = "options"

# Parsing thresholds
MIN_PARTS_SIMPLE_PARSER = 2
SLICE_START_ARGS = 2
SLICE_START_OPTIONS = 1

# Default actions
ACTION_DEFAULT_INFO = "info"
ACTION_DEFAULT_RUN = "run"
ACTION_DEFAULT_SHOW = "show"
ACTION_DEFAULT_LIST = "list"
ACTION_DEFAULT_CREATE = "create"
ACTION_DEFAULT_OPEN = "open"
ACTION_DEFAULT_LS = "ls"
ACTION_DEFAULT_CD = "cd"
ACTION_DEFAULT_PWD = "pwd"
ACTION_DEFAULT_STATUS = "status"
ACTION_DEFAULT_WIZARD = "wizard"

# Error messages (command parsing)
ERROR_MSG_DATA_NO_ACTION = "Data command requires action"
ERROR_MSG_DATA_INVALID_ACTION = (
    "Invalid data action: {}. "
    "Use: read, create, insert, update, delete, drop, head, search, tables"
)
ERROR_MSG_FUNC_NO_NAME = "Func command requires function name"
ERROR_MSG_UTILS_NO_NAME = "Utils command requires utility name"
ERROR_MSG_PLUGIN_NO_SUBCOMMAND = "Plugin command requires subcommand (exec, load, show, clear, reload)"
ERROR_MSG_WALKER_NO_ACTION = "Walker command requires action"
ERROR_MSG_OPEN_NO_PATH = "Open command requires path or URL"
ERROR_MSG_LOAD_NO_ARGS = "Load command requires arguments"
ERROR_MSG_AUTH_NO_ACTION = "Auth command requires action (login, logout, status)"
ERROR_MSG_AUTH_INVALID_ACTION = "Invalid auth action: {}. Use: {}"
ERROR_MSG_EXPORT_NO_TARGET = "Export command requires target (machine or config)"
ERROR_MSG_EXPORT_INVALID_TARGET = "Invalid export target: {}. Use: {}"
ERROR_MSG_CONFIG_NO_ACTION = "Config command requires action"
ERROR_MSG_CONFIG_INVALID_ACTION = "Invalid config action: {}. Use: {}"
ERROR_MSG_CONFIG_PERSIST_NO_TARGET = "Config persistence command requires target"
ERROR_MSG_CONFIG_PERSIST_INVALID_TARGET = "Invalid config persistence target: {}. Use: {}"
ERROR_MSG_COMM_NO_ACTION = "Comm command requires action"
ERROR_MSG_COMM_INVALID_ACTION = "Invalid comm action: {}. Use: {}"
ERROR_MSG_WIZARD_NO_FLAGS = "Wizard command requires at least one flag (--start, --stop, --run, --show, --clear)"
ERROR_MSG_UNKNOWN_COMMAND = "Unknown command: {}"
ERROR_MSG_EMPTY_COMMAND = "Empty command"


# =============================================================================
# PUBLIC API
# =============================================================================

# Export only PUBLIC constants (Phase 3.5.3)
# 59 constants are now PRIVATE (prefixed with _)
# Only 1 constant remains PUBLIC (98% privatization ratio)
__all__ = [
    # Reserved keywords (PUBLIC - validation utility)
    'RESERVED_SCHEMA_KEYS',
]
