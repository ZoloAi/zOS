"""
zownership_store shim — public zOS repo.

zOwnership (the zMachine instance-owner identity at rest, SEPARATE from the
runtime session) persistence lives in the private ``zguard.auth.zownership_store``
package so zGuard can seal the token at rest (OS keychain) in production. This
re-exports the public API so all existing imports are unchanged. Without zGuard it
degrades to a no-op (load→None, save/clear→False) so boot still proceeds with no
owner resolved.
"""

try:
    from zguard.auth.zownership_store import (  # noqa: F401
        zownership_path,
        save_zownership,
        load_zownership,
        clear_zownership,
        ZOWNERSHIP_FILENAME,
        ZOWNERSHIP_BLOCK,
    )
except ImportError:
    ZOWNERSHIP_FILENAME = "zConfig.identity.zolo"
    ZOWNERSHIP_BLOCK = "zIdentity"

    def zownership_path(_zos):
        return None

    def save_zownership(_zos, _identity):
        return False

    def load_zownership(_zos):
        return None

    def clear_zownership(_zos):
        return False

__all__ = [
    "zownership_path", "save_zownership", "load_zownership", "clear_zownership",
    "ZOWNERSHIP_FILENAME", "ZOWNERSHIP_BLOCK",
]
