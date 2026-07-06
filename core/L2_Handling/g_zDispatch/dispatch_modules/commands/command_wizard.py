# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/commands/command_wizard.py

"""
Wizard Command Handler for zDispatch Subsystem.

This module provides the WizardHandler class, which processes zWizard commands
in both string and dict formats. Wizards are multi-step workflows that guide
users through complex operations.

Extracted from dispatch_launcher.py as part of Phase 2 refactoring.

Supported Commands:
    - zWizard({steps: [...]}) - String format with dict literal
    - {zWizard: {steps: [...]}} - Dict format

Features:
    - String payload parsing via ast.literal_eval()
    - Mode-specific returns (zBack for zCLI, zHat for Bifrost)
    - Walker delegation (walker extends wizard)
    - Nested wizard support (organizational containers)

Usage Example:
    handler = WizardHandler(zos, display, logger)
    
    # String format
    result = handler.handle_string("zWizard({'steps': [...]})", walker)
    
    # Dict format
    result = handler.handle_dict({"zWizard": {"steps": [...]}}, walker, context)

Integration:
    - zWizard: Wizard execution via zos.zEngine.handle()
    - zNavigation: Walker for navigation context
    - Mode detection: is_bifrost_mode() for mode-specific returns

Thread Safety:
    - Stateless operations (no instance state mutation)
    - Safe for concurrent execution
"""

import ast
from zOS import Any, Dict, Optional, Union

# Import dispatch constants
from ..dispatch_constants import (
    KEY_ZWIZARD,
    CMD_PREFIX_ZWIZARD,
    _LABEL_HANDLE_ZWIZARD,
    _DEFAULT_INDENT_LAUNCHER,
)


class WizardHandler:
    """
    Processes wizard commands (zWizard) in string and dict formats.
    
    This class handles multi-step workflow execution, delegating to
    the zWizard subsystem or walker (if available for navigation context).
    
    Attributes:
        zos: zOS framework instance (provides wizard subsystem, session)
        display: zDisplay instance for UI output (optional)
        logger: Logger instance for debug output
    
    Methods:
        handle_string(): Process zWizard string command
        handle_dict(): Process zWizard dict command
    
    Example:
        handler = WizardHandler(zos, display, logger)
        result = handler.handle_string("zWizard({'steps': [...]})", walker)
    """

    def __init__(self, zos: Any, display: Any, logger: Any) -> None:
        """
        Initialize wizard handler.
        
        Args:
            zos: zOS framework instance (provides wizard subsystem, session)
            display: zDisplay instance for UI output
            logger: Logger instance for debug output
        
        Example:
            handler = WizardHandler(zos, display, logger)
        """
        self.zos = zos
        self.display = display
        self.logger = logger

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def handle_string(
        self,
        zHorizontal: str,
        walker: Optional[Any]
    ) -> Optional[Union[str, Any]]:
        """
        Handle zWizard string command.
        
        Parses the wizard payload from string format and executes it via walker or
        wizard subsystem. Returns mode-specific results (zBack for Terminal, zHat for Bifrost).
        
        Args:
            zHorizontal: String command in format "zWizard(...)"
            walker: Optional walker instance (preferred for navigation context)
        
        Returns:
            - Bifrost mode: zHat (actual wizard result)
            - zCLI/Walker mode: "zBack" (for navigation) or zHat (no walker)
            - Parse error: None
        
        Example:
            result = handler.handle_string("zWizard({'steps': [...])})", walker)
        
        Notes:
            - Uses ast.literal_eval() for safe payload parsing
            - Walker extends wizard, so walker.handle() is preferred over wizard.handle()
            - Mode-specific returns enable proper zCLI vs. API behavior
        """
        self.logger.framework.debug("zWizard request")
        self._display_handler(_LABEL_HANDLE_ZWIZARD, _DEFAULT_INDENT_LAUNCHER)

        # Extract and parse payload
        inner = zHorizontal[len(CMD_PREFIX_ZWIZARD):-1].strip()
        try:
            wizard_obj = ast.literal_eval(inner)

            # Use modern OOP API - walker extends wizard, so it has handle()
            if walker:
                zHat = walker.handle(wizard_obj)
            else:
                zHat = self.zos.zEngine.handle(wizard_obj)

            # zWizard NEVER drives navigation — it walks forward and returns its
            # zHat result. Any zBack/exit must come from the zUI (^ modifier, zBtn
            # action, zLink), not from wizard completion. Same in zCLI and Bifrost.
            return zHat
        except Exception as e:
            self.logger.error(f"Failed to parse zWizard payload: {e}")
            return None

    def handle_dict(
        self,
        zHorizontal: Dict[str, Any],
        walker: Optional[Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Union[str, Any]]:
        """
        Handle zWizard dict command.
        
        Executes wizard payload from dict format via walker or wizard subsystem.
        Returns mode-specific results (zBack for Terminal, zHat for Bifrost).
        
        Args:
            zHorizontal: Dict command with "zWizard" key
            walker: Optional walker instance (preferred for navigation context)
            context: Optional context dict with mode metadata
        
        Returns:
            - Bifrost mode: zHat (actual wizard result)
            - zCLI/Walker mode: "zBack" (for navigation) or zHat (no walker)
        
        Example:
            result = handler.handle_dict({"zWizard": {"steps": [...]}}, walker, context)
        
        Notes:
            - No parsing needed (already dict format)
            - Walker extends wizard, so walker.handle() is preferred
            - Mode-specific returns enable proper zCLI vs. API behavior
        """
        self.logger.framework.debug("zWizard (dict)")

        # Use modern OOP API - walker extends wizard, so it has handle()
        if walker:
            self.logger.debug("[handle_dict] Calling walker.handle()")
            zHat = walker.handle(zHorizontal[KEY_ZWIZARD])
            self.logger.debug(f"[handle_dict] walker.handle() returned: {type(zHat)}")
        else:
            self.logger.debug("[handle_dict] Calling zos.zEngine.handle()")
            zHat = self.zos.zEngine.handle(zHorizontal[KEY_ZWIZARD])
            self.logger.debug(f"[handle_dict] zos.zEngine.handle() returned: {type(zHat)}")

        # zWizard NEVER drives navigation — it walks forward and returns its zHat
        # result (same in zCLI and Bifrost). Navigation is author-controlled from
        # the zUI (^ modifier, zBtn action, zLink), never emitted by completion.
        return zHat

    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================

    def _display_handler(self, label: str, indent: int) -> None:
        """Display handling message if display system is available."""
        if self.display:
            self.display.zDeclare(label, color="DISPATCH", indent=indent, style="single")
