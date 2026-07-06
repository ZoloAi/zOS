"""
api_key_auth shim — public zOS repo.

The PAT (Personal Access Token) implementation lives in the private
``zguard.auth.api_key_auth`` package (binary wheel via zGuard). This re-exports
the public API so all existing zAuth imports are unchanged. Without zGuard the
functions raise a clear "run z patch" error on use.
"""

try:
    from zguard.auth.api_key_auth import (  # noqa: F401
        hash_token,
        generate_api_key,
        issue_api_key,
        verify_api_key,
        revoke_api_key,
        authenticate_api_key,
    )
except ImportError:
    def _zguard_required(*_args, **_kwargs):
        raise ImportError(
            "zAuth PAT runtime unavailable (Python ABI mismatch or missing zguard).\n"
            "Fix: z patch"
        )

    hash_token = generate_api_key = issue_api_key = _zguard_required
    verify_api_key = revoke_api_key = authenticate_api_key = _zguard_required

__all__ = [
    "hash_token", "generate_api_key",
    "issue_api_key", "verify_api_key", "revoke_api_key", "authenticate_api_key",
]
