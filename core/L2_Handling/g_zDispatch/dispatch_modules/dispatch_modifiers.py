# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/dispatch_modifiers.py

"""
Modifier Processor Orchestrator for zDispatch Subsystem.

This module provides the ModifierProcessor class, which orchestrates prefix and suffix
modifiers by delegating to domain-specific modifier implementations.

Architecture:
    The ModifierProcessor follows an orchestrator pattern:
    
    1. Detection Phase:
       - check_prefix(): Detects prefix modifiers (~)
       - check_suffix(): Detects suffix modifiers (* ! ^)
    
    2. Processing Phase:
       - process(): Routes to domain-specific modifier implementations
       - Delegates to MenuModifier, CrumbsRewindModifier
       - Handles mode-specific return values (zCLI vs. Bifrost)

Modifier Semantics:
    PREFIX MODIFIERS:
    - ~ (tilde): "Anchor" - Disable back navigation (used with *)
    
    SUFFIX MODIFIERS:
    - * (asterisk): "Menu" - Create menu from horizontal data
    - ^ (caret): "Crumbs-rewind" - <key>^: <zPath> mints the bulk-back signal
    (! "Required" is RETIRED — gating is an event (zBtn/zDialog), not a modifier.)

Refactoring:
    This file was refactored from 713 lines → ~200 lines by extracting:
    - MenuModifier → modifiers/modifier_menu.py
    - CrumbsRewindModifier → modifiers/modifier_crumbs.py
    (RequiredModifier retired — `!` gating is an event, not a modifier)
"""

from zOS import Any, Optional, Dict, List, Union

# Import all dispatch constants from centralized location
from .dispatch_constants import (
    # Modifiers
    MOD_CARET,
    MOD_ASTERISK,
    PREFIX_MODIFIERS,
    SUFFIX_MODIFIERS,
    # Log Messages (INTERNAL)
    _LOG_MSG_PARSING_PREFIX,
    _LOG_MSG_PARSING_SUFFIX,
    _LOG_MSG_PRE_MODIFIERS,
    _LOG_MSG_SUF_MODIFIERS,
    _LOG_MSG_RESOLVED,
    # Display Labels (INTERNAL)
    _LABEL_PROCESS_MODIFIERS,
    _DEFAULT_INDENT_PROCESS,
)

# Import domain-specific modifier implementations
# NOTE: `!` (RequiredModifier) is RETIRED — gating is an EVENT (zBtn/zDialog),
# never a modifier. Only menu (*) and crumbs-rewind (^) remain as suffixes.
from .modifiers.modifier_menu import MenuModifier
from .modifiers.modifier_crumbs import CrumbsRewindModifier


