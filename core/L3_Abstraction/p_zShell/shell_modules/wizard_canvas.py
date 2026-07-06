# zOS/core/L3_Abstraction/p_zShell/shell_modules/wizard_canvas.py

"""
Wizard Canvas Manager - Interactive Multi-Line Workflow Builder.

Manages the wizard canvas mode where users can interactively build multi-step
workflows by buffering commands and executing them as a batch via zWizard.

Architecture:
    User Command → is_active() → handle_command() → Route
                                    ↓ wizard cmd    ↓ regular
                                    Control Ops     Buffer Line

Canvas Operations:
    start() - Enter canvas mode
    stop() - Exit and discard buffer
    show() - Display buffer contents
    clear() - Clear buffer (stay in canvas)
    run() - Execute buffer via zWizard
"""

from zOS import Any, Dict, List
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_WIZARD_MODE
from .zshell_constants import (
    COLOR_INFO, COLOR_DATA, COLOR_WARNING, COLOR_EXTERNAL,
    COLOR_SUCCESS, COLOR_ERROR, STYLE_SINGLE, STYLE_FULL,
)
from .executor_constants import (
    # Wizard commands
    WIZARD_CMD_START, WIZARD_CMD_STOP, WIZARD_CMD_RUN, WIZARD_CMD_SHOW, WIZARD_CMD_CLEAR,
    # Wizard state keys
    WIZARD_KEY_ACTIVE, WIZARD_KEY_LINES, WIZARD_KEY_FORMAT,
    # Display constants
    BANNER_WIDTH, BANNER_CHAR, WIZARD_TITLE, WIZARD_INDENT,
    WIZARD_PROMPT_INDENT, WIZARD_LINE_NUM_WIDTH, WIZARD_STEP_PREFIX,
    # Messages
    SUCCESS_WIZARD_EXIT, SUCCESS_WIZARD_CLEAR, SUCCESS_WIZARD_RUN,
    SUCCESS_WIZARD_COMPLETE, SUCCESS_BUFFER_CLEARED,
    INFO_WIZARD_WELCOME, INFO_WIZARD_BUILD, INFO_WIZARD_COMMANDS,
    INFO_WIZARD_EMPTY, INFO_WIZARD_BUFFER, INFO_FORMAT_YAML, INFO_FORMAT_SHELL,
    INFO_TRANSACTION_ENABLED, INFO_EXECUTING_BUFFER, INFO_EXECUTING_STEPS,
    INFO_EXECUTING_COMMANDS, INFO_WIZARD_EMPTY_RUN, INFO_ENTERED_WIZARD,
    WIZARD_CMD_SHOW_DISPLAY, WIZARD_CMD_CLEAR_DISPLAY, WIZARD_CMD_RUN_DISPLAY,
    WIZARD_CMD_STOP_DISPLAY, KEY_TRANSACTION,
)


