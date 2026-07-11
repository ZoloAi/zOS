"""
zguard.push — the `zolo push` implementation (private runtime).

`zolo push` ships a zProject to zCloud. The proprietary parts — manifest
resolution, bundle *closure* (what ships vs. stays dormant), and the upload
protocol (multipart framing + PAT bearer handshake to /api/apps/push) — live
here and compile to a binary in production.

Open core keeps only the CLI seam: the argparse subparser (`zSys.cli.args.push_args`)
and a thin dispatcher (`zSys.cli.push_command.handle_push_command`) that calls
:func:`run_push`. Mirrors the zguard.bifrost / zguard.zengine boundary.
"""

from zguard import __version__  # single-sourced from zguard/__init__.py
from .project_resolver import (
    resolve_zproject, parse_zproject, ZProjectError, ResolvedProject,
)
from .bundle import plan_bundle, build_bundle, BundlePlan, BundleError
from .command import run_push, DEFAULT_ZCLOUD_URL, PUSH_ENDPOINT

__all__ = [
    "resolve_zproject", "parse_zproject", "ZProjectError", "ResolvedProject",
    "plan_bundle", "build_bundle", "BundlePlan", "BundleError",
    "run_push", "DEFAULT_ZCLOUD_URL", "PUSH_ENDPOINT",
]
