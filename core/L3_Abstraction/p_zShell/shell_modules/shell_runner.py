# zOS/core/L3_Abstraction/p_zShell/shell_modules/shell_runner.py

"""
REPL Session Manager with Command History and Dynamic Prompts.

This module manages the Read-Eval-Print Loop (REPL) session infrastructure for zShell,
including the main input loop, persistent command history via readline, dynamic prompt
generation, and special built-in commands.

────────────────────────────────────────────────────────────────────────────────
ARCHITECTURE
────────────────────────────────────────────────────────────────────────────────

    ┌──────────────────────────────────────────────────────────────┐
    │                   SHELL RUNNER (REPL)                        │
    ├──────────────────────────────────────────────────────────────┤
    │                                                              │
    │  User Input                                                  │
    │      ↓                                                       │
    │  run() - Main REPL Loop                                     │
    │      ↓                                                       │
    │  ┌────────────────────┐                                     │
    │  │ While running:     │                                     │
    │  │  1. Get prompt     │                                     │
    │  │  2. Read input     │                                     │
    │  │  3. Check special  │                                     │
    │  │  4. Execute cmd    │ ───→ CommandExecutor               │
    │  │  5. Display result │                                     │
    │  └────────────────────┘                                     │
    │                                                              │
    │  Components:                                                 │
    │    • Readline History (~/.zolo/.zcli_history)               │
    │    • Dynamic Prompt (normal/wizard/zPath)                   │
    │    • Special Commands (exit, clear, tips)                   │
    │    • Error Handling (KeyboardInterrupt, EOFError)           │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────────────
REPL LOOP DETAILS
────────────────────────────────────────────────────────────────────────────────

The main loop handles:
    1. Prompt Generation - Context-aware based on mode (wizard/zPath)
    2. Input Reading - Uses Python's input() with readline support
    3. Special Commands - Built-in commands that bypass normal execution
    4. Command Execution - Delegates to CommandExecutor for routing
    5. Result Display - Fallback display for legacy commands returning data
    6. Error Handling - Graceful handling of interrupts and exceptions

────────────────────────────────────────────────────────────────────────────────
READLINE INTEGRATION
────────────────────────────────────────────────────────────────────────────────

Persistent command history using Python's readline module:
    • History File: ~/.zolo/.zcli_history
    • History Length: 1000 commands
    • Navigation: Up/down arrows to browse history
    • Persistence: Saved on exit, loaded on startup
    • Graceful Fallback: Works without readline if not available

────────────────────────────────────────────────────────────────────────────────
DYNAMIC PROMPT
────────────────────────────────────────────────────────────────────────────────

Prompt changes based on context:
    • Normal Mode:    "zOS> "
    • Wizard Canvas:  "> "
    • With zPath:     "zCLI [~.projects.myapp]> "

zPath Display:
    • Enabled via 'where on' command
    • Converts OS path to zPath notation (~ for home, . for separators)
    • Falls back to absolute path if outside home directory

────────────────────────────────────────────────────────────────────────────────
SPECIAL COMMANDS
────────────────────────────────────────────────────────────────────────────────

Built-in commands that bypass normal execution:
    • exit, quit, q - Exit shell
    • clear, cls     - Clear terminal screen
    • tips           - Show quick tips

These commands are handled directly by the runner and do not go through
CommandExecutor or zParser.

────────────────────────────────────────────────────────────────────────────────
MODULE CONSTANTS
────────────────────────────────────────────────────────────────────────────────

**Special Commands (6):**
    CMD_EXIT, CMD_QUIT, CMD_Q, CMD_CLEAR, CMD_CLS, CMD_TIPS

**Prompts (3):**
    PROMPT_DEFAULT, PROMPT_WIZARD, PROMPT_ZPATH_TEMPLATE

**Messages (7):**
    MSG_GOODBYE, MSG_STARTING_SHELL, MSG_EXITING_SHELL, MSG_HISTORY_ENABLED,
    MSG_HISTORY_LOADED, MSG_HISTORY_SAVED, MSG_ERROR_PREFIX

**History Settings (3):**
    HISTORY_LENGTH, HISTORY_DIR_NAME, HISTORY_FILE_NAME

**Session Keys (2):**
    SESSION_KEY_WIZARD_MODE (from zConfig), SESSION_KEY_SHOW_ZPATH

**Dict Keys (4):**
    KEY_ACTIVE, KEY_ERROR, KEY_SUCCESS, KEY_NOTE

**Display Constants (8):**
    COLOR_INFO, COLOR_ERROR, COLOR_SUCCESS, COLOR_DATA, COLOR_EXTERNAL,
    STYLE_SINGLE, STYLE_FULL, INDENT_NORMAL, INDENT_NESTED

**OS Commands (2):**
    CLEAR_CMD_POSIX, CLEAR_CMD_WINDOWS

**zPath Symbols (2):**
    ZPATH_HOME_PREFIX, ZPATH_SEPARATOR

**Warning Messages (3):**
    WARN_HISTORY_SETUP_FAILED, WARN_HISTORY_SAVE_FAILED, WARN_SHELL_ERROR

────────────────────────────────────────────────────────────────────────────────
DEPENDENCIES
────────────────────────────────────────────────────────────────────────────────

- shell_executor: CommandExecutor for command routing
- shell_help: HelpSystem for welcome messages and tips
- readline: Python's readline module (optional, graceful fallback)
- zConfig: SESSION_KEY_WIZARD_MODE constant
- zDisplay: Mode-agnostic output

────────────────────────────────────────────────────────────────────────────────
EXAMPLES
────────────────────────────────────────────────────────────────────────────────

**Normal REPL Session:**
    >>> runner = ShellRunner(zos)
    >>> runner.run()
    zOS> data read users
    [displays user data]
    zOS> exit
    Goodbye!

**Wizard Canvas Mode:**
    >>> runner.run()
    zOS> wizard --start
    ===============================================================
                   Wizard Canvas Mode - Active
    ===============================================================
    > data read users
    > data read posts
    > wizard --run
    [executes both commands]

**zPath Display:**
    >>> runner.run()
    zOS> where on
    zCLI [~.projects.myapp]> cd ..
    zCLI [~.projects]> exit
    Goodbye!

────────────────────────────────────────────────────────────────────────────────
NOTES
────────────────────────────────────────────────────────────────────────────────

- File Rename: Previously `shell_interactive.py`, renamed to `shell_runner.py`
  for clarity (all shells are "interactive", runner emphasizes REPL management)
- Class Rename: `InteractiveShell` → `ShellRunner` for consistency
- Terminal Clear: Uses os.system() for clear command (terminal-specific, not
  available via zDisplay, documented exception to mode-agnostic design)
- Session State: Wizard canvas state accessed via SESSION_KEY_WIZARD_MODE
- History File: Created in ~/.zolo/ directory (hidden, user-specific)
"""

