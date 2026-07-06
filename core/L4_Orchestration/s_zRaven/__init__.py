# zOS/core/L4_Orchestration/s_zRaven/__init__.py
"""
zRaven — Automated Test Subsystem

Layer: 4r (Orchestration)
Depends on: zWalker (4p), zServer (4q), zBifrost (L3)
"""

from .zRaven import zRaven

__all__ = ["zRaven"]

SUBSYSTEM_NAME    = "zRaven"
SUBSYSTEM_LAYER   = 4
SUBSYSTEM_VERSION = "2.0.0"
