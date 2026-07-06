# zOS/core/L2_Core/c_zDisplay/zDisplay.py
"""
Display & Rendering Subsystem for zOS
======================================

Facade for all display capabilities including event-driven rendering,
input collection, and multi-mode output (Terminal/Bifrost).

Architecture:
- display_primitives: Low-level I/O
- display_events: High-level event packages
- sandbox: Code execution (zTerminal)
- utils: Event buffering, mode detection

Mode Operation:
- zCLI: Direct terminal I/O (print/input)
- zBifrost: WebSocket events via zComm

Event Routing:
All operations route through handle() with event dictionaries.
See display_constants.py for full event list.
"""

from zOS import Any, Dict, Optional, Callable
from zSys.formatting.colors import Colors
from ...L1_Foundation.a_zConfig.zConfig_modules import SESSION_KEY_ZMODE  # pylint: disable=relative-beyond-top-level
from zSys.Utils import validate_zos_instance
from .zDisplay_modules.io.display_primitives import zPrimitives
from .zDisplay_modules.display_events import zEvents
from .zDisplay_modules.display_delegates import zDisplayDelegates
from .zDisplay_modules.sandbox import TerminalExecutor
from .zDisplay_modules.utils.event_buffer import EventBuffer
from .zDisplay_modules.display_routing import build_event_map
from .zDisplay_modules.display_constants import (
    SUBSYSTEM_NAME,
    READY_MESSAGE,
    DEFAULT_COLOR,
    DEFAULT_MODE,
    MODE_BIFROST,
    MODE_ZCLI,
    MODE_WALKER,
    MODE_EMPTY,
    _EVENT_TEXT,
    _EVENT_RICH_TEXT,
    _EVENT_HEADER,
    _EVENT_LINE,
    _EVENT_ERROR,
    _EVENT_WARNING,
    _EVENT_SUCCESS,
    _EVENT_INFO,
    _EVENT_ZMARKER,
    _EVENT_LIST,
    _EVENT_DL,
    _EVENT_JSON,
    _EVENT_JSON_DATA,
    _EVENT_ZTABLE,
    _EVENT_IMAGE,
    _EVENT_VIDEO,
    _EVENT_AUDIO,
    _EVENT_PICTURE,
    _EVENT_ZDECLARE,
    _EVENT_ZSESSION,
    _EVENT_ZCONFIG,
    _EVENT_ZCRUMBS,
    _EVENT_ZMENU,
    _EVENT_ZDASH,
    _EVENT_ZDIALOG,
    _EVENT_ZTERMINAL,
    _EVENT_PROGRESS_BAR,
    _EVENT_SPINNER,
    _EVENT_PROGRESS_ITERATOR,
    _EVENT_INDETERMINATE_PROGRESS,
    _EVENT_SELECTION,
    _EVENT_READ_STRING,
    _EVENT_READ_PASSWORD,
    _EVENT_READ_BOOL,
    _EVENT_READ_RANGE,
    _EVENT_BUTTON,
    _EVENT_LINK,
    _EVENT_WRITE_RAW,
    _EVENT_WRITE_LINE,
    _EVENT_WRITE_BLOCK,
    _ERR_INVALID_OBJ,
    _ERR_MISSING_EVENT,
    _ERR_UNKNOWN_EVENT,
    _ERR_INVALID_PARAMS,
    _KEY_EVENT,
)


