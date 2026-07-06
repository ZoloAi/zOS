"""
Inline Markdown Transformer - Handles inline markdown syntax transformations.

Transforms:
- **bold** → ANSI bold
- *italic* → ANSI dim/italic
- `code` → ANSI cyan
- [text](url) → contextual display using ZLinkResolver (SSOT)
- [*](url) → * with info color (footnote style)

Author: zOS Framework
Version: 3.1.0 (ZLinkResolver delegation)
"""

from zOS import re
from zSys.formatting.colors import Colors  # pylint: disable=import-error

# ZLinkResolver: Python SSOT for href classification (shared with display_event_links)
try:
    from zOS.L2_Handling.h_zNavigation.navigation_modules.resolvers.resolver_zlink import (
        ZLinkResolver,
        LINK_TYPE_EXTERNAL,
        LINK_TYPE_ANCHOR,
        LINK_TYPE_PLACEHOLDER,
    )
    _RESOLVER_AVAILABLE = True
except ImportError:
    _RESOLVER_AVAILABLE = False


def parse_link_target(brace):
    """Parse a markdown link attribute brace for an explicit open-target token.

    Mirrors the zbifrost-client text_renderer convention so `[t](url){_blank}`
    means the same thing in the terminal and the browser:
        _blank | newtab | new-tab  -> "_blank"
        _self  | sametab | same-tab -> "_self"
    Returns the target string, or None when no target token is present
    (non-target tokens are CSS classes, ignored in the terminal).
    """
    if not brace:
        return None
    for tok in brace.split():
        t = tok.lower()
        if t in ('_blank', 'newtab', 'new-tab'):
            return '_blank'
        if t in ('_self', 'sametab', 'same-tab'):
            return '_self'
    return None


