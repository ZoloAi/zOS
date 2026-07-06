# zOS/core/L1_Foundation/c_zLoader/loader_modules/loader_trust.py

"""
Plugin-trust gate — public zOS repo shim.

zLoader executes plugin code (``importlib.exec_module`` for ``.py``, subprocess
for ``.js``) with the live ``zos`` instance injected. This module is the single
enforcement point that decides whether a given plugin path is allowed to load.

The real policy (allowed directories, signature / hash verification, etc.) lives
in the private ``zguard.loader.plugin_trust`` package (binary wheel via zGuard),
mirroring the zAuth shims. Without zGuard the gate is permissive — open-core
stays fully functional and loads plugins from any path (the public, unsealed
path). Installing zGuard seals this seam with no call-site changes.

Enforcement contract
---------------------
``verify_plugin_trust(file_path, zos=None, logger=None) -> bool``
    Returns True when the plugin is allowed to load. The zGuard implementation
    raises ``PluginTrustError`` when policy denies the path; that exception must
    propagate to the caller (never be swallowed or re-wrapped).
"""

from .loader_constants import PluginTrustError  # re-exported for the zGuard seam

try:
    # Sealed enforcement (allowed dirs / signatures) when zGuard is installed.
    from zguard.loader.plugin_trust import verify_plugin_trust  # noqa: F401
except ImportError:
    def verify_plugin_trust(_file_path, _zos=None, _logger=None) -> bool:  # noqa: D401
        """Fallback: no zGuard → no enforcement (open-core permissive path)."""
        return True

__all__ = ["verify_plugin_trust", "PluginTrustError"]
