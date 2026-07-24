# zComm Network Utilities & Constants Guide

> **Modules:** `comm_utils.py`, `comm_constants.py`  
> **Purpose:** Network utilities (port checking) and shared constants

---

## Overview

This guide covers two utility modules:

1. **NetworkUtils** (`comm_utils.py`) - Port availability checking
2. **Constants** (`comm_constants.py`) - Shared constants across zComm modules

---

## NetworkUtils Class

### Purpose

Provides low-level network operations for port availability checking, essential for:
- Service management (checking if PostgreSQL/Redis is running)
- Server initialization (ensuring port is available before binding)
- Health checks (verifying services are accessible)

---

### Initialization

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import NetworkUtils

network_utils = NetworkUtils(logger)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `logger` | Any | Logger instance for debug/error output |

---

### Port Checking

```python
# Check if port is available
is_available = network_utils.check_port(8080)

if is_available:
    print("Port 8080 is available (not in use)")
else:
    print("Port 8080 is in use")

# Check custom host
is_available = network_utils.check_port(5432, host="192.168.1.100")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `port` | int | required | Port number (1-65535) |
| `host` | str | `"localhost"` | Host address to check |

**Returns:** `bool` - True if port is available, False if in use

**Raises:** `ValueError` if port is outside valid range (1-65535)

**Implementation:**
- Delegates the TCP probe to `is_port_open()` (the SSOT below)
- `is_port_open` True (something listening) → `check_port` returns False (in use)
- `is_port_open` False → `check_port` returns True (available)
- Uses 1-second timeout for quick checks

---

### `is_port_open()` — Low-Level Probe (SSOT)

```python
# True if a TCP connection to host:port succeeds (something is listening)
in_use = network_utils.is_port_open(5432)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `port` | int | required | Port number to probe |
| `host` | str | `"localhost"` | Host address |

**Returns:** `bool` - True if a listener accepts the connection, False otherwise (including socket errors)

This is the single TCP-probe primitive in zComm. Both `check_port()` (availability,
with range validation) and the PostgreSQL service's `is_running()` build on it, so
there's one implementation of "is this port in use" rather than several copies.

---

### Usage Patterns

#### Pattern 1: Check Before Binding

```python
if z.comm.check_port(8080):
    # Port available - start server
    server.start(port=8080)
else:
    print("Port 8080 already in use")
```

---

#### Pattern 2: Find Available Port

```python
def find_available_port(start_port=8000, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        if z.comm.check_port(port):
            return port
    return None

port = find_available_port()
if port:
    print(f"Found available port: {port}")
```

> This is an *application-level* helper for your own sockets. zServer's own
> boot has a built-in doctrine — pinned ports fail loud, unpinned ports hunt
> and announce — documented in
> [zServer ports_GUIDE](../../L4_Orchestration/zServer_Guides/ports_GUIDE.md);
> don't pre-hunt a port and pin it yourself, you'd defeat the fail-loud contract.

---

#### Pattern 3: Service Health Check

```python
# Check if PostgreSQL is running
if not z.comm.check_port(5432):
    print("PostgreSQL is running on port 5432")
else:
    print("PostgreSQL is not running")
```

---

### Integration with zComm

```python
from zOS import zOS

z = zOS()

# Access via zComm facade
is_available = z.comm.check_port(8080)
```

---

## Constants Module

### Purpose

Provides shared constants used across zComm modules for consistency and maintainability.

---

### Service Identifiers

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import SERVICE_POSTGRESQL

# Use in service management
z.comm.start_service(SERVICE_POSTGRESQL)  # "postgresql"
```

**Available:**
- `SERVICE_POSTGRESQL` = `"postgresql"`

**Future:**
- `SERVICE_REDIS` = `"redis"` (planned)
- `SERVICE_MONGODB` = `"mongodb"` (planned)

---

### Network Configuration

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import (
    PORT_MIN,                # 1
    PORT_MAX,                # 65535
    DEFAULT_HOST,            # "localhost"
    DEFAULT_TIMEOUT_SECONDS, # 1
    HTTP_DEFAULT_TIMEOUT,    # 10
)

# Validate port range
if PORT_MIN <= port <= PORT_MAX:
    print("Valid port")

# Use default timeout
response = client.get(url, timeout=HTTP_DEFAULT_TIMEOUT)
```

