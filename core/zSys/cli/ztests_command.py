# zSys/cli/ztests_command.py
"""
zTests command (declarative test runner).
"""


def handle_ztests_command(boot_logger, Path, zos_package, verbose: bool = False):
    """
    Handle zTests command (declarative test runner).

    Args:
        boot_logger: BootstrapLogger instance
        Path: pathlib.Path class
        zos_package: Imported zOS package (for __file__ access)
        verbose: If True, show bootstrap logs on stdout

    Returns:
        int: Exit code (0 = success, 1 = error)
    """
    try:
        import __main__  # pylint: disable=import-outside-toplevel

        main_file = Path(__main__.__file__).resolve()
        project_root = main_file.parent
        test_runner_dir = project_root / "zTestRunner"
    except Exception:  # pylint: disable=broad-exception-caught
        zos_path = Path(zos_package.__file__).resolve()
        project_root = zos_path.parent.parent
        test_runner_dir = project_root / "zTestRunner"

    if not test_runner_dir.exists():
        boot_logger.error("zTestRunner directory not found: %s", test_runner_dir)
        from zOS import zOS  # pylint: disable=import-outside-toplevel

        temp_cli = zOS({"zMode": "zCLI"})
        boot_logger.flush_to_framework(temp_cli.logger, verbose=verbose)
        temp_cli.display.text(
            f"Error: zTestRunner directory not found at {test_runner_dir}"
        )
        return 1

    from zOS import zOS  # pylint: disable=import-outside-toplevel

    test_cli = zOS({"zSpace": str(test_runner_dir.absolute()), "zMode": "zCLI"})
    boot_logger.flush_to_framework(test_cli.logger, verbose=verbose)

    test_cli.zspark_obj["zVaFile"] = "@.zUI.test_menu"
    test_cli.zspark_obj["zBlock"] = "zVaF"
    test_cli.walker.run()
    return 0