class ModifierProcessor:
    """
    Modifier processor orchestrator for zDispatch subsystem.
    
    Delegates modifier processing to domain-specific implementations:
    - MenuModifier: Handles * (asterisk) modifier
    - CrumbsRewindModifier: Handles ^ (caret) suffix modifier
    (! is retired — gating is an event, not a modifier)
    
    Attributes:
        dispatch: Parent zDispatch instance
        zos: zOS framework instance (provides subsystems, logger)
        logger: Logger instance for debug output
        menu_modifier: MenuModifier instance for * processing
        crumbs_modifier: CrumbsRewindModifier instance for ^ processing
        (required_modifier removed — `!` gating retired in favor of events)
    
    Methods:
        check_prefix(zKey): Detect prefix modifiers (~)
        check_suffix(zKey): Detect suffix modifiers (* ! ^)
        process(modifiers, zKey, zHorizontal, context, walker): Execute modifiers
    
    Integration:
        - CommandLauncher: Delegates unmodified commands to launcher
        - Domain Modifiers: Routes to MenuModifier, CrumbsRewindModifier
    """

    # Class-level type declarations
    dispatch: Any  # zDispatch instance
    zos: Any  # zOS framework instance
    logger: Any  # Logger instance
    menu_modifier: MenuModifier
    crumbs_modifier: CrumbsRewindModifier

    def __init__(self, dispatch: Any) -> None:
        """
        Initialize modifier processor with parent dispatch instance.
        
        Args:
            dispatch: Parent zDispatch instance providing access to zOS and logger
        
        Example:
            processor = ModifierProcessor(dispatch)
        """
        self.dispatch = dispatch
        self.zos = dispatch.zos
        self.logger = dispatch.logger

        # Initialize domain-specific modifier implementations
        self.menu_modifier = MenuModifier(dispatch, self.zos, self.logger)
        self.crumbs_modifier = CrumbsRewindModifier(dispatch, self.zos, self.logger)

    # ========================================================================
    # PUBLIC METHODS - Modifier Detection
    # ========================================================================

    def check_prefix(self, zKey: str) -> List[str]:
        """
        Check for prefix modifiers at the start of a key.
        
        Detects the following prefix modifiers:
        - ~ (tilde): Anchor modifier (disable back navigation, used with *)
        
        Args:
            zKey: Key string to check for prefix modifiers
        
        Returns:
            List of detected prefix modifier symbols (may be empty)
        
        Examples:
            check_prefix("~menu*")   # Returns ["~"]
            check_prefix("action")   # Returns []
        """
        self.logger.framework.debug(_LOG_MSG_PARSING_PREFIX, zKey)
        pre_modifiers = [sym for sym in PREFIX_MODIFIERS if zKey.startswith(sym)]
        self.logger.framework.debug(_LOG_MSG_PRE_MODIFIERS, pre_modifiers)
        return pre_modifiers

    def check_suffix(self, zKey: str) -> List[str]:
        """
        Check for suffix modifiers at the end of a key.
        
        Detects the following suffix modifiers:
        - * (asterisk): Menu modifier
        - ^ (caret): Crumbs-rewind modifier (<key>^: <zPath>)
        (! is retired — gating is an event, not a modifier.)
        
        Args:
            zKey: Key string to check for suffix modifiers
        
        Returns:
            List of detected suffix modifier symbols (may be empty)
        
        Examples:
            check_suffix("menu*")      # Returns ["*"]
            check_suffix("again^")     # Returns ["^"]
            check_suffix("action")     # Returns []
        """
        self.logger.framework.debug(_LOG_MSG_PARSING_SUFFIX, zKey)
        suf_modifiers = [sym for sym in SUFFIX_MODIFIERS if zKey.endswith(sym)]
        self.logger.framework.debug(_LOG_MSG_SUF_MODIFIERS, suf_modifiers)
        return suf_modifiers

    # ========================================================================
    # PUBLIC METHODS - Modifier Processing
    # ========================================================================

    def process(
        self,
        modifiers: List[str],
        zKey: str,
        zHorizontal: Any,
        context: Optional[Dict[str, Any]] = None,
        walker: Optional[Any] = None
    ) -> Optional[Union[str, Any]]:
        """
        Process modifiers by delegating to domain-specific implementations (ORCHESTRATOR).
        
        Routes modifier processing to focused handlers. Refactored from 713 lines
        to ~200 lines by extracting domain-specific logic.
        
        Modifier priority:
        1. * (menu): Create menu via zNavigation → MenuModifier
        2. ^ (crumbs-rewind): mint the {zCrumb} bulk-back signal → CrumbsRewindModifier
        3. No modifiers: Pass through to launcher
        (! "required" is retired — gating is an event, not a modifier.)
        
        Args:
            modifiers: List of detected modifier symbols
            zKey: Original key with modifiers
            zHorizontal: Command/data to execute
            context: Optional context dict
            walker: Optional walker instance
        
        Returns:
            Modifier-specific result (varies by modifier type)
        
        Examples:
            result = process(["*"], "menu*", menu_dict, context, walker)
            result = process(["^"], "again^", "Profile", context, walker)
        
        Notes:
            - Delegates to MenuModifier, CrumbsRewindModifier
            - Mode-specific behavior handled in domain modifiers
            - Maintains backward compatibility with all modifier types
        """
        # Use walker's display if available, otherwise use zOS display
        display = walker.display if walker else self.zos.display

        self._display_modifier(display, _LABEL_PROCESS_MODIFIERS, _DEFAULT_INDENT_PROCESS)
        self.logger.framework.debug(_LOG_MSG_RESOLVED, modifiers, zKey)

        # Priority 1: Menu modifier (*) → Delegate to MenuModifier
        if MOD_ASTERISK in modifiers:
            return self.menu_modifier.process(modifiers, zKey, zHorizontal, walker)

        # Priority 2: Crumbs-rewind modifier (^ suffix) → mint the bulk-back signal
        # `<key>^: <zPath>` → {'zCrumb': <zPath>}; the walker unwinds the trail to
        # that scope (pop_to_scope) or falls forward to zLink if it's not on it.
        if MOD_CARET in modifiers:
            return self.crumbs_modifier.process(zHorizontal)

        # `!` (Required) is RETIRED — gating is an event, not a modifier. No branch.

        # No modifiers: Pass through to launcher.
        # UI-element shorthand carrying a SCALAR value (e.g. `zCrumbs: true`) arrives
        # here as a bare bool/str. The launcher only routes str/dict/list and would
        # drop the bool (and mis-handle the str as a message/key), so the element would
        # render nothing. Re-wrap {key: value} so it flows through the dict path +
        # shorthand expander exactly like a dict-valued element — the expander coerces
        # the scalar to its default form (e.g. zCrumbs: true → {show: session}).
        if not isinstance(zHorizontal, (dict, list)):
            clean_key = zKey.split('__dup')[0].strip('*^') if zKey else zKey
            ui_keys = getattr(
                getattr(self.dispatch.launcher, 'shorthand_expander', None),
                'UI_ELEMENT_KEYS', ()
            )
            if clean_key in ui_keys:
                zHorizontal = {clean_key: zHorizontal}

        return self.dispatch.launcher.launch(zHorizontal, context=context, walker=walker)

    # ========================================================================
    # DISPLAY HELPERS
    # ========================================================================

    def _display_modifier(
        self,
        display: Any,
        label: str,
        indent: int,
        style: str = "wavy"
    ) -> None:
        """
        Display modifier processing label (optional UI styling).
        
        Args:
            display: zDisplay instance
            label: Label text to display
            indent: Indentation level
            style: Border style (default: "wavy")
        
        Notes:
            - Only displays if display instance is available
            - Uses zDisplay.zDeclare() for UI output
        """
        if display and hasattr(display, 'zDeclare'):
            display.zDeclare(
                label=label,
                indent=indent,
                style=style
            )
