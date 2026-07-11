# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/f_orchestration/system_event_dashboard.py

"""
System Dashboard Events - zDash
================================

This module provides interactive dashboard display with sidebar navigation,
panel rendering, and RBAC-filtered content. zDash orchestrates the complete
dashboard workflow including panel discovery, metadata loading, and navigation.

Purpose:
    - Display dashboards with sidebar navigation
    - Load and render dashboard panels dynamically
    - Filter panels based on RBAC permissions
    - Handle interactive panel switching (Terminal)
    - Support both Terminal (interactive loop) and Bifrost (WebSocket) modes

Public Methods:
    zDash(folder, sidebar, default, _zcli, **kwargs)
        Display dashboard with interactive panel navigation

Private Helpers:
    _filter_accessible_panels(sidebar, folder, _zcli, logger)
        Filter sidebar panels based on RBAC access
        
    _build_panel_metadata(panel_name, panel_file, folder, logger)
        Extract metadata from panel file
        
    _send_zdash_bifrost_event(folder, accessible_panels, panel_metadata, default)
        Send zDash event to Bifrost frontend
        
    _run_zdash_terminal_loop(folder, accessible_panels, panel_metadata, default, _zcli, logger)
        Run interactive dashboard loop in zCLI mode
        
    _render_zdash_panel(panel_name, folder, _zcli, logger)
        Render a single dashboard panel
        
    _show_zdash_menu(accessible_panels, panel_metadata, current_panel)
        Display dashboard menu with panel options

Dependencies:
    - display_constants: _EVENT_*, _KEY_*, _MSG_*
    - display_event_helpers: try_gui_event
    - display_logging_helpers: get_display_logger
    - display_rendering_utilities: output_text_via_basics
    - zWizard.wizardzRBAC: checkzRBAC_access (for panel filtering)

Extracted From:
    display_event_system.py (lines 1243-1611)
"""

from zOS import Any, Optional, Dict, List

# Import Tier 0 infrastructure utilities (none needed - uses primitives/basic directly)

# Import constants
from ..display_constants import (  # pylint: disable=relative-beyond-top-level
    _EVENT_ZDASH,
    _KEY_FOLDER,
    _KEY_SIDEBAR,
    _KEY_DEFAULT,
    _KEY_PANELS,
    _MSG_DASHBOARD_MENU_PROMPT,
    _MSG_INVALID_PANEL_CHOICE,
    _MSG_INVALID_INPUT_FORMAT,
    _FORMAT_MENU_ITEM
)


class _DisplayHandleProxy:
    """Thin proxy so DashboardEvents.BasicOutputs always has text()/error()/warning() even when
    the real BasicOutputs package is not wired (e.g. standalone display init)."""

    def __init__(self, display: Any) -> None:
        self._display = display

    def text(self, content: str, indent: int = 0, break_after: bool = True) -> None:
        self._display.handle({"event": "text", "content": content, "indent": indent})

    def error(self, content: str, indent: int = 0, **_kw) -> None:
        self._display.handle({"event": "error", "content": content, "indent": indent})

    def warning(self, content: str, indent: int = 0, **_kw) -> None:
        self._display.handle({"event": "warning", "content": content, "indent": indent})


