# zOS/core/L2_Handling/d_zParser/parser_modules/parser_trust.py

"""
Path-trust gate — public zOS repo shim.

zParser resolves declarative path references (``@`` workspace paths, ``~``
absolute paths, ``~.zMachine.*`` machine paths) and reads files off disk
(``parse_file_by_path``, ``handle_zRef``). This module is the single seam that
decides whether a resolved path is allowed to be read/used.

The real policy (workspace containment, allowed roots, ``..`` rejection,
signature checks, etc.) lives in the private ``zguard.parser.path_trust``
package (binary wheel via zGuard), mirroring the zLoader ``loader_trust`` and
zAuth shims. Without zGuard the gate is permissive — open-core stays fully
functional and resolves any path (the public, unsealed path). Installing zGuard
seals this seam with no call-site changes.

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
    from zguard.parser.path_trust import verify_path_trust  # noqa: F401
except ImportError:
    def verify_path_trust(_path, _zos=None, _logger=None) -> bool:  # noqa: D401
        """Fallback: no zGuard → no enforcement (open-core permissive path)."""
        return True


__all__ = ["verify_path_trust", "PathTrustError"]
