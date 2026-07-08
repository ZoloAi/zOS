# zSys/cli/patch_command.py
"""
z patch — environment self-healing command.

1. Detects Python ABI mismatches between the running interpreter and the
   bundled zguard .so binaries, then reinstalls via uv with the correct
   Python version automatically.
2. Ensures Playwright Chromium binaries are installed for zRaven browser tests.
3. Updates AI agent context (z agents).

Also called from PostInstallCommand in setup.py after pip install.
"""

import os
import subprocess
import sys
import sysconfig
from pathlib import Path


# Python version the bundled .so files were compiled for.
# Update this when you rebuild zguard binaries for a new Python version.
_BUNDLED_PYTHON_TAG = "cp312"


def _dev_mode() -> bool:
    """
    True when this machine has the local zOS/zGuard/zLSP source checkouts
    (i.e. a dev box, not an end-user install). In dev mode there are no
    bundled .so binaries by design — z patch must never fall back to a
    PyPI registry reinstall, only sync editable local source.
    """
    return all(Path(src).exists() for _, src in _DEV_PACKAGES)


def _current_python_tag() -> str:
    """e.g. 'cp312', 'cp314'"""
    vi = sys.version_info
    return f"cp{vi.major}{vi.minor}"


def _bundled_so_dir() -> Path:
    """
    Location of the bundled zguard .so files.

    zguard/ is always a sibling of the zOS package directory:
      installed: site-packages/zOS/  →  site-packages/zguard/
      editable:  zOS-OpenCore/core/  →  zOS-OpenCore/zguard/
    """
    try:
        import zOS  # pylint: disable=import-outside-toplevel
        # zOS.__file__ is None for editable (namespace-style) installs, so
        # resolve via __path__ which is populated in both layouts:
        #   installed: site-packages/zOS        → .parent = site-packages
        #   editable:  zOS-OpenCore/core         → .parent = zOS-OpenCore
        pkg_dir = Path(next(iter(zOS.__path__)))
        return pkg_dir.parent / "zguard"
    except (ImportError, StopIteration, TypeError):
        return Path(__file__).parent.parent.parent / "zguard"


def _abi_ok() -> bool:
    """Return True if the running Python matches the bundled .so ABI."""
    import sysconfig  # pylint: disable=import-outside-toplevel
    so_dir = _bundled_so_dir()
    if not so_dir.exists():
        return False
    # EXT_SUFFIX on macOS cp312: '.cpython-312-darwin.so'
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX") or ""
    return bool(ext_suffix) and any(so_dir.rglob(f"*{ext_suffix}"))


def _uv_installed() -> bool:
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _install_uv():
    print("\n[z patch] Installing uv (fast Python version manager)...")
    result = subprocess.run(
        "curl -LsSf https://astral.sh/uv/install.sh | sh",
        shell=True,
    )
    if result.returncode != 0:
        print("[z patch] ERROR: uv install failed. Install manually: https://docs.astral.sh/uv/")
        return False
    print("[z patch] uv installed.")
    return True


def _reinstall_via_uv():
    """Reinstall zOS via uv with the pinned Python version."""
    target_py = _BUNDLED_PYTHON_TAG.replace("cp", "")  # "312" → "3.12"
    python_spec = f"3.{target_py[1:]}" if len(target_py) == 3 else f"{target_py[0]}.{target_py[1:]}"

    repo_url = "zolo-os"
    print(f"\n[z patch] Reinstalling zOS with Python {python_spec} via uv...")
    result = subprocess.run([
        "uv", "tool", "install",
        "--python", python_spec,
        "--force",
        repo_url,
    ])
    return result.returncode == 0


def _show_version_banner():
    """Run `z` to show the installed version banner."""
    try:
        result = subprocess.run(["z"], capture_output=False)
        return result.returncode == 0
    except FileNotFoundError:
        try:
            subprocess.run(["uv", "tool", "run", "z"])
        except FileNotFoundError:
            pass
        return False


def _playwright_browsers_ok() -> bool:
    """Return True if Playwright is installed and Chromium binary is available."""
    try:
        from playwright.sync_api import sync_playwright  # pylint: disable=import-outside-toplevel
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except ImportError:
        return False  # playwright package not installed — optional dep, skip silently
    except Exception:
        return False  # package present but binaries missing


def _install_playwright_browsers():
    """Run `playwright install chromium` to download browser binaries."""
    print("\n[z patch] Installing Playwright browser binaries (Chromium ~130MB)...")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=False,
    )
    if result.returncode == 0:
        print("[z patch] ✓ Playwright Chromium installed.")
        return True
    print("[z patch] ERROR: playwright install failed. Run manually: playwright install chromium")
    return False


