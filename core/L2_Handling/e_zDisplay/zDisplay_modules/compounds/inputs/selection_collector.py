# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/d_compounds/inputs/selection_collector.py

"""
Selection Collector - Helper module for BasicInputs
====================================================

Provides input collection logic:
- Single-select collection with validation
- Multi-select collection with toggle behavior
- Button confirmation collection
"""

from zOS import Any, List, Set, Optional, Dict

from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    _PROMPT_INPUT,
    _PROMPT_SINGLE_SELECT_TEMPLATE,
    _CMD_DONE,
    _CMD_DONE_SHORT,
    _CMD_EMPTY,
    _OPTION_INDEX_OFFSET,
    _MSG_MULTI_SELECT_INSTRUCTIONS,
    _MSG_BUTTON_CLICKED,
    _MSG_BUTTON_CANCELLED,
    MODE_ZCLI,
)


class SelectionCollector:
    """Input collection logic for BasicInputs."""

    def __init__(self, display_instance: Any) -> None:
        """Initialize SelectionCollector with display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives
        self.zColors = display_instance.zColors

    def collect_single_selection(
        self,
        options: List[str],
        default: Optional[str],
        validator: Any,
        renderer: Any,
        basic_outputs: Optional[Any] = None
    ) -> Optional[str]:
        """Collect single selection from user with validation.
        
        Args:
            options: List of option strings
            default: Default option (or None)
            validator: InputValidators instance
            renderer: SelectionRenderer instance
            basic_outputs: BasicOutputs instance (optional)
            
        Returns:
            Optional[str]: Selected option or None if cancelled
        """
        # Build default hint — show value name, not index
        default_hint = _CMD_EMPTY
        if default is not None and default in options:
            default_hint = f" [{default}]"

        # Get selection with validation loop
        while True:
            try:
                prompt = _PROMPT_SINGLE_SELECT_TEMPLATE.format(
                    max_num=len(options),
                    default_hint=default_hint
                )
                selection = self.zPrimitives.read_string(prompt).strip()

                # Validate
                is_valid, result = validator.validate_single_selection(
                    selection, options, default
                )

                if is_valid:
                    renderer.display_feedback(f"  > {result} [selected]", basic_outputs=basic_outputs)
                    return result
                else:
                    # Display error message
                    renderer.display_feedback(result, basic_outputs=basic_outputs)

            except KeyboardInterrupt:
                return None

    def collect_multi_selection(
        self,
        options: List[str],
        default_set: Set[str],
        validator: Any,
        renderer: Any,
        basic_outputs: Optional[Any] = None
    ) -> List[str]:
        """Collect multiple selections from user with toggle behavior.
        
        Args:
            options: List of option strings
            default_set: Set of default selections
            validator: InputValidators instance
            renderer: SelectionRenderer instance
            basic_outputs: BasicOutputs instance (optional)
            
        Returns:
            List[str]: List of selected options
        """
        renderer.output_text(
            _MSG_MULTI_SELECT_INSTRUCTIONS,
            break_after=False,
            basic_outputs=basic_outputs
        )

        selected = set(default_set) if default_set else set()

        while True:
            try:
                default_hint = f" [{', '.join(sorted(selected))}]" if selected else ""
                user_input = self.zPrimitives.read_string(f"Input{default_hint}: ").strip().lower()

                if user_input in (_CMD_DONE, _CMD_DONE_SHORT, _CMD_EMPTY):
                    if selected:
                        renderer.display_feedback(
                            f"  > {', '.join(sorted(selected))} [selected]",
                            basic_outputs=basic_outputs
                        )
                    break

                # Parse numbers
                numbers = user_input.split()
                for num_str in numbers:
                    _, feedback = validator.process_multi_selection_number(
                        num_str, options, selected
                    )
                    # Display feedback
                    renderer.display_feedback(feedback, basic_outputs=basic_outputs)

            except KeyboardInterrupt:
                break

        return list(selected)

    def collect_button_confirmation(
        self,
        label: str,
        color: str,
        action: Optional[Any],
        renderer: Any,
        basic_outputs: Optional[Any] = None,
        zIcon: Optional[str] = None,
        zProgress: Any = None
    ) -> Any:
        """Collect button click confirmation in terminal mode.
        
        Args:
            label: Button label text
            color: Button semantic color
            action: Optional action identifier
            renderer: SelectionRenderer instance
            basic_outputs: BasicOutputs instance (optional)
            zIcon: Optional icon name (renders emoji in terminal instead of label)
            
        Returns:
            bool: True if confirmed (y/yes only), False otherwise
            str: confirmed + step-key action — returned as wizard jump target
            dict: confirmed + zLink(...)/zDelta(...) action — {'zLink': path} or
                  {'zDelta': target} navigation result consumed by the wizard engine
        """
        try:
            # Render icon in terminal mode if provided — always keep label
            if zIcon:
                icon_text = self._render_icon_for_terminal(zIcon)
                display_text = f"{label} [{icon_text}]" if icon_text != zIcon else label
            else:
                display_text = label

            # SSOT confirm gate owns the prompt wording, colour, validation loop
            # and zFlat. The action/feedback layer below stays button-specific.
            from ...utils.confirm_gate import confirm_gate
            confirmed = confirm_gate(self.display, "button", label=display_text, color=color)

            # MUST type 'y' or 'yes' - empty/n/no all cancel
            if confirmed:
                renderer.display_feedback(
                    _MSG_BUTTON_CLICKED.format(label=label),
                    basic_outputs=basic_outputs
                )

                # Execute action if provided. Two authoring forms:
                #   • longhand dict {zEvent: {...}} → delegate the unfold to the
                #     zDispatch brain (SSOT). Exactly one event, zWizard for many.
                #   • string verb (&plugin / zLink(...) / step-jump key) → ladder.
                if isinstance(action, dict):
                    self._execute_button_action_event(action)
                elif action and isinstance(action, str):
                    if action.startswith('&'):
                        if zProgress is not None:
                            self._execute_button_action_with_progress(action, zProgress)
                        else:
                            self._execute_button_action(action)
                    elif action.startswith('zLink('):
                        # Imperative zLink string. Don't return it raw — the wizard
                        # loop would treat it as a step-jump key, find no match, and
                        # silently drop it. Return the dict form the wizard engine
                        # already navigates on (_handle_navigation_result → dispatch),
                        # mirroring the Bifrost client's zLink( click intercept.
                        return {'zLink': action[len('zLink('):-1].strip()}
                    elif action.startswith('zAlpha('):
                        # zAlpha is the FIRST-CLASS Greek name for the zLink event
                        # (03_navigation: "different file → zAlpha"). It was missing
                        # from this ladder, so a zBtn `action: zAlpha(@.path)` fell
                        # through to the step-jump return below, matched no sibling
                        # key, and was silently dropped (zOS#19) — the one verb the
                        # docs teach for cross-file buttons was the one that did
                        # nothing in zCLI. Normalize to the zLink dict form here,
                        # exactly like the dispatch seam does for authored zAlpha keys.
                        return {'zLink': action[len('zAlpha('):-1].strip()}
                    elif action.startswith('zDelta('):
                        # Imperative zDelta string — same-file block hop. Symmetric
                        # with zLink( above: return the dict form so the wizard
                        # dispatches it (_handle_navigation_result → zDispatch). Raw
                        # return would be mistaken for a step-jump key and dropped,
                        # which is exactly why a zBtn action: zDelta(...) did nothing
                        # in zCLI/zTerminal while the Bifrost click intercept worked.
                        return {'zDelta': action[len('zDelta('):-1].strip()}
                    elif action.startswith('zModal('):
                        # Imperative zModal string — the CALL verb. Unlike the GOTOs
                        # above, nothing to hand the wizard engine: run the detour
                        # inline (dispatch dict branch → zNavigation run_modal) and
                        # resume right here — the auto-back IS the semantics.
                        self._execute_button_action_event(
                            {'zModal': action[len('zModal('):-1].strip()}
                        )
                    elif action != '#':
                        # Return action as navigation/jump target for wizard step-jumps
                        return action

                return True
            else:
                renderer.display_feedback(
                    _MSG_BUTTON_CANCELLED.format(label=label),
                    basic_outputs=basic_outputs
                )
                return False

        except KeyboardInterrupt:
            renderer.display_feedback(
                _MSG_BUTTON_CANCELLED.format(label=label),
                basic_outputs=basic_outputs
            )
            return False

    def _execute_button_action(self, action: str) -> None:
        """Execute button action (plugin invocation).
        
        Args:
            action: Action string starting with '&'
        """
        zos = getattr(self.display, 'zos', None)
        if zos is None:
            return
        zfunc = getattr(zos, 'zfunc', None)
        try:
            if zfunc is not None and hasattr(zfunc, 'run'):
                # Route through zfunc.run — the SSOT execution path that also
                # handles a browser-only `.js` gracefully (BrowserOnlyFunctionError
                # → one clean warning, not a node traceback). The button `action:`
                # is the terminal twin of the eager `zFunc:`; both must share it.
                zos.logger.debug(f"🎯 Executing button action via zfunc: {action}")
                result = zfunc.run(action)
                zos.logger.debug(f"✅ Button action executed, result: {result}")
            elif hasattr(zos, 'zparser'):
                zos.logger.debug(f"🎯 Executing button action: {action}")
                result = zos.zparser.resolve_plugin_invocation(action, zos)
                zos.logger.debug(f"✅ Button action executed, result: {result}")
            elif hasattr(zos, 'logger'):
                zos.logger.warning(
                    f"⚠️  Cannot execute button action - zfunc/zparser not available: {action}"
                )
        except Exception as e:
            if hasattr(zos, 'logger'):
                zos.logger.error(f"❌ Button action execution failed: {e}", exc_info=True)

    def _execute_button_action_event(self, action: Dict[str, Any]) -> Any:
        """Unfold a longhand button action into a single zEvent via zDispatch.

        The button's job is to COLLECT the confirm; unfolding the action is
        delegated to the zDispatch brain (SSOT) — no event logic lives here.
        Exactly one top-level event key is allowed; declare a `zWizard` event
        for sequences. Accepts both raw shorthand ({zSuccess: {...}}) and the
        already-expanded form ({zDisplay: {event: ...}}); dispatch handles both.

        Args:
            action: Single-event action dict.

        Returns:
            The dispatch result, or None if invalid / dispatch unavailable.
        """
        event_keys = [k for k in action.keys() if not str(k).startswith('_')]
        if len(event_keys) != 1:
            msg = (
                f"zBtn action must declare exactly one event "
                f"(use a zWizard event for sequences); got: {event_keys}"
            )
            if hasattr(self.display, 'zos') and hasattr(self.display.zos, 'logger'):
                self.display.zos.logger.error(f"❌ {msg}")
            # Surface to the author too — dev-visible rejection via the SSOT
            # error signal, so a bad authoring is seen on screen, not just in logs.
            err = getattr(self.display, 'error', None)
            if callable(err):
                try:
                    err(msg)
                except Exception:  # noqa: BLE001
                    pass
            return None

        try:
            zos = getattr(self.display, 'zos', None)
            dispatch = getattr(zos, 'dispatch', None) if zos else None
            if dispatch is not None:
                self.display.zos.logger.debug(
                    f"🎯 Unfolding button action event: {event_keys[0]}"
                )
                result = dispatch.handle("action", action)
                self.display.zos.logger.debug(
                    f"✅ Button action event dispatched, result: {result}"
                )
                return result
            if zos and hasattr(zos, 'logger'):
                zos.logger.warning(
                    f"⚠️  Cannot unfold button action - zDispatch unavailable: {event_keys[0]}"
                )
        except Exception as e:
            if hasattr(self.display, 'zos') and hasattr(self.display.zos, 'logger'):
                self.display.zos.logger.error(
                    f"❌ Button action event dispatch failed: {e}", exc_info=True
                )
        return None

    def _execute_button_action_with_progress(self, action: str, zProgress: Any) -> None:
        """Execute a button's plugin action inside the live zProgress journey.

        The y/n gate has already passed, so wrapping only the execution keeps the
        animation free of any blocking input. zProbe (the SSOT denominator oracle)
        decides the journey's stops — a gated button journeys confirm → resolve →
        execute, so it shows more stops than a direct zFunc. zCLI only; in Bifrost
        the journey is a transparent pass-through.
        """
        try:
            from .....g_zDispatch.dispatch_modules.progress_journey import ProgressJourney
            from .....g_zDispatch.dispatch_modules.zprobe import probe

            spec = zProgress if isinstance(zProgress, dict) else {}
            label = str(spec.get("label", "Working"))
            color = spec.get("color")
            # Only bar | spinner exist; the denominator is the probe's. Anything
            # else (legacy marquee/stepped/…) folds to the bar render.
            ptype = "spinner" if str(spec.get("type", "bar")).lower() == "spinner" else "bar"
            style = str(spec.get("style", "")).lower()
            result = probe({"zBtn": {"action": action}}, getattr(self.display, "zos", None))
            if hasattr(self.display, "zos") and hasattr(self.display.zos, "logger"):
                self.display.zos.logger.debug(f"[zProbe] {result!r}")

            journey = ProgressJourney(self.display, getattr(self.display, "logger", None))
            journey.run(
                lambda: self._execute_button_action(action),
                label=label,
                color=color,
                stops=result.stops,
                ptype=ptype,
                style=style,
            )
        except Exception as e:  # noqa: BLE001
            if hasattr(self.display, 'zos') and hasattr(self.display.zos, 'logger'):
                self.display.zos.logger.error(f"❌ Button progress journey failed: {e}", exc_info=True)
            # Fall back to a plain execution so the action still runs.
            self._execute_button_action(action)

    def _render_icon_for_terminal(self, icon_name: str) -> str:
        """Render icon as ANSI-safe text for terminal mode."""
        try:
            from zSys.accessibility import get_icon_mapper, get_emoji_descriptions
            emoji = get_icon_mapper().render_for_mode(icon_name, mode=MODE_ZCLI)
            safe = get_emoji_descriptions().format_for_terminal(emoji)
            # Strip outer brackets — the prompt template adds its own []
            if safe.startswith('[') and safe.endswith(']'):
                safe = safe[1:-1]
            return safe
        except Exception:
            return icon_name
