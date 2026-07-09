# zSys/cli/requirements_command.py
"""
`z requirements` — installs an app's declared zRequirements.

The explicit, intentional write path for zRequirements (mirrors `z migrate`
for schema drift): zSpark boot only ever verifies and refuses to launch on
missing deps (see zSys/cli/zspark_command.py::_run_requirements_check); this
command is the one place that actually runs `pip install`.
"""


def _resolve_deployment(app_file) -> str:
    """Best-effort deployment name read from the app's zSpark `zEnv:` key.

    Same precedence as WorkspaceResolver.load_dotenv (SSOT for deployment
    resolution). Falls back to "development" if app_file isn't a parseable
    zSpark file — this command also accepts any file inside the workspace.
    """
    if app_file.suffix != ".zolo":
        return "development"
    try:
        from zlsp.parser import tokenize  # pylint: disable=import-outside-toplevel

        content = app_file.read_text(encoding="utf-8")
        result = tokenize(content, str(app_file))
        data = result.data if isinstance(result.data, dict) else {}
        spark = data.get("zSpark", {}) if isinstance(data.get("zSpark"), dict) else {}
        for key in ("zEnv", "zState", "deployment", "Deployment", "DEPLOYMENT"):
            if spark.get(key):
                return str(spark[key]).lower()
    except Exception:  # pylint: disable=broad-except
        pass
    return "development"


def handle_requirements_command(boot_logger, Path, args, verbose: bool = False) -> int:
    """
    Handle `z requirements <app_file>` — thin CLI wrapper.

    Returns:
        int: Exit code (0 = success/nothing to do, 1 = error or user declined)
    """
    app_file = Path(args.app_file).resolve()
    if not app_file.exists():
        boot_logger.error("App file not found: %s", args.app_file)
        if verbose:
            boot_logger.print_buffered_logs()
        print(f"\n❌ Error: App file not found: {args.app_file}\n")
        return 1

    workspace_dir = app_file.parent if app_file.is_file() else app_file
    deployment = _resolve_deployment(app_file)

    from zOS.L1_Foundation.a_zConfig.zConfig_modules.environment.config_requirements import (  # pylint: disable=import-outside-toplevel
        read_declared_requirements,
        find_missing_requirements,
        install_requirements,
    )

    specs = read_declared_requirements(workspace_dir, deployment)
    if not specs:
        print(f"\n✓ No zRequirements declared for {workspace_dir.name} — nothing to do.\n")
        return 0

    missing = find_missing_requirements(specs)
    if not missing:
        print(f"\n✓ All {len(specs)} declared requirement(s) already installed.\n")
        return 0

    print(f"\n[z requirements] Missing {len(missing)} of {len(specs)} declared package(s):")
    for spec in missing:
        print(f"  • {spec}")

    if getattr(args, "dry_run", False):
        print("\n(dry run — nothing installed)\n")
        return 0

    if not getattr(args, "auto_approve", False):
        answer = input(f"\nInstall {len(missing)} package(s) via pip now? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("\nAborted — no packages installed.\n")
            return 1

    print(f"\n[z requirements] Installing: {', '.join(missing)} ...")
    ok, output = install_requirements(missing)
    if ok:
        print("✓ Installed successfully.\n")
        return 0

    print(f"✗ pip install failed:\n{output}\n")
    return 1
