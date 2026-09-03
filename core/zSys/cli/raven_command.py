# zSys/cli/raven_command.py
"""
z raven — zRaven test file management.

--gen               Generate structural tests from current zUI (archives previous)
--gen --v v1.0.0    Generate from a versioned UI backup snapshot
--run               Boot the spark and run the active raven
--run --r 2         Boot and run archived raven r2 for current UI version
--run --v 1.0.0     Boot and run latest raven for UI v1.0.0
--run --v 1.0.0 --r 1  Exact coordinate: UI v1.0.0 + raven r1
--hint              Analyze past run history and surface actionable hints
--commit 'label'    Archive a milestone snapshot of the current flow (spark + raven)
--commit --force    Commit even when the flow's last run didn't pass
--clear             Remove committed _zSpark.<flow>.zolo dev flows + orphaned zShots/
--clear --dry-run   Preview what --clear would remove, without deleting anything
--revive <flow>     Restore a flow's own spark+raven from its latest zCommit
--revive <flow> --r 2  Restore from commit c2 specifically instead of the latest
--revive            List every available commit across the project

File layout (under spark workspace):
    zRaven/
        zRaven.{name}.zolo                  ← active (always used by default)
    zVersions/
        tests/
            zRaven.{name}[v2.0.0]_r1.zolo   ← archived snapshots
        commits/
            {name}/c1/, c2/, ...            ← zCommit milestones (see commit_manager.py)
        commits.csv                          ← project-wide commit ledger
        clears.csv                           ← project-wide clear ledger (see clear_manager.py)
        revives.csv                          ← project-wide revive ledger (see revive_manager.py)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


def handle_raven_command(boot_logger, args, verbose: bool = False) -> int:
    gen       = getattr(args, "gen",        False)
    run       = getattr(args, "run",        False)
    hint      = getattr(args, "hint",       False)
    commit    = getattr(args, "commit",     False)
    clear     = getattr(args, "clear",      False)
    revive    = getattr(args, "revive",     False)
    force     = getattr(args, "force",      False)
    dry_run   = getattr(args, "dry_run",    False)
    spark     = getattr(args, "spark",      None)
    ui_ver    = getattr(args, "ui_version", None)
    raven_ver = getattr(args, "raven_ver",  None)
    out       = getattr(args, "out",        None)

    if not gen and not run and not hint and not commit and not clear and not revive:
        _print_usage()
        return 0

    # --clear scans the WHOLE cwd for _zSpark.*.zolo dev flows — it has no
    # single "the" spark to resolve against, unlike every other subcommand.
    if clear:
        flow_filter = clear if isinstance(clear, str) else None
        return _handle_clear(Path.cwd(), flow_filter, force, dry_run)

    # --revive targets a flow NAME straight against zVersions/commits/ — the
    # spark being revived usually doesn't even exist in the working tree yet
    # (that's the whole point), so there's no spark to resolve here either.
    if revive:
        flow_name = revive if isinstance(revive, str) else None
        commit_n = int(raven_ver) if raven_ver else None
        return _handle_revive(Path.cwd(), flow_name, commit_n, force)

    # --run crm_cli / --gen crm_cli  →  spark name hint (middle part of zSpark.*.zolo)
    # --run / --gen                   →  True (auto-detect)
    run_spark_name = run if isinstance(run, str) else None
    gen_spark_name = gen if isinstance(gen, str) else None
    spark_name = run_spark_name or gen_spark_name

    # --spark takes a full path; --run/--gen <name> is a shorthand for the spark stem.
    # Prefer --spark when both are given.
    spark_hint = spark or (
        f"zSpark.{spark_name}.zolo" if spark_name else None
    )

    spark_path = _find_spark(spark_hint)
    if spark_path is None:
        boot_logger.error("[z raven] No zSpark file found.")
        if spark_name:
            print(f"\n❌ No zSpark.{spark_name}.zolo found in cwd.\n")
        else:
            print("\n❌ No zSpark file found. Use --spark to specify one.\n")
        return 1

    if gen:
        # Requested screenshot viewports. Explicit flags win; --all = all three.
        # Empty list → generator falls back to the sticky `# zRavenShots:` header.
        if getattr(args, "all_viewports", False):
            shots = ["mobile", "tablet", "desktop"]
        else:
            shots = [vp for vp in ("mobile", "tablet", "desktop")
                     if getattr(args, vp, False)]
        return _handle_gen(boot_logger, spark_path, ui_ver, out, verbose, shots)

    if hint:
        return _handle_hint(boot_logger, spark_path, verbose)

    if run:
        return _handle_run(boot_logger, spark_path, ui_ver, raven_ver, verbose)

    if commit:
        label = commit if isinstance(commit, str) else None
        return _handle_commit(boot_logger, spark_path, label, force, verbose)

    return 0


# ─────────────────────────────────────────────────────────────────────────────
# --gen
# ─────────────────────────────────────────────────────────────────────────────

def _handle_gen(boot_logger, spark_path: Path, ui_ver, out, verbose: bool, shots=None) -> int:
    try:
        from zSys.cli.raven_generator import generate_raven  # pylint: disable=import-outside-toplevel
        from zSys.cli.zspark_command import _parse_zspark_file  # pylint: disable=import-outside-toplevel
        from zOS import zOS  # pylint: disable=import-outside-toplevel

        # Boot with the spark's OWN zEnv (matches --run). Forcing "Production"
        # here loaded the cloud/S3 backend → "Unable to locate credentials".
        # Generation only resolves the zUI structure, so any non-cloud env works;
        # default to Development when the spark omits zEnv.
        gen_config, exit_code = _parse_zspark_file(boot_logger, Path, spark_path, verbose)
        if exit_code != 0:
            return exit_code
        gen_env = gen_config.get("zEnv") or gen_config.get("zState") or "Development"

        z = zOS({"zMode": "zCLI", "zLog": "PROD", "zEnv": gen_env,
                 "zSpace": str(spark_path.parent.absolute())})
        boot_logger.flush_to_framework(z.logger, verbose=verbose)

        out_path = Path(out) if out else None
        result   = generate_raven(spark_path, target_version=ui_ver,
                                  out_path=out_path, zos=z, shots=shots)

        print(f"\n✅ zRaven generated: {result}")
        if ui_ver:
            print(f"   UI version: {ui_ver}")
        print(f"   Spark:   {spark_path.name}\n")
        return 0

    except FileNotFoundError as e:
        print(f"\n❌ {e}\n")
        return 1
    except Exception as e:  # pylint: disable=broad-exception-caught
        boot_logger.error("[z raven --gen] %s", e)
        print(f"\n❌ zRaven generation failed: {e}\n")
        if verbose:
            import traceback  # pylint: disable=import-outside-toplevel
            traceback.print_exc()
        return 1


# ─────────────────────────────────────────────────────────────────────────────
# --run
# ─────────────────────────────────────────────────────────────────────────────

def _handle_run(boot_logger, spark_path: Path, ui_ver, raven_ver, verbose: bool) -> int:
    """
    Boot the spark + run zRaven tests.

    zRaven is injected into the spark config at runtime — no need for
    `zRaven:` in the zSpark file (it becomes optional/deprecated).
    """
    try:
        from zSys.cli.zspark_command import _parse_zspark_file, run_spark_with_config  # pylint: disable=import-outside-toplevel
        import os  # pylint: disable=import-outside-toplevel

        zspark_config, exit_code = _parse_zspark_file(
            boot_logger, Path, spark_path, verbose
        )
        if exit_code != 0:
            return exit_code

        workspace  = spark_path.parent

        # SSOT convention: raven file name == spark middle stem.
        # e.g. zSpark.zLogin_cli.zolo → zRaven.zLogin_cli.zolo
        # Explicit zRaven: key in spark overrides; spark_stem is the default.
        spark_stem = spark_path.stem.split(".", 1)[-1]
        raven_name = zspark_config.get("zRaven") or spark_stem

        raven_file = _resolve_raven_for_run(workspace, raven_name, ui_ver, raven_ver)
        if raven_file is None:
            print(f"\n❌ No raven file found for '{raven_name}'.")
            print(f"   Run:  z raven --gen  to generate one first.\n")
            return 1

        # ── zLSP pre-flight ───────────────────────────────────────────────────
        preflight_ok = _preflight(spark_path, zspark_config, raven_file, workspace, verbose)
        if not preflight_ok:
            print("\n⚠️  Pre-flight warnings above — proceeding with tests.\n")
            # Warnings only: don't block the run, let the user decide

        active_path = workspace / "zRaven" / f"zRaven.{raven_name}.zolo"
        if raven_file != active_path:
            # Override: runner will pick up this env var instead of the active file
            os.environ["ZRAVEN_FILE"] = str(raven_file)
            print(f"\n🎯 Targeting raven: {raven_file.name}")

        # Ensure zRaven is injected (may be absent if user removed it from spark)
        zspark_config["zRaven"] = raven_name
        # Store the spark file stem so runner.py can reconstruct the exact
        # spark name to spawn ("zLogin_cli" from "zSpark.zLogin_cli.zolo").
        zspark_config["zSparkStem"] = spark_path.stem.split(".", 1)[-1]
        # Also store the actual filename — the SSOT runner.py prefers this over
        # zSparkStem when spawning the CLI subprocess. The stem-based shorthand
        # ("z add_task") only resolves for a file literally named
        # "zSpark.add_task.zolo"; a dev/flow spark ("_zSpark.add_task.zolo",
        # underscore-prefixed by convention — see zAgents zRaven dev-spark
        # docs) has no such shorthand and must boot via its full filename
        # (a form the boot loader always accepts regardless of naming).
        zspark_config["zSparkFile"] = spark_path.name

        # ── Safe port isolation ───────────────────────────────────────────────
        # zRaven runs its own server instance on dedicated ports so the test server
        # never collides with a developer's live `z zApp`. Port selection is the
        # engine's SSOT (engine._apply_raven_port_offset): live app port + offset,
        # or an explicit ZRAVEN_HTTP_PORT/ZRAVEN_WS_PORT env or zRavenPort/zRavenWsPort
        # spark override. We deliberately do NOT pre-mutate zServer/websocket ports
        # here — doing so stacked on top of the offset and desynced the runner's URL.

        # Mark the current process as the raven *runner* so _run_schema_migrations
        # auto-applies schema drift without prompting.
        # NOTE: ZRAVEN_TARGET is reserved for the test-target subprocess only —
        #       setting it here would cause config_raven.py to disable the runner.
        os.environ["ZRAVEN_RUNNER"] = "1"

        # ── Law 3: snapshot Data/ BEFORE migrations run ───────────────────────
        # run_spark_with_config triggers schema migrations (destructive ALTER TABLE)
        # before the runner thread even starts. Snapshot here so the backup is
        # the true pre-migration state, not post-migration.
        _data_isolated = False
        try:
            from zOS.L4_Orchestration.s_zRaven.zRaven_modules.utils.data_manager import (  # pylint: disable=import-outside-toplevel
                prepare_test_data, teardown_test_data,
            )
            _data_isolated = prepare_test_data(str(workspace))
            if _data_isolated:
                print(f"  → data isolated (pre-migration): {workspace}/Data/", flush=True)
        except Exception:  # pylint: disable=broad-except
            pass

        print(f"\n🚀 z raven --run → {spark_path.name}  +  {raven_file.name}\n")
        exit_code = run_spark_with_config(
            boot_logger, spark_path, zspark_config, verbose=verbose
        )

        # Auto-append hints after every run.
        # run_spark_with_config always returns 0 (the runner thread sets its own
        # exit code internally); so we read .last_raven_result to know the outcome.
        # ── Restore Data/ after run ───────────────────────────────────────────
        if _data_isolated:
            try:
                if teardown_test_data(str(workspace)):
                    print(f"  → data restored (post-run): {workspace}/Data/", flush=True)
                else:
                    print(f"  ⚠ data restore FAILED — {workspace}/Data._zraven_bak/ still "
                          f"holds the original (locked file?)", flush=True)
            except Exception:  # pylint: disable=broad-except
                pass

        # ── Hints ─────────────────────────────────────────────────────────────
        # Ensure we're writing to the real terminal (stream may have been replaced
        # by Tee objects during the run and not fully unwound yet).
        import sys as _sys  # pylint: disable=import-outside-toplevel
        _real_out = _sys.__stdout__ or _sys.stdout
        try:
            import json as _json  # pylint: disable=import-outside-toplevel
            last_result_path = workspace / "zRaven" / "output" / ".last_raven_result"
            if last_result_path.exists():
                _r = _json.loads(last_result_path.read_text(encoding="utf-8"))
                if _r.get("result") != "pass":
                    exit_code = 1
            from zOS.L4_Orchestration.s_zRaven.zRaven_modules.utils.hint_analyzer import (  # pylint: disable=import-outside-toplevel
                analyze_and_print,
            )
            _real_out.flush()
            analyze_and_print(workspace, raven_name)
            _real_out.flush()
        except Exception as _hint_exc:  # pylint: disable=broad-except
            _real_out.write(f"\n  [hint] analyzer error: {_hint_exc}\n")
            _real_out.flush()

        return exit_code

    except Exception as e:  # pylint: disable=broad-exception-caught
        boot_logger.error("[z raven --run] %s", e)
        print(f"\n❌ zRaven run failed: {e}\n")
        if verbose:
            import traceback  # pylint: disable=import-outside-toplevel
            traceback.print_exc()
        return 1


# ─────────────────────────────────────────────────────────────────────────────
# --hint
# ─────────────────────────────────────────────────────────────────────────────

def _handle_hint(boot_logger, spark_path: Path, verbose: bool) -> int:
    """Analyze past run history and surface actionable hints."""
    try:
        from zSys.cli.zspark_command import _parse_zspark_file  # pylint: disable=import-outside-toplevel
        from zOS.L4_Orchestration.s_zRaven.zRaven_modules.utils.hint_analyzer import (  # pylint: disable=import-outside-toplevel
            analyze_and_print,
        )

        zspark_config, exit_code = _parse_zspark_file(
            boot_logger, Path, spark_path, verbose
        )
        if exit_code != 0:
            return exit_code

        workspace  = spark_path.parent
        spark_stem = spark_path.stem.split(".", 1)[-1]
        raven_name = zspark_config.get("zRaven") or spark_stem

        analyze_and_print(workspace, raven_name)
        return 0

    except Exception as e:  # pylint: disable=broad-exception-caught
        boot_logger.error("[z raven --hint] %s", e)
        print(f"\n❌ zRaven hint failed: {e}\n")
        if verbose:
            import traceback  # pylint: disable=import-outside-toplevel
            traceback.print_exc()
        return 1


# ─────────────────────────────────────────────────────────────────────────────
# --commit
# ─────────────────────────────────────────────────────────────────────────────

def _handle_commit(boot_logger, spark_path: Path, label, force: bool, verbose: bool) -> int:
    """Archive a milestone snapshot of the current flow (spark + raven)."""
    try:
        from zSys.cli.zspark_command import _parse_zspark_file  # pylint: disable=import-outside-toplevel
        from zOS.L4_Orchestration.s_zRaven.zRaven_modules.utils.commit_manager import (  # pylint: disable=import-outside-toplevel
            create_commit, CommitBlockedError,
        )

        zspark_config, exit_code = _parse_zspark_file(
            boot_logger, Path, spark_path, verbose
        )
        if exit_code != 0:
            return exit_code

        workspace  = spark_path.parent
        spark_stem = spark_path.stem.split(".", 1)[-1]
        raven_name = zspark_config.get("zRaven") or spark_stem

        result = create_commit(
            workspace, spark_path, raven_name, zspark_config,
            label=label, force=force,
        )

        rel_path = result["path"].relative_to(workspace)
        print(f"\n✅ zCommit {result['flow']}/{result['commit']} → {rel_path}")
        if label:
            print(f"   label: {label}")
        print(f"   flow-owned:  {', '.join(result['flow_owned']) or '(none)'}")
        print(f"   app tree:    {len(result['shared'])} file(s) — full tree minus "
              f"Data/, logs/, zVersions/, run output (see manifest.json)")
        print(f"   diff.txt:    {'yes' if result['has_diff'] else 'no (genesis commit)'}")
        print(f"   shots:       {'yes' if result['has_shots'] else 'no'}")
        print(f"   log:         {'yes' if result['has_log'] else 'no'}\n")
        return 0

    except CommitBlockedError as e:
        print(f"\n❌ {e}\n")
        return 1
    except Exception as e:  # pylint: disable=broad-exception-caught
        boot_logger.error("[z raven --commit] %s", e)
        print(f"\n❌ zCommit failed: {e}\n")
        if verbose:
            import traceback  # pylint: disable=import-outside-toplevel
            traceback.print_exc()
        return 1


# ─────────────────────────────────────────────────────────────────────────────
# --clear
# ─────────────────────────────────────────────────────────────────────────────

def _handle_clear(workspace: Path, flow_filter, force: bool, dry_run: bool) -> int:
    """Remove committed _zSpark.<flow>.zolo dev flows + orphaned zShots/."""
    try:
        from zOS.L4_Orchestration.s_zRaven.zRaven_modules.utils.clear_manager import (  # pylint: disable=import-outside-toplevel
            clear_workspace,
        )

        result = clear_workspace(workspace, flow_filter=flow_filter, force=force, dry_run=dry_run)

        tag       = "🔎 would clear" if dry_run else "🧹 cleared"
        shots_tag = "🔎 would wipe shots" if dry_run else "📸 shots wiped"
        if result["cleared"]:
            print(f"\n{tag}:")
            for flow in result["cleared"]:
                print(f"   - {flow}")
        if result["shots_wiped"]:
            print(f"\n{shots_tag}:")
            for flow in result["shots_wiped"]:
                print(f"   - {flow}")
        if result["skipped"]:
            print("\n⚠️  skipped:")
            for flow, reason in result["skipped"]:
                print(f"   - {flow}: {reason}")
        if not result["cleared"] and not result["shots_wiped"] and not result["skipped"]:
            print("\n✅ nothing to clear — workspace already tidy\n")
        else:
            print()
        if result.get("untouched_shots"):
            print("ℹ️  other zShots/ folders untouched by this scoped --clear:")
            for name, count in result["untouched_shots"]:
                print(f"   - {name}: {count} file(s)  (z raven --clear {name}  or  z raven --clear)")
            print()
        return 0

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"\n❌ zClear failed: {e}\n")
        return 1


# ─────────────────────────────────────────────────────────────────────────────
# --revive
# ─────────────────────────────────────────────────────────────────────────────

def _handle_revive(workspace: Path, flow_name, commit_n, force: bool) -> int:
    """Restore a flow's own spark+raven files from a zCommit."""
    from zOS.L4_Orchestration.s_zRaven.zRaven_modules.utils.revive_manager import (  # pylint: disable=import-outside-toplevel
        revive_flow, list_commits, ReviveNotFoundError, ReviveConflictError,
    )

    if not flow_name:
        rows = list_commits(workspace)
        if not rows:
            print("\n❌ No commits found in this project. Nothing to revive.\n")
            return 1
        print("\nAvailable commits (z raven --revive <flow> [--r N]):")
        for r in rows:
            print(f"   {r['flow']}/{r['commit']}  \"{r['label']}\"  ({r['timestamp']})")
        print()
        return 0

    try:
        result = revive_flow(workspace, flow_name, commit_n=commit_n, force=force)
        print(f"\n✅ zRevive {result['flow']}/{result['commit']} restored:")
        for rel in result["restored"]:
            print(f"   - {rel}")
        if result["shared_drift"]:
            print("\nℹ️  shared files changed since this commit (NOT restored — historical record only):")
            for rel in result["shared_drift"]:
                print(f"   - {rel}")
        print()
        return 0

    except ReviveNotFoundError as e:
        print(f"\n❌ {e}\n")
        return 1
    except ReviveConflictError as e:
        print(f"\n❌ {e}\n")
        return 1
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"\n❌ zRevive failed: {e}\n")
        return 1


