# zSys/cli/info_command.py
"""
Info banner command.
"""


def display_info(boot_logger, zos_package, get_version, get_package_info, detect_install_type):
    """
    Display zOS information banner.

    Args:
        boot_logger: BootstrapLogger instance
        zos_package: Imported zOS package (zCLI is a mode, not the package)
        get_version: Function to get package version
        get_package_info: Function to get package info dict
        detect_install_type: Function to detect install type
    """
    from zSys.formatting import Colors  # pylint: disable=import-outside-toplevel

    install_type = detect_install_type(zos_package, detailed=False)
    pkg_info = get_package_info()

    title = f"{Colors.BOLD}{Colors.PRIMARY}{pkg_info['name']} {get_version()}{Colors.RESET}"
    install = f"{Colors.DARK_GRAY}({install_type}){Colors.RESET}"

    print(f"\n{title} {install}")
    print(f"{Colors.ITALIC}{Colors.zInfo}An LLM-native declarative framework{Colors.RESET}")
    print(f"{Colors.ITALIC}{Colors.zInfo}for building, running, and verifying zApps{Colors.RESET}\n")
    print(f"{Colors.DIM}Run `z --help` to see available commands.{Colors.RESET}\n")
    print(f"{Colors.DIM}By {pkg_info['author']}{Colors.RESET}")
    print(f"{Colors.DIM}License: MIT{Colors.RESET}\n")
