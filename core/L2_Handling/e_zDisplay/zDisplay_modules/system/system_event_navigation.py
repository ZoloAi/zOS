# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/f_orchestration/system_event_navigation.py

"""
System Navigation Events - zCrumbs, zMenu
==========================================

This module provides navigation UI events for breadcrumb trails and menu display.
These events help users understand their current location in the system and
navigate between options.

Purpose:
    - Display breadcrumb navigation trails (zCrumbs)
    - Display interactive or display-only menus (zMenu)
    - Support both Terminal and Bifrost modes

Public Methods:
    zCrumbs(session_data)
        Display breadcrumb navigation trail showing scope paths
        
    zMenu(menu_items, prompt, return_selection)
        Display menu options and optionally collect user selection

Dependencies:
    - display_constants: SESSION_KEY_*, _EVENT_*, _KEY_*, _FORMAT_*, _MSG_*
    - display_event_helpers: try_gui_event
    - display_rendering_utilities: output_text_via_basics
    - BasicOutputs (via cross-reference): text() for rendering
    - BasicInputs (via cross-reference): selection() for interactive menus

Extracted From:
    display_event_system.py (lines 1084-1241)
"""

from zOS import Any, Optional, Dict, List, Tuple, Union

# Import SESSION_KEY_* constants
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_ZCRUMBS

# Import colors
from zSys.formatting.colors import Colors
# zPath grammar — Layer-0 SSOT for sigil/segment decomposition.
from zSys import zpath

# Import Tier 0 infrastructure utilities (none needed - uses primitives directly)

# Import constants
from ..display_constants import (  # pylint: disable=relative-beyond-top-level
    # Event Names
    _EVENT_ZCRUMBS,
    _EVENT_ZMENU,
    # JSON Keys
    _KEY_CRUMBS,
    _KEY_OPTIONS,
    _KEY_TITLE,
    _KEY_ALLOW_BACK,
    # Messages
    _MSG_ZCRUMBS_HEADER,
    _MSG_DEFAULT_MENU_PROMPT,
    # Format strings
    _FORMAT_BREADCRUMB_SEPARATOR,
    _FORMAT_CRUMB_SCOPE,
    _FORMAT_MENU_ITEM,
    # Styles
    STYLE_NUMBERED
)


def _derive_zpath_labels(paths: List[str]) -> List[str]:
    """
    Derive display labels from a list of zPath strings with minimum-depth uniqueness.

    Starts at depth 1 (the block leaf) and increases ONLY on collision, until all
    labels in the set are unique, or the full path (minus root symbol) is used as
    fallback. Consistent depth across all items for visual alignment. Depth 1 is the
    SSOT leaf rule shared with session crumbs (scope.rsplit('.',1)[-1]); manual just
    adds collision-escalation on top, so both modes read the same clean leaf label.

    Examples:
        [@.UI.zNav.zVaF, @.UI.zDemo.Foo]   → depth 1 → [zVaF, Foo]
        [@.UI.zNav.zVaF, @.UI.zDemo.zVaF]  → depth 1 collides → depth 2 → [zNav.zVaF, zDemo.zVaF]
        [@.UI.zNav.zVaF, @.UI.zNav.Block_A] → depth 1 → [zVaF, Block_A]
    """
    if not paths:
        return []
    # Strip #N visit suffix, split into parts
    stripped = [p.split('#')[0] for p in paths]
    parts_list = [p.split('.') for p in stripped]
    max_depth = max(len(p) for p in parts_list)

    for depth in range(1, max_depth):
        labels = ['.'.join(p[-depth:]) for p in parts_list]
        if len(set(labels)) == len(labels):  # all unique at this depth
            return labels

    # Fallback: full path minus root symbol (@/~)
    return ['.'.join(p[1:]) for p in parts_list]


