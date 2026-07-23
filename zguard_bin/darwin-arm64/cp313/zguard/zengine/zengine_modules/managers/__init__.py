# zguard/zengine/zengine_modules/managers/__init__.py

"""
Domain managers for zWizard subsystem.

Provides specialized managers for different aspects of wizard execution:
- DataResolver: Block-level data resolution
- ConditionManager: Conditional evaluation (if statements)

Note: dispatch-fn creation, key filtering, and navigation/menu handling live
on the execution strategies (ExecutionStrategy base + per-mode executors),
not as standalone managers.
"""

from .zwizard_data import DataResolver
from .zwizard_conditions import ConditionManager

__all__ = [
    "DataResolver",
    "ConditionManager",
]
