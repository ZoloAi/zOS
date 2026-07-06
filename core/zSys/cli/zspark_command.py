# zSys/cli/zspark_command.py
"""
zSpark command execution pipeline.

Refactor goals:
- Keep handle_zspark_command() as a thin orchestrator
- Isolate side effects (printing, framework init, exception formatting)
- Preserve lazy imports to avoid premature framework initialization
"""

from __future__ import annotations

from typing import Any, Tuple, Optional


def handle_zspark_command(
    boot_logger,
    Path,
    zspark_path: str,
    verbose: bool = False,
    dev_mode: bool = False,
) -> int:
    """
    Execute declarative zSpark.*.zolo configuration file (native zolo syntax with LSP support).
    Returns exit code (0 success, 1 error).
    """
    zspark_file, exit_code = _validate_zspark_file(boot_logger, Path, zspark_path, verbose)
    if exit_code != 0:
        return exit_code

    try:
        zspark_config, exit_code = _parse_zspark_file(boot_logger, Path, zspark_file, verbose)
        if exit_code != 0:
            return exit_code

        mode = _configure_zspark(boot_logger, zspark_config, zspark_file, verbose, dev_mode)

        if verbose:
            boot_logger.print_buffered_logs()

        zcli = _init_zos_framework(zspark_config, boot_logger)
        # Record the booting zSpark path so a zero-downtime self-replace
        # (z swap) can re-boot the SAME app as the green instance.
        try:
            zcli.zspark_file = str(zspark_file)
        except Exception:  # pylint: disable=broad-except
            pass
        _log_zspark_loaded(zcli, zspark_file.name, mode)

        migration_exit = _run_schema_migrations(zcli, zspark_file)
        if migration_exit != 0:
            return migration_exit

        zcli.run()
        return 0

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_zspark_exception(boot_logger, e, verbose)


def run_spark_with_config(
    boot_logger,
    zspark_file,
    zspark_config: dict,
    verbose: bool = False,
    dev_mode: bool = False,
) -> int:
    """
    Execute a pre-parsed zSpark config dict.
    Used by z raven --run to inject raven config before booting.
    """
    import os as _os  # pylint: disable=import-outside-toplevel
    try:
        mode = _configure_zspark(boot_logger, zspark_config, zspark_file, verbose, dev_mode)
        if verbose:
            boot_logger.print_buffered_logs()
        zcli = _init_zos_framework(zspark_config, boot_logger)
        try:
            zcli.zspark_file = str(zspark_file)
        except Exception:  # pylint: disable=broad-except
            pass
        _log_zspark_loaded(zcli, zspark_file.name, mode)
        migration_exit = _run_schema_migrations(zcli, zspark_file)
        if migration_exit != 0:
            return migration_exit
        zcli.run()
        return 0
    except SystemExit as e:
        # When running as the zRaven runner, the signal handler normally skips
        # sys.exit() so post-run work (hints, teardown) can continue. This
        # catch is a safety net for any remaining code paths that still call
        # sys.exit() — we absorb it and return normally so _handle_run proceeds.
        if _os.environ.get("ZRAVEN_RUNNER") == "1":
            return int(e.code) if e.code is not None else 0
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_zspark_exception(boot_logger, e, verbose)


