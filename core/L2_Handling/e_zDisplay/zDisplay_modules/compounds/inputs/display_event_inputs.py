# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/d_compounds/display_event_inputs.py

"""
InteractiveInputs - Interactive Widgets (FACADE v2.0)
======================================================

REFACTORING v2.0 (Facade Pattern):
    - Decomposed monolith (967 lines) into 4 specialized helper modules
    - Extracted InputValidators for validation logic
    - Extracted SelectionRenderer for display logic
    - Extracted SelectionCollector for input collection
    - Extracted LinkHandler for link handling (v1.6.1 feature)
    - Composition pattern: InteractiveInputs orchestrates specialized modules

ARCHITECTURAL CHANGE (Week 6.5):
    - Moved read_bool to c_basic (boolean is a fundamental input type)
    - This module now focuses on INTERACTIVE WIDGETS (complex UI components)
    - Distinction: c_basic = simple inputs, d_compounds = interactive widgets

This event package provides interactive widgets (selection menus, sliders)
with comprehensive validation, building on the BasicOutputs A+ foundation.

Composition Architecture
------------------------
BasicInputs builds on BasicOutputs (the A+ grade foundation):

Layer 3: display_delegates.py (PRIMARY API)
    ↓
Layer 2: display_events.py (ORCHESTRATOR)
    ↓
Layer 2: events/display_event_inputs.py (InteractiveInputs) ← THIS MODULE (FACADE)
    ↓
Layer 2: inputs/*.py (HELPER MODULES)
    ↓
Layer 2: events/display_event_outputs.py (BasicOutputs) ← A+ FOUNDATION
    ↓
Layer 1: display_primitives.py (FOUNDATION I/O)

Module Decomposition (v2.0)
----------------------------
Helper modules in inputs/ directory:

1. **InputValidators** - Validation logic
   - Range checking for numeric input
   - Numeric validation
   - Toggle behavior for multi-select

2. **SelectionRenderer** - Display logic
   - Prompt rendering
   - Options display with markers (checkboxes/radio buttons)
   - Message output

3. **SelectionCollector** - Input collection
   - Single-select collection with validation
   - Multi-select collection with toggle behavior
   - Button confirmation collection

4. **LinkHandler** - Link handling (NEW v1.6.1)
   - Extract labels from link configurations
   - Execute link actions (open URL, navigate)
   - GUI mode link selection

5. **SliderWidget** - Numeric range slider (moved from b_primitives)
   - Interactive slider with keyboard controls
   - Min/max/step validation
   - Visual feedback

Composition Flow:
1. InteractiveInputs.selection() method called
2. Try GUI mode via primitives.send_gui_event()
3. If terminal mode:
   a. Display prompt via SelectionRenderer
   b. Display options with markers via SelectionRenderer
   c. Collect input via SelectionCollector
   d. Validate input via InputValidators
   e. Return selected option(s)

Interactive Widgets
-------------------
InteractiveInputs provides complex interactive widgets:

**1. Selection Menus (Single/Multi-Select):**
- Display options with [SELECTED]/[UNSELECTED] markers
- Single-select: User enters a single number (1 to N)
- Multi-select: Space-separated numbers with toggle behavior
- Returns: Optional[str] or List[str]
- Validation: Range checking, numeric input, default value support

**2. Numeric Range Slider:**
- Interactive slider with min/max/step controls
- Keyboard navigation (arrow keys, +/-)
- Visual feedback with current value display
- Returns: int or float
- Validation: Range bounds, step increments

Validation Logic
----------------
**Single-Select Validation:**
- Range checking: 1 to len(options)
- Numeric validation: ValueError for non-numeric input
- Default value: Empty input uses default if provided
- Cancel support: KeyboardInterrupt returns None

**Multi-Select Validation:**
- Parse space-separated numbers
- Range checking for each number
- Toggle selection: add if not selected, remove if already selected
- User feedback: "Added: X" or "Removed: X" messages
- Invalid input: Clear error messages with valid range
- Cancel support: KeyboardInterrupt or "done" command

Dual-Mode I/O Pattern
----------------------
All methods implement the same dual-mode pattern:

1. **GUI Mode (Bifrost):** Try send_gui_event() first
   - Send clean JSON event with selection data
   - Returns empty value immediately (GUI handles async)
   - GUI frontend will display selection UI

2. **zCLI Mode (Fallback):** Interactive text-based selection
   - Display prompt via BasicOutputs.text()
   - Display options with markers
   - Collect input via zPrimitives.read_string()
   - Validate and return selection(s)

Benefits of Composition
-----------------------
- **Reuses BasicOutputs logic:** Indentation, I/O, dual-mode handling
- **Consistent behavior:** All events use same display primitives
- **Validation focus:** BasicInputs only handles validation logic
- **Single responsibility:** Display vs. input vs. validation separated

Layer Position
--------------
InteractiveInputs occupies the d_compounds tier in zDisplay architecture:
- **Depends on:** BasicOutputs (A+ foundation) from c_basic
- **Used by:** zSystem (menu prompts, configuration selection)
- **Contrast:** c_basic/BasicInputs handles simple inputs (boolean)

Usage Statistics
----------------
- **4 total references** across 2 files
- **Used by:** zSystem (menu prompts, configuration selection)
- **1 selection method** with 2 modes (single + multi)
- **~350 lines** facade + ~450 lines helpers = ~800 total (v2.0)

zCLI Integration
----------------
- **Initialized by:** display_events.py (zEvents.__init__)
- **Cross-referenced:** BasicOutputs wired after init (lines 225-228 in display_events.py)
- **Accessed via:** zcli.display.zEvents.BasicInputs
- **No session access** - delegates to primitives + BasicOutputs

Thread Safety
-------------
Not thread-safe. All display operations should occur on the main thread or
with appropriate synchronization.

Example
-------
```python
# Via display_events orchestrator:
events = zEvents(display_instance)

# Single-select
color = events.BasicInputs.selection(
    "Select color:", 
    ["Red", "Green", "Blue"],
    default="Green"
)

# Multi-select
features = events.BasicInputs.selection(
    "Select features:", 
    ["Feature A", "Feature B", "Feature C"],
    multi=True,
    default=["Feature A"]
)

# Direct usage (rare):
basic_inputs = BasicInputs(display_instance)
basic_inputs.BasicOutputs = basic_outputs  # Must wire dependency
choice = basic_inputs.selection("Choose:", ["Option 1", "Option 2"])
```
"""

