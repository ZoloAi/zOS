# zOS/core/L2_Handling/g_zDispatch/zDispatch.py

"""
zDispatch - Core Command Dispatch Subsystem (Facade).

This module provides the zDispatch class, which acts as a facade for command
dispatch and routing in zOS. It orchestrates two core components (CommandLauncher
and ModifierProcessor) to provide flexible command execution with modifier support.

Facade Pattern:
    The zDispatch class implements the Facade design pattern, providing a simplified
    interface to the complex subsystem of command dispatch and routing:
    
    1. Component Initialization:
       - ModifierProcessor: Handles prefix (~) and suffix (* ! ^) modifiers
       - CommandLauncher: Executes commands in various formats (string, dict)
    
    2. Orchestration Flow:
       - Check for modifiers (prefix + suffix detection)
       - If modifiers present → Route to ModifierProcessor.process()
       - If no modifiers → Route to CommandLauncher.launch()
    
    3. Result Handling:
       - Return processed result to caller
       - Mode-specific returns (zCLI vs. Bifrost)

Architecture:
    zDispatch (Facade)
        ├── __init__()           # Initialize subsystem, create components
        │   ├── ModifierProcessor  # Detect & process modifiers (^ ~ * !)
        │   └── CommandLauncher    # Execute commands (zFunc, zWizard, zDialog, etc.)
        │
        ├── handle()             # Main entry point for command dispatch
        │   ├── Check for modifiers (prefix + suffix)
        │   ├── If modifiers → modifiers.process()
        │   └── Else → launcher.launch()
        │
        └── Standalone API
            └── handle_zDispatch()  # Convenience function for external callers

Forward Dependencies:
    This facade orchestrates components that interact with 7 future subsystems:
    
    - zNavigation: Menu creation and navigation
    - zParser: Plugin invocation resolution
    - zLoader: zUI file loading
    - zFunc: Function execution
    - zDialog: Interactive forms
    - zWizard: Multi-step workflows
    - zData: Data management and CRUD operations

Integration:
    - zConfig: Session constants (future: SESSION_KEY_ZMODE)
    - zDisplay: UI output (zDeclare) and user interaction
    - zSession: Context passing for mode detection
    - zAuth: Authentication state passed through context

Usage Examples:
    # Using the class directly
    dispatch = zDispatch(zos)
    result = dispatch.handle("action", {"zFunc": "my_function"})
    
    # With modifiers
    result = dispatch.handle("^save", {"zFunc": "save"})  # Bounce back
    result = dispatch.handle("menu*", menu_dict)          # Create menu
    
    # Using the standalone function
    result = handle_zDispatch("action", command, zos=zos)
    
    # With walker context (in wizards)
    result = handle_zDispatch("action", command, walker=walker)

Thread Safety:
    - Relies on thread-safe instances from zOS (logger, display, session)
    - No internal state mutation during dispatch
    - Components (ModifierProcessor, CommandLauncher) are stateless

Constants:
    All magic strings are replaced with module constants to improve maintainability
    and reduce the risk of typos.
"""


__version__ = "1.0.0"
from zOS import Any, Optional, Dict
from zOS.L1_Foundation.a_zConfig.zConfig_modules import SESSION_KEY_ZMODE, ZMODE_ZBIFROST

from zSys.Utils import validate_zos_instance

from .dispatch_modules.dispatch_modifiers import ModifierProcessor
from .dispatch_modules.dispatch_launcher import CommandLauncher
from .dispatch_modules.shorthand_expander import ShorthandExpander

# Import all constants from centralized location
from .dispatch_modules.dispatch_constants import (
    # Public constants
    SUBSYSTEM_NAME,
    SUBSYSTEM_COLOR,
    ERR_NO_ZOS_OR_WALKER,
    # zCrumbs bulk-rewind (longhand → bulk-back signal)
    ZCRUMB_SIGNAL,
    ZCRUMBS_ADVERB_ZBACK,
    # Internal constants
    _MSG_READY,
    _MSG_HANDLE,
    _LOG_MSG_READY,
    _LOG_MSG_HORIZONTAL,
    _LOG_MSG_HANDLE_KEY,
    _LOG_MSG_PREFIX_MODS,
    _LOG_MSG_SUFFIX_MODS,
    _LOG_MSG_DETECTED_MODS,
    _LOG_MSG_MODIFIER_RESULT,
    _LOG_MSG_DISPATCH_RESULT,
    _LOG_MSG_COMPLETED,
    _STYLE_FULL,
    _INDENT_ROOT,
    _INDENT_HANDLE,
)


