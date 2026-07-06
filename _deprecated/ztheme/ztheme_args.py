"""
zTheme Command Arguments

Defines CLI arguments for the 'ztheme' command which builds
the zTheme CSS framework.
"""

import argparse


def add_subparser(subparsers) -> argparse.ArgumentParser:
    """
    Add the 'ztheme' subcommand to the parser.
    
    Args:
        subparsers: The subparsers object from ArgumentParser
        
    Returns:
        The created ztheme subparser
    """
    parser = subparsers.add_parser(
        "ztheme",
        help="Build zTheme CSS framework",
        description="Concatenate all zTheme CSS source files into dist/ztheme.css"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed build output"
    )

    return parser
