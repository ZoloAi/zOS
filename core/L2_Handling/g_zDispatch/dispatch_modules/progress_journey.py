# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/progress_journey.py

"""
Progress Journey — a STEP-based progress indicator around an action (zCLI).

The denominator is owned entirely by zProbe: it reports the internal zOS stops
the event traverses (e.g. zDispatch → zFunc). This module only RENDERS that
count — it fills `done/total` as each stop clears. It deals in STEPS, never time:
no elapsed seconds, no marquee. The last stop is where the real work runs, so the
bar sits at total-1 until the action returns, then snaps to total/total.

Two renders of the same count:
    - bar     — a normal bar filled to done/total (solid, no animation).
    - spinner — the same count as an animated glyph (shape from `style`).

zCLI ONLY. In Bifrost mode `run()` is a transparent pass-through (the client
renders; the streamed step transport is a separate task).

Mechanics (zCLI):
    - The action runs on a worker thread.
    - Global stdout is redirected to a buffer for the worker's duration, so the
      action's own prints / result render are CAPTURED (never interleaved with
      the indicator, which writes to the saved real stdout).
    - On completion, stdout is restored, the bar fills to total/total, and the
      captured action output is flushed in order.
"""

import io
import sys
import time
import threading
from zOS import Any, Optional, Callable

# Spinner frames live in the display SSOT — the journey's spinner type pulls from
# the same source as SpinnerEvents (no redefined frame sets).
from ...e_zDisplay.zDisplay_modules.display_constants import SPINNER_FRAMES, STYLE_DOTS


# Bar geometry / cadence
_WIDTH = 28               # track cells
_TICK = 0.11             # spinner frame cadence (spinner glyph only)
_STEP_PAUSE = 0.18        # brief beat as each internal route stop is shown
_CHAR_ON = "█"
_CHAR_OFF = "░"
_CHAR_DONE = "✓"          # spinner completion glyph

_ANSI_RESET = "\033[0m"
_ANSI_DIM = "\033[2m"
_ANSI_CLEAR_LINE = "\r\033[2K"

# Fallback color map (name → ANSI fg). Prefer zColors when present; this keeps
# the bar working even if zColors is unavailable.
_ANSI_COLORS = {
    "primary":   "\033[38;5;149m",
    "secondary": "\033[38;5;141m",
    "purple":    "\033[38;5;141m",
    "success":   "\033[32m",
    "green":     "\033[32m",
    "info":      "\033[36m",
    "warning":   "\033[33m",
    "danger":    "\033[31m",
    "error":     "\033[31m",
}
_DEFAULT_COLOR = "primary"


