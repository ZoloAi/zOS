# zConfig Network Module Guide

> **Module:** `zOS/core/L1_Foundation/a_zConfig/zConfig_modules/network/`  
> **Purpose:** WebSocket and HTTP server configuration management for zOS network services.

---

## Overview

The `network` module provides configuration management for WebSocket and HTTP server services. It implements hierarchical configuration loading with deployment-aware SSL defaults, multi-mount support, and comprehensive security settings.

---

## Architecture

The network module consists of two main components:

| Component | File | Purpose |
|---|---|---|
| `WebSocketConfig` | `config_websocket.py` | WebSocket server configuration |
| `HttpServerConfig` | `config_http_server.py` | HTTP/HTTPS server configuration |

---

## `WebSocketConfig`

Manages WebSocket configuration with hierarchical loading and deployment-aware SSL defaults.

### Initialization

```python
from zConfig_modules.network import WebSocketConfig

ws_config = WebSocketConfig(
    environment_config=env_config,
    zos=zos_instance,
    logger=logger_instance,
    verbose=False
)
```

| Parameter | Type | Description |
|---|---|---|
| `environment_config` | `EnvironmentConfig` | Environment configuration instance |
| `zos` | `zOS` | zOS framework instance |
| `logger` | `LoggerConfig` | Logger instance |
| `verbose` | `bool` | Show initialization output (default: False) |

**On init, automatically:**
1. Validates zOS instance
2. Loads WebSocket config from environment
3. Checks environment variables (Layer 3/4)
4. Checks zSpark overrides (Layer 5 - highest priority)
5. Applies deployment-aware SSL defaults
6. Applies defaults for missing values
7. Prints ready message (if verbose or Development mode)

---

### Configuration Hierarchy

WebSocketConfig implements hierarchical loading (lowest to highest priority):

| Priority | Source | Example |
|---|---|---|
| 1 (lowest) | Hardcoded defaults | `host: "127.0.0.1"` |
| 2 | Config file | `zConfig.environment.zolo` → `websocket.host` |
| 3 | Environment variables | `$WEBSOCKET_HOST` |
| 4 | zSpark | `zOS({"websocket": {"host": "0.0.0.0"}})` |

**Layer 4 (zSpark) always wins** - allows runtime overrides.

> **Port-conflict validation:** the config validator rejects a setup where the
> WebSocket port equals the HTTP/`zServer` port. The check reads the canonical
> `zServer` key first and falls back to the legacy `http_server` key, so a
> conflict is caught regardless of which key you used.

---

### Properties

#### `host` (property)

WebSocket bind address.

```python
host = ws_config.host
# "127.0.0.1"
```

**Default:** "127.0.0.1"

**Environment variable:** `$WEBSOCKET_HOST`

---

#### `port` (property)

WebSocket port.

```python
port = ws_config.port
# 8765
```

**Default:** 8765 (standard WebSocket development port)

**Environment variable:** `$WEBSOCKET_PORT`

---

#### `require_auth` (property)

Whether authentication is required.

```python
if ws_config.require_auth:
    # Validate token
    pass
```

**Default:** False (security is opt-in for better UX)

**Environment variable:** `$WEBSOCKET_REQUIRE_AUTH`

---

#### `allowed_origins` (property)

List of allowed CORS origins.

```python
origins = ws_config.allowed_origins
# ["https://example.com", "https://app.example.com"]
```

**Default:** `[]` (empty list)

**Environment variable:** `$WEBSOCKET_ALLOWED_ORIGINS` (comma-separated)

---

#### `token` (property)

Authentication token (from .zEnv or env vars).

```python
token = ws_config.token
# "secret_token_123"
```

**Default:** "" (empty string)

**Environment variable:** `$WEBSOCKET_TOKEN`

---

#### `max_connections` (property)

Maximum concurrent connections.

```python
max_conn = ws_config.max_connections
# 100
```

**Default:** 100

---

#### `ping_interval` (property)

Ping interval in seconds.

```python
interval = ws_config.ping_interval
# 20
```

**Default:** 20 seconds

---

#### `ping_timeout` (property)

Ping timeout in seconds.

```python
timeout = ws_config.ping_timeout
# 10
```

**Default:** 10 seconds

---

#### `ssl_enabled` (property)