---

### WebSocket Close Codes

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import (
    WS_CLOSE_CODE_POLICY_VIOLATION,  # 1008
    WS_CLOSE_CODE_INTERNAL_ERROR,    # 1011
)

# Close connection with standard code
await websocket.close(WS_CLOSE_CODE_POLICY_VIOLATION, "Invalid origin")
```

---

### WebSocket Close Reasons

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import (
    WS_REASON_INVALID_ORIGIN,    # "Invalid origin"
    WS_REASON_AUTH_REQUIRED,     # "Authentication required"
    WS_REASON_INVALID_TOKEN,     # "Invalid token"
    WS_REASON_MAX_CONNECTIONS,   # "Maximum connections reached"
)

# Use standard reason strings
await websocket.close(1008, WS_REASON_INVALID_TOKEN)
```

---

### Storage Configuration

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import (
    STORAGE_DEFAULT_BACKEND,         # "local"
    STORAGE_SUPPORTED_BACKENDS,      # ["local", "s3", "azure", "gcs"]
    STORAGE_CONFIG_KEY_BACKEND,      # "storage_backend"
    STORAGE_CONFIG_KEY_LOCAL_ROOT,   # "storage_local_root"
    STORAGE_CONFIG_KEY_S3_BUCKET,    # "storage_s3_bucket"
    STORAGE_CONFIG_KEY_S3_REGION,    # "storage_s3_region"
)

# Validate backend
if backend in STORAGE_SUPPORTED_BACKENDS:
    print("Supported backend")
```

---

### PostgreSQL Defaults

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import (
    POSTGRESQL_DEFAULT_PORT,      # 5432
    POSTGRESQL_DEFAULT_HOST,      # "localhost"
    POSTGRESQL_DEFAULT_USER,      # "postgres"
    POSTGRESQL_DEFAULT_DATABASE,  # "postgres"
)

# Use defaults for connection
conn = psycopg2.connect(
    host=POSTGRESQL_DEFAULT_HOST,
    port=POSTGRESQL_DEFAULT_PORT,
    user=POSTGRESQL_DEFAULT_USER,
    database=POSTGRESQL_DEFAULT_DATABASE
)
```

---

### Status Dictionary Keys

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import (
    STATUS_KEY_ERROR,             # "error"
    STATUS_KEY_SERVICE,           # "service"
    STATUS_KEY_RUNNING,           # "running"
    STATUS_KEY_PORT,              # "port"
    STATUS_KEY_OS,                # "os"
    STATUS_KEY_CONNECTION_INFO,   # "connection_info"
    STATUS_KEY_MESSAGE,           # "message"
)

# Access status dict with constants
status = z.comm.service_status("postgresql")
if status.get(STATUS_KEY_RUNNING):
    info = status[STATUS_KEY_CONNECTION_INFO]
```

---

### Connection Info Keys

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import (
    CONN_KEY_HOST,                # "host"
    CONN_KEY_PORT,                # "port"
    CONN_KEY_USER,                # "user"
    CONN_KEY_DATABASE,            # "database"
    CONN_KEY_CONNECTION_STRING,   # "connection_string"
)

# Access connection info with constants
info = z.comm.get_service_connection_info("postgresql")
host = info[CONN_KEY_HOST]
port = info[CONN_KEY_PORT]
conn_str = info[CONN_KEY_CONNECTION_STRING]
```

---

## Complete Constants Reference

### Service Identifiers

| Constant | Value | Purpose |
|----------|-------|---------|
| `SERVICE_POSTGRESQL` | `"postgresql"` | PostgreSQL service identifier |

---

### Network Configuration

| Constant | Value | Purpose |
|----------|-------|---------|
| `PORT_MIN` | `1` | Minimum valid port number |
| `PORT_MAX` | `65535` | Maximum valid port number |
| `DEFAULT_HOST` | `"localhost"` | Default host for connections |
| `DEFAULT_TIMEOUT_SECONDS` | `1` | Port check timeout |
| `HTTP_DEFAULT_TIMEOUT` | `10` | HTTP request timeout |

---

### WebSocket Close Codes

| Constant | Value | Purpose |
|----------|-------|---------|
| `WS_CLOSE_CODE_POLICY_VIOLATION` | `1008` | Policy violation (auth failure) |
| `WS_CLOSE_CODE_INTERNAL_ERROR` | `1011` | Internal server error |

