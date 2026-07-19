# zSys/cli/patch_command.py
"""
z patch — environment self-healing command.

1. Ensures `import zguard` resolves: dev source (ZGUARD_DEV_PATH), a verified
   fetch cache, or a fresh live-fetch from the public zOS repo (see
   zguard_provision.py). Falls back to reinstalling via uv onto a Python
   version zOS ships a zguard build for, if the running one has none at all.
2. Ensures Playwright Chromium binaries are installed for zRaven browser tests.
3. Updates AI agent context (z agents).

Also called from PostInstallCommand in setup.py after pip install.
"""

import os
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path

from zSys.cli.zguard_provision import (
    current_platform_tag,
    current_py_tag,
    ensure_zguard_importable,
    is_supported,
    zguard_dev_path,
)

# Python version to reinstall onto when the running interpreter's ABI has no
# zguard build at all (see zguard_provision.SUPPORTED_PY_TAGS).
_FALLBACK_PYTHON_SPEC = "3.12"


def _dev_mode() -> bool:
    """
    True when this machine has the local zOS/zLSP source checkouts (i.e. a
    dev box, not an end-user install). zguard's dev-ness is independent —
    gated by ZGUARD_DEV_PATH — since a matching prebuilt binary usually
    exists even on a monorepo dev box; see zguard_provision.py.
    """
    return all(Path(src).exists() for pkg, src in _DEV_PACKAGES if pkg != "zguard")


def _uv_installed() -> bool:
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _install_uv():
    print("\n[z patch] Installing uv (fast Python version manager)...")
    # Per-OS official installers: the curl|sh line is POSIX-only — on Windows
    # it exploded with "'sh' is not recognized" (zOS #30). PowerShell path uses
    # astral's own irm|iex flow.
    if platform.system() == "Windows":
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "ByPass",
               "-Command", "irm https://astral.sh/uv/install.ps1 | iex"]
        result = subprocess.run(cmd)
    else:
        result = subprocess.run(
            "curl -LsSf https://astral.sh/uv/install.sh | sh",
            shell=True,
        )
    if result.returncode != 0:
        print("[z patch] ERROR: uv install failed. Install manually: https://docs.astral.sh/uv/")
        return False
    print("[z patch] uv installed.")
    return True


def _reinstall_via_uv(python_spec: str = _FALLBACK_PYTHON_SPEC):
    """Reinstall zOS via uv onto a Python version we ship a zguard build for."""
    print(f"\n[z patch] Reinstalling zOS with Python {python_spec} via uv...")
    result = subprocess.run([
        "uv", "tool", "install",
        "--python", python_spec,
        "--force",
        "zolo-os",
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
    ("zolo-lsp", str(Path(__file__).resolve().parents[3].parent / "zLSP")),
]
_zguard_dev = zguard_dev_path()
if _zguard_dev is not None:
    _DEV_PACKAGES.append(("zguard", str(_zguard_dev)))


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
    current_py = current_py_tag()
    platform_tag = current_platform_tag()

    print(f"\n[z patch] Checking environment...")
    print(f"  Running Python : {current_py}  ({sys.executable})")
    print(f"  Platform       : {platform_tag or 'unrecognized'}")

    # Always clear pyc caches, purge stale .so, and sync editable installs first
    _clear_pyc_caches()
    print("\n[z patch] Checking for stale .so files in ZGUARD_DEV_PATH...")
    _purge_stale_so_files()
    _ensure_editable_in_tools_venv()

    if _dev_mode():
        print(f"\n✓ Dev mode (local zOS/zLSP source found) — editable source is source of truth.")
        if _zguard_dev is not None:
            print(f"  zguard         : dev source ({_zguard_dev})")
        _check_and_fix_playwright()
        _run_agents()
        if live:
            _live_reload_running_servers()
        return 0

    if is_supported(platform_tag, current_py):
        print(f"\n[z patch] Ensuring zguard binaries are current for {platform_tag}/{current_py}...")
        if ensure_zguard_importable(verbose=True):
            print(f"✓ zguard ready ({platform_tag}/{current_py}).")
            _check_and_fix_playwright()
            _run_agents()
            if live:
                _live_reload_running_servers()
            return 0
        print(f"\n⚠  Could not fetch zguard binaries (network unreachable?). "
              f"Retry: z patch")
        return 1

    print(f"\n⚠  No zguard build for {platform_tag or 'this platform'}/{current_py}.")
    print(f"   z patch will reinstall zOS using uv with Python {_FALLBACK_PYTHON_SPEC}.\n")

    if not _uv_installed():
        if not _install_uv():
            return 1
        # Reload PATH so uv is found
        import os
        uv_bin = Path.home() / ".local" / "bin"
        os.environ["PATH"] = str(uv_bin) + ":" + os.environ.get("PATH", "")

    if not _reinstall_via_uv(_FALLBACK_PYTHON_SPEC):
        print("\n[z patch] ERROR: reinstall failed. Try manually:")
        print(f"  uv tool install --python {_FALLBACK_PYTHON_SPEC} zolo-os")
        return 1

    print(f"\n✓ zOS patched successfully via uv (Python {_FALLBACK_PYTHON_SPEC}).")
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
    Silently ensures zguard is importable (fetching if needed) and advises
    if a patch is needed. Does NOT auto-reinstall (user must confirm via
    z patch) when the running Python ABI has no zguard build at all.
    """
    current_py = current_py_tag()
    platform_tag = current_platform_tag()

    if is_supported(platform_tag, current_py):
        if ensure_zguard_importable():
            print(f"\n✓ zOS {current_py} runtime ready ({platform_tag}).")
            _check_and_fix_playwright()
            _run_agents()
            _show_version_banner()
        else:
            print(f"\n⚠  zguard binaries not yet fetched for {platform_tag}/{current_py} "
                  f"(will retry automatically, or run: z patch)")
    else:
        print(f"\n⚠  No zguard build for {platform_tag or 'this platform'}/{current_py}.")
        print(f"   Run:  z patch   to reinstall onto a supported Python version.\n")
