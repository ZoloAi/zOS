# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/delegates/delegate_widgets_media.py

"""
Widget & Media Convenience Delegates
=====================================

Extracted from display_events.py to reduce file size and improve maintainability.
Contains convenience delegate methods for widgets, media, and system events.

Methods:
- selection(): User selection prompt
- button(): Button with confirmation
- link(): Semantic link rendering
- zTable(): Data table display
- zDeclare(): System declaration
- zSession(): Session information display
- zConfig(): Configuration display
- zCrumbs(): Breadcrumb navigation
- zMenu(): Interactive menu
- zDash(): Dashboard with panels
- zDialog(): Interactive dialog
- progress_bar(): Progress bar widget
- spinner(): Loading spinner
- progress_iterator(): Iterable with progress
- indeterminate_progress(): Indeterminate progress
- swiper(): Content carousel
- image(): Image display
- video(): Video display
- audio(): Audio display
- picture(): Responsive image
"""

from zOS import Any, Optional, List, Dict, Union


class WidgetMediaDelegates:
    """Mixin providing convenience delegates for widgets, media, and system events.
    
    This class is designed to be mixed into zEvents via multiple inheritance.
    It provides backward-compatible convenience methods that delegate to
    the appropriate event packages.
    
    Required Attributes (provided by zEvents):
        - InteractiveInputs: InteractiveInputs package instance
        - LinkEvents: LinkEvents package instance
        - AdvancedData: AdvancedData package instance
        - zSystem: zSystem package instance
        - TimeBased: TimeBased package instance
        - MediaEvents: MediaEvents package instance
    """

    def selection(
        self, prompt: str, options: List[Any], multi: bool = False,
        default: Optional[Any] = None, style: str = "numbered",
        action_type: Optional[str] = None, widget_type: Optional[str] = None
    ) -> Any:
        """Prompt user for selection from options.
        
        Args:
            prompt: Selection prompt text
            options: List of options to choose from
            multi: Allow multiple selections (default: False)
            default: Default selection value
            style: Display style (default: numbered)
            action_type: Action to perform after selection
            widget_type: Rendering hint for Bifrost
            
        Returns:
            Selected option(s) from InteractiveInputs.selection method
        """
        return self.InteractiveInputs.selection(prompt, options, multi, default, style, action_type, widget_type)

    def button(self, label: Optional[str] = None, action: Optional[str] = None, color: str = "primary", **kwargs) -> bool:
        """Display a button that requires confirmation to execute.
        
        Args:
            label: Icon-aware button label — ``bi-*`` tokens render as icons,
                everything else is literal text (see InteractiveInputs.button).
            action: Optional action identifier
            color: Button semantic color
            **kwargs: Additional parameters
            
        Returns:
            bool: True if clicked, False if cancelled
        """
        return self.InteractiveInputs.button(label, action, color, **kwargs)

    def link(self, label: str, href: str, target: str = "_self", **kwargs) -> Optional[Any]:
        """Display a semantic link with mode-aware rendering.
        
        Args:
            label: Link text to display
            href: Link destination
            target: Target behavior (_self, _blank, etc.)
            **kwargs: Additional parameters
            
        Returns:
            Navigation result or None
        """
        link_data = {
            'label': label,
            'href': href,
            'target': target,
            **kwargs
        }
        return self.LinkEvents.handle_link(link_data)

    def zTable(
        self, title: Optional[str] = None, columns: Optional[List[str]] = None, rows: Optional[List[Any]] = None,
        limit: Optional[int] = None, offset: int = 0, show_header: bool = True,
        zPages: bool = False, caption: Optional[str] = None,
        truncate: Union[bool, int] = False, _zColumn: Optional[Any] = None,
        **passthrough: Any,
    ) -> Any:
        """Display data in table format with pagination support.

        Pure display primitive — renders whatever columns/rows are passed in.
        Data fetching is the responsibility of the caller (e.g. zData: read).

        Args:
            title: Table title
            columns: Column header names
            rows: Table row data
            limit: Maximum rows to display
            offset: Row offset for pagination
            show_header: Show column headers (default: True)
            zPages: Enable paginated navigation controls
            caption: Optional table caption
            truncate: Column width control (zCLI only) —
                False (default): content-fit; int (e.g. 20): fixed-width clip
            _zColumn: Per-column style overrides

        Returns:
            Result from AdvancedData.zTable method
        """
        return self.AdvancedData.zTable(
            title, columns, rows, limit, offset, show_header, zPages, caption, truncate,
            _zColumn=_zColumn, **passthrough,
        )

    def zDeclare(self, label: str, color: Optional[str] = None, indent: int = 0, style: Optional[str] = None) -> Any:
        """Display system declaration message.
        
        Args:
            label: Declaration text
            color: Optional color override
            indent: Indentation level (default: 0)
            style: Optional style override
            
        Returns:
            Result from zSystem.zDeclare method
        """
        return self.zSystem.zDeclare(label, color, indent, style)

    def zSession(
        self, session_data: Dict[str, Any], break_after: bool = True,
        break_message: Optional[str] = None
    ) -> Any:
        """Display session information.
        
        Args:
            session_data: Session dictionary to display
            break_after: Add line break after (default: True)
            break_message: Optional break message
            
        Returns:
            Result from zSystem.zSession method
        """
        return self.zSystem.zSession(session_data, break_after, break_message)

    def zConfig(
        self, config_data: Optional[Dict[str, Any]] = None,
        break_after: bool = True, break_message: Optional[str] = None
    ) -> Any:
        """Display configuration information.
        
        Args:
            config_data: Config dictionary
            break_after: Add line break after (default: True)
            break_message: Optional break message
            
        Returns:
            Result from zSystem.zConfig method
        """
        return self.zSystem.zConfig(config_data, break_after, break_message)

    def zCrumbs(
        self, session_data: Optional[Dict[str, Any]] = None,
        parent: Optional[str] = None, show: str = 'session', header: Optional[str] = None,
        trail: Optional[list] = None, zMenu: bool = False,
        crumbs: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Display breadcrumb navigation from session.
        
        Args:
            session_data: Session dictionary
            parent: Declarative parent path
            show: Display mode - 'session', 'manual', or 'structure' (auto, or declarative via parent)
            header: Override display header label
            trail: Explicit label list for show='manual'
            crumbs: Bifrost-only live-trail snapshot the expander attaches to the
                show:session chunk. zCLI ignores it (reads the trail from session),
                but it must be accepted so handle(**params) doesn't raise.
            
        Returns:
            Result from zSystem.zCrumbs method
        """
        return self.zSystem.zCrumbs(
            session_data, parent=parent, show=show, header=header,
            trail=trail, zMenu=zMenu, crumbs=crumbs
        )

    def zMenu(self, options: List[Any], title: Any = None, allow_back: bool = False) -> Any:
        """Display a menu and return the selected option key.

        Args:
            options: Ordered list of option display labels
            title: Optional menu header text
            allow_back: If True, a Back entry is appended

        Returns:
            Result from zSystem.zMenu method
        """
        return self.zSystem.zMenu(options, title, allow_back)

    def zDash(
        self, folder: str, sidebar: List[str], default: Optional[str] = None,
        _zos: Optional[Any] = None, **kwargs
    ) -> Any:
        """Display dashboard with panel navigation.
        
        Args:
            folder: Base folder for panel discovery
            sidebar: List of panel names
            default: Default panel to navigate to
            _zos: zOS instance for context
            **kwargs: Additional parameters
            
        Returns:
            Result from zSystem.zDash method
        """
        return self.zSystem.zDash(folder, sidebar, default, _zos, **kwargs)

    def zDialog(self, context: str, zcli: Optional[Any] = None, walker: Optional[Any] = None) -> Any:
        """Display interactive dialog system.
        
        Args:
            context: Dialog context/configuration
            zcli: Optional zCLI instance (renamed from `zos` to match facade contract)
            walker: Optional walker instance
            
        Returns:
            Result from zSystem.zDialog method
        """
        return self.zSystem.zDialog(context, zcli, walker)

    def progress_bar(
        self, current: int = 0, total: Optional[int] = None,
        label: str = "Processing", **kwargs: Any
    ) -> Any:
        """Display progress bar with current/total status.

        Args:
            current: Current progress value (default 0 so a declarative
                `zProgress:` with only a label renders an indeterminate spinner
                instead of erroring on a missing positional — mirrors Bifrost)
            total: Total progress value (None → indeterminate spinner)
            label: Progress label text
            **kwargs: Additional options
            
        Returns:
            Result from TimeBased.progress_bar method
        """
        return self.TimeBased.progress_bar(current, total, label, **kwargs)

    def spinner(self, label: str = "Loading", style: str = "dots") -> Any:
        """Display animated spinner for loading indication.
        
        Args:
            label: Spinner label text
            style: Spinner animation style
            
        Returns:
            Result from TimeBased.spinner method
        """
        return self.TimeBased.spinner(label, style)

    def progress_iterator(self, iterable: Any, label: str = "Processing", **kwargs: Any) -> Any:
        """Iterate with progress indication.
        
        Args:
            iterable: Iterable to process
            label: Progress label text
            **kwargs: Additional options
            
        Returns:
            Result from TimeBased.progress_iterator method
        """
        return self.TimeBased.progress_iterator(iterable, label, **kwargs)

    def indeterminate_progress(self, label: str = "Processing") -> Any:
        """Display indeterminate progress indicator.
        
        Args:
            label: Progress label text
            
        Returns:
            Result from TimeBased.indeterminate_progress method
        """
        return self.TimeBased.indeterminate_progress(label)

    def swiper(
        self, slides: List[str], label: str = "Slides", auto_advance: bool = True,
        delay: int = 3, loop: bool = False, **_kwargs
    ) -> Any:
        """Display interactive content carousel/swiper.
        
        Args:
            slides: List of slide content strings
            label: Title for the swiper
            auto_advance: Auto-cycle through slides
            delay: Seconds between auto-advance
            loop: Wrap around to start after last slide
            **_kwargs: Tolerated extras from declarative routing (e.g. _zClass);
                folder/zLoom slide sources are handled in later tiers.
            
        Returns:
            Result from TimeBased.swiper method
        """
        def _as_bool(v: Any) -> bool:
            if isinstance(v, str):
                return v.strip().lower() in ("true", "yes", "1", "on")
            return bool(v)

        def _as_int(v: Any, default: int) -> int:
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        return self.TimeBased.swiper(
            slides, label, _as_bool(auto_advance), _as_int(delay, 3), _as_bool(loop),
            folder=_kwargs.get("folder")
        )

    def image(
        self,
        src: str,
        alt_text: str = "",
        caption: str = "",
        open_prompt: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Display an image event.
        
        Args:
            src: Image source URL or path
            alt_text: Alternative text (accessibility)
            caption: Optional caption
            open_prompt: Display button in terminal mode
            indent: Indentation level
            color: Color for terminal output
            **kwargs: Additional parameters
            
        Returns:
            Result from MediaEvents.image method
        """
        return self.MediaEvents.image(src, alt_text, caption, open_prompt, indent, color, **kwargs)

    def video(
        self,
        src: str,
        alt_text: str = "",
        caption: str = "",
        open_prompt: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Display a video event.
        
        Args:
            src: Video source URL or path
            alt_text: Alternative text (accessibility)
            caption: Optional caption
            open_prompt: Display button in terminal mode
            indent: Indentation level
            color: Color for terminal output
            **kwargs: Additional parameters
            
        Returns:
            Result from MediaEvents.video method
        """
        return self.MediaEvents.video(src, alt_text, caption, open_prompt, indent, color, **kwargs)

    def audio(
        self,
        src: str,
        alt_text: str = "",
        caption: str = "",
        open_prompt: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Display an audio event.
        
        Args:
            src: Audio source URL or path
            alt_text: Alternative text (accessibility)
            caption: Optional caption
            open_prompt: Display button in terminal mode
            indent: Indentation level
            color: Color for terminal output
            **kwargs: Additional parameters
            
        Returns:
            Result from MediaEvents.audio method
        """
        return self.MediaEvents.audio(src, alt_text, caption, open_prompt, indent, color, **kwargs)

    def embed(
        self,
        src: str,
        alt_text: str = "",
        caption: str = "",
        open_prompt: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Display an embed event (external URL-type content).

        Args:
            src: Embed source URL (http/https)
            alt_text: Alternative text (accessibility)
            caption: Optional caption
            open_prompt: Show open-in-browser gate in terminal mode
            indent: Indentation level
            color: Color for terminal output
            **kwargs: Additional parameters

        Returns:
            Result from MediaEvents.embed method
        """
        return self.MediaEvents.embed(src, alt_text, caption, open_prompt, indent, color, **kwargs)

    def picture(
        self,
        sources: List[Dict[str, str]],
        fallback: str,
        alt_text: str = "",
        caption: str = "",
        open_prompt: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Display a picture element (responsive image).
        
        Args:
            sources: List of source dicts with 'srcset' and 'media' keys
            fallback: Fallback image path
            alt_text: Alternative text (accessibility)
            caption: Optional caption
            open_prompt: Display selection in terminal mode
            indent: Indentation level
            color: Color for terminal output
            **kwargs: Additional parameters
            
        Returns:
            Result from MediaEvents.picture method
        """
        return self.MediaEvents.picture(sources, fallback, alt_text, caption, open_prompt, indent, color, **kwargs)

    def icon(
        self,
        name: str,
        color: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        Display Bootstrap Icon (mode-aware rendering).
        
        Renders appropriately based on mode:
        - zBifrost (web): HTML <i> tag with Bootstrap Icons classes
        - zCLI (terminal): Emoji fallback or Unicode character
        
        Args:
            name: Icon name (with or without 'bi-' prefix)
            color: Color class (Bifrost only)
            **kwargs: Additional parameters (sizing via _zClass)
            
        Returns:
            Result from MediaEvents.icon method
        """
        return self.MediaEvents.icon(name, color, **kwargs)
