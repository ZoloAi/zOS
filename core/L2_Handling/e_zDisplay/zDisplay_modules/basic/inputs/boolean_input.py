# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/c_basic/inputs/boolean_input.py

"""
BooleanInput - Basic Boolean Input Handler
===========================================

Basic boolean input for yes/no prompts.
Moved from d_compounds to c_basic (proper architectural placement).

This is a BASIC input type - boolean is a fundamental data type:
- Simple y/n validation
- Checkbox UI rendering (☐/☑ icons)
- Supports default values and disabled states
- Uses primitives internally (input(), print())

Architecture:
    Layer: c_basic (Basic I/O Events)
    Uses: Terminal input() and print() (true primitives)
    Contrast: d_compounds has complex widgets (selection menus, sliders)
"""

from zOS import Any, Union, time

from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    _EVENT_READ_BOOL,
    _KEY_EVENT,
    _KEY_REQUEST_ID,
    _KEY_PROMPT,
    _KEY_TIMESTAMP,
    _DEFAULT_PROMPT,
    _VALID_BOOL_INPUTS,
)


class BooleanInput:
    """Basic boolean input handler for yes/no prompts."""

    display: Any
    zPrimitives: Any

    def __init__(self, display_instance: Any) -> None:
        """Initialize BooleanInput with parent display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives

    def _read_raw(self, prompt: str, **meta) -> str:
        """Raw IO hook — patched by sandbox to intercept without touching validation."""
        return input(prompt)

    def read_bool(self, prompt: str = _DEFAULT_PROMPT, **kwargs) -> Union[bool, str]:
        """Read boolean input - terminal (synchronous) or GUI (buffered event).
        
        Basic boolean input for yes/no prompts:
            - Terminal mode: Returns bool directly (synchronous y/n prompt)
            - Bifrost mode: Buffers read_bool event, returns empty string (non-blocking)
        
        Args:
            prompt: Prompt text to display (default: empty string)
            **kwargs: Additional parameters for Bifrost mode (ignored in Terminal):
                - checked: Default checked state (True/False, default: False)
                - required: Whether checkbox is required (default: False)
                - label: Alternative to prompt for consistency
        
        Returns:
            Union[bool, str]: 
                - bool if in zCLI mode (actual user choice)
                - str if in Bifrost mode (empty string, checkbox rendered on frontend)
        
        Notes:
            - Terminal: Displays checkbox icon (☐/☑) + y/n prompt
            - Bifrost: Buffers read_bool event for frontend checkbox rendering
            - zCLI mode ignores 'checked' default (always starts unchecked in prompt)
            - Strips whitespace and accepts y/yes for True, everything else False
        
        Example:
            result = boolean_input.read_bool("Subscribe to newsletter?", checked=False)
            # Terminal: ☐ Subscribe to newsletter? (y/n): y → Returns True
            # Bifrost: Returns "" (checkbox rendered on frontend)
        """
        # Terminal input (always available as fallback)
        if not self.zPrimitives.is_bifrost_mode():
            # Get checkbox state from kwargs (default False)
            checked = kwargs.get('checked', False)
            disabled = kwargs.get('disabled', False)

            # Handle disabled state - display only, no input
            if disabled:
                display_text = f"{prompt} [DISABLED]" if prompt else "[DISABLED]"
                print(display_text)
                return checked

            # Build terminal prompt with default hint
            default_hint = " [Y]" if checked else " [N]"
            if prompt:
                terminal_prompt = f"{prompt} (y/n){default_hint}: "
            else:
                terminal_prompt = f"(y/n){default_hint}: "

            required = kwargs.get('required', False)

            while True:
                response = self._read_raw(terminal_prompt, **kwargs).strip().lower()

                if response not in _VALID_BOOL_INPUTS:
                    self.display.error("Invalid input — please enter 'y' or 'n'.")
                    continue

                result = response in ('y', 'yes') if response else checked

                if required and not result:
                    self.display.error("This field is required — please confirm with 'y'.")
                    continue

                return result

        # Bifrost mode - buffer read_bool event and return empty string
        # The frontend will render the checkbox and handle user interaction
        request_id = self.zPrimitives._generate_request_id()  # pylint: disable=protected-access

        # Support both 'prompt' and 'label' (label takes precedence for consistency)
        display_label = kwargs.get('label', prompt)

        request_event = {
            _KEY_EVENT: _EVENT_READ_BOOL,
            _KEY_REQUEST_ID: request_id,
            _KEY_PROMPT: display_label,
            _KEY_TIMESTAMP: time.time(),
            'checked': kwargs.get('checked', False),
            'required': kwargs.get('required', False),
            'disabled': kwargs.get('disabled', False)
        }

        # Buffer the checkbox request
        if self.display and hasattr(self.display, 'buffer_event'):
            self.display.buffer_event(request_event)

        # Return empty string (wizard continues, frontend handles checkbox)
        return ""
