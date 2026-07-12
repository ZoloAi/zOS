# zOS/core/L3_Abstraction/p_zShell/zShell.py

"""
zShell Subsystem Facade - Simple 3-method API for interactive shell mode.

Facade pattern hiding 2,340 lines of complexity across 3 modules:
- ShellRunner (REPL loop, history, prompts)
- CommandExecutor (18 command types, wizard canvas)
- HelpSystem (welcome, help, tips)

Public API:
    zShell(zos) - Main facade class
        .run_shell() - Start REPL loop
        .execute_command(cmd) - Execute single command
        .show_help() - Display help
    
    launch_shell(zos) - Launch from UI menu

Usage:
    >>> from zOS.L3_Abstraction.p_zShell import zShell
    >>> shell = zShell(zos)
    >>> shell.run_shell()  # Interactive REPL
    >>> shell.execute_command("data read users")  # Single command
    >>> shell.show_help()  # Display help
"""


__version__ = "1.0.0"
from zOS import Any
from .shell_modules.shell_runner import ShellRunner, launch_shell as launch_shell_func
from .shell_modules.shell_executor import CommandExecutor
from .shell_modules.shell_help import HelpSystem
from .shell_modules.zshell_constants import (
    COLOR_SHELL,
    MSG_READY,
    STYLE_FULL,
    INDENT_NORMAL
)


class zShell:
    """
    Interactive shell facade with 3-method API.
    
    Delegates to ShellRunner (REPL), CommandExecutor (routing), HelpSystem (help).
    Displays "zShell Ready" on initialization.
    
    Methods:
        run_shell() - Start interactive REPL loop
        execute_command(cmd) - Execute single command (for testing)
        show_help() - Display welcome and help
    """

    def __init__(self, zos: Any) -> None:
        """Initialize zShell facade with ShellRunner, CommandExecutor, and HelpSystem."""
        self.zos: Any = zos
        self.logger: Any = zos.logger
        self.display: Any = zos.display
        self.mycolor: str = COLOR_SHELL

        # Initialize subcomponents (Level 3 modules)
        self.interactive: ShellRunner = ShellRunner(zos)
        self.executor: CommandExecutor = CommandExecutor(zos)
        self.help_system: HelpSystem = HelpSystem(display=self.display, zos=self.zos)

        # Display ready message
        self.display.zDeclare(MSG_READY, color=self.mycolor, indent=INDENT_NORMAL, style=STYLE_FULL)

    def run_shell(self) -> None:
        """Start interactive REPL loop. Blocks until user exits (exit, Ctrl+C, Ctrl+D)."""
        return self.interactive.run()

    def execute_command(self, command: str) -> Any:
        """Execute single command without REPL. Returns result (or None for UI commands)."""
        return self.executor.execute(command)

    def show_help(self) -> Any:
        """Display welcome message, available commands, and quick tips."""
        return self.help_system.show_help()


def launch_shell(zos: Any) -> str:
    """Launch interactive shell from UI menu. Returns 'Returned from zCLI shell'."""
    return launch_shell_func(zos)
