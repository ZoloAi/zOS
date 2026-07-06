# zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/__init__.py

"""
Cache modules for zLoader subsystem.

This package contains all caching implementations for zLoader, organized
in a dedicated subdirectory for better maintainability and scalability.

Architecture:
    - cache_orchestrator.py: Routes cache requests to appropriate tier
    - cache_pattern.py: Shared wildcard matcher (SSOT) for all cache tiers
    - cache_system.py: UI/config file cache with LRU eviction
    - cache_pinned.py: User alias cache with no eviction
    - cache_schema.py: DB connection cache
    - cache_python_module.py: Python module cache with collision detection
    - cache_utils.py: User-facing cache utilities
"""

from .cache_orchestrator import CacheOrchestrator
from .cache_pattern import matches_pattern
from .cache_system import SystemCache
from .cache_pinned import PinnedCache
from .cache_schema import SchemaCache
from .cache_python_module import PythonModuleCache
from . import cache_utils

__all__ = [
    'CacheOrchestrator',
    'matches_pattern',
    'SystemCache',
    'PinnedCache',
    'SchemaCache',
    'PythonModuleCache',
    'cache_utils',
]
