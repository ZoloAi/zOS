# zOS/core/L3_Abstraction/l_zWizard/zWizard_modules/managers/__init__.py

"""
Domain managers for zWizard subsystem.

Provides specialized managers for different aspects of wizard execution:
- NavigationManager: Navigation signals, breadcrumbs, menu looping
- DispatchManager: Dispatch function creation and routing
- DataResolver: Block-level data resolution
- FilterManager: Key filtering and shorthand expansion
- ConditionManager: Conditional evaluation (if statements)
"""

from .wizard_navigation import NavigationManager
from .wizard_dispatch import DispatchManager
from .wizard_data import DataResolver
from .wizard_filters import FilterManager
from .wizard_conditions import ConditionManager

__all__ = [
    "NavigationManager",
    "DispatchManager",
    "DataResolver",
    "FilterManager",
    "ConditionManager",
]
