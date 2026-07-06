# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/b_primitives/display_primitives_inputs.py

"""
Primitive Input Operations - Foundation Layer Facade
=====================================================

This module provides the input primitives facade for the zDisplay subsystem.
It delegates to specialized input primitive modules in the inputs/ subdirectory.

Architecture:
    - Facade: PrimitivesInputs (this file) - unified input interface
    - Inputs: inputs/input_*.py - individual input implementations
    - Each primitive is self-contained in its own file

⚠️ CRITICAL: DO NOT ADD COMPOUND OPERATIONS TO THIS TIER ⚠️

Input Primitives:
    - read_string(prompt): Read text input
    - read_password(prompt): Read masked password input

Exclusive Mode I/O:
    - Terminal Mode (zCLI): Direct console input via input/getpass (synchronous)
    - Bifrost Mode: WebSocket events via zComm (buffered events, returns empty string)
    - Mode is resolved once at init (not per-call)
    - Return Types:
        - zCLI mode: Returns str (synchronous)
        - Bifrost mode: Returns str (empty, input handled by frontend)

Dependencies:
    - inputs/: Input primitive implementations
    - a_infrastructure: is_bifrost_mode helper
"""

from zOS import Any

# Import primitive input modules
from .inputs import (
    StringInput,
    PasswordInput,
)


class PrimitivesInputs:
    """Input primitives facade - delegates to specialized input modules.
    
    Architecture:
        This class uses the Facade pattern to provide a unified interface to
        all primitive input operations. Each operation is implemented in its own
        module under inputs/ for scalability and management.
        
        Input Primitives (inputs/):
            - read_string() → StringInput
            - read_password() → PasswordInput
    """

    # Type hints for instance attributes
    display: Any  # Parent zDisplay instance

    # Primitive module instances
    _string_input: StringInput
    _password_input: PasswordInput

    def __init__(self, display_instance: Any) -> None:
        """Initialize PrimitivesInputs facade with specialized input modules.
        
        Args:
            display_instance: Parent zDisplay instance (provides mode, zcli access)
        """
        self.display = display_instance

        # Instantiate input primitive modules with pre-computed mode flag
        is_bifrost = display_instance._is_bifrost
        self._string_input = StringInput(display_instance, is_bifrost)
        self._password_input = PasswordInput(display_instance, is_bifrost)

    # Input Primitives - Delegate to specialized modules

    def read_string(self, prompt: str = "", **kwargs):
        """Read string input - terminal (synchronous) or GUI (buffered event).
        
        Delegates to: inputs.input_string.StringInput
        """
        return self._string_input.read_string(prompt, **kwargs)

    def read_password(self, prompt: str = "") -> str:
        """Read password input - terminal (synchronous) or GUI (buffered event).
        
        Delegates to: inputs.input_password.PasswordInput
        """
        return self._password_input.read_password(prompt)

    # Legacy / Backward-Compatible Aliases

    @property
    def read(self):
        """Alias for read_string.
        
        Returns:
            Callable: The read_string method
        """
        return self.read_string
