# zOS/core/L3_Abstraction/m_zData/zData_modules/__init__.py
"""
Internal modules for the zData subsystem.

This package contains the internal implementation modules for zData's data
management functionality, following the facade orchestrator pattern used by zBifrost.

Package Structure
----------------
**Core Orchestration:**
- **orchestrator.py**: DataOrchestrator - coordinates all managers
- **schema_manager.py**: SchemaManager - schema loading and validation
- **connection_manager.py**: ConnectionManager - adapter initialization
- **request_handler.py**: RequestHandler - request routing and execution
- **lifecycle_manager.py**: LifecycleManager - connection cleanup

**Migration:**
- **migration/**: Schema migration modules
  - migration_engine.py: Declarative migrations
  - schema_discovery.py: Automatic schema discovery
  - backend_migration.py: Backend type changes

**shared/**:
The implementation layer containing all zData infrastructure:

- **parsers/**: WHERE clause and value type parsing
- **validator.py**: 5-layer validation architecture
- **operations/**: CRUD and DDL operation handlers
- **backends/**: Database adapters (SQLite, PostgreSQL, CSV)
- **data_operations.py**: Central facade for operation routing

Architecture (Facade Orchestrator Pattern)
------------------------------------------
```
zData.py (lightweight facade ~300 lines)
    ↓
DataOrchestrator (core orchestration)
    ├── SchemaManager
    ├── ConnectionManager
    ├── RequestHandler
    ├── LifecycleManager
    └── MigrationEngine
    ↓
shared/ (operations, validators, backends)
```

This follows the same pattern as zBifrost for consistency and maintainability.

Usage Pattern
------------
External code should use the zData.py facade, not import from zData_modules directly.

Correct usage (via facade):
    >>> from zOS import zOS
    >>> z = zCLI()
    >>> z.data.load_schema("myschema.yaml")
    >>> z.data.insert("users", {"name": "Alice", "age": 30})

Integration
----------
zData_modules is used by:
- **zData.py**: Main facade that delegates to DataOrchestrator
- **zLoader**: Schema loading and caching
- **zOpen**: Direct database file operations
- **zWizard**: Multi-step data collection workflows

See Also
--------
- zData.py: Main facade for data operations
- orchestrator.py: Core orchestration logic
- shared/: Implementation modules (parsers, validators, operations, backends)
- migration/: Schema migration modules
"""

from .orchestrator import DataOrchestrator
from .schema_manager import SchemaManager
from .connection_manager import ConnectionManager
from .request_handler import RequestHandler
from .lifecycle_manager import LifecycleManager

__all__ = [
    'DataOrchestrator',
    'SchemaManager',
    'ConnectionManager',
    'RequestHandler',
    'LifecycleManager'
]
