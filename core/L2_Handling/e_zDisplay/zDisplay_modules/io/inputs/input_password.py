# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/b_primitives/primitives/input_password.py

"""
Password Input Primitive - Masked password input with dual-mode support.

Handles password input collection in both terminal (synchronous with getpass)
and Bifrost (buffered event) modes.
"""

from zOS import Any, getpass, time
from ...display_constants import (
    _DEFAULT_PROMPT,
    _EVENT_READ_PASSWORD,
    _KEY_EVENT,
    _KEY_REQUEST_ID,
    _KEY_PROMPT,
    _KEY_TIMESTAMP,
)


class PasswordInput:
    """Password input primitive - read masked password input."""

    display: Any
    _is_bifrost: bool

    def __init__(self, display_instance: Any, is_bifrost: bool) -> None:
        """Initialize with parent display instance and mode flag.
        
        Args:
            display_instance: Parent zDisplay instance
            is_bifrost: Pre-computed mode flag (True if Bifrost mode)
        """
        self.display = display_instance
        self._is_bifrost = is_bifrost

    def read_password(self, prompt: str = _DEFAULT_PROMPT) -> str:
        """Read password input - terminal (synchronous) or GUI (buffered event).
        
        Critical dual-mode method with different return types based on mode:
            - Terminal mode: Returns str directly (synchronous, masked with getpass)
            - Bifrost mode: Buffers display_prompt_request event, returns empty string (non-blocking)
        
        Args:
            prompt: Prompt text to display (default: empty string)
        
        Returns:
            str: 
                - Terminal mode: Actual masked password input
                - Bifrost mode: Empty string (input handled by frontend)
        
        Notes:
            - Terminal: Uses getpass.getpass() for masked input
            - Bifrost: Buffers display_prompt_request with masked=True flag
            - Always has terminal fallback if GUI request fails
            - Strips whitespace from Terminal input
        
        Example:
            result = primitives.read_password("Password:")
            # Terminal: Returns actual password string
            # Bifrost: Returns "" (input rendered on frontend)
        """
        if self._is_bifrost:
            # Bifrost mode - buffer read_password event and return empty string
            request_id = self.display.zPrimitives._generate_request_id()
            request_event = {
                _KEY_EVENT: _EVENT_READ_PASSWORD,
                _KEY_REQUEST_ID: request_id,
                _KEY_PROMPT: prompt,
                _KEY_TIMESTAMP: time.time(),
                'masked': True
            }

            # Buffer the input request
            if self.display and hasattr(self.display, 'buffer_event'):
                self.display.buffer_event(request_event)

            return ""

        # Terminal input.
        # When running as a zRaven test target the subprocess communicates over
        # stdin/stdout pipes — getpass writes to /dev/tty and reads from /dev/tty,
        # bypassing both the capture reader and the stdin injector entirely.
        # Fall back to plain input() so the prompt goes through stdout (captured
        # as [app] output) and the value is read from the piped stdin.
        import os as _os  # pylint: disable=import-outside-toplevel
        if _os.environ.get("ZRAVEN_TARGET") == "1":
            return input(prompt).strip() if prompt else input().strip()

        if prompt:
            return getpass.getpass(prompt).strip()
        return getpass.getpass().strip()
