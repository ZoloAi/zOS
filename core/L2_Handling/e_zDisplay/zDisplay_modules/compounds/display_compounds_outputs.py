# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/d_compounds/display_compounds_outputs.py

"""
Compound Output Operations - Structured Display Facade
=======================================================

This module provides the compound outputs facade for the zDisplay subsystem.
It delegates to specialized compound output event modules.

Architecture:
    - Facade: CompoundsOutputs (this file) - unified output interface
    - Events: display_event_*.py - event implementations in outputs/ folder
    - Helpers: outputs/*.py - individual output helper modules

⚠️ TIER DISTINCTION ⚠️
- b_primitives: Raw I/O (raw, line, block)
- c_basic: Formatted output (header, text, signals)
- d_compounds: Structured display (lists, data, media, links)

Compound Output Operations:
    - list(): Structured lists with recursive rendering
    - (Future: media, links, etc.)

Dual-Mode I/O:
    - Terminal Mode (zCLI): Formatted text output (synchronous)
    - Bifrost Mode: WebSocket events via zComm (asynchronous)
    - Terminal output ALWAYS happens (immediate feedback)
    - WebSocket output CONDITIONAL (when in Bifrost mode)

Dependencies:
    - display_event_data: CompoundData implementation
    - display_event_links: Link handling
    - display_event_media: Media display
    - c_basic: BasicOutputs (foundation)
    - b_primitives: PrimitivesOutputs (I/O)
"""

from zOS import Any

# Import compound output event modules
from .outputs.display_event_data import CompoundData
from .outputs.display_event_links import LinkEvents
from .outputs.display_event_media import MediaEvents


class CompoundsOutputs:
    """Compound outputs facade - delegates to specialized event modules.
    
    Architecture:
        This class uses the Facade pattern to provide a unified interface to
        all compound output operations. Each operation is implemented in its own
        event module for scalability and management.
        
        Compound Output Events:
            - list() → CompoundData
            - (Future: media, links, etc. → respective event modules)
    """

    # Type hints for instance attributes
    display: Any  # Parent zDisplay instance

    # Event module instances
    _compound_data: CompoundData
    _link_events: LinkEvents
    _media_events: MediaEvents

    def __init__(self, display_instance: Any) -> None:
        """Initialize CompoundsOutputs facade with event modules.
        
        Args:
            display_instance: Parent zDisplay instance (provides mode, zcli access)
        """
        self.display = display_instance

        # Instantiate event modules
        self._compound_data = CompoundData(display_instance)
        self._link_events = LinkEvents(display_instance)
        self._media_events = MediaEvents(display_instance)

    # Compound Output Operations - Delegate to event modules

    def list(self, items, style: str = "bullet", indent: int = 0, **kwargs):
        """Display structured list with recursive rendering.
        
        Delegates to: display_event_data.CompoundData
        """
        return self._compound_data.list(items, style, indent, **kwargs)

    # Future: Add media, links, and other compound output methods
    # def media(self, ...): return self._media_events.media(...)
    # def link(self, ...): return self._link_events.link(...)
