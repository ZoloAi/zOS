# zOS/core/L3_Abstraction/m_zData/zData_modules/lifecycle_manager.py
"""
LifecycleManager - Connection state and cleanup management.

Handles all lifecycle operations including:
- Connection state tracking
- Graceful disconnection
- Resource cleanup
- Connection health monitoring

Architecture:
    - Manages adapter disconnection
    - Tracks connection state
    - Provides connection info for monitoring
"""

from zOS import Any, Dict, Optional

from .shared.data_keys import SCHEMA_KEY_META

# Module Constants
_LOG_PREFIX = "[LifecycleManager]"
_LOG_DISCONNECTED = "Disconnected from backend"
_LOG_DISCONNECT_ERROR = "Error during disconnect: %s"


class LifecycleManager:
    """
    Manages connection lifecycle and cleanup.
    
    Responsibilities:
        - Disconnect from backends gracefully
        - Track connection state
        - Provide connection health info
    
    Attributes:
        logger: Logger instance
    """

    def __init__(self, logger: Any) -> None:
        """
        Initialize LifecycleManager.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger

    def disconnect(self, adapter: Optional[Any]) -> None:
        """
        Disconnect from backend gracefully.
        
        Args:
            adapter: Backend adapter instance (can be None)
        """
        if adapter is None:
            return

        try:
            if hasattr(adapter, 'disconnect'):
                adapter.disconnect()
                self.logger.debug(_LOG_DISCONNECTED)
        except Exception as e:  # pylint: disable=broad-except
            self.logger.error(_LOG_DISCONNECT_ERROR, e, exc_info=True)

    def is_connected(self, adapter: Optional[Any], connected_flag: bool) -> bool:
        """
        Check if adapter is connected.
        
        Args:
            adapter: Backend adapter instance
            connected_flag: Connection state flag
            
        Returns:
            True if adapter is connected, False otherwise
        """
        return connected_flag and adapter is not None

    def get_connection_info(
        self,
        schema: Optional[Dict[str, Any]],
        adapter: Optional[Any],
        connected: bool
    ) -> Dict[str, Any]:
        """
        Get connection information for monitoring.
        
        Args:
            schema: Schema dictionary
            adapter: Backend adapter instance
            connected: Connection state flag
            
        Returns:
            Dict with connection details (backend, path, label, connected)
        """
        if not schema or not adapter:
            return {
                "backend": "none",
                "path": "N/A",
                "label": "N/A",
                "connected": False
            }

        meta = schema.get(SCHEMA_KEY_META, {})
        return {
            "backend": meta.get("Data_Type", "unknown"),
            "path": meta.get("Data_Path", "N/A"),
            "label": meta.get("Data_Label", "data"),
            "connected": connected
        }
