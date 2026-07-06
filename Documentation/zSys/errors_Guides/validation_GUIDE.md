# zSys Errors — Validation Guide

> **Module:** `core/zSys/errors/validation.py`
> **Purpose:** A tiny runtime guard that catches subsystem **initialization-order** bugs early, with a clear message instead of a downstream `AttributeError`.

**[← Back to Errors Guide](../errors_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

Subsystems are constructed with a reference to the live `zos` instance. If wiring order is wrong, a subsystem can receive `None` (or a half-built `zos` without a `session`), and the failure surfaces much later as a confusing `AttributeError`. `validate_zos_instance` fails **fast and legibly** at the point of construction instead.

```python
def validate_zos_instance(zos, subsystem_name, require_session=True):
    if zos is None:
        raise ValueError(f"{subsystem_name} received None for zOS instance. …init order issue…")
    if require_session and not hasattr(zos, 'session'):
        raise ValueError(f"{subsystem_name} requires zOS instance with 'session'. …")
```

---

## Usage

Call it first thing in a subsystem constructor:

```python
from zSys.errors import validate_zos_instance

class zNavigation:
    def __init__(self, zos):
        validate_zos_instance(zos, "x_zNavigation")   # raises ValueError on None / no session
        self.zos = zos
```

| Param | Meaning |
|-------|---------|
| `zos` | the instance to validate |
| `subsystem_name` | used in the error message so the culprit is obvious |
| `require_session` | when `True` (default), also asserts the instance has a `session` attribute |

`validate_zcli_instance` is a **back-compat alias** for the same function; both are in the module's `__all__` and re-exported by the facade (E1).

---

## Trust notes

- **No exec / no network / no file-write.** Two identity/`hasattr` checks raising stdlib `ValueError`.
- **No foreign content** — operates only on the `zos` reference passed in.
- Deliberately uses plain `ValueError` (not `zCLIException`): this runs during early wiring, *before* `zTraceback` may exist, so it must not depend on the richer error path.

**[← Back to Errors Guide](../errors_GUIDE.md) | [Home](../../../README.md)**
