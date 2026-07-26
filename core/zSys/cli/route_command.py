from pathlib import Path


def _handle_build_agents():
    """Run zAgents builder — rebuilds generated/ from src/*.md."""
    import importlib.util  # pylint: disable=import-outside-toplevel

    # Try installed zOS package first
    try:
        import zOS.zAgents.builder as _builder  # pylint: disable=import-outside-toplevel
        _builder.build_all()
        return 0
    except ImportError:
        pass

    # Dev fallback: walk up to monorepo zAgents/builder.py
    try:
        import zOS as _zos  # pylint: disable=import-outside-toplevel
        candidates = [
            Path(_zos.__file__).parent.parent / "zAgents" / "builder.py",
            Path(_zos.__file__).parent.parent.parent / "zAgents" / "builder.py",
        ]
        for builder_path in candidates:
            if builder_path.exists():
                spec = importlib.util.spec_from_file_location("builder", builder_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.build_all()
                return 0
    except Exception:  # pylint: disable=broad-except
        pass

    print("\n[zAgents] ERROR: builder.py not found. Run manually: python zAgents/builder.py\n")
    return 1


def _handle_agents_command(args):
    """Run z agents — inject zolo instructions into the current workspace."""
    import importlib.util  # pylint: disable=import-outside-toplevel

    force = getattr(args, "force", False)
    assoc = getattr(args, "assoc", False)
    build = getattr(args, "build", False)

    if build:
        rc = _handle_build_agents()
        if rc != 0:
            return rc

    # 1. Try as part of the installed zOS package (standard path)
    try:
        import zOS.zAgents.agents_cli as _agents_cli  # pylint: disable=import-outside-toplevel
        _agents_cli.run(force=force, assoc=assoc)
        return 0
    except ImportError:
        pass

    # 2. Try standalone agents_cli or zAgents package
    for mod in ("agents_cli", "zAgents.agents_cli"):
        try:
            import importlib  # pylint: disable=import-outside-toplevel
            _agents_cli = importlib.import_module(mod)
            _agents_cli.run(force=force, assoc=assoc)
            return 0
        except ImportError:
            continue

    # 3. Dev fallback: walk up from zOS package to find monorepo zAgents/
    try:
        import zOS as _zos  # pylint: disable=import-outside-toplevel
        # In dev: zOS-OpenCore/core/__init__.py → repo root → ../zAgents/
        repo_candidates = [
            Path(_zos.__file__).parent.parent / "zAgents" / "agents_cli.py",       # editable core/
            Path(_zos.__file__).parent.parent.parent / "zAgents" / "agents_cli.py", # monorepo root
        ]
        for agents_cli_path in repo_candidates:
            if agents_cli_path.exists():
                spec = importlib.util.spec_from_file_location("agents_cli", agents_cli_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.run(force=force, assoc=assoc)
                return 0
    except Exception:  # pylint: disable=broad-except
        pass

    print("\n[zAgents] ERROR: agents_cli not found. Run: z agents  after a full install.\n")
    return 1


def _handle_raven_command(logger, args, verbose):
    from zSys.cli.raven_command import handle_raven_command  # pylint: disable=import-outside-toplevel
    return handle_raven_command(logger, args, verbose=verbose)


def _handle_demos_command(args):
    from zSys.cli.demos_command import handle_demos_command  # pylint: disable=import-outside-toplevel
    return handle_demos_command(args)


def _handle_reload_command(logger, args, verbose):
    from zSys.cli.reload_command import handle_reload_command  # pylint: disable=import-outside-toplevel
    return handle_reload_command(logger, args, verbose=verbose)


def _handle_swap_command(logger, args, verbose):
    from zSys.cli.swap_command import handle_swap_command  # pylint: disable=import-outside-toplevel
    return handle_swap_command(logger, args, verbose=verbose)


def _handle_visitors_command(logger, args, verbose):
    from zSys.cli.visitors_command import handle_visitors_command  # pylint: disable=import-outside-toplevel
    return handle_visitors_command(logger, args, verbose=verbose)


def route_command(
    args,
    python_file,
    zspark_file,
    verbose,
    dev_mode,
    logger,
    cli,
    sys_module,
    get_zos_package,
    get_version,
    get_package_info,
    detect_installation_type,
):
    """Route to appropriate command handler."""
    if python_file:
        return cli.handle_script_command(
            logger, sys_module, Path, python_file, verbose=verbose
        )

    if zspark_file:
        return cli.handle_zspark_command(
            logger, Path, zspark_file, verbose=verbose, dev_mode=dev_mode
        )

    # Get zos_package for handlers that need it
    zos_package = get_zos_package()

    from zSys.cli.patch_command import handle_patch_command  # pylint: disable=import-outside-toplevel

    handlers = {
        "patch": lambda: handle_patch_command(
            verbose=verbose, live=getattr(args, "live", False),
            force=getattr(args, "force", False),
        ),
        "shell": lambda: cli.handle_shell_command(logger, verbose=verbose),
        "login": lambda: cli.handle_login_command(logger, args, verbose=verbose),
        "push": lambda: cli.handle_push_command(logger, args, verbose=verbose),
        "config": lambda: cli.handle_config_command(logger, verbose=verbose),
        "ztests": lambda: cli.handle_ztests_command(
            logger, Path, zos_package, verbose=verbose
        ),
        "migrate": lambda: cli.handle_migrate_command(
            logger, Path, args, verbose=verbose
        ),
        "requirements": lambda: cli.handle_requirements_command(
            logger, Path, args, verbose=verbose
        ),
        "uninstall": lambda: cli.handle_uninstall_command(
            logger, Path, zos_package, verbose=verbose
        ),
        "agents":   lambda: _handle_agents_command(args),
        "raven": lambda: _handle_raven_command(logger, args, verbose),
        "demos": lambda: _handle_demos_command(args),
        "reload": lambda: _handle_reload_command(logger, args, verbose),
        "swap": lambda: _handle_swap_command(logger, args, verbose),
        "visitors": lambda: _handle_visitors_command(logger, args, verbose),
    }

    if args.command in handlers:
        return handlers[args.command]()

    # Default: show info banner
    if verbose:
        logger.print_buffered_logs()

    cli.display_info(
        logger, zos_package, get_version, get_package_info, detect_installation_type
    )
    return 0
