# zData Orchestrator Module Guide

> **Module:** `zOS/core/L3_Abstraction/m_zData/zData_modules/orchestrator.py`  
> **Purpose:** Core orchestration logic coordinating schema, connection, request handling, and lifecycle management.

---

## Overview

The `orchestrator` module provides the `DataOrchestrator` class - the central coordination hub for all zData operations. It follows the facade-orchestrator pattern used by zBifrost.

---

## Architecture

```
DataOrchestrator
├── SchemaManager: Schema loading and validation
├── ConnectionManager: Adapter initialization
├── RequestHandler: Request routing and execution
├── LifecycleManager: Connection state and cleanup
└── MigrationEngine: Schema migrations
```

**Design Pattern:** Lazy initialization - managers are created on first use to avoid circular dependencies and improve startup performance.

---

## Responsibilities

The orchestrator coordinates:

1. **Manager Initialization** - Lazy-load specialized managers
2. **Request Delegation** - Route requests to appropriate handlers
3. **State Management** - Track schema, adapter, validator, operations
4. **Error Handling** - Graceful degradation with logging
5. **Wizard Mode** - Persistent connections vs one-shot mode

---

## Class: DataOrchestrator

### Initialization

```python
from zData_modules.orchestrator import DataOrchestrator

orchestrator = DataOrchestrator(zos=z, logger=z.logger, session=z.session)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `zos` | `Any` | zOS framework instance (required) |
| `logger` | `Any` | Logger instance (required) |
| `session` | `dict` | Session dict from zOS (required) |

**Raises:** `ValueError` if any parameter is None.

---

## Public Methods

### handle_request()

Route and execute data operation requests.

```python
result = orchestrator.handle_request(request, context={})
```

**Parameters:**
- `request` (dict): Request with model, action, data, where, etc.
- `context` (dict): Optional context (wizard_mode, schema_cache)

**Returns:** Operation result or error dict

**Example:**
```python
request = {
    "model": "@.zSchema.users",
    "action": "read",
    "where": "name = 'Alice'"
}
result = orchestrator.handle_request(request)
```

---

### open_schema()

Open schema file in editor.

```python
success = orchestrator.open_schema(model_path)
```

**Parameters:**
- `model_path` (str): Schema path (e.g., "@.zSchema.users")

**Returns:** `True` if opened successfully, `False` otherwise

---

### open_csv()

Open CSV file in editor or viewer.

```python
success = orchestrator.open_csv(csv_path)
```

**Parameters:**
- `csv_path` (str): CSV file path

**Returns:** `True` if opened successfully, `False` otherwise

---

## Connection Modes

### One-Shot Mode (Default)

Connections are created and closed for each request:

```python
request = {"model": "@.zSchema.users", "action": "read"}
result = orchestrator.handle_request(request)
# Connection closed automatically after request
```

**Use case:** Simple scripts, CLI commands, one-time operations.

---

### Wizard Mode (Persistent)

Connections stay alive across multiple requests:

```python
context = {
    "wizard_mode": True,
    "schema_cache": {}  # Shared cache across requests
}

# First request creates connection
request1 = {"model": "@.zSchema.users", "action": "read"}
result1 = orchestrator.handle_request(request1, context)

# Second request reuses connection
request2 = {"model": "@.zSchema.users", "action": "insert", "data": {...}}
result2 = orchestrator.handle_request(request2, context)

# Connection stays alive for more operations
```

**Use case:** Interactive sessions, zWalker navigation, zWizard workflows.

---

## State Management

The orchestrator maintains state for efficient operation:

```python
# Internal state attributes
orchestrator.schema          # Current schema dict
orchestrator.adapter         # Active backend adapter
orchestrator.validator       # Schema validator instance
orchestrator.operations      # Operations facade instance
orchestrator._connected      # Connection status flag
```

**State lifecycle:**
1. First request loads schema
2. Adapter initialized for backend
3. Validator created with schema
4. Operations facade initialized
5. Subsequent requests reuse state (wizard mode)
6. Cleanup on disconnect or error

---

## Manager Access

Access specialized managers directly:

```python
# Schema operations
schema_manager = orchestrator.schema_manager
schema = schema_manager.load_schema(model_path)

# Connection operations
connection_manager = orchestrator.connection_manager
adapter_result = connection_manager.initialize_adapter(schema, zos)

# Request operations
request_handler = orchestrator.request_handler
result = request_handler.execute_request(request, orchestrator)

# Lifecycle operations
lifecycle_manager = orchestrator.lifecycle_manager
lifecycle_manager.cleanup_connection(adapter)
```

---

## Error Handling

All operations include graceful error handling:

```python
try:
    result = orchestrator.handle_request(request)
    if result.get("error"):
        print(f"Error: {result['message']}")
except Exception as e:
    print(f"Unexpected error: {e}")
    # Error logged automatically to framework logger
```

**Error patterns:**
- Schema not found → Returns error dict with message
- Connection failed → Returns error dict with details
- Invalid request → Returns error dict with validation message
- Backend error → Returns error dict with backend-specific info

---

## Integration with zOS

The orchestrator integrates seamlessly with zOS subsystems:

**zDisplay Integration:**
```python
# Request announcements (via RequestHandler)
z.display.zDeclare("zData Request", color="ZCRUD")
```

**zLoader Integration:**
```python
# Schema loading (via SchemaManager)
schema = z.loader.load(model_path)
```

**zLogger Integration:**
```python
# Framework logging
z.logger.framework.debug("[DataOrchestrator] Request executed")
```

---

## Best Practices

### 1. Use Wizard Mode for Interactive Sessions

```python
# Good: Wizard mode for multiple operations
context = {"wizard_mode": True, "schema_cache": {}}
for request in requests:
    result = orchestrator.handle_request(request, context)
```

### 2. One-Shot Mode for Scripts

```python
# Good: One-shot for simple scripts
result = orchestrator.handle_request(request)
```

### 3. Check Results for Errors

```python
# Good: Always check for errors
result = orchestrator.handle_request(request)
if result.get("error"):
    handle_error(result)
```

### 4. Let Orchestrator Manage State

```python
# Good: Let orchestrator manage connections
result = orchestrator.handle_request(request)

# Bad: Don't manage adapters manually
# adapter = create_adapter(...)  # Don't do this
```

---

## Performance Considerations

**Lazy Loading:**
- Managers created on first use only
- Reduces startup time
- Avoids circular dependencies

**Connection Reuse:**
- Wizard mode reuses connections
- Avoids reconnection overhead
- Reduces database load

**State Caching:**
- Schema cached in wizard mode
- Validator reused across requests
- Operations facade shared

---

## See Also

- [schema_manager_GUIDE.md](schema_manager_GUIDE.md) - Schema loading and validation
- [connection_manager_GUIDE.md](connection_manager_GUIDE.md) - Adapter initialization
- [request_handler_GUIDE.md](request_handler_GUIDE.md) - Request routing
- [lifecycle_manager_GUIDE.md](lifecycle_manager_GUIDE.md) - Connection cleanup
- [migration_GUIDE.md](migration_GUIDE.md) - Schema migrations

---

**[← Back to zData Guide](../zData_GUIDE.md)**
