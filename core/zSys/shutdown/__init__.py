# zSys/shutdown/__init__.py
"""
Shutdown utilities for the zOS engine.
"""

from .cleanup import perform_shutdown
from .signals import register_signal_handlers

# Re-export the full shutdown vocabulary without re-typing it (SSOT lives in
# shutdown_constants.__all__).
# pylint: disable=wildcard-import,unused-wildcard-import
from .shutdown_constants import *  # noqa: F401,F403
from .shutdown_constants import __all__ as _const_all

__all__ = ["perform_shutdown", "register_signal_handlers", *_const_all]
