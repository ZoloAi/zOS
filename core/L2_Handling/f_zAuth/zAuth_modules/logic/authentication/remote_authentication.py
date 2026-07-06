"""
remote_authentication shim — public zOS repo.

The instance → zCloud auth handshake lives in the private
``zguard.auth.remote_authentication`` package (binary wheel via zGuard). This
re-exports ``RemoteAuthenticationManager`` so the open Authentication facade can
compose it unchanged. Without zGuard the manager constructs but raises a clear
"run z patch" error if a remote login is actually attempted.
"""

try:
    from zguard.auth.remote_authentication import RemoteAuthenticationManager  # noqa: F401
except ImportError:
    class RemoteAuthenticationManager:  # noqa: N801
        """Placeholder when zGuard is not installed (remote auth disabled)."""

        def __init__(self, zos=None, **_kwargs):
            self.zos = zos

        def authenticate_remote(self, *_args, **_kwargs):
            raise ImportError(
                "Remote auth runtime unavailable (Python ABI mismatch or missing zguard).\n"
                "Fix: z patch"
            )

__all__ = ["RemoteAuthenticationManager"]
