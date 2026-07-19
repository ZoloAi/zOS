#!/usr/bin/env python3
"""
z agents — inject zolo agent instructions into the current workspace.

Detects which IDE/tool is present and copies the right generated files.
Idempotent: safe to re-run, skips files already up to date.

Claude Code rules install to the machine/user level (~/.claude/) via
Path.home() — cross-platform for macOS/Linux/Windows; one install covers
every workspace. Cursor rules are cloned into the PROJECT root where
`z agents` is fired (<workspace>/.cursor/rules/) — user-level ~/.cursor/rules/
proved unreliable in Cursor and is cleaned up on every run.

Usage:
    z agents          # install to user-level dirs + inject repo-scoped files (Copilot/AGENTS.md)
    z agents --force  # overwrite even if files already exist
    z agents --assoc  # (macOS) install .zolo file association
"""

import platform
import shutil
import sys
from pathlib import Path


GEN_DIR = Path(__file__).parent / "generated"


def _is_up_to_date(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return False
    return dst.read_bytes() == src.read_bytes()


def _copy(src: Path, dst: Path, force: bool, label: str):
    if not force and _is_up_to_date(src, dst):
        print(f"  [zAgents] {label} already up to date — skipped")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  [zAgents] {label} → {dst}")


def _inject_cursor(workspace: Path, force: bool):
    """Install Cursor rules into the project where `z agents` is fired:
      <workspace>/.cursor/rules/zolo-<NN>-<topic>.mdc   — one file per src topic

    Project-level by design: Cursor user-level rules (~/.cursor/rules/) proved
    unreliable, so rules are cloned into each project root instead. Re-running
    `z agents` in a project refreshes them; the zolo- namespace is owned by
    this generator, so renamed/removed topics are pruned on every run.
    """
    cursor_gen = GEN_DIR / "cursor"
    if not cursor_gen.exists():
        print("  [zAgents] WARNING: generated/cursor/ not found — run builder first")
        return None

    rules_dir = workspace / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    generated_names = {mdc.name for mdc in cursor_gen.glob("*.mdc")}
    for mdc in sorted(cursor_gen.glob("*.mdc")):
        _copy(mdc, rules_dir / mdc.name, force, f"Cursor rule {mdc.name}")
    # <workspace>/.cursor/rules/ zolo- namespace is owned entirely by this
    # generator — prune any topic the builder no longer produces (renamed/
    # removed src topics). Scoped to zolo- so user-authored rules are untouched.
    for stale in sorted(rules_dir.glob("zolo-*.mdc")):
        if stale.name not in generated_names:
            stale.unlink()
            print(f"  [zAgents] Cursor rule {stale.name} — stale, removed")

    # Legacy cleanup: earlier builds installed to user-level ~/.cursor/rules/,
    # which Cursor does not reliably load — remove any zolo- rules left there.
    legacy_dir = Path.home() / ".cursor" / "rules"
    if legacy_dir.exists():
        for legacy in sorted(legacy_dir.glob("zolo-*.mdc")):
            legacy.unlink()
            print(f"  [zAgents] Legacy user-level rule {legacy.name} — removed")

    return "Cursor (project)"


def _inject_copilot(workspace: Path, force: bool):
    src = GEN_DIR / "AGENTS.md"
    dst = workspace / ".github" / "copilot-instructions.md"
    (workspace / ".github").mkdir(parents=True, exist_ok=True)
    _copy(src, dst, force, "Copilot instructions")


def _inject_agents_md(workspace: Path, force: bool):
    src = GEN_DIR / "AGENTS.md"
    dst = workspace / "AGENTS.md"
    # If existing AGENTS.md is a slim Cursor-optimised phases file (< 200 lines),
    # preserve it — the full content goes to ~/.claude/CLAUDE.md instead.
    if not force and dst.exists() and sum(1 for _ in dst.open()) < 200:
        print(f"  [zAgents] AGENTS.md (slim phases file) — preserved, not overwritten")
        return
    _copy(src, dst, force, "AGENTS.md")


def _inject_windsurf(workspace: Path, force: bool):
    src = GEN_DIR / "AGENTS.md"
    dst = workspace / ".windsurfrules"
    _copy(src, dst, force, ".windsurfrules")


def _inject_claude_global(force: bool):
    """Install Claude Code global context:
      ~/.claude/CLAUDE.md          — lean index (workflow + topic_refs)
      ~/.claude/zolo/<topic>.md    — topic files read on demand by Claude
    """
    claude_src_dir = GEN_DIR / "claude"
    if not claude_src_dir.exists():
        print("  [zAgents] WARNING: generated/claude/ not found — run builder first")
        return None

    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    # --- index file ---
    src_index = claude_src_dir / "CLAUDE.md"
    if not src_index.exists():
        print("  [zAgents] WARNING: generated/claude/CLAUDE.md not found — skipping")
        return None
    _copy(src_index, claude_dir / "CLAUDE.md", force, "Claude Code index")

    # --- topic files → ~/.claude/zolo/ ---
    topics_src = claude_src_dir / "zolo"
    if topics_src.exists():
        topics_dst = claude_dir / "zolo"
        topics_dst.mkdir(parents=True, exist_ok=True)
        generated_names = {t.name for t in topics_src.glob("*.md")}
        for topic_file in sorted(topics_src.glob("*.md")):
            _copy(topic_file, topics_dst / topic_file.name, force,
                  f"Claude topic {topic_file.name}")
        # ~/.claude/zolo/ is owned entirely by this generator — prune any topic
        # file the builder no longer produces (renamed/removed src topics).
        for stale in sorted(topics_dst.glob("*.md")):
            if stale.name not in generated_names:
                stale.unlink()
                print(f"  [zAgents] Claude topic {stale.name} — stale, removed")

    return "Claude Code (global)"


def _workspace_writable(workspace: Path) -> bool:
    """True when we can actually create files in the workspace.

    A real write probe, not os.access(): Windows ACLs make access() lie, and
    the canonical failure is PowerShell-as-admin defaulting cwd to
    C:\\WINDOWS\\System32 — golden users land there constantly (zOS #31).
    Project injections must SKIP politely in that case, never traceback.
    """
    probe = workspace / ".zagents-write-probe.tmp"
    try:
        probe.touch()
        probe.unlink()
        return True
    except OSError:
        return False


def _has_cursor_ancestor(workspace: Path, max_levels: int = 4) -> bool:
    """Return True if this workspace or any ancestor (up to max_levels) contains a .cursor/ folder.

    Used only to decide whether to skip writing AGENTS.md (Cursor users get rules from
    the global ~/.cursor/rules/ install instead — AGENTS.md there is redundant tokens).
    """
    current = workspace
    for _ in range(max_levels):
        if (current / ".cursor").exists():
            return True
        if current == current.parent:   # filesystem root
            break
        current = current.parent
    return False


def _detect_and_inject(workspace: Path, force: bool):
    injected = []

    # Claude is global (machine/user-level); Cursor rules are cloned into the
    # project root where `z agents` is fired (user-level rules don't load).
    result = _inject_claude_global(force)
    if result:
        injected.append(result)

    # Everything below writes into the WORKSPACE — guard it once, here.
    if not _workspace_writable(workspace):
        print(f"  [zAgents] {workspace} is not writable (system folder?) — "
              "project files skipped.")
        print("  [zAgents] cd into your project folder and re-run: z agents")
        return injected

    result = _inject_cursor(workspace, force)
    if result:
        injected.append(result)

    under_cursor = _has_cursor_ancestor(workspace)

    if (workspace / ".github").exists():
        _inject_copilot(workspace, force)
        injected.append("Copilot")

    if (workspace / ".windsurfrules").exists():
        _inject_windsurf(workspace, force)
        injected.append("Windsurf")

    # Write workspace AGENTS.md only for workspaces with NO Cursor context at all
    # (Cursor users get the global rules install instead — AGENTS.md there is noise).
    if not under_cursor:
        _inject_agents_md(workspace, force)
        injected.append("Codex/Aider (AGENTS.md)")

    return injected


def _install_macos_file_assoc() -> None:
    """
    macOS: compile an AppleScript droplet (.app) that receives .zolo files
    via Apple Events (on open fileList) and launches them with `z` in Terminal.

    Only reacts to files whose name starts with "zSpark." — all other .zolo
    files are ignored (the association is extension-only at the OS level).

    Places the app at ~/Applications/zOS Launcher.app and calls
    lsregister to activate the association immediately.
    """
    if platform.system() != "Darwin":
        print("  [zAgents] File association is macOS-only for now — skipped")
        return

    import subprocess  # pylint: disable=import-outside-toplevel
    import tempfile    # pylint: disable=import-outside-toplevel
    import textwrap    # pylint: disable=import-outside-toplevel

    app_path = Path.home() / "Applications" / "zOS Launcher.app"

    # ── AppleScript droplet source ─────────────────────────────────────────
    # "on open" receives Apple Events when a file is double-clicked in Finder.
    # We filter to zSpark.*.zolo filenames inside the script — OS can only
    # match by extension, not by filename pattern.
    # Use a .command file + `open` instead of Apple Events to Terminal.
    # This avoids the TCC "Not authorized to send Apple events" prompt entirely:
    # macOS opens .command files directly in Terminal without requiring entitlements.
    applescript = textwrap.dedent("""\
    on open fileList
        repeat with aFile in fileList
            set filePath to POSIX path of aFile
            set fileName to do shell script "basename " & quoted form of filePath
            if fileName starts with "zSpark." then
                set ts to do shell script "date +%s%N"
                set cmdFile to "/tmp/zos_launch_" & ts & ".command"
                do shell script "printf '#!/bin/bash\\ncd " & quoted form of (do shell script "dirname " & quoted form of filePath) & "\\nz " & quoted form of filePath & "\\nexec $SHELL\\n' > " & quoted form of cmdFile
                do shell script "chmod +x " & quoted form of cmdFile
                do shell script "open " & quoted form of cmdFile
            end if
        end repeat
    end open

    on run
        -- launched without a file (e.g. clicked in Applications) — do nothing
    end run
    """)

    # ── compile via osacompile ─────────────────────────────────────────────
    with tempfile.NamedTemporaryFile(suffix=".applescript", mode="w",
                                     delete=False, encoding="utf-8") as tmp:
        tmp.write(applescript)
        tmp_path = tmp.name

    # Remove existing bundle first so osacompile writes cleanly
    if app_path.exists():
        import shutil as _shutil  # pylint: disable=import-outside-toplevel
        _shutil.rmtree(app_path)

    try:
        subprocess.run(
            ["osacompile", "-o", str(app_path), tmp_path],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"  [zAgents] ERROR: osacompile failed: {exc}")
        return
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # ── patch osacompile-generated Info.plist to add UTI + document type ──
    plist_path = app_path / "Contents" / "Info.plist"

    # Add CFBundleDocumentTypes so macOS knows this app handles .zolo files
    doc_type_xml = textwrap.dedent("""\
        <array>
            <dict>
                <key>CFBundleTypeExtensions</key>
                <array><string>zolo</string></array>
                <key>CFBundleTypeName</key>
                <string>zolo File</string>
                <key>CFBundleTypeRole</key>
                <string>Editor</string>
                <key>LSHandlerRank</key>
                <string>Owner</string>
            </dict>
        </array>
    """).strip()

    subprocess.run(
        ["plutil", "-replace", "CFBundleDocumentTypes",
         "-xml", doc_type_xml, str(plist_path)],
        check=True,
    )
    subprocess.run(
        ["plutil", "-replace", "CFBundleIdentifier",
         "-string", "media.zolo.zos-launcher", str(plist_path)],
        check=True,
    )

    # ── register with LaunchServices ───────────────────────────────────────
    lsregister = (
        "/System/Library/Frameworks/CoreServices.framework"
        "/Versions/A/Frameworks/LaunchServices.framework"
        "/Versions/A/Support/lsregister"
    )
    try:
        subprocess.run([lsregister, "-f", str(app_path)], check=True)
        print(f"  [zAgents] .zolo file association installed → {app_path}")
        print("  [zAgents] Double-click a zSpark.*.zolo file to launch it in Terminal.")
    except subprocess.CalledProcessError as exc:
        print(f"  [zAgents] WARNING: lsregister failed: {exc}")
        print(f"  [zAgents] App bundle created at {app_path} — may need re-login to take effect.")


def run(force: bool = False, assoc: bool = False):
    """Programmatic entry point (used by z agents router)."""
    workspace = Path.cwd()

    if assoc:
        print("\n[zAgents] Installing .zolo file association...\n")
        _install_macos_file_assoc()
        print()
        return

    if not GEN_DIR.exists():
        print("\n[zAgents] ERROR: generated/ folder not found.")
        print("  Run first: python -m zOS.zAgents.builder\n")
        return

    print(f"\n[zAgents] Injecting zolo agent instructions into: {workspace}\n")
    injected = _detect_and_inject(workspace, force)

    # Always offer to install file association on macOS
    if platform.system() == "Darwin":
        _install_macos_file_assoc()

    print(f"\n[zAgents] Done. Injected for: {', '.join(injected)}\n")


def main():
    """Console script entry point (zagents command)."""
    force = "--force" in sys.argv
    assoc = "--assoc" in sys.argv
    run(force=force, assoc=assoc)


if __name__ == "__main__":
    main()
