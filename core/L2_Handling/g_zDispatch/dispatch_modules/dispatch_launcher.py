# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/dispatch_launcher.py

"""
Command Launcher for zDispatch Subsystem
=========================================

Central dispatcher routing commands to subsystems (zFunc, zNavigation, zWizard, zData, etc.).

Architecture:
    Two command pathways:
    1. String: "zFunc(...)", "zLink(...)", "zOpen(...)", "zWizard(...)", "zRead(...)"
    2. Dict: {"zFunc": ...}, {"zLink": ...}, {"zData": ...}, {"zDialog": ...}
    
    Flow: launch() → _launch_string() or _launch_dict() → subsystem handler

Mode Behavior:
    - zCLI: Plain strings return None, zWizard returns "zBack"
    - Bifrost: Plain strings resolve from zUI, zWizard returns actual result

Plugin Support: "&" prefix in zFunc commands (e.g., "zFunc(&my_plugin)")
CRUD Detection: Auto-routes generic CRUD dicts (action, model, table keys) to zData

Usage:
    launcher.launch("zFunc(calculate)")
    launcher.launch({"zRead": {"model": "users", "where": {"id": 1}}})
    launcher.launch({"action": "read", "model": "users"})  # Auto-detected CRUD
"""

from zOS import Any, Optional, Dict, Union, List

# Import ACTION_PLACEHOLDER from zConfig
from zOS.L1_Foundation.a_zConfig.zConfig_modules import ACTION_PLACEHOLDER, SESSION_KEY_ZMODE

# Import all dispatch constants from centralized location
from .dispatch_constants import (
    # Dict Keys - Subsystem Commands
    KEY_ZFUNC,
    KEY_ZLINK,
    KEY_ZALPHA,
    KEY_ZDELTA,
    KEY_ZMENU,
    KEY_ZDELEGATE,
    KEY_ZMODAL,
    KEY_ZWIZARD,
    KEY_ZREAD,
    KEY_ZDATA,
    KEY_ZDIALOG,
    KEY_ZDASH,
    KEY_ZFLAT,
    KEY_ZDISPLAY,
    KEY_ZLOGIN,
    KEY_ZLOGOUT,
    KEY_ZEXPORT,
    KEY_ZIMPORT,
    KEY_ZTRANSFER,
    KEY_ZVAR,
    KEY_ZLIST,
    KEY_ZPROGRESS,
    PROGRESS_ACTION_KEYS,
    # Event-binding keys (declarative — never executed inline)
    EVENT_BINDING_KEYS,
    # Dict Keys - Context & Session
    KEY_ZVAFILE,
    KEY_ZBLOCK,
    KEY_MESSAGE,
    KEY_ACTION,
    # Mode Values
    MODE_BIFROST,
    MODE_ZCLI,
    # Display Labels (INTERNAL)
    _LABEL_LAUNCHER,
    # Default Values (INTERNAL)
    _DEFAULT_ZBLOCK,
    _DEFAULT_INDENT_LAUNCHER,
    _DEFAULT_STYLE_SINGLE,
)

# zStride passivity verdict — the ONE classifier (shared with the zGuard engine
# and the OrganizationalHandler nested walk). Never re-spell "what is conditional".
from zOS.L2_Handling.h_zNavigation.navigation_modules.breadcrumb_classify import (
    is_passive_zStride,
)

# Import new domain-based architecture modules
from .handlers.handler_auth import AuthHandler
from .handlers.handler_crud import CRUDHandler
from .handlers.handler_navigation import NavigationHandler
from .handlers.handler_subsystems import SubsystemRouter
from .shorthand_expander import ShorthandExpander
from .commands.command_wizard_detector import WizardDetector
from .expansion.expander_organizational import OrganizationalHandler
from .commands.command_list import ListCommandHandler
from .commands.command_string_parser import StringCommandHandler
from .handlers.handler_routing import RoutingHandlers
from .handlers.handler_wizard_data import WizardDataHandlers
from .handlers.handler_export import ExportHandler
from .handlers.handler_import import ImportHandler
from .transfer import TransferEngine, TransferHandler


