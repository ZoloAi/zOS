# zSys/cli/script_command.py
"""
Python script execution command.
"""

import os
import subprocess


def handle_script_command(boot_logger, sys, Path, script_path: str, verbose: bool = False):
    """
    Execute Python script using zolo's interpreter (solves python/python3 ambiguity).

    Args:
        boot_logger: BootstrapLogger instance
        sys: sys module (for sys.executable)
        Path: pathlib.Path class
        script_path: Path to Python script
        verbose: Show bootstrap logs on stdout

    Returns:
        int: Exit code (0 = success, non-zero = error)

    Examples:
        zolo zTest.py
        zolo zTest.py --verbose
    """
    script = Path(script_path).resolve()
    if not script.exists():
        boot_logger.error("Script not found: %s", script_path)
        if verbose:
            boot_logger.print_buffered_logs()
        print(f"\n❌ Error: Script not found: {script_path}\n")
        return 1

    if script.suffix != ".py":
        boot_logger.error("Not a Python file: %s (suffix: %s)", script_path, script.suffix)
        if verbose:
            boot_logger.print_buffered_logs()
        print(f"\n❌ Error: File must be a .py file: {script_path}\n")
        return 1

    if verbose:
        boot_logger.print_buffered_logs()

    try:
        result = subprocess.run(
            [sys.executable, str(script.absolute())],
            cwd=str(script.parent),
            env=os.environ.copy(),
            check=False,
        )
        return result.returncode
    except Exception as e:  # pylint: disable=broad-exception-caught
        boot_logger.error("Failed to execute script: %s", str(e))
        print(f"\n❌ Error executing script: {e}\n")
        return 1
