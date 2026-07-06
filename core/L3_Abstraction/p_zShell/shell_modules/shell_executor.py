# zOS/core/L3_Abstraction/p_zShell/shell_modules/shell_executor.py

"""
Command Execution Engine with Wizard Canvas Support.

Routes shell commands to appropriate handlers and manages interactive wizard canvas
mode for building multi-step workflows.

Architecture:
    User Input → execute() → Wizard Check → Route to Handler
                              ↓ YES        ↓ NO
                            Canvas Mode   Command Map (18 types)

Wizard Canvas Commands:
    wizard --start, --stop, --run, --show, --clear
    
Command Routing:
    18 command types with O(1) dictionary lookup
    Supports aliases (list→ls, cwd→pwd) and deprecations (utils→plugin)

Dependencies:
    zParser (parsing), zWizard (execution), zDisplay (output), zConfig (state)
"""

from zOS import Any, Dict, Optional
from .commands import (
    execute_data, execute_func, execute_session, execute_walker,
    execute_open, execute_auth, execute_load,
    execute_export, execute_utils, execute_config, execute_comm,
    execute_wizard_step,
    execute_ls, execute_cd, execute_pwd, execute_shortcut, execute_where, execute_help
)
from .wizard_canvas import WizardCanvasManager
from .shell_policy import enforce_bifrost_seal
from .executor_constants import (
    # Command types
    CMD_TYPE_DATA, CMD_TYPE_FUNC, CMD_TYPE_UTILS, CMD_TYPE_SESSION,
    CMD_TYPE_WALKER, CMD_TYPE_OPEN, CMD_TYPE_AUTH, CMD_TYPE_EXPORT,
    CMD_TYPE_CONFIG, CMD_TYPE_COMM, CMD_TYPE_LOAD,
    CMD_TYPE_LS, CMD_TYPE_LIST, CMD_TYPE_DIR, CMD_TYPE_CD, CMD_TYPE_CWD,
    CMD_TYPE_PWD, CMD_TYPE_SHORTCUT, CMD_TYPE_WHERE, CMD_TYPE_HELP,
    # Dict keys
    KEY_TYPE, KEY_ERROR,
    # Error messages
    ERROR_UNKNOWN_COMMAND, ERROR_EXECUTION_FAILED,
)


