"""
Core Module - Layer 3: Core Authentication Logic

Provides three-tier authentication and role-based access control.
Depends on: security, persistence (indirectly), zConfig, zDisplay, zComm
"""

from .authentication import Authentication
from .rbac import RBAC

__all__ = ['Authentication', 'RBAC']