from zOS import os, Path, Any, Optional, Dict
from .shell_help import HelpSystem
from .shell_executor import CommandExecutor
from .shell_paths import format_zpath
from .shell_policy import redact_sensitive_command
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_WIZARD_MODE

try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

# Import shared constants
from .zshell_constants import (
    STYLE_SINGLE,
    STYLE_FULL,
    INDENT_NORMAL,
    INDENT_NESTED,
    COLOR_INFO,
    COLOR_ERROR,
    COLOR_SUCCESS,
    COLOR_DATA,
    COLOR_EXTERNAL,
    PROMPT_NORMAL,
    PROMPT_WIZARD,
    MSG_GOODBYE,
    MSG_ERROR_PREFIX
)

# ============================================================
# SPECIAL COMMANDS
# ============================================================
CMD_EXIT = "exit"
CMD_QUIT = "quit"
CMD_Q = "q"
CMD_CLEAR = "clear"
CMD_CLS = "cls"
CMD_TIPS = "tips"

# ============================================================
# PROMPTS (module-specific)
# ============================================================
PROMPT_DEFAULT = PROMPT_NORMAL  # Alias for compatibility
PROMPT_ZPATH_TEMPLATE = "zCLI [{}]> "

# ============================================================
# MESSAGES (module-specific)
# ============================================================
MSG_STARTING_SHELL = "Starting zCLI shell..."
MSG_EXITING_SHELL = "Exiting zCLI shell..."
MSG_HISTORY_ENABLED = "Command history enabled (up/down arrows to navigate)"
MSG_HISTORY_LOADED = "Loaded command history from %s"
MSG_HISTORY_SAVED = "Saved command history to %s"

