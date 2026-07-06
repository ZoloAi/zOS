# zOS/core/L1_Foundation/b_zComm/zComm.py
"""
Communication & Service Management Subsystem for zOS.

This module provides low-level communication infrastructure for zOS:
- HTTP client (GET, POST, PUT, PATCH, DELETE)
- Service management (PostgreSQL, Redis, MongoDB)  
- Network utilities (port checking)

zComm is an L1_Foundation subsystem (lowest infrastructure tier), initialized
before zDisplay, providing the communication backbone for the entire framework.

Architecture:
    zComm follows the Facade pattern, providing a unified interface to multiple
    communication subsystems while delegating implementation to specialized managers:
    
    - HTTPClient: Synchronous HTTP request handling
    - ServiceManager: Local database/cache service management
    - NetworkUtils: Port checking and network utilities

Layer 0 Design:
    As a Layer 0 subsystem, zComm has special considerations:
    - No zDisplay dependency (uses print_ready_message for console output)
    - Initialized before user-facing subsystems
    - Provides infrastructure for higher-layer subsystems

Delegation Pattern:
    All methods are thin wrappers that delegate to specialized managers:
    - start_service/stop_service: → ServiceManager
    - check_port: → NetworkUtils
    - http_post/http_get: → HTTPClient
    
    This separation of concerns allows each manager to be tested and evolved
    independently while maintaining a stable public API.

Auto-Initialization:
    zComm automatically:
    1. Validates zOS instance (session, logger required)
    2. Creates all managers
    3. Prints ready message (before zDisplay available)
    4. Logs ready state

Public API (Network Primitives):
    Service Management:
        - start_service(): Start local service (postgresql, redis, etc.)
        - stop_service(): Stop local service
        - restart_service(): Restart local service
        - service_status(): Get service status
        - get_service_connection_info(): Get connection details
    
    Health Checks:
        - server_health_check(): HTTP server status
        - health_check_all(): Combined health status
    
    Network Utilities:
        - check_port(): Port availability check
    
    HTTP Client (Outgoing Requests):
        - http_get(), http_post(), http_put(), http_patch(), http_delete()
    
    WebSocket Primitives (Low-Level):
        - websocket.start(), websocket.send(), websocket.broadcast()
    
    WebSocket Communication (High-Level):
        - websocket_events.send_event(): Broadcast structured events
        - websocket_events.send_display_event(): Send display-specific events
        - websocket_input.create_request(): Create async input request
        - websocket_input.resolve_input(): Resolve input response

Note:
    HTTP Server orchestration (zServer) is now a separate Layer 1 subsystem.
    Access via z.server, not z.comm.

Usage:
    ```python
    from zOS.L1_Foundation.b_zComm import zComm
    
    # Initialize (done automatically by zOS)
    comm = zComm(zos_instance)
    
    # Start services
    comm.start_service("postgresql")
    
    # Check health
    health = comm.health_check_all()
    
    # Make HTTP requests
    response = comm.http_post("https://api.example.com", data={...})
    ```

Note:
    For WebSocket orchestration (Terminal↔Web bridge), see zBifrost (Layer 2).
    zBifrost coordinates display/auth/data subsystems over WebSocket infrastructure.

See Also:
    - zComm_modules/comm_services.py: ServiceManager implementation
    - zComm_modules/comm_http.py: HTTPClient implementation
    - Documentation/zComm_GUIDE.md: Complete usage guide
    - zBifrost (Layer 2): WebSocket orchestration for Terminal↔Web
"""

from zOS import Any, Dict, Optional
from zSys.Utils import print_ready_message, validate_zos_instance
from .zComm_modules import ServiceManager, HTTPClient, NetworkUtils, WebSocketServer
from .zComm_modules.comm_websocket_events import WebSocketEvents
from .zComm_modules.comm_websocket_input import WebSocketInputHandler

# ═══════════════════════════════════════════════════════════
# Module Constants
# ═══════════════════════════════════════════════════════════

# Color Constants
COLOR_ZCOMM = "ZCOMM"