def _run_schema_migrations(zcli: Any, zspark_file: Any) -> int:
    """
    Auto-detect and run schema migrations before the app starts.

    Behaviour:
    SSOT gate (single behavior for every entry point):
      - The boot path NEVER mutates the schema. It only verifies, via a dry-run
        diff, that the data on disk matches the declared schema (the SSOT).
      - If anything is pending (drift), zOS refuses to launch and prints a clear,
        actionable reason — running on a drifted schema is undefined behavior.
      - zRaven boots through this very function, so it inherits the exact same
        refusal: if zSpark won't launch on drift, neither will zRaven. There is no
        separate auto-apply path. Applying changes is reserved for the one explicit,
        intentional command: `z migrate`.
      - No Models/ dir or no migration-enabled schemas: no-op (returns 0).
    """
    # Support both "models" and "Models" directory names
    models_dir = next(
        (zspark_file.parent / d for d in ("models", "Models") if (zspark_file.parent / d).exists()),
        None,
    )
    if not models_dir:
        return 0

    schema_files = sorted(models_dir.glob("*.zolo"))
    if not schema_files:
        return 0

    try:
        from zOS.L3_Abstraction.m_zData.zData_modules.migration.migration_engine import (  # pylint: disable=import-outside-toplevel
            MigrationEngine,
        )
    except ImportError:
        return 0  # migration module unavailable — skip silently

    migration_engine = MigrationEngine(zcli, zcli.logger)
    drifted: list = []  # [(schema_name, human-readable drift summary), ...]

    for schema_file in schema_files:
        schema_name = schema_file.stem           # e.g. "zSchema.media"
        schema_path = f"@.models.{schema_name}"  # e.g. "@.models.zSchema.media"

        try:
            schema = zcli.loader.handle(schema_path)
        except Exception:  # pylint: disable=broad-except
            schema = None
        if not schema:
            continue

        meta = schema.get("zMeta", {})
        if not meta.get("zMigration"):
            continue

        zcli.data.orchestrator.load_schema(schema)

        # Single SSOT gate — verify only, never mutate. zRaven boots through this
        # same path, so it inherits the refusal (no auto-apply branch). The only
        # writer of schema changes is the explicit `z migrate` command.
        result = migration_engine.migrate(
            orchestrator=zcli.data.orchestrator,
            new_schema_path=schema_path,
            auto_approve=False,
            dry_run=True,
        )
        diff = result.get("diff", {}) or {}
        if diff.get("has_changes"):
            summary = _summarize_schema_drift(diff)
            drifted.append((schema_name, summary))
            zcli.logger.error(f"[zMigrate] Schema drift in {schema_name}: {summary}")

    if drifted:
        _print_drift_refusal(zspark_file, drifted)
        return 1

    return 0


def _summarize_schema_drift(diff: dict) -> str:
    """One-line human description of a schema diff, for the refusal message."""
    parts = []
    added = diff.get("tables_added") or []
    dropped = diff.get("tables_dropped") or []
    if added:
        parts.append(f"+{len(added)} table ({', '.join(added)})")
    if dropped:
        parts.append(f"-{len(dropped)} table ({', '.join(dropped)})")
    for table, ch in (diff.get("tables_modified") or {}).items():
        seg = []
        n_add = len(ch.get("columns_added", {}) or {})
        n_drop = len(ch.get("columns_dropped", []) or [])
        n_mod = len(ch.get("columns_modified", {}) or {})
        if n_add:
            seg.append(f"+{n_add} col")
        if n_drop:
            seg.append(f"-{n_drop} col")
        if n_mod:
            seg.append(f"~{n_mod} col")
        parts.append(f"~{table} ({', '.join(seg)})")
    return "; ".join(parts) or "changes pending"


def _print_drift_refusal(zspark_file: Any, drifted: list) -> None:
    """Graceful, actionable refusal — zOS will not launch on a drifted schema."""
    bar = "═" * 64
    lines = [
        "",
        bar,
        "⛔  zOS refused to launch — schema drift detected",
        bar,
        "   The data on disk no longer matches the declared schema(s):",
        "",
    ]
    for name, summary in drifted:
        lines.append(f"     • {name:<22} {summary}")
    lines += [
        "",
        "   The schema is the source of truth, not the data — running on a",
        "   drifted schema is unsafe. Apply the pending migration, then relaunch:",
        "",
        f"     z migrate {zspark_file.name}",
        "",
        "   (zRaven boots through this same gate — tests won't run on a drifted",
        "    schema either. Migrate first.)",
        bar,
        "",
    ]
    print("\n".join(lines))


def _init_zos_framework(zspark_config: dict, boot_logger):
    """
    Lazy-init zOS framework from zSpark config and flush bootstrap logs into framework logger if present.
    """
    from zOS import zOS  # pylint: disable=import-outside-toplevel

    zcli = zOS(zspark_config)

    # Flush bootstrap logs into framework logger (if available)
    if hasattr(zcli, "logger"):
        boot_logger.flush_to_framework(zcli.logger, verbose=False)

    return zcli


def _log_zspark_loaded(zcli, filename: str, mode: str) -> None:
    """
    Log zSpark configuration loaded using unified log format.
    """
    # Use session framework logger for consistency with other subsystem initialization logs
    if hasattr(zcli, 'logger') and hasattr(zcli.logger, 'session_framework'):
        zcli.logger.session_framework.info(f"zSpark Configuration Loaded ({filename} | Mode: {mode})")
    else:
        # Fallback to print if logger not available (should not happen)
        print(f"\nzSpark Configuration Loaded ({filename} | Mode: {mode})\n")


