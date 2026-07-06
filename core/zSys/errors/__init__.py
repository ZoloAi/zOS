# zSys/errors/__init__.py
"""
Error handling subsystem for zCLI.

This module provides comprehensive error handling and runtime validation:
- Custom exceptions with actionable hints
- Interactive traceback UI via Walker
- Subsystem initialization validation

Each submodule curates its own ``__all__``; the facade re-exports them via
splat so member names live in exactly one place (E1).
"""

# pylint: disable=wildcard-import
from .validation import *
from .validation import __all__ as _validation_all
from .exceptions import *
from .exceptions import __all__ as _exceptions_all
from .traceback import *
from .traceback import __all__ as _traceback_all

__all__ = [*_validation_all, *_exceptions_all, *_traceback_all]
