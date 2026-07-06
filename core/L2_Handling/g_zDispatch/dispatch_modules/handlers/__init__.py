# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/handlers/__init__.py

"""
Subsystem Handlers for zDispatch Subsystem.

This package provides handlers that delegate to specific zOS subsystems
(zAuth, zData, zNavigation, zFunc, zDialog, etc.).

Components:
    - AuthHandler: zLogin/zLogout routing to zAuth
    - CRUDHandler: Generic CRUD detection and routing
    - DataHandler: zRead/zData operations
    - NavigationHandler: zLink/zDelta routing to zNavigation
    - SubsystemRouter: General subsystem command routing
"""

from .handler_auth import AuthHandler
from .handler_crud import CRUDHandler
from .handler_data import DataHandler
from .handler_navigation import NavigationHandler
from .handler_subsystems import SubsystemRouter

__all__ = ['AuthHandler', 'CRUDHandler', 'DataHandler', 'NavigationHandler', 'SubsystemRouter']
