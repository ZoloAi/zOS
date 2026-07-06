# zOS/core/L2_Handling/h_zNavigation/navigation_modules/menu/menu_search.py

"""
Menu Search Feature for zNavigation - Interactive Filter Module.

This module provides the MenuSearch class, which implements interactive search
and filtering for large menu option lists. Extracted from navigation_menu_interaction.py
to follow the approved modular pattern.

Architecture
------------
The MenuSearch class provides an innovative search feature for menus with many options:

1. **Search Trigger** ("/" prefix)
   - User enters "/term" to filter options
   - Case-insensitive substring matching
   - Dynamic results display

2. **Progressive Filtering**
   - Can refine searches iteratively
   - Filter on top of previous filters
   - Reset to full list if no matches

3. **Selection Integration**
   - Enter digit to select from filtered list
   - Same validation as regular menu selection
   - Returns selected option string

Search Flow
-----------
1. Display original options
2. User enters "/" + search term → filter options
3. Display filtered results with count
4. User can:
   - Refine with another search ("/newterm")
   - Select from filtered list (digit)
5. Return selected option

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Menu Component

Integration
-----------
- Called by: MenuInteraction (navigation_menu_interaction.py)
- Uses: zDisplay for I/O operations
"""

from zOS import Any, List

# Search constants
_PREFIX_SEARCH = "/"
_PREFIX_NEWLINE = "\n"
_PROMPT_DEFAULT = "Choice"
_PROMPT_SEARCH_DEFAULT = "Search or select"
_TEMPLATE_SEARCH_PROMPT = "Type /{search_prompt} to filter, or enter choice number:"
_TEMPLATE_FILTERED_COUNT = "Filtered to {count} options:"
_WARN_NO_MATCHES = "No matches found. Showing all options."
_ERR_INVALID_SEARCH = "Invalid input. Enter a number or /search-term."
_LOG_SELECTED_SEARCH = "[MenuSearch] User selected: %s"


class MenuSearch:
    """
    Interactive menu search and filter feature.
    
    Provides search functionality for large menu option lists with progressive
    filtering and dynamic results display.
    
    Attributes
    ----------
    menu : Any
        Reference to parent menu system
    logger : Any
        Logger instance for search operations
    
    Methods
    -------
    search_and_select(options, display, search_prompt)
        Interactive search with selection from filtered results
    """

    # Class-level type declarations
    menu: Any  # Menu system reference
    logger: Any  # Logger instance

    def __init__(self, menu: Any) -> None:
        """
        Initialize menu search feature.
        
        Args
        ----
        menu : Any
            Parent menu system instance
        """
        self.menu = menu
        self.logger = menu.logger

    def search_and_select(
        self,
        options: List[str],
        display: Any,
        search_prompt: str = _PROMPT_SEARCH_DEFAULT,
        format_option_callback: Any = None,
        validate_digit_callback: Any = None,
        validate_range_callback: Any = None
    ) -> str:
        """
        Get choice with interactive search functionality.
        
        Provides search/filter feature for large menus. Users can enter "/" followed
        by a search term to filter options by substring match, or enter a digit to
        select from the current filtered list.
        
        Args
        ----
        options : List[str]
            List of option strings to choose from
        display : Any
            Display adapter (zDisplay instance) for I/O operations
        search_prompt : str, default="Search or select"
            Prompt text for search instructions
        format_option_callback : Any, default=None
            Callback to format option display (index, option) -> str
        validate_digit_callback : Any, default=None
            Callback to validate digit input (choice, display) -> bool
        validate_range_callback : Any, default=None
            Callback to validate index range (index, options, display) -> bool
        
        Returns
        -------
        str
            Selected option string from the (possibly filtered) list
        
        Examples
        --------
        Search and select::
        
            modules = [f"Module{i}" for i in range(100)]
            selected = menu_search.search_and_select(modules, display)
            # User enters: "/auth"
            # Shows: Filtered to 8 options
            # User enters: "1"
            # Returns: selected module
        
        Progressive refinement::
        
            options = ["python-django", "python-flask", "ruby-rails"]
            selected = menu_search.search_and_select(options, display)
            # User: "/python" → Shows: python-django, python-flask
            # User: "/flask" → Shows: python-flask
            # User: "0" → Returns: "python-flask"
        
        Notes
        -----
        - Search Trigger: "/" prefix on input
        - Matching: Case-insensitive substring search
        - Filtering: Updates displayed options after each search
        - Selection: Enter digit to select from current filtered list
        - Reset: No matches → returns to full list with warning
        
        Search Feature Details
        ----------------------
        - Substring Matching: Searches within entire option string
        - Case Insensitive: "AUTH" matches "authentication"
        - Progressive: Can refine searches iteratively
        - Dynamic Display: Shows filtered count and updated list
        - Validation: Uses callbacks for digit/range validation
        """
        filtered_options = options.copy()
        prompt_text = _TEMPLATE_SEARCH_PROMPT.format(search_prompt=search_prompt)
        display.text(prompt_text)

        while True:
            # Show current filtered options
            if len(filtered_options) != len(options):
                count_text = _TEMPLATE_FILTERED_COUNT.format(
                    count=len(filtered_options)
                )
                display.text(_PREFIX_NEWLINE + count_text)

            # Display options using callback or default format
            for i, option in enumerate(filtered_options):
                if format_option_callback:
                    display.text(format_option_callback(i, option))
                else:
                    display.text(f"[{i}] {option}")

            # Get search or selection
            choice = display.read_string(_PROMPT_DEFAULT)

            if choice.startswith(_PREFIX_SEARCH):
                # Search mode
                search_term = choice[1:].lower()
                filtered_options = [
                    opt for opt in options
                    if search_term in str(opt).lower()
                ]

                if not filtered_options:
                    display.warning(_WARN_NO_MATCHES)
                    filtered_options = options.copy()

                continue

            # Selection mode - validate digit and range
            self.logger.debug(f"[MenuSearch] User input: {choice}")

            # Use validation callbacks if provided
            if validate_digit_callback:
                if not validate_digit_callback(choice, display):
                    display.error(_ERR_INVALID_SEARCH)
                    continue
            elif not choice.isdigit():
                display.error(_ERR_INVALID_SEARCH)
                continue

            index = int(choice)

            if validate_range_callback:
                if not validate_range_callback(index, filtered_options, display):
                    continue
            elif index < 0 or index >= len(filtered_options):
                display.error(f"Invalid choice. Please enter 0-{len(filtered_options)-1}.")
                continue

            selected = filtered_options[index]
            self.logger.debug(_LOG_SELECTED_SEARCH, selected)
            return selected

    def filter_options(
        self,
        options: List[str],
        search_term: str
    ) -> List[str]:
        """
        Filter options by search term.
        
        Performs case-insensitive substring matching on option strings.
        
        Args
        ----
        options : List[str]
            Original list of options
        search_term : str
            Search term to filter by
        
        Returns
        -------
        List[str]
            Filtered list of options matching search term
        
        Examples
        --------
        Filter options::
        
            options = ["Apple", "Banana", "Cherry", "Apricot"]
            filtered = menu_search.filter_options(options, "ap")
            # Returns: ["Apple", "Apricot"]
        
        Notes
        -----
        - Case-insensitive matching
        - Substring search (not prefix only)
        - Returns empty list if no matches
        """
        search_lower = search_term.lower()
        return [opt for opt in options if search_lower in str(opt).lower()]