def _check_and_fix_playwright():
    """Check Playwright browser binaries and install if missing."""
    try:
        import playwright  # pylint: disable=import-outside-toplevel, unused-import
    except ImportError:
        return  # playwright optional dep not installed — skip silently
    if _playwright_browsers_ok():
        print("  Playwright     : ✓ Chromium ready")
    else:
        _install_playwright_browsers()


def _purge_stale_so_files() -> None:
    """
    In dev mode (ZGUARD_DEV_PATH set), delete any compiled .so that is OLDER
    than its corresponding .py source. This prevents stale Cython binaries from
    shadowing updated Python sources (e.g. bridge_connection.so vs bridge_connection.py).
    """
    zguard_dev = os.environ.get("ZGUARD_DEV_PATH")
    if not zguard_dev:
        return
    root = Path(zguard_dev)
    if not root.exists():
        return

    removed = []
    ext = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
    for so_file in root.rglob(f"*{ext}"):
        stem = so_file.name.split(".")[0]
        py_file = so_file.parent / f"{stem}.py"
        if py_file.exists() and py_file.stat().st_mtime > so_file.stat().st_mtime:
            try:
                so_file.unlink()
                removed.append(so_file.name)
            except OSError:
                pass

    if removed:
        print(f"  ✓ Purged {len(removed)} stale .so file(s): {', '.join(removed)}")
    else:
        print("  ✓ No stale .so files found.")


def _run_agents():
    """Run `z agents` to inject/update AI workspace rules (e.g. Cursor/Claude context)."""
    print("\n[z patch] Updating AI agent context (z agents)...")
    try:
        result = subprocess.run(["z", "agents"], capture_output=False)
        if result.returncode != 0:
            print("[z patch] z agents skipped (non-zero exit). Run manually: z agents")
    except FileNotFoundError:
        try:
            subprocess.run(["uv", "tool", "run", "z", "agents"], capture_output=False)
        except FileNotFoundError:
            print("[z patch] z agents skipped (z not in PATH). Run manually: z agents")


# ── Dev-source roots that must always be editable in the tools venv ──────────
_DEV_PACKAGES: list[tuple[str, str]] = [
    # (pip package name, source path relative to this file's repo root)
    ("zolo-os",  str(Path(__file__).resolve().parents[3])),           # zOS-OpenCore/
    ("zguard",   str(Path(__file__).resolve().parents[3].parent / "zGuard")),
    ("zolo-lsp", str(Path(__file__).resolve().parents[3].parent / "zLSP")),
]


def _clear_pyc_caches() -> None:
    """Delete all __pycache__ .pyc files under every dev-source root."""
    print("\n[z patch] Clearing stale .pyc caches...")
    removed = 0
    for _, src in _DEV_PACKAGES:
        root = Path(src)
        if not root.exists():
            continue
        for pyc in root.rglob("*.pyc"):
            try:
                pyc.unlink()
                removed += 1
            except OSError:
                pass
    print(f"  ✓ Removed {removed} .pyc files.")


def _tools_python() -> Path | None:
    """Return path to the uv tools-venv Python that runs `z`, or None."""
    candidate = Path.home() / ".local" / "share" / "uv" / "tools" / "zolo-os" / "bin" / "python3"
    return candidate if candidate.exists() else None


def _ensure_editable_in_tools_venv() -> None:
    """
    Re-install every dev package as editable (-e) inside the tools venv.
    Skips packages whose source directory doesn't exist on this machine.
    """
    py = _tools_python()
    if py is None:
        print("\n[z patch] tools-venv Python not found — skipping editable sync.")
        return

    print(f"\n[z patch] Syncing editable installs in tools venv ({py})...")
    for pkg, src in _DEV_PACKAGES:
        src_path = Path(src)
        if not src_path.exists():
            print(f"  skip  {pkg}  (source not found: {src_path})")
            continue
        result = subprocess.run(
            ["uv", "pip", "install", "--python", str(py), "--quiet", "-e", str(src_path)],
            capture_output=True, text=True
        )
        status = "✓" if result.returncode == 0 else "✗"
        print(f"  {status}  {pkg}  ({src_path.name})")
        if result.returncode != 0 and result.stderr:
            print(f"      {result.stderr.strip()[:200]}")