---

### WebSocket Close Reasons

| Constant | Value | Purpose |
|----------|-------|---------|
| `WS_REASON_INVALID_ORIGIN` | `"Invalid origin"` | Origin header rejected |
| `WS_REASON_AUTH_REQUIRED` | `"Authentication required"` | Token missing |
| `WS_REASON_INVALID_TOKEN` | `"Invalid token"` | Token validation failed |
| `WS_REASON_MAX_CONNECTIONS` | `"Maximum connections reached"` | Connection limit exceeded |

---

### Storage Configuration

| Constant | Value | Purpose |
|----------|-------|---------|
| `STORAGE_DEFAULT_BACKEND` | `"local"` | Default storage backend |
| `STORAGE_SUPPORTED_BACKENDS` | `["local", "s3", "azure", "gcs"]` | Supported backends |
| `STORAGE_CONFIG_KEY_BACKEND` | `"storage_backend"` | Config key for backend |
| `STORAGE_CONFIG_KEY_LOCAL_ROOT` | `"storage_local_root"` | Config key for local root |
| `STORAGE_CONFIG_KEY_S3_BUCKET` | `"storage_s3_bucket"` | Config key for S3 bucket |
| `STORAGE_CONFIG_KEY_S3_REGION` | `"storage_s3_region"` | Config key for S3 region |

---

### PostgreSQL Defaults

| Constant | Value | Purpose |
|----------|-------|---------|
| `POSTGRESQL_DEFAULT_PORT` | `5432` | Default PostgreSQL port |
| `POSTGRESQL_DEFAULT_HOST` | `"localhost"` | Default PostgreSQL host |
| `POSTGRESQL_DEFAULT_USER` | `"postgres"` | Default PostgreSQL user |
| `POSTGRESQL_DEFAULT_DATABASE` | `"postgres"` | Default PostgreSQL database |

---

### Status Dictionary Keys

| Constant | Value | Purpose |
|----------|-------|---------|
| `STATUS_KEY_ERROR` | `"error"` | Error message key |
| `STATUS_KEY_SERVICE` | `"service"` | Service name key |
| `STATUS_KEY_RUNNING` | `"running"` | Running status key |
| `STATUS_KEY_PORT` | `"port"` | Port number key |
| `STATUS_KEY_OS` | `"os"` | Operating system key |
| `STATUS_KEY_CONNECTION_INFO` | `"connection_info"` | Connection info key |
| `STATUS_KEY_MESSAGE` | `"message"` | Status message key |

---

### Connection Info Keys

| Constant | Value | Purpose |
|----------|-------|---------|
| `CONN_KEY_HOST` | `"host"` | Host address key |
| `CONN_KEY_PORT` | `"port"` | Port number key |
| `CONN_KEY_USER` | `"user"` | Username key |
| `CONN_KEY_DATABASE` | `"database"` | Database name key |
| `CONN_KEY_CONNECTION_STRING` | `"connection_string"` | Full connection string key |

---

## Best Practices

### 1. Use Constants for Dictionary Keys

```python
# ✅ Use constants
status = z.comm.service_status("postgresql")
if status.get(STATUS_KEY_RUNNING):
    port = status[STATUS_KEY_PORT]

# ❌ Hardcode strings
if status.get("running"):  # Typo-prone
    port = status["port"]
```

---

### 2. Validate Port Range

```python
# ✅ Validate with constants
if PORT_MIN <= port <= PORT_MAX:
    z.comm.check_port(port)

# ❌ Hardcode limits
if 1 <= port <= 65535:  # Magic numbers
    z.comm.check_port(port)
```

---

### 3. Use Standard Close Codes

```python
# ✅ Use constants
await websocket.close(WS_CLOSE_CODE_POLICY_VIOLATION, WS_REASON_INVALID_TOKEN)

# ❌ Hardcode values
await websocket.close(1008, "Invalid token")  # Less maintainable
```

---

## See Also

- [zComm Main Guide](../zComm_GUIDE.md)
- [HTTP Client Guide](http_GUIDE.md)
- [WebSocket Guide](websocket_GUIDE.md)
- [Services Guide](services_GUIDE.md)
- [Storage Guide](storage_GUIDE.md)
