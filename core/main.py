# zOS/core/main.py
"""zOS entry point for the zOS package."""

# Stdlib imports (BEFORE any zOS imports to avoid triggering framework init)
import os
import sys
from pathlib import Path


_ZOS_SENTINEL = Path.home() / ".zos-patched"


def _auto_patch_if_needed() -> None:
    """
    On first boot after pip install: if the running Python ABI doesn't match
    the bundled zguard .so files, auto-reinstall via uv and re-exec.

    After a successful patch, writes ~/.zos-patched containing the uv binary path.
    On all subsequent runs that sentinel is checked first (fast path: one file read),
    so the full ABI scan only ever happens once per machine.
    """
    if os.environ.get("ZOS_PATCHING"):
        return

    # Fast path: already patched — just forward to the uv binary if needed
    try:
        if _ZOS_SENTINEL.exists():
            patched_bin = Path(_ZOS_SENTINEL.read_text().strip())
            current = Path(sys.executable).resolve()
            uv_python = patched_bin.parent.parent / "bin" / "python3"
            if patched_bin.exists() and current != uv_python.resolve():
                # We're not running in the patched env yet — forward immediately
                env = os.environ.copy()
                env["ZOS_PATCHING"] = "1"
                os.execve(str(patched_bin), [str(patched_bin)] + sys.argv[1:], env)
            return  # Already running in the patched env
    except Exception:  # pylint: disable=broad-except
        pass  # Sentinel unreadable — fall through to full check

    # Slow path (first run only): full ABI check
    try:
        from zSys.cli.patch_command import _abi_ok, _bundled_so_dir, _BUNDLED_PYTHON_TAG  # pylint: disable=import-outside-toplevel
        so_dir = _bundled_so_dir()
        if not so_dir.exists() or _abi_ok():
            return
        # ABI mismatch — auto-patch
        import subprocess  # pylint: disable=import-outside-toplevel
        target_py = _BUNDLED_PYTHON_TAG.replace("cp", "")
        python_spec = f"{target_py[0]}.{target_py[1:]}"
        print(f"\n[zOS] Python ABI mismatch — auto-patching to Python {python_spec} via uv...")
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            subprocess.run(
                "curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True
            )
            os.environ["PATH"] = str(Path.home() / ".local" / "bin") + ":" + os.environ.get("PATH", "")
        result = subprocess.run([
            "uv", "tool", "install",
            "--python", python_spec,
            "--force",
            "zolo-os",
        ])
        if result.returncode == 0:
            new_z = Path.home() / ".local" / "bin" / "z"
            if new_z.exists():
                # Write sentinel so every future run uses the fast path
                try:
                    _ZOS_SENTINEL.write_text(str(new_z))
                except OSError:
                    pass
                # Overwrite the current entry point with a forwarder (best-effort)
                current_bin = Path(sys.argv[0]).resolve()
                if current_bin != new_z.resolve():
                    try:
                        current_bin.write_text(f'#!/bin/sh\nexec "{new_z}" "$@"\n')
                    except OSError:
                        pass
                print(f"[zOS] Patched. Restarting command...\n")
                env = os.environ.copy()
                env["ZOS_PATCHING"] = "1"
                os.execve(str(new_z), [str(new_z)] + sys.argv[1:], env)
    except Exception:  # pylint: disable=broad-except
        pass  # Never block normal boot


_auto_patch_if_needed()


# zSys imports (system utilities, safe to import)
from zSys.logger import BootstrapLogger  # pylint: disable=import-error
from zSys.install import detect_installation_type  # pylint: disable=import-error
from zSys import cli  # pylint: disable=import-error
from zSys.cli.special_files import detect_special_files # pylint: disable=import-error
from zSys.cli.route_command import route_command # pylint: disable=import-error
from zSys.logger.execution_context import log_execution_context  # pylint: disable=import-error

# Install the SSOT emoji output gate on stdout/stderr BEFORE any logging
# StreamHandlers bind (app/framework loggers construct later in boot). Capability
# is auto-detected now and pinned by zConfig from zMachine once it resolves.
from zSys.accessibility import install_stream_gate  # pylint: disable=import-error
install_stream_gate()

# Version imports (safe to import)
from .version import get_version, get_package_info

# CLI parser factory (modular argument parsing)
from zSys.cli.args import create_parser  # pylint: disable=import-error

def _get_zos_package():
    """Lazy import zOS package to avoid triggering framework initialization at module load."""
    import zOS as zos_package  # pylint: disable=import-outside-toplevel
    return zos_package

# Bootstrap Logger Initialization
boot_logger = BootstrapLogger()

boot_logger.debug("Python: %s", sys.version.split()[0])
boot_logger.debug("Installation: %s", detect_installation_type(_get_zos_package(), detailed=True))

# Main Entry Point
def main() -> None:
    """Main entry point for the zOS command."""

    try:
        parser = create_parser(get_version())

        python_file, zspark_file, args = detect_special_files(
            parser,
            boot_logger,
            argv=sys.argv[1:],
            cwd=Path.cwd(),
        )

        verbose = getattr(args, 'verbose', False)
        dev_mode = getattr(args, 'dev', False)

        log_execution_context(boot_logger, args, python_file, zspark_file)

        return route_command(
            args,
            python_file,
            zspark_file,
            verbose,
            dev_mode,
            boot_logger,
            cli,
            sys,
            _get_zos_package,
            get_version,
            get_package_info,
            detect_installation_type,
        )

    except KeyboardInterrupt:
        boot_logger.info("Interrupted by user (Ctrl+C)")
        print("\n\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)

    except Exception as e:  # pylint: disable=broad-exception-caught
        boot_logger.critical("Unhandled exception: %s", str(e))
        boot_logger.emergency_dump(e)
        sys.exit(1)

if __name__ == "__main__":
    main()
