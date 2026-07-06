# zOS/core/L2_Handling/h_zNavigation/navigation_modules/navigation_menu_renderer.py

"""
Menu Renderer for zNavigation - Foundation Module.

This module provides the MenuRenderer class, which implements rendering strategies
for displaying menus in different formats and contexts. It integrates with zDisplay
to provide mode-agnostic rendering (Terminal and Bifrost).

Architecture
------------
The MenuRenderer is a Tier 1 (Foundation) component with no internal dependencies.
It provides three distinct rendering strategies optimized for different use cases:

1. Full Rendering (render):
   - Displays title with colored headers
   - Shows breadcrumb navigation
   - Uses zDisplay.zMenu() for formatted output
   - Best for primary navigation menus
   
2. Simple Rendering (render_simple):
   - Displays prompt with single-line header
   - Shows numbered list of options
   - Uses basic text output
   - Best for quick selections and dialogs
   
3. Compact Rendering (render_compact):
   - Single-line space-efficient format
   - Format: "0:option1 | 1:option2 | 2:option3"
   - Uses minimal display space
   - Best for space-constrained displays

Mode-Agnostic Rendering
------------------------
All rendering methods delegate to zDisplay, which handles zCLI vs. Bifrost
mode switching automatically:

- zCLI Mode: Direct console output with ANSI colors
- Bifrost Mode: WebSocket events sent to frontend

The renderer doesn't need to know which mode is active; zDisplay handles the
abstraction transparently.

Display Integration
-------------------
MenuRenderer uses the following zDisplay methods:

- zDeclare(text, color, indent, style):
  Used for titles and prompts with colored formatting
  
- zCrumbs(session):
  Displays breadcrumb navigation trail
  
- zMenu(menu_pairs):
  Renders formatted menu with numbered options
  
- text(content):
  Simple text output without special formatting

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Tier 1 (Foundation)

Integration
-----------
- Called by: MenuSystem (navigation_menu_system.py)
- Uses: zDisplay for all output operations
- Session: Accesses session for breadcrumb display
- Logging: Logs all rendering operations at debug level

Thread Safety
-------------
MenuRenderer is thread-safe as it does not maintain state between render calls.
Each render operation is independent.

Usage Examples
--------------
Full menu rendering::

    renderer = MenuRenderer(menu_system)
    menu_obj = {
        "options": ["Edit", "Delete", "View", "zBack"],
        "title": "Actions Menu",
        "allow_back": True
    }
    renderer.render(menu_obj, display)

Simple menu rendering::

    options = ["Option 1", "Option 2", "Option 3"]
    renderer.render_simple(options, display, prompt="Choose action")

Compact menu rendering::

    options = ["Yes", "No", "Cancel"]
    renderer.render_compact(options, display)

Module Constants
----------------
KEY_* : str
    Menu object dictionary keys
DEFAULT_* : str/int/bool
    Default values for rendering parameters
TEMPLATE_* : str
    String templates for formatting
SEPARATOR_* : str
    Separators for compact rendering
LOG_* : str
    Logging message templates
"""

from zOS import Any, Dict, List

from ..navigation_constants import (
    NAV_ZBACK,
    NAV_ZBACK_LABEL,
    NAV_ZDONE,
    NAV_ZDONE_LABEL,
    KEY_OPTIONS,
    KEY_TITLE,
    KEY_ALLOW_BACK,
    _DEFAULT_ALLOW_BACK,
    _DEFAULT_INDENT,
    _DEFAULT_STYLE_FULL,
    _DEFAULT_STYLE_SINGLE,
    _DEFAULT_PROMPT,
    _TEMPLATE_SIMPLE_ITEM,
    _TEMPLATE_COMPACT_ITEM,
    _SEPARATOR_COMPACT,
    _LOG_RENDERED_MENU,
    _LOG_RENDERED_SIMPLE,
    _LOG_RENDERED_COMPACT,
    _LOG_BREADCRUMB_FAILED,
)


# ============================================================================
# MenuRenderer Class
# ============================================================================

