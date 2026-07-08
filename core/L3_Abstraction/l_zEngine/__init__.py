# zOS/core/L3_Abstraction/l_zEngine/__init__.py
"""
zEngine facade — public zOS repo.

The engine that runs any zolo block (the walk) and its `{zWizard:}` event live in
the private zguard.zengine package (binary wheel via zGuard). This file re-exports
the public API so all existing zOS imports resolve unchanged.

What this facade surfaces:
  • zEngine        — the universal walk/event runtime (the zWizard event rides it)
  • zForce         — the typed return of every zStride/zWave + its SSOT classifier
                     (sense_force). Consumed by CORE dispatch (the `!` modifier and
                     organizational expansion), not just wizards.

Why a zForce FALLBACK lives here:
  zForce is pure Python and load-bearing for core dispatch on EVERY app. So when
  zGuard is absent (pure open-core install), we cannot simply raise — that would
  break the `!` modifier and org expansion. Instead we provide a pure-Python
  MIRROR of the classifier below. The SSOT is zguard.zengine.zforce; this mirror
  must track it. zEngine itself (the wizard runtime) still raises ZGuardRequired,
  because it has no public fallback.
"""

try:
    from zguard.zengine import (  # noqa: F401
        zEngine,
        zForce,
        sense_force,
        OUTCOME_VOID,
        OUTCOME_OK,
        OUTCOME_FAIL,
        VECTOR_NONE,
        VEC_ZBACK,
        VEC_EXIT,
        VEC_STOP,
        VEC_NAVIGATE,
        STR_VECTORS,
        DICT_VECTOR_KEYS,
    )
    from zguard.zengine.zengine_modules import (  # noqa: F401
        SUBSYSTEM_NAME,
        SUBSYSTEM_COLOR,
        NAVIGATION_SIGNALS,
    )
    _ZGUARD_AVAILABLE = True
except ImportError:
    _ZGUARD_AVAILABLE = False

    class zEngine:  # noqa: N801
        """Placeholder raised when zGuard is not installed."""
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "zEngine runtime unavailable (Python ABI mismatch or missing zguard).\n"
                "Fix: z patch\n"
                "Docs: http://127.0.0.1:9090/zStack/zOS"
            )

    SUBSYSTEM_NAME = "zEngine"
    SUBSYSTEM_COLOR = "white"
    NAVIGATION_SIGNALS: list = []

    # ── zForce pure-Python FALLBACK MIRROR ────────────────────────────────────
    # SSOT is zguard.zengine.zforce — keep this in sync. Present so core dispatch
    # (the `!` modifier + org expansion) still classifies returns without zGuard.
    from dataclasses import dataclass
    from typing import Any

    OUTCOME_VOID: str = "void"
    OUTCOME_OK: str = "ok"
    OUTCOME_FAIL: str = "fail"
    VECTOR_NONE: str = ""
    VEC_ZBACK: str = "zBack"
    VEC_EXIT: str = "exit"
    VEC_STOP: str = "stop"
    VEC_NAVIGATE: str = "navigate"
    STR_VECTORS: tuple = (VEC_ZBACK, VEC_EXIT, VEC_STOP, VEC_NAVIGATE)
    DICT_VECTOR_KEYS: tuple = ("zLink", "zDelta", "zCrumb")

    @dataclass(frozen=True)
    class zForce:  # noqa: N801
        outcome: str
        vector: str
        mass: Any = None

        @property
        def is_void(self) -> bool:
            return self.outcome == OUTCOME_VOID

        @property
        def is_ok(self) -> bool:
            return self.outcome == OUTCOME_OK

        @property
        def is_fail(self) -> bool:
            return self.outcome == OUTCOME_FAIL

        @property
        def proceeds(self) -> bool:
            return self.outcome != OUTCOME_FAIL

        @property
        def has_vector(self) -> bool:
            return self.vector != VECTOR_NONE

        @property
        def is_exception(self) -> bool:
            return isinstance(self.mass, BaseException)

    def _sense_vector(raw: Any) -> str:
        if isinstance(raw, str) and raw in STR_VECTORS:
            return raw
        if isinstance(raw, dict):
            for key in DICT_VECTOR_KEYS:
                if key in raw:
                    return key
        return VECTOR_NONE

    def sense_force(raw: Any) -> "zForce":
        if isinstance(raw, BaseException):
            return zForce(OUTCOME_FAIL, VECTOR_NONE, mass=raw)
        vector = _sense_vector(raw)
        if raw is False:
            outcome = OUTCOME_FAIL
        elif raw is None:
            outcome = OUTCOME_VOID
        else:
            outcome = OUTCOME_OK
        return zForce(outcome, vector, mass=raw)

__all__ = [
    "zEngine",
    "SUBSYSTEM_NAME",
    "SUBSYSTEM_COLOR",
    "NAVIGATION_SIGNALS",
    "zForce",
    "sense_force",
    "OUTCOME_VOID",
    "OUTCOME_OK",
    "OUTCOME_FAIL",
    "VECTOR_NONE",
    "VEC_ZBACK",
    "VEC_EXIT",
    "VEC_STOP",
    "VEC_NAVIGATE",
    "STR_VECTORS",
    "DICT_VECTOR_KEYS",
]
