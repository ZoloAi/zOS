# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/expansion/expander_organizational.py

"""
Organizational Handler Module for zDispatch Subsystem.

This module provides the OrganizationalHandler class, which handles nested
organizational structures (dicts/lists with no direct actions). It recursively
processes nested content and integrates with ShorthandExpander.

Extracted from dispatch_launcher.py as part of Phase 3 refactoring.
This module depends on ShorthandExpander and CommandRouter (circular dependency
resolved via composition).

Detection Rules:
    A dict is considered organizational if:
    1. All content keys are nested (dicts or lists)
    2. It's NOT a subsystem call
    3. It's NOT a CRUD call

Special Cases:
    - Implicit sequences: All keys are UI events → process sequentially
    - Mixed structures: Some UI events + organizational keys → recurse

Usage Example:
    handler = OrganizationalHandler(expander, logger)
    
    # Check and handle organizational structure
    result = handler.handle(
        {'Header': {'zH1': {...}}, 'Body': {'zText': {...}}},
        context={},
        walker=None,
        command_router=router
    )

Integration:
    - ShorthandExpander: Nested shorthand expansion
    - CommandRouter: Recursive command execution (circular dependency)

Thread Safety:
    - Modifies walker.session if walker provided (not thread-safe per walker)
    - Safe for concurrent walkers
"""

from zOS import Any, Dict, List, Optional

from zOS.L1_Foundation.a_zConfig.zConfig_modules import SESSION_KEY_ZMODE

# zForce SSOT — the ONE classifier that decides what a return MEANS. A nested
# zStride return carrying a navigation vector must bubble up to the nav-aware
# engine; this handler used to re-sniff the str/dict vector set inline (4 copies,
# blind to the same drift zForce was built to kill). Now it consults force.vector
# exactly like execute_loop does, so the two readers are literally one source.
from zOS.L3_Abstraction.l_zEngine import sense_force

# zStride passivity verdict — the ONE classifier (shared with the zGuard engine
# and the CommandLauncher hoist). Never re-spell "what is conditional" here.
from zOS.L2_Handling.h_zNavigation.navigation_modules.breadcrumb_classify import (
    is_passive_zStride,
)

from ..dispatch_constants import EVENT_BINDING_KEYS, KEY_ZDELEGATE, MODE_BIFROST, MODE_ZCLI

# Keys excluded from organizational content: pure metadata + declarative event
# bindings (onChange/onClick/...). Event bindings attach a handler to a sibling
# UI element and are consumed declaratively (zAPI scan, Bifrost enrichment,
# client) — they must NEVER be recursed into or executed during render.
_METADATA_KEYS = {'_zClass', '_zStyle', '_zHTML', '_zId', 'zScripts', 'zId'} | set(EVENT_BINDING_KEYS)

