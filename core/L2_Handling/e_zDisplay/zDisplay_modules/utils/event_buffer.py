# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/utils/event_buffer.py

"""
Event Buffer for zBifrost Mode
===============================

Provides event buffering for Bifrost mode, allowing events to be captured
instead of broadcast immediately. This solves async event loop issues when
zDispatch runs in a worker thread.

Extracted from zDisplay.py to reduce file size and improve separation of concerns.
"""

from zOS import Dict, Any, List


class EventBuffer:
    """Event buffering for zBifrost mode.
    
    Captures display events in a buffer instead of broadcasting immediately.
    Events are collected and returned as part of command results.
    """
    
    def __init__(self) -> None:
        """Initialize empty event buffer."""
        self._buffer: List[Dict[str, Any]] = []
    
    def buffer_event(self, event_data: Dict[str, Any]) -> None:
        """Buffer a display event for later collection.
        
        Args:
            event_data: Event dictionary to buffer
        """
        self._buffer.append(event_data)
    
    def collect_buffered_events(self) -> List[Dict[str, Any]]:
        """Collect all buffered events and clear the buffer.
        
        Returns:
            List of all buffered events since last collection
        """
        events = self._buffer.copy()
        self._buffer.clear()
        return events
    
    def clear_event_buffer(self) -> None:
        """Clear the event buffer without returning events."""
        self._buffer.clear()