from zOS import Any, Optional, Union, List, Dict, asyncio

# Import constants from centralized module
from ...display_constants import (
    _EVENT_NAME_BUTTON,
    DEFAULT_MULTI,
    DEFAULT_STYLE,
)

# Import helper modules (v2.0 Decomposition)
from .input_validators import InputValidators
from .selection_renderer import SelectionRenderer
from .selection_collector import SelectionCollector
from .link_handler import LinkHandler
from .slider_widget import SliderWidget

# BasicInputs Class

class InteractiveInputs:
    """Interactive widgets with validation (FACADE v2.0).
    
    Builds on BasicOutputs (A+ foundation) to provide complex interactive
    widgets: selection menus and numeric range sliders.
    
    **Composition:**
    - Depends on BasicOutputs (A+ grade, Week 6.4.7)
    - Pattern: BasicOutputs.text() for display + zPrimitives.read_string() for input
    - Benefits: Reuses BasicOutputs logic (indent, I/O, dual-mode)
    
    **Interactive Widgets:**
    - selection(multi=False) - Single-select menu → Optional[str]
    - selection(multi=True) - Multi-select menu → List[str]
    - read_range() - Numeric slider → int/float
    
    **Validation:**
    - Selection: Range checking, numeric validation, default support
    - Slider: Min/max bounds, step increments
    
    **Usage:**
    - Used by: zSystem (menu prompts, configuration selection)
    
    **Pattern:**
    All methods implement dual-mode I/O (GUI-first, terminal fallback).
    
    **Architecture (v2.0):**
    This class is now a FACADE that orchestrates 5 specialized helper modules:
    - InputValidators: Validation logic
    - SelectionRenderer: Display logic
    - SelectionCollector: Input collection
    - LinkHandler: Link handling
    - SliderWidget: Numeric range slider
    
    **Note:** read_bool moved to c_basic/BasicInputs (boolean is a basic type)
    """

    # Type hints for instance attributes
    display: Any  # Parent zDisplay instance
    zPrimitives: Any  # Primitives instance for I/O operations
    zColors: Any  # Colors instance for terminal styling
    BasicOutputs: Optional[Any]  # BasicOutputs instance for composition (wired after init)

    # Helper modules (v2.0 Composition)
    InputValidators: Any
    SelectionRenderer: Any
    SelectionCollector: Any
    LinkHandler: Any
    SliderWidget: Any

    def __init__(self, display_instance: Any) -> None:
        """Initialize InteractiveInputs with parent display reference.
        
        Args:
            display_instance: Parent zDisplay instance providing primitives and colors
            
        Note:
            BasicOutputs is set to None initially and wired after initialization
            by display_events.py to avoid circular dependencies. The fallback
            logic handles the rare edge case where BasicOutputs is not yet set.
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives
        self.zColors = display_instance.zColors
        # Get reference to BasicOutputs for composition
        self.BasicOutputs = None  # Will be set after zEvents initialization

        # Instantiate helper modules (v2.0 Decomposition)
        self.InputValidators = InputValidators(display_instance)
        self.SelectionRenderer = SelectionRenderer(display_instance)
        self.SelectionCollector = SelectionCollector(display_instance)
        self.LinkHandler = LinkHandler(display_instance)
        self.SliderWidget = SliderWidget(display_instance)

    # Public API Methods - Delegate to specialized helper modules

    def selection(self, prompt: str, options: List[Union[str, Dict[str, Any]]], multi: bool = DEFAULT_MULTI,
                  default: Optional[Union[str, List[str]]] = None,
                  style: str = DEFAULT_STYLE,
                  action_type: Optional[str] = None,
                  input_type: Optional[str] = None) -> Union[Optional[str], List[str], 'asyncio.Future']:
        """Display selection prompt and collect user's choice(s).
        
        Foundation method for interactive selection prompts. Implements dual-mode
        I/O pattern and delegates to specialized helper modules.
        
        Supports inline modifiers in option strings:
        - [disabled] suffix: marks option as disabled. GUI greys it out; terminal
          keeps it numbered + shown as "label [disabled]" with NO marker, and the
          validator rejects it if chosen ("please choose another").
        - [default] suffix: auto-sets as default if no explicit default provided
        
        Delegates to:
        - LinkHandler for link extraction and execution
        - InputValidators for validation
        - SelectionRenderer for display
        - SelectionCollector for input collection
        
        Args:
            prompt: Selection prompt text
            options: List of option strings OR link dicts to choose from
            multi: Enable multi-select mode (default: False)
            default: Default selection (default: None)
            style: Display style (default: "numbered")
            action_type: Action to perform after selection (default: None)
            type: Rendering hint for Bifrost (radio/checkbox/dropdown)
                
        Returns:
            zCLI mode: Optional[str] or List[str] depending on multi flag
            Bifrost mode: asyncio.Future that resolves to selection value(s)
        
        Note:
            See module docstring for detailed examples and usage patterns.
        """
        # Auto-detect default from [default] suffix if no explicit default provided
        if default is None and options:
            for opt in options:
                if isinstance(opt, str):
                    parsed = self.LinkHandler.parse_option_string(opt)
                    if parsed['is_default']:
                        default = parsed['clean_label']
                        break
        
        # Extract labels from link dicts if present (also parses string modifiers)
        display_options, link_configs = self.LinkHandler.extract_option_labels(options)

        # Try GUI mode first
        if action_type == "link" and link_configs:
            gui_future = self.LinkHandler.try_gui_mode_links(prompt, link_configs, style)
            if gui_future is not None:
                return gui_future
        else:
            gui_future = self._try_gui_mode_future(prompt, display_options, multi, default, style, input_type)
            if gui_future is not None:
                return gui_future

        # zCLI mode: Validate options
        if not self.InputValidators.validate_options(display_options):
            return [] if multi else None

        # zCLI mode: Display prompt and options
        self.SelectionRenderer.display_prompt(prompt, self.BasicOutputs)
        self.SelectionRenderer.display_options(display_options, multi, default, self.BasicOutputs)

        # zCLI mode: Handle selection
        result = self._handle_selection(display_options, multi, default)

        # Execute link action if specified
        if action_type == "link" and link_configs and result:
            self.LinkHandler.execute_link_action(
                result, display_options, link_configs,
                self.SelectionRenderer, self.BasicOutputs
            )

        return result

    # Private Helper Methods - GUI Mode & Selection Orchestration

    def _try_gui_mode_future(
        self, prompt: str, options: List[str], multi: bool,
        default: Optional[Union[str, List[str]]], style: str, input_type: Optional[str] = None
    ) -> Optional['asyncio.Future']:
        """Try to handle selection in GUI mode with Future return (extracted method).
        
        Creates and returns an asyncio.Future that will be resolved when the GUI
        client sends back the selection response. This enables fire-and-forget
        pattern for selections in Bifrost mode.
        
        Args:
            prompt: Selection prompt text
            options: List of option strings
            multi: Multi-select flag
            default: Default selection
            style: Display style
            type: Rendering hint for Bifrost (radio/checkbox/dropdown)
            
        Returns:
            Optional[asyncio.Future]: Future that resolves to selection value(s),
                                      or None if not in GUI mode
        """
        # Check if in GUI mode
        if not self.zPrimitives.is_bifrost_mode():
            return None

        # Send selection request via input_request mechanism (creates Future)
        gui_future = self.zPrimitives._send_input_request(  # pylint: disable=protected-access
            'selection',  # request_type
            prompt,
            options=options,
            multi=multi,
            default=default,
            style=style,
            type=input_type
        )

        return gui_future

    def _try_gui_mode_button(self, label: str, action: Optional[str], color: str, zIcon: Optional[str] = None) -> Optional['asyncio.Future']:
        """Try to handle button in GUI mode with Future return.
        
        Args:
            label: Button label text
            action: Optional action identifier
            color: Button color (primary, success, danger, warning, info)
            zIcon: Optional icon name (e.g., "bi-backspace", "tools")
            
        Returns:
            Optional[asyncio.Future]: Future that resolves to bool (True if clicked),
                                      or None if not in GUI mode
        """
        if not self.zPrimitives.is_bifrost_mode():
            return None

        kwargs = {
            'action': action,
            'color': color
        }
        if zIcon:
            kwargs['zIcon'] = zIcon

        return self.zPrimitives._send_input_request(  # pylint: disable=protected-access
            _EVENT_NAME_BUTTON,
            label,
            **kwargs
        )

    def _handle_selection(self, options: List[str], multi: bool,
                         default: Optional[Union[str, List[str]]]) -> Optional[Union[str, List[str]]]:
        """Handle selection based on mode (orchestrator method).
        
        Args:
            options: List of option strings
            multi: Multi-select flag
            default: Default selection
            
        Returns:
            Single-select: Optional[str] - Selected option or None
            Multi-select: List[str] - List of selected options
        """
        if multi:
            default_set = set(default) if isinstance(default, list) else set()
            return self.SelectionCollector.collect_multi_selection(
                options, default_set,
                self.InputValidators,
                self.SelectionRenderer,
                self.BasicOutputs
            )
        else:
            return self.SelectionCollector.collect_single_selection(
                options, default,
                self.InputValidators,
                self.SelectionRenderer,
                self.BasicOutputs
            )

    # Public API - Button Method

    def button(
        self,
        label: Optional[str] = None,
        action: Optional[str] = None,
        color: str = "primary",
        _context: Optional[dict] = None,
        **_kwargs
    ) -> Union[bool, 'asyncio.Future']:
        """Display a button that requires EXPLICIT confirmation to execute.

        The label is **icon-aware** (SSOT: IconMapper): any ``bi-*`` token in the
        label renders as an icon, everything else is literal text. There is no
        separate ``zIcon`` property — an icon-only button is just
        ``zBtn: { label: bi-gear }``; an icon + text is ``label: bi-gear Settings``.

        Delegates to SelectionCollector for implementation.

        Args:
            label: Icon-aware button label (``bi-*`` tokens become icons).
            action: Optional plugin invocation or action identifier
            color: Button semantic color (primary, success, danger, warning, info, secondary)
            _context: Context dict (accepted for consistency, not used)
            **kwargs: Additional parameters

        Returns:
            bool: True if explicitly confirmed ("y"/"yes"), False otherwise
            asyncio.Future: In GUI mode, Future that resolves to bool

        Note:
            See module docstring for detailed examples and usage patterns.
        """
        from zSys.accessibility import get_icon_mapper  # pylint: disable=import-outside-toplevel
        mapper = get_icon_mapper()
        label = label or ""
        icons, text = mapper.split_label(label)

        # The icon-aware label IS the contract — authored once, rendered by whichever
        # surface receives it. Bifrost gets the raw label verbatim and the client
        # parses it (bi-* token → <i>, rest → text, order preserved); zCLI bakes the
        # glyph(s) inline below. Same string, symmetric rendering — no zIcon split.
        if self.zPrimitives.is_bifrost_mode():
            gui_future = self._try_gui_mode_button(label or "Button", action, color)
            if gui_future is not None:
                return gui_future

        # zCLI mode: bake the icon glyph(s) inline into the label (order preserved).
        from zOS.zVocabulary import ZMODE_ZCLI  # pylint: disable=import-outside-toplevel
        cli_label = mapper.render_inline(label, ZMODE_ZCLI) if icons else (text or "Button")
        return self.SelectionCollector.collect_button_confirmation(
            cli_label, color, action,
            self.SelectionRenderer,
            self.BasicOutputs,
            zProgress=_kwargs.get("zProgress"),
        )

    # Public API - Widget Methods (moved from b_primitives)

    def read_range(self, prompt: str = "", **kwargs) -> Union[int, float, str]:
        """Read numeric range slider - interactive widget for value selection.
        
        Delegates to SliderWidget for implementation.
        Moved from b_primitives to d_compounds (proper architectural placement).
        
        Args:
            prompt: Label text to display
            **kwargs: Range configuration (min, max, step, value, disabled)
        
        Returns:
            Union[int, float, str]: int/float in terminal mode, empty string in Bifrost mode
        
        Example:
            volume = inputs.read_range("Volume", min=0, max=100, step=5, value=50)
        """
        return self.SliderWidget.read_range(prompt, **kwargs)
