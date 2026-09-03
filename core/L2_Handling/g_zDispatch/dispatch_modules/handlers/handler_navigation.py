# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/handlers/handler_navigation.py

"""
Navigation Handler Module for zDispatch Subsystem.

This module provides the NavigationHandler class, which handles zLink and zDelta
navigation commands. It supports inter-file navigation (zLink) and intra-file
block navigation (zDelta) with auto-discovery fallback.

Extracted from dispatch_launcher.py as part of Phase 2 refactoring.
This module depends on zNavigation subsystem and Walker, but has no internal
dispatch dependencies.

Supported Commands:
    - zLink: Inter-file navigation (menu:users, file paths, etc.)
    - zDelta: Intra-file block navigation with auto-discovery

Features:
    - zLink routing to zNavigation subsystem
    - zDelta target block resolution with fallback chain
    - Auto-discovery of blocks in separate files
    - Breadcrumb scope initialization for zDelta
    - Walker validation for navigation commands

Usage Example:
    handler = NavigationHandler(zos, display, logger)
    
    # zLink command
    result = handler.handle_zlink({"zLink": "menu:users"}, walker)
    
    # zDelta command  
    result = handler.handle_zdelta({"zDelta": "$Demo_Block"}, walker)

Integration:
    - zNavigation: Inter-file navigation via zos.navigation.handle_zLink()
    - Walker: Block execution and session management
    - zLoader: File loading for fallback discovery

Thread Safety:
    - Modifies walker.session in-place (zBlock, zCrumbs)
    - Not thread-safe for same walker instance
    - Safe for concurrent walkers
"""

from zOS import Any, Dict, List, Optional

# zPath grammar — Layer-0 SSOT for sigil/segment decomposition.
from zSys import zpath

# Import dispatch constants
from ..dispatch_constants import (
    KEY_ZDELTA,
    KEY_ZMENU,
    KEY_ZDELEGATE,
    KEY_ZMODAL,
    _LABEL_HANDLE_ZDELTA,
    _LABEL_HANDLE_ZDELEGATE,
    _LABEL_HANDLE_ZMODAL,
    _DEFAULT_INDENT_HANDLER,
    _DEFAULT_STYLE_SINGLE,
)

# Mode helper (SSOT) — gates the zCLI-only navbar Done row + RESET flag.
from ..dispatch_helpers import is_bifrost_mode

# SSOT halt signal — a navbar pick replaces the page, so it terminates the host
# block loop (zVocabulary.CONTROL_RETURN_STOP = "stop").
from zOS.zVocabulary import CONTROL_RETURN_STOP

# Navbar Done affordance (SSOT in zNavigation): the "exit-forward" row every
# navbar carries in the terminal (a blocking menu there needs a way to step past).
# NAV_SIGNAL: the zCLI REPLACE-hop trampoline sentinel — a menu pick whose
# dispatch STAGED a navigation must propagate it, never swallow it (zOS#19).
from zOS.L2_Handling.h_zNavigation.navigation_modules.navigation_constants import (
    NAV_ZDONE,
    NAV_SIGNAL,
)