class OrganizationalHandler:
    """
    Handles nested organizational structures (recursion).
    
    This class detects and processes organizational structures, which are
    dicts with nested dicts/lists that don't directly execute actions.
    
    Attributes:
        expander: ShorthandExpander instance for nested expansion
        logger: Logger instance for debug output
    
    Methods:
        handle(): Main entry point - detect and process organizational structures
        is_organizational(): Check if dict is organizational
        detect_implicit_sequence(): Check if all keys are UI events
        
        Private:
        _recurse_nested_structure(): Recursively process nested keys
        _process_nested_key(): Process individual nested key
        _is_all_nested(): Check if all content keys are nested
    
    Example:
        handler = OrganizationalHandler(expander, logger)
        
        # Organizational structure
        result = handler.handle(
            {'Page_Header': {...}, 'Page_Body': {...}},
            context,
            walker,
            command_router
        )
    """

    def __init__(self, expander: Any, logger: Any) -> None:
        """
        Initialize organizational handler.
        
        Args:
            expander: ShorthandExpander instance for nested expansion
            logger: Logger instance for debug output
        
        Example:
            handler = OrganizationalHandler(expander, logger)
        """
        self.expander = expander
        self.logger = logger

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def handle(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any],
        command_router: Any
    ) -> Optional[Any]:
        """
        Handle organizational structure (nested dicts/lists with no direct actions).
        
        If dict has only nested dicts/lists, it's organizational - recurse into it
        rather than treating as implicit wizard. Enables flexible YAML organization.
        
        Args:
            zHorizontal: Dict command
            context: Optional context dict
            walker: Optional walker instance
            command_router: CommandRouter instance for recursive execution
        
        Returns:
            Recursion result, or None if not organizational structure
        
        Example:
            result = handler.handle(
                {'Header': {...}, 'Body': {...}},
                context,
                walker,
                command_router
            )
        
        Notes:
            - Detects implicit sequences (all UI events)
            - Recursively processes nested structures
            - Integrates with ShorthandExpander for nested expansion
        """
        # Get ALL content keys, excluding metadata + declarative event bindings.
        content_keys = [k for k in zHorizontal.keys() if k not in _METADATA_KEYS]

        # Check if organizational (all nested)
        if not self._is_all_nested(zHorizontal, content_keys):
            return None

        # Process keys in their original order to maintain correct buffering sequence
        # This ensures injection order matches processing order
        # CRITICAL: Check for _ prefix FIRST before checking zDisplay
        # Organizational containers like _Visual_Caption may contain expanded zDisplay,
        # but they should still be treated as organizational, not UI events

        # Track what we find for logging
        ui_event_count = 0
        org_key_count = 0
        input_event_count = 0
        processed_any = False

        # ═══════════════════════════════════════════════════════════════
        # TERMINAL MODE CHECK (2026-01-28)
        # Detect mode to skip terminal-suppressed content (_prefixed keys)
        # ═══════════════════════════════════════════════════════════════
        is_terminal_mode = True  # Default to zCLI
        if walker and hasattr(walker, 'session'):
            mode = walker.session.get(SESSION_KEY_ZMODE, MODE_ZCLI)
            is_terminal_mode = mode != MODE_BIFROST
        elif context and SESSION_KEY_ZMODE in context:
            is_terminal_mode = context.get(SESSION_KEY_ZMODE) != MODE_BIFROST

        # zFlat passive render: when a host renders this block inert, input events
        # must NOT be deferred to a wizard (there is none) — they render their
        # visual affordance via the event map's flat wrappers like any other event.
        is_flat = False
        try:
            is_flat = bool(command_router.zos.session.get('_zflat'))
        except Exception:  # noqa: BLE001
            is_flat = False

        # ═══════════════════════════════════════════════════════════════
        # zDelegate CLI CARRIER HARVEST (2026-05-29)
        # A delegating carrier (zBtn with action: {zDelegate: $X}) is a
        # Bifrost DOM click — but in CLI a standalone button is dropped
        # (skipped below as an input event). To keep zDelegate a FIRST-CLASS
        # dual-mode SSOT (not _bifrost-only), harvest such carriers here and
        # fold them into this block's *-actions menu (rendered last, no inline
        # pause). Selecting the harvested label dispatches its {zDelegate: …}
        # through the same handler the Bifrost click routes to.
        # ═══════════════════════════════════════════════════════════════
        delegate_map = self._harvest_delegates(zHorizontal) if is_terminal_mode else {}

        # ── ! GATE (SSOT) ───────────────────────────────────────────────────
        # A block carrying a gate key (suffix '!') must run through the ONE flow
        # engine (zWizard.execute_loop) so the gate — and any inputs it guards —
        # are enforced uniformly, exactly like nested *-menus delegate below.
        # Without this, the per-key loop reaches the gate's input event and the
        # zDisplay branch SKIPS it ("let the wizard handle it"), but no wizard
        # runs in a nested/non-wizard scope — so the button never renders and the
        # gate is silently ignored. Delegating to execute_loop makes the engine
        # render display keys, block on the gate's input, and only advance past
        # the gate on a truthy pass — identical top-level, nested, or as a menu
        # option, across zCLI/zTerminal/Bifrost.
        if (is_terminal_mode and not is_flat and not delegate_map
                and walker is not None and hasattr(walker, 'execute_loop')
                and any(isinstance(k, str) and k.endswith('!') for k in content_keys)):
            self.logger.framework.debug(
                "[OrganizationalHandler] Gate key detected → delegating block to "
                "execute_loop (SSOT flow engine)"
            )
            return walker.execute_loop(
                items_dict=zHorizontal,
                navigation_callbacks=walker._create_navigation_callbacks(),  # pylint: disable=protected-access
                start_key=content_keys[0],
            )

        for key in content_keys:
            val = zHorizontal[key]

            # Check for organizational container FIRST (before zDisplay check)
            if key.startswith('_'):
                # ═══════════════════════════════════════════════════════════════
                # TERMINAL SUPPRESSION: Skip _ prefixed keys in zCLI mode
                # These are Bifrost-only visual elements (e.g. _Visual_Progression)
                # ═══════════════════════════════════════════════════════════════
                if is_terminal_mode:
                    self.logger.framework.debug(
                        f"[OrganizationalHandler] Skipping terminal-suppressed key '{key}' (zCLI mode)"
                    )
                    continue

                # Bifrost mode: Organizational container (not metadata)
                org_key_count += 1
                self.logger.framework.debug(
                    f"[OrganizationalHandler] Processing organizational container '{key}' in order"
                )
                if command_router:
                    result = self._process_nested_key(key, val, context, walker, command_router)
                    processed_any = True

                    # Surface a navigation vector up to the nav-aware engine (SSOT: zForce)
                    if sense_force(result).has_vector:
                        return result

            elif isinstance(val, dict) and 'zDisplay' in val:
                # UI event with explicit zDisplay wrapper
                ui_event_count += 1

                # Input event handling. Historically these were ALWAYS skipped
                # ("let the wizard handle it") — but no wizard ever iterates the
                # inside of an organizational container, so in a MIXED container
                # (inputs alongside display keys) a zBtn was silently dropped:
                # the same key at walker top level prompted/navigated, nested in
                # a Card it vanished — an SSOT violation across zCLI/zTerminal.
                #
                # Resolution by container shape:
                #   all-input container → keep skipping; routed below as an
                #     implicit wizard (line ~360), which DOES handle them.
                #   zDelegate carriers  → keep skipping; harvested into *-menus.
                #   mixed + terminal    → execute inline, in document order, and
                #     propagate navigation results like any other UI event.
                #   mixed + Bifrost     → keep skipping; the client renders the
                #     button declaratively from the chunk (no double render).
                event_type = val.get('zDisplay', {}).get('event', '')
                is_input_event = event_type in ('read_string', 'read_password', 'selection', 'button')

                if is_input_event and not is_flat:
                    execute_inline = (
                        is_terminal_mode and not delegate_map
                        and not self._all_inline_inputs(zHorizontal, content_keys)
                    )
                    if not execute_inline:
                        input_event_count += 1
                        self.logger.framework.debug(
                            f"[OrganizationalHandler] Skipping input event '{key}' "
                            f"(event: {event_type}) - will be handled by wizard"
                        )
                        # Don't execute, let wizard handle it
                        continue
                    self.logger.framework.debug(
                        f"[OrganizationalHandler] Executing inline input event '{key}' "
                        f"(event: {event_type}) - mixed container, no wizard owns it"
                    )

                # zStride: a non-input display leaf is passive structure the nested
                # zWalk touched — record it pre-order. Inputs are conditional
                # (commit-on-success) and are recorded by the wizard/execute_loop.
                if not is_input_event:
                    self._zStride_passive(key, walker)

                self.logger.framework.debug(
                    f"[OrganizationalHandler] Processing UI event '{key}' in order"
                )
                if command_router:
                    # Process single UI event (not as a list)
                    result = command_router._launch_dict(val, context, walker)  # pylint: disable=protected-access
                    processed_any = True

                    # Surface a navigation vector up to the nav-aware engine (SSOT: zForce)
                    if sense_force(result).has_vector:
                        return result

            else:
                # Non-UI, non-organizational key - treat as organizational
                org_key_count += 1

                # ── * modifier: list → navigation menu ──────────────────────
                # key* (no ~): menu WITH Back   |   ~key* : menu WITHOUT Back
                if key.endswith('*') and isinstance(val, list) and command_router:
                    processed_any = True
                    if not is_terminal_mode:
                        # Bifrost: a block-level navbar (~zNavBar*) is PASSIVE chrome —
                        # message_walker renders it as a navbar_inline event. Do NOT
                        # launch its items: _launch_list would dispatch the first item's
                        # zLink, which navigation_linking defers to _zPendingNavigate,
                        # firing a phantom navigate_back redirect on page load. Other
                        # *-menus still render declaratively.
                        if key.startswith('~zNavBar'):
                            return None
                        # Bifrost: render menu declaratively then stop
                        result = self._process_nested_key(key, val, context, walker, command_router)
                        return result

                    # CLI SSOT: a nested *-menu must behave IDENTICALLY to a
                    # walker-level one — the pick is a STARTING LINE, then the flow
                    # falls through the siblings until a gate ('!') or a nav signal.
                    # Rather than re-derive that here, delegate the parent block to
                    # the ONE flow engine (zWizard.execute_loop) starting at the menu
                    # key: its native menu key-jump runs the menu, then iterates the
                    # remaining siblings exactly like the top level (jump, ^ crumbs-
                    # rewind via trail, anchor-back, gates — all inherited, zero dup).
                    # zDelegate carrier menus (Account-style action bars) can't ride
                    # the executor's key-jump — carriers aren't real keys — so those
                    # keep the dedicated MenuModifier path.
                    if not delegate_map and walker is not None and hasattr(walker, 'execute_loop'):
                        return walker.execute_loop(
                            items_dict=zHorizontal,
                            navigation_callbacks=walker._create_navigation_callbacks(),  # pylint: disable=protected-access
                            start_key=key,
                        )

                    # Carrier menus: invoke the real MenuModifier so * behaves
                    # identically whether nested or at walker level. Fold any
                    # harvested zDelegate carriers in as extra options.
                    menu_options = list(val)
                    for lbl in delegate_map:
                        if lbl not in menu_options:
                            menu_options.append(lbl)
                    result = self._process_star_menu_cli(
                        key, menu_options, zHorizontal, context, walker, command_router,
                        delegate_map=delegate_map,
                    )
                    return result  # menu owns the rest of the flow
                # ─────────────────────────────────────────────────────────────

                # zStride: a passive organizational container — record on ENTRY,
                # before descending into its children (parent-before-child).
                self._zStride_passive(key, walker)

                self.logger.framework.debug(
                    f"[OrganizationalHandler] Processing non-UI organizational key '{key}' in order"
                )
                if command_router:
                    result = self._process_nested_key(key, val, context, walker, command_router)
                    processed_any = True

                    # Surface a navigation vector up to the nav-aware engine (SSOT: zForce)
                    if sense_force(result).has_vector:
                        return result

        self.logger.framework.debug(
            f"[OrganizationalHandler] Processed {ui_event_count} UI events and "
            f"{org_key_count} organizational containers in original order"
        )

        # If we processed anything, return None (success)
        if processed_any:
            return None

        # Check if this is a wizard input container (all keys are input events)
        # If so, treat it as an IMPLICIT WIZARD and route to wizard subsystem
        if input_event_count > 0 and input_event_count == len(content_keys):
            self.logger.framework.debug(
                f"[OrganizationalHandler] Wizard input container detected "
                f"({input_event_count} input events) - routing as implicit wizard"
            )
            # Route as implicit wizard for sequential execution with if conditions
            if command_router and hasattr(command_router, 'wizard_detector'):
                # Mark as implicit wizard and route to wizard subsystem
                self.logger.framework.debug(
                    "[OrganizationalHandler] Routing wizard input container "
                    "to wizard subsystem"
                )
                return command_router._handle_implicit_wizard(zHorizontal, walker)  # pylint: disable=protected-access
            # Fallback: return None if no wizard detector available
            return None

        # Recurse into organizational structure
        self.logger.framework.debug(
            f"[OrganizationalHandler] Organizational structure detected ({len(content_keys)} keys)"
        )

        return self._recurse_nested_structure(zHorizontal, content_keys, context, walker, command_router)

    def is_organizational(
        self,
        zHorizontal: Dict[str, Any],
        is_subsystem_call: bool,
        is_crud_call: bool
    ) -> bool:
        """
        Check if dict is organizational (all nested dicts/lists).
        
        Args:
            zHorizontal: Dict to check
            is_subsystem_call: Whether this is a subsystem call
            is_crud_call: Whether this is a CRUD call
        
        Returns:
            True if organizational, False otherwise
        
        Example:
            is_org = handler.is_organizational(
                {'Header': {...}, 'Body': {...}},
                is_subsystem_call=False,
                is_crud_call=False
            )
            # Returns: True
        """
        # Get ALL content keys, excluding metadata + declarative event bindings.
        content_keys = [k for k in zHorizontal.keys() if k not in _METADATA_KEYS]

        # Not organizational if subsystem or CRUD call
        if is_subsystem_call or is_crud_call:
            return False

        # Not organizational if no content keys
        if not content_keys:
            return False

        # Check if all nested
        return self._is_all_nested(zHorizontal, content_keys)

    def detect_implicit_sequence(
        self,
        zHorizontal: Dict[str, Any],
        content_keys: List[str]
    ) -> bool:
        """
        Detect if all keys are UI events (implicit sequence).
        
        Args:
            zHorizontal: Dict to check
            content_keys: List of content keys
        
        Returns:
            True if all keys are UI events, False otherwise
        
        Example:
            is_seq = handler.detect_implicit_sequence(
                {'zH1': {...}, 'zText': {...}},
                ['zH1', 'zText']
            )
            # Returns: True
        """
        if len(content_keys) < 2:
            return False

        # Check if all keys are UI events (after expansion)
        ui_event_count = 0
        for key in content_keys:
            val = zHorizontal[key]

            # Check if already expanded (has zDisplay)
            if isinstance(val, dict) and 'zDisplay' in val:
                ui_event_count += 1

        return ui_event_count == len(content_keys) and ui_event_count >= 2

    # ========================================================================
    # PRIVATE - Recursion Logic
    # ========================================================================

    def _zStride_passive(self, key: str, walker: Optional[Any]) -> None:
        """Record ONE pre-order zStride for passive structure the nested zWalk descends.

        OrganizationalHandler is the NESTED zWalk: it walks a container's inner
        keys that the top-level ``execute_loop`` never iterates. For trail SSOT
        those passive keys must zStride exactly like top-level structure — on
        ENTRY (before descending) so the trail reads parent-before-child — making
        zCLI record EVERYTHING the walk touches, at any depth.

        Boundaries (mirror the engine's split, commit-on-success for the rest):
          - **terminal only**: Bifrost records via the click-ancestry chain, not
            the walk, so recording here would pollute its chunk-render trail.
          - **passive only**: conditional keys (gates ``!``, menus ``*``, crumbs-
            rewind ``^``/anchor ``~``, inputs, nav) are NOT stamped here — they are
            delegated to ``execute_loop`` (commit-on-success), so the ``!`` gate
            keeps its post path and never leaves a false-positive crumb.
          - **zCrumbs skipped**: the breadcrumb display directive is not a
            navigation key (mirrors zWalker.on_continue).
        """
        if walker is None:
            return
        nav = getattr(walker, 'navigation', None)
        if nav is None or not hasattr(nav, 'record_zStride'):
            return
        try:
            sess = getattr(walker, 'session', None) or {}
            if sess.get(SESSION_KEY_ZMODE, MODE_ZCLI) == MODE_BIFROST:
                return
        except Exception:  # noqa: BLE001
            return
        # Conditional keys (modifiers, zCrumbs) commit on success elsewhere — the
        # ONE classifier decides. The caller already filtered inputs, so a
        # display leaf here is passive (no value/event needed).
        if not is_passive_zStride(key):
            return
        nav.record_zStride(key, walker=walker)

    def _harvest_delegates(self, zHorizontal: Any) -> Dict[str, Any]:
        """
        Recursively collect zDelegate carriers in a block (CLI only).

        A carrier is any node carrying ``action: {zDelegate: …}`` — whether
        still raw (zBtn) or already expanded (zDisplay button). Returns a map
        of {carrier label → action dict} so the *-menu can surface each as a
        selectable entry that dispatches the same {zDelegate: …} the Bifrost
        click routes to. Render-safe: carriers stay out of inline flow (a lone
        button is skipped in CLI), they only appear in the end-of-block menu.

        v1 only MERGES into an existing *-menu in this block; blocks without a
        menu don't auto-synthesize one yet (deferred).
        """
        found: Dict[str, Any] = {}

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                action = node.get('action')
                if isinstance(action, dict) and KEY_ZDELEGATE in action:
                    label = node.get('label') or node.get('zIcon') or str(action[KEY_ZDELEGATE])
                    found[str(label)] = action
                for val in node.values():
                    _walk(val)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(zHorizontal)
        return found

    def _process_star_menu_cli(
        self,
        key: str,
        options: list,
        parent_dict: dict,
        context: Any,
        walker: Any,
        command_router: Any,
        delegate_map: Optional[dict] = None,
    ) -> Any:
        """
        Invoke the MenuModifier for a key* list in CLI mode so that
        nested sub-menus behave identically to top-level walker menus.

        * (no ~) → allow_back=True   (Back injected automatically)
        ~key*    → allow_back=False  (anchor, no Back)

        After selection, dispatches the matching sibling key from parent_dict.
        Harvested zDelegate carriers (delegate_map: label → action dict) are
        dispatched through the launcher so the CLI pick routes to the same
        handler the Bifrost click does. Re-shows the menu if a child returns
        'zBack'.
        """
        delegate_map = delegate_map or {}
        is_anchor = key.startswith('~')
        modifiers = (['~'] if is_anchor else []) + ['*']
        menu_modifier = command_router.dispatch.modifiers.menu_modifier

        while True:
            selected = menu_modifier.process(modifiers, key, options, walker)

            if selected == 'zBack':
                return 'zBack'

            # Harvested zDelegate carrier picked → dispatch its action dict.
            if isinstance(selected, str) and selected in delegate_map:
                action = delegate_map[selected]
                self.logger.framework.debug(
                    f"[OrganizationalHandler] *-menu: delegate carrier '{selected}' → {action}"
                )
                child_result = command_router.dispatch.launcher.launch(action, context, walker)
                # Delegate is activation-only: re-show this menu after it runs.
                if child_result == 'zBack':
                    continue
                continue

            if isinstance(selected, str):
                # Carrier/action-menu path: each option is an independent action —
                # run ONLY the chosen sibling (no fall-through). Content menus that
                # need start-line fall-through are routed through the SSOT executor
                # (walker.execute_loop, start_key=menu_key) by the caller, so the
                # fall-through logic lives in exactly ONE place (the zWizard engine).
                for sibling_key, sibling_val in parent_dict.items():
                    bare = sibling_key.lstrip('~').rstrip('*^')
                    if bare == selected:
                        child_result = self._process_nested_key(
                            sibling_key, sibling_val, context, walker, command_router
                        )
                        if child_result == 'zBack':
                            # zBack from child → re-show this sub-menu (parent
                            # absorbs the signal and loops). A `<key>^` sibling
                            # returns {'zCrumb': ...}, a bulk-back that must
                            # propagate UP, not loop here — so it falls through.
                            break
                        return child_result
                else:
                    self.logger.framework.debug(
                        f"[OrganizationalHandler] *-menu: no sibling key for '{selected}'"
                    )
                    return None

    def _all_inline_inputs(
        self,
        zHorizontal: Dict[str, Any],
        content_keys: List[str]
    ) -> bool:
        """
        True when EVERY direct child is an expanded input event (button/
        selection/read_*) — a wizard input container, which the implicit-wizard
        route below handles. Mixed containers return False, so their inputs
        execute inline (no wizard ever iterates a container's inner keys).
        """
        if not content_keys:
            return False
        for key in content_keys:
            val = zHorizontal.get(key)
            if not (isinstance(val, dict) and isinstance(val.get('zDisplay'), dict)
                    and val['zDisplay'].get('event') in (
                        'read_string', 'read_password', 'selection', 'button')):
                return False
        return True

    def _is_all_nested(
        self,
        zHorizontal: Dict[str, Any],
        content_keys: List[str]
    ) -> bool:
        """
        Check if all content keys are nested (dicts or lists).
        
        Args:
            zHorizontal: Dict to check
            content_keys: List of content keys
        
        Returns:
            True if all nested, False otherwise
        """
        return all(
            isinstance(zHorizontal[k], (dict, list))
            for k in content_keys
        )

    def _recurse_nested_structure(
        self,
        zHorizontal: Dict[str, Any],
        content_keys: List[str],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any],
        command_router: Any
    ) -> Optional[Any]:
        """
        Recursively process nested organizational structure.
        
        Args:
            zHorizontal: Dict with nested structure
            content_keys: List of content keys
            context: Optional context dict
            walker: Optional walker instance
            command_router: CommandRouter for recursive execution
        
        Returns:
            Last recursion result, or None
        
        Notes:
            - Processes each nested key individually
            - Checks for navigation signals (zBack, exit, etc.)
            - Stops on navigation signal
            - Skips terminal-suppressed keys (_prefix) in zCLI mode
        """
        result = None

        # Detect mode for terminal suppression
        is_terminal_mode = True  # Default to zCLI
        if walker and hasattr(walker, 'session'):
            mode = walker.session.get(SESSION_KEY_ZMODE, MODE_ZCLI)
            is_terminal_mode = mode != MODE_BIFROST
        elif context and SESSION_KEY_ZMODE in context:
            is_terminal_mode = context.get(SESSION_KEY_ZMODE) != MODE_BIFROST

        for key in content_keys:
            # Skip terminal-suppressed keys in zCLI mode
            if is_terminal_mode and key.startswith('_'):
                self.logger.framework.debug(
                    f"[OrganizationalHandler] Skipping terminal-suppressed key '{key}' in _recurse_nested_structure"
                )
                continue

            value = zHorizontal[key]

            self.logger.framework.debug(
                f"[OrganizationalHandler] Processing nested key: {key} (type: {type(value).__name__})"
            )

            # * modifier on a list: navigation menu (same logic as handle())
            if key.endswith('*') and isinstance(value, (list,)) and command_router:
                if not is_terminal_mode:
                    # Block-level navbars (~zNavBar*) are passive chrome in Bifrost —
                    # rendered as navbar_inline by message_walker. Launching their items
                    # would dispatch the first item's zLink → phantom _zPendingNavigate
                    # redirect. Skip the launch; other *-menus render declaratively.
                    if key.startswith('~zNavBar'):
                        return None
                    result = self._process_nested_key(key, value, context, walker, command_router)
                    return result
                result = self._process_star_menu_cli(
                    key, value, zHorizontal, context, walker, command_router
                )
                return result

            # zStride: passive structure descended by the nested zWalk — record on entry.
            self._zStride_passive(key, walker)

            # Process nested content
            result = self._process_nested_key(key, value, context, walker, command_router)

            # Surface a navigation vector up to the nav-aware engine (SSOT: zForce —
            # str signals + {zLink|zDelta|zCrumb} dicts, the same union execute_loop reads)
            if sense_force(result).has_vector:
                return result

        return result

    def _process_nested_key(
        self,
        key: str,
        value: Any,
        context: Optional[Dict[str, Any]],
        walker: Optional[Any],
        command_router: Any
    ) -> Optional[Any]:
        """
        Process individual nested key (recursively).
        
        Args:
            key: Key name
            value: Key value (dict or list)
            context: Optional context dict
            walker: Optional walker instance
            command_router: CommandRouter for recursive execution
        
        Returns:
            Recursion result
        
        Notes:
            - Applies shorthand expansion if needed
            - Recursively launches dicts and lists
            - Supports 'if:' conditions on shorthands (wizard context)
        """
        # Apply shorthand expansion if dict
        # The 'if' parameter will be passed through to zDisplay wrapper
        # for the wizard to evaluate during sequential execution
        # ═══════════════════════════════════════════════════════════════════
        # KEY-LEVEL SHORTHAND EXPANSION (2026-01-29)
        # If the KEY itself is a UI element shorthand (zTerminal, zCrumbs, …),
        # wrap {key: value} before expansion so the expander sees the key.
        # SCALAR shorthands too: a UI-element key carrying a bare scalar value
        # (e.g. `zCrumbs: true`) must ALSO expand here — otherwise it skips the
        # expander, reaches the launcher as a bare bool/str (neither str/dict/
        # list), and renders nothing. The expander coerces such scalars to their
        # default dict form (zCrumbs: true → {show: session}).
        # ═══════════════════════════════════════════════════════════════════
        clean_key = key.split('__dup')[0] if '__dup' in key else key
        is_ui_key = bool(self.expander) and clean_key in self.expander.UI_ELEMENT_KEYS
        should_expand = bool(self.expander) and (
            isinstance(value, dict) or (is_ui_key and not isinstance(value, list))
        )
        if should_expand:
            # DEBUG: Log metadata before expansion (dict children only)
            if isinstance(value, dict) and (key.startswith('_Box_') or key.startswith('_Visual_')):
                has_style_before = '_zStyle' in value
                self.logger.framework.debug(
                    f"[OrganizationalHandler] 🎨 BEFORE expansion of {key}: "
                    f"_zStyle present = {has_style_before}, keys = {list(value.keys())}"
                )

            if is_ui_key:
                # Wrap key-value (dict OR scalar), expand, then extract result
                wrapped = {key: value}
                expanded, _ = self.expander.expand(wrapped, walker.session if walker else {}, False)
                # Get the expanded value (might be wrapped in zDisplay now)
                value = expanded.get(key, value)
                value_repr = list(value.keys()) if isinstance(value, dict) else type(value)
                self.logger.framework.debug(
                    f"[OrganizationalHandler] Expanded UI element shorthand '{key}' -> {value_repr}"
                )
            else:
                # Regular nested expansion (for non-UI element keys)
                value, _ = self.expander.expand(value, walker.session if walker else {}, False)

            # DEBUG: Log metadata after expansion (dict children only)
            if isinstance(value, dict) and (key.startswith('_Box_') or key.startswith('_Visual_')):
                has_style_after = '_zStyle' in value
                self.logger.framework.debug(
                    f"[OrganizationalHandler] 🎨 AFTER expansion of {key}: "
                    f"_zStyle present = {has_style_after}, keys = {list(value.keys())}"
                )

        # NOTE: 'if' conditions are NOT evaluated here during organizational preprocessing.
        # They are evaluated by the wizard during sequential execution when zHat is available.
        # The 'if' parameter passes through in the zDisplay wrapper for wizard handling.

        # Recursively process
        if isinstance(value, dict) and command_router:
            # Mark nested content to prevent wizards from triggering navigation
            nested_context = context.copy() if context else {}
            nested_context['_is_nested_in_org_container'] = True
            return command_router._launch_dict(value, nested_context, walker)  # pylint: disable=protected-access
        elif isinstance(value, list) and command_router:
            # Mark nested content to prevent wizards from triggering navigation
            nested_context = context.copy() if context else {}
            nested_context['_is_nested_in_org_container'] = True
            return command_router._launch_list(value, nested_context, walker)  # pylint: disable=protected-access

        return None
