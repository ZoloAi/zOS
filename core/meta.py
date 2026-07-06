# zOS/core/meta.py
"""
Package metadata and architecture constants for zOS.

This module is the single source of truth for package-level constants that are
re-exported from zOS/core/__init__.py.
"""

from .version import __author__, __version__

PACKAGE_NAME: str = "zOS"
PACKAGE_VERSION: str = __version__
PACKAGE_AUTHOR: str = __author__
PACKAGE_LICENSE: str = "MIT"

SUBSYSTEM_COUNT: int = 16  # v1.7.0: Removed zUtils (migrated to zLoader)
LAYER_COUNT: int = 4

MODERNIZATION_COMPLETE: bool = True
MODERNIZATION_VERSION: str = __version__
MODERNIZATION_DATE: str = "2025-01-07"
