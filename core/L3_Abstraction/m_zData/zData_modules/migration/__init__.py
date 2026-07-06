# zOS/core/L3_Abstraction/m_zData/zData_modules/migration/__init__.py
"""
Migration modules for zData subsystem.

Provides migration engine, schema discovery, and backend migration capabilities.
"""

from .migration_engine import MigrationEngine
from .schema_discovery import SchemaDiscovery
from .backend_migration import BackendMigration

__all__ = [
    'MigrationEngine',
    'SchemaDiscovery',
    'BackendMigration'
]
