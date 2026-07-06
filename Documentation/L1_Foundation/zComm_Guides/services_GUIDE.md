# zComm Service Management Module Guide

> **Modules:** `comm_services.py`, `services/postgresql_service.py`  
> **Purpose:** Local development service lifecycle management (PostgreSQL)

---

## Overview

The service management module provides cross-platform lifecycle management for local development services. It uses a registry-based pattern where services implement a common interface and are managed through a unified `ServiceManager` facade.

**Current Implementation:**
- ✅ PostgreSQL (macOS Homebrew, Linux systemd, Windows services)

**Planned:**
- 🔄 Redis (cache service)
- 🔄 MongoDB (document database)

**Key Features:**
- Cross-platform service detection and management
- Unified start/stop/restart/status interface
- Connection information retrieval
- OS-specific command execution (Homebrew, systemd, pg_ctl, Windows services)
- Graceful error handling and logging

---

## Architecture

### Registry Pattern

```
ServiceManager (Facade)
├── Registry: {"postgresql": PostgreSQLService}
├── Methods: start(), stop(), restart(), status(), get_connection_info()
└── Delegates to registered service implementations

PostgreSQLService (Implementation)
├── Platform detection (Darwin, Linux, Windows)
├── Start methods (Homebrew, systemd, pg_ctl, Windows services)
├── Stop methods (platform-specific)
└── Status check (port-based detection)
```

---

### Service Interface

All services must implement:

```python
class ServiceInterface:
    def start(**kwargs) -> bool:
        """Start the service. Returns True if successful."""
        
    def stop() -> bool:
        """Stop the service. Returns True if successful."""
        
    def status() -> Dict[str, Any]:
        """Get service status dict."""
        
    def get_connection_info() -> Dict[str, Any]:
        """Get connection details (host, port, etc.)."""
```

---

## ServiceManager Class

### Initialization

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import ServiceManager

manager = ServiceManager(logger)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `logger` | Any | Logger instance (required) |

**Raises:** `ValueError` if logger is None

**On Init:**
- Validates logger
- Registers available services (currently PostgreSQL)
- Logs initialization to framework logger

---

### Starting Services

```python
# Start with defaults
success = manager.start("postgresql")

# Start with custom parameters (future)
success = manager.start("postgresql", port=5433, data_dir="/custom/path")
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `service_name` | str | Service identifier ("postgresql") |
| `**kwargs` | Any | Service-specific configuration (reserved for future use) |

**Returns:** `bool` - True if started successfully, False otherwise

**Raises:** `ValueError` if service_name is invalid (None, empty, not a string)

**Behavior:**
- Checks if service is already running (returns True if yes)
- Attempts platform-specific start method
- Logs success/failure at info/error level
- Returns False if service not found in registry

---

### Stopping Services

```python
success = manager.stop("postgresql")
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `service_name` | str | Service identifier |

**Returns:** `bool` - True if stopped successfully, False otherwise

**Raises:** `ValueError` if service_name is invalid

**Behavior:**
- Checks if service is running (returns True if already stopped)
- Attempts platform-specific stop method
- Logs success/failure
- Returns False if service not found

---

### Restarting Services

```python
success = manager.restart("postgresql")
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `service_name` | str | Service identifier |

**Returns:** `bool` - True if restarted successfully, False otherwise

**Raises:** `ValueError` if service_name is invalid

**Implementation:** Calls `stop()` then `start()` sequentially

---

### Getting Service Status

#### Single Service Status

```python
status = manager.status("postgresql")
# {
#     "service": "postgresql",
#     "running": True,
#     "port": 5432,
#     "os": "Darwin",
#     "connection_info": {
#         "host": "localhost",
#         "port": 5432,
#         "user": "postgres",
#         "database": "postgres",
#         "connection_string": "postgresql://postgres@localhost:5432/postgres"
#     }
# }
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `service_name` | str | Service identifier |

**Returns:** `Dict[str, Any]` with status information

