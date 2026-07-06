# zComm WebSocket Module Guide

> **Modules:** `comm_websocket.py`, `comm_websocket_auth.py`, `comm_websocket_events.py`, `comm_websocket_input.py`, `comm_ssl.py`  
> **Purpose:** WebSocket server primitives with authentication, event broadcasting, and async input coordination

---

## Overview

The WebSocket module provides both low-level and high-level infrastructure for real-time bidirectional communication. It combines five specialized components:

**Low-Level Infrastructure:**
1. **WebSocketServer** (`comm_websocket.py`) - Core server, connection management, send/broadcast
2. **WebSocketAuth** (`comm_websocket_auth.py`) - Token authentication, origin validation, connection limits
3. **SSL/TLS** (`comm_ssl.py`) - Certificate handling for secure connections (WSS)

**High-Level Communication APIs:**
4. **WebSocketEvents** (`comm_websocket_events.py`) - Structured event broadcasting for subsystems
5. **WebSocketInputHandler** (`comm_websocket_input.py`) - Async input request/response coordination

**Key Features:**
- Persistent bidirectional connections
- Token-based authentication (opt-in)
- Origin validation (CORS/CSRF protection)
- Connection limit enforcement
- SSL/TLS encryption (WSS protocol)
- Graceful handshake error handling
- Broadcast to multiple clients
- Clean shutdown (Ctrl+C safe)

---

## Architecture

### Layer 0 Design

WebSocket is a **Layer 0 primitive** providing raw infrastructure:

```
Layer 0 (zComm): WebSocket server primitives
├── Start server (host, port, handler)
├── Send to specific client
├── Broadcast to all clients
├── Authentication (token, origin)
└── SSL/TLS (certificate loading)

Layer 2 (zBifrost): WebSocket orchestration
├── Three-tier authentication (zSession, Application, Dual)
├── Display/auth/data coordination
├── Terminal↔Web bridge
└── Caching and CRUD operations
```

**This guide covers Layer 0 primitives.** For orchestration, see [zBifrost Guide](../../L3_Abstraction/zBifrost_GUIDE.md).

---

### Component Interaction

```
WebSocketServer (Low-Level)
├── Uses: WebSocketAuth (if require_auth=True)
├── Uses: create_ssl_context() (if ssl_enabled=True)
├── Manages: Set of connected clients
└── Delegates: Message handling to custom handler

WebSocketEvents (High-Level)
├── Uses: WebSocketServer.broadcast() for sending
├── Formats: Structured events with consistent schema
├── Buffers: Events for capture pattern (zWalker)
└── Used by: zDisplay, zAuth, other subsystems

WebSocketInputHandler (High-Level)
├── Creates: asyncio.Future for async input
├── Tracks: Pending input requests by ID
├── Resolves: Futures when client responds
└── Used by: zDisplay for GUI input (read_string, etc.)
```

---

## WebSocketServer Class

### Initialization

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import WebSocketServer

server = WebSocketServer(logger, config)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `logger` | Any | Logger instance from zOS |
| `config` | Any | WebSocketConfig from zConfig (provides defaults) |

**Attributes:**
- `logger`: Logger instance
- `config`: WebSocketConfig (host, port, auth settings)
- `auth`: WebSocketAuth instance (authentication primitive)
- `server`: WebSocket server instance (after start)
- `clients`: Set of connected WebSocket clients
- `handler`: Custom message handler function
- `_running`: Server running state (bool)

---

### Starting the Server

#### Synchronous Start (Blocking)

```python
# Start server - blocks until Ctrl+C
server.start(
    host="127.0.0.1",
    port=8765,
    handler=my_message_handler
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | str | from config | Host address to bind |
| `port` | int | from config | Port number to bind |
| `handler` | callable | echo handler | Custom message handler function |

**Behavior:**
- Uses zConfig defaults if parameters not provided (respects 5-layer hierarchy)
- Blocks until Ctrl+C or `shutdown()` called
- Handles asyncio internally (no `async`/`await` needed)
- Graceful shutdown on Ctrl+C (closes connections, releases port)

**Handler Signature:**

```python
async def my_handler(websocket: WebSocketServerProtocol, message: str) -> None:
    """
    Process incoming message from client.
    
    Args:
        websocket: Client connection (use to send responses)
        message: Received message string
    """
    # Process message
    await websocket.send(f"Echo: {message}")
