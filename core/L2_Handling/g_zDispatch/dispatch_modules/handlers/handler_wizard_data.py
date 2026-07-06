# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/handlers/handler_wizard_data.py

"""
Wizard & Data Command Handlers
===============================

Extracted from dispatch_launcher.py to reduce file size.
Provides handlers for zWizard, zRead, and zData commands.
"""

from zOS import Any, Optional, Dict, Union, ast


class WizardDataHandlers:
    """Mixin providing wizard and data command handlers for CommandLauncher.
    
    Required Attributes (provided by CommandLauncher):
        - zos: zOS instance
        - logger: Logger instance
        - dispatch: Dispatch instance
    """

    zos: Any
    logger: Any
    dispatch: Any

    def _log_detected(self, _message: str) -> None:
        """Log detected command (provided by parent)."""
        pass

    def _display_handler(self, _label: str, _indent: int) -> None:
        """Display handler label (provided by parent)."""
        pass

    def _set_default_action(self, _req: Dict[str, Any], _default_action: str) -> None:
        """Set default action for data requests (provided by parent)."""
        pass

    def _handle_wizard_string(
        self,
        zHorizontal: str,
        walker: Optional[Any]
    ) -> Optional[Union[str, Any]]:
        """Handle zWizard string command.
        
        Args:
            zHorizontal: String in format "zWizard(...)"
            walker: Optional walker instance
        
        Returns:
            - Bifrost: Wizard result (zHat)
            - zCLI: "zBack" for navigation (or zHat if no walker)
        """
        from ..dispatch_constants import (
            CMD_PREFIX_ZWIZARD, _LABEL_HANDLE_ZWIZARD, _DEFAULT_INDENT_LAUNCHER,
        )

        self._log_detected("zWizard request")
        self._display_handler(_LABEL_HANDLE_ZWIZARD, _DEFAULT_INDENT_LAUNCHER)

        inner = zHorizontal[len(CMD_PREFIX_ZWIZARD):-1].strip()
        try:
            wizard_obj = ast.literal_eval(inner)

            if walker:
                zHat = walker.handle(wizard_obj)
            else:
                zHat = self.zos.zEngine.handle(wizard_obj)

            # zWizard NEVER drives navigation — walk forward, return zHat.
            return zHat
        except Exception as e:
            self.logger.error(f"Failed to parse zWizard payload: {e}")
            return None

    def _handle_wizard_dict(
        self,
        zHorizontal: Dict[str, Any],
        walker: Optional[Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Union[str, Any]]:
        """Handle zWizard dict command.
        
        Args:
            zHorizontal: Dict with "zWizard" key
            walker: Optional walker instance
            context: Optional context dict
        
        Returns:
            - Bifrost: Wizard result (zHat)
            - zCLI: "zBack" for navigation (or zHat if no walker)
        """
        from ..dispatch_constants import KEY_ZWIZARD

        self._log_detected("zWizard (dict)")

        self.logger.debug("=" * 80)
        self.logger.debug("[_handle_wizard_dict] ENTRY POINT")
        self.logger.debug(f"  Walker: {walker is not None}")
        self.logger.debug(f"  zWizard keys: {list(zHorizontal[KEY_ZWIZARD].keys())}")
        self.logger.debug("=" * 80)

        if walker:
            self.logger.debug("[_handle_wizard_dict] Calling walker.handle()")
            zHat = walker.handle(zHorizontal[KEY_ZWIZARD])
            self.logger.debug(f"[_handle_wizard_dict] walker.handle() returned: {type(zHat)}")
        else:
            self.logger.debug("[_handle_wizard_dict] Calling zos.zEngine.handle()")
            zHat = self.zos.zEngine.handle(zHorizontal[KEY_ZWIZARD])
            self.logger.debug(f"[_handle_wizard_dict] zos.zEngine.handle() returned: {type(zHat)}")

        # zWizard NEVER drives navigation — walk forward, return zHat. Navigation
        # is author-controlled from the zUI, never emitted by wizard completion.
        return zHat

    def _handle_read_string(
        self,
        zHorizontal: str,
        context: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        """Handle zRead string command.
        
        Args:
            zHorizontal: String in format "zRead(...)"
            context: Optional context dict
        
        Returns:
            Data result from zData.handle_request()
        """
        from ..dispatch_constants import (
            CMD_PREFIX_ZREAD, _LABEL_HANDLE_ZREAD_STRING, _DEFAULT_INDENT_LAUNCHER,
            KEY_ACTION, _DEFAULT_ACTION_READ, KEY_MODEL
        )

        self._log_detected("zRead request (string)")
        self._display_handler(_LABEL_HANDLE_ZREAD_STRING, _DEFAULT_INDENT_LAUNCHER)

        inner = zHorizontal[len(CMD_PREFIX_ZREAD):-1].strip()
        req = {KEY_ACTION: _DEFAULT_ACTION_READ}
        if inner:
            req[KEY_MODEL] = inner

        self.logger.framework.debug(f"Dispatching zRead (string) with request: {req}")
        return self.zos.data.handle_request(req, context=context)

    def _handle_read_dict(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        """Handle zRead dict command.
        
        Args:
            zHorizontal: Dict with "zRead" key
            context: Optional context dict
        
        Returns:
            Data result from zData.handle_request()
        """
        from ..dispatch_constants import (
            KEY_ZREAD, _LABEL_HANDLE_ZREAD_DICT, _DEFAULT_INDENT_LAUNCHER,
            KEY_MODEL, _DEFAULT_ACTION_READ
        )

        self._log_detected("zRead (dict)")
        self._display_handler(_LABEL_HANDLE_ZREAD_DICT, _DEFAULT_INDENT_LAUNCHER)

        req = zHorizontal.get(KEY_ZREAD) or {}
        if isinstance(req, str):
            req = {KEY_MODEL: req}

        self._set_default_action(req, _DEFAULT_ACTION_READ)

        self.logger.framework.debug(f"Dispatching zRead (dict) with request: {req}")
        return self.zos.data.handle_request(req, context=context)

    def _handle_data_dict(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        """Handle zData dict command.
        
        Args:
            zHorizontal: Dict with "zData" key
            context: Optional context dict
        
        Returns:
            Data result from zData.handle_request()
        """
        from ..dispatch_constants import (
            KEY_ZDATA, _LABEL_HANDLE_ZDATA_DICT, _DEFAULT_INDENT_LAUNCHER,
            KEY_MODEL, _DEFAULT_ACTION_READ
        )

        self._log_detected("zData (dict)")
        self._display_handler(_LABEL_HANDLE_ZDATA_DICT, _DEFAULT_INDENT_LAUNCHER)

        req = zHorizontal.get(KEY_ZDATA) or {}
        if isinstance(req, str):
            req = {KEY_MODEL: req}

        self._set_default_action(req, _DEFAULT_ACTION_READ)

        self.logger.framework.debug(f"Dispatching zData (dict) with request: {req}")
        return self.zos.data.handle_request(req, context=context)

    def _handle_implicit_wizard(
        self,
        zHorizontal: Dict[str, Any],
        walker: Optional[Any]
    ) -> Dict[str, Any]:
        """Handle implicit wizard (dict with multiple content keys).
        
        Args:
            zHorizontal: Dict command
            walker: Optional walker instance
        
        Returns:
            Wizard execution result (zHat)
        """
        self._log_detected("Implicit zWizard (multi-step)")

        if walker:
            zHat = walker.handle(zHorizontal)
        else:
            zHat = self.zos.zEngine.handle(zHorizontal)

        return zHat