**Status Dict Keys:**
- `service`: Service name
- `running`: Boolean (True if running)
- `port`: Default port number
- `os`: Operating system
- `connection_info`: Connection details (if running)
- `message`: Installation instructions (if not running)
- `error`: Error message (if service not found)

---

#### All Services Status

```python
status = manager.status()
# {
#     "postgresql": {
#         "service": "postgresql",
#         "running": True,
#         "port": 5432,
#         ...
#     }
# }
```

**Parameters:** None (or `service_name=None`)

**Returns:** `Dict[str, Dict[str, Any]]` - Service name → status dict mapping

---

### Getting Connection Information

```python
info = manager.get_connection_info("postgresql")
# {
#     "host": "localhost",
#     "port": 5432,
#     "user": "postgres",
#     "database": "postgres",
#     "connection_string": "postgresql://postgres@localhost:5432/postgres"
# }
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `service_name` | str | Service identifier |

**Returns:** `Dict[str, Any]` with connection details, or `None` if service not found

**Raises:** `ValueError` if service_name is invalid

**Connection Info Keys:**
- `host`: Hostname/IP address
- `port`: Port number
- `user`: Default username
- `database`: Default database name
- `connection_string`: Full connection string

---

## PostgreSQLService Class

### Platform Support

| Platform | Detection Method | Start Method | Stop Method |
|----------|------------------|--------------|-------------|
| **macOS** | Homebrew, pg_ctl | `brew services start` | `brew services stop` |
| **Linux** | systemd, pg_ctl | `sudo systemctl start` | `sudo systemctl stop` |
| **Windows** | Windows services | `net start postgresql` | `net stop postgresql` |

---

### Initialization

```python
from zOS.L1_Foundation.b_zComm.zComm_modules.services import PostgreSQLService

service = PostgreSQLService(logger)
```

**Note:** Typically accessed via ServiceManager, not directly.

---

### Starting PostgreSQL

```python
success = service.start()
```

**Returns:** `bool` - True if started, False otherwise

**Start Sequence (macOS):**
1. Check if already running (port 5432) → Return True
2. Try `brew services start postgresql@14`
3. Try `brew services start postgresql` (fallback)
4. Try `pg_ctl -D <data_dir> start` (fallback)
5. Return False if all methods fail

**Start Sequence (Linux):**
1. Check if already running → Return True
2. Try `sudo systemctl start postgresql`
3. Try `pg_ctl -D <data_dir> start` (fallback)
4. Return False if all methods fail

**Start Sequence (Windows):**
1. Check if already running → Return True
2. Try `net start postgresql`
3. Return False if failed

---

### Stopping PostgreSQL

```python
success = service.stop()
```

**Returns:** `bool` - True if stopped, False otherwise

**Stop Sequence:**
- macOS: `brew services stop postgresql`
- Linux: `sudo systemctl stop postgresql`
- Windows: `net stop postgresql`

---

### Checking Status

```python
# Check if running
if service.is_running():
    print("PostgreSQL is running")

# Check custom port
if service.is_running(port=5433):
    print("PostgreSQL is running on port 5433")

# Get full status
status = service.status()
```

**Port Detection:**
- Delegates the TCP probe to `NetworkUtils.is_port_open()` (zComm SSOT; see [Network Guide](network_GUIDE.md))
- Returns True if connection succeeds (port in use → PostgreSQL running)
- Returns False if connection fails (port available)
- Default port: 5432

**Raises:** `ValueError` if port outside valid range (1-65535)

---

### Getting Connection Info

```python
info = service.get_connection_info()
# {
#     "host": "localhost",
#     "port": 5432,
#     "user": "postgres",
#     "database": "postgres",
#     "connection_string": "postgresql://postgres@localhost:5432/postgres"
# }
```

**Returns:** `Dict[str, Any]` with default connection details

---

### Data Directory Detection

PostgreSQL requires a data directory. The service automatically searches:

| Priority | Path | Platform |
|----------|------|----------|
| 1 | `/usr/local/var/postgresql@14` | macOS (Homebrew 14) |
| 2 | `/usr/local/var/postgres` | macOS (Homebrew) |
| 3 | `/var/lib/postgresql/data` | Linux |
| 4 | `~/.postgres` | User home |

**Validation:** Checks for `PG_VERSION` file in directory

---

## Constants Reference

### Service Identifiers

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import SERVICE_POSTGRESQL

manager.start(SERVICE_POSTGRESQL)  # "postgresql"
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
```

