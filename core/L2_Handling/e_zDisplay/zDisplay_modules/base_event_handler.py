# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/base_event_handler.py

"""
Base Event Handler - Template Pattern for Dual-Mode Events (DRY Foundation)
=============================================================================

This module provides a base class implementing the dual-mode event pattern
that is repeated across 15+ event classes. By centralizing this pattern,
we achieve DRY compliance and provide a single source of truth for
GUI-first, terminal-fallback behavior.

Pattern:
--------
All zDisplay events follow the same flow:
1. Try GUI mode first (send structured JSON event)
2. If GUI mode succeeds, return early
3. Otherwise, fall back to terminal mode (format and print)

This pattern was duplicated in every event class. Now it's centralized here.

Usage:
------
Event classes inherit from BaseEventHandler and use the template method:

```python
class BasicOutputs(BaseEventHandler):
    def header(self, label, color, indent, style, **kwargs):
        return self._dual_mode_event(
            event_name='header',
            gui_data={'label': label, 'color': color, 'style': style, **kwargs},
            terminal_formatter=lambda: self._format_header_terminal(label, color, indent, style)
        )
    
    def _format_header_terminal(self, label, color, indent, style):
        # Terminal-specific formatting logic
        return formatted_string
```

Benefits:
---------
- DRY: Eliminates ~20 lines of duplicate pattern per event class
- SSOT: Single location for dual-mode logic changes
- Consistency: All events behave identically
- Testability: Template method can be unit tested once

Integration:
------------
Used by all event packages:
- BasicOutputs (c_basic)
- BasicInputs (c_basic)
- InteractiveInputs (d_compounds)
- CompoundData (d_compounds)
- MediaEvents (d_compounds)
- AdvancedData (e_advanced)
- TimeBased (e_advanced)
- zSystem (system)
"""

from zOS import Any, Dict, Optional, Callable


class BaseEventHandler:
    """Base class for dual-mode event handling with template pattern.
    
    Provides the _dual_mode_event() template method that implements
    GUI-first, terminal-fallback pattern used by all event handlers.
    
    Attributes:
        zPrimitives: Primitives instance (required, must be set by subclass)
        display: Display instance (optional, for advanced use cases)
    """
    
    # Type hints for required attributes (must be set by subclass)
    zPrimitives: Any  # Required: Primitives instance for I/O operations
    display: Optional[Any]  # Optional: Display instance for context

    def _dual_mode_event(
        self,
        event_name: str,
        gui_data: Dict[str, Any],
        terminal_formatter: Optional[Callable[[], str]] = None,
        terminal_action: Optional[Callable[[], Any]] = None
    ) -> Any:
        """Execute event with GUI-first, terminal-fallback pattern (DRY template).
        
        This is the core template method that all event handlers use. It implements
        the dual-mode pattern in a single location, eliminating duplication.
        
        Args:
            event_name: GUI event name (e.g., 'header', 'text', 'error')
            gui_data: Clean JSON data for GUI mode (sent via WebSocket)
            terminal_formatter: Optional callable that returns formatted string for terminal
            terminal_action: Optional callable that performs terminal action (instead of formatter)
        
        Returns:
            Result from terminal action, or None
        
        Flow:
            1. Try GUI mode: self.zPrimitives.send_gui_event(event_name, gui_data)
            2. If GUI succeeded: return early (GUI handles rendering)
            3. Otherwise: Execute terminal formatter/action
        
        Note:
            Either terminal_formatter OR terminal_action must be provided.
            - terminal_formatter: Returns string → displayed via zPrimitives.line()
            - terminal_action: Performs action directly → return value passed through
        
        Examples:
            # Simple output event
            self._dual_mode_event(
                'text',
                {'content': 'Hello'},
                terminal_formatter=lambda: 'Hello'
            )
            
            # Complex event with terminal action
            self._dual_mode_event(
                'selection',
                {'prompt': 'Choose:', 'options': ['A', 'B']},
                terminal_action=lambda: self._terminal_selection_menu()
            )
        """
        # Try GUI mode first
        if self.zPrimitives.send_gui_event(event_name, gui_data):
            return  # GUI event sent successfully
        
        # Terminal fallback
        if terminal_formatter:
            # Format and display string
            content = terminal_formatter()
            if content:  # Only display non-empty content
                self.zPrimitives.line(content)
            return None
        elif terminal_action:
            # Execute terminal action and return result
            return terminal_action()
        else:
            # No formatter or action provided - log warning
            if hasattr(self, 'display') and self.display:
                logger = getattr(self.display, 'logger', None)
                if logger:
                    logger.warning(
                        f"[BaseEventHandler] No terminal formatter/action provided for event '{event_name}'"
                    )
            return None

    def _send_gui_event(self, event_name: str, data: Dict[str, Any]) -> bool:
        """Helper: Send GUI event via primitives (convenience wrapper).
        
        This is a convenience wrapper around zPrimitives.send_gui_event()
        for subclasses that prefer explicit calls.
        
        Args:
            event_name: GUI event name
            data: Event data dictionary
        
        Returns:
            bool: True if event was sent, False if in terminal mode
        """
        return self.zPrimitives.send_gui_event(event_name, data)
