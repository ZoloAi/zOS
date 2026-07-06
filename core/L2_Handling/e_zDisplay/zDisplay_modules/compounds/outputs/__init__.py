"""
Output Event Modules for CompoundsOutputs
==========================================

This package contains specialized event modules for the CompoundsOutputs facade:
- display_event_data: CompoundData - structured list display with recursive rendering
- display_event_links: LinkEvents - link handling and navigation
- display_event_media: MediaEvents - media display operations

These modules handle compound output operations built on top of c_basic/BasicOutputs.
"""

from .display_event_data import CompoundData
from .display_event_links import LinkEvents
from .display_event_media import MediaEvents

__all__ = [
    'CompoundData',
    'LinkEvents',
    'MediaEvents',
]