---

### Status Dict Keys

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import (
    STATUS_KEY_SERVICE,           # "service"
    STATUS_KEY_RUNNING,           # "running"
    STATUS_KEY_PORT,              # "port"
    STATUS_KEY_OS,                # "os"
    STATUS_KEY_CONNECTION_INFO,   # "connection_info"
    STATUS_KEY_MESSAGE,           # "message"
    STATUS_KEY_ERROR,             # "error"
)

status = manager.status("postgresql")
if status.get(STATUS_KEY_RUNNING):
    print("Service is running")
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

info = manager.get_connection_info("postgresql")
host = info[CONN_KEY_HOST]
port = info[CONN_KEY_PORT]
```

---

## Usage Patterns

### Pattern 1: Start and Connect

```python
from zOS import zOS

z = zOS()

# Start PostgreSQL
if z.comm.start_service("postgresql"):
    # Get connection info
    info = z.comm.get_service_connection_info("postgresql")
    
    # Connect to database
    import psycopg2
    conn = psycopg2.connect(
        host=info["host"],
        port=info["port"],
        user=info["user"],
        database=info["database"]
    )
    print("Connected to PostgreSQL")
else:
    print("Failed to start PostgreSQL")
```

---

### Pattern 2: Check Status Before Starting

```python
status = z.comm.service_status("postgresql")

if status.get("running"):
    print(f"PostgreSQL already running on port {status['port']}")
else:
    print("Starting PostgreSQL...")
    z.comm.start_service("postgresql")
```

---

### Pattern 3: Environment Setup Script

```python
from zOS import zOS

z = zOS()

# Check all required services
services = ["postgresql"]  # Add "redis", "mongodb" when available

for service_name in services:
    status = z.comm.service_status(service_name)
    
    if status.get("running"):
        print(f"✅ {service_name}: Running")
    else:
        print(f"❌ {service_name}: Not running")
        print(f"   Install: {status.get('message', 'N/A')}")
```

---

### Pattern 4: Restart on Configuration Change

```python
# Restart PostgreSQL after config change
if z.comm.restart_service("postgresql"):
    print("PostgreSQL restarted successfully")
else:
    print("Failed to restart PostgreSQL")
```

---

## Error Handling

### Service Not Found

```python
status = manager.status("unknown_service")
# {"error": "Unknown service: unknown_service"}

if "error" in status:
    print(f"Error: {status['error']}")
```

---

### Start Failure

```python
if not manager.start("postgresql"):
    # Check status for details
    status = manager.status("postgresql")
    if not status.get("running"):
        print(f"Installation required: {status.get('message')}")
```

---

### Invalid Service Name

```python
try:
    manager.start("")  # Empty string
except ValueError as e:
    print(f"Invalid service name: {e}")
    # "Service name cannot be empty or None"

try:
    manager.start(None)  # None
except ValueError as e:
    print(f"Invalid service name: {e}")
```

---

## Installation Requirements

### PostgreSQL Installation

**macOS (Homebrew):**
```bash
brew install postgresql
brew services start postgresql
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install postgresql
sudo systemctl start postgresql
```

**Linux (RHEL/CentOS):**
```bash
sudo yum install postgresql-server
sudo systemctl start postgresql
```

**Windows:**
- Download installer from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/)
- Run installer
- Service starts automatically

---

### zOS PostgreSQL Support

```bash
# Install zOS with PostgreSQL support
pip install git+ssh://git@github.com/ZoloAi/zolo-zcli.git[postgresql]
```

---

## Logging

### Service Manager Logs

```python
# Initialization (framework logger, DEBUG)
[ServiceManager] Initializing ServiceManager
[ServiceManager] Registering available services
[ServiceManager] Registered PostgreSQL service
[ServiceManager] ServiceManager initialized with 1 services

