# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/chunk_bridge.py
"""Open bridge to the bifrost chunked-render contract.

The coordination keys + buffering semantics live in the private, compiled
`zguard.bifrost.chunk_contract`. Open zData/zDisplay code imports the three
entry points from here so the protocol details never appear in open source.

Fallback (zGuard absent): no-op stubs that degrade to plain non-chunked
behaviour. In practice the wizard engine already requires zGuard to run, so
this path is purely defensive.
"""
from __future__ import annotations

try:
    from zguard.bifrost.zBifrost_modules.chunk_contract import (  # noqa: F401
        chunking_active,
        live_read,
        capture,
    )
except ImportError:
    from contextlib import nullcontext as _nullcontext

    # Fallback stubs intentionally ignore their args (no chunking without zGuard).
    # pylint: disable=unused-argument
    def chunking_active(zos) -> bool:  # type: ignore[misc]
        return False

    def live_read(zos):  # type: ignore[misc]
        return _nullcontext()

    def capture(zos, payload, *, only_live: bool = False) -> bool:  # type: ignore[misc]
        return False

__all__ = ["chunking_active", "live_read", "capture"]