Whether SSL/TLS is enabled for WSS connections.

```python
if ws_config.ssl_enabled:
    # Use WSS protocol
    pass
```

**Default:** False (disabled for local development)

**Environment variable:** `$WEBSOCKET_SSL_ENABLED`

**Deployment-aware:** Auto-enabled in Production if certs present (v1.5.10)

---

#### `ssl_cert` (property)

Path to SSL certificate file.

```python
cert_path = ws_config.ssl_cert
# "/etc/ssl/cert.pem"
```

**Default:** None

**Environment variable:** `$WEBSOCKET_SSL_CERT`

---

#### `ssl_key` (property)

Path to SSL private key file.

```python
key_path = ws_config.ssl_key
# "/etc/ssl/key.pem"
```

**Default:** None

**Environment variable:** `$WEBSOCKET_SSL_KEY`

---

### Methods

#### `get(key: str, default=None) -> Any`

Get WebSocket config value by key.

```python
host = ws_config.get("host")
port = ws_config.get("port", 8765)
```

---

#### `get_all() -> Dict[str, Any]`

Get complete WebSocket configuration (copy).

```python
config = ws_config.get_all()
print(f"Host: {config['host']}")
print(f"Port: {config['port']}")
```

---

#### `update(key: str, value: Any) -> None`

Update WebSocket config value (runtime only, not persisted).

```python
ws_config.update("port", 9000)
ws_config.update("require_auth", True)
```

---

## `HttpServerConfig`

Manages HTTP/HTTPS server configuration with multi-mount support and deployment-aware SSL defaults.

### Initialization

```python
from zConfig_modules.network import HttpServerConfig

http_config = HttpServerConfig(
    zspark_obj=zSpark_dict,
    logger=logger_instance,
    verbose=False
)
```

| Parameter | Type | Description |
|---|---|---|
| `zspark_obj` | `dict` | zSpark configuration dictionary |
| `logger` | `LoggerConfig` | Logger instance |
| `verbose` | `bool` | Show initialization output (default: False) |

**On init, automatically:**
1. Gets zServer config from zSpark (looks for `zServer` key)
2. Backward compatibility: Falls back to `http_server` key
3. Checks environment variables for SSL settings
4. Applies deployment-aware SSL defaults
5. Parses static mount points
6. Logs configuration (if enabled)
7. Prints ready message (if verbose or not Production)

---

### Configuration Key

**Primary key:** `zServer` (v1.5.7+)

**Backward compatible:** `http_server` (deprecated)

```python
# Modern (recommended)
zSpark = {
    "zServer": {
        "enabled": True,
        "port": 8080
    }
}

# Backward compatible (deprecated)
zSpark = {
    "http_server": {
        "enabled": True,
        "port": 8080
    }
}
```

---

### Attributes

#### `host` (str)

Server host address.

```python
host = http_config.host
# "127.0.0.1"
```

**Default:** "127.0.0.1"

---

#### `port` (int)

Server port.

```python
port = http_config.port
# 8080
```

**Default:** 8080

---

#### `serve_path` (str)

Directory to serve files from.

```python
serve_path = http_config.serve_path
# "."
```

**Default:** "." (current directory)

---

#### `routes_file` (Optional[str])

Optional routes configuration file.

```python
routes_file = http_config.routes_file
# "/path/to/zServer.routes.zolo" or None
```

**Default:** None (auto-detected if not specified)

---

#### `enabled` (bool)

Whether zServer is enabled.

```python
if http_config.enabled:
    # Start server
    pass
```

**Default:** False

**Behavior:** If True, server ALWAYS waits (blocking or interactive).

---

#### `zShell` (bool)

Whether to drop into zShell REPL (v1.5.8).

```python
if http_config.zShell:
    # Drop into interactive shell
    pass
else:
    # Silent blocking (standard server behavior)
    pass
```

**Default:** False (silent blocking)

**Use case:** Interactive server management, debugging.

---

#### `ssl_enabled` (bool)

Whether SSL/TLS is enabled for HTTPS (v1.5.10).

```python
if http_config.ssl_enabled:
    # Use HTTPS protocol
    pass
```

**Default:** False (disabled for local development)

**Environment variable:** `$HTTP_SSL_ENABLED`

