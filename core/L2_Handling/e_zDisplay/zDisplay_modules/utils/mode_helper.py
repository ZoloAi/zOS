# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/utils/mode_helper.py

"""
Mode Detection Utilities - Single Source of Truth (SSOT)
=========================================================

This module provides centralized mode detection logic for the zDisplay subsystem.
Previously, mode checking was duplicated across 28+ files with inconsistent
implementations. This module consolidates all mode detection into a single
source of truth.

Problem:
--------
Mode checking was scattered with variations:
- `if self.display._is_bifrost:`
- `if mode == 'zBifrost':`
- `if self.display.mode not in ('zCLI', 'Walker', ''):`
- `if session.get('zMode') == 'zBifrost':`

This violated DRY and made mode logic changes error-prone.

Solution:
---------
Single source of truth with two main functions:
1. is_bifrost_mode() - Boolean check for Bifrost mode
2. get_mode() - Get mode string

Both functions accept flexible inputs (display instance, session dict, or mode string)
for maximum reusability.

Usage:
------
```python
from ...utils.mode_helper import is_bifrost_mode, get_mode

# In event classes
if is_bifrost_mode(self.display):
    # GUI mode logic
else:
    # Terminal mode logic

# With session dict
mode = get_mode(session)

# Direct mode string check
if is_bifrost_mode('zBifrost'):
    # ...
```

Integration:
------------
Replace all mode checks across:
- display_primitives.py
- display_events.py
- All event packages (basic, compounds, advanced, system)
- All helper modules

Total: 28+ files with duplicate mode logic consolidated here.
"""

from zOS import Any, Dict, Optional
from zOS.zVocabulary import SESSION_KEY_ZMODE

from ..display_constants import MODE_ZCLI, MODE_BIFROST, TERMINAL_MODES


def is_bifrost_mode(context: Any) -> bool:
    """Check if running in Bifrost/GUI mode (SSOT).
    
    Single source of truth for Bifrost mode detection. Accepts flexible
    input types for maximum reusability across different contexts.
    
    Args:
        context: Can be one of:
            - Display instance with _is_bifrost attribute
            - Session dict with 'zMode' key
            - Mode string directly ('zBifrost', 'zCLI', etc.)
            - None (defaults to False)
    
    Returns:
        bool: True if in Bifrost/GUI mode, False if in terminal mode (zCLI/Walker)
    
    Terminal Modes:
        - 'zCLI': Standard terminal mode
        - 'Walker': Walker mode (also terminal-based)
        - '': Empty string (default terminal)
    
    Bifrost Modes:
        - 'zBifrost': Standard GUI mode
        - Any other non-empty string not in terminal modes
    
    Examples:
        # With display instance
        if is_bifrost_mode(self.display):
            send_websocket_event()
        
        # With session dict
        session = {'zMode': 'zBifrost'}
        if is_bifrost_mode(session):
            prepare_gui_data()
        
        # With mode string
        mode = session.get('zMode', 'zCLI')
        if is_bifrost_mode(mode):
            buffer_events()
    """
    if context is None:
        return False
    
    # Case 1: Display instance with pre-computed _is_bifrost flag
    if hasattr(context, '_is_bifrost'):
        return context._is_bifrost
    
    # Case 2: Session dict with 'zMode' key
    if isinstance(context, dict):
        mode = context.get(SESSION_KEY_ZMODE, MODE_ZCLI)
        return mode not in TERMINAL_MODES
    
    # Case 3: Mode string directly
    if isinstance(context, str):
        return context not in TERMINAL_MODES
    
    # Default: Assume terminal mode
    return False


def get_mode(context: Any) -> str:
    """Get current mode string (SSOT).
    
    Single source of truth for mode retrieval. Accepts flexible input
    types for maximum reusability.
    
    Args:
        context: Can be one of:
            - Display instance with mode attribute
            - Session dict with 'zMode' key
            - Mode string directly
            - None (defaults to 'zCLI')
    
    Returns:
        str: Mode string ('zCLI', 'zBifrost', 'Walker', etc.)
    
    Examples:
        # With display instance
        mode = get_mode(self.display)
        
        # With session dict
        session = {'zMode': 'zBifrost'}
        mode = get_mode(session)
        
        # Pass-through
        mode = get_mode('zBifrost')
    """
    if context is None:
        return MODE_ZCLI
    
    # Case 1: Display instance with mode attribute
    if hasattr(context, 'mode'):
        return context.mode
    
    # Case 2: Session dict with 'zMode' key
    if isinstance(context, dict):
        return context.get(SESSION_KEY_ZMODE, MODE_ZCLI)
    
    # Case 3: Mode string directly (pass-through)
    if isinstance(context, str):
        return context
    
    # Default: terminal mode
    return MODE_ZCLI


def is_terminal_mode(context: Any) -> bool:
    """Check if running in terminal mode (inverse of is_bifrost_mode).
    
    Convenience function for readability when checking for terminal mode.
    
    Args:
        context: Display instance, session dict, mode string, or None
    
    Returns:
        bool: True if in terminal mode (zCLI/Walker), False if in Bifrost mode
    
    Example:
        if is_terminal_mode(self.display):
            print_to_console()
    """
    return not is_bifrost_mode(context)
