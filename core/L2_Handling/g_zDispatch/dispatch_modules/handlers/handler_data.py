# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/handlers/handler_data.py

"""
Data Handler Module for zDispatch Subsystem.

This module provides the DataHandler class, which routes zRead and zData
commands to the zData subsystem. It handles string and dict formats for
data operations.

Extracted from dispatch_launcher.py as part of Phase 2 refactoring.

Supported Commands:
    - zRead(model): Read operation on model (string format)
    - zRead: {model: "...", where: {...}} (dict format)
    - zData: {action: "create", model: "...", values: {...}} (dict format)

Features:
    - Default action "read" for zRead commands
    - String and dict format support
    - Context passing for data operations
    - Debug logging for data routing

Usage Example:
    handler = DataHandler(zos, display, logger)
    
    # String format
    result = handler.handle_read_string("zRead(users)", context)
    
    # Dict format
    result = handler.handle_read_dict({"zRead": {"model": "users", "limit": 10}}, context)
    result = handler.handle_data_dict({"zData": {"action": "create", "model": "users", "values": {...}}}, context)

Integration:
    - zData: Query execution via zos.data.handle_request()
    - zLoom (zos.zloom): Data block resolution via resolver.resolve_block_data()
    - zDisplay: Handler label display (optional)

Thread Safety:
    - Stateless operations (no instance state mutation)
    - Safe for concurrent execution
"""

from zOS import Any, Dict, Optional

# Import dispatch constants
from ..dispatch_constants import (
    KEY_ACTION,
    KEY_MODEL,
    KEY_ZREAD,
    KEY_ZDATA,
    CMD_PREFIX_ZREAD,
    _DEFAULT_ACTION_READ,
    _LABEL_HANDLE_ZREAD_STRING,
    _LABEL_HANDLE_ZREAD_DICT,
    _LABEL_HANDLE_ZDATA_DICT,
    _DEFAULT_INDENT_LAUNCHER,
)

class DataHandler:
    """
    Routes data commands (zRead, zData) to zData subsystem.
    
    This class provides focused routing for data operations,
    extracting parameters from command strings/dicts and dispatching
    to the appropriate zData handlers.
    
    Attributes:
        zos: zOS framework instance (provides data subsystem)
        display: zDisplay instance for UI output (optional)
        logger: Logger instance for debug output
    
    Methods:
        handle_read_string(): Route zRead string command to zData
        handle_read_dict(): Route zRead dict command to zData
        handle_data_dict(): Route zData dict command to zData
    
    Example:
        handler = DataHandler(zos, display, logger)
        result = handler.handle_read_string("zRead(users)", context)
    """

    def __init__(self, zos: Any, display: Any, logger: Any) -> None:
        """
        Initialize data handler.
        
        Args:
            zos: zOS framework instance (provides data subsystem)
            display: zDisplay instance for UI output
            logger: Logger instance for debug output
        
        Example:
            handler = DataHandler(zos, display, logger)
        """
        self.zos = zos
        self.display = display
        self.logger = logger

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def handle_read_string(
        self,
        zHorizontal: str,
        context: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        """
        Handle zRead string command.
        
        Parses the model name from string format and dispatches to zData subsystem
        with default action "read".
        
        Args:
            zHorizontal: String command in format "zRead(...)"
            context: Optional context dict for data operation
        
        Returns:
            Data result from zData.handle_request() (typically dict or list)
        
        Example:
            result = handler.handle_read_string("zRead(users)", context)
        
        Notes:
            - Empty payload: {"action": "read"} (no model specified)
            - Non-empty payload: {"action": "read", "model": "..."}
            - Dispatched to zData.handle_request()
        """
        self.logger.framework.debug("zRead request (string)")
        self._display_handler(_LABEL_HANDLE_ZREAD_STRING, _DEFAULT_INDENT_LAUNCHER)

        # Extract and build request
        inner = zHorizontal[len(CMD_PREFIX_ZREAD):-1].strip()
        req = {KEY_ACTION: _DEFAULT_ACTION_READ}
        if inner:
            req[KEY_MODEL] = inner

        self.logger.framework.debug(f"Dispatching zRead (string) with request: {req}")
        return self.zos.data.handle_request(req, context=context)

    def handle_read_dict(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        """
        Handle zRead dict command.
        
        Extracts the read request from dict format and dispatches to zData subsystem
        with default action "read".
        
        Args:
            zHorizontal: Dict command with "zRead" key
            context: Optional context dict for data operation
        
        Returns:
            Data result from zData.handle_request() (typically dict or list)
        
        Example:
            result = handler.handle_read_dict({"zRead": {"model": "users", "where": {"id": 1}}}, context)
        
        Notes:
            - String payload: {"zRead": "users"} -> {"action": "read", "model": "users"}
            - Dict payload: {"zRead": {...}} -> {action: "read", ...}
            - Sets default action if not specified
        """
        self.logger.framework.debug("zRead (dict)")
        self._display_handler(_LABEL_HANDLE_ZREAD_DICT, _DEFAULT_INDENT_LAUNCHER)

        # Extract and normalize request
        req = zHorizontal.get(KEY_ZREAD) or {}
        if isinstance(req, str):
            req = {KEY_MODEL: req}

        self._set_default_action(req, _DEFAULT_ACTION_READ)

        self.logger.framework.debug(f"Dispatching zRead (dict) with request: {req}")
        return self.zos.data.handle_request(req, context=context)

    def handle_data_dict(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        """
        Handle zData dict command.
        
        Extracts the data request from dict format and dispatches to zData subsystem
        with default action "read".
        
        Args:
            zHorizontal: Dict command with "zData" key
            context: Optional context dict for data operation
        
        Returns:
            Data result from zData.handle_request() (typically dict or list)
        
        Example:
            result = handler.handle_data_dict({"zData": {"action": "create", "model": "users", ...}}, context)
        
        Notes:
            - String payload: {"zData": "users"} -> {"action": "read", "model": "users"}
            - Dict payload: {"zData": {...}} -> {action: "read" (default), ...}
            - Sets default action if not specified
        """
        self.logger.framework.debug("zData (dict)")
        self._display_handler(_LABEL_HANDLE_ZDATA_DICT, _DEFAULT_INDENT_LAUNCHER)

        # Extract and normalize request
        req = zHorizontal.get(KEY_ZDATA) or {}
        if isinstance(req, str):
            req = {KEY_MODEL: req}

        self._set_default_action(req, _DEFAULT_ACTION_READ)

        self.logger.framework.debug(f"Dispatching zData (dict) with request: {req}")
        return self.zos.data.handle_request(req, context=context)

    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================

    def _display_handler(self, label: str, indent: int) -> None:
        """Display handling message if display system is available."""
        if self.display:
            self.display.zDeclare(label, color="DISPATCH", indent=indent, style="single")

    def _set_default_action(self, req: Dict[str, Any], default_action: str) -> None:
        """Set default action if not present in request."""
        if KEY_ACTION not in req:
            req[KEY_ACTION] = default_action
