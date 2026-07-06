# zOS/core/L2_Handling/k_zOpen/open_modules/open_trust.py

"""
Path-trust gate — public zOS repo shim (zOpen surface).

zOpen resolves user/content-supplied paths (``@`` workspace, ``~`` absolute,
bare filesystem paths) and then **reads them, displays their content, or
launches a local application on them**. This module is the single seam that
decides whether a resolved path is allowed to be opened.

It reuses the *same* sealed policy as zParser's read gate (workspace
containment, allowed roots, ``..`` rejection, signature checks) — pulled from
the private ``zguard.parser.path_trust`` package — so path-trust enforcement is
DRY across every subsystem that touches disk. Mirrors the per-surface seam
pattern (``loader_trust`` / ``parser_trust`` / ``display_trust``).

Without zGuard the gate is permissive — open-core stays fully functional and
opens any path the operator's workspace points at (the public, unsealed path).
Installing zGuard seals this seam with no call-site changes. Note this is the
*content/path* gate (V2); the *who-triggered-it* mode gate (zCLI vs Bifrost)
lives in the zOpen facade.

Enforcement contract
--------------------
``verify_path_trust(path, zos=None, logger=None) -> bool``
    Returns True when the path is allowed. The zGuard implementation raises
    ``PathTrustError`` when policy denies the path; that exception must
    propagate to the caller (never be swallowed or re-wrapped).
"""


class PathTrustError(Exception):
    """Raised by the zGuard path-trust policy when a resolved path is denied.

    Propagated unwrapped so a denial is always visible to the caller. In
    open-core (no zGuard) this is never raised — the gate is permissive.
    """


try:
    # Sealed enforcement (containment / allowed roots) when zGuard is installed.
    # Reuses zParser's path-trust policy module so the rule set is single-sourced.
    from zguard.parser.path_trust import verify_path_trust  # noqa: F401
except ImportError:
    def verify_path_trust(_path, _zos=None, _logger=None) -> bool:  # noqa: D401
        """Fallback: no zGuard → no enforcement (open-core permissive path)."""
        return True


__all__ = ["verify_path_trust", "PathTrustError"]
