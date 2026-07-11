# zGuard/zguard/zengine/zengine_modules/__init__.py
"""
zWizard Modules - Modular Components for zWizard Subsystem
===========================================================

This package contains the modular components that make up the zWizard subsystem.
The modules are organized for clarity, testability, and reusability.

Module Organization:
--------------------
### Core Components (Always Available)
1. **zwizard_hat.py**: WizardHat triple-access container (numeric, key, attribute)
2. **zwizard_interpolation.py**: zHat template variable interpolation ({{ zHat.key }})
3. **zwizard_transactions.py**: Database transaction management (commit/rollback)
4. **zengine_rbac.py**: Role-based access control enforcement
5. **zengine_exceptions.py**: Custom exception hierarchy
6. **zwizard_examples.py**: Comprehensive usage patterns and examples

### Domain Managers (Refactored Architecture - v1.5.4+)
7. **managers/zwizard_data.py**: Block-level data resolution
8. **managers/zwizard_conditions.py**: Conditional evaluation (if statements)

### Execution Strategies (Mode-Specific)
9. **execution/zengine_execution_base.py**: Shared base — dispatch fn, error handling, block extraction
10. **execution/zengine_execution_sequential.py**: zCLI sequential mode (key filtering, menu/navigation)
11. **execution/zengine_execution_chunked.py**: Bifrost chunked mode (key filtering, gate chunking)

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
- DataResolver: Block-level data resolution
- ConditionManager: Conditional evaluation

### Advanced Usage: Execution Strategies (Optional)
- SequentialExecutor: zCLI mode execution
- ChunkedExecutor: Bifrost mode execution

Usage:
------
```python
# Basic usage (public API)
from zguard.zengine.zengine_modules import (
    WizardHat,
    interpolate_zhat,
    check_transaction_start,
    WizardInitializationError,
)

# Advanced usage (managers - optional)
from zguard.zengine.zengine_modules import (
    DataResolver,
    ConditionManager,
)
```

Architecture:
------------
- **Layer**: L3 (Abstraction)
- **Position**: l_zEngine (after k_zOpen, before the L4 orchestration tier)
- **Design**: Modular, testable, industry-grade
- **Pattern**: Facade + Strategy + Manager delegation
- **Refactored**: v1.5.4+ (zConfig/zComm modular pattern)

Version: v1.5.4+ (Modular Architecture)
"""

# Layer 0: Constants (Public API)
from .zengine_constants import (
    SUBSYSTEM_NAME,
    SUBSYSTEM_COLOR,
    NAVIGATION_SIGNALS,
    RBAC_ACCESS_GRANTED,
    RBAC_ACCESS_DENIED,
    RBAC_ACCESS_DENIED_ZGUEST,
    ERR_MISSING_INSTANCE,
)

# Layer 0: zForce — the engine's typed return (SSOT classifier). Lives here, with
# the engine; the public zOS facade (l_zEngine) re-exports it.
from .zforce import (
    zForce,
    sense_force,
    OUTCOME_VOID,
    OUTCOME_OK,
    OUTCOME_FAIL,
    VECTOR_NONE,
    VEC_ZBACK,
    VEC_EXIT,
    VEC_STOP,
    VEC_NAVIGATE,
    STR_VECTORS,
    DICT_VECTOR_KEYS,
)

# Layer 1: Core Components
from .zwizard_hat import WizardHat
from .zwizard_interpolation import interpolate_zhat
from .zwizard_transactions import (
    check_transaction_start,
    commit_transaction,
    rollback_transaction,
)
from .zengine_rbac import checkzRBAC_access, display_access_denied
from .zengine_exceptions import (
    zWizardError,
    WizardInitializationError,
    WizardExecutionError,
    WizardRBACError,
)

# Layer 2: Domain Managers (Optional - Advanced Usage)
from .managers import (
    DataResolver,
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
    # zForce (typed step return + SSOT classifier)
    "zForce",
    "sense_force",
    "OUTCOME_VOID",
    "OUTCOME_OK",
    "OUTCOME_FAIL",
    "VECTOR_NONE",
    "VEC_ZBACK",
    "VEC_EXIT",
    "VEC_STOP",
    "VEC_NAVIGATE",
    "STR_VECTORS",
    "DICT_VECTOR_KEYS",
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
    "DataResolver",
    "ConditionManager",
    # Execution Strategies (Advanced API - Optional)
    "SequentialExecutor",
    "ChunkedExecutor",
]