# Ready Messages
MSG_READY = "zComm Ready"
MSG_SUBSYSTEM_READY = "Communication subsystem ready"

# Service Log Messages
LOG_PREFIX_SERVICE_START = "Starting service: %s"
LOG_PREFIX_SERVICE_START_PARAMS = "Service start parameters: %s"
LOG_MSG_SERVICE_STARTED = "Service '%s' started successfully"
LOG_MSG_SERVICE_START_FAILED = "Failed to start service '%s'"

LOG_PREFIX_SERVICE_STOP = "Stopping service: %s"
LOG_MSG_SERVICE_STOPPED = "Service '%s' stopped successfully"
LOG_MSG_SERVICE_STOP_FAILED = "Failed to stop service '%s'"

LOG_PREFIX_SERVICE_RESTART = "Restarting service: %s"
LOG_MSG_SERVICE_RESTARTED = "Service '%s' restarted successfully"
LOG_MSG_SERVICE_RESTART_FAILED = "Failed to restart service '%s'"

LOG_PREFIX_SERVICE_STATUS = "Getting status for service: %s"
LOG_PREFIX_ALL_SERVICES_STATUS = "Getting status for all services"
LOG_MSG_SERVICE_STATUS = "Service '%s' status: %s"
LOG_MSG_ALL_SERVICES_STATUS = "All services status: %s"

LOG_PREFIX_SERVICE_CONN_INFO = "Getting connection info for service: %s"
LOG_MSG_SERVICE_CONN_INFO = "Service '%s' connection info: %s"

# Health Check Messages
HEALTH_KEY_RUNNING = "running"
HEALTH_KEY_ERROR = "error"
HEALTH_KEY_HTTP_SERVER = "http_server"

HEALTH_MSG_HTTP_NOT_AVAIL = "HTTP server not available"

# Note: HTTP server host/port defaults live in zConfig (config_http_server.DEFAULT_PORT);
# zComm reads them from zos.config rather than mirroring them here (SSOT).


# ═══════════════════════════════════════════════════════════
# zComm Class
# ═══════════════════════════════════════════════════════════

