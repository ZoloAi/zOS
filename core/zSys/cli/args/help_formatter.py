"""
zOS CLI help formatter.

Aesthetics-only wrapper around argparse's help output — colors section
headings and tightens column layout via the `Colors` SSOT. Changes no
command names, help text, or descriptions.
"""

import argparse

from zSys.formatting import Colors


class ZoloHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """RawDescription formatter with colored headings + roomier help column."""

    def __init__(self, prog):
        super().__init__(prog, max_help_position=30, indent_increment=2)

    def start_section(self, heading):
        if heading:
            heading = f"{Colors.BOLD}{Colors.PRIMARY}{heading}{Colors.RESET}"
        return super().start_section(heading)
