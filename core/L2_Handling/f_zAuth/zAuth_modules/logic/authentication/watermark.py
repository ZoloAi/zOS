"""
watermark shim — public zOS repo.

The trust watermark (zOS License 3.2) is decided + emitted by the private
``zguard.auth.watermark`` package (binary wheel via zGuard). This re-exports the
verdict + renderers so the engine's render path is unchanged. Without zGuard
there is no sealed runtime to enforce the mark, so the public fallback emits
nothing (the anonymous open-core path): no mark, treated as unmarked.
"""

try:
    from zguard.auth.watermark import (  # noqa: F401
        is_registered, watermark_html, watermark_banner,
    )
except ImportError:
    def is_registered(_zos):
        """Fallback: no zGuard → nothing to enforce; treat as unmarked."""
        return True

    def watermark_html(_zos):
        """Fallback: no sealed runtime → no served-page mark."""
        return ""

    def watermark_banner(_zos):
        """Fallback: no sealed runtime → no CLI banner mark."""
        return ""

__all__ = ["is_registered", "watermark_html", "watermark_banner"]
