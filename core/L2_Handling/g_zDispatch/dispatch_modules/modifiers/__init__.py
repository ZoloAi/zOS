# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/modifiers/__init__.py

"""
Modifier Implementations for zDispatch Subsystem.

This package provides individual modifier logic for command behavior modification.

Modifiers:
    - MenuModifier: * (asterisk) - Create menu from data
    - CrumbsRewindModifier: ^ (caret suffix) - bulk-rewind to a zPath crumb
    - AnchorModifier: ~ (tilde) - Disable back navigation

`!` (RequiredModifier) is RETIRED — gating is an event (zBtn/zDialog), not a modifier.

Each modifier encapsulates specific behavior patterns for command routing.
"""

from .modifier_menu import MenuModifier
from .modifier_crumbs import CrumbsRewindModifier

__all__ = ['MenuModifier', 'CrumbsRewindModifier']
