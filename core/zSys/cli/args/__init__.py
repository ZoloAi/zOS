"""
CLI Argument Parser for zOS Framework

This module provides a modular CLI argument parsing system where each
command group is defined in its own file for better maintainability.

Structure:
    zSys/cli/args/
        __init__.py          - Main parser factory (this file)
        shell_args.py        - Shell command arguments
        config_args.py       - Config command arguments
        ztests_args.py       - zTests command arguments
        migrate_args.py      - Migrate command arguments
        uninstall_args.py    - Uninstall command arguments
        
Usage:
    from zSys.cli.args import create_parser
    parser = create_parser()
    args = parser.parse_args()
"""

import argparse
from typing import Optional

from zSys.formatting import Colors
from .help_formatter import ZoloHelpFormatter

# Implicit launch forms handled by detect_special_files (no subcommand needed).
# Documented here so `zolo --help` advertises them alongside the subcommands.
# Paths are regular filesystem paths (relative to cwd, or absolute) — not zPaths.
_LAUNCH_EPILOG = (
    f"{Colors.BOLD}{Colors.PRIMARY}run directly{Colors.RESET} (no subcommand):\n"
    f"  {Colors.zInfo}zolo <app>{Colors.RESET}         zSpark.<app>.zolo in the current dir\n"
    f"  {Colors.zInfo}zolo <path>.zolo{Colors.RESET}   a zSpark file by path (relative or absolute)\n"
    f"  {Colors.zInfo}zolo <path>.py{Colors.RESET}     a Python file, run in the zOS context\n"
    f"\n{Colors.DIM}Learn more at https://zolo.media{Colors.RESET}\n"
)

# Import command modules (order here is cosmetic; --help order is set in create_parser)
from . import config_args
from . import scaffold_args
from . import shell_args
from . import demos_args
from . import reload_args
from . import swap_args
from . import visitors_args
from . import raven_args
from . import migrate_args
from . import agents_args
from . import login_args
from . import push_args
from . import patch_args
from . import uninstall_args
from . import ztests_args


def create_parser(version: str) -> argparse.ArgumentParser:
    """
    Create and configure the main argument parser for zOS.
    
    Args:
        version: Version string to display (e.g., "1.5.8")
        
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="An LLM-native declarative framework\nfor building, running, and verifying zApps",
        prog="zolo",
        formatter_class=ZoloHelpFormatter,
        epilog=_LAUNCH_EPILOG,
    )
    
    # Global arguments
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"zOS {version}"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Show bootstrap process and detailed initialization"
    )
    parser.add_argument(
        "--dev", 
        action="store_true",
        help="Enable Development mode (show framework banners and internal flow)"
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest="command",
        metavar="<command>",
        help="Available commands",
    )
    
    # Add each command's subparser — this order = `z --help` display order (UX-ordered).
    # Onboarding / common first; maintenance + questionable/deprecated last.
    config_args.add_subparser(subparsers)
    scaffold_args.add_subparser(subparsers)
    shell_args.add_subparser(subparsers)
    demos_args.add_subparser(subparsers)
    reload_args.add_subparser(subparsers)
    swap_args.add_subparser(subparsers)
    visitors_args.add_subparser(subparsers)
    raven_args.add_subparser(subparsers)
    migrate_args.add_subparser(subparsers)
    agents_args.add_subparser(subparsers)
    login_args.add_subparser(subparsers)
    push_args.add_subparser(subparsers)
    # — maintenance / questionable / deprecated —
    patch_args.add_subparser(subparsers)
    uninstall_args.add_subparser(subparsers)
    ztests_args.add_subparser(subparsers)

    return parser


__all__ = ["create_parser"]
