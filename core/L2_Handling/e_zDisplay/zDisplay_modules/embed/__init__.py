# zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/embed/__init__.py

"""zEmbed policy package — server-side trust boundary for the embed event.

embed_policy : provider normalization + allow-list + sandbox-envelope (SSOT).
embed_trust  : zGuard attestation seam (permissive in open-core).
"""

from .embed_policy import (
    resolve_embed,
    EMBED_MODE_OFF,
    EMBED_MODE_SAFE,
    EMBED_MODE_TRUST,
    EMBED_MODE_DEFAULT,
    DEFAULT_ASPECT,
)
from .embed_trust import verify_embed, EmbedTrustError

__all__ = [
    "resolve_embed",
    "verify_embed",
    "EmbedTrustError",
    "EMBED_MODE_OFF",
    "EMBED_MODE_SAFE",
    "EMBED_MODE_TRUST",
    "EMBED_MODE_DEFAULT",
    "DEFAULT_ASPECT",
]