class DashboardEvents:
    """
    Interactive dashboard with sidebar navigation and RBAC filtering.
    
    Provides zDash event for displaying multi-panel dashboards with
    built-in navigation in zCLI mode and WebSocket-based navigation
    in Bifrost mode.
    
    Composition:
        - NavigationEvents: For menu display (set after zSystem init)
        - zNav: For panel navigation (from zos)
        - zLoader: For panel file loading (from zos)
    
    Usage:
        # Via zSystem coordinator
        display.zEvents.zSystem.zDash(
            folder="@.UI.zAccount",
            sidebar=["Overview", "Apps", "Settings"],
            default="Overview",
            _zos=zos
        )
    """

    # Class-level type declarations
    display: Any                     # Parent zDisplay instance
    BasicOutputs: Optional[Any]      # BasicOutputs for text rendering
    NavigationEvents: Optional[Any]  # NavigationEvents (for menu display)

    def __init__(self, display_instance: Any) -> None:
        """
        Initialize DashboardEvents with reference to parent zDisplay instance.
        
        Args:
            display_instance: Parent zDisplay instance
        
        Returns:
            None
        
        Notes:
            - NavigationEvents is set to None initially
            - Will be populated by zSystem after all event packages instantiated
        """
        self.display = display_instance
        _bo = (
            getattr(display_instance.zEvents, 'BasicOutputs', None)
            if hasattr(display_instance, 'zEvents') else None
        )
        # Fall back to a thin proxy so _show_zdash_menu always has .text()
        if _bo is None:
            _bo = _DisplayHandleProxy(display_instance)
        self.BasicOutputs = _bo
        self.NavigationEvents = None  # Will be set after zSystem initialization

    def _get_logger(self) -> Optional[Any]:
        """Get logger instance from display hierarchy."""
        if not self.display:
            return None
        if hasattr(self.display, 'zos') and hasattr(self.display.zos, 'logger'):
            return self.display.zos.logger
        if hasattr(self.display, 'logger'):
            return self.display.logger
        return None

    def zDash(
        self,
        folder: str,
        sidebar: List[str],
        default: Optional[str] = None,
        _zcli: Optional[Any] = None,
        _zos: Optional[Any] = None,
        **_kwargs
    ) -> Optional[str]:
        """
        Display dashboard with interactive panel navigation (Terminal or Bifrost mode).
        
        Built-in Gate Behavior (Terminal):
        - Runs in interactive loop until user enters "done"
        - Allows panel switching between sidebar items
        - Acts as built-in gate (no need for ! modifier)
        
        Args:
            folder: Base folder for panel discovery (e.g., "@.UI.zAccount")
            sidebar: List of panel names (e.g., ["Overview", "Apps", "Settings"])
            default: Default panel to navigate to (defaults to first in sidebar)
            _zcli: zCLI instance for zLoader access
            **kwargs: Additional parameters (e.g., _context for extended metadata)
        
        Returns:
            Optional[str]: Last panel viewed (Terminal), None (Bifrost)
        
        Bifrost Mode:
            - Sends _EVENT_ZDASH event with dashboard structure
            - Frontend renders sidebar and content panels
            - Returns None (navigation handled via WebSocket)
        
        zCLI Mode:
            - Discovers panel metadata from folder
            - Auto-navigates to default panel immediately
            - Shows menu after panel content
            - Loops until "done" entered
            - Panel content rendered by zDispatch
        
        Usage:
            display.zEvents.zSystem.zDash(
                folder="@.UI.zAccount",
                sidebar=["Overview", "Apps", "Settings"]
            )
        """
        # Validate sidebar
        if not sidebar:
            logger = self._get_logger()
            if logger:
                logger.warning("[zDash] No sidebar items provided")
            return None

        # Get zOS / zCLI instances — both are the same object; derive from display if not passed
        if not _zos:
            _zos = getattr(self.display, 'zos', None)
        if not _zcli:
            _zcli = _zos

        logger = self._get_logger()

        # Filter panels based on RBAC access and collect metadata
        accessible_panels, panel_metadata = self._filter_accessible_panels(
            sidebar, folder, _zcli, _zos, logger
        )

        if not accessible_panels:
            if logger:
                logger.warning("[zDash] No accessible panels after RBAC filtering")
            if self.display.Signals:
                self.display.BasicOutputs.warning("No dashboard panels available", indent=0)
            return None

        # Set default panel (first accessible if not specified)
        if not default or default not in accessible_panels:
            default = accessible_panels[0]

        # Try Bifrost (GUI) mode first
        if self._send_zdash_bifrost_event(folder, accessible_panels, panel_metadata, default):
            return None

        # zCLI mode - run interactive dashboard loop
        return self._run_zdash_terminal_loop(
            folder, accessible_panels, panel_metadata, default, _zcli, logger
        )

    # ZDASH HELPER METHODS (Private)

    @staticmethod
    def _check_panel_rbac(panel_block: Any, _zos: Optional[Any]) -> bool:
        """
        Panel-visibility gate for a panel's root-level zGate guard.

        DUMB CALLER: hands the panel block to ``zos.zgate.check`` — the ONE
        facade that extracts the authored gate (`zGate:`, or a legacy
        `zRBAC:` block auto-lowered) and evaluates it through the SAME engine
        every page/route/action_row gate uses (15_rbac.md "verb"). Enforced
        per panel during _filter_accessible_panels so a guard like::
            Overview:
                zGate:
                    role: [admin]
        is applied before the panel reaches the sidebar list.

        Fails open on errors so a broken auth stack never locks out all panels.
        """
        if not isinstance(panel_block, dict):
            return True
        try:
            zgate = getattr(_zos, "zgate", None) if _zos else None
            if zgate is None:
                return True  # no gate engine → fail open
            granted, _reason = zgate.check(panel_block)
            return bool(granted)
        except Exception:  # pylint: disable=broad-except
            return True  # fail open — never block on unexpected errors

    def _filter_accessible_panels(
        self,
        sidebar: List[str],
        folder: str,
        _zcli: Any,
        _zos: Optional[Any],
        logger: Optional[Any]
    ) -> tuple:
        """
        Filter sidebar panels based on RBAC access and collect metadata.

        RBAC sidebar filtering is applied **only in Bifrost (GUI) mode**.
        In CLI (terminal) mode all panels remain visible; RBAC is still enforced
        per-action inside each panel via dispatch_launcher._check_zrbac().

        Returns:
            tuple: (accessible_panels: List[str], panel_metadata: Dict[str, Dict])
        """
        # Detect Bifrost mode via the display primitive's _is_bifrost flag.
        _in_bifrost = bool(
            hasattr(self.display, 'zPrimitives') and
            getattr(self.display.zPrimitives, '_is_bifrost', False)
        )

        accessible_panels = []
        panel_metadata = {}

        for panel_name in sidebar:
            try:
                zLink_path = f"{folder}.zUI.{panel_name}"
                panel_file = _zcli.loader.handle(zPath=zLink_path) if hasattr(_zcli, 'loader') else {}

                # Get the panel's main block
                panel_block = panel_file.get(panel_name, {})

                # Enforce root-level zRBAC only in Bifrost mode
                if _in_bifrost and not self._check_panel_rbac(panel_block, _zos):
                    if logger:
                        logger.debug(f"[zDash] Panel '{panel_name}' filtered out by RBAC (Bifrost)")
                    continue

                accessible_panels.append(panel_name)
                panel_metadata[panel_name] = self._build_panel_metadata(
                    panel_name, panel_file, folder, logger
                )

            except Exception as e:  # pylint: disable=broad-except
                if logger:
                    logger.error(f"[zDash] Error loading panel '{panel_name}': {e}")

        return accessible_panels, panel_metadata

    def _build_panel_metadata(
        self,
        panel_name: str,
        panel_file: Dict[str, Any],
        folder: str,
        logger: Optional[Any]
    ) -> Dict[str, Any]:
        """
        Extract metadata from panel file for dashboard display.
        
        Returns:
            Dict[str, Any]: Panel metadata {title, icon, description, ...}
        """
        panel_block = panel_file.get(panel_name, {})

        # Extract zMeta if present
        zmeta = panel_block.get('zMeta', {})

        # Icon SSOT: a Bootstrap `bi-*` name (same vocabulary as zIcon / zMenu).
        # IconMapper renders it per mode — `<i class="bi bi-*">` on Bifrost, a
        # bracketed [name] in the terminal — so authors write ONE canonical value.
        metadata = {
            'title': zmeta.get('title', panel_name),
            'icon': zmeta.get('icon', 'bi-window'),
            'description': zmeta.get('description', ''),
            'zLink': f"{folder}.zUI.{panel_name}"
        }

        if logger:
            logger.debug(f"[zDash] Panel metadata for '{panel_name}': {metadata}")

        return metadata

    def _send_zdash_bifrost_event(
        self,
        folder: str,
        accessible_panels: List[str],
        panel_metadata: Dict[str, Dict],
        default: str
    ) -> bool:
        """
        Send zDash event to Bifrost frontend.
        
        Returns:
            bool: True if GUI event sent successfully
        """
        return self.display.zPrimitives.try_gui_event(_EVENT_ZDASH, {
            _KEY_FOLDER: folder,
            _KEY_SIDEBAR: accessible_panels,
            _KEY_PANELS: panel_metadata,
            _KEY_DEFAULT: default
        })

    def _run_zdash_terminal_loop(
        self,
        folder: str,
        accessible_panels: List[str],
        panel_metadata: Dict[str, Dict],
        default: str,
        _zcli: Any,
        logger: Optional[Any]
    ) -> str:
        """
        Run interactive dashboard loop in zCLI mode.
        
        Returns:
            str: Last panel viewed
        """
        current_panel = default

        # Log dashboard start
        if logger:
            logger.info(f"[zDash] Starting Terminal dashboard - folder: {folder}")
            logger.info(f"[zDash] Accessible panels: {accessible_panels}")
            logger.info(f"[zDash] Default panel: {default}")

        # Auto-navigate to default panel on first load
        self._render_zdash_panel(current_panel, folder, _zcli, logger)

        # Interactive loop: show menu and navigate until "done"
        while True:
            # Show menu
            self._show_zdash_menu(accessible_panels, panel_metadata, current_panel)

            # Get user choice
            user_input = self.display.zPrimitives.read_string("\n> ").strip().lower()

            # Handle "done" command
            if user_input == "done":
                if logger:
                    logger.info("[zDash] User entered 'done' - exiting dashboard")
                break

            # Handle numeric choice
            try:
                choice_num = int(user_input)

                # Validate choice
                if 1 <= choice_num <= len(accessible_panels):
                    new_panel = accessible_panels[choice_num - 1]

                    if logger:
                        logger.info(f"[zDash] User selected panel {choice_num}: {new_panel}")

                    # Navigate to new panel
                    current_panel = new_panel
                    self._render_zdash_panel(current_panel, folder, _zcli, logger)
                else:
                    if logger:
                        logger.warning(f"[zDash] Invalid menu choice: {choice_num}")
                    self.BasicOutputs.text(
                        _MSG_INVALID_PANEL_CHOICE.format(max=len(accessible_panels)),
                        indent=0,
                        break_after=False
                    )

            except ValueError:
                if logger:
                    logger.warning(f"[zDash] Invalid input (not a number or 'done'): {user_input}")
                self.BasicOutputs.text(
                    _MSG_INVALID_INPUT_FORMAT.format(max=len(accessible_panels)),
                    indent=0,
                    break_after=False
                )

        # Dashboard loop complete
        if logger:
            logger.info("[zDash] Dashboard gate satisfied, continuing execution")

        return current_panel

    def _render_zdash_panel(
        self,
        panel_name: str,
        folder: str,
        _zcli: Any,
        logger: Optional[Any]
    ) -> None:
        """Render a single dashboard panel via loader + dispatch."""
        zLink_path = f"{folder}.zUI.{panel_name}"

        if logger:
            logger.info(f"[zDash] Rendering panel: {panel_name} (path: {zLink_path})")

        try:
            # Load panel file via zLoader
            loader = getattr(_zcli, 'loader', None)
            if not loader:
                if logger:
                    logger.error("[zDash] Cannot render panel - loader not available")
                return

            panel_file = loader.handle(zPath=zLink_path)
            if not panel_file:
                if logger:
                    logger.warning(f"[zDash] Panel file empty or not found: {zLink_path}")
                return

            # Get the panel block by name.
            block_data = panel_file.get(panel_name, panel_file)

            # SSOT data binding for CLI panels: resolve `_data` + `zMeta.zLoom`
            # BEFORE stripping zMeta, and stash into session["_current_block_data"]
            # so %data.* tokens interpolate (mirrors zWizard._bind_block_data for
            # the Bifrost chunked path). Uses the zLoom subsystem (zos.zloom).
            self._bind_panel_data(block_data, _zcli, logger)

            # Strip zMeta and root-level zRBAC before dispatch:
            # - zMeta is document metadata, not rendered content
            # - root-level zRBAC was already evaluated by _filter_accessible_panels
            #   (Bifrost sidebar) or is irrelevant in CLI mode; letting dispatch_launcher
            #   see it would block the entire panel content for unauthenticated sessions.
            if isinstance(block_data, dict):
                block_data = {
                    k: v for k, v in block_data.items()
                    if k not in ('zMeta', 'zRBAC')
                }

            # Stamp the panel's source file so same-file navigation from WITHIN
            # the panel (zDelegate $Block, zDelta) resolves against the panel
            # file — not the dashboard route (session zVaFile stays on the
            # dashboard during zDash). The carrier + its $target both live here.
            session = getattr(_zcli, 'session', None)
            if isinstance(session, dict):
                session['_panel_zVaFile'] = zLink_path

            # Render the block via dispatch
            dispatch = getattr(_zcli, 'dispatch', None)
            if dispatch and hasattr(dispatch, 'launcher'):
                dispatch.launcher.launch(block_data, context=None, walker=None)
            else:
                if logger:
                    logger.error("[zDash] Cannot render panel - dispatch not available")

        except Exception as e:
            if logger:
                logger.error(f"[zDash] Error rendering panel '{panel_name}': {e}")
            self.display.BasicOutputs.error(f"Error loading panel: {panel_name}", indent=0)

    def _bind_panel_data(
        self,
        block_data: Any,
        _zcli: Any,
        logger: Optional[Any]
    ) -> None:
        """Resolve a panel's `zMeta.zSpool` bindings and stash the results into
        session["_current_block_data"] so %data.* tokens interpolate when the
        panel renders in CLI mode.

        TODO(zLoom leak audit): this still hand-rolls build_binding_block ->
        resolve_block_data -> expand_list_bindings -> expand_knots instead of
        calling the SSOT `resolver.prepare_block_render(block_data, block_data)`
        directly. The `expand_knots` gap (page-scoped zKnot values never
        collapsing in a CLI panel) is now closed — see zDemos/zConsole's Status
        panel, the first zDash golden app to exercise it. Still open: this
        MERGES into session["_current_block_data"] where prepare_block_render
        REPLACES it (replace is arguably more correct — a panel should only see
        its own resolved data, not leftovers from a previously-viewed panel).
        Left as-is: no observed golden-app case yet where two panels' spools
        share a field name, so the merge has never mis-rendered in practice.
        Revisit if one does — see zAgents zLoom audit, finding #6.
        """
        try:
            if not isinstance(block_data, dict):
                return
            resolver = getattr(_zcli, 'zloom', None)
            if resolver is None or not resolver.has_bindings(block_data):
                return

            binding = resolver.build_binding_block(block_data)
            resolved = resolver.resolve_block_data(binding, {})
            if not resolved:
                return

            session = getattr(_zcli, 'session', None)
            if isinstance(session, dict):
                existing = session.get('_current_block_data') or {}
                existing.update(resolved)
                session['_current_block_data'] = existing

            # SSOT zList loop expansion at the binding layer: replace any zList
            # directive in this panel with concrete per-row card blocks (%item.*
            # resolved) BEFORE dispatch. Same engine the Bifrost path calls — the
            # loop is resolved once, mode-agnostically, not at render time.
            resolver.expand_list_bindings(block_data, resolved)

            # SSOT knot collapse — mirrors prepare_block_render's ordering (loops
            # first so any loop-scoped %item.* knot is already baked per-row,
            # THEN page-scoped %data.*/%route.*/zVar knots). Without this a
            # page-scope zKnot (e.g. a %data.<spool>.<field> computation) never
            # collapses in a CLI zDash panel — it lands as a raw op dict, which
            # a prose slot can't render as text and silently drops the line
            # (zAgents zLoom audit finding #6 — first exercised by zDemos/zConsole's
            # Status panel).
            expand_knots = getattr(resolver, 'expand_knots', None)
            if expand_knots is not None:
                expand_knots(block_data, {"_resolved_data": resolved})
        except Exception as e:  # pylint: disable=broad-except
            if logger:
                logger.error(f"[zDash] panel data binding failed: {e}")

    def _show_zdash_menu(
        self,
        accessible_panels: List[str],
        panel_metadata: Dict[str, Dict],
        current_panel: str
    ) -> None:
        """Display dashboard menu with panel options."""
        self.BasicOutputs.text("", indent=0, break_after=False)
        self.BasicOutputs.text(_MSG_DASHBOARD_MENU_PROMPT, indent=0, break_after=False)

        # Icon SSOT: render each panel's bi-* name for the terminal via IconMapper
        # (→ bracketed [name]) — the same mapper zIcon/zMenu use, imported lazily
        # (zSys is Layer 0, no top-level zOS import from a display module).
        from zSys.accessibility import get_icon_mapper  # pylint: disable=import-outside-toplevel
        icons = get_icon_mapper()

        for idx, panel_name in enumerate(accessible_panels, 1):
            # Get panel title from metadata
            metadata = panel_metadata.get(panel_name, {})
            title = metadata.get('title', panel_name)
            icon = icons.render_for_mode(metadata.get('icon', 'bi-window'), mode='zCLI')

            # Mark current panel
            indicator = " (current)" if panel_name == current_panel else ""

            # Format menu item
            menu_text = _FORMAT_MENU_ITEM.format(
                index=idx,
                label=f"{icon} {title}{indicator}"
            )
            self.BasicOutputs.text(menu_text, indent=0, break_after=False)

        # Add "done" option
        self.BasicOutputs.text("", indent=0, break_after=False)
        self.BasicOutputs.text("Enter 'done' to exit dashboard", indent=0, break_after=False)
