# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/display_routing.py

"""
Event Routing Map - Single Source of Truth
===========================================

Centralizes event routing logic for zDisplay subsystem.
This module provides a single function to build the event routing map,
eliminating duplication between zDisplay.py and other modules.

Usage:
    from .display_routing import build_event_map
    
    self._event_map = build_event_map(self.zEvents, self.zPrimitives, self._terminal_executor)
"""

from zOS import Dict, Callable, Any
from .display_constants import (
    _EVENT_TEXT,
    _EVENT_RICH_TEXT,
    _EVENT_HEADER,
    _EVENT_CODE,
    _EVENT_LINE,
    _EVENT_ERROR,
    _EVENT_WARNING,
    _EVENT_SUCCESS,
    _EVENT_INFO,
    _EVENT_PRIMARY,
    _EVENT_SECONDARY,
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
    _EVENT_ICON,
    _EVENT_EMBED,
    _EVENT_ZDECLARE,
    _EVENT_ZSESSION,
    _EVENT_ZCONFIG,
    _EVENT_ZCRUMBS,
    _EVENT_ZMENU,
    _EVENT_ZDASH,
    _EVENT_ZDIALOG,
    _EVENT_ZLOGGER,
    _EVENT_ZTERMINAL,
    _EVENT_PROGRESS_BAR,
    _EVENT_SPINNER,
    _EVENT_SWIPER,
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
    TERMINAL_MODES,
)


