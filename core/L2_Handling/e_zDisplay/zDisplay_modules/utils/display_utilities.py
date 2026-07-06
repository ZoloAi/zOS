# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/a_infrastructure/display_utilities.py

"""
Display Utilities - Re-exports for Backward Compatibility
==========================================================

This module re-exports utility functions from their individual modules.
Maintained for backward compatibility with existing imports.

Architecture:
    Tier 0: Infrastructure (THIS MODULE) - Pure utilities
    Tier 1: Primitives - Raw I/O using these utilities
    Tier 2+: Higher tiers - Use primitives + these utilities

Utilities:
    - value_formatter: Format values for display
    - system_message_filter: Check if system messages should display

Note:
    - event_id_generator moved to e_advanced/event_id_utils.py (only used by time-based widgets)
    - semantic_colors moved to c_basic/outputs/semantic_colors.py (rendering utility)
"""

from .value_formatter import format_value_for_display
from .system_message_filter import should_show_system_message

__all__ = [
    'format_value_for_display',
    'should_show_system_message',
]
