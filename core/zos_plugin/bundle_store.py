"""
Bundle stores — the storage primitive behind ``zolo push``. "Persist a pushed
app bundle and make its files reachable" is a *general* zOS capability, so it
lives here in the plugin SDK (sibling to :mod:`drivers`, which runs instances).

A :class:`BundleStore` is the swappable backend:

    * :class:`LocalBundleStore` — dev/localhost. Unpacks the bundle's ``app/``
      slice into ``<workspace>/_hosted/<slug>/`` so the same front-door +
      LocalProcessDriver path that wakes a checked-in app wakes a pushed one.
      ``attachments/`` (dormant include payload) land beside it, never executed.
    * An ``S3BundleStore`` (prod) registers later via :func:`register_bundle_store`
      with no change to callers — bytes go to S3, app/ syncs to the pod volume.

The store only moves bytes; *policy* (who may push, registry upsert) stays with
the caller (the host platform's push plugin). The returned :class:`StoredBundle`
carries everything the registry needs to point an app-registry row at the app.
"""

from __future__ import annotations

import abc
import io
import os
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .release import normalize_build_id

from .drivers import DEFAULT_SPARK

__all__ = [
    "StoredBundle", "BundleStore", "LocalBundleStore",
    "register_bundle_store", "get_bundle_store",
    "HOSTED_DIRNAME", "BUILDS_DIRNAME",
]

# Where pushed apps land under a workspace, kept distinct from checked-in apps.
# Neutral, platform-agnostic default — the leading underscore keeps it out of
# zServer's folder→route discovery. A host platform may override via ZHOST_HOSTED_DIR.
HOSTED_DIRNAME = os.environ.get("ZHOST_HOSTED_DIR") or "_hosted"
# Per-version subtree so blue and green coexist for a zRelease rollout.
BUILDS_DIRNAME = "builds"

_APP_PREFIX = "app/"
_ATTACH_PREFIX = "attachments/"

# Resource caps for unpacking a client-supplied bundle — a tar.gz is untrusted
# input, so guard against decompression bombs / OOM before writing anything.
# Overridable per host via env; defaults suit an app bundle (UI + plugins).
DEFAULT_MAX_BUNDLE_BYTES = 512 * 1024 * 1024   # 512 MiB uncompressed total
DEFAULT_MAX_BUNDLE_FILES = 10_000              # member-count ceiling


@dataclass
class StoredBundle:
    """Result of unpacking a bundle — what the registry needs to wake the app."""

    slug: str
    app_dir: Path             # absolute dir the spark boots from (driver cwd)
    rel_root: str             # app_dir relative to the workspace (posix)
    spark: str                # spark filename (basename)
    app_files: int = 0
    attachment_files: int = 0

    @property
    def zspark_path(self) -> str:
        """Registry ``zspark_path`` — folder/spark relative to the workspace.

        Matches :meth:`AppSpec.from_spark_path` (it splits dirname/basename), so
        the front door resolves it against ``serve_path`` and the driver
        spawns ``zolo <spark>`` with ``cwd=<app_dir>``.
        """
        return f"{self.rel_root}/{self.spark}"


class BundleStore(abc.ABC):
    """Backend that persists a pushed bundle and exposes its app slice."""

    @abc.abstractmethod
    def unpack(self, slug: str, tar_bytes: bytes, spark: Optional[str] = None,
               build_id: Optional[Any] = None) -> StoredBundle:
        """Persist ``tar_bytes`` for ``slug``; return where the app now lives.

        ``build_id`` (zRelease) unpacks into a per-version subtree so a new build
        (green) can be staged without clobbering the live one (blue). When omitted,
        the store keeps the flat single-version layout (Phase-1 behaviour).
        """

    @abc.abstractmethod
    def remove(self, slug: str) -> bool:
        """Delete a stored bundle (all versions). Returns True if removed."""

    def prune(self, slug: str, keep_build_ids) -> list:  # pylint: disable=unused-argument
        """Remove build versions not in ``keep_build_ids``. Returns removed ids.

        Default no-op for stores without a versioned layout; overridden where
        builds coexist on a filesystem (see :class:`LocalBundleStore`).
        """
        return []


def _safe_join(base: Path, member_name: str) -> Optional[Path]:
    """Resolve ``member_name`` under ``base``, refusing traversal/absolute paths."""
    target = (base / member_name).resolve()
    base_resolved = base.resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError:
        return None
    return target