```

---

#### Asynchronous Start (Advanced)

```python
# For integration with existing asyncio code
await server.start_async(
    host="127.0.0.1",
    port=8765,
    handler=my_handler
)
```

**Use Case:** When you need to run WebSocket server alongside other async operations.

---

### Sending Messages

#### Send to Specific Client

```python
async def handler(websocket, message):
    # Send response to this client only
    success = await server.send(websocket, "Response message")
    if success:
        print("Message sent")
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `client` | WebSocketServerProtocol | Target client connection |
| `message` | str | Message to send |

**Returns:** `bool` - True if sent successfully, False otherwise

---

#### Broadcast to All Clients

```python
async def handler(websocket, message):
    # Broadcast to all connected clients (except sender)
    count = await server.broadcast(
        message=f"User says: {message}",
        exclude=websocket  # Don't send back to sender
    )
    print(f"Broadcasted to {count} clients")
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `message` | str | Message to broadcast |
| `exclude` | WebSocketServerProtocol | Optional client to exclude |

**Returns:** `int` - Number of clients message was sent to

**Behavior:**
- Automatically handles disconnected clients (removes from set)
- Logs broadcast count at debug level
- Returns 0 if no clients connected

---

### Server Properties

```python
# Check if server is running
if server.is_running:
    print("Server is active")

# Get connected client count
print(f"Connected clients: {server.client_count}")
```

---

### Graceful Shutdown

```python
# Shutdown server (closes all connections)
await server.shutdown()
```

**Behavior:**
- Closes all client connections gracefully
- Clears client set
- Closes server socket
- Releases port
- Sets `_running = False`

**Note:** Ctrl+C automatically triggers shutdown.

---

## WebSocketAuth Class

### Initialization

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import WebSocketAuth

auth = WebSocketAuth(config, logger)
```

**Note:** Typically created automatically by WebSocketServer.

---

### Authentication Flow

When `require_auth=True` in config:

```
1. Client connects
2. Check connection limit → Reject if exceeded (code 1008)
3. Validate origin header → Reject if invalid (code 1008)
4. Extract token (query param or header) → Reject if missing (code 1008)
5. Validate token against config → Reject if invalid (code 1008)
6. Register client → Accept connection
```

> Close code `1008` and the rejection reasons ("Invalid origin", "Authentication required", "Invalid token", "Maximum connections reached") are sourced from `comm_constants` (`WS_CLOSE_CODE_POLICY_VIOLATION`, `WS_REASON_*`) — one definition shared by the server (SSOT), not hardcoded per call site.

---

### Origin Validation

Protects against CORS/CSRF attacks by validating the `Origin` header.

**Configuration:**

```python
# In zSpark or .zEnv
websocket = {
    "allowed_origins": [
        "https://example.com",
        "https://app.example.com",
        "file://",  # Local HTML files
    ]
}
```