class NavigationEvents:
    """
    Navigation UI events (breadcrumbs, menus).
    
    Provides zCrumbs and zMenu events for displaying navigation information
    and collecting user choices in both Terminal and Bifrost modes.
    
    Composition:
        - BasicOutputs: For text() rendering (set after zEvents init)
        - InteractiveInputs: For selection() in interactive menus (set after zEvents init)
    
    Usage:
        # Via zSystem coordinator
        zcli.display.zEvents.zSystem.zCrumbs(zcli.session)
        zcli.display.zEvents.zSystem.zMenu(menu_items, return_selection=True)
    """

    # Class-level type declarations
    display: Any          # Parent zDisplay instance
    BasicOutputs: Optional[Any]  # BasicOutputs event package (set after init)
    InteractiveInputs: Optional[Any]   # InteractiveInputs event package (set after init)

    def __init__(self, display_instance: Any) -> None:
        """
        Initialize NavigationEvents with reference to parent zDisplay instance.
        
        Args:
            display_instance: Parent zDisplay instance
        
        Returns:
            None
        
        Notes:
            - BasicOutputs and BasicInputs are set to None initially
            - Will be populated by zSystem after all event packages instantiated
        """
        self.display = display_instance
        self.BasicOutputs = None  # Will be set after zEvents initialization
        self.InteractiveInputs = None   # Will be set after zEvents initialization

    def zCrumbs(
        self, session_data: Optional[Dict[str, Any]] = None, parent: Optional[str] = None,
        show: str = 'session', header: Optional[str] = None,
        trail: Optional[list] = None, zMenu: bool = False,
        crumbs: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Display breadcrumb navigation trail showing scope paths (Terminal or Bifrost mode).
        
        Breadcrumbs show the navigation trail through different scopes (file, vafile, block).
        Uses SESSION_KEY_ZCRUMBS for safe session access.
        
        Args:
            session_data: zCLI session dictionary containing zCrumbs
            parent: Declarative parent path for stateless breadcrumbs (works in both Terminal and Bifrost)
                    Format: "zProducts.zTheme" or "zProducts.zTheme.Containers"
            show: Display mode - 'session' (default), 'manual', or 'structure'
                  (auto-derived from location, or declarative when given a parent path)
        
        Returns:
            None
        
        Bifrost Mode:
            - Sends _EVENT_ZCRUMBS event with crumbs data
            - Frontend displays interactive breadcrumb UI
            - Returns immediately
        
        zCLI Mode:
            - Displays formatted breadcrumb trails:
              zCrumbs:
                file[Main > Setup > Config]
                vafile[App > Database > Users]
                block[^Root* > User Management]
        
        Structure (Session-based):
            session[SESSION_KEY_ZCRUMBS] = {
                "trails": {
                    "file": ["Main", "Setup", "Config"],
                    "vafile": ["App", "Database", "Users"],
                    "block": ["^Root*", "User Management"]
                },
                "_context": {...},  # Internal metadata (filtered out)
                "_depth_map": {...}  # Internal metadata (filtered out)
            }
        
        Structure (Declarative with parent):
            {
                "trails": {
                    "declarative": ["zProducts", "zTheme", "Containers"]
                },
                "_source": "declarative"
            }
        
        Usage:
            # Session-based (Terminal or warm GUI)
            zcli.display.zEvents.zSystem.zCrumbs(zcli.session)
            
            # Declarative (works in both Terminal and Bifrost)
            zcli.display.zEvents.zSystem.zCrumbs(parent="zProducts.zTheme", show='structure')
        
        Notes:
            - Uses SESSION_KEY_ZCRUMBS constant for session access
            - Joins trail items with " > " separator
            - Displays in "scope[path]" format
            - Filters out internal metadata keys (_context, _depth_map)
            - parent parameter enables stateless breadcrumbs for both Terminal and Bifrost
        """
        # `crumbs` is a Bifrost-only snapshot: the expander attaches the live session
        # trail to the show:session chunk (because the Bifrost page streams this event's
        # raw metadata and zCrumbs() never runs client-side). In zCLI THIS method runs
        # and reads the trail straight from session below, so the snapshot is ignored
        # here — it exists only so handle(**params) doesn't choke on the extra key.
        _ = crumbs

        # Auto-inject session if not provided (declarative .zolo support)
        if session_data is None and hasattr(self.display, 'zos'):
            session_data = self.display.zos.session

        # Manual mode: author-declared trail (zPaths + plain labels) — highest priority,
        # no session/folder logic. Shares one renderer with static (both are pre-defined).
        if show == 'manual':
            return self._render_predefined_trail(trail, header=header, zMenu=zMenu)

        # Structure mode: the trail of where the page SITS — derived from the walker
        # context (zVaFolder + zVaFile). ONE logic, no second path. `parent` is just a
        # zPath ALREADY ON THIS PAGE'S ROUTE that tells the trail WHERE TO START: the
        # deepest of its segments that's on the trail becomes the first crumb, trimming
        # everything above it. No parent → the trail starts after the mount root.
        if show == 'structure':
            folder_raw = (session_data or {}).get('zVaFolder', '')
            file_raw = (session_data or {}).get('zVaFile', '')
            if not folder_raw and not file_raw:
                return None
            # "@.zViews.zProducts.zOS.Events" → grammar split → ["zViews", "zProducts",
            # "zOS", "Events"] → drop mount root (idx 0) → ["zProducts", "zOS", "Events"]
            folder_parts = list(zpath.split(folder_raw).segments) if folder_raw else []
            folder_segments = folder_parts[1:] if len(folder_parts) > 1 else []
            # "zUI.zNavigation" → strip "zUI." prefix → "zNavigation"
            file_label = file_raw[len('zUI.'):] if file_raw.startswith('zUI.') else file_raw
            segments = [s for s in folder_segments if s] + ([file_label] if file_label else [])
            if not segments:
                return None
            # parent: a zPath on the route → start the trail at it. Match the DEEPEST
            # parent segment that's on the trail and slice from there, so the parent's
            # page becomes the first crumb. 'zUI' is structural noise, never a crumb.
            if parent:
                p_segs = [s for s in zpath.split(parent).segments if s and s != 'zUI']
                cut = next((segments.index(s) for s in reversed(p_segs) if s in segments), None)
                if cut is not None:
                    segments = segments[cut:]
            if self.display.zPrimitives.try_gui_event(
                _EVENT_ZCRUMBS, {_KEY_CRUMBS: {'trails': {'structure': segments}}}
            ):
                return None
            header_text = header if header else _MSG_ZCRUMBS_HEADER
            if zMenu:
                # Display as a menu — segments are labels only (no zPaths to navigate to).
                # Selecting is informational; returns None (no zLink possible without hub convention).
                self.BasicOutputs.text("", indent=0, break_after=False)
                self.zMenu(options=segments, title=header_text)
                return None
            parts = []
            for i, seg in enumerate(segments):
                if i == len(segments) - 1:
                    parts.append(f"{Colors.ZCRUMB}{seg}{Colors.RESET}")
                else:
                    parts.append(f"{Colors.SECONDARY}{seg}{Colors.RESET}")
            trail_str = f" {_FORMAT_BREADCRUMB_SEPARATOR} ".join(parts)
            self.BasicOutputs.text("", indent=0, break_after=False)
            self.BasicOutputs.text(
                f"{Colors.PRIMARY}{header_text}{Colors.RESET}", indent=0, break_after=False
            )
            self.BasicOutputs.text(trail_str, indent=0, break_after=False)
            self.BasicOutputs.text("", indent=0, break_after=False)
            return None

        # Session mode (default): pull the live trail from the session
        z_crumbs = session_data.get(SESSION_KEY_ZCRUMBS, {}) if session_data else {}

        # Try to send as WebSocket event first (for top-level zCrumbs calls)
        # For nested zCrumbs (in YAML structures), this will return False and fall through to embedding
        if self.display.zPrimitives.try_gui_event(_EVENT_ZCRUMBS, {_KEY_CRUMBS: z_crumbs}):
            return None  # GUI event sent successfully

        # zCLI mode - display breadcrumbs using composed events
        # Phase 1: For show='session', if breadcrumbs are empty, initialize with current file path
        if show == 'session' and not z_crumbs and session_data:
            # Construct full file path from session (same format as navigation system)
            # Format: @.UI.zProducts.zTheme.zUI.zContainers.zContainers_Details
            zfolder = session_data.get('zVaFolder', '')  # e.g., "@.UI.zProducts.zTheme"
            zfile = session_data.get('zVaFile', '')      # e.g., "zUI.zContainers"
            zblock = session_data.get('zBlock', '')      # e.g., "zContainers_Details"

            # Construct full path
            full_path_parts = []
            if zfolder:
                full_path_parts.append(zfolder)
            if zfile:
                full_path_parts.append(zfile)
            if zblock:
                full_path_parts.append(zblock)

            if full_path_parts:
                full_path = '.'.join(full_path_parts)
                # Initialize breadcrumbs with file path and empty trail
                z_crumbs = {
                    'trails': {
                        full_path: []  # Empty trail, but full file path is shown
                    }
                }

        if not z_crumbs:
            return None

        # zMenu mode for session: scope keys = visited pages in chronological order
        if zMenu and show == 'session':
            trails_dict = z_crumbs.get('trails', z_crumbs) if isinstance(z_crumbs, dict) else {}
            nav_paths = []
            labels = []
            for scope, val in trails_dict.items():
                if scope.startswith('_') or not isinstance(val, list):
                    continue
                # Strip #N suffix → navigable base path
                base_path = scope.split('#')[0] if '#' in scope else scope
                nav_paths.append(base_path)
            if not nav_paths:
                return None
            labels = _derive_zpath_labels(nav_paths)
            header_text = header if header else _MSG_ZCRUMBS_HEADER
            self.BasicOutputs.text("", indent=0, break_after=False)
            selected = self.zMenu(options=labels, title=header_text)
            if selected and selected in labels:
                selected_path = nav_paths[labels.index(selected)]
                return {'zLink': selected_path}
            return None

        # Phase 0.5: Use centralized banner method to filter out metadata (_context, _depth_map)
        # This ensures only user-facing trails are displayed, not internal architecture
        # NOTE: If we manually initialized z_crumbs (session bootstrap), use z_crumbs directly
        manually_initialized = ('trails' in z_crumbs and len(z_crumbs.get('trails', {})) == 1 and
                                list(z_crumbs.get('trails', {}).values())[0] == [])

        has_navigation = (
            hasattr(self.display, 'zos') and hasattr(self.display.zos, 'navigation')
            and hasattr(self.display.zos.navigation, 'breadcrumbs')
        )
        if manually_initialized or not has_navigation:
            # Manually initialized (session bootstrap) or no-navigation fallback
            crumbs_display = {}
            # Handle enhanced format: check if 'trails' key exists (Phase 0.5+)
            trails_dict = z_crumbs.get('trails', z_crumbs)
            for scope, trail in trails_dict.items():
                # Skip internal metadata keys (_context, _depth_map)
                if scope.startswith('_'):
                    continue
                # Only process actual trail lists
                if isinstance(trail, list):
                    path = _FORMAT_BREADCRUMB_SEPARATOR.join(trail) if trail else ""
                    crumbs_display[scope] = path
        else:
            # Session-based mode (show='session'): DRY reuse breadcrumbs.zCrumbs_banner()
            crumbs_display = self.display.zos.navigation.breadcrumbs.zCrumbs_banner()

        # Display breadcrumbs using BasicOutputs.text()
        self.BasicOutputs.text("", indent=0, break_after=False)
        # Header: authored events pass header='zCrumbs:', auto-display uses default
        header_text = header if header else _MSG_ZCRUMBS_HEADER
        header_colored = f"{Colors.PRIMARY}{header_text}{Colors.RESET}"
        self.BasicOutputs.text(header_colored, indent=0, break_after=False)
        for scope, path in crumbs_display.items():
            if scope == 'declarative':
                content = f"[{path}]"
            elif header:
                # Authored zCrumbs event: strip scope path to block name only, apply ZCRUMB color
                block_name = scope.split('.')[-1] if '.' in scope else scope
                content = (
                    f"{Colors.ZCRUMB}{block_name}{Colors.RESET}"
                    f"  [{Colors.SECONDARY}{path}{Colors.RESET}]"
                )
            else:
                content = _FORMAT_CRUMB_SCOPE.format(scope=scope, path=path)
            self.BasicOutputs.text(content, indent=0, break_after=False)
        # Add blank line after breadcrumbs
        self.BasicOutputs.text("", indent=0, break_after=False)

    def _render_predefined_trail(
        self, trail: Optional[list], header: Optional[str] = None, zMenu: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Render a PRE-DEFINED breadcrumb trail (shared by show='manual' and show='structure' w/ a parent).

        One renderer, one look. Items may be zPaths (`@.UI.zProducts.zOS`) or plain
        labels — zPaths get min-depth-unique labels, plain strings pass through as-is.
        Output is a colored arrow trail with the last item in ZCRUMB (current), the
        rest in SECONDARY. In Bifrost the full paths go over the wire; CLI shows labels.

        Returns {'zLink': <path>} when zMenu selects a zPath item, otherwise None.
        """
        if not trail:
            return None
        items = [str(i).strip('"\'') for i in (trail if isinstance(trail, list) else [trail])]
        # Derive labels: zPaths → min-depth uniqueness (file.block, deeper if needed),
        # plain strings → used verbatim. Preserve original order when interleaving.
        _sigils = (zpath.SIGIL_WORKSPACE, zpath.SIGIL_HOME)
        zpath_labels = _derive_zpath_labels([s for s in items if s.startswith(_sigils)])
        zpath_iter = iter(zpath_labels)
        plain_iter = iter([s for s in items if not s.startswith(_sigils)])
        labels = [
            next(zpath_iter) if s.startswith(_sigils) else next(plain_iter)
            for s in items
        ]
        # Bifrost: send full paths (navigable); CLI: render labels.
        z_crumbs = {'trails': {'manual': items}, '_source': 'manual', '_labels': labels}
        if self.display.zPrimitives.try_gui_event(_EVENT_ZCRUMBS, {_KEY_CRUMBS: z_crumbs}):
            return None
        header_text = header if header else _MSG_ZCRUMBS_HEADER
        if zMenu:
            # Interactive: a crumb pick is a BULK-BACK intent, not a plain forward.
            # We emit {'zCrumb': <full path>} and let zNavigation decide: if the
            # path names a scope already on the trail it unwinds to it (the lone
            # POP_TO caller); otherwise it falls forward to zLink. The intent is
            # omega-agnostic here — Bifrost layers the in-scope section anchor on
            # its own render; zCLI needs only the scope path.
            self.BasicOutputs.text("", indent=0, break_after=False)
            selected = self.zMenu(options=labels, title=header_text)
            if selected and selected in labels:
                return {'zCrumb': items[labels.index(selected)]}
            return None
        parts = [
            f"{Colors.ZCRUMB if i == len(labels) - 1 else Colors.SECONDARY}{label}{Colors.RESET}"
            for i, label in enumerate(labels)
        ]
        trail_str = f" {_FORMAT_BREADCRUMB_SEPARATOR} ".join(parts)
        self.BasicOutputs.text("", indent=0, break_after=False)
        self.BasicOutputs.text(
            f"{Colors.PRIMARY}{header_text}{Colors.RESET}", indent=0, break_after=False
        )
        self.BasicOutputs.text(trail_str, indent=0, break_after=False)
        self.BasicOutputs.text("", indent=0, break_after=False)
        return None

    def zMenu(
        self,
        options: List[str],
        title: Optional[str] = None,
        allow_back: bool = False
    ) -> Optional[str]:
        """
        Display a menu and return the selected option key.

        zMenu is the primitive for all menu rendering. The * and ~ modifiers
        are shorthands that will eventually delegate here.

        Args:
            options: Ordered list of option display labels, e.g. ["Option A", "Option B"]
            title: Optional menu header text shown above the options
            allow_back: If True, a "Back" entry is appended to the option list

        Returns:
            Optional[str]: Selected label in zCLI mode; None in Bifrost mode
                           (Bifrost selection is returned via WebSocket input response)

        Wire format (Bifrost):
            { event: "zMenu", options: [...], title: str|None, allow_back: bool }

        zCLI mode:
            Renders a numbered list via InteractiveInputs.selection() and returns
            the chosen label string.
        """
        # Bifrost: send clean event, selection comes back via display_prompt_request
        if self.display.zPrimitives.try_gui_event(_EVENT_ZMENU, {
            _KEY_OPTIONS: options,
            _KEY_TITLE: title,
            _KEY_ALLOW_BACK: allow_back,
        }):
            return None

        # zCLI mode
        if not options:
            return None

        prompt = title or _MSG_DEFAULT_MENU_PROMPT
        if self.InteractiveInputs:
            return self.InteractiveInputs.selection(
                prompt=prompt,
                options=options,
                multi=False,
                style=STYLE_NUMBERED
            )
        # Fallback display-only (no InteractiveInputs wired)
        self.BasicOutputs.text("", indent=0, break_after=False)
        for i, label in enumerate(options, 1):
            self.BasicOutputs.text(
                _FORMAT_MENU_ITEM.format(index=i, label=label),
                indent=0, break_after=False
            )
        return None
