# zSys/cli/zguard_provision.py
"""
zguard_provision — resolves, caches, and live-fetches the compiled `zguard`
binaries the running machine needs so `import zguard` works.

Three-way branch, decided fresh each boot (cheap after the first — the
"verified cache" path is a single local file read plus one tiny HTTP GET):

  1. Dev / editable  -- ZGUARD_DEV_PATH points at a local zGuard source
                         checkout: use it directly, skip everything else.
  2. Verified cache   -- a matching <platform-tag>/<py-tag> build is already
                         fetched under zMachine and its VERSION matches the
                         repo's current one: no-op.
  3. Fetch            -- otherwise: pull VERSION + MANIFEST.txt + every file
                         the manifest lists from the public zOS GitHub repo
                         (plain HTTPS GET, no git needed) into the zMachine
                         cache.

If the running platform/Python ABI isn't one zOS ships a build for at all
(e.g. cp313, or an unsupported OS/arch), none of the above can help --
`is_supported()` returns False and the caller (patch_command.py / main.py)
falls back to reinstalling onto a Python version we do support.
"""

import os
import platform
import sys
import time
from pathlib import Path
from typing import Optional

RAW_BASE = "https://raw.githubusercontent.com/ZoloAi/zOS/main/zguard_bin"

# Once a cached build is verified against the repo's VERSION, trust it for a
# day before checking again -- every `z` invocation calls
# ensure_zguard_importable(), and a network round-trip on every single CLI
# command would be a real latency tax for no practical benefit.
_RECHECK_INTERVAL_SECONDS = 24 * 60 * 60

SUPPORTED_PY_TAGS = ("cp310", "cp311", "cp312")
SUPPORTED_PLATFORM_TAGS = (
    "darwin-arm64", "darwin-x86_64",
    "linux-x86_64", "linux-aarch64",
    "win-amd64",
)


def current_platform_tag() -> Optional[str]:
    """e.g. 'darwin-arm64', 'linux-x86_64', 'win-amd64' — or None if this OS/arch isn't one we build for."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        return "darwin-arm64" if machine in ("arm64", "aarch64") else "darwin-x86_64"
    if system == "linux":
        return "linux-aarch64" if machine in ("aarch64", "arm64") else "linux-x86_64"
    if system == "windows":
        return "win-amd64" if machine in ("amd64", "x86_64") else None
    return None


def current_py_tag() -> str:
    """e.g. 'cp312'."""
    vi = sys.version_info
    return f"cp{vi.major}{vi.minor}"


def is_supported(platform_tag: Optional[str], py_tag: str) -> bool:
    return platform_tag in SUPPORTED_PLATFORM_TAGS and py_tag in SUPPORTED_PY_TAGS


def zguard_dev_path() -> Optional[Path]:
    """
    Explicit dev/editable override. Deliberately read from an env var, never
    guessed from a sibling-folder convention — zGuard's source checkout can
    live anywhere on a given dev's machine.
    """
    raw = os.environ.get("ZGUARD_DEV_PATH")
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if (path / "zguard").exists() else None


def cache_root(platform_tag: str, py_tag: str) -> Path:
    """
    zMachine-rooted cache dir for one platform+ABI's fetched binaries. This
    directory's *contents* mirror the repo's own <platform-tag>/<py-tag>/
    folder (VERSION, MANIFEST.txt, zguard/) — the parent of the `zguard/`
    subfolder is what belongs on sys.path.
    """
    from zOS.L1_Foundation.a_zConfig.zConfig_modules import zConfigPaths  # pylint: disable=import-outside-toplevel
    zmachine = zConfigPaths().user_data_dir
    return zmachine / "zguard_bin" / platform_tag / py_tag


def _get_text(url: str, timeout: float = 10.0) -> Optional[str]:
    import requests  # pylint: disable=import-outside-toplevel
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.text if resp.status_code == 200 else None
    except requests.RequestException:
        return None


def _get_bytes(url: str, timeout: float = 15.0) -> Optional[bytes]:
    import requests  # pylint: disable=import-outside-toplevel
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.content if resp.status_code == 200 else None
    except requests.RequestException:
        return None


def is_provisioned(dest: Path, platform_tag: str, py_tag: str) -> bool:
    """
    True if `dest` already holds a build whose VERSION matches the repo's
    current one. Recently-verified caches skip the network entirely (see
    _RECHECK_INTERVAL_SECONDS); unreachable network is treated as "trust the
    cache" so a machine that's already working never breaks by going offline.
    """
    local_version_file = dest / "VERSION"
    if not (dest / "zguard" / "__init__.py").exists() or not local_version_file.exists():
        return False

    age = time.time() - local_version_file.stat().st_mtime
    if age < _RECHECK_INTERVAL_SECONDS:
        return True

    remote_version = _get_text(f"{RAW_BASE}/{platform_tag}/{py_tag}/VERSION")
    if remote_version is None:
        return True  # unreachable -- don't punish an already-working install

    if local_version_file.read_text().strip() != remote_version.strip():
        return False
    local_version_file.touch()  # verified again -- reset the recheck clock
    return True


def fetch_zguard_binaries(dest: Path, platform_tag: str, py_tag: str) -> bool:
    """
    Pull VERSION + MANIFEST.txt + every manifest-listed file into `dest`,
    preserving the zguard/... relative layout. Writes VERSION last, only on
    full success, so a half-fetched build never looks "provisioned" to the
    next boot — it just retries.
    """
    base = f"{RAW_BASE}/{platform_tag}/{py_tag}"
    manifest_text = _get_text(f"{base}/MANIFEST.txt")
    version_text = _get_text(f"{base}/VERSION")
    if manifest_text is None or version_text is None:
        return False

    files = [line.strip() for line in manifest_text.splitlines() if line.strip()]
    dest.mkdir(parents=True, exist_ok=True)
    for rel in files:
        data = _get_bytes(f"{base}/{rel}")
        if data is None:
            return False
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    (dest / "VERSION").write_text(version_text)
    return True


def ensure_zguard_importable(verbose: bool = False) -> bool:
    """
    Make `import zguard` resolve for the rest of this process: dev source,
    a verified cache, or a fresh fetch, in that priority order. Call once,
    early in boot (see core/main.py). Returns False if this machine's
    platform/Python ABI isn't one we ship a build for, or if fetching failed
    — callers decide what to do about that (patch_command.py falls back to
    reinstalling onto a supported Python version via uv).
    """
    dev_path = zguard_dev_path()
    if dev_path is not None:
        parent = str(dev_path)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        if verbose:
            print(f"[zguard] dev mode — using {dev_path}")
        return True

    platform_tag = current_platform_tag()
    py_tag = current_py_tag()
    if not is_supported(platform_tag, py_tag):
        return False

    dest = cache_root(platform_tag, py_tag)
    if not is_provisioned(dest, platform_tag, py_tag):
        if verbose:
            print(f"[zguard] fetching {platform_tag}/{py_tag} binaries...")
        if not fetch_zguard_binaries(dest, platform_tag, py_tag):
            return False
        if verbose:
            print(f"[zguard] cached at {dest}")

    parent = str(dest)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    return True