def _resolve_raven_for_run(
    workspace: Path,
    raven_name: str,
    ui_ver: Optional[str],
    raven_ver: Optional[str],
) -> Optional[Path]:
    """
    Resolve which raven file to use.

    Priority:
      --v + --r  → exact versioned archive coordinate
      --v only   → highest rN for that UI version
      --r only   → that rN for the most recent UI version
      (none)     → active file
    """
    raven_dir  = workspace / "zRaven"
    active     = raven_dir / f"zRaven.{raven_name}.zolo"
    # Archives live where the generator writes them: workspace/zVersions/tests/
    # (see raven_generator._archive_current_raven). Previously this looked in
    # zRaven/zVersions/, which never existed — so --run --r N always missed.
    ver_dir    = workspace / "zVersions" / "tests"

    if ui_ver is None and raven_ver is None:
        return active if active.exists() else None

    if not ver_dir.exists():
        return active if active.exists() else None

    # Use iterdir() + string matching — avoids glob treating [v2.0.0] as a char class.
    all_archived = list(ver_dir.iterdir()) if ver_dir.exists() else []

    if ui_ver and raven_ver:
        p = ver_dir / f"zRaven.{raven_name}[{ui_ver}]_r{raven_ver}.zolo"
        return p if p.exists() else None

    if ui_ver:
        prefix     = f"zRaven.{raven_name}[{ui_ver}]_r"
        candidates = sorted(
            p for p in all_archived
            if p.name.startswith(prefix) and p.name.endswith(".zolo")
        )
        return candidates[-1] if candidates else None

    # raven_ver only — find across all UI versions, most recently modified
    suffix     = f"_r{raven_ver}.zolo"
    prefix_any = f"zRaven.{raven_name}["
    candidates = sorted(
        (p for p in all_archived
         if p.name.startswith(prefix_any) and p.name.endswith(suffix)),
        key=lambda p: p.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _preflight(
    spark_path: Path,
    zspark_config: dict,
    raven_file: Path,
    workspace: Path,
    verbose: bool,
) -> bool:
    """
    zLSP pre-flight checks before running tests.

    Checks:
      1. Raven file parses (no syntax errors via zLSP tokenizer)
      2. UI file parses cleanly
      3. zRavenVersion in raven matches zUIVersion in UI (drift guard)

    Returns True if all clean, False if warnings were emitted.
    """
    # Use the canonical zOS parser (same as zLoader/parse_zlsp) for parse checks.
    # Do NOT use zlsp.tokenize for data validation — it's an LSP diagnostic tool
    # and returns empty for valid zRaven files (false negative).
    try:
        from zlsp import parser as _zolo  # pylint: disable=import-outside-toplevel
        _zolo_ok = True
    except ImportError:
        _zolo_ok = False

    try:
        from zlsp.parser import tokenize  # pylint: disable=import-outside-toplevel
        _tok_ok = True
    except ImportError:
        _tok_ok = False

    if not _zolo_ok and not _tok_ok:
        return True  # zLSP not available — skip silently

    issues: list = []

    # 1. Raven file syntax — use zolo.loads (canonical runtime parser)
    try:
        raven_text = raven_file.read_text(encoding="utf-8")
        if _zolo_ok:
            raven_data = _zolo.loads(raven_text, filename=raven_file.name)
            if not isinstance(raven_data, dict) or not raven_data:
                issues.append(f"  [ERROR] {raven_file.name} parsed empty — check zolo syntax")
        # Diagnostic-only: tokenize for line-level warnings (don't block on empty data)
        if _tok_ok:
            raven_result = tokenize(raven_text, raven_file.name)
            if raven_result.diagnostics:
                for d in raven_result.diagnostics:
                    sev = {1: "ERROR", 2: "WARN", 3: "INFO"}.get(d.severity, "?")
                    issues.append(f"  [{sev}] {raven_file.name} line {d.range.start.line+1}: {d.message}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        issues.append(f"  [ERROR] Failed to read {raven_file.name}: {e}")

    # 2. UI file syntax
    va_file      = zspark_config.get("zVaFile", "")
    va_folder    = workspace / "UI"  # default; zSpark resolution not needed for pre-flight
    ui_file_path = va_folder / f"{va_file}.zolo"
    ui_version: Optional[str] = None

    if ui_file_path.exists():
        try:
            ui_text   = ui_file_path.read_text(encoding="utf-8")
            ui_result = tokenize(ui_text, ui_file_path.name)
            if ui_result.diagnostics:
                for d in ui_result.diagnostics:
                    sev = {1: "ERROR", 2: "WARN", 3: "INFO"}.get(d.severity, "?")
                    issues.append(f"  [{sev}] {ui_file_path.name} line {d.range.start.line+1}: {d.message}")
            if isinstance(ui_result.data, dict):
                ui_version = str(
                    (ui_result.data.get("zMeta") or {}).get("zUIVersion", "")
                ).strip() or None
        except Exception as e:  # pylint: disable=broad-exception-caught
            issues.append(f"  [WARN] Could not parse UI file: {e}")

    # 3. Version drift check
    raven_version: Optional[str] = None
    for line in raven_text.splitlines()[:10]:
        m = re.match(r"#\s*zRavenVersion:\s*(\S+)", line)
        if m:
            raven_version = m.group(1)
            break

    if raven_version and ui_version and raven_version != ui_version:
        issues.append(
            f"  [WARN] Version drift: raven is {raven_version}, "
            f"UI is {ui_version} — run z raven --gen to resync"
        )
    elif raven_version and ui_version and raven_version == ui_version:
        if verbose:
            print(f"  ✓ zRaven version matches UI ({ui_version})")

    if issues:
        print("\n🔍 zLSP pre-flight:")
        for issue in issues:
            print(issue)
        return False

    return True


def _print_usage() -> None:
    print("\nUsage:")
    print("  z raven --gen               Generate tests from current UI")
    print("  z raven --gen --v v1.0.0    Generate from a UI backup")
    print("  z raven --run               Boot spark + run active raven")
    print("  z raven --run crm_cli       Select spark by name (zSpark.crm_cli.zolo)")
    print("  z raven --run --r 2         Run archived raven r2")
    print("  z raven --run --v 1.0.0     Run latest raven for UI v1.0.0")
    print("  z raven --hint              Analyze history + surface hints")
    print("  z raven --commit 'label'    Archive a milestone snapshot of this flow")
    print("  z raven --commit --force    Commit even if the last run failed")
    print("  z raven --clear             Remove committed dev flows + orphaned zShots/")
    print("  z raven --clear --dry-run   Preview what --clear would remove")
    print("  z raven --revive <flow>     Restore a flow's spark+raven from its latest commit")
    print("  z raven --revive <flow> --r 2  Restore a specific commit instead of the latest")
    print("  z raven --revive            List every available commit across the project")
    print()


def _find_spark(explicit: str | None) -> Path | None:
    cwd = Path.cwd()

    if explicit:
        p = Path(explicit)
        return p.resolve() if p.exists() else None

    for p in sorted(cwd.glob("zSpark.*.zolo")):
        return p.resolve()

    for sub in sorted(cwd.iterdir()):
        if sub.is_dir():
            for p in sorted(sub.glob("zSpark.*.zolo")):
                return p.resolve()

    return None
