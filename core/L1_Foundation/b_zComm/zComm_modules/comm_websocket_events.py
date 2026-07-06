# zOS/core/L1_Foundation/b_zComm/zComm_modules/comm_websocket_events.py
"""
WebSocket Event Broadcasting Primitives for zComm.

Provides high-level event broadcasting API for subsystems (zDisplay, zAuth, etc.)
to send structured events to WebSocket clients.

Architecture:
    Layer: L1_Foundation (zComm)
    Used by: L2_Handling (zDisplay, zAuth, etc.)
    Uses: comm_websocket.WebSocketServer for low-level broadcast

This module separates concerns:
- WebSocketServer: Low-level connection/broadcast infrastructure
- WebSocketEvents: High-level event formatting and routing
"""

from zOS import Any, Dict, Optional, asyncio, json, time


class WebSocketEvents:
    """
    High-level WebSocket event broadcasting API.
    
    Provides structured event sending for subsystems that need to communicate
    with WebSocket clients (e.g., zDisplay sending UI events, zAuth sending
    auth status updates).
    
    Architecture:
        - Formats events with consistent structure
        - Handles JSON serialization
        - Manages asyncio coordination (thread-safe)
        - Delegates to WebSocketServer for actual broadcast
    
    Usage:
        # From zDisplay or other subsystems
        events = zos.comm.websocket_events
        events.send_event("header", {"label": "Title", "color": "BLUE"})
        events.buffer_event(event_data)  # For capture pattern
    """

    def __init__(self, zos: Any) -> None:
        """Initialize WebSocketEvents with zOS instance.
        
        Args:
            zos: Parent zOS instance (provides logger, websocket server access)
        """
        self.zos = zos
        self.logger = zos.logger if hasattr(zos, 'logger') else None
        self._event_buffer = []  # For capture pattern (zWalker compatibility)

    def send_event(self, event_data: Dict[str, Any]) -> bool:
        """Send structured event to all connected WebSocket clients.
        
        Thread-safe method that handles asyncio coordination automatically.
        
        Args:
            event_data: Event dictionary to broadcast (will be JSON-serialized)
        
        Returns:
            bool: True if broadcast succeeded, False otherwise
        
        Example:
            events.send_event({
                "displayEvent": "header",
                "data": {"label": "Title", "color": "BLUE"},
                "timestamp": time.time()
            })
        
        Notes:
            - Automatically handles JSON serialization
            - Thread-safe (uses asyncio.run_coroutine_threadsafe)
            - Gracefully handles missing event loop (returns False)
        """
        # Check if WebSocket server is available
        if not hasattr(self.zos, 'comm') or not hasattr(self.zos.comm, 'websocket'):
            return False

        websocket_server = self.zos.comm.websocket
        if not websocket_server or not hasattr(websocket_server, 'broadcast'):
            return False

        try:
            # Serialize event to JSON
            message = json.dumps(event_data)

            # Get running event loop and schedule broadcast
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(
                    websocket_server.broadcast(message),
                    loop
                )
                return True
            except RuntimeError:
                # No running event loop - can't broadcast
                if self.logger:
                    self.logger.framework.debug(
                        "[WebSocketEvents] No event loop running, skipping broadcast"
                    )
                return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"[WebSocketEvents] Broadcast failed: {e}")
            return False

    def buffer_event(self, event_data: Dict[str, Any]) -> None:
        """Buffer event for later collection (capture pattern).
        
        Used by zWalker and other subsystems that need to collect events
        for batch processing or result aggregation.
        
        Args:
            event_data: Event dictionary to buffer
        
        Notes:
            - Events are stored in memory buffer
            - Call get_buffered_events() to retrieve and clear
            - Used for zWalker command result capture
        """
        self._event_buffer.append(event_data)

    def get_buffered_events(self) -> list:
        """Retrieve and clear buffered events.
        
        Returns:
            list: All buffered events (buffer is cleared after retrieval)
        """
        events = self._event_buffer.copy()
        self._event_buffer.clear()
        return events

    def clear_buffer(self) -> None:
        """Clear event buffer without retrieving events."""
        self._event_buffer.clear()

    def send_display_event(self, event_name: str, data: Dict[str, Any],
                          special_events: Optional[list] = None) -> bool:
        """Send display event with proper formatting.
        
        Convenience method for zDisplay that handles event structure formatting.
        
        Args:
            event_name: Name of display event (e.g., "header", "error")
            data: Event data dictionary
            special_events: List of special event names that need top-level 'event' key
        
        Returns:
            bool: True if event was sent/buffered successfully
        
        Example:
            events.send_display_event("header", {"label": "Title", "color": "BLUE"})
        """
        special_events = special_events or ['zDash', 'zMenu', 'zDialog']

        # Format event based on type
        if event_name in special_events:
            # Special events need top-level 'event' key for frontend routing
            event_data = {
                "event": event_name,
                **data
            }
        else:
            # Regular display events use nested structure
            event_data = {
                "displayEvent": event_name,
                "data": data,
                "timestamp": time.time()
            }

        # Buffer for capture pattern (zWalker compatibility)
        self.buffer_event(event_data)

        # Also broadcast immediately
        return self.send_event(event_data)
