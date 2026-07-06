# zSys/cli/uninstall_command.py
"""
Uninstall command.
"""


def handle_uninstall_command(boot_logger, Path, zos_package, verbose: bool = False):
    """
    Handle uninstall command with interactive menu.

    Args:
        boot_logger: BootstrapLogger instance
        Path: pathlib.Path class
        zos_package: Imported zOS package (for __file__ access)
        verbose: If True, show bootstrap logs on stdout
    """
    zos_package_dir = Path(zos_package.__file__).parent
    from zOS import zOS  # pylint: disable=import-outside-toplevel

    uninstall_cli = zOS(
        {
            "zWorkspace": str(zos_package_dir),
            "zVaFile": "@.UI.zUI.zcli_sys",
            "zBlock": "Uninstall",
        }
    )
    boot_logger.flush_to_framework(uninstall_cli.logger, verbose=verbose)

    uninstall_cli.walker.run()
