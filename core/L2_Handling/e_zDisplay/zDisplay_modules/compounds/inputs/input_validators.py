# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/d_compounds/inputs/input_validators.py

"""
Input Validators - Helper module for BasicInputs
=================================================

Provides validation logic:
- Range checking for numeric input
- Numeric validation
- Toggle behavior for multi-select
"""

from zOS import Any, List, Set

from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    _OPTION_INDEX_OFFSET,
    _MSG_INVALID_NUMBER,
    _MSG_INVALID_RANGE_TEMPLATE,
    _MSG_INVALID_INPUT_TEMPLATE,
    _MSG_ADDED_TEMPLATE,
    _MSG_REMOVED_TEMPLATE,
)


class InputValidators:
    """Validation logic for BasicInputs."""

    def __init__(self, display_instance: Any) -> None:
        """Initialize InputValidators with display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance

    def validate_options(self, options: List[str]) -> bool:
        """Validate that options list is not empty.
        
        Args:
            options: List of option strings
            
        Returns:
            bool: True if options valid, False otherwise
        """
        return len(options) > 0

    def validate_single_selection(
        self,
        selection: str,
        options: List[str],
        default: Any
    ) -> tuple:
        """Validate single selection input.
        
        Args:
            selection: User input string
            options: List of option strings
            default: Default option
            
        Returns:
            tuple: (is_valid, result_or_error_message)
                - (True, selected_option) if valid
                - (False, error_message) if invalid
        """
        # Empty input uses default
        if not selection and default is not None:
            return (True, default)

        # Validate numeric input
        try:
            choice_index = int(selection) - _OPTION_INDEX_OFFSET
            if 0 <= choice_index < len(options):
                selected = options[choice_index]
                if selected.endswith(' [disabled]'):
                    return (False, "  That option is disabled — please choose another.")
                return (True, selected)
            else:
                from ...display_constants import _MSG_RANGE_ERROR_TEMPLATE  # pylint: disable=relative-beyond-top-level
                return (False, _MSG_RANGE_ERROR_TEMPLATE.format(max_num=len(options)))
        except ValueError:
            return (False, _MSG_INVALID_NUMBER)

    def process_multi_selection_number(
        self,
        num_str: str,
        options: List[str],
        selected: Set[str]
    ) -> tuple:
        """Process a single selection number with toggle behavior.
        
        Args:
            num_str: Number string to process
            options: List of option strings
            selected: Set of currently selected options
            
        Returns:
            tuple: (is_valid, feedback_message)
                - (True, "Added: X" or "Removed: X") if valid
                - (False, error_message) if invalid
        """
        try:
            idx = int(num_str) - _OPTION_INDEX_OFFSET
            if 0 <= idx < len(options):
                option = options[idx]
                if option.endswith(' [disabled]'):
                    return (False, "  That option is disabled — please choose another.")
                # Toggle selection
                if option in selected:
                    selected.remove(option)
                    return (True, _MSG_REMOVED_TEMPLATE.format(option=option))
                else:
                    selected.add(option)
                    return (True, _MSG_ADDED_TEMPLATE.format(option=option))
            else:
                return (False, _MSG_INVALID_RANGE_TEMPLATE.format(
                    input=num_str,
                    max_num=len(options)
                ))
        except ValueError:
            return (False, _MSG_INVALID_INPUT_TEMPLATE.format(input=num_str))
