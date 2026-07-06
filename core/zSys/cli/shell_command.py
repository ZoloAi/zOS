# zSys/cli/shell_command.py
"""
Interactive zShell command.
"""


def handle_shell_command(boot_logger, verbose: bool = False):
    """
    Handle shell command.

    Args:
        boot_logger: BootstrapLogger instance
        verbose: If True, show bootstrap logs and initialization output
    """
    from zOS import zOS  # pylint: disable=import-outside-toplevel

    cli = zOS(verbose=verbose)
    boot_logger.flush_to_framework(cli.logger, verbose=verbose)
    cli.run_shell()
