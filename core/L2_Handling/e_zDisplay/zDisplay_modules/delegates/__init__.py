# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/delegates/__init__.py

"""
Convenience Delegates Package
==============================

Contains mixin classes with convenience delegate methods for zEvents.
Extracted from display_events.py to improve maintainability and reduce file size.
"""

from .delegate_outputs_signals import OutputSignalDelegates
from .delegate_widgets_media import WidgetMediaDelegates

__all__ = ['OutputSignalDelegates', 'WidgetMediaDelegates']
