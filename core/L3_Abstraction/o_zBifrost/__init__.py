# zOS/core/L3_Abstraction/o_zBifrost/__init__.py
"""
zBifrost shim — public zOS repo.

Source lives in the private zguard.bifrost package (binary wheel via zGuard).
This file re-exports the public API so all existing zOS imports remain unchanged.

Public users (no zGuard): a clear ZGuardRequired error is raised on first use.
"""


__version__ = "1.0.0"
try:
    from zguard.bifrost import zBifrost  # noqa: F401
    _ZGUARD_AVAILABLE = True
except ImportError:
    _ZGUARD_AVAILABLE = False

    class zBifrost:  # noqa: N801
        """Placeholder raised when zGuard is not installed."""
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "zBifrost runtime unavailable (Python ABI mismatch or missing zguard).\n"
                "Fix: z patch\n"
                "Docs: http://127.0.0.1:9090/zStack/zOS"
            )

__all__ = ['zBifrost']
