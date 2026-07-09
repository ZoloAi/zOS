# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/environment/config_requirements.py
"""
zRequirements — declarative per-app Python dependencies.

Declared inside an app's zEnv.*.zolo (same file, same grammar as any other
zEnv key — no new file format):

    zRequirements: [Pillow>=10.0, requests]

SSOT gate — same shape as schema migrations (zSys/cli/zspark_command.py):
  - Boot NEVER auto-installs. It only VERIFIES the declared packages are
    already installed, and refuses to launch if not, printing the exact
    command to fix it.
  - The only writer is the explicit `z requirements <zspark file>` command.

Checked by DISTRIBUTION name (importlib.metadata), not import name, so a
spec like "Pillow" correctly matches even though it imports as "PIL" —
sidesteps the classic install-name/import-name mismatch.
"""

from __future__ import annotations

import re
import subprocess
import sys
from importlib import metadata as _metadata

from zOS import os, List, Tuple

# Distribution name at the head of a PEP 508 requirement spec, e.g.
# "Pillow>=10.0" -> "Pillow", "requests" -> "requests", "a[extra]==1" -> "a".
_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")


def parse_distribution_name(spec: str) -> str:
    """Extract the bare distribution name from a pip requirement spec."""
    match = _NAME_RE.match(spec)
    return match.group(1) if match else spec.strip()


def read_declared_requirements(
    workspace_dir,
    deployment: str = "development",
    logger=None,
) -> List[str]:
    """Load ``zRequirements`` declared in an app's zEnv.*.zolo files.

    Loads zEnv (base -> deployment override) for ``workspace_dir`` through
    the SAME loader zOS boots with (config_zenv.zEnv), then reads the
    resolved ``zRequirements`` key back out of os.environ. Only a flat list
    is a supported shape; anything else is ignored (returns []).
    """
    from .config_zenv import zEnv, loads_env_value  # local: avoid early-boot import cycle

    zEnv(str(workspace_dir), deployment, logger=logger).load()
    raw = loads_env_value(os.environ.get("zRequirements"))
    return raw if isinstance(raw, list) else []


def find_missing_requirements(specs: List[str]) -> List[str]:
    """Return the subset of ``specs`` whose distribution is not installed.

    Presence-only check (by distribution name) — version constraints in the
    spec are not resolved. This keeps the boot gate a lightweight tripwire,
    not a dependency resolver; `z requirements` still passes the full spec
    (including the constraint) to pip when installing.
    """
    missing = []
    for spec in specs:
        name = parse_distribution_name(spec)
        try:
            _metadata.version(name)
        except _metadata.PackageNotFoundError:
            missing.append(spec)
    return missing


def _uv_available() -> bool:
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def install_requirements(specs: List[str]) -> Tuple[bool, str]:
    """Install ``specs`` into the current interpreter's environment.

    Prefers `uv pip install --python <sys.executable>` (same tool z patch
    already relies on) — a `z` install via `uv tool install` has no bundled
    `pip` module, so a plain `python -m pip install` fails there. Falls back
    to `python -m pip install` for interpreters that DO have pip (e.g. a
    plain venv) and don't have uv on PATH.
    """
    if not specs:
        return True, "Nothing to install."
    if _uv_available():
        cmd = ["uv", "pip", "install", "--python", sys.executable, *specs]
    else:
        cmd = [sys.executable, "-m", "pip", "install", *specs]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    ok = result.returncode == 0
    return ok, (result.stdout or "") + (result.stderr or "")