class zDisplay(zDisplayDelegates):
    """Display and rendering subsystem with unified event routing.
    
    Facade for all display operations, supporting Terminal and Bifrost modes.
    All operations route through unified handle() method with event dictionaries.
    """

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    # Type hints for instance attributes
    zos: Any
    session: Dict[str, Any]
    logger: Any
    mode: str
    _is_bifrost: bool
    zColors: Any
    mycolor: str
    zPrimitives: Any
    zEvents: Any
    _event_map: Dict[str, Callable]
    _terminal_executor: Any
    _event_buffer: Any

    def __init__(self, zos: Any) -> None:
        """Initialize zDisplay subsystem.
        
        Args:
            zos: zOS instance (required, must have session and logger)
        """
        super().__init__()
        
        validate_zos_instance(zos, SUBSYSTEM_NAME)
        
        self.zos = zos
        self.logger = zos.logger
        self.mode = self.session.get(SESSION_KEY_ZMODE, DEFAULT_MODE)
        self._is_bifrost = self.mode not in (MODE_ZCLI, MODE_WALKER, MODE_EMPTY)
        
        self.zColors = Colors
        self.mycolor = DEFAULT_COLOR
        
        self.zPrimitives = zPrimitives(self)
        self.zEvents = zEvents(self)
        
        # Initialize extracted modules
        self._terminal_executor = TerminalExecutor(self)
        self._event_buffer = EventBuffer()
        
        # Build event routing map (SSOT)
        self._event_map = build_event_map(self.zEvents, self.zPrimitives, self._terminal_executor)
        
        # Initialize ready message
        self.handle({
            _KEY_EVENT: _EVENT_ZDECLARE,
            "label": READY_MESSAGE,
            "color": self.mycolor,
            "indent": 0,
            "style": "full",
        })

    @property
    def handler(self) -> Callable:
        """Return handler function for external routing."""
        return self.handle

    def handle(self, display_obj: Dict[str, Any]) -> Any:
        """Single event handler for all zDisplay operations.
        
        Args:
            display_obj: Event dictionary with 'event' key and parameters
        
        Returns:
            Result from event handler, or None if error
        """
        if not isinstance(display_obj, dict):
            self.logger.warning(_ERR_INVALID_OBJ, type(display_obj))
            return None

        event = display_obj.get(_KEY_EVENT)
        if not event:
            self.logger.warning(_ERR_MISSING_EVENT)
            return None

        handler = self._event_map.get(event)
        if not handler:
            self.logger.warning(_ERR_UNKNOWN_EVENT, event)
            return None

        params = {
            k: v for k, v in display_obj.items()
            if k != _KEY_EVENT and (not k.startswith('_') or k.startswith('_z') or k == '_context')
        }

        try:
            return handler(**params)
        except TypeError as error:
            self.logger.error(_ERR_INVALID_PARAMS, event, error)
            return None
    """Display and rendering subsystem with unified event routing.
    
    Facade for all display operations, supporting Terminal and Bifrost modes.
    """

    # Type hints
    zos: Any
    session: Dict[str, Any]
    logger: Any
    mode: str
    _is_bifrost: bool
    zColors: Any
    mycolor: str
    zPrimitives: Any
    zEvents: Any
    _event_map: Dict[str, Callable]
    _terminal_executor: Any
    _event_buffer: Any

    def __init__(self, zos: Any) -> None:
        """Initialize zDisplay subsystem.
        
        Args:
            zos: zOS instance (required, must have session and logger)
        """
        super().__init__()
        
        validate_zos_instance(zos, SUBSYSTEM_NAME)
        
        self.zos = zos
        self.logger = zos.logger
        self.mode = self.session.get(SESSION_KEY_ZMODE, DEFAULT_MODE)
        self._is_bifrost = self.mode not in (MODE_ZCLI, MODE_WALKER, MODE_EMPTY)
        
        self.zColors = Colors
        self.mycolor = DEFAULT_COLOR
        
        self.zPrimitives = zPrimitives(self)
        self.zEvents = zEvents(self)
        
        # Initialize extracted modules
        self._terminal_executor = TerminalExecutor(self)
        self._event_buffer = EventBuffer()
        
        # Build event routing map (SSOT)
        self._event_map = build_event_map(self.zEvents, self.zPrimitives, self._terminal_executor)
        
        # Initialize ready message using modern handler
        self.handle({
            _KEY_EVENT: _EVENT_ZDECLARE,
            "label": READY_MESSAGE,
            "color": self.mycolor,
            "indent": 0,
            "style": "full",
        })

    @property
    def handler(self) -> Callable:
        """Return handler function for external routing (alias for handle)."""
        return self.handle

    def handle(self, display_obj: Dict[str, Any]) -> Any:
        """Single event handler for all zDisplay operations.
        
        Args:
            display_obj: Event dictionary with 'event' key and parameters
        
        Returns:
            Result from event handler, or None if error
        """
        if not isinstance(display_obj, dict):
            self.logger.warning(_ERR_INVALID_OBJ, type(display_obj))
            return None

        event = display_obj.get(_KEY_EVENT)
        if not event:
            self.logger.warning(_ERR_MISSING_EVENT)
            return None

        handler = self._event_map.get(event)
        if not handler:
            self.logger.warning(_ERR_UNKNOWN_EVENT, event)
            return None

        params = {
            k: v for k, v in display_obj.items()
            if k != _KEY_EVENT and (not k.startswith('_') or k.startswith('_z') or k == '_context')
        }

        try:
            return handler(**params)
        except TypeError as error:
            self.logger.error(_ERR_INVALID_PARAMS, event, error)
            return None

    def buffer_event(self, event_data: Dict[str, Any]) -> None:
        """Buffer a display event for zBifrost mode.
        
        Args:
            event_data: Event dictionary to buffer
        """
        self._event_buffer.buffer_event(event_data)

    def collect_buffered_events(self) -> list:
        """Collect all buffered events and clear the buffer.
        
        Returns:
            List of all buffered events since last collection
        """
        return self._event_buffer.collect_buffered_events()

    def clear_event_buffer(self) -> None:
        """Clear the event buffer without returning events."""
        self._event_buffer.clear_event_buffer()

    # ═══════════════════════════════════════════════════════════════════════════
    # Convenience Method Delegates (Backward Compatibility)
    # ═══════════════════════════════════════════════════════════════════════════

    def progress_bar(
        self,
        current: int,
        total: Optional[int] = None,
        label: str = "Processing",
        **kwargs: Any
    ) -> Any:
        """Convenience method: Display a progress bar.
        
        Args:
            current: Current progress value
            total: Total value (None for indeterminate)
            label: Progress bar label
            **kwargs: Additional parameters (color, width, etc.)
            
        Returns:
            Any: Result from progress_bar handler
        """
        return self.zEvents.progress_bar(current, total, label, **kwargs)

    def spinner(self, label: str = "Loading", style: str = "dots") -> Any:
        """Convenience method: Loading spinner context manager.
        
        Args:
            label: Spinner label
            style: Spinner style (dots, arc, line)
            
        Returns:
            Any: Context manager for spinner
        """
        return self.zEvents.spinner(label, style)

    def progress_iterator(
        self,
        iterable: Any,
        label: str = "Processing",
        **kwargs: Any
    ) -> Any:
        """Convenience method: Wrap iterable with progress bar.
        
        Args:
            iterable: Iterable to wrap
            label: Progress bar label
            **kwargs: Additional parameters
            
        Returns:
            Any: Iterator with progress bar
        """
        return self.zEvents.progress_iterator(iterable, label, **kwargs)

    def indeterminate_progress(self, label: str = "Processing") -> Any:
        """Convenience method: Indeterminate progress indicator.
        
        Args:
            label: Progress indicator label
            
        Returns:
            Any: Context manager for indeterminate progress
        """
        return self.zEvents.indeterminate_progress(label)

    def button(
        self,
        label: str,
        action: Optional[str] = None,
        color: str = "primary"
    ) -> bool:
        """Convenience method: Display a button that requires confirmation.
        
        Terminal-First Design:
        - Terminal: Colored prompt based on semantic button color
        - Bifrost: Styled button with same semantic color
        
        Args:
            label: Button label text (e.g., "Submit", "Delete", "Save")
            action: Optional action identifier or zVar name
            color: Button semantic color (primary, success, danger, warning, info, secondary)
            
        Returns:
            bool: True if clicked (y), False if cancelled (n)
        """
        return self.zEvents.button(label, action, color)

    def link(
        self,
        label: str,
        href: str,
        target: str = "_self",
        **kwargs
    ) -> Optional[Any]:
        """Convenience method: Display a semantic link with mode-aware rendering.
        
        Terminal-First Design:
        - Terminal: Auto-navigate for internal links, prompt for external links
        - Bifrost: Semantic <a> tag with proper target and security attributes
        
        Supports:
        - Internal navigation (delta $, zPath @)
        - External URLs (http/https) with target control
        - Anchor links (#section) with smooth scroll
        - Placeholder links (#) for styled text
        - Window features for custom popup windows
        
        Args:
            label: Link text to display
            href: Link destination (internal $/@, external http/https, anchor #, placeholder #)
            target: Target behavior (_self, _blank, _parent, _top)
            **kwargs: Additional parameters:
                - color: Link color theme
                - rel: Link relationship (auto-added for _blank external)
                - window: Dict with width, height, features for window.open()
                - _zClass: CSS classes for styling (e.g., "zBtn zBtn-primary")
            
        Returns:
            Navigation result (for internal links) or None
            
        Examples:
            # Internal navigation
            zos.display.link("About", "$zAbout")
            
            # External link (new tab)
            zos.display.link("GitHub", "https://github.com", target="_blank")
            
            # Styled as button
            zos.display.link("Docs", "https://docs.site.com", 
                             _zClass="zBtn zBtn-primary")
            
            # Placeholder for mock/design
            zos.display.link("Coming Soon", "#", _zClass="zBtn zBtn-secondary")
        """
        return self.zEvents.link(label, href, target, **kwargs)
