"""
zDispatch - String Command Handler
===================================

Extracted from dispatch_launcher.py Phase 4 refactoring.

Purpose:
    Handles string-based launch commands with prefix routing (zFunc, zLink, zOpen,
    zWizard, zRead) and mode-specific plain string handling (zCLI vs. Bifrost).

Dependencies:
    - subsystem_router.py (Phase 2) - for routing to subsystems
    - Integrates with zFunc, zOpen, navigation, and other subsystems

Author: zOS Framework
"""

from zOS import Any, Dict, Optional, Union

# Import dispatch constants
from ..dispatch_constants import (
    CMD_PREFIX_ZALPHA,
    CMD_PREFIX_ZFUNC,
    CMD_PREFIX_ZLINK,
    CMD_PREFIX_ZOPEN,
    CMD_PREFIX_ZWIZARD,
    CMD_PREFIX_ZREAD,
    KEY_MESSAGE,
    KEY_ZVAFILE,
    KEY_ZBLOCK,
    MODE_BIFROST,
    _DEFAULT_ZBLOCK,
    _LABEL_HANDLE_ZFUNC,
    _LABEL_HANDLE_ZLINK,
    _LABEL_HANDLE_ZOPEN,
    _DEFAULT_INDENT_HANDLER,
    _DEFAULT_INDENT_LAUNCHER
)

# Import mode detection (handled dynamically in tests, or via dispatcher)
# NOTE: This will be imported from the main dispatch context
try:
    from ....L1_Foundation.d_zSession.zSession_modules.session_bifrost_utils import is_bifrost_mode
except ImportError:
    def is_bifrost_mode(_session):
        """Mock for testing: always returns False (non-Bifrost mode)."""
        return False