**Deployment-aware:** Auto-enabled in Production if certs present.

---

#### `ssl_cert` (Optional[str])

Path to SSL certificate file (v1.5.10).

```python
cert_path = http_config.ssl_cert
# "/etc/ssl/cert.pem"
```

**Default:** None

**Environment variable:** `$HTTP_SSL_CERT`

---

#### `ssl_key` (Optional[str])

Path to SSL private key file (v1.5.10).

```python
key_path = http_config.ssl_key
# "/etc/ssl/key.pem"
```

**Default:** None

**Environment variable:** `$HTTP_SSL_KEY`

---

#### `static_mounts` (Dict[str, str])

Multi-mount support (v1.5.11) - serve files from multiple directories.

```python
mounts = http_config.static_mounts
# {
#     "/bifrost/": "/Users/gal/bifrost/",
#     "/assets/": "/var/www/assets/"
# }
```

**Default:** `{}` (empty dict)

**Environment variable:** `$ZSERVER_MOUNTS` (JSON string)

**Format:** `{"/url_prefix/": "/absolute/filesystem/path/"}`

**Security:**
- Each mount has directory traversal protection
- URL prefixes must start and end with `/`
- Filesystem paths resolved to absolute paths

---

## `zRavenConfig`

Configuration for the **zRaven** test subsystem (`config_raven.py`). Reads the
`zRaven` key from `zSpark_obj` and decides whether a UI test run is launched.

### zSpark syntax

```python
zSpark = {"zRaven": "crm"}    # run zRaven/zRaven.crm.zolo
zSpark = {"zRaven": False}    # disabled (default)
# key absent                 # also disabled
# zSpark = {"zRaven": True}   # deprecated → warns; use a test name instead
```

### Attributes

| Attribute | Type | Description |
|---|---|---|
| `enabled` | bool | `True` only when a valid test name is set |
| `name` | str \| None | The test name (e.g. `"crm"`) |
| `timeout` | int | Max seconds before the run is killed (`zRavenTimeout`, default 120) |

### Self-activation guard

When zRaven spawns a test-target subprocess it sets the `ZRAVEN_TARGET` env var.
If that var is present, `zRavenConfig` forces `enabled = False` so the target
process never recursively starts its own zRaven run.

```python
from zConfig_modules.network.config_raven import zRavenConfig

cfg = zRavenConfig(zspark_obj, logger)
if cfg.enabled:
    print(f"zRaven test: {cfg.name} (timeout {cfg.timeout}s)")
```

---

## Deployment-Aware SSL Defaults

Both WebSocket and HTTP server configs implement smart SSL defaults (v1.5.10):

### Priority Order

1. **Explicit env var** (`$WEBSOCKET_SSL_ENABLED` / `$HTTP_SSL_ENABLED`) - Highest priority
2. **Production + certs present** - Auto-enable SSL
3. **Development or no certs** - Disable SSL

### Example

**Development mode:**
```python
# .zEnv
WEBSOCKET_SSL_CERT=/etc/ssl/cert.pem
WEBSOCKET_SSL_KEY=/etc/ssl/key.pem

zSpark = {"deployment": "Development"}
z = zOS(zSpark)

# SSL disabled (Development mode)
print(z.config.websocket.ssl_enabled)  # False
```

**Production mode:**
```python
# .zEnv
WEBSOCKET_SSL_CERT=/etc/ssl/cert.pem
WEBSOCKET_SSL_KEY=/etc/ssl/key.pem

zSpark = {"deployment": "Production"}
z = zOS(zSpark)

# SSL auto-enabled (Production + certs present)
print(z.config.websocket.ssl_enabled)  # True
```

**Explicit override:**
```python
# .zEnv
WEBSOCKET_SSL_ENABLED=true
WEBSOCKET_SSL_CERT=/etc/ssl/cert.pem
WEBSOCKET_SSL_KEY=/etc/ssl/key.pem

# SSL enabled regardless of deployment mode
print(z.config.websocket.ssl_enabled)  # True
```

---

## Practical Examples

### Example 1: Basic WebSocket Config

```python
from zOS import zOS

z = zOS()

# Access WebSocket config
ws = z.config.websocket

print(f"WebSocket: {ws.host}:{ws.port}")
print(f"Auth required: {ws.require_auth}")
print(f"Max connections: {ws.max_connections}")
```

