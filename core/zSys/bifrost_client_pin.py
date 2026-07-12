# zSys/bifrost_client_pin.py
"""
bifrost_client_pin — SSOT for which bifrost-client the browser loads.

THE SSOT IS THE GIT TAG. The client repo (github.com/ZoloAi/zbifrost-client)
is public, and jsdelivr serves any tag directly:

    https://cdn.jsdelivr.net/gh/ZoloAi/zbifrost-client@v<pin>/...

Bootstrap (bifrost_client.js), zbase.css, AND bifrost_core.js all resolve from
the SAME tag — one pin versions the entire client atomically (the ~130 lazy
modules resolve relative to the core's own URL, so they ride the tag too).
No npm publish, no CDN purge, no propagation lag: push a tag, bump the pin.

The npm @1 channel remains ONLY as a fail-safe when the pin cannot be
resolved at all (fresh install, offline, no cache) — it must never be the
primary path again, because npm/local/git triple-sourcing caused exactly the
drift this module exists to kill.

The pin lives in zguard_bin/BIFROST_CLIENT_PIN (git-tracked, pruned from the
wheel like the rest of zguard_bin) and is resolved exactly like the zguard
binaries themselves (see zguard_provision.py): dev checkout reads the file
straight from the repo; installed machines fetch it from raw.githubusercontent
and cache it under zMachine with a daily recheck. Bumping the client is
therefore a git tag push + a one-line commit to zOS main — never a zolo-os
release, never a zGuard rebuild.

Consumed by BOTH sides of the bridge:
  * zOS zServer html_injectors  — <script src> / zbase.css <link> injection.
  * zGuard bridge_connection.so — connection_info.bifrost_core_url (imports
    this module at runtime; falls back to the npm @1 alias if absent).
"""

import os
import time
from pathlib import Path
from typing import Optional

# Both hosts below MUST be cdn.jsdelivr.net — bifrost_client.js's
# DEFAULT_CORE_ORIGINS allowlist only trusts that host (2026-07-11 bugfix).
_GH_CDN_FMT = 'https://cdn.jsdelivr.net/gh/ZoloAi/zbifrost-client@v{pin}'
# npm floating alias: FAIL-SAFE ONLY (pin unresolvable). Not the SSOT.
BIFROST_CDN_BASE = 'https://cdn.jsdelivr.net/npm/@zolomedia/bifrost-client@1'

_PIN_FILENAME = 'BIFROST_CLIENT_PIN'
_RAW_PIN_URL = f'https://raw.githubusercontent.com/ZoloAi/zOS/main/zguard_bin/{_PIN_FILENAME}'
_RECHECK_INTERVAL_SECONDS = 24 * 60 * 60

# Repo-checkout location: core/zSys/bifrost_client_pin.py -> <repo>/zguard_bin/
_REPO_PIN_PATH = Path(__file__).resolve().parents[2] / 'zguard_bin' / _PIN_FILENAME

_memo = {"pin": None, "at": 0.0}  # process-lifetime memo of the resolved pin


def bifrost_client_base() -> str:
    """Base URL for the whole client: bootstrap <script>, zbase.css, core.

    Priority: ZBIFROST_CLIENT_BASE env (explicit dev override) -> git-tag pin
    via jsdelivr/gh -> npm @1 alias (fail-safe only).
    """
    base = os.getenv('ZBIFROST_CLIENT_BASE')
    if base:
        return base
    pin = _resolve_pin()
    if pin:
        return _GH_CDN_FMT.format(pin=pin)
    return BIFROST_CDN_BASE


def bifrost_core_url() -> str:
    """URL of bifrost_core.js the client must dynamic-import.

    Same resolution as bifrost_client_base() — one pin, one tag, atomic client.
    """
    return f'{bifrost_client_base()}/bifrost_core.js'


def _resolve_pin() -> Optional[str]:
    """Repo file (dev checkout) -> zMachine cache / raw-GitHub fetch -> None."""
    if _memo["pin"] is not None and (time.time() - _memo["at"]) < _RECHECK_INTERVAL_SECONDS:
        return _memo["pin"]

    pin = _read_repo_pin() or _fetch_pin_cached()
    if pin:
        _memo["pin"], _memo["at"] = pin, time.time()
    return pin


def _read_repo_pin() -> Optional[str]:
    try:
        if _REPO_PIN_PATH.is_file():
            value = _REPO_PIN_PATH.read_text().strip()
            return value or None
    except OSError:
        pass
    return None


def _fetch_pin_cached() -> Optional[str]:
    """Installed machines: raw-GitHub fetch with a zMachine-cached daily recheck.

    Mirrors zguard_provision's offline posture — an unreachable network trusts
    the existing cache rather than breaking a working install.
    """
    cache_file = _pin_cache_path()
    cached = None
    if cache_file is not None and cache_file.is_file():
        cached = cache_file.read_text().strip() or None
        if (time.time() - cache_file.stat().st_mtime) < _RECHECK_INTERVAL_SECONDS:
            return cached

    remote = _get_text(_RAW_PIN_URL)
    if remote is None:
        return cached  # offline -> trust cache (possibly None)

    remote = remote.strip()
    if cache_file is not None and remote:
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(remote)
        except OSError:
            pass
    return remote or cached


def _pin_cache_path() -> Optional[Path]:
    try:
        from zOS.L1_Foundation.a_zConfig.zConfig_modules import zConfigPaths  # pylint: disable=import-outside-toplevel
        return zConfigPaths().user_data_dir / 'zguard_bin' / _PIN_FILENAME
    except Exception:  # pylint: disable=broad-except
        return None


def _get_text(url: str, timeout: float = 5.0) -> Optional[str]:
    import requests  # pylint: disable=import-outside-toplevel
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.text if resp.status_code == 200 else None
    except requests.RequestException:
        return None
