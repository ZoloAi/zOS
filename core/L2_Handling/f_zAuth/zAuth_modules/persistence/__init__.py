"""
Persistence Module — zOwnership: instance-owner identity at rest

Stores the zOS/zMachine INSTANCE OWNER in a single config file
(zConfig.identity.zolo), git-like: "this machine is owned/signed-in as X".
zOwnership is SEPARATE from the runtime ("flask-like") session — it is read on
demand and must never be poured into a session. No SQLite store.

Architecture:
    - zownership_store: read/write/clear the local zOwnership identity file
"""

from .zownership_store import (
    zownership_path,
    save_zownership,
    load_zownership,
    clear_zownership,
)

__all__ = [
    'zownership_path',
    'save_zownership',
    'load_zownership',
    'clear_zownership',
]
