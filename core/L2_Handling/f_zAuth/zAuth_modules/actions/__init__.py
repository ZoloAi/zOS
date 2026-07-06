"""
Actions Module - Layer 3: Declarative Authentication Actions

Provides built-in action handlers for zLogin and zLogout.
Depends on: core (authentication)
"""

from .action_login import handle_zLogin
from .action_logout import handle_zLogout

__all__ = ['handle_zLogin', 'handle_zLogout']