class zDispatch:
    """
    Core command dispatch subsystem for zOS (Facade).
    
    Orchestrates command routing through ModifierProcessor and CommandLauncher,
    providing a simplified interface for command execution with modifier support.
    
    Attributes:
        zos: zOS framework instance
        session: Session dictionary from zOS
        logger: Logger instance from zOS
        mycolor: Color identifier for display ("DISPATCH")
        modifiers: ModifierProcessor instance (handles ^ ~ * !)
        launcher: CommandLauncher instance (executes commands)
    
    Methods:
        handle(): Main entry point for command dispatch
        
        Helper methods (DRY):
        _get_display(): Get appropriate display instance (walker or zOS)
        _display_message(): Display message with consistent styling
    
    Integration:
        - ModifierProcessor: Detects and processes prefix/suffix modifiers
        - CommandLauncher: Executes commands in various formats
        - zDisplay: UI output via zDeclare()
        - zSession: Context passing for mode detection
    
    Example:
        dispatch = zDispatch(zos)
        result = dispatch.handle("action", {"zFunc": "my_function"})
    """

    # Class-level type declarations
    zos: Any  # zOS framework instance
    session: Dict[str, Any]  # Session dictionary
    logger: Any  # Logger instance
    mycolor: str  # Color identifier
    modifiers: ModifierProcessor  # Modifier processor
    launcher: CommandLauncher  # Command launcher

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any) -> None:
        """
        Initialize zDispatch subsystem.
        
        Creates ModifierProcessor and CommandLauncher components, stores references
        to zOS instance, session, and logger, and displays ready message.
        
        Args:
            zos: zOS framework instance providing access to session, logger, and display
        
        Raises:
            ValueError: If zos parameter is None
        
        Examples:
            # Initialize as part of zOS startup
            dispatch = zDispatch(zos)
            
            # Access components
            dispatch.modifiers.check_suffix("again^")  # Returns ["^"]
            dispatch.launcher.launch({"zFunc": "my_func"})
        
        Notes:
            - Validates zos parameter before initialization
            - Displays ready message using zDisplay
            - Logs initialization to zOS logger
            - Creates stateless components (ModifierProcessor, CommandLauncher)
        """
        validate_zos_instance(zos, SUBSYSTEM_NAME)

        self.zos = zos
        self.logger = zos.logger
        self.mycolor = SUBSYSTEM_COLOR

        # Initialize components (Facade pattern)
        self.modifiers = ModifierProcessor(self)
        self.launcher = CommandLauncher(self)

        # Display ready message using zDisplay
        self._display_message(self.zos.display, _MSG_READY, _INDENT_ROOT)

        self.logger.framework.debug(_LOG_MSG_READY)

    # ========================================================================
    # PUBLIC METHODS - Main Entry Point
    # ========================================================================

    def handle(
        self,
        zKey: str,
        zHorizontal: Any,
        context: Optional[Dict[str, Any]] = None,
        walker: Optional[Any] = None
    ) -> Optional[Any]:
        """
        Handle command dispatch with optional wizard context and walker.
        
        Main entry point for command routing. Detects modifiers (^ ~ * !) and
        routes to appropriate handler (ModifierProcessor or CommandLauncher).
        
        Args:
            zKey: Command key (may include modifiers, e.g., "^action", "menu*")
            zHorizontal: Command data (string, dict, or other format)
            context: Optional context dict with mode and session metadata
            walker: Optional walker instance for navigation and display
        
        Returns:
            Command execution result (type varies by command):
            - Modifier results: "zBack", "stop", or processed result
            - Command results: Action-specific return value
            - None: If execution fails or command not found
        
        Examples:
            # Simple command (no modifiers)
            result = dispatch.handle("action", {"zFunc": "my_function"})
            
            # Bounce back modifier (^)
            result = dispatch.handle("^save", {"zFunc": "save_data"})
            # Terminal: Returns "zBack"
            # Bifrost: Returns save_data result
            
            # Menu modifier (*)
            result = dispatch.handle("menu*", menu_dict)
            # Creates menu via zNavigation.create()
            
            # Anchor + Menu (~*)
            result = dispatch.handle("~menu*", menu_dict)
            # Creates anchored menu (no back button)
            
            # Required modifier (!)
            result = dispatch.handle("validate!", {"zFunc": "validate"})
            # Retries until validate() returns True
            
            # With walker context (in wizard)
            result = dispatch.handle("action", cmd, context=ctx, walker=walker)
        
        Notes:
            - Uses walker.display if available, otherwise zos.display
            - Logs all steps for debugging
            - Detects prefix modifiers (~) and suffix modifiers (* ! ^)
            - Routes to ModifierProcessor if modifiers detected
            - Routes to CommandLauncher if no modifiers
            - Mode-specific returns handled by ModifierProcessor
        
        Flow:
            1. Display "handle zDispatch" message
            2. Log zHorizontal and zKey
            3. Check for prefix modifiers (~)
            4. Check for suffix modifiers (* ! ^)
            5. Combine modifiers
            6. If modifiers → modifiers.process()
            7. Else → launcher.launch()
            8. Log result and return
        """
        # Get appropriate display instance (walker or zCLI)
        display = self._get_display(walker)

        self._display_message(display, _MSG_HANDLE, _INDENT_HANDLE)

        self.logger.framework.debug(_LOG_MSG_HORIZONTAL, zHorizontal)
        self.logger.framework.debug(_LOG_MSG_HANDLE_KEY, zKey)

        # Detect modifiers (prefix + suffix)
        prefix_mods = self.modifiers.check_prefix(zKey)
        suffix_mods = self.modifiers.check_suffix(zKey)
        zModifiers = prefix_mods + suffix_mods

        self.logger.framework.debug(_LOG_MSG_PREFIX_MODS, prefix_mods)
        self.logger.framework.debug(_LOG_MSG_SUFFIX_MODS, suffix_mods)
        self.logger.framework.debug(_LOG_MSG_DETECTED_MODS, zKey, zModifiers)

        # Route to appropriate handler (Facade orchestration)
        if zModifiers:
            # Route to ModifierProcessor
            result = self.modifiers.process(zModifiers, zKey, zHorizontal, context=context, walker=walker)
            self.logger.framework.debug(_LOG_MSG_MODIFIER_RESULT, result)
        else:
            # ═══════════════════════════════════════════════════════════════
            # KEY-LEVEL SHORTHAND WRAPPING (2026-01-29)
            # If the KEY is a UI element shorthand (zTerminal, zImage, etc.)
            # and the VALUE is a dict, wrap {key: value} so expansion works
            # ═══════════════════════════════════════════════════════════════
            clean_key = zKey.split('__dup')[0] if '__dup' in zKey else zKey
            # zCrumbs bulk-rewind LONGHAND: zCrumbs: { show: none, zBack: <zPath> }.
            # Collapse to the SSOT bulk-back signal (identical to the `<key>^` sugar)
            # so the walker unwinds the trail via handle_zCrumb_back instead of
            # rendering a banner. A plain zCrumbs (no zBack adverb) still flows to
            # the display expander below as before.
            if (clean_key == 'zCrumbs' and isinstance(zHorizontal, dict)
                    and ZCRUMBS_ADVERB_ZBACK in zHorizontal):
                target = zHorizontal.get(ZCRUMBS_ADVERB_ZBACK)
                self.logger.framework.debug(
                    f"[zDispatch] zCrumbs rewind → {{'{ZCRUMB_SIGNAL}': {target!r}}}"
                )
                return {ZCRUMB_SIGNAL: target}
            # zCrumbs bulk-rewind WRAPPED LONGHAND: <option>: { zCrumbs: { show:
            # none, zBack: <target> } }. This is the true longhand of `<option>^:
            # <target>` as a NAMED menu option — the `^` suffix mints the signal
            # for ANY key via the modifier path, so the longhand must reach the
            # SAME signal even when zCrumbs is the BODY of an arbitrary key, not a
            # direct `zCrumbs:` step. Without this the two forms diverge (SSOT
            # split): `again^: Profile` rewinds, `again: {zCrumbs:{…}}` renders a
            # show:none banner and falls through to the next step.
            if isinstance(zHorizontal, dict):
                _crumb_body = zHorizontal.get('zCrumbs')
                if (isinstance(_crumb_body, dict)
                        and ZCRUMBS_ADVERB_ZBACK in _crumb_body):
                    target = _crumb_body.get(ZCRUMBS_ADVERB_ZBACK)
                    self.logger.framework.debug(
                        f"[zDispatch] zCrumbs rewind (wrapped '{clean_key}') → "
                        f"{{'{ZCRUMB_SIGNAL}': {target!r}}}"
                    )
                    return {ZCRUMB_SIGNAL: target}
            # Subsystem keys used as wizard step names (e.g. zVaF: { zDialog: {...} })
            # must be wrapped so _launch_dict can detect them via KEY_ZDIALOG/KEY_ZFUNC/...
            # Without this, the wrapper key is dropped and the inner body is mis-routed
            # (e.g. zDialog body falls through to organizational structure handling).
            _SUBSYSTEM_STEP_KEYS = {
                # zAlpha — Greek-letter alias for zLink (normalized to zLink in
                # _launch_dict). Listed so a bare `zAlpha:` step key is wrapped
                # for routing, exactly like its zLink twin.
                'zDialog', 'zFunc', 'zDisplay', 'zLink', 'zAlpha', 'zDelta',
                # zMenu — the longhand of the `*` key-modifier. The walker dispatches
                # it as a bare key (execute_loop → handle), so it must be wrapped here
                # for _launch_dict to detect KEY_ZMENU and route to handle_zmenu (the
                # ONE menu engine). Without this, the bare {title, options} value has
                # no zMenu key, the route misses, and zCLI renders the sibling options
                # ungated — the Bifrost serializer (_defer_menu_options) is unaffected
                # because the organizational path calls _launch_dict(val) directly.
                'zMenu',
                'zRead', 'zData', 'zWizard', 'zLogin', 'zLogout', 'zOpen',
                'zExport',
                'zImport',
                'zTransfer',
            }
            if clean_key in ShorthandExpander.UI_ELEMENT_KEYS and isinstance(zHorizontal, (dict, str, bool)):
                # Wrap key-value pair so shorthand expansion can see the key.
                # Handles dict form (zText: {content: ...}), scalar string form
                # (zText: "..."), AND bare bool shorthand (zCrumbs: true) — the
                # expander coerces the scalar to its default form (true → {show: session}).
                wrapped = {zKey: zHorizontal}
                self.logger.framework.debug(f"[zDispatch] Wrapped UI element shorthand '{zKey}' for expansion")
                result = self.launcher.launch(wrapped, context=context, walker=walker)
            elif clean_key in _SUBSYSTEM_STEP_KEYS and isinstance(zHorizontal, (dict, str, list)):
                wrapped = {clean_key: zHorizontal}
                self.logger.framework.debug(f"[zDispatch] Wrapped subsystem step '{zKey}' for routing")
                result = self.launcher.launch(wrapped, context=context, walker=walker)
            else:
                # Route to CommandLauncher (normal flow)
                result = self.launcher.launch(zHorizontal, context=context, walker=walker)
            self.logger.framework.debug(_LOG_MSG_DISPATCH_RESULT, result)

        self.logger.framework.debug(_LOG_MSG_COMPLETED, zKey)
        return result

    # ========================================================================
    # HELPER METHODS - DRY Refactoring
    # ========================================================================

    def _get_display(self, walker: Optional[Any]) -> Any:
        """
        Get appropriate display instance (walker.display or zos.display).
        
        Args:
            walker: Optional walker instance
        
        Returns:
            Display instance (walker.display if walker exists, else zos.display)
        
        Example:
            display = self._get_display(walker)
            display.zDeclare("message", ...)
        
        Notes:
            - Avoids repeated "walker.display if walker else self.zos.display" pattern
            - Centralizes display resolution logic
        """
        return walker.display if walker else self.zos.display

    def _display_message(self, display: Any, message: str, indent: int) -> None:
        """
        Display message with consistent styling.
        
        Args:
            display: Display instance (walker.display or zos.display)
            message: Message to display
            indent: Indentation level (spaces)
        
        Example:
            self._display_message(display, _MSG_READY, _INDENT_ROOT)
        
        Notes:
            - Uses subsystem color (self.mycolor) for consistency
            - Uses _STYLE_FULL for all dispatch messages
            - Avoids repeated zDeclare calls with identical styling
        """
        display.zDeclare(message, color=self.mycolor, indent=indent, style=_STYLE_FULL)


