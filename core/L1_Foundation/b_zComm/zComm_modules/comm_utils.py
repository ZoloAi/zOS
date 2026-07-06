# zOS/core/L1_Foundation/b_zComm/zComm_modules/comm_utils.py
"""
Network utility functions for zComm subsystem.

Provides network-level utilities for port checking, availability testing,
and other low-level network operations needed by zComm services.
"""

from zOS import Any, socket
from .comm_constants import PORT_MIN, PORT_MAX, DEFAULT_HOST, DEFAULT_TIMEOUT_SECONDS

# Module Constants

# Logging
_LOG_PREFIX = "[NetworkUtils]"

# Error Messages
_ERROR_INVALID_PORT = "Port must be between {min} and {max}, got: {port}"
_ERROR_PORT_CHECK_FAILED = "Failed to check port {port}"


class NetworkUtils:
    """
    Network utility functions for zComm subsystem.
    
    Provides low-level network operations including port availability
    checking, which is essential for service management and server initialization.
    """

    def __init__(self, logger: Any) -> None:
        """
        Initialize network utilities.
        
        Args:
            logger: Logger instance for debug/error output
        """
        self.logger = logger

    def is_port_open(self, port: int, host: str = DEFAULT_HOST) -> bool:
        """
        Low-level TCP probe: True if something is listening on host:port.

        SSOT for "is a port in use" across zComm (used by check_port and by
        service managers like PostgreSQL).

        Args:
            port: Port number to probe
            host: Host address (default: localhost)

        Returns:
            bool: True if a connection succeeds (port in use), False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(DEFAULT_TIMEOUT_SECONDS)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0  # 0 means a listener accepted the connection
        except (socket.error, OSError) as e:
            self.logger.debug(f"{_LOG_PREFIX} {_ERROR_PORT_CHECK_FAILED.format(port=port)}: {e}")
            return False

    def check_port(self, port: int, host: str = DEFAULT_HOST) -> bool:
        """
        Check if a port is available for binding.
        
        Attempts to connect to the specified port. If connection fails,
        the port is considered available (nothing is listening on it).
        
        Args:
            port: Port number to check (1-65535)
            host: Host address to check (default: localhost)
            
        Returns:
            bool: True if port is available, False if in use
            
        Raises:
            ValueError: If port is outside valid range (1-65535)
            
        Example:
            >>> network_utils = NetworkUtils(logger)
            >>> if network_utils.check_port(8080):
            ...     print("Port 8080 is available")
        """
        # Validate port range
        if not isinstance(port, int) or port < PORT_MIN or port > PORT_MAX:
            error_msg = _ERROR_INVALID_PORT.format(
                min=PORT_MIN,
                max=PORT_MAX,
                port=port
            )
            self.logger.error(f"{_LOG_PREFIX} {error_msg}")
            raise ValueError(error_msg)

        self.logger.debug(f"{_LOG_PREFIX} Checking port availability: {port} on {host}")

        is_available = not self.is_port_open(port, host)
        self.logger.debug(
            f"{_LOG_PREFIX} Port {port} is {'available' if is_available else 'in use'}"
        )
        return is_available
