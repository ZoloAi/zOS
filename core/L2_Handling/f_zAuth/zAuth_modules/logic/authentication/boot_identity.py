"""
boot_identity shim — public zOS repo.

The boot-time Tier-1 identity cascade lives in the private
``zguard.auth.boot_identity`` package (binary wheel via zGuard). This re-exports
``resolve_boot_identity`` so the engine's boot path is unchanged. Without zGuard
boot proceeds anonymously (the public, unauthenticated path).
"""

try:
    from zguard.auth.boot_identity import resolve_boot_identity  # noqa: F401
except ImportError:
    def resolve_boot_identity(_zos):
        """Fallback: no zGuard → no identity resolution; stay anonymous."""
        return {"status": "anonymous", "source": None}

__all__ = ["resolve_boot_identity"]