def _live_reload_running_servers() -> None:
    """
    After a successful patch, self-replace every running zServer so each one
    adopts the patched code with zero downtime (SIGUSR2 → blue-green swap).

    Patch is machine-wide, so we refresh ALL running instances (no prompt).
    A server that predates the SIGUSR2 handler will not be signalled safely,
    so this only targets instances found in the registry — which are only
    written by builds that already support the self-replace handshake.
    """
    import signal  # pylint: disable=import-outside-toplevel

    if not hasattr(signal, "SIGUSR2"):
        print("\n[z patch --live] SIGUSR2 is unavailable on this platform "
              "(Windows) — restart servers manually to pick up the patch.")
        return

    try:
        from zOS.L4_Orchestration.r_zServer.zServer_modules.lifecycle.pidfile import (  # pylint: disable=import-outside-toplevel
            list_instances,
        )
    except ImportError:
        try:
            from L4_Orchestration.r_zServer.zServer_modules.lifecycle.pidfile import (  # pylint: disable=import-outside-toplevel
                list_instances,
            )
        except ImportError:
            print("\n[z patch --live] Instance registry unavailable — "
                  "skipping live reload.")
            return

    instances = list_instances()
    if not instances:
        print("\n[z patch --live] No running zServers to refresh.")
        return

    print(f"\n[z patch --live] Self-replacing {len(instances)} running "
          f"zServer(s) with the patched code (zero downtime)...")
    for rec in instances:
        pid = rec.get("pid")
        title = rec.get("title", "zServer")
        port = rec.get("port")
        where = f":{port}" if port else ""
        if not pid:
            continue
        try:
            os.kill(pid, signal.SIGUSR2)
            print(f"  ✓ {title}{where} (pid {pid}) — swap signal sent")
        except ProcessLookupError:
            print(f"  ✗ {title}{where} (pid {pid}) — process gone (stale record)")
        except PermissionError:
            print(f"  ✗ {title}{where} (pid {pid}) — not permitted to signal")
    print("  Watch each server's console for the green→blue handoff receipt.\n")


def handle_patch_command(verbose: bool = False, live: bool = False) -> int:
    """
    Main handler for `z patch`.

    When ``live`` is True, every running zServer is self-replaced with the
    patched code after a successful patch (zero-downtime swap, no restart).

    Returns 0 on success, 1 on failure.
    """
    current = _current_python_tag()
    bundled = _BUNDLED_PYTHON_TAG

    print(f"\n[z patch] Checking environment...")
    print(f"  Running Python : {current}  ({sys.executable})")
    print(f"  Bundled runtime: {bundled}")

    # Always clear pyc caches, purge stale .so, and sync editable installs first
    _clear_pyc_caches()
    print("\n[z patch] Checking for stale .so files in ZGUARD_DEV_PATH...")
    _purge_stale_so_files()
    _ensure_editable_in_tools_venv()

    if _dev_mode():
        print(f"\n✓ Dev mode (local zOS/zGuard/zLSP source found) — skipping "
              f"registry ABI check, editable source is source of truth.")
        _check_and_fix_playwright()
        _run_agents()
        if live:
            _live_reload_running_servers()
        return 0

    if _abi_ok():
        print(f"\n✓ zOS runtime OK ({current} matches bundled {bundled}).")
        _check_and_fix_playwright()
        _run_agents()
        if live:
            _live_reload_running_servers()
        return 0

    print(f"\n⚠  ABI mismatch: running {current}, bundled .so requires {bundled}.")
    print(f"   z patch will reinstall zOS using uv with Python {bundled}.\n")

    if not _uv_installed():
        if not _install_uv():
            return 1
        # Reload PATH so uv is found
        import os
        uv_bin = Path.home() / ".local" / "bin"
        os.environ["PATH"] = str(uv_bin) + ":" + os.environ.get("PATH", "")

    if not _reinstall_via_uv():
        print("\n[z patch] ERROR: reinstall failed. Try manually:")
        print(f"  uv tool install --python {bundled.replace('cp', '3.')} zolo-os")
        return 1

    print(f"\n✓ zOS patched successfully via uv (Python {bundled}).")
    _check_and_fix_playwright()
    _run_agents()
    if live:
        _live_reload_running_servers()

    # Re-exec with the uv-installed z so this same terminal session works immediately
    import os as _os  # pylint: disable=import-outside-toplevel
    new_z = Path.home() / ".local" / "bin" / "z"
    if new_z.exists():
        env = _os.environ.copy()
        env["ZOS_PATCHING"] = "1"
        print(f"\n[z patch] Relaunching via patched binary...\n")
        _os.execve(str(new_z), [str(new_z)], env)
    else:
        print("  Open a new terminal window to use the patched 'z' command.\n")
        _show_version_banner()
    return 0


def run_post_install_check():
    """
    Called from setup.py PostInstallCommand after pip install.
    Silently checks ABI and advises if patch is needed.
    Does NOT auto-reinstall (user must confirm via z patch).
    """
    current = _current_python_tag()
    bundled = _BUNDLED_PYTHON_TAG

    if _abi_ok():
        print(f"\n✓ zOS {current} runtime ready.")
        _check_and_fix_playwright()
        _run_agents()
        _show_version_banner()
    else:
        print(f"\n⚠  Python version mismatch: running {current}, bundled runtime requires {bundled}.")
        print(f"   Run:  z patch   to automatically fix this.\n")