---

### Example 2: Custom WebSocket Settings

```python
# Configure via zSpark
zSpark = {
    "websocket": {
        "host": "0.0.0.0",
        "port": 9000,
        "require_auth": True,
        "max_connections": 500
    }
}
z = zOS(zSpark)

ws = z.config.websocket
print(f"WebSocket: {ws.host}:{ws.port}")
print(f"Auth: {ws.require_auth}")
```

---

### Example 3: WebSocket with SSL

```python
# .zEnv
# WEBSOCKET_SSL_ENABLED=true
# WEBSOCKET_SSL_CERT=/etc/ssl/cert.pem
# WEBSOCKET_SSL_KEY=/etc/ssl/key.pem

zSpark = {"deployment": "Production"}
z = zOS(zSpark)

ws = z.config.websocket

if ws.ssl_enabled:
    print(f"WSS: {ws.host}:{ws.port}")
    print(f"Cert: {ws.ssl_cert}")
    print(f"Key: {ws.ssl_key}")
else:
    print(f"WS: {ws.host}:{ws.port}")
```

---

### Example 4: CORS Configuration

```python
# .zEnv
# WEBSOCKET_ALLOWED_ORIGINS=https://example.com,https://app.example.com

z = zOS()
ws = z.config.websocket

print(f"Allowed origins: {ws.allowed_origins}")
# ["https://example.com", "https://app.example.com"]

# Check origin
if "https://example.com" in ws.allowed_origins:
    print("Origin allowed")
```

---

### Example 5: WebSocket Authentication

```python
# .zEnv
# WEBSOCKET_REQUIRE_AUTH=true
# WEBSOCKET_TOKEN=secret_token_123

z = zOS()
ws = z.config.websocket

if ws.require_auth:
    # Validate client token
    client_token = get_client_token()
    if client_token == ws.token:
        print("Authentication successful")
    else:
        print("Authentication failed")
```

---

### Example 6: Basic HTTP Server Config

```python
# Enable HTTP server via zSpark
zSpark = {
    "zServer": {
        "enabled": True,
        "port": 8080,
        "serve_path": "./public"
    }
}
z = zOS(zSpark)

http = z.config.http_server

if http.enabled:
    print(f"HTTP Server: {http.host}:{http.port}")
    print(f"Serving: {http.serve_path}")
```

---

### Example 7: HTTP Server with SSL

```python
# .zEnv
# HTTP_SSL_ENABLED=true
# HTTP_SSL_CERT=/etc/ssl/cert.pem
# HTTP_SSL_KEY=/etc/ssl/key.pem

zSpark = {
    "deployment": "Production",
    "zServer": {
        "enabled": True,
        "port": 443
    }
}
z = zOS(zSpark)

http = z.config.http_server

if http.ssl_enabled:
    print(f"HTTPS Server: {http.host}:{http.port}")
    print(f"Cert: {http.ssl_cert}")
else:
    print(f"HTTP Server: {http.host}:{http.port}")
```

---

### Example 8: Multi-Mount Support

```python
# .zEnv (v1.5.11)
# ZSERVER_MOUNTS={"/bifrost/": "/Users/gal/bifrost/", "/assets/": "/var/www/assets/"}

zSpark = {
    "zServer": {
        "enabled": True
    }
}
z = zOS(zSpark)

http = z.config.http_server

# Access static mounts
for url_prefix, fs_path in http.static_mounts.items():
    print(f"Mount: {url_prefix} → {fs_path}")

# Output:
# Mount: /bifrost/ → /Users/gal/bifrost/
# Mount: /assets/ → /var/www/assets/
```

**URL mapping:**
- `http://host/bifrost/file.js` → `/Users/gal/bifrost/file.js`
- `http://host/assets/style.css` → `/var/www/assets/style.css`

---

### Example 9: Interactive Server Mode

```python
# Enable zShell REPL (v1.5.8)
zSpark = {
    "zServer": {
        "enabled": True,
        "zShell": True  # Drop into interactive shell
    }
}
z = zOS(zSpark)

# Server starts, then drops into zShell REPL
# User can run commands while server is running
```

---

### Example 10: Routes Configuration

