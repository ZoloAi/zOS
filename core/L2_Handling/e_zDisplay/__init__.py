# zOS/core/L2_Core/c_zDisplay/__init__.py

"""
zDisplay — Layer 1 UI Subsystem
================================

The primary display/rendering interface for zOS. Mode is resolved once at
initialization; zDisplay operates exclusively in that mode for the session.

Usage:
    zos.display.error("Connection failed")
    zos.display.header("Settings", color="CYAN")
    zos.display.zTable("Users", columns, rows)
    name = zos.display.read_string("Enter name:")

Architecture:
    zDisplay (zDisplay.py)
        ├─► Inherits from zDisplayDelegates (25 convenience methods)
        ├─► Owns handle() — unified event router
        ├─► Owns zPrimitives — exclusive I/O layer (mode flag set at init)
        └─► Owns zEvents — orchestrator for 10 event packages

    Internal modules (zDisplay_modules/):
        api/        Convenience methods (error, header, list, etc.)
        basic/      Core event implementations (output, signals, input)
        compounds/  Complex widgets (selection, media, links)
        advanced/   Markdown, progress bars, spinners, zTable
        system/     System UI (menu, dialog, session, declare)
        io/         Terminal syscalls (zCLI) OR object prep + delegation (Bifrost)
        utils/      Pure utilities (no I/O)

Mode Support (Exclusive):
    - zCLI (Terminal): zDisplay IS the renderer (direct print/input/getpass)
    - zBifrost (GUI): zDisplay is the producer (preps objects, delegates to zComm)
    
    Mode flag (_is_bifrost) is computed once in __init__() from session config.

Initialization:
    Automatically initialized by zOS.__init__():
        self.display = zDisplay(self)
        # Reads zMode from session → sets _is_bifrost flag

Dependencies:
    - zConfig (session dict, logger)
    - zComm (WebSocket transport for Bifrost mode delegation)
"""

from .zDisplay import zDisplay
from .zDisplay_modules.display_constants import *

__all__ = ['zDisplay']