class NavigationHandler:
    """
    Handles zLink and zDelta navigation commands.
    
    This class provides focused routing for navigation operations,
    supporting both inter-file (zLink) and intra-file (zDelta) navigation
    with auto-discovery and breadcrumb management.
    
    Attributes:
        zos: zOS framework instance (provides navigation, loader, logger)
        display: zDisplay instance for UI output (optional)
        logger: Logger instance for debug output
    
    Methods:
        handle_zlink(): Route zLink command to zNavigation
        handle_zdelta(): Handle zDelta intra-file navigation
        
        Private helpers:
        _resolve_delta_target_block(): Resolve target block with fallback
        _construct_fallback_zpath(): Build fallback zPath for auto-discovery
        _check_walker(): Validate walker instance
        _display_handler(): Display handler label
    
    Example:
        handler = NavigationHandler(zos, display, logger)
        
        # Inter-file navigation
        link_result = handler.handle_zlink({"zLink": "menu:users"}, walker)
        
        # Intra-file navigation with auto-discovery
        delta_result = handler.handle_zdelta({"zDelta": "$Settings"}, walker)
    """

    def __init__(self, zos: Any, display: Any, logger: Any) -> None:
        """
        Initialize navigation handler.
        
        Args:
            zos: zOS framework instance (provides navigation, loader)
            display: zDisplay instance for UI output
            logger: Logger instance for debug output
        
        Example:
            handler = NavigationHandler(zos, display, logger)
        """
        self.zos = zos
        self.display = display
        self.logger = logger

    # ========================================================================
    # PUBLIC API - Navigation Commands
    # ========================================================================

    def handle_zlink(
        self,
        zHorizontal: Dict[str, Any],
        walker: Optional[Any]
    ) -> Optional[Any]:
        """
        Route zLink command to zNavigation subsystem.
        
        Handles inter-file navigation (menu links, file paths, etc.)
        Requires walker instance for navigation context.
        
        Args:
            zHorizontal: Dict containing KEY_ZLINK (target path)
            walker: Walker instance (required for navigation)
        
        Returns:
            Navigation result from zNavigation, or None if walker not available
        
        Example:
            result = handler.handle_zlink({"zLink": "menu:users"}, walker)
            result = handler.handle_zlink({"zLink": "@.UI.zSettings"}, walker)
        
        Notes:
            - Validates walker instance before proceeding
            - Delegates to zNavigation.handle_zLink()
            - Logs navigation attempt
        """
        # Fall back to the engine walker when none was threaded through. A
        # block-level ^Route zWizard runs via zos.zEngine (walker=None), but
        # zLink navigation still needs the live walker — and zos.walker shares
        # the same session, so navigation targets the correct context.
        if walker is None:
            walker = getattr(self.zos, "walker", None)

        if not self._check_walker(walker, "zLink"):
            return None

        self.logger.debug("[NavigationHandler] zLink command detected")
        return self.zos.navigation.handle_zLink(zHorizontal, walker=walker)

    def handle_zmenu(
        self,
        zHorizontal: Dict[str, Any],
        walker: Optional[Any],
        crumb_key: Optional[str] = None,
        navbar_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Route the longhand ``zMenu`` block to the ONE menu engine (SSOT).

        ``zMenu`` is the spelled-out form of the ``*`` key-modifier. A
        ``Name*: [A, B]`` shorthand is sugar for::

            zMenu:
                title: ...
                zAnchor: true|false      # true = no Back (the ~ prefix)
                options: [A, B]          # sibling block keys to offer

        Both forms funnel through ``_run_menu`` → ``navigation.create``. This
        method only NORMALIZES the dict (or a bare ``zMenu: [A, B]`` list) into
        ``(options, title, anchored)``; the shared loop does the rest. The option
        strings name SIBLING blocks; rendering the picked block on selection is
        the walker loop's job — this seam builds, shows, and re-shows the menu.

        Args:
            zHorizontal: Dict containing KEY_ZMENU (the menu spec).
            walker: Walker instance (falls back to the engine walker).
            crumb_key: When set (the ``*`` modifier passes its key), record a
                breadcrumb APPEND for the menu. The bare longhand route omits it.
            navbar_key: When set (the ``~zNavBar*`` modifier), run the navbar
                flavor — RBAC-filter the options, append the zCLI Done row, and
                treat a pick as terminal (STOP). Innately anchored, no crumb.
            context: Dispatch context (carries ``_resolved_data``) — used to
                resolve dynamic ``%data.*`` option sources.

        Returns:
            The selected option string, the re-dispatched nav result, or None.

        Dynamic options (longhand only): ``options`` may be a runtime SOURCE
        instead of a literal list — ``&plugin(...)`` (zFunc result), ``%data.key``
        (a resolved _data list), or ``%var`` (a session zVar). A ``display`` key
        names the field to show when the source yields dicts.
        """
        if walker is None:
            walker = getattr(self.zos, "walker", None)

        spec = zHorizontal.get(KEY_ZMENU)
        if isinstance(spec, dict):
            raw_options = spec.get("options")
            title = spec.get("title")
            anchored = bool(spec.get("zAnchor", False))
            display = spec.get("display")
        elif isinstance(spec, list):
            # Bare list form — title/back default like the plain `*` shorthand.
            raw_options, title, anchored, display = spec, None, False, None
        else:
            raw_options, title, anchored, display = None, None, False, None

        options = self._resolve_menu_options(raw_options, display, context)
        if not options:
            self.logger.warning("[NavigationHandler] zMenu has no options to render")
            return None

        self.logger.debug("[NavigationHandler] zMenu command detected")
        return self._run_menu(
            options, title, anchored, walker,
            crumb_key=crumb_key, navbar_key=navbar_key,
        )

    def _run_menu(
        self,
        options: Any,
        title: Optional[str],
        anchored: bool,
        walker: Optional[Any],
        crumb_key: Optional[str] = None,
        navbar_key: Optional[str] = None
    ) -> Optional[Any]:
        """
        Shared menu loop (SSOT) — the ONE place a menu is shown + its result
        handled, used by the longhand ``zMenu`` route AND the ``*`` modifier
        (plain AND navbar). Shows the menu via the single engine
        (``navigation.create``); on a child navigation that returns ``zBack``,
        re-shows THIS menu (the nested-menu re-show loop) after popping the
        unwound crumb. A ``$``-pick returns a nav dict, re-dispatched through the
        launcher so the branch actually navigates.

        Navbar flavor (``navbar_key`` set): the options are RBAC-filtered and a
        zCLI Done row is appended before the loop; picking Done disarms the
        pending RESET and continues the block flow; picking an item is terminal
        (STOP) because the navbar pick replaces the page.
        """
        is_navbar = navbar_key is not None
        if is_navbar:
            # RBAC filter + (zCLI only) Done row. The navbar records no crumb (its
            # only trail effect is the RESET armed inside _apply_navbar_rbac).
            options = self._apply_navbar_rbac(navbar_key, options)
            if not is_bifrost_mode(self.zos.session):
                options = list(options) + [NAV_ZDONE]
        elif crumb_key and getattr(self.zos, "navigation", None):
            # Crumb zStride — parity with the * modifier. Opt-in: the shorthand
            # passes its key; the bare longhand route omits it. Routes through
            # the SSOT recorder contract (record_zStride), not a raw APPEND.
            self.zos.navigation.record_zStride(crumb_key, walker=None)

        while True:
            result = self.zos.navigation.create(
                options, title=title, allow_back=not anchored, walker=walker
            )
            # Direct Back from THIS menu → propagate up to the parent.
            if result == "zBack":
                return result
            # Navbar Done → NO navigation. Disarm the pending RESET (armed at
            # render on the assumption of an item hop) and continue the block flow.
            if is_navbar and result == NAV_ZDONE:
                self.zos.navigation.breadcrumbs.clear_navbar_pending()
                self.logger.debug(
                    "[zMenu] Navbar Done — continue block flow (no nav, RESET disarmed)"
                )
                return None
            # A $-pick returns a nav dict — re-dispatch it.
            if isinstance(result, dict):
                result = self.zos.dispatch.launcher.launch(result, None, walker)
                # Child unwound with zBack → pop its crumb and re-show this menu.
                if result == "zBack":
                    self._pop_last_crumb()
                    continue
                # zCLI trampoline (zOS#19): the zLink hop did NOT render — it
                # STAGED the target in session and returned NAV_SIGNAL for
                # zWalker.run()'s trampoline to re-enter execute_loop with.
                # Returning STOP here swallowed the signal: the staged page was
                # never walked and the session ended ("Walker session
                # completed") right after the pick. Bubble it up instead — the
                # host block halts anyway because the executor exits on it.
                if result == NAV_SIGNAL:
                    self.logger.debug(
                        "[zMenu] Pick staged a navigation — bubbling NAV_SIGNAL"
                    )
                    return NAV_SIGNAL
                # Navbar pick is terminal: the target already rendered inside
                # launch() (zBifrost / direct-call paths); halt the host block
                # so it does not re-render the keys.
                if is_navbar:
                    self.logger.debug(
                        "[zMenu] Navbar pick dispatched — halting host block (stop)"
                    )
                    return CONTROL_RETURN_STOP
            return result

    def _apply_navbar_rbac(self, zKey: str, options: List[Any]) -> List[Any]:
        """
        RBAC-filter navbar items, re-evaluated dynamically on every render.

        Strips ``$`` delta prefixes before filtering, re-adds them after (items
        carrying an explicit ``zLink`` / ``zBrand`` keep their absolute target).
        In zCLI it also arms the navbar RESET marker so the next pick resets the
        crumb trail (scoped for inline bars, full for global); in Bifrost the
        reset is client-driven, so the flag is not set here (SSOT split).
        """
        self.logger.framework.debug(
            f"[NavigationHandler] Applying dynamic RBAC filtering for navbar: {zKey}"
        )

        clean_items = [
            item.lstrip("$") if isinstance(item, str) else item for item in options
        ]

        filtered_items = self.zos.navigation._filter_navbar_byzRBAC(clean_items)  # pylint: disable=protected-access
        self.logger.framework.info(
            f"[NavigationHandler] Navbar filtered: {len(options)} → {len(filtered_items)} items"
        )

        filtered_with_prefix = []
        for item in filtered_items:
            if isinstance(item, str):
                filtered_with_prefix.append(f"${item}")
            elif isinstance(item, dict):
                item_name = list(item.keys())[0]
                item_data = item[item_name]
                carries_zlink = (
                    item_name == "zBrand"
                    or (isinstance(item_data, dict) and item_data.get("zLink"))
                )
                if carries_zlink:
                    filtered_with_prefix.append(item)
                else:
                    filtered_with_prefix.append({f"${item_name}": item_data})
            else:
                filtered_with_prefix.append(item)

        # SET NAVBAR FLAG (zCLI ONLY): the next navigation is a navbar pick → arm
        # the RESET. zNavigation owns the marker (inline bars reset to their host
        # scope; global bars reset to the absolute root).
        if not is_bifrost_mode(self.zos.session):
            is_inline = zKey.startswith("~zNavBarInline")
            self.zos.navigation.breadcrumbs.set_navbar_pending(scoped=is_inline)
            self.logger.framework.debug(
                "[NavigationHandler] Navbar flag set (%s): next navigation triggers OP_RESET",
                "SCOPED/inline" if is_inline else "FULL/global",
            )

        return filtered_with_prefix

    # ========================================================================
    # PRIVATE HELPERS - Dynamic Option Resolution (longhand zMenu)
    # ========================================================================

    def _resolve_menu_options(
        self,
        raw: Any,
        display: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> List[Any]:
        """
        Resolve a zMenu ``options`` value to a concrete list of option strings.

        A literal list passes through untouched (the shorthand + static longhand
        path). A STRING is a dynamic source, resolved against the SSOT seams:

            &plugin(...)   → zFunc result (a plugin that returns a list)
            %data.<key>    → a resolved spool list (zos.zloom._lookup_list_source — SSOT)
            %<var>         → a session zVar
            <plain>        → a single literal option
        
        Source rows that are dicts are reduced to a label via ``display`` (or the
        row's first value when no display field is named).
        """
        if isinstance(raw, list):
            return raw
        if not isinstance(raw, str):
            return raw or []

        ref = raw.strip()
        data: Any = None
        if ref.startswith("&"):
            try:
                data = self.zos.zfunc.handle(f"zFunc({ref})")
            except Exception as e:  # plugin failure must not blank the menu
                self.logger.warning(f"[NavigationHandler] zMenu plugin options '{ref}' failed: {e}")
                return []
            # A plugin may return a ZResult — unwrap to its data payload.
            if hasattr(data, "success") and hasattr(data, "data"):
                data = data.data if data.success else None
        elif ref.startswith("%data."):
            data = self.zos.zloom.resolve_list_source(ref, context)
        elif ref.startswith("%"):
            data = self.zos.session.get("zVars", {}).get(ref[1:])
        else:
            return [raw]  # a single static option

        return self._coerce_options(data, display)

    def _coerce_options(self, data: Any, display: Optional[str]) -> List[str]:
        """Normalize a resolved source into a list of display strings. Dicts use
        the ``display`` field (or their first value); scalars are stringified."""
        if data is None:
            return []
        if not isinstance(data, list):
            data = [data]
        out: List[str] = []
        for item in data:
            if isinstance(item, dict):
                if display and item.get(display) is not None:
                    out.append(str(item.get(display)))
                else:
                    out.append(str(next(iter(item.values()), item)))
            else:
                out.append(str(item))
        return out

    def _pop_last_crumb(self) -> None:
        """Pop the last crumb-trail entry when a child menu's zBack unwinds back
        to this menu (shared by the longhand loop and the navbar * path)."""
        try:
            session = self.zos.session
            crumbs = session.get("zCrumbs", {})
            trails = crumbs.get("trails") if isinstance(crumbs, dict) else None
            if trails and isinstance(trails, dict):
                active_key = crumbs.get("active_scope") or (
                    next(reversed(trails)) if trails else None
                )
                trail = trails.get(active_key) if active_key else None
                if trail:
                    removed = trail.pop()
                    self.logger.framework.debug(f"[zMenu] Popped crumb on zBack: '{removed}'")
        except Exception as e:
            self.logger.framework.debug(f"[zMenu] _pop_last_crumb failed: {e}")

    def handle_zdelta(
        self,
        zHorizontal: Dict[str, Any],
        walker: Optional[Any]
    ) -> Optional[Any]:
        """
        Handle zDelta intra-file block navigation.
        
        Navigates to a different block within the same UI file or
        auto-discovers blocks from separate files (fallback pattern).
        
        Args:
            zHorizontal: Dict containing KEY_ZDELTA (target block name)
            walker: Walker instance (required for navigation)
        
        Returns:
            Navigation result from walker.execute_loop(), or None if block not found
        
        Example:
            result = handler.handle_zdelta({"zDelta": "$Settings_Menu"}, walker)
            result = handler.handle_zdelta({"zDelta": "%Demo_Block"}, walker)
        
        Notes:
            - Strips $ or % prefix from target block name
            - Fallback: If block not in current file, tries loading zUI.{blockName}.yaml
            - Creates new breadcrumb scope for target block
            - Updates session zBlock to reflect navigation
        """
        # Fall back to the engine walker when none was threaded through — parity
        # with handle_zlink / handle_zdelegate. The dict-form button action
        # (action: {zDelta: {target, zPsi}}, the ONLY way to carry zPsi) reaches
        # here via dispatch.handle("action", …) with walker=None; zos.walker
        # shares the same session, so the same-file hop targets the right context.
        if walker is None:
            walker = getattr(self.zos, "walker", None)

        if not self._check_walker(walker, "zDelta"):
            return None

        self._display_handler(_LABEL_HANDLE_ZDELTA)

        # Compile to the canonical nav IR (SSOT) — the SAME compiler zLink and
        # zURL use. Unifies the string shorthand and the {target, zPsi} dict, and
        # carries zPsi: the dict form's anchor sets the walker start_key in the
        # landed block (a menu-pick start line, by address). Verb is pinned to
        # zDelta (explicit dispatch); KEY_ZDELTA == "zDelta" is the verb token.
        intent = self.zos.navigation.compile_intent(
            zHorizontal[KEY_ZDELTA], verb=KEY_ZDELTA
        )
        target_block_name = intent.target
        zpsi_anchor = intent.zpsi

        # Strip $ or % prefix if present (delta navigation markers)
        if isinstance(target_block_name, str) and target_block_name.startswith(("$", "%")):
            target_block_name = target_block_name[1:]

        self.logger.framework.debug(f"[NavigationHandler] zDelta navigation to block: {target_block_name}")

        # Get current zVaFile from session — reconstruct full path if zVaFolder is present.
        # Inside a zDash panel the session route stays on the dashboard, so prefer the
        # panel's stamped source file (set by zDash._render_zdash_panel) — the $target
        # block lives there, not in the dashboard file. Mirrors handle_zdelegate so a
        # zDelegate normalized to zDelta by the Bifrost client resolves identically.
        panel_zVaFile = walker.session.get("_panel_zVaFile")
        if panel_zVaFile:
            current_zVaFile = panel_zVaFile
        else:
            zVaFile = walker.session.get("zVaFile") or walker.zSpark_obj.get("zVaFile")
            if not zVaFile:
                self.logger.error("[NavigationHandler] No zVaFile in session or zspark_obj")
                return None

            zVaFolder = walker.session.get("zVaFolder") or walker.zSpark_obj.get("zVaFolder")
            if zVaFolder and not zVaFile.startswith("@"):
                current_zVaFile = f"{zVaFolder}.{zVaFile}"
            else:
                current_zVaFile = zVaFile

        self.logger.framework.debug(f"[NavigationHandler] Resolved zDelta file path: {current_zVaFile}")

        # Reload the UI file
        raw_zFile = walker.loader.handle(current_zVaFile)
        if not raw_zFile:
            self.logger.error(f"[NavigationHandler] Failed to load UI file: {current_zVaFile}")
            return None

        # Extract the target block dict - with fallback chain
        target_block_dict = self._resolve_delta_target_block(
            target_block_name,
            raw_zFile,
            current_zVaFile,
            walker
        )

        if not target_block_dict:
            self.logger.error(f"[NavigationHandler] Failed to resolve block '{target_block_name}'")
            return None

        # Update session and create breadcrumb scope via the SSOT seeder.
        # zNavigation owns crumb scope construction; zDelta must not invent its
        # own format. The legacy seeder wrote the FLAT top-level form
        # (session["zCrumbs"][path]) which the enhanced-format readers ignored —
        # so zDelta scopes were orphaned and zBack from a delta page could not
        # return. seed_scope writes into the enhanced 'trails' map and stamps the
        # '$' arrival marker so a delta page is one back-unit, identical to zLink.
        walker.session["zBlock"] = target_block_name
        self.zos.navigation.breadcrumbs.seed_scope(
            walker=walker,
            folder="",
            file=current_zVaFile,
            block=target_block_name,
            arrival=True,
        )

        # zPsi: resolve the #anchor to a real key and start the run there (run-from
        # -here-to-end, like a menu pick). Missing anchor → start at the top.
        start_key = self.zos.navigation.resolve_anchor_key(target_block_dict, zpsi_anchor)
        if zpsi_anchor and not start_key:
            self.logger.framework.warning(
                f"[zPsi] Anchor '#{zpsi_anchor}' not found in block "
                f"'{target_block_name}' — starting at top"
            )

        # zLoom SSOT pre-render (parity with navigation_linking's zLink hop and
        # zWalker.run's boot entry): re-bind the file-root zMeta.zSpool + loop-
        # expand any zList/zShuttle in the LANDED block BEFORE dispatch. Without
        # this a zDelta ($Block, same-file) hop reused whatever %data.* was
        # resolved at app boot (session["_current_block_data"]) forever after —
        # a spool declaring a live list (e.g. a zList's `source: %data.<spool>`)
        # never saw a row written by an insert/delete that happened AFTER boot,
        # even though every OTHER nav primitive (zLink, the initial boot render)
        # already re-resolved it on each hop. First caught by zDemos/zBooking's
        # My_Bookings screen: a booking made via New_Booking (a zDelta hop away)
        # never appeared in My_Bookings' zList until the next process restart.
        #
        # A zDash PANEL file has no file-root zMeta at all — the convention
        # (16_dashboards.md, zConsole's own panels) puts zMeta NESTED under the
        # panel's own top block (`Contacts: {zMeta: {zSpool: [...]}, ...}`), so
        # build_binding_block's `zfile_parsed.get("zMeta")` finds nothing for a
        # same-file Refresh hop (`zDelta($Contacts)` landing back on itself) —
        # the panel's zList silently fell back to its unbound %item template
        # (zCRM's zDash capstone, Refresh-after-Add). Fall back to the LANDED
        # block's own zMeta when the file has none at its root.
        binding_source = raw_zFile
        if isinstance(raw_zFile, dict) and not raw_zFile.get("zMeta") and isinstance(target_block_dict, dict) and target_block_dict.get("zMeta"):
            binding_source = target_block_dict
        block_context = self.zos.zloom.prepare_block_render(binding_source, target_block_dict)

        # Navigate to the target block.
        # SSOT navigation (parity with zLink): hand the walker's own navigation
        # callbacks to the nested loop so the landed delta block honors zCrumbs.
        # Without them a zBack raised inside the target (e.g. a zBtn action: zBack)
        # had no on_back to pop the trail and was silently swallowed — the zCLI run
        # just ended instead of returning to the source block. Bifrost runs the
        # chunked executor (callbacks unused; zBack is client-side), so this only
        # affects the zCLI/zTerminal path — exactly where the gap showed.
        nav_callbacks = (
            walker._create_navigation_callbacks()
            if hasattr(walker, "_create_navigation_callbacks")
            else None
        )
        # REPLACE navigation: zCLI trampolines (stage + NAV_SIGNAL → flat stack),
        # zBifrost keeps the direct call. navigate_or_recurse owns the mode gate.
        if hasattr(walker, "navigate_or_recurse"):
            return walker.navigate_or_recurse(
                items_dict=target_block_dict,
                start_key=start_key,
                navigation_callbacks=nav_callbacks,
                context=block_context,
            )
        return walker.execute_loop(
            items_dict=target_block_dict,
            start_key=start_key,
            navigation_callbacks=nav_callbacks,
            context=block_context,
        )

    def handle_zdelegate(
        self,
        zHorizontal: Dict[str, Any],
        walker: Optional[Any]
    ) -> Optional[Any]:
        """
        Handle zDelegate — routeless activation of a same-file target block.

        zDelegate is the first-class, dual-mode "internal rewiring" verb. A
        delegating carrier (e.g. a zBtn with ``action: {zDelegate: $X}``) runs
        another block's behavior IN PLACE — same route, no breadcrumb push,
        AJAX-like (delta semantics). Both modes route through here: the CLI
        carrier harvest dispatches this dict on menu pick, and Bifrost wires the
        carrier's DOM click to the same target.

        Forms:
            {"zDelegate": "$Edit_Profile.Change_Photo"}
            {"zDelegate": {"target": "$Edit_Profile.Change_Photo", "data": {...}}}

        Target grammar:
            - "$Block"            top-level block in the current file
            - "$Block.Sub"        dotted descent into a nested section
            - "^"/"~"/"$"/"%"     leading markers are tolerated and stripped

        Differs from zDelta: zDelta is a navigation (mutates session zBlock +
        breadcrumb scope); zDelegate is activation-only and leaves the origin
        route untouched, so the user stays on the panel that hosts the carrier.

        TODO (v2 — cross-file delegation): "$" resolves ONLY within the current
        zVaFile (delta scope). Targets that leave the file need zLink syntax —
        "~" (machine-relative) or "@" (zSpark workspace-relative) zPaths. The
        ajax/routeless feel must be preserved even on those zLink-like targets:
        load + activate the foreign block IN PLACE without pushing a route. Stage
        this as a separate iteration (route via the zLink resolver, then run the
        resolved block through execute_loop without a breadcrumb push).
        """
        # Fall back to the engine walker when none was threaded through (e.g.
        # dispatched from the CLI *-menu carrier harvest, where the menu layer
        # renders via zos.display with walker=None). zos.walker shares the same
        # session, so the delegate target resolves/executes in the right context.
        if walker is None:
            walker = getattr(self.zos, "walker", None)

        if not self._check_walker(walker, "zDelegate"):
            return None

        self._display_handler(_LABEL_HANDLE_ZDELEGATE)

        # Accept both the bare-target form and the {target, data} dict form.
        spec = zHorizontal[KEY_ZDELEGATE]
        payload = None
        if isinstance(spec, dict):
            target = spec.get("target") or spec.get("to") or spec.get(KEY_ZDELTA)
            payload = spec.get("data") or spec.get("with")
        else:
            target = spec

        if not isinstance(target, str) or not target:
            self.logger.error("[NavigationHandler] zDelegate: missing/invalid target")
            return None

        # Strip leading nav/modifier markers ($ % ^ ~) defensively
        target = target.lstrip("$%^~")

        self.logger.framework.debug(f"[NavigationHandler] zDelegate → target: {target}")

        # Resolve the file that hosts the carrier ($ = "this file"). Inside a
        # zDash panel the session route stays on the dashboard, so prefer the
        # panel's stamped source file (set by zDash._render_zdash_panel) — the
        # carrier and its $target both live there. Fall back to the session
        # route (standalone / non-dashboard panels).
        panel_zVaFile = walker.session.get("_panel_zVaFile")
        if panel_zVaFile:
            current_zVaFile = panel_zVaFile
        else:
            zVaFile = walker.session.get("zVaFile") or walker.zSpark_obj.get("zVaFile")
            if not zVaFile:
                self.logger.error("[NavigationHandler] zDelegate: no zVaFile in session or zspark_obj")
                return None

            zVaFolder = walker.session.get("zVaFolder") or walker.zSpark_obj.get("zVaFolder")
            if zVaFolder and not zVaFile.startswith("@"):
                current_zVaFile = f"{zVaFolder}.{zVaFile}"
            else:
                current_zVaFile = zVaFile

        raw_zFile = walker.loader.handle(current_zVaFile)
        if not raw_zFile:
            self.logger.error(f"[NavigationHandler] zDelegate: failed to load UI file: {current_zVaFile}")
            return None

        # Resolve target (supports dotted descent into nested sections)
        target_block_dict = self._resolve_delta_target_block(
            target, raw_zFile, current_zVaFile, walker
        )
        if not target_block_dict:
            self.logger.error(f"[NavigationHandler] zDelegate: cannot resolve target '{target}'")
            return None

        # Optional data payload → stash on session for the target activation
        if isinstance(payload, dict):
            ctx = walker.session.setdefault("zDelegate_data", {})
            ctx.update(payload)
            self.logger.framework.debug(f"[NavigationHandler] zDelegate: payload merged: {payload}")

        # Activation-only: run the target in place. No zBlock/breadcrumb mutation
        # (routeless — the user stays on the origin panel/route).
        return walker.execute_loop(items_dict=target_block_dict)

    def handle_zmodal(
        self,
        zHorizontal: Dict[str, Any],
        walker: Optional[Any],
        source_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """
        Handle zModal — the CALL verb: run a block as a detour, auto-return.

        Where zAlpha/zDelta are GOTOs (route moves, trail records), zModal is a
        CALL: walk into the target, complete it, return to the firing point and
        resume. Trail-invisible (no crumb, route untouched); a zBack inside the
        modal dismisses it. This seam only RECOGNIZES the key and RESOLVES the
        authored form to a block dict — the run semantics are owned by
        zNavigation's Detour (zos.navigation.run_modal).

        Value forms (first-character routing, mirroring href):
            zModal: {zH1: Hello, ...}              # inline — the dict IS the modal
            zModal: $Block                          # same-file block (zDelta-style)
            zModal: @.zViews.zUI.Help               # cross-file (zAlpha-style)
            zModal: {zUI: <target>, params: {...}}  # longhand target (+ phase-2 params)

        zLoom is read-only here: a $/@ target's file-root zSpool bindings are
        pre-woven (prepare_block_render) so a data-bound modal renders exactly
        like the same block would as a page.
        """
        if walker is None:
            walker = getattr(self.zos, "walker", None)
        if not self._check_walker(walker, KEY_ZMODAL):
            return None

        self._display_handler(_LABEL_HANDLE_ZMODAL)

        spec = zHorizontal[KEY_ZMODAL]
        params = None

        # Longhand dict: {zUI: <target>, params: {...}}. Any OTHER dict is
        # inline content — the dict IS the modal (the _data-style polymorphism).
        if isinstance(spec, dict) and "zUI" in spec:
            params = spec.get("params")
            spec = spec.get("zUI")

        block_dict: Optional[Dict[str, Any]] = None
        block_context: Optional[Dict[str, Any]] = None

        if isinstance(spec, dict):
            # Inline content — already a block; the caller's context rides along
            # so %data.* woven for the firing page stays resolvable inside.
            block_dict, block_context = spec, context
        elif isinstance(spec, str) and spec.strip():
            block_dict, block_context = self._resolve_modal_target(spec.strip(), walker, context)
        else:
            self.logger.error(f"[NavigationHandler] zModal: missing/invalid target ({spec!r})")
            return None

        if not block_dict:
            self.logger.error("[NavigationHandler] zModal: could not resolve modal content")
            return None

        # Phase 2 (the %modal reel) reads these; staged now so the frame shape
        # is stable. Scoped to the detour: set before, cleared after.
        if isinstance(params, dict) and params:
            walker.session["_zmodal_params"] = params
        try:
            return self.zos.navigation.run_modal(
                block_dict, walker, source_key=source_key, context=block_context
            )
        finally:
            walker.session.pop("_zmodal_params", None)

    def _resolve_modal_target(
        self,
        target: str,
        walker: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> "tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]":
        """Resolve a string zModal target to ``(block_dict, zloom_context)``.

        ``$Block`` / bare name → same-file (the zDelta resolution chain, incl.
        the zUI.<name> auto-discovery fallback). ``@.zPath`` → cross-file (the
        zAlpha path grammar). Either way the host file's root zSpool bindings
        are pre-woven so the modal renders data exactly like a page would.
        """
        if target.startswith(zpath.SIGIL_WORKSPACE):
            # Cross-file: last segment = block, rest = file (zPath grammar SSOT).
            block_name, file_path = self.zos.navigation.linking.resolver.extract_block_from_path(target)
            raw_zFile = walker.loader.handle(file_path)
            if not isinstance(raw_zFile, dict):
                self.logger.error(f"[NavigationHandler] zModal: failed to load {file_path}")
                return None, None
            block_dict = self._resolve_delta_target_block(block_name, raw_zFile, file_path, walker)
        else:
            # Same-file: strip the $ marker, resolve in the current file.
            block_name = target.lstrip("$%")
            current_zVaFile = self._current_modal_vafile(walker, context)
            if not current_zVaFile:
                self.logger.error("[NavigationHandler] zModal: no current zVaFile to resolve against")
                return None, None
            raw_zFile = walker.loader.handle(current_zVaFile)
            if not isinstance(raw_zFile, dict):
                self.logger.error(f"[NavigationHandler] zModal: failed to load {current_zVaFile}")
                return None, None
            block_dict = self._resolve_delta_target_block(block_name, raw_zFile, current_zVaFile, walker)

        if not block_dict:
            return None, None

        # Weave: bind the host file's root zSpool + expand loops before the run
        # (the SAME seam every navigation landing uses). zLoom stays read-only.
        try:
            block_context = self.zos.zloom.prepare_block_render(raw_zFile, block_dict)
        except Exception as err:  # pylint: disable=broad-except
            self.logger.framework.debug(f"[NavigationHandler] zModal weave skipped: {err}")
            block_context = None
        return block_dict, block_context

    def _current_modal_vafile(
        self, walker: Any, context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Current host file for a same-file modal target.

        Resolution order: bridge dispatch payload first (the CLIENT's page
        identity — on a routed Bifrost page the server session's zVaFile still
        points at the spark home, so a bare $Block would resolve against the
        wrong file), then zDash panel stamp, then session/zSpark route
        (zDelta's classic order).
        """
        ws_data = (context or {}).get("websocket_data") or {}
        ws_zVaFile = ws_data.get("zVaFile")
        if ws_zVaFile:
            ws_zVaFolder = ws_data.get("zVaFolder")
            if ws_zVaFolder and not str(ws_zVaFile).startswith("@"):
                return f"{ws_zVaFolder}.{ws_zVaFile}"
            return ws_zVaFile
        panel_zVaFile = walker.session.get("_panel_zVaFile")
        if panel_zVaFile:
            return panel_zVaFile
        zVaFile = walker.session.get("zVaFile") or walker.zSpark_obj.get("zVaFile")
        if not zVaFile:
            return None
        zVaFolder = walker.session.get("zVaFolder") or walker.zSpark_obj.get("zVaFolder")
        if zVaFolder and not zVaFile.startswith("@"):
            return f"{zVaFolder}.{zVaFile}"
        return zVaFile

    # ========================================================================
    # PRIVATE HELPERS - zDelta Resolution
    # ========================================================================

    def _resolve_delta_target_block(
        self,
        target_block_name: str,
        raw_zFile: Dict[str, Any],
        current_zVaFile: str,
        walker: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve target block for zDelta navigation with fallback.
        
        FALLBACK CHAIN:
        1. Try finding block in current file
        2. If not found, try loading {blockName}.yaml from same directory
        
        Args:
            target_block_name: Name of target block
            raw_zFile: Current UI file content
            current_zVaFile: Current zVaFile path
            walker: Walker instance (for loader access)
        
        Returns:
            Target block dict, or None if not found
        
        Example:
            # Block in current file
            block = _resolve_delta_target_block("Settings", raw_file, current_file, walker)
            
            # Block in separate file (auto-discovered)
            block = _resolve_delta_target_block("About", raw_file, current_file, walker)
        """
        # Dotted path: descend into nested sections (e.g. "Edit_Profile.Change_Photo").
        # Tolerates modifier-decorated keys (e.g. Edit_Profile^) at each level so a
        # delegate target can point at a modified block without restating the modifier.
        if "." in target_block_name:
            descended = self._descend_dotted_block(target_block_name, raw_zFile)
            if descended is not None:
                self.logger.framework.debug(
                    f"[NavigationHandler] Resolved dotted target '{target_block_name}' via descent"
                )
                return descended
            self.logger.framework.debug(
                f"[NavigationHandler] Dotted target '{target_block_name}' not found via descent"
            )

        # Try current file first
        if target_block_name in raw_zFile:
            self.logger.framework.debug(
                f"[NavigationHandler] zDelta: Block '{target_block_name}' found in current file"
            )
            return raw_zFile[target_block_name]

        # FALLBACK: Try loading zUI.{blockName}.yaml from same directory
        fallback_zPath = self._construct_fallback_zpath(target_block_name, current_zVaFile)

        self.logger.framework.debug(
            f"[NavigationHandler] zDelta: Block '{target_block_name}' not in current file, "
            f"trying fallback zPath: {fallback_zPath}"
        )

        # Try loading the fallback file
        try:
            fallback_zFile = walker.loader.handle(fallback_zPath)
        except Exception as e:
            self.logger.debug(f"[NavigationHandler] zDelta: Fallback failed: {e}")
            fallback_zFile = None

        if fallback_zFile and isinstance(fallback_zFile, dict):
            # SUCCESS: Fallback file loaded
            self.logger.info(
                f"[NavigationHandler] [ok] zDelta: Auto-discovered block '{target_block_name}' "
                f"from separate file: {fallback_zPath}"
            )
            return fallback_zFile
        else:
            # FAILED: Neither current file nor fallback file has the block
            self.logger.error(
                f"[NavigationHandler] Block '{target_block_name}' not found:\n"
                f"  - Not in current file: {current_zVaFile}\n"
                f"  - Fallback zPath not found: {fallback_zPath}"
            )
            return None

    def _descend_dotted_block(
        self,
        dotted_name: str,
        raw_zFile: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve a dotted target path by descending nested blocks.

        Each segment matches a dict key at the current level. Modifier-prefixed
        keys (^/~) and *-menu keys are tolerated: a segment "Edit_Profile" will
        match a key "^Edit_Profile". Returns the resolved block dict, or None.

        Example:
            _descend_dotted_block("Edit_Profile.Change_Photo", raw_zFile)
            # → raw_zFile["^Edit_Profile"]["Change_Photo"]
        """
        node: Any = raw_zFile
        for part in dotted_name.split("."):
            if not isinstance(node, dict):
                return None
            if part in node:
                node = node[part]
                continue
            # Tolerate modifier-prefixed / *-suffixed sibling keys
            matched = None
            for key, val in node.items():
                if isinstance(key, str) and key.lstrip("^~").rstrip("*") == part:
                    matched = val
                    break
            if matched is None:
                return None
            node = matched
        return node if isinstance(node, dict) else None

    def _construct_fallback_zpath(
        self,
        target_block_name: str,
        current_zVaFile: str
    ) -> str:
        """
        Construct fallback zPath for zDelta auto-discovery.
        
        File naming: zUI.{blockName}.yaml -> zPath = "@.zViews.zUI.{blockName}"
        
        Args:
            target_block_name: Name of target block
            current_zVaFile: Current zVaFile path
        
        Returns:
            Fallback zPath string
        
        Example:
            current = "@.zViews.zUI.index" -> fallback = "@.zViews.zUI.zAbout"
            current = "@.zViews.zUI.Settings" -> fallback = "@.zViews.zUI.Profile"
        """
        if current_zVaFile.startswith(zpath.SIGIL_WORKSPACE):
            # Swap the trailing block for the target, via the grammar SSOT.
            parts = zpath.split(current_zVaFile)
            return zpath.join(parts.symbol, *parts.segments[:-1], target_block_name)
        else:
            # No current zPath - construct the default views-folder fallback.
            return zpath.join(zpath.SIGIL_WORKSPACE, "zViews", "zUI", target_block_name)

    # ========================================================================
    # PRIVATE HELPERS - Validation & Display
    # ========================================================================

    def _check_walker(self, walker: Optional[Any], command_name: str) -> bool:
        """
        Validate walker instance for navigation commands.
        
        Args:
            walker: Walker instance to validate (can be None)
            command_name: Name of command requiring walker (for error message)
        
        Returns:
            True if walker is valid (not None), False otherwise
        
        Example:
            if not self._check_walker(walker, "zLink"):
                return None
        
        Notes:
            - Logs warning if walker is None
            - Calling code should return None if validation fails
        """
        if not walker:
            self.logger.warning(f"[NavigationHandler] {command_name} requires walker instance")
            return False
        return True

    def _display_handler(self, label: str) -> None:
        """
        Display handler label with consistent styling.
        
        Args:
            label: Handler label to display (from dispatch_constants)
        
        Notes:
            - Uses zDisplay.zDeclare for consistent styling
            - Style is always "single" for handler labels
            - Color comes from parent dispatch instance (via self.display)
        """
        if self.display:
            # Get color from display instance (set by parent dispatcher)
            color = getattr(self.display, 'mycolor', None)
            if color:
                self.display.zDeclare(
                    label,
                    color=color,
                    indent=_DEFAULT_INDENT_HANDLER,
                    style=_DEFAULT_STYLE_SINGLE
                )
