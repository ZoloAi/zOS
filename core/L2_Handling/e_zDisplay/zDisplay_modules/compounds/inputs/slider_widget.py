# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/d_compounds/inputs/slider_widget.py

"""
SliderWidget - Numeric Range Slider Input Widget
=================================================

Interactive slider widget for numeric range input collection.
Moved from b_primitives to d_compounds (proper architectural placement).

This is NOT a primitive - it's an interactive widget that:
- Renders slider UI with visual bar (====●-----)
- Handles keyboard input (arrow keys, +/-, Enter, ESC)
- Validates min/max boundaries and step increments
- Uses primitives internally (raw(), line(), input())
- Requires termios and ANSI escape sequences

Architecture:
    Layer: d_compounds (Compound Widgets)
    Uses: zPrimitives.raw(), zPrimitives.line() (true primitives)
    Similar to: selection(), button() (other interactive widgets)
"""

from zOS import Any, Union, time, os, signal

from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    _EVENT_READ_RANGE,
    _KEY_EVENT,
    _KEY_REQUEST_ID,
    _KEY_PROMPT,
    _KEY_TIMESTAMP,
    _DEFAULT_PROMPT,
    _ANSI_CARRIAGE_RETURN,
    _ANSI_CLEAR_LINE,
    _ANSI_CURSOR_UP,
)