**Rules:**
- Empty `allowed_origins` → Only localhost/file:// allowed
- Missing `Origin` header → Connection allowed (some clients don't send it)
- `"null"` origin → Allowed if `"file://"` in allowed_origins (local files)

**Example:**

```python
# Browser sends: Origin: https://example.com
# Server checks: Is "https://example.com" in allowed_origins?
# If yes → Accept connection
# If no → Close with code 1008 "Invalid origin"
```

---

### Token Authentication

Clients pass tokens via query parameter or Authorization header.

**Client-Side (JavaScript):**

```javascript
// Method 1: Query parameter (recommended)
const ws = new WebSocket('ws://127.0.0.1:8765?token=my_secret_token');

// Method 2: Authorization header (advanced)
const ws = new WebSocket('ws://127.0.0.1:8765', {
    headers: {'Authorization': 'Bearer my_secret_token'}
});
```

**Server-Side Configuration:**

```bash
# .zEnv file
WEBSOCKET_TOKEN=my_secret_token
```

**Validation:**

```python
# Server extracts token from connection
token = auth.extract_token(websocket)

# Server validates against configured token
if auth.validate_token(token):
    # Accept connection
    auth.register_client(websocket, {"token": token, "addr": addr})
else:
    # Reject connection (code 1008)
    await websocket.close(1008, "Invalid token")
```

> **Security:** `validate_token()` compares with `hmac.compare_digest()` (constant-time), so a mismatch can't be inferred from response timing. If no token is configured, all token-auth attempts are rejected.

---

### Connection Limits

Prevent resource exhaustion by limiting concurrent connections.

**Configuration:**

```python
websocket = {
    "max_connections": 100  # Default from zConfig
}
```

**Check:**

```python
if auth.check_connection_limit():
    # Accept connection
else:
    # Reject (code 1008 "Maximum connections reached")
```

---

### Client Registration

Track authenticated clients:

```python
# Register client after successful auth
auth.register_client(websocket, {
    "token": token,
    "addr": client_addr,
    "user_id": 123  # Optional metadata
})

# Get client info later
info = auth.get_client_info(websocket)
# {"token": "...", "addr": ("127.0.0.1", 54321), "user_id": 123}

# Unregister on disconnect
auth.unregister_client(websocket)

# Get authenticated client count
count = auth.client_count
```

---

## SSL/TLS Support

### Creating SSL Context

```python
from zOS.L1_Foundation.b_zComm.zComm_modules.comm_ssl import create_ssl_context

ssl_context = create_ssl_context(
    ssl_enabled=True,
    ssl_cert="certs/server.cert",
    ssl_key="certs/server.key",
    logger=logger
)

if ssl_context:
    # SSL context created successfully
    # WebSocketServer will use it automatically
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `ssl_enabled` | bool | Whether SSL is enabled |
| `ssl_cert` | str | Path to SSL certificate file |
| `ssl_key` | str | Path to SSL private key file |
| `logger` | Any | Logger for diagnostics |
| `log_prefix` | str | Custom log prefix (optional) |

**Returns:** `ssl.SSLContext` if successful, `None` otherwise

---

### SSL Configuration

**Via zSpark:**

```python
zSpark = {
    "websocket": {
        "ssl_enabled": True,
        "ssl_cert": "certs/server.cert",
        "ssl_key": "certs/server.key",
    }
}
z = zOS(zSpark)
```

**Via .zEnv:**

```bash
WEBSOCKET_SSL_ENABLED=true
WEBSOCKET_SSL_CERT=certs/server.cert
WEBSOCKET_SSL_KEY=certs/server.key
```

**Production (Environment Variables):**

```bash
export WEBSOCKET_SSL_CERT=/etc/ssl/certs/yourdomain.crt
export WEBSOCKET_SSL_KEY=/etc/ssl/private/yourdomain.key
```

---

### Client Connection (WSS)

```javascript
// Use wss:// instead of ws://
const ws = new WebSocket('wss://127.0.0.1:8765?token=my_token');

ws.onopen = function() {
    console.log('Secure connection established');
};
```

**Note:** Browsers require trusted certificates. For self-signed certificates, manually trust them first by visiting `https://127.0.0.1:8765` in the browser.

---

### Certificate Requirements

**Development (Self-Signed):**

```bash
# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.cert -days 365 -nodes
```

**Production (CA-Signed):**
- **Let's Encrypt** (free, automated, recommended)
- Commercial providers (DigiCert, Comodo, etc.)
- Organization CA

**Security:**
- Uses `PROTOCOL_TLS_SERVER` (TLS 1.2+ only)
- Validates certificate/key files exist before loading
- Comprehensive error logging

---

## Configuration Reference

### WebSocket Config (from zConfig)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `host` | str | `"127.0.0.1"` | Bind address |
| `port` | int | auto-assigned | Port number |
| `require_auth` | bool | `False` | Enable authentication |
| `allowed_origins` | list | `[]` | Allowed CORS origins |
| `token` | str | from .zEnv | Authentication token |
| `max_connections` | int | `100` | Connection limit |
| `ping_interval` | int | `20` | Ping interval (seconds) |
| `ping_timeout` | int | `10` | Ping timeout (seconds) |
| `ssl_enabled` | bool | `False` | Enable SSL/TLS |
| `ssl_cert` | str | `None` | Certificate path |
| `ssl_key` | str | `None` | Private key path |

**Configuration Sources (5-layer hierarchy):**
1. System defaults (code)
2. zConfig.environment.zolo
3. .zEnv file
4. Environment variables
5. zSpark (highest priority)

---

## Usage Patterns

### Pattern 1: Basic Echo Server

```python
from zOS import zOS

async def echo_handler(websocket, message):
    """Echo messages back to client."""
    await websocket.send(f"Echo: {message}")

z = zOS()
z.comm.websocket.start(
    host="127.0.0.1",
    port=8765,
    handler=echo_handler
)
```

---

### Pattern 2: Broadcast Server

```python
async def broadcast_handler(websocket, message):
    """Broadcast messages to all clients."""
    client_addr = websocket.remote_address
    broadcast_msg = f"{client_addr[0]} says: {message}"
    
    count = await z.comm.websocket.broadcast(
        broadcast_msg,
        exclude=websocket  # Don't send back to sender
    )
    print(f"Broadcasted to {count} clients")

z.comm.websocket.start(port=8765, handler=broadcast_handler)
```

---

### Pattern 3: Authenticated Server

```python
# .zEnv file
# WEBSOCKET_TOKEN=my_secret_token

zSpark = {
    "websocket": {
        "require_auth": True,
        "allowed_origins": [
            "https://example.com",
            "file://",  # Local HTML files
        ],
    }
}

z = zOS(zSpark)

async def secure_handler(websocket, message):
    """Only authenticated clients reach this handler."""
    # Get client auth info
    client_info = z.comm.websocket.auth.get_client_info(websocket)
    print(f"Message from {client_info['addr']}: {message}")
    
    await websocket.send(f"Received: {message}")

z.comm.websocket.start(port=8765, handler=secure_handler)
```

---

### Pattern 4: Secure Server (WSS)

```python
zSpark = {
    "websocket": {
        "port": 8766,
        "require_auth": True,
        "ssl_enabled": True,
        "ssl_cert": "certs/server.cert",
        "ssl_key": "certs/server.key",
        "allowed_origins": [
            "https://example.com",  # Note: https (not http)
        ],
    }
}

z = zOS(zSpark)
z.comm.websocket.start(handler=my_handler)
# Server runs on wss://127.0.0.1:8766
```

---

## Error Handling

### Handshake Errors (v1.5.10)

The WebSocket server gracefully handles benign handshake errors:

**Filtered Errors (Suppressed):**
- Port probes (connection closed before sending data)
- Health checks (invalid HTTP requests)
- Incomplete connections (line without CRLF)

**Implementation:**
- `_process_request()` - Rejects non-WebSocket connections at HTTP layer
- `WebSocketHandshakeFilter` - Filters benign errors from logs
- `_custom_exception_handler()` - Suppresses asyncio tracebacks for known issues

**Result:** Clean logs showing only real WebSocket errors, not network noise.

---

### Connection Errors

```python
async def handler(websocket, message):
    try:
        await websocket.send(message)
    except Exception as e:
        # Client disconnected or network error
        logger.error(f"Send failed: {e}")
```

---

### Authentication Failures

Clients receive WebSocket close codes:

| Code | Reason | Cause |
|------|--------|-------|
| 1008 | "Invalid origin" | Origin header not in allowed_origins |
| 1008 | "Authentication required" | Token missing |
| 1008 | "Invalid token" | Token doesn't match configured value |
| 1008 | "Maximum connections reached" | Connection limit exceeded |

**Client-Side Handling:**

```javascript
ws.onclose = function(event) {
    if (event.code === 1008) {
        console.log('Authentication failed:', event.reason);
    }
};
```

---

## Best Practices

### 1. Security in Production

```python
# ✅ Production configuration
websocket = {
    "require_auth": True,           # Always require auth
    "ssl_enabled": True,            # Always use WSS
    "allowed_origins": [            # Whitelist specific domains
        "https://example.com",
        "https://app.example.com"
    ],
    "max_connections": 1000,        # Set reasonable limit
}

# ❌ Development-only configuration
websocket = {
    "require_auth": False,          # No auth
    "ssl_enabled": False,           # No encryption
    "allowed_origins": ["file://"], # Local files only
}
```

---

### 2. Store Tokens Securely

```bash
# ✅ .zEnv file (add to .gitignore)
WEBSOCKET_TOKEN=your_secure_token_here

# ❌ Hardcoded in code
websocket = {"token": "my_token"}  # Never do this!
```

---

### 3. Handle Disconnections

```python
async def handler(websocket, message):
    try:
        # Process message
        await websocket.send(response)
    except Exception:
        # Client disconnected - cleanup handled automatically
        pass
```

---

### 4. Use Broadcast Wisely

```python
# ✅ Exclude sender
await server.broadcast(message, exclude=websocket)

# ❌ Include sender (message loops back)
await server.broadcast(message)  # Sender receives own message
```

---

### 5. Graceful Shutdown

```python
# Server handles Ctrl+C automatically
# No manual cleanup needed

# For programmatic shutdown:
await server.shutdown()
```

---

## Integration with zComm

Access WebSocket server via zComm facade:

```python
from zOS import zOS

z = zOS()

# Start server
z.comm.websocket.start(port=8765, handler=my_handler)

# Send to client
await z.comm.websocket.send(client, message)

# Broadcast to all
await z.comm.websocket.broadcast(message, exclude=sender)

# Access auth info
client_info = z.comm.websocket.auth.get_client_info(websocket)

# Check server state
if z.comm.websocket.is_running:
    print(f"Connected clients: {z.comm.websocket.client_count}")
```

---

## High-Level WebSocket APIs

### WebSocketEvents - Structured Event Broadcasting

The `WebSocketEvents` class provides a high-level API for subsystems (zDisplay, zAuth, etc.) to send structured events to WebSocket clients.

**Purpose:**
- Consistent event formatting across subsystems
- JSON serialization and asyncio coordination
- Event buffering for capture pattern (zWalker compatibility)
- Thread-safe broadcasting

**Usage:**

```python
from zOS import zOS

z = zOS()

# Send structured event
z.comm.websocket_events.send_event({
    "event": "notification",
    "message": "Task completed",
    "timestamp": 1234567890
})

# Send display-specific event (used by zDisplay)
z.comm.websocket_events.send_display_event(
    "header",
    {"label": "Section Title", "color": "BLUE"}
)

# Buffer event for later collection (capture pattern)
z.comm.websocket_events.buffer_event(event_data)

# Retrieve buffered events
events = z.comm.websocket_events.get_buffered_events()
```

**Methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `send_event(event_data)` | Broadcast structured event to all clients | `bool` (success) |
| `send_display_event(name, data)` | Send display event with proper formatting | `bool` (success) |
| `buffer_event(event_data)` | Buffer event for capture pattern | `None` |
| `get_buffered_events()` | Retrieve and clear buffered events | `list` |
| `clear_buffer()` | Clear event buffer | `None` |

**Architecture:**
- Thread-safe (uses `asyncio.run_coroutine_threadsafe`)
- Handles missing event loop gracefully
- Delegates to `WebSocketServer.broadcast()` for actual transmission

---

### WebSocketInputHandler - Async Input Coordination

The `WebSocketInputHandler` class provides async input request/response coordination for GUI clients.

**Purpose:**
- Create async input requests with unique IDs
- Return Futures that resolve when client responds
- Track pending requests
- Coordinate request/response cycle

**Usage:**

```python
from zOS import zOS
import asyncio

z = zOS()

# Create async input request
async def get_user_input():
    # Create request and get Future
    future = z.comm.websocket_input.create_request(
        request_type="string",
        prompt="Enter your name:",
        placeholder="John Doe"
    )
    
    if future:
        # Wait for client to respond
        name = await future
        print(f"User entered: {name}")
    else:
        # No event loop - terminal fallback
        name = input("Enter your name: ")
    
    return name

# In WebSocket message handler (resolving input)
async def message_handler(websocket, message):
    data = json.loads(message)
    
    if data.get('event') == 'input_response':
        # Client sent input response
        request_id = data['requestId']
        value = data['value']
        
        # Resolve the pending Future
        z.comm.websocket_input.resolve_input(request_id, value)
```

**Methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `create_request(type, prompt, **kwargs)` | Create async input request | `Optional[asyncio.Future]` |
| `resolve_input(request_id, value)` | Resolve pending input Future | `bool` (success) |
| `cancel_request(request_id)` | Cancel pending request | `bool` (success) |
| `get_pending_requests()` | List pending request IDs | `list` |
| `clear_pending_requests()` | Cancel all pending requests | `None` |
| `generate_request_id()` | Generate unique request ID | `str` (UUID) |

**Architecture:**
- Manages `asyncio.Future` objects for async coordination
- Thread-safe Future creation and resolution
- Graceful handling of missing event loop
- Used by zDisplay for GUI input widgets

---

## See Also

- [zComm Main Guide](../zComm_GUIDE.md) - Complete zComm overview
- [HTTP Client Guide](http_GUIDE.md) - Synchronous HTTP requests
- [zBifrost Guide](../../L3_Abstraction/zBifrost_GUIDE.md) - WebSocket orchestration (Layer 2)
- [Network Utils Guide](network_GUIDE.md) - Port checking