# ============================================================
# HISTORY SETTINGS
# ============================================================
HISTORY_LENGTH = 1000
HISTORY_DIR_NAME = ".zolo"
HISTORY_FILE_NAME = ".zcli_history"

# ============================================================
# SESSION KEYS
# ============================================================
SESSION_KEY_SHOW_ZPATH = "zShowZPathInPrompt"

# ============================================================
# DICT KEYS
# ============================================================
KEY_ACTIVE = "active"
KEY_ERROR = "error"
KEY_SUCCESS = "success"
KEY_NOTE = "note"

# ============================================================
# OS COMMANDS
# ============================================================
CLEAR_CMD_POSIX = "clear"
CLEAR_CMD_WINDOWS = "cls"

# ============================================================
# ZPATH SYMBOLS
# ============================================================
ZPATH_HOME_PREFIX = "~"
ZPATH_SEPARATOR = "."
ZPATH_CURRENT_DIR_MARKER = "."

# ============================================================
# WARNING MESSAGES
# ============================================================
WARN_HISTORY_SETUP_FAILED = "Could not setup command history: %s"
WARN_HISTORY_SAVE_FAILED = "Could not save command history: %s"
WARN_SHELL_ERROR = "Shell error: %s"

# ============================================================
# SPECIAL COMMANDS LISTS
# ============================================================
SPECIAL_COMMANDS_EXIT = [CMD_EXIT, CMD_QUIT, CMD_Q]
SPECIAL_COMMANDS_CLEAR = [CMD_CLEAR, CMD_CLS]