class MenuRenderer:
    """
    Menu rendering engine for zNavigation.
    
    Provides three rendering strategies (full, simple, compact) for displaying
    menus in different contexts. Integrates with zDisplay for mode-agnostic
    rendering across Terminal and Bifrost modes.
    
    Attributes
    ----------
    menu : MenuSystem
        Reference to parent menu system
    zos : zOS
        Reference to zOS instance
    logger : logging.Logger
        Logger instance for rendering operations
    
    Methods
    -------
    render(menu_obj, display)
        Full menu rendering with title, breadcrumbs, and formatted display
    render_simple(options, display, prompt)
        Simple numbered list rendering with prompt
    render_compact(options, display)
        Compact single-line rendering for space efficiency
    
    Private Methods
    ---------------
    _log_render(strategy, option_count)
        Log rendering operation (DRY helper)
    
    Examples
    --------
    Full rendering with title and breadcrumbs::
    
        menu_obj = builder.build(["Edit", "Delete"], "Actions")
        renderer.render(menu_obj, display)
    
    Simple rendering for quick selection::
    
        renderer.render_simple(["Yes", "No"], display, "Confirm?")
    
    Compact rendering for space-constrained UI::
    
        renderer.render_compact(["A", "B", "C"], display)
    
    Integration
    -----------
    - Called by: MenuSystem for all menu display operations
    - Uses: zDisplay for all output (mode-agnostic)
    - Logging: All rendering operations logged at debug level
    - Session: Accessed for breadcrumb navigation display
    """

    # Class-level type declarations
    menu: Any  # MenuSystem reference
    zos: Any  # zOS instance
    logger: Any  # Logger instance

    def __init__(self, menu: Any) -> None:
        """
        Initialize menu renderer.
        
        Args
        ----
        menu : MenuSystem
            Parent menu system instance that provides access to zos and logger
        
        Notes
        -----
        The MenuRenderer stores references to the parent menu system, zcli core,
        and logger for use during rendering operations. No rendering state is
        maintained between calls.
        """
        self.menu = menu
        self.zos = menu.zos
        self.logger = menu.logger

    def _format_brand_label(self, brand: dict) -> str:
        """Build the zCLI brand label: optional ANSI-safe zIcon + label/alt text.

        The icon is resolved through the icon_mapper gate, so it renders as an
        emoji on capable terminals and ``[name]`` otherwise (SSOT). A logo image
        is intentionally suppressed in zCLI — the label is its alt text.
        """
        label = brand.get("label") or "Home"
        icon = brand.get("icon")
        if not icon:
            return label
        try:
            from zSys.accessibility import get_icon_mapper  # pylint: disable=import-outside-toplevel
            from zOS.zVocabulary import ZMODE_ZCLI  # pylint: disable=import-outside-toplevel
            glyph = get_icon_mapper().render_for_mode(icon, mode=ZMODE_ZCLI)
        except Exception:  # pylint: disable=broad-except
            return label
        return f"{glyph} {label}" if glyph else label

    def render(
        self,
        menu_obj: Dict[str, Any],
        display: Any
    ) -> None:
        """
        Render full menu with title, breadcrumbs, and formatted display.
        
        This is the primary rendering method, providing a complete menu experience
        with optional title, breadcrumb navigation, and formatted menu display
        through zDisplay.zMenu().
        
        Args
        ----
        menu_obj : Dict[str, Any]
            Menu object containing:
            - "options": List of menu option strings
            - "title": Optional menu title (or None)
            - "allow_back": Boolean flag (default: True)
        display : Any
            Display adapter (zDisplay instance) for output operations
        
        Returns
        -------
        None
            Output is sent directly to display adapter
        
        Examples
        --------
        Render menu with title::
        
            menu_obj = {
                "options": ["Edit", "Delete", "View", "zBack"],
                "title": "Actions Menu",
                "allow_back": True
            }
            renderer.render(menu_obj, display)
        
        Render menu without title::
        
            menu_obj = {
                "options": ["Option 1", "Option 2"],
                "title": None,
                "allow_back": True
            }
            renderer.render(menu_obj, display)
        
        Notes
        -----
        - Title is displayed using zDisplay.zDeclare() with full style
        - Breadcrumbs are displayed if available (Walker context)
        - Menu options are rendered using zDisplay.zMenu()
        - All output is mode-agnostic (zCLI/Bifrost handled by zDisplay)
        - If breadcrumb display fails, error is logged but rendering continues
        
        Mode Behavior
        -------------
        - Terminal: ANSI-colored output with interactive selection
        - Bifrost: WebSocket events sent to frontend for rendering
        """
        # Extract menu object properties
        options = menu_obj[KEY_OPTIONS]
        title = menu_obj.get(KEY_TITLE)
        _allow_back = menu_obj.get(KEY_ALLOW_BACK, _DEFAULT_ALLOW_BACK)

        # Show title if provided
        if title:
            display.zDeclare(
                title,
                color=self.menu.navigation.mycolor,
                indent=_DEFAULT_INDENT,
                style=_DEFAULT_STYLE_FULL
            )

        # Create menu pairs for display (enumerate with indices).
        # Strip $ prefix / decorate sub-items for the DISPLAY label only — but
        # keep the ORIGINAL option aligned so the returned selection preserves
        # $-delta prefixes (navbar / cross-block) and dict (zSub / RBAC)
        # metadata. Returning the stripped label here was an SSOT drop: it
        # erased the $ that the wizard's zDelta handler and modifier_menu's
        # dict re-dispatch rely on, so navbar picks silently no-op'd in zCLI.
        # Format sub-items: "zProducts (zCLI, zBifrost, zTheme, zTrivia)"
        labels = []
        originals = []
        for opt in options:
            if isinstance(opt, dict) and len(opt) == 1:
                # Dict with metadata: {"$zProducts": {"zSub": ["zCLI", "zBifrost", ...]}}
                item_name = list(opt.keys())[0]
                item_data = opt[item_name]

                # zBrand (home): display the brand label, not the target name.
                # zIcon (if any) renders ANSI-safe via the icon_mapper gate (emoji
                # on capable terminals, [name] otherwise). logo (image) is suppressed
                # in zCLI — the label is its alt text.
                if item_name == "zBrand" and isinstance(item_data, dict):
                    labels.append(self._format_brand_label(item_data))
                    originals.append(opt)
                    continue

                # zLink override (any item without zSub): display its name (or
                # optional label); it dispatches its absolute zLink directly.
                # Parents with zSub fall through to the sub-item display below.
                if (isinstance(item_data, dict) and item_data.get("zLink")
                        and "zSub" not in item_data):
                    labels.append(item_data.get("label") or item_name.lstrip('$'))
                    originals.append(opt)
                    continue

                # Extract display name (strip $ prefix)
                display_name = item_name.lstrip('$')

                # Check for sub-items in metadata. zSub is normalized to a dict
                # {child: meta}, but tolerate a raw list — join the child names.
                if isinstance(item_data, dict) and "zSub" in item_data:
                    sub_items = item_data["zSub"]
                    child_names = (
                        list(sub_items.keys()) if isinstance(sub_items, dict)
                        else [s for s in sub_items if isinstance(s, str)]
                    )
                    display_text = f"{display_name} ({', '.join(child_names)})"
                else:
                    display_text = display_name

                labels.append(display_text)
            elif isinstance(opt, str):
                # The auto-injected Back / Done options carry NAV_ZBACK / NAV_ZDONE
                # as their value (the selection keys the wizard / modifier read). Show
                # the friendly label in the list; originals keeps the raw token so the
                # position-mapped return below still yields the raw token.
                if opt == NAV_ZBACK:
                    labels.append(NAV_ZBACK_LABEL)
                elif opt == NAV_ZDONE:
                    labels.append(NAV_ZDONE_LABEL)
                else:
                    labels.append(opt.lstrip('$'))
            else:
                labels.append(str(opt))
            originals.append(opt)

        # Show breadcrumbs if available (for Walker context)
        try:
            display.zCrumbs(self.zos.session)
        except AttributeError as e:
            # Log if zCrumbs method not available
            self.logger.debug(_LOG_BREADCRUMB_FAILED, e)

        # Render menu using modern zDisplay method (labels only — selection() handles numbering)
        # In zCLI mode, zMenu() blocks for input and returns the selected label
        selected = display.zMenu(labels)

        # Log rendering operation
        self._log_render("full", len(options))

        # Map the chosen display label back to its ORIGINAL option so downstream
        # navigation keeps full fidelity. Selection is unambiguous by position;
        # first label match wins.
        #   • $-prefixed string → transform to the canonical {zLink: path} dict
        #     (same as the interaction path) so modifier_menu re-dispatches it
        #     through the zLink subsystem and the navbar OP_RESET flag is honored.
        #   • dict (zSub / RBAC) → return as-is for hierarchical handling.
        #   • plain string → return as-is (in-block menu jump).
        if selected is not None:
            for label, original in zip(labels, originals):
                if label == selected:
                    if isinstance(original, str) and original.startswith('$'):
                        return self.menu.interaction._transform_delta_link(original)  # pylint: disable=protected-access
                    # Explicit zLink override (zBrand or any item): dispatch its
                    # absolute zLink directly, bypassing structure-by-name resolution.
                    # zSub parents fall through (return original) to open the submenu.
                    if isinstance(original, dict) and len(original) == 1:
                        item_name = next(iter(original))
                        meta = original[item_name]
                        if (isinstance(meta, dict) and meta.get("zLink")
                                and "zSub" not in meta):
                            return {"zLink": meta["zLink"]}
                        # zSub parent: open the submenu here (the navbar comes
                        # through this render path, NOT get_choice_from_list, so
                        # the submenu must be resolved before returning — else the
                        # raw zSub dict leaks to the launcher and mis-resolves to a
                        # child's zLink). zBack re-renders this parent menu.
                        if isinstance(meta, dict) and "zSub" in meta:
                            sub_result = self.menu.interaction.resolve_zsub(item_name, meta)
                            if sub_result == NAV_ZBACK:
                                return self.render(menu_obj, display)
                            return sub_result
                    return original
        return selected

    def render_simple(
        self,
        options: List[str],
        display: Any,
        prompt: str = _DEFAULT_PROMPT
    ) -> None:
        """
        Render simple menu without complex formatting.
        
        Provides a lightweight menu rendering with a prompt and numbered list.
        Best for quick selections, dialogs, and scenarios where full menu
        formatting is not needed.
        
        Args
        ----
        options : List[str]
            List of option strings to display
        display : Any
            Display adapter (zDisplay instance) for output
        prompt : str, default="Select option"
            Prompt text displayed above options
        
        Returns
        -------
        None
            Output is sent directly to display adapter
        
        Examples
        --------
        Simple yes/no prompt::
        
            renderer.render_simple(["Yes", "No"], display, "Continue?")
        
        Quick action selection::
        
            actions = ["Edit", "Delete", "Cancel"]
            renderer.render_simple(actions, display, "Choose action")
        
        Default prompt::
        
            renderer.render_simple(["A", "B", "C"], display)
            # Uses default prompt: "Select option"
        
        Notes
        -----
        - Prompt is displayed using zDisplay.zDeclare() with single style
        - Each option is numbered starting from 0
        - Format: "  [0] option1"
        - Uses display.text() for simple output
        - No breadcrumbs or complex formatting
        
        Use Cases
        ---------
        - Dialog confirmations (Yes/No/Cancel)
        - Quick action selections
        - Nested menu selections
        - Space-efficient alternatives to full menus
        """
        # Display prompt with single-line style
        display.zDeclare(
            prompt,
            color=self.menu.navigation.mycolor,
            indent=_DEFAULT_INDENT,
            style=_DEFAULT_STYLE_SINGLE
        )

        # Simple numbered list
        for i, option in enumerate(options):
            formatted_item = _TEMPLATE_SIMPLE_ITEM.format(index=i, option=option)
            display.text(formatted_item)

        # Log rendering operation
        self._log_render("simple", len(options))

    def render_compact(
        self,
        options: List[str],
        display: Any
    ) -> None:
        """
        Render compact menu for space-constrained displays.
        
        Provides the most space-efficient menu rendering with all options on
        a single line, separated by pipes. Best for mobile displays, small
        terminals, or when screen real estate is limited.
        
        Args
        ----
        options : List[str]
            List of option strings to display
        display : Any
            Display adapter (zDisplay instance) for output
        
        Returns
        -------
        None
            Output is sent directly to display adapter
        
        Examples
        --------
        Compact yes/no menu::
        
            renderer.render_compact(["Yes", "No"], display)
            # Output: "0:Yes | 1:No"
        
        Compact action menu::
        
            actions = ["Edit", "Delete", "View", "Cancel"]
            renderer.render_compact(actions, display)
            # Output: "0:Edit | 1:Delete | 2:View | 3:Cancel"
        
        Notes
        -----
        - Format: "index:option | index:option | index:option"
        - No prompt or title displayed
        - Single line of output
        - Uses display.text() for output
        - Each option is numbered starting from 0
        
        Format Details
        --------------
        - Separator: " | " (space-pipe-space)
        - Item format: "index:option" (no spaces)
        - Example: "0:option1 | 1:option2 | 2:option3"
        
        Use Cases
        ---------
        - Mobile-optimized displays
        - Small terminal windows
        - Status bar menus
        - Quick inline selections
        - Dashboard controls
        """
        # Show options in compact format
        formatted_items = [
            _TEMPLATE_COMPACT_ITEM.format(index=i, option=opt)
            for i, opt in enumerate(options)
        ]
        option_text = _SEPARATOR_COMPACT.join(formatted_items)
        display.text(option_text)

        # Log rendering operation
        self._log_render("compact", len(options))

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _log_render(
        self,
        strategy: str,
        option_count: int
    ) -> None:
        """
        Log menu rendering operation.
        
        Args
        ----
        strategy : str
            Rendering strategy used ("full", "simple", or "compact")
        option_count : int
            Number of options rendered
        
        Notes
        -----
        DRY Helper: Eliminates 3 duplications of logging pattern
        (lines 43, 60, 74 in original)
        
        Logs at debug level with format: "Rendered {strategy} menu with N options"
        """
        if strategy == "full":
            self.logger.debug(_LOG_RENDERED_MENU, option_count)
        elif strategy == "simple":
            self.logger.debug(_LOG_RENDERED_SIMPLE, option_count)
        elif strategy == "compact":
            self.logger.debug(_LOG_RENDERED_COMPACT, option_count)
