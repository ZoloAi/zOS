# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/resolvers/__init__.py

"""
Data Resolvers for zDispatch Subsystem.

Components:
    - UIResolver: zUI key resolution for Bifrost mode

(The former DataResolver moved to the zLoom subsystem — reach it via ``zos.zloom``.)
"""

from .resolver_ui import UIResolver

__all__ = ['UIResolver']