# Start operation (INFO)
[ServiceManager] Starting service: postgresql
[ServiceManager] Service 'postgresql' started successfully

# Stop operation (INFO)
[ServiceManager] Stopping service: postgresql
[ServiceManager] Service 'postgresql' stopped successfully

# Status query (DEBUG)
[ServiceManager] Getting status for service: postgresql
[ServiceManager] Service 'postgresql' status: {...}
```

---

### PostgreSQL Service Logs

```python
# Start success (INFO)
[PostgreSQLService] Starting PostgreSQL service...
[PostgreSQLService] [OK] PostgreSQL started via Homebrew

# Start failure (ERROR)
[PostgreSQLService] [ERROR] Could not start PostgreSQL. Install with: brew install postgresql

# Stop success (INFO)
[PostgreSQLService] Stopping PostgreSQL service...
[PostgreSQLService] [OK] PostgreSQL stopped

# Status check (DEBUG)
[PostgreSQLService] Checking port availability: 5432 on localhost
[PostgreSQLService] Port 5432 is in use
```

---

## Best Practices

### 1. Check Status Before Starting

```python
# ✅ Check first
status = z.comm.service_status("postgresql")
if not status.get("running"):
    z.comm.start_service("postgresql")

# ❌ Start blindly
z.comm.start_service("postgresql")  # Wastes time if already running
```

---

### 2. Handle Start Failures

```python
# ✅ Check return value
if z.comm.start_service("postgresql"):
    # Proceed with database operations
    pass
else:
    # Handle failure (show installation instructions)
    status = z.comm.service_status("postgresql")
    print(status.get("message"))

# ❌ Assume success
z.comm.start_service("postgresql")
# Database operations fail if start failed
```

---

### 3. Use Connection Info

```python
# ✅ Get connection info from service
info = z.comm.get_service_connection_info("postgresql")
conn = psycopg2.connect(**info)

# ❌ Hardcode connection details
conn = psycopg2.connect(host="localhost", port=5432)  # Breaks if port changes
```

---

### 4. Environment Setup Scripts

```python
# ✅ Validate environment before running app
def check_services():
    required = ["postgresql"]
    for service in required:
        status = z.comm.service_status(service)
        if not status.get("running"):
            print(f"Error: {service} not running")
            print(f"Install: {status.get('message')}")
            return False
    return True

if check_services():
    # Run application
    pass
```

---

## Integration with zComm

Access service management via zComm facade:

```python
from zOS import zOS

z = zOS()

# Start service
z.comm.start_service("postgresql")

# Stop service
z.comm.stop_service("postgresql")

# Restart service
z.comm.restart_service("postgresql")

# Get status
status = z.comm.service_status("postgresql")

# Get all services status
all_status = z.comm.service_status()

# Get connection info
info = z.comm.get_service_connection_info("postgresql")

# Access ServiceManager directly
z.comm.services.start("postgresql")
```

---

## Future Services

### Redis (Planned)

```python
# Future API (not yet implemented)
z.comm.start_service("redis")
status = z.comm.service_status("redis")
# {
#     "service": "redis",
#     "running": True,
#     "port": 6379,
#     "connection_info": {
#         "host": "localhost",
#         "port": 6379
#     }
# }
```

---

### MongoDB (Planned)

```python
# Future API (not yet implemented)
z.comm.start_service("mongodb")
info = z.comm.get_service_connection_info("mongodb")
# {
#     "host": "localhost",
#     "port": 27017,
#     "connection_string": "mongodb://localhost:27017"
# }
```

---

## See Also

- [zComm Main Guide](../zComm_GUIDE.md) - Complete zComm overview
- [HTTP Client Guide](http_GUIDE.md) - HTTP requests
- [WebSocket Guide](websocket_GUIDE.md) - Real-time communication
- [Network Utils Guide](network_GUIDE.md) - Port checking
