"""
zPersist mounts — a hosted app's writable ``Data/`` root, OUTSIDE the bundle
(zOS#114, the data-survival spec spun out of #63).

Every ``zolo push`` is a full replace: the new build's directory is written
fresh and the old one eventually pruned. The #63 guard stops the *accidental*
wipe (409 when a push would drop live ``Data/`` files), but the correct
long-term shape for a stateful hosted app is a writable root that a code push
never even has to think about. That is what a persist mount is:

    <persist_root>/<namespace>/Data      e.g. …/_persist/herald/zledger/Data

An app opts in from its own zSpark — ``zPersist: true`` — and the push
receiver calls :func:`relocate_data_root` after unpack:

    1. FIRST persist push: the mount is seeded — from the previous LIVE
       build's ``Data/`` when one exists (that's the production truth, not
       the pushed seed), else from the bundle's own ``Data/``.
    2. The build's unpacked ``Data/`` dir is replaced with a SYMLINK to the
       mount. The child boots with cwd = build dir, so every relative
       ``Data/…`` read/write lands on the mount — no zData changes needed.
    3. Every later push repeats step 2 only. The mount is never written by
       a push again; the bundle's ``Data/`` becomes seed-only, exactly as
       specced in #63.

Emergent properties worth knowing:
    • The #63 guard goes quiet for persist apps on its own: the store's
      ``list_app_files`` never follows symlinks, so the live build appears
      to have no ``Data/`` files — truthful, since a push can't delete them.
    • A soft delete (``zolo apps delete``) removes build dirs but not the
      mount — a re-push revives the app WITH its data.
    • Local dev is untouched: nothing here runs outside a push receiver.
      (The zSpark ``zPersist`` key's existing local meaning — create the
      per-machine ``Apps/<app>/`` root — is unchanged and unrelated.)

SECURITY: a pushed spark never chooses the mount's location. ``zPersist``
may carry a path value for future local use, but the receiver treats ANY
truthy value as a plain opt-in — the host derives the mount from its own
persist root + the owner-scoped namespace, so one tenant can never point
their mount at another tenant's data (or at ``/etc``).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Optional

from .bundle_store import resolve_hosted_root

__all__ = [
    "PERSIST_DIRNAME", "DATA_DIRNAME",
    "resolve_persist_root", "persist_mount",
    "spark_wants_persist", "relocate_data_root", "data_is_relocated",
]

PERSIST_DIRNAME = "_persist"
DATA_DIRNAME = "Data"

_FALSY = {"", "false", "no", "off", "0", "none", "null"}


def resolve_persist_root(zos: Any = None) -> Path:
    """Where this host keeps persist mounts.

    Priority: ``ZHOST_PERSIST_ROOT`` (env, absolute) → ``<storage root>/_persist``
    where the storage root is ``STORAGE_LOCAL_ROOT`` (env or zEnv; relative
    values resolve against the hosted root) → ``<hosted_root>/storage/_persist``.

    Anchoring under the storage root is deliberate (#63 spec): user data and
    uploaded media share a lifetime — back up the storage root and you have
    everything users ever wrote, no matter how many builds came and went.
    """
    raw = os.environ.get("ZHOST_PERSIST_ROOT")
    if raw:
        candidate = Path(raw).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()

    hosted = resolve_hosted_root(zos)
    storage = os.environ.get("STORAGE_LOCAL_ROOT")
    if not storage:
        try:
            env = getattr(getattr(zos, "config", None), "environment", None)
            if env is not None:
                storage = env.get("storage_local_root") or env.get_env_var("STORAGE_LOCAL_ROOT")
        except Exception:  # pylint: disable=broad-except
            storage = None
    storage_root = Path(str(storage)).expanduser() if storage else Path("storage")
    if not storage_root.is_absolute():
        storage_root = hosted / storage_root
    return (storage_root / PERSIST_DIRNAME).resolve()


def persist_mount(zos: Any, namespace: str) -> Path:
    """The Data mount for one owner-scoped app namespace (e.g. ``herald/zledger``)."""
    return resolve_persist_root(zos) / namespace / DATA_DIRNAME


def spark_wants_persist(spark_file: Path) -> bool:
    """Does this unpacked zSpark opt into a persist mount? (tolerant line scan)

    Same doctrine as the receiver's other spark reads: a raw-text scan for the
    single-line scalar, never a parser dependency — an exotic-but-bootable
    spark can't brick a push. Any non-falsy value counts as opt-in (a path
    value is honoured as TRUE, not as a location — see module SECURITY note).
    """
    try:
        text = Path(spark_file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped.startswith("zPersist:"):
            value = stripped.split(":", 1)[1].strip().lower()
            return value not in _FALSY
    return False


def data_is_relocated(build_dir: Path) -> bool:
    """True when a build's ``Data/`` is already a symlink onto a mount."""
    return (Path(build_dir) / DATA_DIRNAME).is_symlink()


def relocate_data_root(build_dir: Path, mount: Path,
                       seed_from: Optional[Path] = None,
                       logger: Any = None) -> dict:
    """Point ``<build_dir>/Data`` at ``mount``; seed the mount on first use.

    Idempotent: an already-linked build is a no-op. Returns a summary dict —
    ``{"seeded_from": str|None, "seeded_files": int, "mount": str}`` — for the
    push response / log line.

    Seeding happens only when the mount does not yet exist (never merges into
    live data): preference order is ``seed_from`` (the previous LIVE build's
    ``Data/``, i.e. production truth when zPersist is turned on for an app
    that already has users) then the bundle's own ``Data/``.
    """
    build_dir = Path(build_dir)
    mount = Path(mount)
    bundle_data = build_dir / DATA_DIRNAME

    seeded_from: Optional[Path] = None
    if not mount.exists():
        for candidate in (seed_from, bundle_data):
            if candidate and Path(candidate).is_dir() and not Path(candidate).is_symlink():
                seeded_from = Path(candidate)
                break
        mount.parent.mkdir(parents=True, exist_ok=True)
        if seeded_from is not None:
            shutil.copytree(seeded_from, mount, symlinks=False)
        else:
            mount.mkdir(parents=True, exist_ok=True)

    if bundle_data.is_symlink():
        # Re-push onto an already-relocated layout: refresh the link only if
        # it points elsewhere (e.g. the persist root moved).
        if bundle_data.resolve() != mount.resolve():
            bundle_data.unlink()
            bundle_data.symlink_to(mount, target_is_directory=True)
    else:
        if bundle_data.is_dir():
            shutil.rmtree(bundle_data)
        bundle_data.symlink_to(mount, target_is_directory=True)

    seeded_files = 0
    if seeded_from is not None:
        seeded_files = sum(1 for p in mount.rglob("*") if p.is_file())
    summary = {
        "mount": str(mount),
        "seeded_from": str(seeded_from) if seeded_from else None,
        "seeded_files": seeded_files,
    }
    if logger is not None:
        if seeded_from is not None:
            logger.info(f"[zpersist] mount seeded from {seeded_from} "
                        f"({seeded_files} files) → {mount}")
        logger.info(f"[zpersist] {build_dir.name}: Data/ → {mount}")
    return summary