```python
# Custom routes file
zSpark = {
    "zServer": {
        "enabled": True,
        "routes_file": "./zServer.routes.zolo"
    }
}
z = zOS(zSpark)

http = z.config.http_server

if http.routes_file:
    print(f"Routes: {http.routes_file}")
    # Load and apply routes
```

---

## Environment Variables

### WebSocket

| Variable | Type | Description | Default |
|---|---|---|---|
| `WEBSOCKET_HOST` | str | Bind address | "127.0.0.1" |
| `WEBSOCKET_PORT` | int | Port number | 8765 |
| `WEBSOCKET_REQUIRE_AUTH` | bool | Require authentication | False |
| `WEBSOCKET_ALLOWED_ORIGINS` | str | CORS origins (comma-separated) | "" |
| `WEBSOCKET_TOKEN` | str | Authentication token | "" |
| `WEBSOCKET_SSL_ENABLED` | bool | Enable SSL/TLS | False |
| `WEBSOCKET_SSL_CERT` | str | SSL certificate path | None |
| `WEBSOCKET_SSL_KEY` | str | SSL private key path | None |

### HTTP Server

| Variable | Type | Description | Default |
|---|---|---|---|
| `HTTP_SSL_ENABLED` | bool | Enable SSL/TLS | False |
| `HTTP_SSL_CERT` | str | SSL certificate path | None |
| `HTTP_SSL_KEY` | str | SSL private key path | None |
| `ZSERVER_MOUNTS` | str | Static mounts (JSON) | {} |

---

## Configuration Examples

### WebSocket Config File

**zConfig.environment.zolo:**
```zolo
zEnv:
  websocket:
    host: 127.0.0.1
    port: 8765
    require_auth: false
    allowed_origins: []
    token: ""
    max_connections: 100
    ping_interval: 20
    ping_timeout: 10
    ssl_enabled: false
    ssl_cert: null
    ssl_key: null
```

---

### WebSocket .zEnv File

**.zEnv:**
```bash
WEBSOCKET_HOST=0.0.0.0
WEBSOCKET_PORT=9000
WEBSOCKET_REQUIRE_AUTH=true
WEBSOCKET_TOKEN=secret_token_123
WEBSOCKET_ALLOWED_ORIGINS=https://example.com,https://app.example.com
```

---

### HTTP Server zSpark

```python
zSpark = {
    "zServer": {
        "enabled": True,
        "host": "0.0.0.0",
        "port": 8080,
        "serve_path": "./public",
        "routes_file": "./zServer.routes.zolo",
        "zShell": False
    }
}
```

---

### Multi-Mount .zEnv

**.zEnv:**
```bash
ZSERVER_MOUNTS={"/bifrost/": "/Users/gal/bifrost/", "/assets/": "/var/www/assets/"}
```

---

## Best Practices

1. **Security:**
   - Enable `require_auth` in production
   - Use SSL/TLS for production deployments
   - Store tokens in `.zEnv` (add to `.gitignore`)
   - Configure `allowed_origins` for CORS protection

2. **Deployment-Aware SSL:**
   - Let Production mode auto-enable SSL (if certs present)
   - Use explicit `SSL_ENABLED=true` for forced SSL
   - Disable SSL in Development for easier testing

3. **Port Selection:**
   - WebSocket: 8765 (standard development port)
   - HTTP: 8080 (standard development port)
   - HTTPS: 443 (standard production port)
   - Use environment variables for deployment-specific ports

4. **Multi-Mount:**
   - Use for serving multiple directories
   - URL prefixes must start and end with `/`
   - Filesystem paths resolved to absolute
   - Each mount has directory traversal protection

5. **Configuration Hierarchy:**
   - Use config file for persistent settings
   - Use `.zEnv` for secrets and deployment-specific settings
   - Use zSpark for runtime overrides (testing, experiments)

6. **CORS:**
   - Configure `allowed_origins` for cross-origin requests
   - Use comma-separated list in environment variables
   - Empty list = no CORS restrictions (development only)

7. **Connection Limits:**
   - Set `max_connections` based on expected load
   - Monitor connection count in production
   - Adjust ping intervals for network conditions

8. **Interactive Mode:**
   - Use `zShell: True` for development/debugging
   - Use `zShell: False` for production (standard blocking)
   - Interactive mode allows server management while running
