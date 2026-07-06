# zSys/cli/demos_command.py
"""
z demos — list and inspect zOS reference demo apps.

z demos                  List all available demos
z demos <name>           Show detail for a specific demo
z demos <name> --clone   Clone demo into cwd as a new app (requires --name)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional


# ── Locate zDemos/ ────────────────────────────────────────────────────────────

def _find_demos_dir() -> Optional[Path]:
    """
    Resolve zDemos/ directory.

    Priority:
      1. Editable install — zDemos/ sits next to the zOS-OpenCore source root.
         Detected by walking up from the zOS package until we find zDemos/.
      2. Regular install — zDemos/ not on disk; remote manifest would be used.
         (stub: prints a message and returns None)
    """
    try:
        import zOS as _zos  # pylint: disable=import-outside-toplevel
        zos_file = Path(_zos.__file__).resolve()
        # Walk up up to 4 levels looking for zDemos/
        candidate = zos_file.parent
        for _ in range(4):
            demos = candidate / "zDemos"
            if demos.is_dir():
                return demos
            candidate = candidate.parent
    except ImportError:
        pass
    return None


# ── zSpark / zInfo reader ─────────────────────────────────────────────────────

def _read_spark_info(demo_dir: Path) -> dict:
    """Parse the first zSpark.*.zolo found and extract zInfo + title."""
    sparks = list(demo_dir.glob("zSpark.*.zolo"))
    if not sparks:
        return {}
    spark_file = sparks[0]
    try:
        try:
            from zlsp import parser as _p  # pylint: disable=import-outside-toplevel
            data = _p.loads(spark_file.read_text(encoding="utf-8"), filename=spark_file.name)
        except ImportError:
            import yaml  # pylint: disable=import-outside-toplevel
            data = yaml.safe_load(spark_file.read_text(encoding="utf-8")) or {}

        spark  = data.get("zSpark") or {}
        zinfo  = data.get("zInfo")  or {}
        return {
            "title":       spark.get("title", demo_dir.name),
            "description": zinfo.get("description", ""),
            "tags":        zinfo.get("tags") or [],
            "author":      zinfo.get("author", ""),
            "spark_file":  spark_file.name,
        }
    except Exception:  # pylint: disable=broad-except
        return {"title": demo_dir.name, "description": "", "tags": [], "author": ""}


def _read_raven_result(demo_dir: Path) -> Optional[dict]:
    """Read .last_raven_result JSON if present."""
    result_path = demo_dir / "zRaven" / ".last_raven_result"
    if not result_path.exists():
        return None
    try:
        return json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:  # pylint: disable=broad-except
        return None


def _raven_badge(result: Optional[dict]) -> str:
    if not result:
        return "  [no raven result]"
    total   = result.get("steps_total", 0)
    passed  = result.get("steps_passed", 0)
    status  = result.get("result", "?")
    mark    = "✓" if status == "pass" else "✗"
    return f"  zRaven: {mark} {passed}/{total}"


# ── Commands ──────────────────────────────────────────────────────────────────

def _cmd_list(demos_dir: Path) -> int:
    demos = sorted(p for p in demos_dir.iterdir() if p.is_dir())
    if not demos:
        print("\n  No demos found.\n")
        return 0

    print(f"\n  zDemos  ({demos_dir})\n")
    print(f"  {'Name':<16}  {'Description'}")
    print(f"  {'-'*16}  {'-'*48}")
    for demo in demos:
        info   = _read_spark_info(demo)
        raven  = _read_raven_result(demo)
        badge  = ("✓" if (raven or {}).get("result") == "pass" else
                  ("✗" if raven else "·"))
        tags   = "  [" + ", ".join(info.get("tags", [])) + "]" if info.get("tags") else ""
        print(f"  {demo.name:<16}  {info.get('description','')}")
        print(f"  {'':<16}  {badge} raven{tags}")
        print()

    print(f"  Run  z demos <name>            for detail")
    print(f"  Run  z demos <name> --clone    to start from this demo\n")
    return 0


def _cmd_detail(demos_dir: Path, name: str) -> int:
    demo = demos_dir / name
    if not demo.is_dir():
        print(f"\n  ✗ Demo '{name}' not found in {demos_dir}\n")
        return 1

    info  = _read_spark_info(demo)
    raven = _read_raven_result(demo)

    print(f"\n  ── {name} ──")
    print(f"  Title:       {info.get('title','')}")
    print(f"  Description: {info.get('description','')}")
    print(f"  Author:      {info.get('author','')}")
    tags = info.get("tags", [])
    if tags:
        print(f"  Tags:        {', '.join(tags)}")
    print(f"  Spark:       {info.get('spark_file','')}")
    print(_raven_badge(raven))
    if raven and raven.get("failed_steps"):
        print(f"  Failed:      {', '.join(raven['failed_steps'])}")
    print(f"\n  Path:  {demo}")
    print(f"\n  Clone: z demos {name} --clone --name <appname>\n")
    return 0


def _cmd_clone(demos_dir: Path, name: str, new_name: Optional[str], dest: Optional[str]) -> int:
    demo = demos_dir / name
    if not demo.is_dir():
        print(f"\n  ✗ Demo '{name}' not found.\n")
        return 1

    if not new_name:
        print(f"\n  ✗ --name <appname> required for --clone.\n")
        return 1

    target_base = Path(dest).resolve() if dest else Path.cwd()
    target      = target_base / new_name

    if target.exists():
        print(f"\n  ✗ Destination already exists: {target}\n")
        return 1

    print(f"\n  Cloning {name} → {target} ...")
    shutil.copytree(
        demo, target,
        ignore=shutil.ignore_patterns(
            "*.pyc", "__pycache__", ".last_raven_result",
            "zRaven.last_run.log", "logs", "*.log",
        ),
    )
    # Rename spark file
    for spark in target.glob("zSpark.*.zolo"):
        new_spark = target / f"zSpark.{new_name}.zolo"
        if spark != new_spark:
            spark.rename(new_spark)
        break

    print(f"  ✓ Done — {target}")
    print(f"\n  Next:")
    print(f"    cd {target}")
    print(f"    z raven --run\n")
    return 0


# ── Entry ─────────────────────────────────────────────────────────────────────

def handle_demos_command(args) -> int:
    demos_dir = _find_demos_dir()

    if demos_dir is None:
        print(
            "\n  zDemos not found locally.\n"
            "  This is a regular (non-editable) install — remote demo registry coming soon.\n"
            "  For now: clone zOS-OpenCore and install with  pip install -e .\n"
        )
        return 1

    name     = getattr(args, "name",     None)
    clone    = getattr(args, "clone",    False)
    new_name = getattr(args, "new_name", None)
    dest     = getattr(args, "dest",     None)

    if not name:
        return _cmd_list(demos_dir)

    if clone:
        return _cmd_clone(demos_dir, name, new_name, dest)

    return _cmd_detail(demos_dir, name)
