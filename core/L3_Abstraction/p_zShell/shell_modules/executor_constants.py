# zOS/core/L3_Abstraction/p_zShell/shell_modules/executor_constants.py

"""
Shared Constants for Command Executor and Wizard Canvas.

Centralizes all constants used by shell_executor.py and wizard_canvas.py
to eliminate duplication and improve maintainability.
"""

# ============================================================
# WIZARD COMMANDS
# ============================================================
WIZARD_CMD_START = "wizard --start"
WIZARD_CMD_STOP = "wizard --stop"
WIZARD_CMD_RUN = "wizard --run"
WIZARD_CMD_SHOW = "wizard --show"
WIZARD_CMD_CLEAR = "wizard --clear"

# ============================================================
# WIZARD STATE KEYS
# ============================================================
WIZARD_KEY_ACTIVE = "active"
WIZARD_KEY_LINES = "lines"
WIZARD_KEY_FORMAT = "format"

# ============================================================
# COMMAND TYPES
# ============================================================
CMD_TYPE_DATA = "data"
CMD_TYPE_FUNC = "func"
CMD_TYPE_UTILS = "utils"
CMD_TYPE_SESSION = "session"
CMD_TYPE_WALKER = "walker"
CMD_TYPE_OPEN = "open"
CMD_TYPE_AUTH = "auth"
CMD_TYPE_EXPORT = "export"
CMD_TYPE_CONFIG = "config"
CMD_TYPE_COMM = "comm"
CMD_TYPE_LOAD = "load"
CMD_TYPE_PLUGIN = "plugin"
CMD_TYPE_LS = "ls"
CMD_TYPE_LIST = "list"
CMD_TYPE_DIR = "dir"
CMD_TYPE_CD = "cd"
CMD_TYPE_CWD = "cwd"
CMD_TYPE_PWD = "pwd"
CMD_TYPE_SHORTCUT = "shortcut"
CMD_TYPE_WHERE = "where"
CMD_TYPE_HELP = "help"

# ============================================================
# DISPLAY CONSTANTS
# ============================================================
BANNER_WIDTH = 63
BANNER_CHAR = "="
WIZARD_TITLE = "Wizard Canvas Mode - Active"
WIZARD_INDENT = 0
WIZARD_PROMPT_INDENT = 1
WIZARD_LINE_NUM_WIDTH = 3
WIZARD_STEP_PREFIX = "step_"

# ============================================================
# STATUS VALUES
# ============================================================
STATUS_SUCCESS = "success"
STATUS_STOPPED = "stopped"
STATUS_EMPTY = "empty"
STATUS_SHOWN = "shown"
STATUS_CLEARED = "cleared"
STATUS_ERROR = "error"

# ============================================================
# FORMAT TYPES
# ============================================================
FORMAT_TYPE_YAML = "yaml"
FORMAT_TYPE_COMMANDS = "commands"

# ============================================================
# ERROR MESSAGES
# ============================================================
ERROR_UNKNOWN_COMMAND = "Unknown command type: {}"
ERROR_EMPTY_BUFFER = "empty_buffer"
ERROR_WIZARD_FAILED = "Wizard execution failed"
ERROR_EXECUTION_FAILED = "Command execution failed: {}"
ERROR_YAML_PARSE = "YAML parsing failed: {} - treating as shell commands"

# ============================================================
# SUCCESS MESSAGES
# ============================================================
SUCCESS_WIZARD_EXIT = "Exited wizard canvas - {} lines discarded"
SUCCESS_WIZARD_CLEAR = "Buffer cleared - {} lines removed"
SUCCESS_WIZARD_RUN = "[OK] {} commands executed successfully"
SUCCESS_WIZARD_COMPLETE = "[OK] Wizard execution complete"
SUCCESS_BUFFER_CLEARED = "Buffer cleared after execution"

# ============================================================
# INFO MESSAGES
# ============================================================
INFO_WIZARD_WELCOME = "Build your workflow by typing YAML structure or shell commands."
INFO_WIZARD_BUILD = "Each Enter adds a new line to the buffer."
INFO_WIZARD_COMMANDS = "Commands:"
INFO_WIZARD_EMPTY = "Wizard buffer empty"
INFO_WIZARD_BUFFER = "Wizard Buffer ({} lines):"
INFO_FORMAT_YAML = "Detected YAML/Hybrid format"
INFO_FORMAT_SHELL = "Detected shell command format"
INFO_TRANSACTION_ENABLED = "Transaction mode: ENABLED"
INFO_EXECUTING_BUFFER = "Executing wizard buffer ({} lines)..."
INFO_EXECUTING_STEPS = "Executing {} steps via zWizard..."
INFO_EXECUTING_COMMANDS = "Executing {} commands via zWizard..."
INFO_WIZARD_EMPTY_RUN = "Wizard buffer empty - nothing to run"
INFO_ENTERED_WIZARD = "Entered wizard canvas mode"

# ============================================================
# WIZARD COMMAND DISPLAY STRINGS
# ============================================================
WIZARD_CMD_SHOW_DISPLAY = "  wizard --show    Show buffer"
WIZARD_CMD_CLEAR_DISPLAY = "  wizard --clear   Clear buffer"
WIZARD_CMD_RUN_DISPLAY = "  wizard --run     Execute buffer"
WIZARD_CMD_STOP_DISPLAY = "  wizard --stop    Exit canvas mode"

# ============================================================
# DICT KEYS
# ============================================================
# Canonical parsed-command keys — the SSOT for the shape zParser hands every
# executor. Use these (or command_helpers.get_command_parts) instead of
# re-declaring "action"/"args"/"options" per file.
KEY_ACTION = "action"
KEY_ARGS = "args"
KEY_OPTIONS = "options"

KEY_TYPE = "type"
KEY_ERROR = "error"
KEY_STATUS = "status"
KEY_FORMAT = "format"
KEY_RESULT = "result"
KEY_EXCEPTION = "exception"
KEY_TRANSACTION = "_transaction"