class CommandExecutor:
    """
    Command execution engine with wizard canvas delegation.
    
    Routes shell commands to appropriate handlers. Delegates wizard canvas
    operations to WizardCanvasManager for clean separation of concerns.
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance for debugging
        wizard: WizardCanvasManager for canvas mode operations
    """

    def __init__(self, zos: Any) -> None:
        """
        Initialize command executor with zOS framework instance.
        
        Args:
            zos: zOS framework instance
        """
        self.zos = zos
        self.logger = zos.logger
        self.wizard = WizardCanvasManager(zos)

    def execute(self, command: str) -> Optional[Dict[str, Any]]:
        """
        Parse and execute a shell command.
        
        Routes commands through one of two paths:
        1. Wizard canvas mode: Delegates to WizardCanvasManager
        2. Normal mode: Parses command via zParser and routes to handler
        
        Args:
            command: Raw shell command string from user input
            
        Returns:
            Optional[Dict[str, Any]]: Error dict if command fails, None if UI adapter
                                     
        Examples:
            >>> executor.execute("data read users")
            None  # UI adapter - displays via zDisplay
            
            >>> executor.execute("invalid_command")
            {"error": "Unknown command type: invalid_command"}
        """
        if not command.strip():
            return None

        # Check if this is a wizard command or if wizard mode is active
        command_stripped = command.strip()
        if command_stripped.startswith("wizard ") or self.wizard.is_active():
            return self.wizard.handle_command(command)

        try:
            parsed = self.zos.zparser.parse_command(command)

            if KEY_ERROR in parsed:
                return parsed

            return self._execute_parsed_command(parsed)

        except Exception as e:  # pylint: disable=broad-except
            self.logger.error(ERROR_EXECUTION_FAILED.format(e))
            return {KEY_ERROR: str(e)}

    def _execute_parsed_command(self, parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute a pre-parsed command.
        
        Routes parsed command to appropriate handler based on command type.
        Uses dictionary-based command map for O(1) lookup.
        
        Args:
            parsed: Parsed command dictionary from zParser
            
        Returns:
            Optional[Dict[str, Any]]: Result from command handler, or error dict
            
        Examples:
            >>> parsed = {"type": "data", "action": "read", "args": ["users"]}
            >>> self._execute_parsed_command(parsed)
            None  # UI adapter - displays via zDisplay
            
            >>> parsed = {"type": "invalid_cmd"}
            >>> self._execute_parsed_command(parsed)
            {"error": "Unknown command type: invalid_cmd"}
            
        Notes:
            - Command map supports aliases (list→ls, dir→ls, cwd→pwd)
            - Deprecated commands still supported but redirect with warnings
            - Unknown commands return error dict (not None)
            - Command validation done by _validate_command_type helper
        """
        command_type = parsed.get(KEY_TYPE)

        if not self._validate_command_type(command_type):
            return {KEY_ERROR: ERROR_UNKNOWN_COMMAND.format(command_type)}

        # SSOT Bifrost seal: block destructive/mutating ops in remote sessions
        seal_error = enforce_bifrost_seal(self.zos, parsed)
        if seal_error is not None:
            return seal_error

        command_map = {
            CMD_TYPE_DATA: execute_data,
            CMD_TYPE_FUNC: execute_func,
            CMD_TYPE_UTILS: execute_utils,
            CMD_TYPE_SESSION: execute_session,
            CMD_TYPE_WALKER: execute_walker,
            CMD_TYPE_OPEN: execute_open,
            CMD_TYPE_AUTH: execute_auth,
            CMD_TYPE_EXPORT: execute_export,
            CMD_TYPE_CONFIG: execute_config,
            CMD_TYPE_COMM: execute_comm,
            CMD_TYPE_LOAD: execute_load,
            CMD_TYPE_LS: execute_ls,
            CMD_TYPE_LIST: execute_ls,  # Modern alias for ls (beginner-friendly)
            CMD_TYPE_DIR: execute_ls,   # Windows alias for ls
            CMD_TYPE_CD: execute_cd,
            CMD_TYPE_CWD: execute_pwd,       # Primary: Current Working Directory
            CMD_TYPE_PWD: execute_pwd,       # Alias: Unix compatibility (Print Working Directory)
            CMD_TYPE_SHORTCUT: execute_shortcut,
            CMD_TYPE_WHERE: execute_where,
            CMD_TYPE_HELP: execute_help,
        }

        executor = command_map.get(command_type)
        if executor:
            return executor(self.zos, parsed)

        return {KEY_ERROR: ERROR_UNKNOWN_COMMAND.format(command_type)}

    def execute_wizard_step(
        self,
        step_key: str,
        step_value: Any,
        step_context: Dict[str, Any]
    ) -> Any:
        """
        Execute a wizard step via the shell's wizard step executor.
        
        Callback method for zWizard to execute individual workflow steps in shell
        context. Handles zData, zFunc, zDisplay, and generic shell commands.
        
        Args:
            step_key: Step identifier (e.g., "step_1", "create_user")
            step_value: Step definition (command string or dict)
            step_context: Shared context dictionary for step execution
            
        Returns:
            Any: Result from step execution (varies by step type)
            
        Examples:
            >>> self.execute_wizard_step("step_1", "data read users", {})
            None  # Executes data read, returns via zDisplay
            
        Notes:
            - Called by zWizard during workflow execution
            - Context shared across all steps in workflow
            - Delegates to shell_cmd_wizard_step.py for implementation
        """
        return execute_wizard_step(self.zos, step_key, step_value, self.logger, step_context)

    def _validate_command_type(self, command_type: Optional[str]) -> bool:
        """
        Validate command type before execution.
        
        Checks if command_type is non-empty and is a string. Logs invalid types
        for debugging.
        
        Args:
            command_type: Command type from parsed command dict
            
        Returns:
            bool: True if valid, False if invalid
            
        Examples:
            >>> self._validate_command_type("data")
            True
            
            >>> self._validate_command_type(None)
            False  # Logs warning
            
            >>> self._validate_command_type("")
            False  # Logs warning
            
        Notes:
            - Validation happens before command map lookup
            - Invalid types logged for debugging
            - Prevents KeyError from dict access
        """
        if not command_type or not isinstance(command_type, str):
            self.logger.warning("Invalid command type: %s", command_type)
            return False
        return True
