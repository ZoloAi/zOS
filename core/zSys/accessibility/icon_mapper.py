"""
Bootstrap Icons Mapper Module

Maps Bootstrap Icons names to appropriate representations based on rendering mode:
- Unicode codepoints (from bootstrap-icons.json)
- Emoji equivalents (curated fallbacks for terminal UX)
- HTML class names (for Bifrost web rendering)

Features:
- Lazy loading (no file access until first use)
- Singleton pattern (shared instance)
- Mode-aware rendering (zCLI vs zBifrost)
- Emoji fallbacks for common icons
- Graceful degradation

Usage:
    from zSys.accessibility import get_icon_mapper
    
    icons = get_icon_mapper()
    
    # Bifrost mode (web)
    icons.render_for_mode("bi-tools", mode="zBifrost")
    # Returns: '<i class="bi bi-tools"></i>'
    
    # zCLI mode (terminal)
    icons.render_for_mode("bi-tools", mode="zCLI")
    # Returns: '[tools]' (always the [name] description in terminal)
    
    # With size/color
    icons.render_for_mode("bi-tools", mode="zBifrost", color="zText-primary")
    # Returns: '<span class="zTitle-2 zText-primary"><i class="bi bi-tools"></i></span>'

Author: zOS Framework
Version: 1.0.0
Date: 2026-03-24
"""

import html
import re
from typing import List, Optional, Dict, Tuple

# An icon token inside an icon-aware label: a Bootstrap name like `bi-rocket-takeoff`.
# Lowercase alphanumerics in dash-joined segments — the only reserved shape a label
# treats as an icon (everything else is literal, string-first).
_ICON_TOKEN_RE = re.compile(r"bi-[a-z0-9]+(?:-[a-z0-9]+)*")

from ._data import load_data_json, BOOTSTRAP_ICONS_FILE
from .sanitize import safe_icon_name, safe_class_attr


# Curated emoji fallbacks for common Bootstrap Icons
# Provides better terminal UX than raw Unicode codepoints
ICON_TO_EMOJI_FALLBACK = {
    # Tools & Development
    "tools": "🔧",
    "hammer": "🔨",
    "wrench": "🔧",
    "gear": "⚙️",
    "gear-fill": "⚙️",
    "rocket": "🚀",
    "rocket-fill": "🚀",
    "rocket-takeoff": "🚀",
    "rocket-takeoff-fill": "🚀",
    "code": "💻",
    "code-slash": "<//>",
    "code-square": "💻",
    "terminal": "⌨️",
    "terminal-fill": "⌨️",
    
    # Navigation & Direction
    "compass": "🧭",
    "compass-fill": "🧭",
    "map": "🗺️",
    "map-fill": "🗺️",
    "arrow-right": "→",
    "arrow-left": "←",
    "arrow-up": "↑",
    "arrow-down": "↓",
    "arrow-return-left": "↩",
    "arrow-return-right": "↪",
    "chevron-right": "›",
    "chevron-left": "‹",
    "chevron-up": "^",
    "chevron-down": "v",
    
    # Ideas & Learning
    "lightbulb": "💡",
    "lightbulb-fill": "💡",
    "book": "📖",
    "book-fill": "📖",
    "book-half": "📖",
    "journal": "📓",
    "journal-text": "📓",
    "mortarboard": "🎓",
    "mortarboard-fill": "🎓",
    
    # Home & Buildings
    "house": "🏠",
    "house-fill": "🏠",
    "house-door": "🏠",
    "house-door-fill": "🏠",
    "building": "🏢",
    "building-fill": "🏢",
    
    # Search & Discovery
    "search": "🔍",
    "binoculars": "🔭",
    "binoculars-fill": "🔭",
    "eye": "👁",
    "eye-fill": "👁",
    
    # Status & Feedback
    "check": "✓",
    "check-lg": "✓",
    "check-circle": "✓",
    "check-circle-fill": "✓",
    "check-square": "☑",
    "check-square-fill": "☑",
    "x": "✗",
    "x-circle": "✗",
    "x-circle-fill": "✗",
    "exclamation": "!",
    "exclamation-circle": "⚠",
    "exclamation-triangle": "⚠",
    "question": "?",
    "question-circle": "?",
    "info": "ℹ",
    "info-circle": "ℹ",
    
    # Files & Documents
    "file": "📄",
    "file-text": "📄",
    "file-earmark": "📄",
    "file-earmark-text": "📄",
    "folder": "📁",
    "folder-fill": "📁",
    "folder2": "📂",
    "folder2-open": "📂",
    
    # Communication
    "chat": "💬",
    "chat-fill": "💬",
    "chat-dots": "💬",
    "chat-quote": "💬",
    "envelope": "✉",
    "envelope-fill": "✉",
    "telephone": "📞",
    "telephone-fill": "📞",
    
    # Media
    "image": "🖼️",
    "image-fill": "🖼️",
    "camera": "📷",
    "camera-fill": "📷",
    "film": "🎬",
    "music-note": "🎵",
    "music-note-beamed": "🎶",
    
    # People
    "person": "👤",
    "person-fill": "👤",
    "people": "👥",
    "people-fill": "👥",
    
    # Time
    "clock": "🕐",
    "clock-fill": "🕐",
    "alarm": "⏰",
    "alarm-fill": "⏰",
    "calendar": "📅",
    "calendar-fill": "📅",
    
    # Actions
    "trash": "🗑️",
    "trash-fill": "🗑️",
    "pencil": "✏️",
    "pencil-fill": "✏️",
    "pencil-square": "✏️",
    "download": "⬇",
    "upload": "⬆",
    "save": "💾",
    "save-fill": "💾",
    
    # UI Elements
    "star": "★",
    "star-fill": "★",
    "heart": "♥",
    "heart-fill": "♥",
    "plus": "+",
    "plus-circle": "+",
    "dash": "−",
    "dash-circle": "−",
    
    # Grid & Layout
    "grid": "▦",
    "grid-fill": "▦",
    "grid-3x3": "▦",
    "list": "☰",
    "list-ul": "•",
    "list-ol": "1.",
}


