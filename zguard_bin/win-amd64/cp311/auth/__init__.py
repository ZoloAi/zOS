"""
zguard.auth — the load-bearing instance-auth slice (private runtime).

This is the "important slice" of zAuth that proves a zOS instance's Tier-1
identity to zCloud and establishes it at boot. Without it the runtime can't
authenticate (zolo push, hosted env-injected instances, the bifrost/GUI session
all depend on a resolved Tier-1 identity), so it ships compiled in production:

    api_key_auth          — PAT (Personal Access Token) mint / verify / revoke
    zownership_store       — zOwnership: the zMachine instance-owner identity at
                             rest (zConfig.identity.zolo; SEPARATE from runtime;
                             zGuard can seal this in the OS keychain later)
    zownership_login       — `z login` flows: registrar verify (password/PAT)
                             + browser device flow (the Zolo Media authority)
    remote_authentication  — the instance → zCloud HTTP auth handshake
    boot_identity          — boot-time runtime identity precedence cascade

Standard, non-secret pieces stay OPEN in zOS.f_zAuth: bcrypt password security,
RBAC, the login/logout facade glue, and the credential-verification SSOT
(action_login) — open algorithms are correct practice; this package is the slice
that is *operationally* load-bearing, not the cryptography.

Open core re-exports these via thin shims at their original f_zAuth paths, so all
existing imports are unchanged and boot degrades gracefully when zGuard is absent.
"""

from .api_key_auth import (
    hash_token, generate_api_key,
    issue_api_key, verify_api_key, revoke_api_key, authenticate_api_key,
)
from .zownership_store import (
    zownership_path, save_zownership, load_zownership, clear_zownership,
    ZOWNERSHIP_FILENAME, ZOWNERSHIP_BLOCK,
)
from .zownership_login import run_login
from .remote_authentication import RemoteAuthenticationManager
from .boot_identity import resolve_boot_identity
from .watermark import (
    instance_owner, is_registered, watermark_html, watermark_banner,
)

__all__ = [
    "hash_token", "generate_api_key",
    "issue_api_key", "verify_api_key", "revoke_api_key", "authenticate_api_key",
    "zownership_path", "save_zownership", "load_zownership", "clear_zownership",
    "ZOWNERSHIP_FILENAME", "ZOWNERSHIP_BLOCK",
    "run_login",
    "RemoteAuthenticationManager",
    "resolve_boot_identity",
    "instance_owner", "is_registered", "watermark_html", "watermark_banner",
]