class CommandLauncher(RoutingHandlers, WizardDataHandlers):
    """
    Central command launcher for zDispatch subsystem.
    
    Routes string and dict commands to appropriate subsystem handlers, with mode-aware
    behavior for zCLI vs. Bifrost execution environments.
    
    Attributes:
        dispatch: Parent zDispatch instance
        zos: zOS framework instance
        logger: Logger instance from zOS
        display: zDisplay instance for UI output
    
    Methods:
        launch(): Main entry point for command routing (type detection)
        _launch_string(): Route string-based commands (zFunc(), zLink(), etc.)
        _launch_dict(): Route dict-based commands ({zFunc:, zLink:, etc.})
        _handle_wizard_string(): Parse and execute wizard from string
        _handle_wizard_dict(): Execute wizard from dict
        _handle_read_string(): Handle zRead string -> zData
        _handle_read_dict(): Handle zRead dict -> zData
        _handle_data_dict(): Handle zData dict -> zData
        _handle_crud_dict(): Handle generic CRUD dict -> zData
        
        Helper methods (DRY):
        _display_handler(): Display handler label with consistent styling
        _log_detected(): Log detected command with consistent format
    
    Integration:
        - zConfig: Uses ACTION_PLACEHOLDER constant
        - zDisplay: UI output via zDeclare() and text()
        - zSession: Mode detection via context dict
        - Forward dependencies: 8 subsystems (see module docstring)
    """

    # Class-level type declarations
    dispatch: Any  # zDispatch instance
    zos: Any  # zOS framework instance
    logger: Any  # Logger instance
    display: Any  # zDisplay instance

    def __init__(self, dispatch: Any) -> None:
        """
        Initialize command launcher with parent dispatch instance.
        
        Args:
            dispatch: Parent zDispatch instance providing access to zCLI, logger, and display
        
        Raises:
            AttributeError: If dispatch is missing required attributes (zos, logger)
        
        Example:
            launcher = CommandLauncher(dispatch)
        """
        self.dispatch = dispatch
        self.zos = dispatch.zos
        self.logger = dispatch.logger
        self.display = dispatch.zos.display

        # ========================================================================
        # Phase 5 Micro-Step 5.1: Initialize Extracted Modules
        # ========================================================================
        # These modules are initialized but not yet used. They will be integrated
        # incrementally in subsequent micro-steps.

        # Phase 1 modules (Leaf)
        # Binding resolution lives in the zLoom subsystem — reach it via zos.zloom.
        self.auth_handler = AuthHandler(self.zos, self.display, self.logger)
        self.crud_handler = CRUDHandler(self.zos, self.display, self.logger)

        # Phase 2 modules (Core Logic)
        self.navigation_handler = NavigationHandler(self.zos, self.display, self.logger)
        self.subsystem_router = SubsystemRouter(
            self.zos,
            self.display,
            self.logger,
            self.auth_handler,
            self.navigation_handler
        )

        # Phase 3 modules (Shorthand & Detection)
        self.shorthand_expander = ShorthandExpander(self.logger)
        self.wizard_detector = WizardDetector()
        self.organizational_handler = OrganizationalHandler(
            self.shorthand_expander,  # Needs expander, not zos
            self.logger
        )

        # zTransfer — the SSOT I/O primitive. zImport/zExport are sugar on top
        # of this one engine, so file/model/storage/bytes moves share a path.
        self.transfer_engine = TransferEngine(self.zos, self.display, self.logger)
        self.transfer_handler = TransferHandler(self.transfer_engine, self.logger)
        # Expose to any subsystem that needs backend-agnostic I/O.
        if getattr(self.zos, "transfer", None) is None:
            self.zos.transfer = self.transfer_engine

        # Phase 4 modules (Command Handlers)
        self.export_handler = ExportHandler(self.zos, self.display, self.logger, self.transfer_engine)
        self.import_handler = ImportHandler(self.zos, self.display, self.logger, self.transfer_engine)
        self.list_handler = ListCommandHandler(self.zos, self.logger)
        self.string_handler = StringCommandHandler(
            self.zos,
            self.logger,
            self.subsystem_router,
            self.launch  # Pass launch function for recursion
        )
        # Note: dict_handler will be added in later micro-step (has circular deps)

    # ========================================================================
    # PUBLIC METHODS - Main Entry Points
    # ========================================================================

    def launch(
        self,
        zHorizontal: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        walker: Optional[Any] = None
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """Main entry point: routes string/dict commands to appropriate handlers."""
        self._display_handler(_LABEL_LAUNCHER, _DEFAULT_INDENT_LAUNCHER)

        # Early return for placeholder actions (development/testing)
        if zHorizontal == ACTION_PLACEHOLDER:
            self.logger.debug(f"[CommandLauncher] Placeholder action detected: '{ACTION_PLACEHOLDER}' - no-op")
            return None

        if isinstance(zHorizontal, str):
            return self._launch_string(zHorizontal, context, walker)
        elif isinstance(zHorizontal, dict):
            return self._launch_dict(zHorizontal, context, walker)
        elif isinstance(zHorizontal, list):
            return self._launch_list(zHorizontal, context, walker)

        # Unknown type - return None
        return None

    # ========================================================================
    # PRIVATE METHODS - List Command Routing (Sequential Execution)
    # ========================================================================

    def _launch_list(
        self,
        zHorizontal: list,
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """Delegate list command handling to ListCommandHandler."""
        return self.list_handler.handle(zHorizontal, context, walker, self.launch)

    # ========================================================================
    # PRIVATE METHODS - String Command Routing
    # ========================================================================

    def _launch_string(
        self,
        zHorizontal: str,
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """Delegate string command handling to StringCommandHandler."""
        return self.string_handler.handle(zHorizontal, context, walker)

    # ========================================================================
    # STRING ROUTING HELPERS - Decomposed from _launch_string()
    # ========================================================================

    def _resolve_plain_string_in_bifrost(
        self,
        zHorizontal: str,
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Union[Dict[str, Any], Any]:
        """Resolve plain string in Bifrost mode from zUI block or return as message."""
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
                        return self.launch(resolved_value, context=context, walker=walker)
                    else:
                        self.logger.framework.debug(
                            f"[{MODE_BIFROST}] Key '{zHorizontal}' not found in zUI block '{zBlock}'"
                        )
            except Exception as e:
                self.logger.warning(f"[{MODE_BIFROST}] Error resolving key from zUI: {e}")

        # If we couldn't resolve it, return as display message
        self.logger.framework.debug(f"Plain string in {MODE_BIFROST} mode - returning as message")
        return {KEY_MESSAGE: zHorizontal}

    # ========================================================================
    # PRIVATE METHODS - Dict Command Routing
    # ========================================================================

    def _launch_dict(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """Route dict commands: zRBAC check → wrapper unwrap → data resolution → organizational/wizard/subsystem → CRUD."""
        # ========================================================================
        # GREEK-LETTER ALIAS NORMALIZATION — zAlpha → zLink
        # ========================================================================
        # zAlpha is the Greek-letter first-class name for the zLink event; zLink
        # remains a permanent alias. Rename the authored key to the canonical
        # token (shallow copy — never mutate the cached block) so all downstream
        # routing, the {"zLink": path} nav-signal protocol, and the client stay
        # single-spelling. zDelta / zURL are untouched; zOmega (zPsi) is handled
        # by the resolver's value normalizer.
        if KEY_ZALPHA in zHorizontal and KEY_ZLINK not in zHorizontal:
            zHorizontal = {
                (KEY_ZLINK if k == KEY_ZALPHA else k): v
                for k, v in zHorizontal.items()
            }

        # ========================================================================
        # GATE ENFORCEMENT — check before any execution (zGate SSOT engine)
        # ========================================================================
        # NOTE: read via gate_predicate (not pop) — the block dict is shared/cached;
        # mutating it would permanently strip the gate on first dispatch. We strip
        # the gate key from a SHALLOW COPY so downstream routing never re-sees it.
        gate = self.zos.zgate.gate_predicate(zHorizontal)
        if gate is not None:
            if not self._check_gate(gate):
                return None
            zHorizontal = {
                k: v for k, v in zHorizontal.items() if k not in ("zGate", "zRBAC")
            }

        # ========================================================================
        # zPROGRESS ACTION-PROPERTY EXTRACTION
        # ========================================================================
        # `zProgress` beside an action key (zFunc, ...) is NOT a standalone bar —
        # it asks zOS to show a live "processing this event" journey AROUND that
        # action. Pull it out (shallow copy, like zRBAC) so shorthand expansion
        # and routing never see it; a standalone `zProgress:` block is untouched
        # and still expands via the normal UI shorthand path.
        progress_spec = None
        if KEY_ZPROGRESS in zHorizontal and any(k in zHorizontal for k in PROGRESS_ACTION_KEYS):
            progress_spec = zHorizontal.get(KEY_ZPROGRESS)
            zHorizontal = {k: v for k, v in zHorizontal.items() if k != KEY_ZPROGRESS}

        # Nested zFunc form: `zFunc: { src: &plugin(), zProgress: true|{...} }`.
        # The dict carries the call under `src` plus optional action-properties
        # (zProgress + its customization). Normalize to the canonical string form
        # so routing/parse_function_path stay string-first, lifting zProgress out
        # as the journey spec (a sibling zProgress, extracted above, wins).
        zfunc_val = zHorizontal.get(KEY_ZFUNC)
        if isinstance(zfunc_val, dict) and "src" in zfunc_val:
            if progress_spec is None:
                progress_spec = zfunc_val.get(KEY_ZPROGRESS)
            zHorizontal = {**zHorizontal, KEY_ZFUNC: zfunc_val["src"]}

        # ========================================================================
        # PRELIMINARY CHECKS
        # ========================================================================
        subsystem_keys = {KEY_ZDISPLAY, KEY_ZFUNC, KEY_ZDIALOG, KEY_ZDASH, KEY_ZFLAT, KEY_ZLINK, KEY_ZDELTA, KEY_ZMODAL, KEY_ZMENU, KEY_ZWIZARD, KEY_ZREAD, KEY_ZDATA, KEY_ZEXPORT, KEY_ZIMPORT, KEY_ZTRANSFER, KEY_ZVAR, KEY_ZLIST, KEY_ZLOGIN, KEY_ZLOGOUT}
        # Get ALL content keys, excluding metadata (_zClass, _zStyle, ...) AND
        # declarative event bindings (onChange/onClick/...). Event bindings attach
        # a handler to a sibling UI element and must NEVER be executed inline —
        # they are consumed by the zAPI scanner + Bifrost enrichment + client.
        # __zListSource: zLoom LoopOps' stashed original zList directive (see
        # expander_organizational.py's _METADATA_KEYS) — never a renderable node.
        metadata_keys = (
            {'_zClass', '_zStyle', '_zId', 'zScripts', 'zId', '__zListSource'}
            | set(EVENT_BINDING_KEYS)
        )
        content_keys = [k for k in zHorizontal.keys() if k not in metadata_keys]
        # zStride: remember a lone display directive BEFORE shorthand expansion.
        # The single-UI hoist (shorthand_expander early-return) collapses
        # {zH0: "..."} → bare {zDisplay: ...}, destroying the directive name and
        # routing it straight to _route_zdisplay — bypassing the organizational
        # walk that records multi-key leaves. Capturing it here lets the hoisted
        # leaf zStride identically to its multi-key siblings (uniform trail depth).
        _pre_expand_single_key = content_keys[0] if len(content_keys) == 1 else None
        is_subsystem_call = any(k in zHorizontal for k in subsystem_keys)
        crud_keys = {'action', 'model', 'table', 'collection'}
        is_crud_call = any(k in zHorizontal for k in crud_keys)

        # ========================================================================
        # CONTENT WRAPPER UNWRAPPING
        # ========================================================================
        result = self._unwrap_content_wrapper(zHorizontal, content_keys, context, walker)
        if result is not None or (len(content_keys) == 1 and content_keys[0] == 'Content'):
            return result

        # ========================================================================
        # SHORTHAND SYNTAX EXPANSION
        # ========================================================================
        zHorizontal, is_subsystem_call = self._expand_plural_shorthands(zHorizontal, is_subsystem_call)

        # Phase 5 Micro-Step 5.3: MODE-AGNOSTIC Shorthand Expansion (FIXES zCrumbs BUG!)
        # OLD: Only expanded in zCLI mode → zCrumbs never rendered in Bifrost
        # NEW: Expands for BOTH modes → zCrumbs work everywhere!
        zHorizontal, is_subsystem_call = self.shorthand_expander.expand(
            zHorizontal,
            self.zos.session,  # Pass session dict (not .data)
            is_subsystem_call
        )

        # Recalculate content_keys and subsystem check after shorthand expansion
        # Use same metadata filtering as initial check to include organizational containers
        content_keys = [k for k in zHorizontal.keys() if k not in metadata_keys]

        # Check for explicit subsystem keys at top level (zDisplay, zFunc, etc.)
        has_explicit_subsystem_keys = any(k in zHorizontal for k in subsystem_keys)
        if has_explicit_subsystem_keys:
            is_subsystem_call = True

        # zStride a single display leaf that the shorthand hoist just collapsed to
        # a bare {zDisplay} — see _pre_expand_single_key above. Recorded here (the
        # render choke point) so single-leaf containers reach the same trail depth
        # as multi-key ones. Top-level leaves also pass here, but the engine records
        # them too; the consecutive-dup guard collapses that to one.
        self._zStride_hoisted_leaf(_pre_expand_single_key, zHorizontal, walker)

        # ========================================================================
        # ORGANIZATIONAL STRUCTURE DETECTION (mutually exclusive with wizard)
        # ========================================================================
        # After shorthand expansion, we may have: {'zH1': {'zDisplay': {...}}, 'zText': {'zDisplay': {...}}}
        # These are organizational structures that need recursive launching, even if is_subsystem_call=True

        # SPECIAL CASE: When zWizard is mixed with other content keys, process non-wizard keys first
        # Example: {'zText': {...}, 'zWizard': {...}} should render zText then execute wizard
        has_zwizard_key = KEY_ZWIZARD in zHorizontal
        non_wizard_content_keys = [k for k in content_keys if k != KEY_ZWIZARD]

        should_check_organizational = (
            not is_crud_call and len(content_keys) > 0 and
            (not has_explicit_subsystem_keys or (has_zwizard_key and len(non_wizard_content_keys) > 0))
        )
        if should_check_organizational:
            # If zWizard is present with other keys, only process the non-wizard keys here
            keys_to_process = non_wizard_content_keys if has_zwizard_key else content_keys

            if len(keys_to_process) > 0:
                result = self._handle_organizational_structure(zHorizontal, context, walker)
                # If organizational structure was detected and processed, return immediately
                # (even if result is None) to prevent fallthrough to implicit wizard
                # UNLESS we have a zWizard to process after
                if result is not None and not has_zwizard_key:
                    return result

                # Check if organizational structure was detected (all keys are nested)
                all_nested = all(
                    isinstance(zHorizontal[k], (dict, list))
                    for k in keys_to_process
                )
                if all_nested and not has_zwizard_key:
                    # Organizational structure was processed, don't fall through to wizard
                    return result

        # ========================================================================
        # IMPLICIT WIZARD DETECTION
        # ========================================================================
        # Run after shorthand expansion so zImage/zText/etc are already converted
        if not is_subsystem_call and not is_crud_call and len(content_keys) > 1:
            return self._handle_implicit_wizard(zHorizontal, walker)

        # ========================================================================
        # EXPLICIT SUBSYSTEM ROUTING
        # ========================================================================
        if KEY_ZDISPLAY in zHorizontal:
            return self._route_zdisplay(zHorizontal, context, progress_spec)
        if KEY_ZFUNC in zHorizontal:
            if progress_spec is not None:
                return self._route_zfunc_with_progress(zHorizontal, context, progress_spec)
            return self._route_zfunc(zHorizontal, context)
        if KEY_ZDIALOG in zHorizontal:
            return self._route_zdialog(zHorizontal, context, walker)
        if KEY_ZDASH in zHorizontal:
            return self._route_zdash(zHorizontal, context)
        if KEY_ZFLAT in zHorizontal:
            return self._route_zflat(zHorizontal, context, walker)
        # Phase 5 Micro-Step 5.4: Delegate Auth routing to AuthHandler (Phase 1)
        if KEY_ZLOGIN in zHorizontal:
            if isinstance(zHorizontal[KEY_ZLOGIN], dict):
                return self.auth_handler.handle_zlogin_block(zHorizontal, walker, context)
            return self.auth_handler.handle_zlogin(zHorizontal, context)
        if KEY_ZLOGOUT in zHorizontal:
            if isinstance(zHorizontal[KEY_ZLOGOUT], dict):
                return self.auth_handler.handle_zlogout_block(zHorizontal, walker, context)
            return self.auth_handler.handle_zlogout(zHorizontal)
        # Phase 5 Micro-Step 5.5: Delegate Navigation routing to NavigationHandler (Phase 2)
        if KEY_ZLINK in zHorizontal:
            return self.navigation_handler.handle_zlink(zHorizontal, walker)
        if KEY_ZDELTA in zHorizontal:
            return self.navigation_handler.handle_zdelta(zHorizontal, walker)
        if KEY_ZMODAL in zHorizontal:
            return self.navigation_handler.handle_zmodal(zHorizontal, walker, context=context)
        if KEY_ZMENU in zHorizontal:
            return self.navigation_handler.handle_zmenu(zHorizontal, walker, context=context)
        if KEY_ZDELEGATE in zHorizontal:
            return self.navigation_handler.handle_zdelegate(zHorizontal, walker)
        if KEY_ZWIZARD in zHorizontal:
            return self._handle_wizard_dict(zHorizontal, walker, context)
        if KEY_ZREAD in zHorizontal:
            return self._handle_read_dict(zHorizontal, context)
        if KEY_ZDATA in zHorizontal:
            return self._handle_data_dict(zHorizontal, context)
        if KEY_ZEXPORT in zHorizontal:
            return self.export_handler.handle_export(zHorizontal, context, walker)
        if KEY_ZIMPORT in zHorizontal:
            return self.import_handler.handle_import(zHorizontal, context, walker)
        if KEY_ZTRANSFER in zHorizontal:
            return self.transfer_handler.handle(zHorizontal, context, walker)
        if KEY_ZVAR in zHorizontal:
            return self._handle_zvar(zHorizontal, context, walker)
        if KEY_ZLIST in zHorizontal:
            return self._handle_zlist(zHorizontal, context, walker)

        # ========================================================================
        # CRUD FALLBACK
        # ========================================================================
        # Phase 5 Micro-Step 5.6: Delegate CRUD detection to CRUDHandler (Phase 1)
        if self.crud_handler.is_crud_pattern(zHorizontal):
            return self.crud_handler.handle(zHorizontal, context)

        # No recognized keys found
        self.logger.framework.debug("[zCLI Launcher] No recognized keys found, returning None")
        return None

    # ========================================================================
    # PRIVATE METHODS - Specialized Command Handlers
    # ========================================================================


    # ========================================================================
    # DICT ROUTING HELPERS - Decomposed from _launch_dict()
    # ========================================================================

    def _check_gate(self, gate: Any) -> bool:
        """
        Enforce an authored ``zGate:`` predicate on a dispatched action.

        DUMB CALLER: the verdict belongs to the zGate engine. The predicate IS the
        authored IR (no lowering); the engine forwards any auth keys straight to
        ``zos.auth.check_zrbac`` (still the auth SSOT — no logic moved here). We act
        only on (granted, reason) — no auth/role/session logic here. Denials surface
        a warning; unexpected errors fail open (an action gate must not hard-block on
        infra hiccups).
        """
        try:
            granted, reason = self.zos.zgate.evaluate(gate)
            if not granted:
                self.zos.display.warning(f"[zGate] Access denied: {reason}")
            return granted
        except Exception as e:
            self.logger.framework.warning(f"[zGate] Check failed with error: {e}")
            return True  # fail-open: don't block on unexpected errors

    def _unwrap_content_wrapper(
        self,
        zHorizontal: Dict[str, Any],
        content_keys: List[str],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """Unwrap 'Content' wrapper and dispatch recursively."""
        if len(content_keys) == 1 and content_keys[0] == 'Content':
            self._log_detected("Content wrapper (unwrapping)")
            content_value = zHorizontal['Content']
            return self.launch(content_value, context=context, walker=walker)
        return None

    def _handle_organizational_structure(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """Delegate organizational structure handling to OrganizationalHandler."""
        return self.organizational_handler.handle(zHorizontal, context, walker, self)

    def _zStride_hoisted_leaf(
        self,
        single_key: Optional[str],
        zHorizontal: Dict[str, Any],
        walker: Optional[Any],
    ) -> None:
        """Record ONE zStride for a single display leaf collapsed by the hoist.

        The shorthand expander early-returns a lone UI directive as a bare
        ``{zDisplay: ...}`` (single-element case), dropping the directive name and
        skipping the organizational walk. To keep zCLI trail depth uniform — every
        leaf at any nesting is a zStride — record the captured pre-hoist key here.

        Boundaries (mirror OrganizationalHandler._zStride_passive):
          - terminal only: Bifrost records via its click-ancestry chain, never the
            walk, so recording here would pollute its chunk-render trail.
          - hoisted display leaves only: must have collapsed to a top-level
            ``zDisplay`` from a single non-zDisplay directive.
          - passive only: conditional events (url/button/inputs/selection) commit
            on success in the engine — they are never pre-stamped.
          - ``^``/``~``/``!``/``*`` modifiers and ``zCrumbs`` are skipped.
        """
        if walker is None or not single_key or not isinstance(single_key, str):
            return
        if single_key == KEY_ZDISPLAY:
            return  # already an explicit zDisplay — engine/other owns recording
        disp = zHorizontal.get(KEY_ZDISPLAY)
        if not isinstance(disp, dict):
            return  # not hoisted (multi-key / organizational stays in the walk)
        # The ONE classifier owns "conditional vs passive": modifiers, zCrumbs,
        # and commit-on-success leaf events (url/button/inputs/selection) are all
        # decided there — feed it the resolved leaf event.
        if not is_passive_zStride(single_key, event=disp.get('event')):
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
        nav.record_zStride(single_key, walker=walker)

    def _route_zflat(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """Render a nested block in passive (flat) mode.

        SSOT for "render rich zUI without sync interaction". While the flag is
        set, interactive events (zBtn/zURL/zInput/zSelect/…) render their visual
        affordance but skip the blocking prompt — see build_event_map. The flag
        is a depth counter so nested zFlat blocks stay flat and restore cleanly.
        Hosts like zSwiper slides / zTable cells set the same flag programmatically.
        """
        inner = zHorizontal.get(KEY_ZFLAT)
        if not isinstance(inner, dict):
            return None
        session = self.zos.session
        prev = session.get("_zflat", 0)
        session["_zflat"] = prev + 1
        try:
            return self._launch_dict(inner, context, walker)
        finally:
            session["_zflat"] = prev



    # ========================================================================
    # HELPER METHODS - DRY Refactoring
    # ========================================================================

    def _display_handler(self, label: str, indent: int) -> None:
        """Display handler label with consistent styling."""
        self.display.zDeclare(label, color=self.dispatch.mycolor, indent=indent, style=_DEFAULT_STYLE_SINGLE)

    def _log_detected(self, message: str) -> None:
        """Log detected command."""
        self.logger.framework.debug(f"Detected {message}")

    def _set_default_action(self, req: Dict[str, Any], default_action: str) -> None:
        """Set default action if not present in request."""
        if KEY_ACTION not in req:
            req[KEY_ACTION] = default_action

    def _expand_plural_shorthands(
        self,
        zHorizontal: Dict[str, Any],
        is_subsystem_call: bool
    ) -> tuple:
        """Expand plural shorthands (zURLs, zTexts, etc.) to wizard format."""
        plural_shorthands = ['zURLs', 'zTexts', 'zH1s', 'zH2s', 'zH3s', 'zH4s', 'zH5s', 'zH6s', 'zImages', 'zMDs']
        found_plural = None
        for plural_key in plural_shorthands:
            if plural_key in zHorizontal and isinstance(zHorizontal[plural_key], dict):
                found_plural = plural_key
                break

        if found_plural:
            self.logger.debug(f"[Shorthand] Found plural: {found_plural}")
            plural_items = zHorizontal[found_plural]
            expanded = {}
            event_map = {
                'zURLs': 'zURL',
                'zTexts': 'text',
                'zImages': 'image',
                'zMDs': 'rich_text'
            }
            singular = event_map.get(found_plural)

            if not singular and found_plural.startswith('zH') and found_plural.endswith('s'):
                indent = int(found_plural[2])
                if 1 <= indent <= 6:
                    singular = ('header', indent)

            if singular:
                for key, params in plural_items.items():
                    if isinstance(params, dict):
                        if isinstance(singular, tuple):
                            event_type, indent = singular
                            expanded[key] = {KEY_ZDISPLAY: {'event': event_type, 'indent': indent, **params}}
                        else:
                            expanded[key] = {KEY_ZDISPLAY: {'event': singular, **params}}

                if expanded and '_zClass' in zHorizontal:
                    for key, value in expanded.items():
                        if KEY_ZDISPLAY in value:
                            value[KEY_ZDISPLAY]['_zClass'] = zHorizontal['_zClass']

                if expanded:
                    self.logger.debug(f"[Shorthand] Expanded to {len(expanded)} steps")
                    return expanded, False

        return zHorizontal, is_subsystem_call

    # ========================================================================
    # DATA RESOLUTION HELPERS - Decomposed from _resolve_block_data()
    # ========================================================================

    # ========================================================================
    # ZVAR / ZLIST HANDLERS
    # ========================================================================

    def _handle_zvar(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any] = None
    ) -> None:
        """Write key-value pairs into session["zVars"].

        Supports %data.*, %session.*, and %varname placeholders in values.
        Optional special key _navigate: <zLink-path> navigates after setting vars.
        """
        from zOS.L2_Handling.d_zParser.parser_modules.parser_functions import resolve_variables

        var_dict = zHorizontal.get(KEY_ZVAR, {})
        if not isinstance(var_dict, dict):
            return None

        navigate_target = var_dict.pop("_navigate", None)

        zvars = self.zos.session.setdefault("zVars", {})
        for key, raw_value in var_dict.items():
            value = str(raw_value) if raw_value is not None else ""
            value = resolve_variables(value, self.zos, context)
            zvars[key] = value
            self.logger.framework.debug(f"[zVar] Set zVars[{key!r}] = {value!r}")

        if navigate_target:
            nav_path = resolve_variables(str(navigate_target), self.zos, context)
            effective_walker = walker or getattr(self.zos, "walker", None)
            self.logger.framework.debug(f"[zVar] _navigate to {nav_path!r} via {type(effective_walker).__name__!r}")
            return self.navigation_handler.handle_zlink({KEY_ZLINK: nav_path}, effective_walker)

        return None

    def _handle_zlist(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> None:
        """Render a zList by DELEGATING the loop to the zLoom SSOT.

        The loop engine is ``zos.zloom.expand_list_bindings`` — the SAME one the
        structural render paths (navigation_linking, zDash dashboard) use. Dispatch
        no longer re-implements source resolution or the per-row walk: it hands the
        directive to zLoom, which resolves the source, binds ``%item.*`` per row, and
        applies the per-row ``zGate`` filter, then dispatch launches each woven row
        block in order. One engine → source resolution, ``%item`` binding, and gating
        can never drift between dispatch and render.

        (Most page renders are already expanded upstream before dispatch; this covers
        a zList dispatched directly, e.g. from an event flow.)
        """
        import copy

        cfg = zHorizontal.get(KEY_ZLIST, {})
        if not isinstance(cfg, dict):
            return None

        resolver = getattr(self.zos, "zloom", None)
        if resolver is None or not hasattr(resolver, "expand_list_bindings"):
            return None

        # zLoom reads resolved_data first, then falls back to session
        # ["_current_block_data"] internally — same sources the old resolver used.
        resolved_data = context.get("_resolved_data") if isinstance(context, dict) else None
        parent: Dict[str, Any] = {KEY_ZLIST: copy.deepcopy(cfg)}
        resolver.expand_list_bindings(
            parent, resolved_data if isinstance(resolved_data, dict) else {}, context
        )

        # Launch each woven row block in insertion order (%item.* already baked,
        # gated rows already dropped by the engine).
        for key, block in parent.items():
            if isinstance(key, str) and key.startswith("zListItem__"):
                self.launch(block, context=context, walker=walker)
        return None
