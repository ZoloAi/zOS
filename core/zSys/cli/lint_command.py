# zSys/cli/lint_command.py
"""
`z lint` — run the strict-gate static checks standalone (zOS#84).

Thin CLI wrapper over lint_core.lint_app: resolve the app dir from whatever
the user pointed at (zSpark file, app dir, or any file inside it), run the
walk, print the report, exit 1 on faults.
"""

from __future__ import annotations

from pathlib import Path


def handle_lint_command(app_file: str, verbose: bool = False) -> int:
    """Run static lint over the app containing ``app_file``. Returns exit code."""
    from .lint_core import lint_app  # pylint: disable=import-outside-toplevel

    target = Path(app_file).resolve()
    if not target.exists():
        print(f"\n❌ Error: path not found: {app_file}\n")
        return 1
    app_dir = target if target.is_dir() else target.parent

    faults = lint_app(app_dir)

    if verbose:
        print(f"\nz lint — {app_dir}")

    if not faults:
        print(f"\n✅ z lint: no static faults found in {app_dir.name}/\n")
        return 0

    print(f"\n⛔ z lint: {len(faults)} static fault(s) in {app_dir.name}/\n")
    for fault in faults:
        print(f"   • {fault.render()}")
    print(
        "\n   Strict boot (the default) refuses to launch on these. Fix them,"
        "\n   or declare `strict: false` in the zSpark to boot anyway.\n"
    )
    return 1
