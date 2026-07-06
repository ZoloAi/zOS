# zOS/core/L3_Abstraction/l_zWizard/zWizard_modules/__init__.py
"""
zWizard Modules - Modular Components for zWizard Subsystem
===========================================================

This package contains the modular components that make up the zWizard subsystem.
The modules are organized for clarity, testability, and reusability.

Module Organization:
--------------------
### Core Components (Always Available)
1. **wizard_hat.py**: WizardHat triple-access container (numeric, key, attribute)
2. **wizard_interpolation.py**: zHat template variable interpolation ({{ zHat.key }})
3. **wizard_transactions.py**: Database transaction management (commit/rollback)
4. **wizard_rbac.py**: Role-based access control enforcement
5. **wizard_exceptions.py**: Custom exception hierarchy
6. **wizard_examples.py**: Comprehensive usage patterns and examples

### Domain Managers (Refactored Architecture - v1.5.4+)
7. **managers/wizard_navigation.py**: Navigation signals, breadcrumbs, menu looping
8. **managers/wizard_dispatch.py**: Dispatch function creation and routing
9. **managers/wizard_data.py**: Block-level data resolution
10. **managers/wizard_filters.py**: Key filtering, shorthand expansion
11. **managers/wizard_conditions.py**: Conditional evaluation (if statements)

### Execution Strategies (Mode-Specific)
12. **execution/wizard_execution_sequential.py**: zCLI sequential mode
13. **execution/wizard_execution_chunked.py**: Bifrost chunked mode

Exported Components:
-------------------
### Classes
- WizardHat: Triple-access results container
- zWizardError: Base exception class
- WizardInitializationError: Initialization failures
- WizardExecutionError: Execution failures
- WizardRBACError: Access control violations

### Functions
- interpolate_zhat(): Template variable interpolation
- check_transaction_start(): Detect transaction start
- commit_transaction(): Commit active transaction
- rollback_transaction(): Rollback on error
- checkzRBAC_access(): Enforce RBAC before step execution
- display_access_denied(): Display access denial messages

### Advanced Usage: Managers (Optional)
- NavigationManager: Navigation signal handling
- DispatchManager: Dispatch function creation
- DataResolver: Block-level data resolution
- FilterManager: Key filtering and shorthand expansion
- ConditionManager: Conditional evaluation

### Advanced Usage: Execution Strategies (Optional)
- SequentialExecutor: zCLI mode execution
- ChunkedExecutor: Bifrost mode execution

Usage:
------
```python
# Basic usage (public API)
from zwizard.zWizard_modules import (
    WizardHat,
    interpolate_zhat,
    check_transaction_start,
    WizardInitializationError,
)

# Advanced usage (managers - optional)
from zwizard.zWizard_modules import (
    NavigationManager,
    DispatchManager,
    DataResolver,
)
```

Architecture:
------------
- **Layer**: 2 (Orchestration)
- **Position**: 2 (After zUtils, before zData/zShell)
- **Design**: Modular, testable, industry-grade
- **Pattern**: Facade + Strategy + Manager delegation
- **Refactored**: v1.5.4+ (zConfig/zComm modular pattern)

Version: v1.5.4+ (Modular Architecture)
"""

# Layer 0: Constants (Public API)
from .wizard_constants import (
    SUBSYSTEM_NAME,
    SUBSYSTEM_COLOR,
    NAVIGATION_SIGNALS,
    RBAC_ACCESS_GRANTED,
    RBAC_ACCESS_DENIED,
    RBAC_ACCESS_DENIED_ZGUEST,
    ERR_MISSING_INSTANCE,
)

# Layer 1: Core Components
from .wizard_hat import WizardHat
from .wizard_interpolation import interpolate_zhat
from .wizard_transactions import (
    check_transaction_start,
    commit_transaction,
    rollback_transaction,
)
from .wizard_rbac import checkzRBAC_access, display_access_denied
from .wizard_exceptions import (
    zWizardError,
    WizardInitializationError,
    WizardExecutionError,
    WizardRBACError,
)

# Layer 2: Domain Managers (Optional - Advanced Usage)
from .managers import (
    NavigationManager,
    DispatchManager,
    DataResolver,
    FilterManager,
    ConditionManager,
)

# Layer 3: Execution Strategies (Optional - Advanced Usage)
from .execution import (
    SequentialExecutor,
    ChunkedExecutor,
)

__all__ = [
    # Public Constants
    "SUBSYSTEM_NAME",
    "SUBSYSTEM_COLOR",
    "NAVIGATION_SIGNALS",
    "RBAC_ACCESS_GRANTED",
    "RBAC_ACCESS_DENIED",
    "RBAC_ACCESS_DENIED_ZGUEST",
    "ERR_MISSING_INSTANCE",
    # Classes & Functions (Core API)
    "WizardHat",
    "interpolate_zhat",
    "check_transaction_start",
    "commit_transaction",
    "rollback_transaction",
    "checkzRBAC_access",
    "display_access_denied",
    "zWizardError",
    "WizardInitializationError",
    "WizardExecutionError",
    "WizardRBACError",
    # Managers (Advanced API - Optional)
    "NavigationManager",
    "DispatchManager",
    "DataResolver",
    "FilterManager",
    "ConditionManager",
    # Execution Strategies (Advanced API - Optional)
    "SequentialExecutor",
    "ChunkedExecutor",
]

