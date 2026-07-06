# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/a_infrastructure/__init__.py

"""
Tier 0 Infrastructure - Pure Utilities
=======================================

Public API for pure utility functions used by all display tiers.

Architecture:
    Infrastructure provides the BACKBONE - pure functions with no side effects
    that flow DOWN through the tier hierarchy:
    
    Infrastructure (tier 0) ← Pure utilities, no dependencies
        ↓ used by
    Primitives (tier 1) ← Raw I/O using infrastructure utilities
        ↓ used by
    Basic (tier 2) ← Formatted output using primitives + infrastructure
        ↓ used by
    Compounds (tier 3+) ← Complex widgets using lower tiers + infrastructure

Organization:
    - display_utilities: Pure utility functions (no display parameter)
        * format_value_for_display: Format values for terminal display
        * should_show_system_message: Deployment-aware message filtering (special case)

Design Principles:
    - Pure functions only (no side effects)
    - No display parameter (except should_show_system_message - special case)
    - Minimal dependencies (stdlib + zOS core only)
    - Testable in isolation
    - Reusable across all tiers

Moved to Other Tiers:
    - generate_event_id → e_advanced/event_id_utils.py (only used by time-based widgets)
    - get_semantic_color → c_basic/outputs/semantic_colors.py (rendering utility)
    - is_bifrost_mode() → moved to zPrimitives
    - emit_websocket_event() → moved to zPrimitives
    - try_gui_event() → moved to zPrimitives
    - render_field() → moved to BasicOutputs.FieldRenderer
    - render_section_title() → moved to BasicOutputs.FieldRenderer
    - get_display_logger() → moved to event classes (_get_logger method)
"""

from .display_utilities import (
    format_value_for_display,
    should_show_system_message,
)

__all__ = [
    'format_value_for_display',
    'should_show_system_message',
]
