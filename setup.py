#!/usr/bin/env python3
"""
setup.py for zOS - Enables smart monorepo dependency resolution

This setup.py works alongside pyproject.toml to provide industry-standard
monorepo dependency management:

- Local development (-e): Automatically installs zlsp in editable mode
- PyPI install: Uses zlsp from PyPI  
- Standard install: Uses zlsp from PyPI

This is the industry-standard approach used by large Python monorepos.
"""

import os
import subprocess
import sys
from pathlib import Path
from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install
from setuptools.command.egg_info import egg_info


def _discover_packages():
    """
    Walk core/ and build the full packages + package_dir mappings.

    Mapping rules:
      core/                      → zOS
      core/zSys/**               → zSys.**  (kept as zSys.*)
      core/zos_plugin/           → zos_plugin
      core/<anything else>/**    → zOS.<anything else>.**
    """
    root = Path(__file__).parent
    core = root / "core"
    packages = []
    package_dir = {}

    for init in sorted(core.rglob("__init__.py")):
        pkg_path = init.parent
        rel = pkg_path.relative_to(core)
        parts = rel.parts

        if not parts:  # core itself → zOS
            pkg_name = "zOS"
        elif parts[0] == "zSys":
            pkg_name = ".".join(parts)
        elif parts[0] == "zos_plugin":
            pkg_name = "zos_plugin"
        else:
            pkg_name = "zOS." + ".".join(parts)

        packages.append(pkg_name)
        package_dir[pkg_name] = str(pkg_path.relative_to(root))

    # zRaven entry point lives in core/L4_Orchestration/s_zRaven/entry.py — no separate zRaven/ package

    # zAgents/ — AI instruction build + install system
    agents = root / "zAgents"
    if (agents / "__init__.py").exists():
        packages.append("zOS.zAgents")
        package_dir["zOS.zAgents"] = str(agents.relative_to(root))

    # NOTE: zguard is never bundled here. zguard_bin/<platform-tag>/<py-tag>/*.so
    # is a flat, git-tracked (not a Python package) binary store that `z patch`
    # live-fetches the one matching file from at install/patch time — see
    # core/zSys/cli/patch_command.py. It must never be discovered as a package
    # or added to package_data, or every platform's binaries would ship in
    # every wheel.

    return packages, package_dir


def _install_playwright_browsers():
    """Install Playwright browser binaries (one-time, ~130MB for Chromium)."""
    print("\n" + "="*70)
    print("Setting up zRaven browser engine (one-time download, ~130MB)...")
    print("="*70)
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("zRaven browser engine ready.")
    except subprocess.CalledProcessError as e:
        print(f"Warning: browser engine install failed: {e}")
        print("Run manually: playwright install chromium")
    except FileNotFoundError:
        print("Warning: playwright not found — run: pip install playwright && playwright install chromium")


def _install_zlsp(monorepo=False):
    """Install zlsp (editable from monorepo or from PyPI), then wire all IDEs."""
    zlsp_path = Path(__file__).parent.parent / "zlsp"

    if monorepo and zlsp_path.exists() and (zlsp_path / "pyproject.toml").exists():
        print("\n" + "="*70)
        print("Monorepo detected — installing zlsp in editable mode...")
        print("="*70)
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", str(zlsp_path)])
            print("zlsp installed in editable mode from monorepo.")
        except subprocess.CalledProcessError as e:
            print(f"Warning: editable zlsp install failed: {e} — falling back to PyPI...")
            subprocess.call([sys.executable, "-m", "pip", "install", "zlsp>=1.0.0"])
    else:
        print("\nInstalling zlsp from PyPI...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "zlsp>=1.0.0"])
            print("zlsp installed.")
        except subprocess.CalledProcessError as e:
            print(f"Warning: could not install zlsp: {e}")
            return  # no point running IDE install if zlsp isn't available

    # Wire zLSP into every IDE found on this machine (silently skips missing ones)
    print("\nRegistering zLSP with available editors...")
    try:
        subprocess.call(["zlsp-install-all"])
    except FileNotFoundError:
        print("Warning: zlsp-install-all not found — run it manually after install.")


class PostDevelopCommand(develop):
    """Post-installation for editable/development mode."""

    def run(self):
        develop.run(self)
        _install_zlsp(monorepo=True)
        _install_playwright_browsers()


def _run_post_install_check():
    """Check ABI compatibility and show z version banner after install."""
    try:
        from zSys.cli.patch_command import run_post_install_check  # pylint: disable=import-outside-toplevel
        run_post_install_check()
    except Exception as e:  # pylint: disable=broad-except
        print(f"\n[zOS] Post-install check skipped: {e}")
        print("  Run: z patch   if you experience issues.\n")


def _run_agents_inject():
    """Inject zOS AI agent rules into the current workspace (updates Cursor/Claude context)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "zOS.main", "agents"],
            capture_output=False,
        )
        if result.returncode != 0:
            print("[zOS] z agents: skipped (run manually: z agents)")
    except Exception as e:  # pylint: disable=broad-except
        print(f"[zOS] z agents skipped: {e}")


class PostInstallCommand(install):
    """Post-installation for standard install mode."""

    def run(self):
        install.run(self)
        _run_post_install_check()
        _run_agents_inject()
        _install_zlsp(monorepo=False)


_packages, _package_dir = _discover_packages()

setup(
    # name/version are NOT passed here — pyproject.toml's [project] table is the
    # SSOT for both (static, non-dynamic fields there always win over setup.py's
    # setup() kwargs; duplicating them here was dead code that risked drifting
    # out of sync, e.g. a version bump in one file but not the other).
    packages=_packages,
    package_dir=_package_dir,
    package_data={
        # Accessibility ships its built-in JSON data (emoji descriptions + icon codepoints)
        "zSys.accessibility": ["data/*.json"],
    },
    cmdclass={
        "develop": PostDevelopCommand,
        "install": PostInstallCommand,
    },
)
