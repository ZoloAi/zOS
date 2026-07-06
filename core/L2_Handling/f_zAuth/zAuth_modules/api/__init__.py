# zOS/core/L2_Handling/d_zAuth/zAuth_modules/api/__init__.py

"""
API Delegates Module - User-Facing Convenience Methods for zAuth

This module provides delegate mixins for the zAuth facade following zDisplay's
proven delegate pattern. The delegates organize the public API surface into
focused categories.

Delegate Categories:
    - DelegatePassword: Password hashing/verification (2 methods)
    - DelegateSession: zSession authentication (5 methods)
    - DelegateApplication: Multi-app authentication (3 methods)
    - DelegateContext: Context switching (2 methods)
    - DelegateRBAC: Role and permission checks (4 methods)

Pattern:
    Each delegate is a mixin class that provides methods delegating to the
    appropriate internal module (password_security, authentication, rbac).
    
    The zAuthDelegates class (in auth_delegates.py) composes all delegates
    using multiple inheritance, then zAuth inherits from zAuthDelegates.

Benefits:
    - Optimal file sizes (80-220 lines per delegate)
    - Clear single responsibility per delegate
    - Easy to extend with new delegate categories
    - Matches zDisplay's proven architecture
    - Reduces main zAuth.py from 1190 → ~200 lines
"""

from .delegate_password import DelegatePassword
from .delegate_session import DelegateSession
from .delegate_application import DelegateApplication
from .delegate_context import DelegateContext
from .delegate_rbac import DelegateRBAC

__all__ = [
    'DelegatePassword',
    'DelegateSession',
    'DelegateApplication',
    'DelegateContext',
    'DelegateRBAC',
]
