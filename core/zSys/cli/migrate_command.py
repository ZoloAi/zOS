# zSys/cli/migrate_command.py
"""
Schema migration command.
"""


def handle_migrate_command(boot_logger, Path, args, verbose: bool = False):
    """
    Handle schema migration command - thin CLI wrapper.

    Args:
        boot_logger: BootstrapLogger instance
        zCLI: zCLI class
        Path: pathlib.Path class
        args: Parsed arguments from argparse
        verbose: If True, show bootstrap logs on stdout

    Returns:
        int: Exit code (0 = success, 1 = error)
    """
    app_file = args.app_file
    if not Path(app_file).exists():
        boot_logger.error("App file not found: %s", app_file)
        from zOS import zOS  # pylint: disable=import-outside-toplevel

        temp_z = zOS({"zMode": "zCLI", "zLog": "PROD", "zEnv": "Production"})
        boot_logger.flush_to_framework(temp_z.logger, verbose=verbose)
        temp_z.display.text(f"❌ Error: App file not found: {app_file}")
        return 1

    from zOS import zOS  # pylint: disable=import-outside-toplevel

    z = zOS({"zMode": "zCLI"})
    boot_logger.flush_to_framework(z.logger, verbose=verbose)

    return z.data.cli_migrate(
        app_file=str(Path(app_file).resolve()),
        auto_approve=getattr(args, "auto_approve", False),
        dry_run=getattr(args, "dry_run", False),
        specific_schema=getattr(args, "schema", None),
        force_version=getattr(args, "version", None),
        plan=getattr(args, "plan", False),
        rollback=getattr(args, "rollback", False),
    )