class StringCommandHandler:
    """Handles execution of string-based commands."""

    def __init__(
        self,
        zos: Any,
        logger: Any,
        subsystem_router: Any,
        dispatcher_launch_fn: Any
    ) -> None:
        """
        Initialize the string command handler.
        
        Args:
            zos: Reference to zOS framework instance
            logger: Logger instance
            subsystem_router: SubsystemRouter instance from Phase 2
            dispatcher_launch_fn: Reference to dispatcher's launch() for recursion
        """
        self.zos = zos
        self.logger = logger
        self.subsystem_router = subsystem_router
        self.dispatcher_launch_fn = dispatcher_launch_fn

    def handle(
        self,
        zHorizontal: str,
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """
        Handle string-based launch commands (ORCHESTRATOR).
        
        Routes string commands based on prefix or mode-specific handling.
        
        Command prefixes:
        - zFunc(...): Function execution
        - zLink(...): Navigation link
        - zOpen(...): File/URL opening
        - zWizard(...): Multi-step workflow
        - zRead(...): Data read operation
        
        Plain strings (no prefix):
        - Terminal: Return None (display-only)
        - Bifrost: Resolve from zUI or return {"message": str}
        
        Args:
            zHorizontal: String command to execute
            context: Optional context dict
            walker: Optional walker instance
        
        Returns:
            Command execution result or None
        
        Examples:
            result = handler.handle("zFunc(calculate)", context, walker)
            result = handler.handle("zLink(menu:users)", context, walker)
            result = handler.handle("submit_button", bifrost_context, walker)
        """
        # ===== Greek-letter alias: zAlpha(...) → zLink(...) =====
        # zAlpha is the first-class name for the zLink event; zLink stays a
        # permanent alias. Canonicalize the imperative wrapper so the single
        # zLink branch below (and the resolver) stay one spelling.
        if zHorizontal.startswith(CMD_PREFIX_ZALPHA):
            zHorizontal = CMD_PREFIX_ZLINK + zHorizontal[len(CMD_PREFIX_ZALPHA):]

        # ===== Prefix-based routing (5 command types) =====

        if zHorizontal.startswith(CMD_PREFIX_ZFUNC):
            self.logger.framework.debug("[StringCommandHandler] Detected zFunc request")
            self._display_handler(_LABEL_HANDLE_ZFUNC, _DEFAULT_INDENT_HANDLER)
            return self.zos.zfunc.handle(zHorizontal)

        if zHorizontal.startswith(CMD_PREFIX_ZLINK):
            if not self._check_walker(walker, "zLink"):
                return None
            self.logger.framework.debug("[StringCommandHandler] Detected zLink request")
            self._display_handler(_LABEL_HANDLE_ZLINK, _DEFAULT_INDENT_LAUNCHER)
            return self.zos.navigation.handle_zLink(zHorizontal, walker=walker)

        if zHorizontal.startswith(CMD_PREFIX_ZOPEN):
            self.logger.framework.debug("[StringCommandHandler] Detected zOpen request")
            self._display_handler(_LABEL_HANDLE_ZOPEN, _DEFAULT_INDENT_LAUNCHER)
            return self.zos.open.handle(zHorizontal)

        if zHorizontal.startswith(CMD_PREFIX_ZWIZARD):
            return self._handle_wizard_string(zHorizontal, walker, context)

        if zHorizontal.startswith(CMD_PREFIX_ZREAD):
            return self._handle_read_string(zHorizontal, context)

        # ===== Plain string - mode-specific handling =====

        if is_bifrost_mode(self.zos.session):
            return self._resolve_plain_string_in_bifrost(zHorizontal, context, walker)

        # zCLI mode: Plain strings are displayed but return None
        return None

    # ========================================================================
    # INTERNAL HELPERS
    # ========================================================================

    def _resolve_plain_string_in_bifrost(
        self,
        zHorizontal: str,
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Union[Dict[str, Any], Any]:
        """
        Resolve plain string in Bifrost mode (attempts zUI resolution).
        
        Args:
            zHorizontal: Plain string key
            context: Context dict
            walker: Optional walker instance
        
        Returns:
            Resolved value (recursively launched) or {"message": str}
        
        Notes:
            - Attempts to resolve key from current zUI block
            - Recursively launches resolved value (could be dict with zFunc)
            - Falls back to {"message": str} if resolution fails
            - Error handling for missing zUI context
        """
        zVaFile = self.zos.zspark_obj.get(KEY_ZVAFILE)
        zBlock = self.zos.zspark_obj.get(KEY_ZBLOCK, _DEFAULT_ZBLOCK)

        if zVaFile and zBlock:
            try:
                raw_zFile = self.zos.loader.handle(zVaFile)
                if raw_zFile and zBlock in raw_zFile:
                    block_dict = raw_zFile[zBlock]

                    # Look up the key in the block
                    if zHorizontal in block_dict:
                        resolved_value = block_dict[zHorizontal]
                        self.logger.framework.debug(
                            f"[{MODE_BIFROST}] Resolved key '{zHorizontal}' from zUI to: {resolved_value}"
                        )
                        # Recursively launch with the resolved value
                        return self.dispatcher_launch_fn(resolved_value, context=context, walker=walker)
                    else:
                        self.logger.framework.debug(
                            f"[{MODE_BIFROST}] Key '{zHorizontal}' not found in zUI block '{zBlock}'"
                        )
            except Exception as e:
                self.logger.warning(f"[{MODE_BIFROST}] Error resolving key from zUI: {e}")

        # If we couldn't resolve it, return as display message
        self.logger.framework.debug(f"Plain string in {MODE_BIFROST} mode - returning as message")
        return {KEY_MESSAGE: zHorizontal}

    def _handle_wizard_string(
        self,
        zHorizontal: str,
        walker: Optional[Any],
        _context: Optional[Dict[str, Any]]
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """
        Route zWizard(...) string command by parsing and converting to dict format.
        
        Parses "zWizard({...})" string, extracts payload, and routes to subsystem router.
        """
        import ast
        if not self._check_walker(walker, "zWizard"):
            return None
        
        # Parse string: "zWizard({...})" -> {...}
        inner = zHorizontal[len(CMD_PREFIX_ZWIZARD):-1].strip()
        try:
            wizard_obj = ast.literal_eval(inner)
            # Convert to dict format for route_zwizard
            return self.subsystem_router.route_zwizard({"zWizard": wizard_obj}, walker)
        except Exception as e:
            self.logger.error(f"Failed to parse zWizard payload: {e}")
            return None

    def _handle_read_string(
        self,
        zHorizontal: str,
        context: Optional[Dict[str, Any]]
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """Route zRead(...) string command to subsystem router."""
        return self.subsystem_router.route_zread(zHorizontal, context)

    def _display_handler(self, label: str, indent: int) -> None:
        """Display handling message if display system is available.

        Uses zDeclare like every other dispatch handler — the old
        display.zBasics API no longer exists and raised AttributeError,
        aborting the walker mid-block (e.g. a plain key carrying a
        zLink(...) string inside a zTerminal-spawned zui snippet).
        """
        display = getattr(self.zos, 'display', None)
        if display:
            display.zDeclare(label, color="DISPATCH", indent=indent, style="single")

    def _check_walker(self, walker: Optional[Any], command_name: str) -> bool:
        """
        Validate walker instance exists for navigation commands.
        
        Args:
            walker: Walker instance to check
            command_name: Name of command requiring walker (for error message)
        
        Returns:
            True if walker is valid, False otherwise
        """
        if walker is None:
            self.logger.error(
                f"[StringCommandHandler] {command_name} requires walker but walker is None"
            )
            return False
        return True
