# zSys/cli/scaffold_command.py
"""
zolo scaffold <appname>

Clones confirmed template files from zOS/zDemos/zScaffold/ into a new app
directory. Only the appname is substituted in FILENAMES — all content __hints__
are left intact for the agent to reason about and fill in.

NOTE: zScaffold lives under zDemos/ and is slated for removal down the line.
"""

import shutil
from pathlib import Path


# repo_root/zDemos/zScaffold  (was repo_root/zScaffold)
_SCAFFOLD_SRC = Path(__file__).parent.parent.parent.parent / "zDemos" / "zScaffold"


def handle_scaffold_command(appname: str, title: str | None, dest: str | None) -> int:
    appname = appname.strip().lower().replace(" ", "_")

    # Resolve destination
    if dest:
        app_dir = Path(dest).resolve()
    else:
        demos = Path.cwd() / "AGENT_GEN_DEMOS"
        app_dir = (demos / appname) if demos.is_dir() else (Path.cwd() / appname)

    if app_dir.exists():
        print(f"\n[zScaffold] ✗  '{app_dir}' already exists — aborting.\n")
        return 1

    if not _SCAFFOLD_SRC.is_dir():
        print(f"\n[zScaffold] ✗  Template source not found: {_SCAFFOLD_SRC}\n")
        return 1

    # Walk scaffold source — substitute __appname__ in filenames only, copy content as-is
    for src_path in sorted(_SCAFFOLD_SRC.rglob("*")):
        rel = src_path.relative_to(_SCAFFOLD_SRC)

        new_parts = [part.replace("__appname__", appname) for part in rel.parts]
        dst_path = app_dir / Path(*new_parts)

        if src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
            continue

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)

    # Confirm
    rel_display = app_dir.relative_to(Path.cwd()) if app_dir.is_relative_to(Path.cwd()) else app_dir
    print(f"\n[zScaffold] ✓  {title} scaffolded → {rel_display}/")
    print(f"            Edit  zSpark.{appname}.zolo  to begin.\n")
    _print_tree(app_dir)
    return 0


def _print_tree(root: Path, prefix: str = "  ") -> None:
    entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name))
    for i, entry in enumerate(entries):
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if i == len(entries) - 1 else "│   "
            _print_tree(entry, prefix + extension)
