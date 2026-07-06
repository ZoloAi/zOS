# zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/embed/embed_trust.py

"""
zEmbed trust gate — public zOS repo shim.

``zEmbed`` renders foreign content (an ``<iframe>``) in the visitor's browser.
The open-core boundary is the fail-closed allow-list in ``embed_policy`` —
unknown providers are denied under the safe default and degrade to a plain link,
never an iframe. That policy is intentionally open and auditable.

This module is the seam for the *proprietary* layer on top of that policy:
attestation that the allow-list / sandbox envelope has not been weakened, and
(for hosted / multi-tenant deployments) per-app provider entitlements. The real
policy lives in the private ``zguard.display.embed_trust`` package (binary wheel
via zGuard), mirroring ``display.terminal_trust`` and the zLoader / zParser trust
shims. Without zGuard the seam is permissive (returns True) — the open-core
allow-list remains the safe-by-default boundary and the feature stays functional.
Installing zGuard seals this seam with no call-site changes.

Enforcement contract
--------------------
``verify_embed(url, provider, mode, zos=None, logger=None) -> bool``
    Returns True when the embed is allowed. The zGuard implementation raises
    ``EmbedTrustError`` when policy / attestation denies; that exception must
    propagate to the caller (never be swallowed or re-wrapped).
"""


class EmbedTrustError(Exception):
    """Raised by the zGuard embed-trust policy when an embed is denied.

    Propagated unwrapped so a denial is always visible. In open-core (no zGuard)
    this is never raised — the fail-closed allow-list in ``embed_policy`` is the
    boundary and this seam is permissive.
    """


try:
    # Sealed attestation / entitlement policy when zGuard is installed.
    from zguard.display.embed_trust import verify_embed  # noqa: F401
except ImportError:
    def verify_embed(_url, _provider, _mode, _zos=None, _logger=None) -> bool:  # noqa: D401
        """Fallback: no zGuard → no attestation (open-core permissive seam).

        The fail-closed allow-list in ``embed_policy`` is the open-core boundary;
        this seam only adds zGuard-sealed attestation / per-app entitlements.
        """
        return True


__all__ = ["verify_embed", "EmbedTrustError"]
