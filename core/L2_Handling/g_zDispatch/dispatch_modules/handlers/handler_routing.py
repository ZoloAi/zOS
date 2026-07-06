# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/handlers/handler_routing.py

"""
Command Routing Handlers
=========================

Extracted from dispatch_launcher.py to reduce file size.
Provides routing logic for zDisplay, zFunc, and zDialog commands.
"""

from zOS import Any, Optional, Dict


class RoutingHandlers:
    """Mixin providing routing methods for CommandLauncher.
    
    Required Attributes (provided by CommandLauncher):
        - zos: zOS instance
        - display: Display instance
        - logger: Logger instance
        - dispatch: Dispatch instance
    """

    zos: Any
    display: Any
    logger: Any
    dispatch: Any

    def _log_detected(self, _message: str) -> None:
        """Log detected command (provided by parent)."""
        pass

    def _display_handler(self, _label: str, _indent: int) -> None:
        """Display handler label (provided by parent)."""
        pass

    def _route_zdisplay(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        progress_spec: Any = None
    ) -> Any:
        """Route zDisplay command (legacy format).
        
        Args:
            zHorizontal: Dict containing zDisplay key
            context: Optional context dict
            progress_spec: zProgress action-property pulled by the launcher when a
                zBtn (now expanded to a button event) carried `zProgress`. Stamped
                onto the event so the display layer can wrap the button's action
                execution in the live journey.
        
        Returns:
            Result from display event
        """
        from ..dispatch_constants import KEY_ZDISPLAY

        self._log_detected("zDisplay (wrapped)")
        display_data = zHorizontal[KEY_ZDISPLAY]

        keys_repr = list(display_data.keys()) if isinstance(display_data, dict) else 'not a dict'
        self.logger.framework.debug(f"[_route_zdisplay] display_data keys: {keys_repr}")
        self.logger.framework.debug(f"[_route_zdisplay] display_data: {display_data}")

        if isinstance(display_data, dict):
            if context and "_resolved_data" in context:
                display_data["_context"] = context

            # Carry the journey request to the button executor (zCLI: animated bar
            # around the post-confirm action). Use a shallow copy so the shared
            # cached block dict is never mutated.
            if progress_spec is not None:
                display_data = {**display_data, "zProgress": progress_spec}

            result = self.display.handle(display_data)
            return result
        else:
            self.logger.framework.warning(f"[_route_zdisplay] display_data is not a dict! Type: {type(display_data)}")

        return None

    def _route_zfunc(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        """Route zFunc command (function execution or plugin invocation).
        
        Args:
            zHorizontal: Dict containing zFunc key
            context: Optional context dict
        
        Returns:
            Function/plugin execution result
        """
        from ..dispatch_constants import (
            KEY_ZFUNC, _LABEL_HANDLE_ZFUNC_DICT, _DEFAULT_INDENT_HANDLER
        )

        self._log_detected("zFunc (dict)")
        self._display_handler(_LABEL_HANDLE_ZFUNC_DICT, _DEFAULT_INDENT_HANDLER)
        func_spec = zHorizontal[KEY_ZFUNC]

        context_keys = context.keys() if context else 'None'
        self.logger.debug(f"[_route_zfunc] context type: {type(context)}, keys: {context_keys}")
        if context and "zHat" in context:
            self.logger.debug(f"[_route_zfunc] zHat found in context: {context['zHat']}")

        # SSOT dispatch: & (auto plugin folders) and @. (explicit zPath) converge
        # in zfunc.run — same execution, same on-screen result, same for Py/JS.
        return self.zos.zfunc.run(func_spec, context=context)

    @staticmethod
    def _parse_progress_spec(spec: Any) -> tuple:
        """Read a zProgress action-property into (label, color, type, style).

        spec may be True (bare opt-in) or a dict ({label, color, type, style}).
        The denominator always comes from zProbe; `type` only picks the render:
          - `bar` (default) — a normal bar that fills done/total across the
            probe's internal stops. Steps/percent, never time.
          - `spinner` — the same probe count shown as an animated glyph; `style`
            picks the shape (dots | line | arc | arrow | bouncing_ball | simple).
        `style` is meaningful for `spinner` only.
        """
        if isinstance(spec, dict):
            label = str(spec.get("label", "Working"))
            ptype = RoutingHandlers._normalize_ptype(spec.get("type", "bar"))
            style = str(spec.get("style", "")).lower()
            return label, spec.get("color"), ptype, style
        return "Working", None, "bar", ""

    @staticmethod
    def _normalize_ptype(value: Any) -> str:
        """Canonicalize a zProgress type. Only bar | spinner exist; everything
        else (legacy marquee/stepped/solid/…) folds to the bar render."""
        return "spinner" if str(value).lower() == "spinner" else "bar"

    def _route_zfunc_with_progress(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        progress_spec: Any
    ) -> Optional[Any]:
        """Run a zFunc inside a live progress journey (zCLI: animated bar).

        The journey shows that zOS is processing this event — it parks on the
        EXECUTE stage for the action's whole duration, then snaps to done. In
        Bifrost mode the journey is a transparent pass-through (separate task),
        so this is identical to `_route_zfunc` there.
        """
        from ..progress_journey import ProgressJourney
        from ..zprobe import probe

        label, color, ptype, style = self._parse_progress_spec(progress_spec)
        # zProbe is the SSOT denominator oracle — ask it how many stops this
        # journey has (read-only). For a direct zFunc that is a single EXECUTE.
        result = probe(zHorizontal, self.zos)
        if self.logger:
            self.logger.debug(f"[zProbe] {result!r}")
        journey = ProgressJourney(self.zos.display, self.logger)
        return journey.run(
            lambda: self._route_zfunc(zHorizontal, context),
            label=label,
            color=color,
            stops=result.stops,
            ptype=ptype,
            style=style,
        )

    def _route_zdialog(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Optional[Any]:
        """Route zDialog command (interactive form).
        
        Args:
            zHorizontal: Dict containing zDialog key
            context: Optional context dict
            walker: Optional walker instance
        
        Returns:
            Dialog execution result
        """
        from ....j_zDialog import handle_zDialog

        self._log_detected("zDialog")
        return handle_zDialog(zHorizontal, zcli=self.zos, walker=walker, context=context)

    def _route_zdash(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        """Route zDash command (interactive dashboard with sidebar navigation).
        
        Args:
            zHorizontal: Dict containing zDash key with folder, sidebar, default params
            context: Optional context dict
        
        Returns:
            Dashboard execution result
        """
        from ..dispatch_constants import KEY_ZDASH

        self._log_detected("zDash")
        dash_params = zHorizontal[KEY_ZDASH]

        if not isinstance(dash_params, dict):
            self.logger.framework.warning(f"[_route_zdash] zDash value must be a dict, got: {type(dash_params)}")
            return None

        display_data = {"event": "zDash", **dash_params}

        if context and "_resolved_data" in context:
            display_data["_context"] = context

        return self.display.handle(display_data)