class WizardCanvasManager:
    """Interactive wizard canvas mode manager for multi-step workflow building."""

    def __init__(self, zos: Any):
        """Initialize wizard canvas manager with zOS framework instance.
        
        Args:
            zos: zOS framework instance (provides display, logger, wizard subsystems)
        """
        self.zos = zos
        self.logger = zos.logger
        self.display = zos.display

    def is_active(self) -> bool:
        """Check if wizard canvas mode is currently active."""
        return self._get_state().get(WIZARD_KEY_ACTIVE, False)

    def handle_command(self, command: str) -> None:
        """Route wizard command or buffer workflow line.
        
        Args:
            command: Raw command string (wizard control or workflow line)
            
        Returns:
            None: UI adapter pattern - all output via zDisplay
        """
        command_stripped = command.strip()
        wizard_mode = self._get_state()

        if command_stripped == WIZARD_CMD_START:
            return self.start()

        if command_stripped == WIZARD_CMD_STOP:
            return self.stop()

        if command_stripped == WIZARD_CMD_RUN:
            return self.run()

        if command_stripped == WIZARD_CMD_SHOW:
            return self.show()

        if command_stripped == WIZARD_CMD_CLEAR:
            return self.clear()

        # Buffer line for workflow
        wizard_mode.get(WIZARD_KEY_LINES, []).append(command)
        return None

    def start(self) -> None:
        """Enter wizard canvas mode and initialize buffer."""
        wizard_mode = self._get_state()

        # Initialize wizard mode state
        wizard_mode[WIZARD_KEY_ACTIVE] = True
        wizard_mode[WIZARD_KEY_LINES] = []
        wizard_mode[WIZARD_KEY_FORMAT] = None

        self.logger.info(INFO_ENTERED_WIZARD)

        # Display welcome banner
        self._display_banner()

        return None

    def stop(self) -> None:
        """Exit wizard mode and discard buffer."""
        wizard_mode = self._get_state()
        line_count = len(wizard_mode.get(WIZARD_KEY_LINES, []))

        wizard_mode[WIZARD_KEY_ACTIVE] = False
        wizard_mode[WIZARD_KEY_LINES] = []
        wizard_mode[WIZARD_KEY_FORMAT] = None

        self.display.zDeclare(
            SUCCESS_WIZARD_EXIT.format(line_count),
            color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        return None

    def show(self) -> None:
        """Display current buffer contents with line numbers."""
        wizard_mode = self._get_state()
        lines = wizard_mode.get(WIZARD_KEY_LINES, [])

        if not lines:
            self.display.zDeclare(
                INFO_WIZARD_EMPTY,
                color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE
            )
            return None

        self.display.zDeclare(
            INFO_WIZARD_BUFFER.format(len(lines)),
            color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_FULL
        )

        for i, line in enumerate(lines, 1):
            self.display.zDeclare(
                f"{i:{WIZARD_LINE_NUM_WIDTH}}: {line}",
                color=COLOR_DATA, indent=WIZARD_PROMPT_INDENT, style=STYLE_SINGLE
            )

        return None

    def clear(self) -> None:
        """Clear buffer without exiting wizard mode."""
        wizard_mode = self._get_state()
        line_count = len(wizard_mode.get(WIZARD_KEY_LINES, []))
        wizard_mode[WIZARD_KEY_LINES] = []

        self.display.zDeclare(
            SUCCESS_WIZARD_CLEAR.format(line_count),
            color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        return None

    def run(self) -> None:
        """Execute wizard buffer with smart format detection."""
        wizard_mode = self._get_state()
        lines = wizard_mode.get(WIZARD_KEY_LINES, [])

        if not lines:
            self.display.zDeclare(
                INFO_WIZARD_EMPTY_RUN,
                color=COLOR_WARNING, indent=WIZARD_INDENT, style=STYLE_SINGLE
            )
            return None

        buffer = "\n".join(lines)

        self.display.zDeclare(
            INFO_EXECUTING_BUFFER.format(len(lines)),
            color=COLOR_EXTERNAL, indent=WIZARD_INDENT, style=STYLE_FULL
        )

        success = self._execute_buffer(buffer)

        if success:
            wizard_mode[WIZARD_KEY_LINES] = []
            self.display.zDeclare(
                SUCCESS_BUFFER_CLEARED,
                color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE
            )

        return None

    def _execute_buffer(self, buffer: str) -> bool:
        """Smart format detection and execution via zWizard.
        
        Args:
            buffer: Multi-line string (YAML or shell commands)
            
        Returns:
            bool: True if execution succeeded, False otherwise
        """
        # Attempt YAML parsing via zParser (centralized parsing)
        wizard_obj = self.zos.zparser.parse_yaml(buffer)

        if wizard_obj and isinstance(wizard_obj, dict):
            self.display.zDeclare(
                INFO_FORMAT_YAML,
                color=COLOR_INFO, indent=WIZARD_PROMPT_INDENT, style=STYLE_SINGLE
            )

            use_transaction = wizard_obj.get(KEY_TRANSACTION, False)
            if use_transaction:
                self.display.zDeclare(
                    INFO_TRANSACTION_ENABLED,
                    color=COLOR_WARNING, indent=WIZARD_PROMPT_INDENT, style=STYLE_SINGLE
                )

            step_count = len([k for k in wizard_obj.keys() if not k.startswith("_")])
            self.display.zDeclare(
                INFO_EXECUTING_STEPS.format(step_count),
                color=COLOR_EXTERNAL, indent=WIZARD_PROMPT_INDENT, style=STYLE_SINGLE
            )

            self.zos.zEngine.handle(wizard_obj)

            self.display.zDeclare(
                SUCCESS_WIZARD_COMPLETE,
                color=COLOR_SUCCESS, indent=WIZARD_PROMPT_INDENT, style=STYLE_SINGLE
            )
            return True

        # Fallback to shell command format
        self.display.zDeclare(
            INFO_FORMAT_SHELL,
            color=COLOR_INFO, indent=WIZARD_PROMPT_INDENT, style=STYLE_SINGLE
        )
        lines = [line.strip() for line in buffer.split("\n") if line.strip()]

        self.display.zDeclare(
            INFO_EXECUTING_COMMANDS.format(len(lines)),
            color=COLOR_EXTERNAL, indent=WIZARD_PROMPT_INDENT, style=STYLE_SINGLE
        )

        # Convert shell commands to wizard format
        wizard_obj = self._convert_to_wizard_format(lines)

        # Execute via zWizard
        try:
            self.zos.zEngine.handle(wizard_obj)

            self.display.zDeclare(
                SUCCESS_WIZARD_RUN.format(len(lines)),
                color=COLOR_SUCCESS, indent=WIZARD_PROMPT_INDENT, style=STYLE_FULL
            )
            return True
        except Exception as e:  # pylint: disable=broad-except
            self.display.zDeclare(
                f"Execution error: {e}",
                color=COLOR_ERROR, indent=WIZARD_PROMPT_INDENT + 1, style=STYLE_SINGLE
            )
            return False

    def _get_state(self) -> Dict[str, Any]:
        """Get wizard state from zSession."""
        return self.zos.session.get(SESSION_KEY_WIZARD_MODE, {})

    def _display_banner(self) -> None:
        """Display wizard canvas welcome banner."""
        # Top border
        self.display.zDeclare(
            BANNER_CHAR * BANNER_WIDTH,
            color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        # Title
        self.display.zDeclare(
            WIZARD_TITLE.center(BANNER_WIDTH),
            color=COLOR_SUCCESS, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        # Bottom border
        self.display.zDeclare(
            BANNER_CHAR * BANNER_WIDTH,
            color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        self.display.zDeclare("", color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE)

        # Instructions
        self.display.zDeclare(
            INFO_WIZARD_WELCOME,
            color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        self.display.zDeclare(
            INFO_WIZARD_BUILD,
            color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        self.display.zDeclare("", color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE)

        # Commands
        self.display.zDeclare(
            INFO_WIZARD_COMMANDS,
            color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        self.display.zDeclare(
            WIZARD_CMD_SHOW_DISPLAY,
            color=COLOR_DATA, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        self.display.zDeclare(
            WIZARD_CMD_CLEAR_DISPLAY,
            color=COLOR_DATA, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        self.display.zDeclare(
            WIZARD_CMD_RUN_DISPLAY,
            color=COLOR_DATA, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        self.display.zDeclare(
            WIZARD_CMD_STOP_DISPLAY,
            color=COLOR_DATA, indent=WIZARD_INDENT, style=STYLE_SINGLE
        )
        self.display.zDeclare("", color=COLOR_INFO, indent=WIZARD_INDENT, style=STYLE_SINGLE)

    def _convert_to_wizard_format(self, lines: List[str]) -> Dict[str, str]:
        """Convert shell commands to wizard format with step keys.
        
        Args:
            lines: List of shell command strings
            
        Returns:
            Dict[str, str]: Wizard format dict {"step_1": cmd1, "step_2": cmd2, ...}
        """
        wizard_obj = {}
        for i, command in enumerate(lines, 1):
            wizard_obj[f"{WIZARD_STEP_PREFIX}{i}"] = command
        return wizard_obj