class zComm:
    """
    Communication & Service Management Facade for zOS.
    
    Provides unified interface to low-level communication infrastructure including
    HTTP client, service management, and network utilities. Delegates to specialized
    managers while maintaining a stable public API.
    
    Architecture:
        L1_Foundation subsystem providing communication infrastructure:
        - HTTPClient: Synchronous HTTP requests
        - ServiceManager: Local database/cache services (PostgreSQL, Redis, etc.)
        - NetworkUtils: Port checking and network utilities
    
    Auto-Initialization:
        On __init__:
        1. Validates zOS instance (session + logger required)
        2. Creates all managers
        3. Prints ready message (Layer 0, no zDisplay yet)
        4. Logs ready state
    
    Attributes:
        zos: zOS instance (dependency injection)
        session: Reference to zos.session (read-only from zComm perspective)
        logger: Reference to zos.logger
        mycolor: Color code for console output
        services: ServiceManager instance (public API)
        _http_client: HTTPClient instance (private, use methods)
        _network_utils: NetworkUtils instance (private, use methods)
    
    Public API Groups:
        - WebSocket: websocket (server primitives), websocket_events, websocket_input
        - Service Management: start_service, stop_service, restart_service, service_status, get_service_connection_info
        - Health Checks: server_health_check, health_check_all
        - Network: check_port
        - HTTP Client: http_get, http_post, http_put, http_patch, http_delete
        - Storage: storage (StorageClient: put/get/delete/exists/get_url)
    
    Example:
        ```python
        # Initialize (done automatically by zOS)
        comm = zComm(zos_instance)
        
        # Service management
        comm.start_service("postgresql")
        status = comm.service_status("postgresql")
        
        # HTTP
        response = comm.http_post("https://api.example.com", data={...})
        ```
    
    Note:
        For WebSocket orchestration, see zBifrost (Layer 2) which coordinates
        display/auth/data subsystems over WebSocket infrastructure.
    
    See Also:
        - ServiceManager: Service orchestration
        - HTTPClient: HTTP request handling
        - NetworkUtils: Network utilities
        - zBifrost: WebSocket bridge orchestrator (Layer 2)
    """

    # Type hints for instance attributes
    zos: Any  # zOS instance
    session: Dict[str, Any]
    logger: Any
    mycolor: str
    _http_client: HTTPClient
    _network_utils: NetworkUtils
    services: ServiceManager

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any) -> None:
        """
        Initialize zComm subsystem with automatic configuration and service setup.
        
        Validates zOS instance, creates all managers, and logs ready state.
        This is called automatically by zOS during initialization.
        
        Args:
            zos: zOS instance with session and logger attributes
        
        Raises:
            ValueError: If zos is None or missing required attributes (session, logger)
        
        Side Effects:
            - Creates HTTPClient, NetworkUtils, ServiceManager
            - Prints ready message to console
            - Logs initialization to logger
        
        Example:
            ```python
            # Done automatically by zOS
            comm = zComm(zos_instance)
            ```
        """
        # Validate zOS instance FIRST - session is always required
        validate_zos_instance(zos, "zComm")

        self.zos = zos
        self.logger = zos.logger
        self.mycolor = COLOR_ZCOMM

        # Initialize modular components
        self._http_client = HTTPClient(self.logger)
        self._network_utils = NetworkUtils(self.logger)
        self._websocket_server = WebSocketServer(self.logger, zos.config.websocket)
        self.services = ServiceManager(self.logger)

        # Initialize WebSocket communication primitives (high-level API)
        self.websocket_events = WebSocketEvents(zos)
        self.websocket_input = WebSocketInputHandler(zos)

        # Initialize storage client (Phase 1.3: Storage Manager)
        from .zComm_modules.comm_storage import StorageClient
        self.storage = StorageClient(zos)

        # Print ready banner in Development mode (deployment-aware)
        if self.logger.should_show_sysmsg():
            print_ready_message("zComm Ready", color=COLOR_ZCOMM)

        # Log ready at DEBUG level
        self.logger.framework.debug(MSG_SUBSYSTEM_READY)

    # ═══════════════════════════════════════════════════════════
    # HTTP Server Management (Optional Feature)
    # ═══════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════
    # WebSocket Server (Layer 0 Primitives)
    # ═══════════════════════════════════════════════════════════

    @property
    def websocket(self) -> WebSocketServer:
        """
        Access WebSocket server instance.
        
        Returns:
            WebSocketServer: WebSocket server primitives
            
        Example:
            ```python
            # Access WebSocket server
            ws = z.comm.websocket
            
            # Start server
            await ws.start(host="127.0.0.1", port=8765)
            
            # Broadcast message
            await ws.broadcast("Hello all clients!")
            ```
        """
        return self._websocket_server

    # ═══════════════════════════════════════════════════════════
    # Service Management - Delegated to ServiceManager
    # ═══════════════════════════════════════════════════════════

    def start_service(self, service_name: str, **kwargs: Any) -> bool:
        """
        Start a local service (PostgreSQL, Redis, MongoDB, etc.).
        
        Args:
            service_name: Service identifier ("postgresql", "redis", "mongodb")
            **kwargs: Service-specific start parameters
        
        Returns:
            bool: True if started successfully, False otherwise
        
        Example:
            ```python
            if comm.start_service("postgresql"):
                print("PostgreSQL started")
            ```
        """
        self.logger.info(LOG_PREFIX_SERVICE_START, service_name)
        self.logger.debug(LOG_PREFIX_SERVICE_START_PARAMS, kwargs)

        result = self.services.start(service_name, **kwargs)

        if result:
            self.logger.info(LOG_MSG_SERVICE_STARTED, service_name)
        else:
            self.logger.error(LOG_MSG_SERVICE_START_FAILED, service_name)

        return result

    def stop_service(self, service_name: str) -> bool:
        """
        Stop a running service.
        
        Args:
            service_name: Service identifier
        
        Returns:
            bool: True if stopped successfully, False otherwise
        
        Example:
            ```python
            comm.stop_service("postgresql")
            ```
        """
        self.logger.info(LOG_PREFIX_SERVICE_STOP, service_name)

        result = self.services.stop(service_name)

        if result:
            self.logger.info(LOG_MSG_SERVICE_STOPPED, service_name)
        else:
            self.logger.error(LOG_MSG_SERVICE_STOP_FAILED, service_name)

        return result

    def restart_service(self, service_name: str) -> bool:
        """
        Restart a service (stop then start).
        
        Args:
            service_name: Service identifier
        
        Returns:
            bool: True if restarted successfully, False otherwise
        
        Example:
            ```python
            comm.restart_service("postgresql")
            ```
        """
        self.logger.info(LOG_PREFIX_SERVICE_RESTART, service_name)

        result = self.services.restart(service_name)

        if result:
            self.logger.info(LOG_MSG_SERVICE_RESTARTED, service_name)
        else:
            self.logger.error(LOG_MSG_SERVICE_RESTART_FAILED, service_name)

        return result

    def service_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get service status.
        
        Args:
            service_name: Specific service (None for all services)
        
        Returns:
            Dict with status info ("running", "stopped", "unknown")
        
        Example:
            ```python
            status = comm.service_status("postgresql")
            # status = {"status": "running", "pid": 1234, ...}
            
            all_status = comm.service_status()
            # all_status = {"postgresql": {...}, "redis": {...}}
            ```
        """
        if service_name:
            self.logger.debug(LOG_PREFIX_SERVICE_STATUS, service_name)
        else:
            self.logger.debug(LOG_PREFIX_ALL_SERVICES_STATUS)

        status = self.services.status(service_name)

        if service_name:
            self.logger.debug(LOG_MSG_SERVICE_STATUS, service_name, status)
        else:
            self.logger.debug(LOG_MSG_ALL_SERVICES_STATUS, status)

        return status

    def get_service_connection_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Get connection information for a service.
        
        Args:
            service_name: Service identifier
        
        Returns:
            Dict with connection info (host, port, default_db, etc.) or None
        
        Example:
            ```python
            info = comm.get_service_connection_info("postgresql")
            # info = {"host": "localhost", "port": 5432, "default_db": "postgres"}
            ```
        """
        self.logger.debug(LOG_PREFIX_SERVICE_CONN_INFO, service_name)

        info = self.services.get_connection_info(service_name)

        self.logger.debug(LOG_MSG_SERVICE_CONN_INFO, service_name, info)

        return info

    # ═══════════════════════════════════════════════════════════
    # Health Checks
    # ═══════════════════════════════════════════════════════════

    def server_health_check(self) -> Dict[str, Any]:
        """
        Get HTTP server health status (if available via z.server).
        
        Note:
            HTTP server (zServer) is typically accessed via z.server.health_check().
            This method provides a convenience wrapper for accessing it via zComm.
        
        Returns:
            Dict with health status including running state, port, serve_path, etc.
            Returns error dict if HTTP server not available
        
        Example:
            ```python
            health = comm.server_health_check()
            # health = {
            #     "running": True,
            #     "port": 8080,
            #     "host": "127.0.0.1",
            #     "serve_path": "/path/to/static"
            # }
            ```
        """
        if self.zos and hasattr(self.zos, 'server') and self.zos.server:
            return self.zos.server.health_check()
        return {HEALTH_KEY_RUNNING: False, HEALTH_KEY_ERROR: HEALTH_MSG_HTTP_NOT_AVAIL}

    def health_check_all(self) -> Dict[str, Any]:
        """
        Get health status for all communication services.
        
        Returns:
            Dict with combined health status for HTTP server
        
        Example:
            ```python
            health = comm.health_check_all()
            # health = {
            #     "http_server": {"running": True, ...}
            # }
            ```
        """
        return {
            HEALTH_KEY_HTTP_SERVER: self.server_health_check()
        }

    # ═══════════════════════════════════════════════════════════
    # Network Utilities - Delegated to NetworkUtils
    # ═══════════════════════════════════════════════════════════

    def check_port(self, port: int) -> bool:
        """
        Check if a port is available.
        
        Args:
            port: Port number to check
        
        Returns:
            bool: True if port is available, False if in use
        
        Example:
            ```python
            if comm.check_port(5432):
                print("Port 5432 is available")
            ```
        """
        return self._network_utils.check_port(port)

    # ═══════════════════════════════════════════════════════════
    # HTTP Client - Delegated to HTTPClient
    # ═══════════════════════════════════════════════════════════

    def http_get(self, url: str, params: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Any:
        """
        Make HTTP GET request.
        
        Note:
            Pure communication layer - no auth logic. Applications should handle
            authentication separately (e.g., adding auth headers, using zAuth).
        
        Args:
            url: Target URL
            params: Query parameters (will be URL-encoded)
            headers: Optional custom headers
            timeout: Request timeout in seconds (default: 10)
        
        Returns:
            Response object or None on failure
        
        Example:
            ```python
            response = comm.http_get(
                "https://api.example.com/users",
                params={"limit": 10, "offset": 0}
            )
            ```
        """
        return self._http_client.get(url, params=params, headers=headers, timeout=timeout)

    def http_post(self, url: str, data: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Any:
        """
        Make HTTP POST request.
        
        Note:
            Pure communication layer - no auth logic. Applications should handle
            authentication separately (e.g., adding auth headers, using zAuth).
        
        Args:
            url: Target URL
            data: Request body data (will be JSON-encoded)
            timeout: Request timeout in seconds (default: 10)
        
        Returns:
            Response object or None on failure
        
        Example:
            ```python
            response = comm.http_post(
                "https://api.example.com/users",
                data={"username": "john", "email": "john@example.com"}
            )
            ```
        """
        return self._http_client.post(url, data=data, timeout=timeout)

    def http_put(self, url: str, data: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Any:
        """
        Make HTTP PUT request.
        
        Note:
            Pure communication layer - no auth logic. Applications should handle
            authentication separately (e.g., adding auth headers, using zAuth).
        
        Args:
            url: Target URL
            data: Request body data (will be JSON-encoded)
            headers: Optional custom headers
            timeout: Request timeout in seconds (default: 10)
        
        Returns:
            Response object or None on failure
        
        Example:
            ```python
            response = comm.http_put(
                "https://api.example.com/users/123",
                data={"username": "john", "email": "john@example.com"}
            )
            ```
        """
        return self._http_client.put(url, data=data, headers=headers, timeout=timeout)

    def http_patch(self, url: str, data: Optional[Dict[str, Any]] = None,
                   headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Any:
        """
        Make HTTP PATCH request.
        
        Note:
            Pure communication layer - no auth logic. Applications should handle
            authentication separately (e.g., adding auth headers, using zAuth).
        
        Args:
            url: Target URL
            data: Request body data (will be JSON-encoded)
            headers: Optional custom headers
            timeout: Request timeout in seconds (default: 10)
        
        Returns:
            Response object or None on failure
        
        Example:
            ```python
            response = comm.http_patch(
                "https://api.example.com/users/123",
                data={"email": "newemail@example.com"}
            )
            ```
        """
        return self._http_client.patch(url, data=data, headers=headers, timeout=timeout)

    def http_delete(self, url: str, headers: Optional[Dict[str, str]] = None,
                    timeout: int = 10) -> Any:
        """
        Make HTTP DELETE request.
        
        Note:
            Pure communication layer - no auth logic. Applications should handle
            authentication separately (e.g., adding auth headers, using zAuth).
        
        Args:
            url: Target URL
            headers: Optional custom headers
            timeout: Request timeout in seconds (default: 10)
        
        Returns:
            Response object or None on failure
        
        Example:
            ```python
            response = comm.http_delete("https://api.example.com/users/123")
            ```
        """
        return self._http_client.delete(url, headers=headers, timeout=timeout)
