# zLoader Schema Cache Module Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_schema.py`  
> **Purpose:** Database connection caching with transaction management.

---

## Overview

The `cache_schema` module provides the Schema Cache implementation (Tier 2) for zLoader's caching system. It is optimized for database connections with transaction support.

| Class | File | Purpose |
|---|---|---|
| `SchemaCache` | `cache/cache_schema.py` | DB connection cache with transactions |

---

## Key Features

**Database Connections:**
- Cache expensive database connections
- Connection pooling support
- Session-based lifetime

**Transaction Management:**
- Begin/commit/rollback support
- Nested transaction handling
- Transaction isolation

**Use Cases:**
- Database schema loading
- Connection pooling
- Transaction coordination

---

## Architecture: Tier 2 Cache Implementation

`SchemaCache` serves as Tier 2 in the zLoader architecture, implementing DB connection caching:

```
SchemaCache (Tier 2)
├── Connection Caching   — Reuse DB connections
├── Transaction Support  — Begin/commit/rollback
├── Session-based        — Per-session lifetime
└── Statistics           — Track connections, transactions
```

---

## Method Reference

> Keyed by `alias_name` (the connection alias). Constructor: `SchemaCache(session, logger)`.

### Connections

| Method | Purpose |
|---|---|
| `get_connection(alias_name)` | Get a cached handler/connection, or `None` |
| `set_connection(alias_name, handler)` | Cache a connection handler |
| `has_connection(alias_name)` | `True` / `False` |
| `disconnect(alias_name)` | Close + remove a single connection |
| `clear()` | Close and remove **all** connections (no pattern support) |
| `list_connections()` | `List[Dict]` describing active connections |

### Transactions

| Method | Purpose |
|---|---|
| `begin_transaction(alias_name)` | Begin a transaction on the connection |
| `commit_transaction(alias_name)` | Commit the active transaction |
| `rollback_transaction(alias_name)` | Roll back the active transaction |
| `is_transaction_active(alias_name)` | `True` if a transaction is in progress |

> The orchestrator's `get_stats("schema")` derives `{namespace, active_connections, connections}` from `list_connections()` — `SchemaCache` has no `get_stats()` of its own. There is no pattern-based `clear` for this tier.

---

## Integration Points

**Used By:**
- CacheOrchestrator (`cache_orchestrator.py`) - Routes schema cache requests
- zData subsystem - Database operations

**Architecture Position:**
- Tier 2 (Cache Implementation) - Provides DB connection caching

---

## See Also

- [orchestrator_GUIDE.md](orchestrator_GUIDE.md) - Cache orchestrator (Tier 3)
- [cache_system_GUIDE.md](cache_system_GUIDE.md) - System cache (UI/config)
- [cache_pinned_GUIDE.md](cache_pinned_GUIDE.md) - Pinned cache (aliases)
- [cache_plugin_GUIDE.md](cache_plugin_GUIDE.md) - Plugin cache (modules)
