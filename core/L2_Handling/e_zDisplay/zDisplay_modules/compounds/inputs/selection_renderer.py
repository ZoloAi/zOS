# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/d_compounds/inputs/selection_renderer.py

"""
Selection Renderer - Helper module for BasicInputs
===================================================

Provides display logic:
- Prompt rendering
- Options display with markers (checkboxes/radio buttons)
- Message output
"""

from zOS import Any, List, Optional, Union

from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    _MARKER_CHECKED,
    _MARKER_UNCHECKED,
    _MARKER_SELECTED,
    _MARKER_UNSELECTED,
    _OPTION_INDEX_OFFSET,
    DEFAULT_INDENT,
)


class SelectionRenderer:
    """Display logic for BasicInputs."""

    def __init__(self, display_instance: Any) -> None:
        """Initialize SelectionRenderer with display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives

    def output_text(
        self,
        content: str,
        break_after: bool = False,
        indent: int = DEFAULT_INDENT,
        basic_outputs: Optional[Any] = None
    ) -> None:
        """Output text via BasicOutputs with fallback.
        
        Args:
            content: Text content to output
            break_after: Whether to pause after output
            indent: Indentation level
            basic_outputs: BasicOutputs instance (optional)
        """
        if basic_outputs:
            basic_outputs.text(content, indent=indent, break_after=break_after)
        else:
            # Fallback if BasicOutputs not set
            self.zPrimitives.line(content)

    def display_prompt(self, prompt: str, basic_outputs: Optional[Any] = None) -> None:
        """Display selection prompt.
        
        Args:
            prompt: Prompt text to display
            basic_outputs: BasicOutputs instance (optional)
        """
        if prompt:
            self.output_text(prompt, break_after=False, basic_outputs=basic_outputs)

    def display_options(
        self,
        options: List[str],
        multi: bool,
        default: Optional[Union[str, List[str]]],
        basic_outputs: Optional[Any] = None
    ) -> None:
        """Display options with appropriate markers.
        
        Args:
            options: List of option strings
            multi: Multi-select flag
            default: Default selection
            basic_outputs: BasicOutputs instance (optional)
        """
        if multi:
            # Multi-select: show checkboxes
            default_set = set(default) if isinstance(default, list) else set()
            for i, option in enumerate(options):
                # Disabled rows keep their number (positional index↔number SSOT)
                # but wear NO marker — they aren't selectable, the [disabled] text
                # is the only cue. Enforcement rejects the index if typed.
                if option.endswith(' [disabled]'):
                    text = f"  {i + _OPTION_INDEX_OFFSET}. {option}"
                else:
                    marker = _MARKER_CHECKED if option in default_set else _MARKER_UNCHECKED
                    text = f"  {i + _OPTION_INDEX_OFFSET}. {marker} {option}"
                self.output_text(text, break_after=False, basic_outputs=basic_outputs)
        else:
            # Single-select. Radio markers only make sense when a default exists —
            # the (•) marks it against the ( ) others. With no default (e.g. a
            # zMenu, which is just "pick one to go"), the markers are empty noise,
            # so drop them and show a clean numbered list. Disabled rows never
            # wear a marker (not selectable) but keep their sequential number.
            show_markers = default is not None
            for i, option in enumerate(options):
                if show_markers and not option.endswith(' [disabled]'):
                    marker = _MARKER_SELECTED if option == default else _MARKER_UNSELECTED
                    text = f"  {i + _OPTION_INDEX_OFFSET}. {marker} {option}"
                else:
                    text = f"  {i + _OPTION_INDEX_OFFSET}. {option}"
                self.output_text(
                    text,
                    break_after=False,
                    basic_outputs=basic_outputs
                )

    def display_feedback(
        self,
        message: str,
        indent: int = 1,
        basic_outputs: Optional[Any] = None
    ) -> None:
        """Display feedback message with indentation.
        
        Args:
            message: Feedback message
            indent: Indentation level
            basic_outputs: BasicOutputs instance (optional)
        """
        self.output_text(message, break_after=False, indent=indent, basic_outputs=basic_outputs)
