# zSys/cli/__init__.py
"""
CLI command handlers for zolo entry point.

This module provides handler functions for all `zolo` CLI commands.
"""

from .config_command import handle_config_command
from .info_command import display_info
from .migrate_command import handle_migrate_command
from .requirements_command import handle_requirements_command
from .script_command import handle_script_command
from .shell_command import handle_shell_command
from .login_command import handle_login_command
from .push_command import handle_push_command
from .uninstall_command import handle_uninstall_command
from .zspark_command import handle_zspark_command
from .ztests_command import handle_ztests_command

__all__ = [
    'display_info',
    'handle_shell_command',
    'handle_login_command',
    'handle_push_command',
    'handle_config_command',
    'handle_ztests_command',
    'handle_migrate_command',
    'handle_requirements_command',
    'handle_uninstall_command',
    'handle_script_command',
    'handle_zspark_command',
]