class SliderWidget:
    """Numeric range slider widget for interactive value selection."""

    display: Any
    zPrimitives: Any

    def __init__(self, display_instance: Any) -> None:
        """Initialize SliderWidget with parent display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives

    def read_range(self, prompt: str = _DEFAULT_PROMPT, **kwargs) -> Union[int, float, str]:
        """Read numeric range slider - terminal (interactive) or GUI (buffered event).
        
        Interactive range slider with real-time visual feedback:
            - Terminal mode: Renders visual slider with keyboard controls
            - Bifrost mode: Buffers read_range event, returns empty string (non-blocking)
        
        Args:
            prompt: Label text to display (default: empty string)
            **kwargs: Range configuration:
                - min: Minimum value (default: 0)
                - max: Maximum value (default: 100)
                - step: Increment step (default: 1)
                - value: Initial/default value (default: midpoint)
                - disabled: Whether slider is disabled (default: False)
        
        Returns:
            Union[int, float, str]: 
                - int/float if in terminal mode (actual user selection)
                - str if in Bifrost mode (empty string, slider rendered on frontend)
        
        Terminal Controls:
            - Arrow keys (←/→): Decrease/increase value by step
            - +/- keys: Alternative increment/decrement
            - Enter: Confirm selection
            - ESC: Cancel (returns default value)
        
        Visual Example:
            Volume: [====●-----]  50/100
            (Use ← → or +/- to adjust, Enter to confirm)
        
        Notes:
            - Uses carriage return for in-place updates (modern terminals)
            - Fallback to newlines for Terminal.app
            - Validates min/max boundaries
            - Handles step increments properly
            - Returns int if step is whole number, float otherwise
        
        Example:
            volume = slider.read_range("Volume", min=0, max=100, step=5, value=50)
            # Terminal: Interactive slider → Returns 75 (int)
            # Bifrost: Returns "" (slider rendered on frontend)
        """
        # Extract parameters with defaults
        min_val = kwargs.get('min', 0)
        max_val = kwargs.get('max', 100)
        step = kwargs.get('step', 1)
        value = kwargs.get('value', (min_val + max_val) / 2)
        disabled = kwargs.get('disabled', False)

        # Validate and normalize value
        value = max(min_val, min(max_val, value))

        # Determine return type (int if step is whole number, else float)
        is_integer = step == int(step)

        # Terminal input (interactive slider)
        if not self.zPrimitives.is_bifrost_mode():
            import sys
            import tty
            import termios

            # Handle disabled state - display only, no interaction
            if disabled:
                display_text = f"{prompt}: {value} [DISABLED]" if prompt else f"{value} [DISABLED]"
                print(display_text)
                return int(value) if is_integer else value

            # Helper function to render slider visual
            def render_slider(current_val):
                # Calculate percentage for visual bar
                percentage = (current_val - min_val) / (max_val - min_val) if max_val > min_val else 0
                bar_width = 20
                filled = int(percentage * bar_width)
                progress_bar = "=" * filled + "●" + "-" * (bar_width - filled - 1)

                # Format value display
                val_display = int(current_val) if is_integer else f"{current_val:.2f}"
                max_display = int(max_val) if is_integer else f"{max_val:.2f}"

                # Build display line
                label = f"{prompt}: " if prompt else ""
                return f"{label}[{progress_bar}]  {val_display}/{max_display}"

            # Save terminal settings for restoration
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)

            try:
                # Set raw mode for immediate key capture
                tty.setraw(fd)

                current_value = value

                # Print instructions using zOS primitives
                self.zPrimitives.line("(Use ← → or +/- to adjust, Enter to confirm)")

                # Initial render of slider using zOS primitives
                slider_display = render_slider(current_value)
                self.zPrimitives.raw(f"{_ANSI_CARRIAGE_RETURN}{_ANSI_CLEAR_LINE}{slider_display}", flush=True)

                # Keyboard input loop
                while True:
                    # Read single character
                    char = sys.stdin.read(1)

                    # Handle Ctrl+C (trigger graceful shutdown)
                    if char == '\x03':  # Ctrl+C
                        # Clean up display
                        self.zPrimitives.raw(f"{_ANSI_CURSOR_UP}{_ANSI_CLEAR_LINE}{_ANSI_CLEAR_LINE}\n", flush=True)
                        # Restore terminal first
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                        # Send SIGINT to ourselves to trigger zOS graceful shutdown handler
                        os.kill(os.getpid(), signal.SIGINT)
                        # Should not reach here, but return default as fallback
                        return int(value) if is_integer else value

                    # Handle Enter key (confirm)
                    if char == '\r' or char == '\n':
                        break

                    # Handle ESC key (cancel - return default)
                    if char == '\x1b':
                        # Check if it's an arrow key sequence
                        next_chars = sys.stdin.read(2)
                        if next_chars == '[C':  # Right arrow
                            current_value = min(max_val, current_value + step)
                        elif next_chars == '[D':  # Left arrow
                            current_value = max(min_val, current_value - step)
                        else:
                            # ESC without arrow - cancel
                            current_value = value
                            break

                    # Handle +/- keys
                    elif char == '+' or char == '=':
                        current_value = min(max_val, current_value + step)
                    elif char == '-' or char == '_':
                        current_value = max(min_val, current_value - step)
                    else:
                        # Ignore other keys
                        continue

                    # Re-render slider using zOS primitives (in-place update)
                    slider_display = render_slider(current_value)
                    self.zPrimitives.raw(
                        f"{_ANSI_CARRIAGE_RETURN}{_ANSI_CLEAR_LINE}{slider_display}", flush=True
                    )

                # Move to new line after slider - carriage return first, then newline
                self.zPrimitives.raw("\r\n")  # Return to column 0, then newline

                # Return value (let zDispatch continue)
                return int(current_value) if is_integer else current_value

            finally:
                # Restore terminal settings
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        # Bifrost mode - buffer read_range event and return empty string
        request_id = self.zPrimitives._generate_request_id()  # pylint: disable=protected-access

        # Support both 'prompt' and 'label' (label takes precedence)
        display_label = kwargs.get('label', prompt)

        request_event = {
            _KEY_EVENT: _EVENT_READ_RANGE,
            _KEY_REQUEST_ID: request_id,
            _KEY_PROMPT: display_label,
            _KEY_TIMESTAMP: time.time(),
            'min': min_val,
            'max': max_val,
            'step': step,
            'value': value,
            'disabled': disabled
        }

        # Buffer the range request
        if self.display and hasattr(self.display, 'buffer_event'):
            self.display.buffer_event(request_event)

        # Return empty string (wizard continues, frontend handles slider)
        return ""