class IconMapper:
    """
    Bootstrap Icons mapper with lazy loading and mode-aware rendering.
    
    Loads icon → codepoint mappings from bootstrap-icons.json on first access.
    Provides emoji fallbacks for better terminal UX.
    Cached in memory for performance.
    
    Attributes:
        _data: Dictionary of icon_name → Unicode codepoint (None until loaded)
        _loaded: Whether data has been loaded from disk
    """

    def __init__(self):
        """Initialize with lazy loading (no file access yet)."""
        self._data: Optional[Dict[str, int]] = None
        self._loaded: bool = False

    def load(self) -> None:
        """
        Load Bootstrap Icons mappings from JSON file (if not already loaded).
        
        Only loads once per instance (singleton pattern).
        Falls back gracefully if file not found or invalid.
        """
        # Already loaded - return immediately
        if self._loaded:
            return

        # Shared loader resolves zSys/data and degrades to {} on any error.
        self._data = load_data_json(BOOTSTRAP_ICONS_FILE)
        self._loaded = True

    def render_for_mode(
        self,
        icon_name: str,
        mode: Optional[str] = None,
        color: Optional[str] = None
    ) -> str:
        """
        Render icon appropriately for the given mode.
        
        Args:
            icon_name: Bootstrap icon name (with or without 'bi-' prefix)
                      Examples: "tools", "bi-tools", "compass", "bi-compass"
            mode: Rendering mode - "zBifrost" (web) or "zCLI" (terminal)
            color: Optional SEMANTIC colour value for Bifrost (primary, info,
                   warning, …) — mapped to the canonical .zText-<sem> class.
        
        Returns:
            Rendered icon string:
            - zBifrost: HTML <i> tag (optionally wrapped in <span> with classes)
            - zCLI: Emoji fallback, Unicode character, or [icon-name] text
        
        Examples:
            >>> icons = IconMapper()
            >>> icons.render_for_mode("tools", "zBifrost")
            '<i class="bi bi-tools"></i>'
            >>> icons.render_for_mode("bi-tools", "zCLI")
            '[tools]'
            >>> icons.render_for_mode("tools", "zBifrost", color="primary")
            '<span class="zText-primary"><i class="bi bi-tools"></i></span>'
        """
        # Canonical zMode vocabulary (lazy: zSys is Layer-0, no top-level zOS import).
        from zOS.zVocabulary import ZMODE_ZBIFROST  # pylint: disable=import-outside-toplevel
        if mode is None:
            mode = ZMODE_ZBIFROST

        # Strip 'bi-' prefix for terminal lookups / text fallback (inert in zCLI).
        clean_name = icon_name.removeprefix("bi-") if icon_name else ""

        if mode == ZMODE_ZBIFROST:
            # Web mode - emits raw HTML, so everything interpolated must be
            # validated at this trust boundary (fail closed against XSS).
            safe_name = safe_icon_name(icon_name)
            if not safe_name:
                # Unvalidated name -> never build markup; show inert escaped text.
                return html.escape(f"[{clean_name}]")

            icon_html = f'<i class="bi bi-{safe_name}"></i>'

            # color is a SEMANTIC value (primary/info/warning/…), same contract as
            # the JS IconRenderer. Map it to the canonical .zText-<sem> class — those
            # names are the SSOT in zbase.css, so we derive the class by convention
            # instead of duplicating a colour table across languages. A value already
            # shaped like a zText-* class passes through unchanged.
            color_class = ""
            if color:
                c = color.strip()
                color_class = c if c.lower().startswith("ztext-") else f"zText-{c.lower()}"
            classes = [c for c in (safe_class_attr(color_class),) if c]
            if classes:
                return f'<span class="{" ".join(classes)}">{icon_html}</span>'

            return icon_html

        # zCLI mode (terminal) — ALWAYS the [name] description, never an emoji.
        #
        # Decision (2026-06): drop the curated-emoji layer + supports_emoji() gate
        # for icons. The old path was "clever" — curated icons got an emoji, the
        # rest got [name] — which produced inconsistent, font-dependent output
        # (e.g. bi-terminal → ⌨️ keyboard, a misleading glyph) and on a true
        # terminal the emoji was usually re-bracketed to [description] downstream
        # anyway (the double-hop through convert_emojis_for_terminal). A single
        # [name] form is predictable, font-independent, ANSI-safe, and screen-
        # reader-clean — every icon reads the same way everywhere.
        #
        # (ICON_TO_EMOJI_FALLBACK / has_emoji_fallback are retained for callers
        # that ask the question explicitly, but rendering no longer consults them.)
        return f"[{clean_name}]"

    def describe(self, icon_name: str) -> str:
        """Human-readable accessible name for an icon (aria-label / zCLI label).

        Strips the ``bi-`` prefix and turns dashes into spaces so a bare ``zIcon``
        can stand in for a missing label — e.g. ``bi-rocket-takeoff`` → ``"rocket
        takeoff"``. Pure string transform (no file I/O); the SSOT used whenever an
        icon must speak for itself (a zBtn with an icon but no label).

        Args:
            icon_name: Icon name (with or without ``bi-`` prefix).

        Returns:
            Spaced, prefix-free name, or "" when nothing usable was given.
        """
        clean_name = icon_name.removeprefix("bi-").strip() if icon_name else ""
        return clean_name.replace("-", " ") if clean_name else ""

    def split_label(self, label: str) -> Tuple[List[str], str]:
        """Split an icon-aware label into (icon_names, text).

        Whitespace tokens matching ``bi-<name>`` are icons (kept in order); every
        other token is literal text (joined with spaces). Lets a caller that needs
        the parts separately — e.g. the Bifrost button event, which still ships a
        structured ``zIcon`` field — avoid re-implementing the token rule.

        Args:
            label: The raw label string (may contain ``bi-*`` tokens).

        Returns:
            (icon_names, text): icon tokens in order, and the remaining words.
        """
        if not label:
            return [], ""
        icons: List[str] = []
        words: List[str] = []
        for tok in label.split():
            if _ICON_TOKEN_RE.fullmatch(tok):
                icons.append(tok)
            else:
                words.append(tok)
        return icons, " ".join(words)

    def render_inline(
        self,
        label: str,
        mode: Optional[str] = None,
        color: Optional[str] = None,
    ) -> str:
        """Render an icon-aware label in place: ``bi-*`` tokens → glyphs, text kept.

        Order-preserving — each ``bi-<name>`` token becomes its mode rendering
        (HTML ``<i>`` in Bifrost, emoji/``[name]`` in zCLI) while other tokens pass
        through untouched. This is the SSOT behind "label is icon-aware": one
        declaration, the right glyph for wherever it lands, any number of icons.

        Args:
            label: Icon-aware label (e.g. ``"bi-rocket-takeoff Deploy"``).
            mode: Rendering mode (defaults to Bifrost, like render_for_mode).
            color: Optional color class (Bifrost only).

        Returns:
            The label with icon tokens replaced by mode-appropriate glyphs.
        """
        if not label:
            return ""
        return " ".join(
            self.render_for_mode(tok, mode, color)
            if _ICON_TOKEN_RE.fullmatch(tok) else tok
            for tok in label.split()
        )

    def get_codepoint(self, icon_name: str) -> Optional[int]:
        """
        Get Unicode codepoint for an icon.
        
        Args:
            icon_name: Icon name (with or without 'bi-' prefix)
        
        Returns:
            Unicode codepoint as integer, or None if not found
        
        Example:
            >>> icons = IconMapper()
            >>> icons.get_codepoint("tools")
            62134
        """
        clean_name = icon_name.removeprefix("bi-") if icon_name else ""
        self.load()
        return self._data.get(clean_name) if self._data else None

    def has_emoji_fallback(self, icon_name: str) -> bool:
        """
        Check if icon has a curated emoji fallback.
        
        Args:
            icon_name: Icon name (with or without 'bi-' prefix)
        
        Returns:
            True if emoji fallback exists, False otherwise
        """
        clean_name = icon_name.removeprefix("bi-") if icon_name else ""
        return clean_name in ICON_TO_EMOJI_FALLBACK


# Singleton instance
_icon_mapper_instance: Optional[IconMapper] = None


def get_icon_mapper() -> IconMapper:
    """
    Get singleton IconMapper instance.
    
    Returns:
        Shared IconMapper instance (created on first call)
    
    Example:
        >>> from zSys.accessibility import get_icon_mapper
        >>> icons = get_icon_mapper()
        >>> icons.render_for_mode("tools", "zCLI")
        '🔧'
    """
    global _icon_mapper_instance
    if _icon_mapper_instance is None:
        _icon_mapper_instance = IconMapper()
    return _icon_mapper_instance