# ============================================================================
# STANDALONE API - Convenience Function
# ============================================================================

def handle_zDispatch(
    zKey: str,
    zHorizontal: Any,
    zos: Optional[Any] = None,
    walker: Optional[Any] = None,
    context: Optional[Dict[str, Any]] = None
) -> Optional[Any]:
    """
    Standalone dispatch function with optional wizard context and walker.
    
    Convenience function that provides a simplified interface to zDispatch.handle()
    without requiring direct access to the dispatch instance. Automatically resolves
    the zOS instance from either the zos or walker parameter.
    
    Args:
        zKey: Command key (may include modifiers, e.g., "^action", "menu*")
        zHorizontal: Command data (string, dict, or other format)
        zos: Optional zOS framework instance (used if walker not provided)
        walker: Optional walker instance (takes precedence over zos)
        context: Optional context dict with mode and session metadata
    
    Returns:
        Command execution result from dispatch.handle()
    
    Raises:
        ValueError: If neither zos nor walker parameter is provided
    
    Examples:
        # With explicit zos instance
        result = handle_zDispatch("action", {"zFunc": "my_func"}, zos=zos)
        
        # With walker context (in wizard)
        result = handle_zDispatch("action", cmd, walker=walker)
        
        # With modifiers
        result = handle_zDispatch("^save", {"zFunc": "save"}, zos=zos)
        
        # With context for request-scoped data
        result = handle_zDispatch(
            "action",
            cmd,
            zos=zos,
            context={"websocket_data": data}
        )
        
        # Note: Mode is detected from session[SESSION_KEY_ZMODE], not context
    
    Notes:
        - Walker parameter takes precedence over zos parameter
        - Uses walker.zos if walker is provided
        - Requires at least one of zos or walker
        - Delegates to zOS dispatch subsystem (zos.dispatch.handle)
    
    Resolution Flow:
        1. If walker → use walker.zos
        2. Else if zos → use zos
        3. Else → raise ValueError
        4. Call zos_instance.dispatch.handle()
    """
    # Determine zOS instance (walker takes precedence)
    if walker:
        zos_instance = walker.zos
    elif zos:
        zos_instance = zos
    else:
        raise ValueError(ERR_NO_ZOS_OR_WALKER)

    # Check if we're in zBifrost mode (event capture mode)
    # Mode is now sourced from session (canonical source)
    is_bifrost = zos_instance.session.get(SESSION_KEY_ZMODE) == ZMODE_ZBIFROST

    # Clear event buffer before execution (for clean capture)
    if is_bifrost and hasattr(zos_instance.display, 'clear_event_buffer'):
        zos_instance.display.clear_event_buffer()

    # Use zOS dispatch subsystem
    result = zos_instance.dispatch.handle(zKey, zHorizontal, context=context, walker=walker)

    # Collect buffered events after execution (zBifrost mode only)
    if is_bifrost and hasattr(zos_instance.display, 'collect_buffered_events'):
        buffered_events = zos_instance.display.collect_buffered_events()

        # Return structured response with events
        if buffered_events:
            return {
                'result': result,
                'events': buffered_events
            }

    # zCLI mode or no events: return result directly
    return result
