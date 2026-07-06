# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/e_advanced/timebased_swiper.py
"""
TimeBased Swiper Events - Interactive Content Carousel
=======================================================

This module provides interactive content carousels (swipers) with keyboard
navigation, auto-advance, and touch gesture support. Swipers display multiple
slides with smooth transitions and user controls.

Purpose:
    - Display multi-slide content carousels
    - Support keyboard navigation (arrow keys, numbers)
    - Auto-advance with configurable delay
    - Box-drawing UI for Terminal, WebSocket events for Bifrost

Public Methods:
    swiper(slides, label, auto_advance, delay, loop)
        Display interactive content carousel with navigation

Dependencies:
    - display_event_helpers: is_bifrost_mode, emit_websocket_event, generate_event_id
    - display_primitives: zPrimitives for terminal I/O
    - display_constants: Event names, keys, defaults, box-drawing characters

Extracted From:
    display_event_timebased.py (lines 959-1219)
"""

import io
import os

from zOS import sys, time, Any, Optional, List

# In-place repaint idiom (same SSOT as zProgress): clear a line and rewrite it,
# never clear the whole screen. Multi-line frames move the cursor up first so the
# swiper redraws ONLY its own region and leaves the feed above it untouched.
_ANSI_CLEAR_LINE = "\r\033[2K"
_ANSI_CURSOR_UP = "\033[{n}A"

# Import event ID utility
from .event_id_utils import generate_event_id  # pylint: disable=relative-beyond-top-level

# Import Tier 1 primitives
from .timebased_utilities import ActiveStateManager  # pylint: disable=relative-beyond-top-level

# Import constants
from ..display_constants import (  # pylint: disable=relative-beyond-top-level
    _EVENT_SWIPER_INIT,
    _KEY_EVENT,
    _KEY_SWIPER_ID,
    _KEY_LABEL,
    _KEY_SLIDES,
    _KEY_CURRENT_SLIDE,
    _KEY_TOTAL_SLIDES,
    _KEY_AUTO_ADVANCE,
    _KEY_DELAY,
    _KEY_LOOP,
    _KEY_CONTAINER,
    _DEFAULT_LABEL_SLIDES,
    _DEFAULT_CONTAINER,
    DEFAULT_SWIPER_DELAY,
    DEFAULT_AUTO_ADVANCE,
    DEFAULT_LOOP,
    DEFAULT_SWIPER_WIDTH,
    _CHAR_SPACE,
    _BOX_TOP_LEFT,
    _BOX_TOP_RIGHT,
    _BOX_BOTTOM_LEFT,
    _BOX_BOTTOM_RIGHT,
    _BOX_HORIZONTAL,
    _BOX_VERTICAL,
    _BOX_LEFT_T,
    _BOX_RIGHT_T,
    _SWIPER_CMD_PREV,
    _SWIPER_CMD_NEXT,
    _SWIPER_CMD_PAUSE,
    _SWIPER_CMD_QUIT,
    _ESC_KEY,
    _ARROW_RIGHT,
    _ARROW_LEFT,
    _SWIPER_STATUS_PAUSED,
    _SWIPER_STATUS_AUTO,
    _SWIPER_STATUS_MANUAL,
    _MSG_SWIPER_COMPLETED
)


