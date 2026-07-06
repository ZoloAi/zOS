# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/c_basic/display_basic_inputs.py

"""
BasicInputs - Basic Input Operations for zDisplay
==================================================

This event package provides basic input operations, specifically boolean input
for yes/no prompts. This is distinct from d_compounds which handles complex
interactive widgets (selection menus, sliders, etc.).

Architecture
------------
BasicInputs is part of the c_basic tier:

Layer 3: display_delegates.py (PRIMARY API)
    ↓
Layer 2: display_events.py (ORCHESTRATOR)
    ↓
Layer 2: events/display_event_inputs.py (BasicInputs) ← THIS MODULE
    ↓
Layer 2: inputs/*.py (HELPER MODULES)
    ↓
Layer 1: display_primitives.py (FOUNDATION I/O)

Module Decomposition
--------------------
Helper modules in inputs/ directory:

1. **BooleanInput** - Boolean input logic
   - Simple y/n validation
   - Checkbox UI rendering
   - Default values and disabled states

Basic vs. Interactive
---------------------
**c_basic/BasicInputs:**
- Simple, fundamental input types
- Boolean (yes/no)
- Direct primitive wrappers with minimal logic

**d_compounds/InteractiveInputs:**
- Complex interactive widgets
- Multi-option selection menus
- Numeric range sliders
- Link handlers

Methods
-------
BasicInputs provides 1 fundamental input method:

1. **read_bool(prompt, checked, required, disabled)** - Boolean yes/no input
   - Terminal: Checkbox icon + y/n prompt
   - Bifrost: Buffers checkbox event for frontend
   - Returns bool in terminal, empty string in GUI

Example
-------
```python
# Via display_events orchestrator:
events = zEvents(display_instance)
result = events.BasicInputs.read_bool("Subscribe to newsletter?", checked=False)

# Direct usage (rare):
basic_inputs = BasicInputs(display_instance)
result = basic_inputs.read_bool("Enable notifications?")
```

Version Info
------------
Created: Week 6.5 (Architectural refactoring - moved read_bool from d_compounds)
"""

from zOS import Any, Union

from .inputs.boolean_input import BooleanInput


class BasicInputs:
    """Basic input operations facade for c_basic tier."""

    display: Any
    BooleanInput: "BooleanInput"

    def __init__(self, display_instance: Any) -> None:
        """Initialize BasicInputs with parent display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance

        # Initialize helper modules
        self.BooleanInput = BooleanInput(display_instance)

    def read_bool(self, prompt: str = "", **kwargs) -> Union[bool, str]:
        """Read boolean input - basic yes/no prompt.
        
        Delegates to BooleanInput for implementation.
        This is a BASIC input type - boolean is a fundamental data type.
        
        Args:
            prompt: Prompt text to display
            **kwargs: Additional parameters (checked, required, disabled)
        
        Returns:
            Union[bool, str]: bool in terminal mode, empty string in Bifrost mode
        
        Example:
            result = inputs.read_bool("Subscribe to newsletter?", checked=False)
        """
        return self.BooleanInput.read_bool(prompt, **kwargs)