class ShellRunner:
    """
    REPL session manager with command history and dynamic prompts.
    
    Manages the Read-Eval-Print Loop infrastructure for zShell, including
    the main input loop, persistent command history, and special commands.
    
    Attributes:
        zos: The zOS framework instance
        logger: Logger instance for debugging
        display: zDisplay instance for output
        executor: CommandExecutor for command routing
        help_system: HelpSystem for welcome messages and tips
        running: bool indicating if REPL loop is active
        history_file: Optional[Path] to readline history file
    """

    def __init__(self, zos: Any) -> None:
        """
        Initialize shell runner.
        
        Sets up the REPL infrastructure including command executor and help system.
        History setup is deferred until run() is called (lazy initialization).
        
        Args:
            zos: The zOS framework instance
            
        Examples:
            >>> runner = ShellRunner(zos)
            >>> runner.run()  # Start REPL loop (history setup happens here)
        """
        self.zos: Any = zos
        self.logger: Any = zos.logger
        self.display: Any = zos.display
        self.executor: CommandExecutor = CommandExecutor(zos)
        self.help_system: HelpSystem = HelpSystem(display=self.display, zos=self.zos)
        self.running: bool = False

        self.history_file: Optional[Path] = None
        self._history_initialized: bool = False

    def run(self) -> None:
        """
        Main REPL loop - handles user input and command execution.
        
        Runs the Read-Eval-Print Loop until user exits (exit/quit/q command)
        or interrupts (Ctrl+C, Ctrl+D). Handles wizard canvas mode, special
        commands, and error conditions gracefully.
        
        Returns:
            None
            
        Raises:
            None: All exceptions are caught and handled
            
        Examples:
            >>> runner = ShellRunner(zos)
            >>> runner.run()
            zOS> data read users
            [displays results]
            zOS> exit
            Goodbye!
            
        Notes:
            - KeyboardInterrupt (Ctrl+C) exits gracefully
            - EOFError (Ctrl+D) exits gracefully
            - Wizard canvas mode preserves indentation
            - Command history saved on exit (if readline available)
            - History setup is lazy (only initialized on first run)
        """
        # Lazy initialization: Setup history only when shell is actually run
        if not self._history_initialized and READLINE_AVAILABLE:
            self._setup_history()
            self._history_initialized = True
        
        self.logger.framework.debug(MSG_STARTING_SHELL)
        self.zos.display.write_block(self.help_system.get_welcome_message())
        self.running = True

        while self.running:
            try:
                prompt = self._get_prompt()
                raw_input = input(prompt)
                self._redact_history(raw_input)

                wizard_mode = self._get_wizard_mode()
                if wizard_mode.get(KEY_ACTIVE):
                    command = raw_input  # Preserve indentation in wizard canvas
                else:
                    command = raw_input.strip()

                if not command:
                    continue

                if self._handle_special_commands(command):
                    continue

                result = self.executor.execute(command)
                if result:
                    self._display_result(result)

            except KeyboardInterrupt:
                self.zos.display.zDeclare(
                    MSG_GOODBYE,
                    color=COLOR_INFO, indent=INDENT_NORMAL, style=STYLE_SINGLE
                )
                break

            except EOFError:
                self.zos.display.zDeclare(
                    MSG_GOODBYE,
                    color=COLOR_INFO, indent=INDENT_NORMAL, style=STYLE_SINGLE
                )
                break

            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(WARN_SHELL_ERROR, e)
                self.zos.display.zDeclare(
                    MSG_ERROR_PREFIX.format(e),
                    color=COLOR_ERROR, indent=INDENT_NORMAL, style=STYLE_SINGLE
                )

        self.logger.framework.debug(MSG_EXITING_SHELL)
        if READLINE_AVAILABLE and self.history_file:
            self._save_history()

    def _redact_history(self, raw_input: str) -> None:
        """Scrub inline credentials from the just-entered readline history item.

        readline records every line before ``input()`` returns, so a command
        like ``auth login <user> <password>`` would otherwise be persisted to the
        history file verbatim. We replace that entry in place with a masked form.
        """
        if not READLINE_AVAILABLE:
            return
        redacted = redact_sensitive_command(raw_input)
        if redacted is None:
            return
        try:
            last = readline.get_current_history_length() - 1
            if last >= 0:
                readline.replace_history_item(last, redacted)
        except Exception:  # pylint: disable=broad-except
            pass

    def _get_prompt(self) -> str:
        """
        Get the appropriate prompt based on current mode.
        
        Generates context-aware prompt that changes based on:
        - Wizard canvas mode (active or not)
        - zPath display setting (enabled via 'where on')
        
        Returns:
            str: Prompt string for input()
            
        Examples:
            >>> runner._get_prompt()
            "zOS> "  # Normal mode
            
            >>> # In wizard canvas mode
            >>> runner._get_prompt()
            "> "
            
            >>> # With zPath display enabled
            >>> runner._get_prompt()
            "zCLI [~.projects.myapp]> "
            
        Notes:
            - Wizard canvas mode has minimal prompt ("> ")
            - zPath display shows current working directory
            - Falls back to default if zPath formatting fails
        """
        wizard_mode = self._get_wizard_mode()
        if wizard_mode.get(KEY_ACTIVE):
            return PROMPT_WIZARD
        
        # Check if zPath display is enabled (via 'where on' command)
        show_zpath = self.zos.session.get(SESSION_KEY_SHOW_ZPATH, False)
        if show_zpath:
            zpath = format_zpath(fallback_absolute=True)
            if zpath:
                return PROMPT_ZPATH_TEMPLATE.format(zpath)
        
        return PROMPT_DEFAULT
    
    def _setup_history(self) -> None:
        """
        Setup readline history file for persistent command history.
        
        Creates ~/.zolo/.zcli_history file and configures readline to:
        - Load existing history on startup
        - Save history on exit
        - Maintain up to 1000 commands
        - Enable up/down arrow navigation
        
        Returns:
            None
            
        Raises:
            None: Logs warning on failure, sets history_file to None
            
        Examples:
            >>> runner._setup_history()
            # Creates ~/.zolo/.zcli_history
            # Loads existing history if present
            # Enables arrow key navigation
            
        Notes:
            - Only called if readline module is available
            - Gracefully handles failures (logs warning, continues)
            - History file is hidden (starts with .)
            - Directory created if doesn't exist
        """
        try:
            home = Path.home()
            history_dir = home / HISTORY_DIR_NAME
            history_dir.mkdir(exist_ok=True)
            self.history_file = history_dir / HISTORY_FILE_NAME

            if self.history_file.exists():
                readline.read_history_file(str(self.history_file))
                self.logger.framework.debug(MSG_HISTORY_LOADED, self.history_file)

            readline.set_history_length(HISTORY_LENGTH)
            self.logger.framework.debug(MSG_HISTORY_ENABLED)

        except Exception as e:  # pylint: disable=broad-except
            self.logger.warning(WARN_HISTORY_SETUP_FAILED, e)
            self.history_file = None

    def _save_history(self) -> None:
        """
        Save command history to file.
        
        Writes readline history to ~/.zolo/.zcli_history for persistence
        across sessions.
        
        Returns:
            None
            
        Raises:
            None: Logs warning on failure
            
        Examples:
            >>> runner._save_history()
            # Saves current session history to file
            
        Notes:
            - Only called if readline available and history_file set
            - Called automatically on shell exit
            - Gracefully handles failures (logs warning, continues)
        """
        try:
            readline.write_history_file(str(self.history_file))
            self.logger.debug(MSG_HISTORY_SAVED, self.history_file)
        except Exception as e:  # pylint: disable=broad-except
            self.logger.warning(WARN_HISTORY_SAVE_FAILED, e)

    def _handle_special_commands(self, command: str) -> bool:
        """
        Handle special built-in commands.
        
        Processes built-in commands that bypass normal execution:
        - exit, quit, q: Exit shell
        - clear, cls: Clear terminal screen
        - tips: Show quick tips
        
        Args:
            command: User input command string
            
        Returns:
            bool: True if command was special (handled), False otherwise
            
        Examples:
            >>> runner._handle_special_commands("exit")
            True  # Exits shell
            
            >>> runner._handle_special_commands("data read users")
            False  # Not special, should execute normally
            
        Notes:
            - Case-insensitive matching
            - Special commands do not go through CommandExecutor
            - clear/cls uses os.system() (terminal-specific exception)
        """
        if self._is_special_command(command):
            cmd_lower = command.lower()

            if cmd_lower in SPECIAL_COMMANDS_EXIT:
                self.zos.display.zDeclare(
                    MSG_GOODBYE,
                    color=COLOR_INFO, indent=INDENT_NORMAL, style=STYLE_SINGLE
                )
                self.running = False
                return True

            if cmd_lower in SPECIAL_COMMANDS_CLEAR:
                self._clear_terminal()
                return True

            if cmd_lower == CMD_TIPS:
                self.zos.display.write_block(self.help_system.get_quick_tips())
                return True

        return False

    def _display_result(self, result: Any) -> None:
        """
        Display command execution result in terminal mode.
        
        Fallback display for legacy commands that return data dictionaries.
        Modern commands use UI adapter pattern (return None, use zDisplay).
        
        Args:
            result: Command execution result (dict, str, or None)
            
        Returns:
            None
            
        Examples:
            >>> runner._display_result({"error": "Not found"})
            # Displays: Error: Not found
            
            >>> runner._display_result({"success": "Done", "note": "Details"})
            # Displays: Done
            #           Details
            
            >>> runner._display_result("Some data")
            # Displays: Some data
            
        Notes:
            - For programmatic access, bypass shell and use subsystems directly
            - Suppresses JSON output for dicts without error/success keys
            - Commands should display their own messages, not rely on returns
        """
        if result is None:
            return

        if isinstance(result, dict):
            if KEY_ERROR in result:
                self.zos.display.zDeclare(
                    MSG_ERROR_PREFIX.format(result[KEY_ERROR]),
                    color=COLOR_ERROR, indent=INDENT_NORMAL, style=STYLE_SINGLE
                )
            elif KEY_SUCCESS in result:
                self.zos.display.zDeclare(
                    result[KEY_SUCCESS],
                    color=COLOR_SUCCESS, indent=INDENT_NORMAL, style=STYLE_SINGLE
                )
                if KEY_NOTE in result:
                    self.zos.display.zDeclare(
                        result[KEY_NOTE],
                        color=COLOR_INFO, indent=INDENT_NESTED, style=STYLE_SINGLE
                    )
            # Suppress JSON output if dict has no "error" or "success"
            # (commands already displayed friendly messages)

        elif isinstance(result, str):
            self.zos.display.zDeclare(
                result,
                color=COLOR_DATA, indent=INDENT_NORMAL, style=STYLE_SINGLE
            )

        # Note: Removed automatic JSON fallback for dicts without error/success
        # Commands should display their own messages, not rely on JSON dumps

    def execute_command(self, command: str) -> Any:
        """
        Execute a single command (useful for testing or scripting).
        
        Delegates to CommandExecutor for command routing and execution.
        
        Args:
            command: Command string to execute
            
        Returns:
            Any: Result from command execution
            
        Examples:
            >>> runner.execute_command("data read users")
            None  # UI adapter - displays via zDisplay
            
        Notes:
            - Used primarily for testing
            - For production, use run() for full REPL loop
        """
        return self.executor.execute(command)

    # ============================================================
    # DRY HELPER FUNCTIONS
    # ============================================================

    def _get_wizard_mode(self) -> Dict[str, Any]:
        """
        Get wizard mode state from zSession.
        
        Centralized access point for wizard canvas state. Uses
        SESSION_KEY_WIZARD_MODE constant from zConfig.
        
        Returns:
            Dict[str, Any]: Wizard mode state with keys: active, lines, format
            
        Examples:
            >>> wizard_state = runner._get_wizard_mode()
            >>> wizard_state
            {"active": True, "lines": ["cmd1", "cmd2"], "format": None}
            
        Notes:
            - Returns empty dict if wizard_mode not yet initialized
            - Centralized access prevents key name inconsistencies
            - State persisted across command executions in zSession
        """
        return self.zos.session.get(SESSION_KEY_WIZARD_MODE, {})

    def _is_special_command(self, command: str) -> bool:
        """
        Check if command is a special built-in command.
        
        Determines if command should be handled directly by runner
        (bypassing CommandExecutor and zParser).
        
        Args:
            command: User input command string
            
        Returns:
            bool: True if command is special, False otherwise
            
        Examples:
            >>> runner._is_special_command("exit")
            True
            
            >>> runner._is_special_command("data read users")
            False
            
        Notes:
            - Case-insensitive comparison
            - Special commands: exit, quit, q, clear, cls, tips
            - Used to short-circuit normal execution flow
        """
        cmd_lower = command.lower()
        return (
            cmd_lower in SPECIAL_COMMANDS_EXIT or
            cmd_lower in SPECIAL_COMMANDS_CLEAR or
            cmd_lower == CMD_TIPS
        )

    def _clear_terminal(self) -> None:
        """
        Clear terminal screen.
        
        Uses os.system() to call platform-specific clear command.
        This is a documented exception to zCLI's mode-agnostic design,
        as terminal clearing is inherently terminal-specific and not
        available via zDisplay.
        
        Returns:
            None
            
        Examples:
            >>> runner._clear_terminal()
            # Clears screen on POSIX: 'clear'
            # Clears screen on Windows: 'cls'
            
        Notes:
            - POSIX (Linux/macOS): Uses 'clear' command
            - Windows: Uses 'cls' command
            - Only works in terminal mode (not Bifrost/Walker)
            - Direct system call is required (no zDisplay equivalent)
        """
        os.system(CLEAR_CMD_POSIX if os.name == 'posix' else CLEAR_CMD_WINDOWS)


