# zOS/core/L1_Foundation/b_zComm/zComm_modules/comm_websocket_input.py
"""
WebSocket Input Coordination Primitives for zComm.

Provides async input request/response coordination for WebSocket clients.
Used by zDisplay and other subsystems that need to collect user input from
GUI clients.

Architecture:
    Layer: L1_Foundation (zComm)
    Used by: L2_Handling (zDisplay for read_string, read_password, etc.)
    Pattern: Request/Response with asyncio.Future coordination
"""

from zOS import Any, Dict, Optional, asyncio, uuid


class WebSocketInputHandler:
    """
    Async input coordination for WebSocket clients.
    
    Manages request/response cycle for user input from GUI clients:
    1. Create input request with unique ID
    2. Return Future that will be resolved when client responds
    3. Client sends response with request ID
    4. Resolve Future with user's input value
    
    Architecture:
        - Thread-safe Future management
        - Request ID generation and tracking
        - Graceful handling of missing event loop
    
    Usage:
        # From zDisplay primitives
        input_handler = zos.comm.websocket_input
        future = input_handler.create_request("string", "Enter name:")
        if future:
            name = await future  # Resolved when client responds
    """

    def __init__(self, zos: Any) -> None:
        """Initialize WebSocketInputHandler with zOS instance.
        
        Args:
            zos: Parent zOS instance (provides logger)
        """
        self.zos = zos
        self.logger = zos.logger if hasattr(zos, 'logger') else None
        self._response_futures: Dict[str, asyncio.Future] = {}

    def generate_request_id(self) -> str:
        """Generate unique request ID for input requests.
        
        Returns:
            str: UUID string for tracking request/response pairs
        """
        return str(uuid.uuid4())

    def create_request(self, request_type: str, prompt: str, **kwargs) -> Optional[asyncio.Future]:  # pylint: disable=unused-argument
        """Create async input request and return Future.
        
        Creates a Future that will be resolved when the GUI client responds
        with user input. The Future is stored in _response_futures dict keyed
        by request_id.
        
        Args:
            request_type: Type of input (e.g., "string", "password", "bool", "range")
            prompt: Prompt text to display to user
            **kwargs: Additional request parameters (e.g., masked=True, min=0, max=100)
        
        Returns:
            Optional[asyncio.Future]: Future that resolves to user input,
                                      or None if event loop not available
        
        Example:
            future = handler.create_request("string", "Enter name:")
            if future:
                name = await future
        
        Notes:
            - Returns None if no event loop is running (terminal mode)
            - Future must be resolved by calling resolve_input()
            - Request ID is generated automatically
            - Parameters are stored for logging/debugging purposes
        """
        request_id = self.generate_request_id()

        try:
            # Create future for response
            try:
                loop = asyncio.get_running_loop()
                future = loop.create_future()
            except RuntimeError:
                # No running event loop - return None (terminal fallback)
                if self.logger:
                    self.logger.framework.debug(
                        f"[WebSocketInput] No event loop, cannot create {request_type} request"
                    )
                return None

            # Store future for later resolution
            self._response_futures[request_id] = future

            # Log request creation for debugging
            if self.logger:
                self.logger.framework.debug(
                    f"[WebSocketInput] Created {request_type} request: {request_id} - {prompt}"
                )

            return future

        except Exception as e:
            if self.logger:
                self.logger.error(f"[WebSocketInput] Failed to create request: {e}")
            return None

    def resolve_input(self, request_id: str, value: Any) -> bool:
        """Resolve pending input Future with user's response.
        
        Called by WebSocket message handler when client sends input response.
        
        Args:
            request_id: UUID of the original input request
            value: User's input value from GUI client
        
        Returns:
            bool: True if Future was resolved, False if request_id not found
        
        Example:
            # In WebSocket message handler
            if message['event'] == 'input_response':
                handler.resolve_input(message['requestId'], message['value'])
        
        Notes:
            - Removes Future from tracking dict after resolution
            - Logs warning if request_id not found (stale/duplicate response)
        """
        if self.logger:
            self.logger.framework.debug(
                f"[WebSocketInput] Resolving input: {request_id} = {value}"
            )

        if request_id in self._response_futures:
            future = self._response_futures.pop(request_id)

            if not future.done():
                future.set_result(value)
                if self.logger:
                    self.logger.framework.debug(
                        f"[WebSocketInput] Future resolved: {request_id}"
                    )
                return True
            else:
                if self.logger:
                    self.logger.warning(
                        f"[WebSocketInput] Future already done: {request_id}"
                    )
                return False
        else:
            if self.logger:
                self.logger.warning(
                    f"[WebSocketInput] No matching future for request: {request_id}"
                )
            return False

    def cancel_request(self, request_id: str) -> bool:
        """Cancel pending input request.
        
        Args:
            request_id: UUID of the request to cancel
        
        Returns:
            bool: True if request was cancelled, False if not found
        """
        if request_id in self._response_futures:
            future = self._response_futures.pop(request_id)
            if not future.done():
                future.cancel()
            return True
        return False

    def get_pending_requests(self) -> list:
        """Get list of pending request IDs.
        
        Returns:
            list: List of request IDs waiting for response
        """
        return list(self._response_futures.keys())

    def clear_pending_requests(self) -> None:
        """Cancel and clear all pending requests."""
        for request_id in list(self._response_futures.keys()):
            self.cancel_request(request_id)