class SwiperEvents:
    """
    Interactive content carousel events with keyboard navigation.
    
    Provides swiper() for displaying multi-slide content with auto-advance,
    keyboard navigation, and box-drawing UI in Terminal or WebSocket events
    in Bifrost mode.
    
    Composition:
        - zPrimitives: For terminal I/O (raw, line)
        - BasicOutputs: For fallback rendering
        - ActiveStateManager: For tracking active swipers (Bifrost)
    
    Usage:
        # Via TimeBased coordinator
        slides = ["Slide 1 content", "Slide 2 content", "Slide 3 content"]
        display.swiper(slides, label="Tutorial", auto_advance=True, delay=3)
    """

    # Class-level type declarations
    display: Any
    zPrimitives: Any
    BasicOutputs: Optional[Any]
    _active_state: ActiveStateManager

    def __init__(self, display_instance: Any) -> None:
        """
        Initialize SwiperEvents with reference to parent display instance.
        
        Args:
            display_instance: Parent display instance (TimeBased or zDisplay)
        
        Returns:
            None
        """
        self.display = display_instance
        self.zPrimitives = (
            display_instance.zPrimitives if hasattr(display_instance, 'zPrimitives') else None
        )
        self.BasicOutputs = None  # Will be set after zEvents initialization
        self._active_state = (
            display_instance._active_state if hasattr(display_instance, '_active_state')
            else ActiveStateManager()
        )
        # Number of lines the current in-place frame occupies (0 = nothing painted
        # yet). Used to move the cursor back up and repaint only our own region.
        self._painted = 0

    def swiper(
        self,
        slides: List[str],
        label: str = _DEFAULT_LABEL_SLIDES,
        auto_advance: bool = DEFAULT_AUTO_ADVANCE,
        delay: int = DEFAULT_SWIPER_DELAY,
        loop: bool = DEFAULT_LOOP,
        folder: Optional[str] = None
    ) -> None:
        """
        Display interactive content carousel with keyboard navigation.
        
        Args:
            slides: List of content strings to display (one per slide)
            label: Title for the swiper (str, default "Slides")
            auto_advance: Auto-advance slides (bool, default True)
            delay: Seconds between auto-advances (int, default 3)
            loop: Loop back to start (bool, default True)
        
        Returns:
            None
        
        Terminal Navigation:
            - Arrow keys (◀▶): Navigate prev/next
            - Number keys (1-9): Jump to specific slide
            - 'p': Pause/resume auto-advance
            - 'q': Quit swiper
        
        Bifrost Navigation:
            - Touch gestures: Swipe left/right
            - WebSocket events for slide changes
        
        Usage:
            slides = [
                "Welcome to the tutorial",
                "Step 1: Configuration",
                "Step 2: Implementation"
            ]
            display.swiper(slides, label="Getting Started", auto_advance=True)
        
        Notes:
            - Terminal: Box-drawing UI with keyboard input
            - Bifrost: WebSocket events for React carousel component
            - Windows fallback: Simple Enter/q navigation (no termios)
        """
        if not slides:
            return

        # Generate unique ID
        swiper_id = generate_event_id("swiper", label)

        # zBifrost mode - emit WebSocket events
        if self.display.zPrimitives.is_bifrost_mode():
            # Initialize swiper
            init_event = {
                _KEY_EVENT: _EVENT_SWIPER_INIT,
                _KEY_SWIPER_ID: swiper_id,
                _KEY_LABEL: label,
                _KEY_SLIDES: slides,
                _KEY_CURRENT_SLIDE: 0,
                _KEY_TOTAL_SLIDES: len(slides),
                _KEY_AUTO_ADVANCE: auto_advance,
                _KEY_DELAY: delay,
                _KEY_LOOP: loop,
                _KEY_CONTAINER: _DEFAULT_CONTAINER
            }
            self.display.zPrimitives.emit_websocket_event(init_event)
            self._active_state.register(swiper_id, init_event)

            # Bifrost handles navigation via WebSocket, so we just return
            # Frontend will emit swiper_update and swiper_complete events
            return

        # zCLI mode - interactive carousel
        # Check if termios is available (Unix-like systems)
        try:
            import termios
            import tty
            import select
            has_termios = True
        except ImportError:
            has_termios = False

        is_tty = has_termios and sys.stdin.isatty()

        # Tier 2 — page slides: each slide name is a real zUI page in `folder`,
        # loaded like a zDash panel and rendered FLAT (inert) so the carousel is
        # never blocked by the page's buttons/inputs/links. Pages are read-paced,
        # so navigation is manual (no auto-advance).
        if folder:
            if is_tty:
                self._swiper_pages_interactive(slides, label, folder, loop, termios, tty, select)
            else:
                self._swiper_pages_static(slides, label, folder)
            return

        # The interactive carousel needs a real TTY (termios raw mode). Without
        # one — Windows, piped stdin, CI, captured output — render every slide
        # sequentially instead of driving a keyboard loop.
        if not is_tty:
            self._swiper_static(slides, label)
            return

        # Full terminal swiper with keyboard navigation
        self._swiper_terminal(slides, label, auto_advance, delay, loop, termios, tty, select)

    def _render_page_flat(self, folder: str, name: str) -> None:
        """Load a zUI page from `folder` and render it inert (zFlat).

        Mirrors zDash's panel loader (loader.handle → strip zMeta/zRBAC →
        launcher.launch), wrapped in the flat flag so interactive widgets render
        their visual affordance without prompting. SSOT: same load+dispatch path
        a dashboard panel uses; the only difference is the passive render flag.
        """
        # SwiperEvents.display is the TimeBased coordinator; zos lives on the
        # real zDisplay it wraps (self.display.display.zos).
        zos = getattr(self.display, "zos", None)
        if zos is None:
            zos = getattr(getattr(self.display, "display", None), "zos", None)
        loader = getattr(zos, "loader", None)
        dispatch = getattr(zos, "dispatch", None)
        session = getattr(zos, "session", None)
        if not (loader and dispatch and hasattr(dispatch, "launcher")):
            if self.zPrimitives:
                self.zPrimitives.line(f"(cannot render page: {name})")
            return

        zlink = f"{folder}.zUI.{name}"

        # Flat flag wraps BOTH load and launch so the loader's own breadcrumbs
        # (zLoader/zPath decoder/Reading) are suppressed too — not just dispatch.
        prev = session.get("_zflat", 0) if isinstance(session, dict) else 0
        if isinstance(session, dict):
            session["_zflat"] = prev + 1
        try:
            try:
                page = loader.handle(zPath=zlink)
            except Exception:  # noqa: BLE001
                page = None
            if not page:
                if self.zPrimitives:
                    self.zPrimitives.line(f"(missing page: {name})")
                return

            block = page.get(name, page)
            if isinstance(block, dict):
                block = {k: v for k, v in block.items() if k not in ("zMeta", "zRBAC")}

            dispatch.launcher.launch(block, context=None, walker=None)
        finally:
            if isinstance(session, dict):
                session["_zflat"] = prev

    def _swiper_pages_static(self, slides: List[str], label: str, folder: str) -> None:
        """Non-interactive page render (CI / piped): every page in order, flat."""
        if not self.zPrimitives:
            return
        total = len(slides)
        for idx, name in enumerate(slides, 1):
            self.zPrimitives.line("")
            self.zPrimitives.line(f"── {label} · {idx}/{total} · {name} " + _BOX_HORIZONTAL * 12)
            self._render_page_flat(folder, name)
        self.zPrimitives.line(_MSG_SWIPER_COMPLETED)

    def _paint(self, lines: List[str]) -> None:
        """Repaint `lines` in place, like zProgress — never clears the screen.

        First call prints the block where the cursor sits (bottom of the feed).
        Later calls move the cursor up over the previous frame and rewrite each
        line (clearing it first). A shorter new frame blanks the leftover rows so
        nothing from the taller previous frame lingers. Everything ABOVE the block
        is left intact.
        """
        out = sys.stdout
        chunks: List[str] = []
        if self._painted:
            chunks.append(_ANSI_CURSOR_UP.format(n=self._painted))
        for ln in lines:
            chunks.append(_ANSI_CLEAR_LINE + ln + "\n")
        leftover = self._painted - len(lines)
        if leftover > 0:
            for _ in range(leftover):
                chunks.append(_ANSI_CLEAR_LINE + "\n")
            chunks.append(_ANSI_CURSOR_UP.format(n=leftover))
        out.write("".join(chunks))
        out.flush()
        self._painted = len(lines)

    def _finish_paint(self) -> None:
        """Release the in-place region so subsequent output appends to the feed."""
        self._painted = 0

    def _capture_lines(self, render: Any) -> List[str]:
        """Run `render()` with stdout captured and return its output as lines.

        Page slides render through normal dispatch (print → sys.stdout). Capturing
        lets us repaint that content in place instead of clearing the screen.
        """
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            render()
        finally:
            sys.stdout = old
        text = buf.getvalue().rstrip("\n")
        return text.split("\n") if text else []

    def _read_key(self, termios: Any, tty: Any, select: Any) -> str:
        """Read one keypress in cbreak mode then restore the prior settings.

        Reads via os.read on the raw fd — NOT sys.stdin.read. sys.stdin is a
        buffered TextIOWrapper: reading the ESC pulls the rest of the arrow burst
        (e.g. '[C') into Python's internal buffer, so a select() on the fd then
        sees nothing and the tail is lost — that was why Tour arrows died while
        numbers (single byte) worked. os.read keeps select() and the read in sync.
        """
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            # setcbreak (NOT setraw): keeps ISIG so Ctrl+C fires a real SIGINT into
            # zOS's integrated shutdown. TCSANOW (not default TCSAFLUSH): don't
            # flush queued input, or arrows pressed during the page render vanish.
            tty.setcbreak(fd, termios.TCSANOW)
            key = os.read(fd, 1).decode(errors="ignore")
            # Arrow keys arrive as a burst: CSI (ESC [ C) or SS3 (ESC O C). Drain
            # the tail from the fd and decode by the final letter, normalizing both
            # forms to the CSI constant the loop compares against.
            if key == _ESC_KEY and select.select([fd], [], [], 0.2)[0]:
                seq = os.read(fd, 8).decode(errors="ignore")
                if seq[-1:] in ("A", "B", "C", "D"):
                    key = _ESC_KEY + "[" + seq[-1]
                else:
                    key += seq
            return key
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def _swiper_pages_interactive(
        self, slides: List[str], label: str, folder: str, loop: bool,
        termios: Any, tty: Any, select: Any
    ) -> None:
        """Manual page viewer: clear → header → flat page → footer → one key."""
        if not self.zPrimitives:
            return
        current = 0
        total = len(slides)
        running = True
        self._finish_paint()
        while running:
            jump = f"1-{total}:Jump | " if total > 1 else ""
            header = [
                f"{label} · {current + 1}/{total} · {slides[current]}",
                _BOX_HORIZONTAL * DEFAULT_SWIPER_WIDTH,
            ]
            body = self._capture_lines(
                lambda: self._render_page_flat(folder, slides[current])
            )
            footer = ["", f"◀▶:Navigate | {jump}o:Open | q:Quit"]
            self._paint(header + body + footer)

            key = self._read_key(termios, tty, select)
            if key in (_SWIPER_CMD_QUIT, "q"):
                running = False
            elif key in (_ARROW_RIGHT, _SWIPER_CMD_NEXT):
                current = self._next_slide(current, total, loop)
            elif key in (_ARROW_LEFT, _SWIPER_CMD_PREV):
                current = self._prev_slide(current, total, loop)
            elif key in ("o", "O", "\r", "\n"):
                # zBounce: run the slide's page in the REAL interactive flow,
                # then fall back into the carousel at the same index.
                self._finish_paint()  # let the real flow print into the feed
                self._open_page_real(folder, slides[current])
            elif key.isdigit() and 1 <= int(key) <= total:
                current = int(key) - 1

        self._finish_paint()
        self.zPrimitives.line(_MSG_SWIPER_COMPLETED)

    def _open_page_real(self, folder: str, name: str) -> None:
        """Run a slide's page in the normal (non-flat) interactive flow.

        zBounce semantics: launch the page block with full interactivity (buttons
        prompt, inputs read, links offer y/n) and return to the carousel when the
        page's own flow completes. Self-contained pages bounce cleanly; pages that
        navigate AWAY (zURL internal → walker) are the open design question.
        """
        zos = getattr(self.display, "zos", None)
        if zos is None:
            zos = getattr(getattr(self.display, "display", None), "zos", None)
        loader = getattr(zos, "loader", None)
        dispatch = getattr(zos, "dispatch", None)
        if not (loader and dispatch and hasattr(dispatch, "launcher")):
            return

        try:
            page = loader.handle(zPath=f"{folder}.zUI.{name}")
        except Exception:  # noqa: BLE001
            page = None
        if not page:
            return
        block = page.get(name, page)
        if isinstance(block, dict):
            block = {k: v for k, v in block.items() if k not in ("zMeta", "zRBAC")}

        # The page flow prints straight into the feed below the carousel — no
        # screen clear. NOTE: no _zflat flag → real flow. walker=None keeps it
        # scoped to the page; navigation primitives that need a walker are inert.
        dispatch.launcher.launch(block, context=None, walker=None)
        # Cooked mode here — a blocking prompt lets the user read the page's final
        # output before the loop repaints the carousel (zBounce complete).
        try:
            input("\n↩ Enter to return to the deck… ")
        except (EOFError, KeyboardInterrupt):
            pass

    def _swiper_static(self, slides: List[str], label: str) -> None:
        """Non-interactive render: print each slide as a labelled box, in order.

        Used when there is no interactive TTY (CI, piped output). No screen
        clearing, no input — just the full deck so the content is still shown.
        """
        if not self.zPrimitives:
            return
        total = len(slides)
        width = DEFAULT_SWIPER_WIDTH
        for idx, slide in enumerate(slides, 1):
            top = _BOX_TOP_LEFT + _BOX_HORIZONTAL * (width - 2) + _BOX_TOP_RIGHT
            title_text = f"{label} - Slide {idx}/{total}"
            title_line = _BOX_VERTICAL + _CHAR_SPACE + title_text.ljust(width - 4) + _CHAR_SPACE + _BOX_VERTICAL
            sep = _BOX_LEFT_T + _BOX_HORIZONTAL * (width - 2) + _BOX_RIGHT_T
            self.zPrimitives.line(top)
            self.zPrimitives.line(title_line)
            self.zPrimitives.line(sep)
            for line in self._wrap_text(slide, width - 4):
                self.zPrimitives.line(
                    _BOX_VERTICAL + _CHAR_SPACE + line.ljust(width - 4) + _CHAR_SPACE + _BOX_VERTICAL
                )
            self.zPrimitives.line(_BOX_BOTTOM_LEFT + _BOX_HORIZONTAL * (width - 2) + _BOX_BOTTOM_RIGHT)
        self.zPrimitives.line(_MSG_SWIPER_COMPLETED)

    def _swiper_fallback(self, slides: List[str], label: str) -> None:
        """
        Fallback swiper for Windows/systems without termios.
        
        Simple navigation: Press Enter for next slide, 'q' to quit.
        """
        if self.BasicOutputs:
            self.BasicOutputs.header(label, color="INFO", style="full")

        for idx, slide in enumerate(slides, 1):
            if self.zPrimitives:
                self.zPrimitives.line(f"\n[Slide {idx}/{len(slides)}]")
                self.zPrimitives.line(slide)

                if idx < len(slides):
                    user_input = input("\nPress Enter for next slide (or 'q' to quit): ").strip().lower()
                    if user_input == 'q':
                        break

        if self.zPrimitives:
            self.zPrimitives.line(_MSG_SWIPER_COMPLETED)

    def _swiper_terminal(
        self,
        slides: List[str],
        label: str,
        auto_advance: bool,
        delay: int,
        loop: bool,
        termios: Any,
        tty: Any,
        select: Any
    ) -> None:
        """
        Full-featured terminal swiper with keyboard navigation.
        
        Uses termios for non-blocking keyboard input and box-drawing characters
        for beautiful UI.
        """
        current_slide = 0
        is_paused = False
        running = True
        last_advance = time.time()

        # Save terminal settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            # setcbreak (not setraw): keeps ISIG so Ctrl+C → real SIGINT → zOS
            # shutdown. TCSANOW so switching modes doesn't flush queued input.
            tty.setcbreak(fd, termios.TCSANOW)
            self._finish_paint()

            # Only repaint when the slide or pause state actually changes —
            # repainting every poll causes flicker and a runaway scroll.
            prev_state = None

            # Main swiper loop
            while running:
                state = (current_slide, is_paused)
                if state != prev_state:
                    self._render_slide_box(
                        slides[current_slide], label, current_slide + 1,
                        len(slides), is_paused, auto_advance
                    )
                    prev_state = state

                # Check for keyboard input (non-blocking)
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1)

                    # Handle escape sequences (arrow keys)
                    if key == _ESC_KEY:
                        key += sys.stdin.read(2)  # Read [A or [B or [C or [D

                    # Process key commands
                    if key == _SWIPER_CMD_QUIT or key == 'q':
                        running = False
                    elif key == _SWIPER_CMD_PAUSE or key == 'p':
                        is_paused = not is_paused
                        last_advance = time.time()  # Reset timer on pause toggle
                    elif key == _ARROW_RIGHT or key == _SWIPER_CMD_NEXT:
                        current_slide = self._next_slide(current_slide, len(slides), loop)
                        last_advance = time.time()
                    elif key == _ARROW_LEFT or key == _SWIPER_CMD_PREV:
                        current_slide = self._prev_slide(current_slide, len(slides), loop)
                        last_advance = time.time()
                    elif key.isdigit() and 1 <= int(key) <= len(slides):
                        current_slide = int(key) - 1
                        last_advance = time.time()

                # Auto-advance logic
                if auto_advance and not is_paused:
                    if time.time() - last_advance >= delay:
                        next_idx = self._next_slide(current_slide, len(slides), loop)
                        if next_idx == 0 and not loop:
                            # Reached end without loop
                            running = False
                        else:
                            current_slide = next_idx
                            last_advance = time.time()

        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            # Release the in-place region and finalize below the deck — the feed
            # above the swiper stays intact (no screen clear).
            if self.zPrimitives:
                self._finish_paint()
                self.zPrimitives.line(_MSG_SWIPER_COMPLETED)

    def _render_slide_box(
        self,
        content: str,
        title: str,
        current: int,
        total: int,
        is_paused: bool,
        auto_advance: bool = True
    ) -> None:
        """Render slide with box-drawing UI, repainted in place.

        The box is redrawn over its own region (cursor-up + clear-line per row)
        so the feed above it is never erased — no full-screen clear.
        """
        if not self.zPrimitives:
            return

        width = DEFAULT_SWIPER_WIDTH
        status = (
            _SWIPER_STATUS_PAUSED if is_paused
            else (_SWIPER_STATUS_AUTO if auto_advance else _SWIPER_STATUS_MANUAL)
        )
        title_text = f"{title} - Slide {current}/{total} {status}"

        rows = [
            _BOX_TOP_LEFT + _BOX_HORIZONTAL * (width - 2) + _BOX_TOP_RIGHT,
            _BOX_VERTICAL + _CHAR_SPACE + title_text.ljust(width - 4) + _CHAR_SPACE + _BOX_VERTICAL,
            _BOX_LEFT_T + _BOX_HORIZONTAL * (width - 2) + _BOX_RIGHT_T,
        ]
        for line in self._wrap_text(content, width - 4):
            rows.append(
                _BOX_VERTICAL + _CHAR_SPACE + line.ljust(width - 4) + _CHAR_SPACE + _BOX_VERTICAL
            )
        rows.append(_BOX_BOTTOM_LEFT + _BOX_HORIZONTAL * (width - 2) + _BOX_BOTTOM_RIGHT)
        rows.append("")
        # Jump hint reflects the real slide count (digit keys are bounded to it).
        jump = f"1-{total}:Jump | " if total > 1 else ""
        rows.append(f"◀▶:Navigate | {jump}p:Pause | q:Quit")

        self._paint(rows)

    def _wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to fit within specified width."""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_len = len(word)
            if current_length + word_len + len(current_line) <= width:
                current_line.append(word)
                current_length += word_len
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_len

        if current_line:
            lines.append(' '.join(current_line))

        return lines if lines else [""]

    def _next_slide(self, current: int, total: int, loop: bool) -> int:
        """Calculate next slide index."""
        next_idx = current + 1
        if next_idx >= total:
            return 0 if loop else current
        return next_idx

    def _prev_slide(self, current: int, total: int, loop: bool) -> int:
        """Calculate previous slide index."""
        prev_idx = current - 1
        if prev_idx < 0:
            return total - 1 if loop else 0
        return prev_idx