def launch_shell(zos: Any) -> str:
    """
    Launch interactive shell from within the UI.
    
    Wrapper function for launching mode-agnostic shell from menu-driven UI.
    Displays transition messages and delegates to zos.run_shell().
    
    Args:
        zos: The zOS framework instance
        
    Returns:
        str: Status message "Returned from zCLI shell"
        
    Examples:
        >>> launch_shell(zos)
        # Displays: Launching zCLI Shell from UI
        # Displays: Type 'exit' to return to UI menu
        # [runs shell - output adapts to current mode]
        # Displays: Returning to UI menu
        "Returned from zCLI shell"
        
    Notes:
        - Used when transitioning from UI menu to shell
        - Provides user feedback about mode transition
        - Returns status string for UI menu display
    """
    zos.display.zDeclare(
        "Launching zCLI Shell from UI",
        color=COLOR_EXTERNAL, indent=INDENT_NORMAL, style=STYLE_FULL
    )

    zos.display.zDeclare(
        "Type 'exit' to return to UI menu",
        color=COLOR_INFO, indent=INDENT_NORMAL, style=STYLE_SINGLE
    )

    zos.run_shell()

    zos.display.zDeclare(
        "Returning to UI menu",
        color=COLOR_EXTERNAL, indent=INDENT_NORMAL, style=STYLE_FULL
    )

    return "Returned from zCLI shell"