class ProgressJourney:
    """Render a live processing bar around a single action's execution."""

    def __init__(self, display: Any, logger: Any = None) -> None:
        self.display = display
        self.logger = logger
        self.zColors = getattr(display, "zColors", None)

    # ------------------------------------------------------------------ public
    def run(
        self,
        action: Callable[[], Any],
        label: str = "Working",
        color: Optional[str] = None,
        stage: str = "zFunc",
        stops: Optional[list] = None,
        ptype: str = "bar",
        style: str = "",
    ) -> Any:
        """Execute `action`, showing a STEP-based progress indicator in zCLI.

        `stops` (from zProbe) is the ordered list of internal zOS stops the event
        traverses (e.g. zDispatch → zFunc). It is the ONLY source of the
        denominator — never time. The indicator fills `done/total` as the event
        clears each stop; the last stop is where the real work runs, so the bar
        sits there (done = total-1) until the action returns, then snaps to
        total/total.

        `ptype` is JUST the render of that same count:
          - `bar` — a normal bar that fills done/total (no animation, no time).
          - `spinner` — the same count shown as an animated glyph (shape: `style`).

        Returns the action's return value (re-raises its exception).
        """
        if self._is_bifrost():
            return self._run_bifrost(action, label, color, stops or [stage], ptype, style)
        return self._run_cli(action, label, color, stops or [stage], ptype, style)

    # -------------------------------------------------------------- bifrost run
    def _run_bifrost(
        self,
        action: Callable[[], Any],
        label: str,
        color: Optional[str],
        stops: list,
        ptype: str = "bar",
        style: str = "",
    ) -> Any:
        """Stream the SAME step count to the browser via WS progress events.

        The client (progressbar_renderer) already updates a bar in place by its
        progressId and fades it on progress_complete. So the journey just emits
        the pre-EXECUTE stops (bar fills toward the execute step), runs the action
        — the bar sits at the execute step, kept alive by the renderer's own sheen
        — then emits a final complete. Steps, never time; the denominator is
        zProbe's, identical to the zCLI face.

        Emission goes through display.progress_bar(), which broadcasts over WS
        (asyncio.run_coroutine_threadsafe). This dispatch runs off the event-loop
        thread, so each emit flushes to the client immediately — including the one
        BEFORE the (possibly slow) action, which is what makes the bar visible
        during the wait rather than only at the end.
        """
        disp = self.display
        total = max(1, len(stops))
        final_idx = total - 1

        def emit(current: Optional[int], indeterminate: bool = False) -> None:
            try:
                disp.progress_bar(
                    current=0 if current is None else current,
                    total=None if indeterminate else total,
                    label=label,
                    color=color or _DEFAULT_COLOR,
                    show_percentage=False,
                )
            except Exception:  # pylint: disable=broad-except
                pass

        # Pre-execute stops already cleared by the time we wrap the call — fill to
        # the execute step (done = final_idx). A lone-stop journey has no room to
        # fill, so show an indeterminate "working" bar for the action's duration.
        if final_idx > 0:
            for idx in range(final_idx):
                emit(idx + 1)
        else:
            emit(None, indeterminate=True)

        try:
            result = action()
        finally:
            # Snap to done — the renderer treats current >= total as complete and
            # fades the bar; the action's own result renders in its place.
            emit(total)
        return result

    # ----------------------------------------------------------------- helpers
    def _is_bifrost(self) -> bool:
        try:
            if self.display and self.display.zPrimitives.is_bifrost_mode():
                return True
        except Exception:  # pylint: disable=broad-except
            pass
        return getattr(self.display, "mode", "") == "zBifrost"

    def _ansi(self, color: Optional[str]) -> str:
        name = (color or _DEFAULT_COLOR)
        # Try zColors SSOT first (attribute by upper name), then fallback map.
        if self.zColors is not None:
            code = getattr(self.zColors, str(name).upper(), None)
            if isinstance(code, str) and code:
                return code
        return _ANSI_COLORS.get(str(name).lower(), _ANSI_COLORS[_DEFAULT_COLOR])

    def _fill_bar(self, done: int, total: int, code: str) -> str:
        """A normal progress bar filled to done/total — solid, no animation."""
        filled = int(round(_WIDTH * done / max(1, total)))
        filled = max(0, min(_WIDTH, filled))
        cells = _CHAR_ON * filled + _CHAR_OFF * (_WIDTH - filled)
        return f"[{code}{cells}{_ANSI_RESET}]"

    def _visual(self, ptype: str, frames: list, frame_i: int, done: int, total: int, code: str) -> str:
        """Render the SAME done/total count. `bar` fills; `spinner` is a glyph."""
        if ptype == "spinner":
            glyph = _CHAR_DONE if done >= total else frames[frame_i % len(frames)]
            return f"{code}{glyph}{_ANSI_RESET}"
        return self._fill_bar(done, total, code)

    def _draw(self, out, ptype, frames, frame_i, done, total, stage, label, code, newline=False) -> None:
        """Redraw the indicator in place. STEPS only — never seconds."""
        line = (
            f"{_ANSI_CLEAR_LINE}  {self._visual(ptype, frames, frame_i, done, total, code)}  "
            f"{label} {_ANSI_DIM}· {stage} · {done}/{total}{_ANSI_RESET}"
        )
        out.write(line + ("\n" if newline else ""))
        out.flush()

    def _run_cli(
        self,
        action: Callable[[], Any],
        label: str,
        color: Optional[str],
        stops: list,
        ptype: str = "bar",
        style: str = "",
    ) -> Any:
        """Fill done/total across the probe's stops. No time, no marquee."""
        real_out = sys.stdout
        code = self._ansi(color)
        frames = SPINNER_FRAMES.get(style, SPINNER_FRAMES[STYLE_DOTS])
        total = max(1, len(stops))
        final_idx = total - 1
        final_stage = stops[final_idx] if stops else "zFunc"

        # Pre-EXECUTE stops are internal route stages already cleared by the time
        # we wrap the call — draw each as a completed step (fill advances).
        for idx in range(final_idx):
            self._draw(real_out, ptype, frames, idx, idx + 1, total, stops[idx], label, code)
            time.sleep(_STEP_PAUSE)

        # Final stop = where the work runs. Bar sits at final_idx/total; spinner
        # animates its glyph. Run on a worker thread; capture the action's stdout.
        box: dict = {}

        def worker() -> None:
            try:
                box["value"] = action()
            except BaseException as exc:  # noqa: BLE001  (re-raised on main)
                box["error"] = exc

        buf = io.StringIO()
        thread = threading.Thread(target=worker, daemon=True)
        sys.stdout = buf
        thread.start()
        try:
            if ptype == "spinner":
                i = 0
                while thread.is_alive():
                    self._draw(real_out, ptype, frames, i, final_idx, total, final_stage, label, code)
                    i += 1
                    time.sleep(_TICK)
            else:
                # bar: a static fill at the execute step — steps, not motion.
                self._draw(real_out, ptype, frames, 0, final_idx, total, final_stage, label, code)
                while thread.is_alive():
                    time.sleep(_TICK)
        finally:
            thread.join()
            sys.stdout = real_out

        # Done: fill to total/total on its own line.
        self._draw(real_out, ptype, frames, 0, total, total, "done", label, code, newline=True)

        # Flush the action's captured output (prints + result render) in order.
        captured = buf.getvalue()
        if captured:
            real_out.write(captured)
            real_out.flush()

        if "error" in box:
            raise box["error"]
        return box.get("value")