def build_event_map(
    events: Any,
    primitives: Any,
    terminal_executor: Any
) -> Dict[str, Callable]:
    """Build unified event routing map (SSOT).
    
    Single source of truth for event routing. Maps event names to handler functions.
    
    Args:
        events: zEvents instance with all event packages
        primitives: zPrimitives instance for I/O operations
        terminal_executor: TerminalExecutor instance for code execution
    
    Returns:
        Dict mapping event names to handler callables
    
    Example:
        self._event_map = build_event_map(self.zEvents, self.zPrimitives, self._terminal_executor)
        handler = self._event_map.get('text')
        handler(content="Hello")
    """
    # zText paragraph spacing: only the dispatched zText event gets a trailing \n.
    # Internal text() calls (error, warning, zCrumbs, selection, etc.) go directly
    # to BasicOutputs.text() and never hit this wrapper.
    def _ztext_event(**kw):
        events.text(**kw)
        if events.BasicOutputs.display.mode in TERMINAL_MODES:
            primitives.raw('\n')

    # ── zFlat: passive (flat) render mode ────────────────────────────────────
    # A host (zSwiper slide, zTable cell, future print/export) can render nested
    # zUI inertly by setting session["_zflat"]. Interactive events then render
    # their VISUAL affordance but skip the blocking sync interaction.
    #
    # Two cooperating SSOTs:
    #   1. These wrappers — for events with a richer inert form (button label,
    #      link "label → href", input placeholders). They short-circuit BEFORE
    #      the event's own decline/"cancelled" branch, so the flat render stays
    #      clean.
    #   2. confirm_gate (utils/confirm_gate.py) — the y/n prompt SSOT, itself
    #      zFlat-aware. Events that route their confirmation through it (zImage,
    #      zVideo, zAudio, zTerminal) get a safe non-blocking flat fallback for
    #      free without needing a wrapper here.
    # zCLI/terminal only — Bifrost widgets stay live in the browser.
    def _flat_active() -> bool:
        try:
            disp = events.BasicOutputs.display
            if disp.mode not in TERMINAL_MODES:
                return False
            return bool(disp.zos.session.get("_zflat"))
        except Exception:  # noqa: BLE001 — never let a probe break rendering
            return False

    def _flat_button(**kw):
        primitives.line(f"[ {kw.get('label', 'Button')} ]")
        return False

    def _flat_link(**kw):
        label = kw.get("label") or kw.get("text") or "Link"
        href = kw.get("href") or kw.get("url") or ""
        primitives.line(f"{label} → {href}" if href else label)
        return None

    def _flat_input(**kw):
        label = kw.get("prompt") or kw.get("label") or kw.get("message") or "Input"
        default = kw.get("default", kw.get("value", ""))
        primitives.line(f"{label} [{default}]" if default not in (None, "") else f"{label} ____")
        return default if default is not None else ""

    def _flat_bool(**kw):
        label = kw.get("prompt") or kw.get("label") or "Confirm"
        checked = bool(kw.get("checked", kw.get("default", False)))
        primitives.line(f"[{'x' if checked else ' '}] {label}")
        return checked

    def _flat_selection(**kw):
        primitives.line(kw.get("prompt") or kw.get("label") or "Select")
        for i, opt in enumerate(kw.get("options") or [], 1):
            primitives.line(f"  {i}. {opt.get('label') if isinstance(opt, dict) else opt}")
        return None

    def _flat_aware(flat_fn, real_fn):
        def _wrapped(**kw):
            if _flat_active():
                return flat_fn(**kw)
            return real_fn(**kw)
        return _wrapped

    return {
        # Output events
        _EVENT_TEXT: _ztext_event,
        _EVENT_RICH_TEXT: events.rich_text,
        _EVENT_HEADER: events.header,
        _EVENT_CODE: events.code,
        _EVENT_LINE: events.text,

        # Signal events
        _EVENT_ERROR: events.error,
        _EVENT_WARNING: events.warning,
        _EVENT_SUCCESS: events.success,
        _EVENT_INFO: events.info,
        _EVENT_PRIMARY: events.primary,
        _EVENT_SECONDARY: events.secondary,
        _EVENT_ZMARKER: events.zMarker,

        # Data events
        _EVENT_LIST: events.list,
        _EVENT_DL: lambda **kwargs: events.list(style='details', **kwargs),
        _EVENT_JSON: events.json_data,
        _EVENT_JSON_DATA: events.json_data,
        _EVENT_ZTABLE: events.zTable,

        # Media events
        _EVENT_IMAGE: events.image,
        _EVENT_VIDEO: events.video,
        _EVENT_AUDIO: events.audio,
        _EVENT_PICTURE: events.picture,
        _EVENT_ICON: events.icon,
        _EVENT_EMBED: events.embed,

        # System events
        _EVENT_ZDECLARE: events.zDeclare,
        _EVENT_ZSESSION: events.zSession,
        _EVENT_ZCONFIG: events.zConfig,
        _EVENT_ZCRUMBS: events.zCrumbs,
        _EVENT_ZMENU: events.zMenu,
        _EVENT_ZDASH: events.zDash,
        _EVENT_ZDIALOG: events.zDialog,
        _EVENT_ZLOGGER: lambda message=None, level="INFO", tag=None, **_: (
            events.BasicOutputs.display.zos.log(str(message or ""), level, tag)
            if hasattr(events.BasicOutputs.display, "zos")
            else None
        ),
        # Drop GUI/styling metadata (_zClass, _GUI, _zDelegate, ...) — the local
        # executor only takes content/language/title. Other handlers tolerate the
        # extra keys; execute() has a fixed signature, so filter here.
        _EVENT_ZTERMINAL: lambda **kwargs: terminal_executor.execute(
            **{k: v for k, v in kwargs.items() if not k.startswith("_")}
        ),

        # Widget events (progress, spinners)
        _EVENT_PROGRESS_BAR: events.progress_bar,
        _EVENT_SPINNER: events.spinner,
        _EVENT_SWIPER: events.swiper,
        _EVENT_PROGRESS_ITERATOR: events.progress_iterator,
        _EVENT_INDETERMINATE_PROGRESS: events.indeterminate_progress,

        # Input events — wrapped so zFlat renders them inert (zCLI). In normal
        # mode the wrapper is a transparent pass-through to the real handler.
        _EVENT_SELECTION: _flat_aware(_flat_selection, events.selection),
        _EVENT_READ_STRING: _flat_aware(_flat_input, primitives.read_string),
        _EVENT_READ_PASSWORD: _flat_aware(_flat_input, primitives.read_password),
        _EVENT_READ_BOOL: _flat_aware(_flat_bool, events.BasicInputs.read_bool),
        _EVENT_READ_RANGE: _flat_aware(_flat_input, events.InteractiveInputs.read_range),
        _EVENT_BUTTON: _flat_aware(_flat_button, events.button),
        _EVENT_LINK: _flat_aware(_flat_link, events.link),

        # Primitive events
        _EVENT_WRITE_RAW: primitives.raw,
        _EVENT_WRITE_LINE: primitives.line,
        _EVENT_WRITE_BLOCK: primitives.block,
    }