class InlineTransformer:
    """Transforms inline markdown syntax to ANSI codes."""

    def __init__(self):
        """Initialize with ANSI code constants — sourced from Colors SSOT."""
        self.ANSI_RESET       = Colors.RESET    # \033[0m — full reset (color + style)
        self.ANSI_BOLD        = '\033[1m'       # bold on
        self.ANSI_DIM         = '\033[2m'       # dim on
        self.ANSI_UNDERLINE   = '\033[4m'       # underline on
        self.ANSI_NO_UNDERLINE = '\033[24m'     # underline off — preserves color
        self.ANSI_NORMAL      = '\033[22m'      # normal intensity — turns off bold+dim WITHOUT resetting color
        self.ANSI_CYAN        = Colors.CYAN      # \033[96m — bright cyan  (inline code)
        self.ANSI_HIGHLIGHT   = Colors.EXTERNAL  # \033[30;103m — black text on bright yellow bg
        self.ANSI_RED         = Colors.RED       # \033[91m — bright red    (strikethrough)
        self.ANSI_STRIKE      = '\033[9m'        # strikethrough on

    def transform(self, text: str, wrap_color: str = '', link_sink=None) -> str:
        """
        Apply all inline transformations in correct order.

        wrap_color: optional ANSI open-code for the surrounding text color
        (e.g. '\\033[38;5;75m' for PRIMARY). When provided, spans that change
        color restore it after their override so the outer color is not lost.

        link_sink: optional callable(label, href, target) invoked for each
        navigable link found. When provided, the link label is rendered as
        ==highlighted== and the link is deferred to the sink so the caller
        (MarkdownParser.parse) can fire a display.link() prompt after the
        paragraph completes. target is '_blank'/'_self' from a {…} token, else None.

        Order matters:
        1. Links FIRST — plain-text only; must run before any ANSI codes so the
           pattern [label](href) never consumes a [ from an ANSI escape sequence.
        2. Icons (<bi-name>) — atomic tokens swapped for a glyph before emphasis,
           so a name like <bi-code-slash> is never seen as italic markers.
        3. Highlight / Strikethrough
        4. Code — emits ANSI cyan; safe now that links are already converted.
        5. Bold (**…**)
        6. Underline (__…__) — before italic so __ is not seen as two _ markers.
        7. Italic (*…* / _…_)
        """
        if not text:
            return text

        text = self._convert_links(text, link_sink=link_sink)
        text = self._convert_icons(text)
        text = self._convert_highlight(text, wrap_color)
        text = self._convert_strikethrough(text, wrap_color)
        text = self._convert_code(text, wrap_color)
        text = self._convert_bold(text)
        text = self._convert_underline(text)
        text = self._convert_italic(text)

        return text

    def _convert_code(self, text: str, wrap_color: str = '') -> str:
        """
        Convert `code` to ANSI cyan.

        After the cyan span, emits RESET + wrap_color so the outer text color
        is restored. Without wrap_color, a bare RESET is used (backward compat).
        """
        pattern = r'(?<!`)(`{1})(?!`)([^`\n]+)\1(?!`)'
        restore = f"{self.ANSI_RESET}{wrap_color}" if wrap_color else self.ANSI_RESET

        def replacer(match):
            code_text = match.group(2)
            return f"{self.ANSI_CYAN}{code_text}{restore}"

        return re.sub(pattern, replacer, text)

    def _convert_highlight(self, text: str, wrap_color: str = '') -> str:
        """
        Convert ==highlight== to black text on bright yellow background.

        Uses Colors.EXTERNAL (\033[30;103m) — black fg + bright yellow bg.
        Close with RESET + wrap_color to restore the outer color.
        zTerminal: handled via _ansiBgColorMap '103' + _ansiColorMap '30'.
        """
        pattern = r'==(.+?)=='
        restore = f"{self.ANSI_RESET}{wrap_color}" if wrap_color else self.ANSI_RESET

        def replacer(match):
            return f"{self.ANSI_HIGHLIGHT}{match.group(1)}{restore}"

        return re.sub(pattern, replacer, text)

    def _convert_strikethrough(self, text: str, wrap_color: str = '') -> str:
        """
        Convert ~~strikethrough~~ to red + strikethrough (ANSI 9).

        Uses RESET + wrap_color to close so the outer color is restored.
        zTerminal: \033[91m maps to '#ff6b6b'; \033[9m maps to
        'text-decoration: line-through' in _ansiStyleMap JS.
        """
        pattern = r'~~(.+?)~~'
        restore = f"{self.ANSI_RESET}{wrap_color}" if wrap_color else self.ANSI_RESET

        def replacer(match):
            return f"{self.ANSI_RED}{self.ANSI_STRIKE}{match.group(1)}{restore}"

        return re.sub(pattern, replacer, text)

    def _convert_bold(self, text: str) -> str:
        """
        Convert **bold** to ANSI bold.

        Underscores are NOT bold here — __x__ is underline (see _convert_underline),
        matching the zbifrost-client text_renderer SSOT. Uses \\033[22m (normal
        intensity) to close — preserves outer color.
        """
        pattern = r'\*\*(.+?)\*\*'

        def replacer(match):
            return f"{self.ANSI_BOLD}{match.group(1)}{self.ANSI_NORMAL}"

        return re.sub(pattern, replacer, text)

    def _convert_underline(self, text: str) -> str:
        """
        Convert __underline__ to ANSI underline (\\033[4m).

        Mirrors the zbifrost-client text_renderer (__x__ → <u>). Closes with
        \\033[24m (underline off) so the outer color is preserved. Must run
        before _convert_italic so the __ pair is not split into two _ markers.
        zTerminal: \\033[4m maps to 'text-decoration: underline' in _ansiStyleMap.
        """
        pattern = r'(?<!_)__(?!_)([^_\n]+?)(?<!_)__(?!_)'

        def replacer(match):
            return f"{self.ANSI_UNDERLINE}{match.group(1)}{self.ANSI_NO_UNDERLINE}"

        return re.sub(pattern, replacer, text)

    def _convert_italic(self, text: str) -> str:
        """
        Convert *italic* or _italic_ to ANSI dim.

        Uses \\033[22m (normal intensity) to close — preserves outer color.
        Avoids matching bold markers (**/__).
        """
        pattern = r'(?<!\*)(\*)(?!\*)(.+?)\1(?!\*)|(?<!_)(_)(?!_)(.+?)\3(?!_)'

        def replacer(match):
            italic_text = match.group(2) if match.group(2) else match.group(4)
            return f"{self.ANSI_DIM}{italic_text}{self.ANSI_NORMAL}"

        return re.sub(pattern, replacer, text)

    def _convert_icons(self, text: str) -> str:
        """Convert inline icon tokens ``<bi-name>`` to their zCLI glyph.

        The inline twin of the icon-aware label rule: an angle-bracketed
        ``<bi-name>`` marker (brackets chosen over ``:`` so the token never
        collides with zolo's ``key: value`` dict shape, and over backticks so a
        literal ``bi-*`` code reference stays code) is replaced by IconMapper's
        terminal rendering — a curated emoji, else the ``[name]`` description.
        Same SSOT the zIcon event and icon-aware labels use, so the glyph never
        drifts. Bifrost has its own twin in TextRenderer._parseInline.

        The name shape (lowercase alphanumerics in dash-joined segments) is baked
        into the pattern, so only well-formed tokens are touched; everything else
        passes through string-first.
        """
        # Lazy import: zSys is Layer-0, avoid a top-level zOS dependency here.
        from zSys.accessibility import get_icon_mapper  # pylint: disable=import-outside-toplevel
        from zOS.zVocabulary import ZMODE_ZCLI  # pylint: disable=import-outside-toplevel

        mapper = get_icon_mapper()
        pattern = r'<(bi-[a-z0-9]+(?:-[a-z0-9]+)*)>'

        def replacer(match):
            return mapper.render_for_mode(match.group(1), mode=ZMODE_ZCLI)

        return re.sub(pattern, replacer, text)

    def _convert_links(self, text: str, link_sink=None) -> str:
        """
        Convert markdown links to terminal-readable format.

        Uses ZLinkResolver.classify_href() (Python SSOT) to produce
        contextual output per link type:
          - external:        label (highlighted if link_sink provided)
          - internal_*:      label (highlighted if link_sink provided)
          - anchor:          label (#section)  — no sink, no prompt
          - placeholder:     label              — no sink, no prompt

        When link_sink is provided (callable(label, href)):
        - Navigable links (external, internal) render the label as
          ==highlighted== using ANSI_HIGHLIGHT and defer the prompt
          to the caller via link_sink(label, href). The caller fires
          display.link() after the paragraph, keeping zMD flow clean.
        - Anchor / placeholder links are never sunk — they are not
          navigable and need no y/n prompt.

        Handles:
        - [text](url)              → contextual display
        - [text](url){class}       → class ignored in terminal
        - [text](url){_blank}      → opens in new tab (Bifrost); target recorded on display.link
        - [*](url)                 → * with info color (footnote style)

        Args:
            text: Text with markdown links
            link_sink: optional callable(label, href, target) for navigable links

        Returns:
            Text with links rendered for terminal
        """
        # Capture: label, href, optional {attrs} (target token + classes)
        pattern = r'\[([^\]]+)\]\(([^)]+)\)(?:\{([^}]*)\})?'

        def replacer(match):
            link_text = match.group(1)
            href = match.group(2).strip()
            target = parse_link_target(match.group(3))

            # Special case: footnote-style link [*](url)
            if link_text == '*':
                try:
                    from zSys.formatting.ztheme_to_ansi import (
                        map_ztheme_classes_to_ansi,
                        get_reset_code
                    )
                    ansi_codes = map_ztheme_classes_to_ansi(['zLink-info'])
                    if ansi_codes:
                        return f"{ansi_codes}*{get_reset_code()}"
                except ImportError:
                    pass
                return '*'

            # Delegate type classification to ZLinkResolver SSOT
            if _RESOLVER_AVAILABLE:
                link_type = ZLinkResolver.classify_href(href)

                # Any link type — highlight inline and defer prompt to caller.
                # Anchor / placeholder links return None from display.link()
                # (no navigation), so zMD always continues for them.
                if link_sink is not None:
                    link_sink(link_text, href, target)
                    return f"{self.ANSI_HIGHLIGHT}{link_text}{self.ANSI_RESET}"

                # No sink: fallback to original text-only rendering
                if link_type == LINK_TYPE_ANCHOR:
                    return f"{link_text} ({href})"
                elif link_type == LINK_TYPE_PLACEHOLDER:
                    return link_text
                elif link_type == LINK_TYPE_EXTERNAL:
                    return f"{link_text} ({href})"
                return f"{link_text} [\u2192 {href}]"

            # Fallback if resolver not available: show label and href
            return f"{link_text} ({href})"

        return re.sub(pattern, replacer, text)
