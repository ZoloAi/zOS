# zSys/cli/config_command.py
"""
Machine/environment config display command.
"""


def handle_config_command(boot_logger, verbose: bool = False):
    """
    Handle config command - display only (read-only).

    Args:
        boot_logger: BootstrapLogger instance
        verbose: If True, show bootstrap logs on stdout
    """
    from zOS import zOS  # pylint: disable=import-outside-toplevel

    cli = zOS({"zMode": "zCLI", "zLog": "PROD", "zEnv": "Production"})
    boot_logger.flush_to_framework(cli.logger, verbose=verbose)

    cli.config.persistence.show_machine_config()
    cli.config.persistence.show_environment_config()
