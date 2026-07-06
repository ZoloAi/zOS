# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/d_compounds/display_compounds_inputs.py

"""
Compound Input Operations - Interactive Widgets Facade
=======================================================

This module provides the compound inputs facade for the zDisplay subsystem.
It delegates to specialized compound input event modules.

Architecture:
    - Facade: CompoundsInputs (this file) - unified input interface
    - Events: display_event_inputs.py - interactive widgets implementation
    - Helpers: inputs/*.py - individual input helper modules

⚠️ TIER DISTINCTION ⚠️
- b_primitives: Raw I/O (read_string, read_password)
- c_basic: Simple inputs (read_bool)
- d_compounds: Interactive widgets (selection menus, sliders)

Compound Input Operations:
    - selection(): Interactive selection menus (single/multi-select)
    - button(): Confirmation buttons with explicit user action
    - read_range(): Numeric range sliders with keyboard controls

Dual-Mode I/O:
    - Terminal Mode (zCLI): Interactive text-based widgets (synchronous)
    - Bifrost Mode: WebSocket events via zComm (asynchronous Future)
    - Return Types:
        - zCLI mode: Returns selected value(s) (synchronous)
        - Bifrost mode: Returns asyncio.Future (asynchronous)

Dependencies:
    - display_event_inputs: InteractiveInputs implementation
    - c_basic: BasicInputs, BasicOutputs (foundation)
    - b_primitives: PrimitivesInputs (I/O)
"""

from zOS import Any

# Import compound input event module
from .inputs.display_event_inputs import InteractiveInputs


class CompoundsInputs:
    """Compound inputs facade - delegates to interactive widgets event module.
    
    Architecture:
        This class uses the Facade pattern to provide a unified interface to
        all compound input operations. The implementation is in display_event_inputs.py
        which handles interactive widgets with validation.
        
        Compound Input Events:
            - selection() → InteractiveInputs
            - button() → InteractiveInputs
            - read_range() → InteractiveInputs
    """

    # Type hints for instance attributes
    display: Any  # Parent zDisplay instance

    # Event module instance
    _interactive_inputs: InteractiveInputs

    def __init__(self, display_instance: Any) -> None:
        """Initialize CompoundsInputs facade with event module.
        
        Args:
            display_instance: Parent zDisplay instance (provides mode, zcli access)
        """
        self.display = display_instance

        # Instantiate event module
        self._interactive_inputs = InteractiveInputs(display_instance)

    # Compound Input Operations - Delegate to event module

    def selection(self, prompt: str, options, multi: bool = False, **kwargs):
        """Interactive selection menu - single or multi-select.
        
        Delegates to: display_event_inputs.InteractiveInputs
        """
        return self._interactive_inputs.selection(prompt, options, multi, **kwargs)

    def button(self, label: str, action = None, color: str = "primary", **kwargs):
        """Display confirmation button requiring explicit user action.
        
        Delegates to: display_event_inputs.InteractiveInputs
        """
        return self._interactive_inputs.button(label, action, color, **kwargs)

    def read_range(self, prompt: str = "", **kwargs):
        """Numeric range slider - interactive widget for value selection.
        
        Delegates to: display_event_inputs.InteractiveInputs
        """
        return self._interactive_inputs.read_range(prompt, **kwargs)
