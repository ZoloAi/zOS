# zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/sandbox/display_trust.py

"""
Terminal-exec trust gate — public zOS repo shim.

zDisplay's ``zTerminal`` feature can execute code on the LOCAL machine (zCLI
mode). The open-core executor (``terminal_executor.py``) enforces a fail-closed
config gate first: zTerminal runs only when the operator explicitly declares
``ZTERMINAL_MODE = sandbox|trust`` in zEnv (``readonly`` / absent / empty /
unknown => render-only, no execution). That gate is intentionally open and auditable —
it is the thing protecting the user's machine from foreign ``.zolo`` content.

This module is the seam for the *proprietary* layer on top of that gate:
integrity / attestation of the executor and provenance of the code. The real
policy lives in the private ``zguard.display.terminal_trust`` package (binary
wheel via zGuard), mirroring the zLoader ``loader_trust`` and zParser
``parser_trust`` shims. Without zGuard the seam is permissive (returns True) —
the open-core config gate remains the safe-by-default boundary and the feature
stays fully functional. Installing zGuard seals this seam (e.g. verifies the
gate has not been weakened by a fork) with no call-site changes.

Anti-fork reality (no false comfort)
------------------------------------
A malicious fork that strips zGuard entirely cannot be stopped by code alone;
the defense there is signed / authentic distribution plus zGuard being a
required, unforgeable attestation component. This seam *detects* tampering when
genuine zGuard is present — it does not pretend to prevent hostile
redistribution of open-core source.

Enforcement contract
--------------------
``verify_terminal_exec(code, language, policy, zos=None, logger=None) -> bool``
    Returns True when execution is allowed. The zGuard implementation raises
    ``TerminalTrustError`` when policy / attestation denies; that exception must
    propagate to the caller (never be swallowed or re-wrapped).
"""


class TerminalTrustError(Exception):
    """Raised by the zGuard terminal-trust policy when execution is denied.

    Propagated unwrapped so a denial is always visible to the caller. In
    open-core (no zGuard) this is never raised — the seam is permissive and the
    fail-closed ``ZTERMINAL_MODE`` config gate in ``terminal_executor`` is the
    boundary.
    """


try:
    # Sealed attestation / integrity policy when zGuard is installed.
    from zguard.display.terminal_trust import verify_terminal_exec  # noqa: F401
except ImportError:
    def verify_terminal_exec(_code, _language, _policy, _zos=None, _logger=None) -> bool:  # noqa: D401
        """Fallback: no zGuard → no attestation (open-core permissive seam).

        The fail-closed ``ZTERMINAL_MODE`` gate in ``terminal_executor`` is the
        open-core boundary; this seam only adds zGuard-sealed attestation.
        """
        return True


__all__ = ["verify_terminal_exec", "TerminalTrustError"]
