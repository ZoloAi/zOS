# zOS/core/L3_Abstraction/n_zLoom/__init__.py
"""
zLoom subsystem — the dynamic-grammar layer (Layer 3), sibling of zData.

Public surface: two facades, both attached at boot —
  * ``zLoom`` → ``zos.zloom``  (weave: spool / dye / pattern / shuttle / knot)
  * ``zGate`` → ``zos.zgate``  (decide: one predicate engine for every yes/no gate)

zGate is folded in here (not a separate subsystem) because it is pure composition
over zLoom-resolved values — zLoom weaves, zGate decides. See zLoom.py / zGate.py
and memos/Development/ZLOOM_SUBSYSTEM_SSOT.notes.md + ZGATE_CONSOLIDATION_PLAN.notes.md.
"""

from .zLoom import zLoom
from .zGate import zGate, GateLoweringError

__all__ = [
    "zLoom",
    "zGate",
    "GateLoweringError",
]