class LocalBundleStore(BundleStore):
    """Dev store: unpack the bundle onto the local filesystem under the workspace.

    Fresh pushes are authoritative — the slug's directory is replaced wholesale,
    so the on-disk app always reflects the last ``zolo push`` (no version cruft).
    """

    def __init__(self, workspace_dir: str):
        self._workspace = Path(workspace_dir).resolve()
        self._base = self._workspace / HOSTED_DIRNAME

    def _dest(self, slug: str, build_id: Optional[Any] = None) -> Path:
        if build_id is None:
            return self._base / slug
        # Per-version dir: <slug>/builds/<build_id>/ so blue/green coexist.
        # normalize_build_id keeps the dir name canonical ("2", not "2.0") so it
        # matches the prune keep-set even when the id arrives float-coerced.
        return self._base / slug / BUILDS_DIRNAME / normalize_build_id(build_id)

    def _builds_dir(self, slug: str) -> Path:
        return self._base / slug / BUILDS_DIRNAME

    def unpack(self, slug: str, tar_bytes: bytes, spark: Optional[str] = None,
               build_id: Optional[Any] = None) -> StoredBundle:
        dest = self._dest(slug, build_id)
        # Replace only THIS build's dir — sibling builds (blue) are untouched.
        if dest.exists():
            shutil.rmtree(dest)
        app_dir = dest  # app/ contents are written at the build root (cwd to spark)
        attach_dir = dest / "_attachments"
        app_dir.mkdir(parents=True, exist_ok=True)

        max_bytes = int(os.environ.get("ZHOST_MAX_BUNDLE_BYTES") or DEFAULT_MAX_BUNDLE_BYTES)
        max_files = int(os.environ.get("ZHOST_MAX_BUNDLE_FILES") or DEFAULT_MAX_BUNDLE_FILES)

        app_n = attach_n = 0
        total_bytes = total_files = 0
        detected_spark = spark
        try:
            with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
                for member in tar.getmembers():
                    if not member.isfile():
                        # Skip dirs and, crucially, sym/hardlinks (never extracted).
                        continue
                    # Fail closed on decompression-bomb shapes *before* writing.
                    total_files += 1
                    if total_files > max_files:
                        raise ValueError(
                            f"bundle exceeds file-count cap ({max_files}); refusing to unpack"
                        )
                    total_bytes += max(int(member.size or 0), 0)
                    if total_bytes > max_bytes:
                        raise ValueError(
                            f"bundle exceeds size cap ({max_bytes} bytes); refusing to unpack"
                        )

                    name = member.name.lstrip("./")
                    if name.startswith(_APP_PREFIX):
                        rel = name[len(_APP_PREFIX):]
                        out = _safe_join(app_dir, rel)
                        if out is None:
                            continue
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(tar.extractfile(member).read())
                        app_n += 1
                        base = os.path.basename(rel)
                        if not detected_spark and base.startswith("zSpark.") and base.endswith(".zolo"):
                            detected_spark = base
                    elif name.startswith(_ATTACH_PREFIX):
                        rel = name[len(_ATTACH_PREFIX):]
                        out = _safe_join(attach_dir, rel)
                        if out is None:
                            continue
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(tar.extractfile(member).read())
                        attach_n += 1
                    # zProject.json + anything else at bundle root is metadata — skip.
        except Exception:
            # Never leave a half-written build dir behind on a rejected bundle.
            shutil.rmtree(dest, ignore_errors=True)
            raise

        rel_root = app_dir.relative_to(self._workspace).as_posix()
        return StoredBundle(
            slug=slug,
            app_dir=app_dir,
            rel_root=rel_root,
            spark=detected_spark or DEFAULT_SPARK,
            app_files=app_n,
            attachment_files=attach_n,
        )

    def remove(self, slug: str) -> bool:
        # Whole slug subtree (flat app dir + any builds/).
        dest = self._base / slug
        if dest.exists():
            shutil.rmtree(dest)
            return True
        return False

    def prune(self, slug: str, keep_build_ids) -> list:
        """Drop build dirs not in ``keep_build_ids`` (e.g. keep live + previous)."""
        builds = self._builds_dir(slug)
        if not builds.is_dir():
            return []
        # Normalize so a float-coerced id ("1.0") still matches its dir ("1") —
        # otherwise prune deletes the rollback build it was meant to keep.
        keep = {normalize_build_id(b) for b in keep_build_ids}
        removed = []
        for child in builds.iterdir():
            if child.is_dir() and child.name not in keep:
                shutil.rmtree(child, ignore_errors=True)
                removed.append(child.name)
        return removed


# ─────────────────────────────────────────────────────────────────────────────
# Store registry — env selects the backend (dev=local, prod=s3, …)
# ─────────────────────────────────────────────────────────────────────────────

_STORES: Dict[str, Callable[[str], BundleStore]] = {
    "local": LocalBundleStore,
}


def register_bundle_store(name: str, factory: Callable[[str], BundleStore]) -> None:
    """Register a backend factory (e.g. ``register_bundle_store('s3', S3BundleStore)``)."""
    _STORES[name] = factory


def get_bundle_store(zos: Any = None, workspace_dir: Optional[str] = None) -> BundleStore:
    """Resolve the active store: ``ZHOST_STORE`` env → 'local', rooted at the workspace.

    Workspace resolution: explicit arg → ``zos.workspace_dir`` → cwd. Unlike the
    compute driver these are not cached as singletons — a store is cheap and the
    workspace is stable per host process.
    """
    name = os.environ.get("ZHOST_STORE") or "local"
    root = workspace_dir or getattr(zos, "workspace_dir", None) or os.getcwd()
    factory = _STORES.get(name) or _STORES["local"]
    return factory(str(root))