def _handle_zspark_exception(boot_logger, exc: Exception, verbose: bool) -> int:
    """
    Normalize zSpark runtime exceptions into consistent logging + user output.
    """
    error_type = "Missing required key" if isinstance(exc, KeyError) else "Failed to execute"

    boot_logger.error("%s in zSpark: %s", error_type, str(exc))
    if verbose:
        boot_logger.print_buffered_logs()

    print(f"\n❌ Error: {error_type} in zSpark file: {exc}\n")

    # Only print traceback for non-KeyError to keep UX clean
    if not isinstance(exc, KeyError):
        import traceback  # pylint: disable=import-outside-toplevel
        traceback.print_exc()

    return 1


# ---------------------------------------------------------------------
# Expected helpers for zSpark command pipeline.
# ---------------------------------------------------------------------

def _validate_zspark_file(boot_logger, Path, zspark_path: str, verbose: bool):
    """Validate zSpark file exists and has correct extension."""
    zspark_file = Path(zspark_path).resolve()
    if not zspark_file.exists():
        boot_logger.error("zSpark file not found: %s", zspark_path)
        if verbose:
            boot_logger.print_buffered_logs()
        print(f"\n❌ Error: zSpark file not found: {zspark_path}\n")
        return None, 1

    if zspark_file.suffix != ".zolo":
        boot_logger.error(
            "Not a .zolo file: %s (suffix: %s)", zspark_path, zspark_file.suffix
        )
        if verbose:
            boot_logger.print_buffered_logs()
        print(f"\n❌ Error: File must be a .zolo file: {zspark_path}\n")
        return None, 1

    return zspark_file, 0


def _parse_zspark_file(boot_logger, Path, zspark_file, verbose: bool):
    """Parse and validate zSpark.*.zolo file."""
    import sys  # pylint: disable=import-outside-toplevel

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from zlsp.parser import tokenize  # pylint: disable=import-outside-toplevel

    with open(zspark_file, "r", encoding="utf-8") as handle:
        content = handle.read()

    result = tokenize(content, str(zspark_file))

    if result.diagnostics:
        boot_logger.error("Parsing errors in zSpark file:")
        for diag in result.diagnostics:
            severity_map = {1: "ERROR", 2: "WARNING", 3: "INFO", 4: "HINT"}
            severity = severity_map.get(diag.severity, "UNKNOWN")
            boot_logger.error(
                "  [%s] Line %d:%d - %s",
                severity,
                diag.range.start.line + 1,
                diag.range.start.character,
                diag.message,
            )

        if verbose:
            boot_logger.print_buffered_logs()

        print("\n❌ Error: Failed to parse zSpark file:\n")
        for diag in result.diagnostics:
            severity_map = {1: "ERROR", 2: "WARNING", 3: "INFO", 4: "HINT"}
            severity = severity_map.get(diag.severity, "UNKNOWN")
            print(f"  [{severity}] Line {diag.range.start.line + 1}: {diag.message}")
        print()
        return None, 1

    if not isinstance(result.data, dict) or "zSpark" not in result.data:
        boot_logger.error("Invalid zSpark file: missing 'zSpark' root key")
        if verbose:
            boot_logger.print_buffered_logs()
        print("\n❌ Error: Invalid zSpark file format\n")
        print(
            "zSpark.*.zolo files must contain a root 'zSpark' key with configuration "
            "dictionary.\n"
        )
        return None, 1

    return result.data["zSpark"], 0


def _configure_zspark(boot_logger, zspark_config: dict, zspark_file, verbose: bool, dev_mode: bool) -> str:
    """Apply overrides and log zSpark configuration."""
    if dev_mode:
        zspark_config["zEnv"] = "Development"

    if verbose:
        zspark_config["zLog"] = "DEBUG"

    boot_logger.session("zSpark file: %s", zspark_file.name)
    boot_logger.session("Configuration keys: %d", len(zspark_config))

    zenv = zspark_config.get("zEnv", zspark_config.get("zState", zspark_config.get("deployment", "Production (default)")))
    zenv_str = f"{zenv} (--dev override)" if dev_mode else zenv
    boot_logger.session("zEnv: %s", zenv_str)

    mode = zspark_config.get("zMode", "N/A")
    boot_logger.session("Mode: %s", mode)

    logger_level = zspark_config.get("zLog", zspark_config.get("zScrap", "INFO (default)"))
    logger_str = "DEBUG (--verbose override)" if verbose else logger_level
    boot_logger.session("zLog: %s", logger_str)

    return mode
