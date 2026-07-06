"""
Markdown Parser - Main orchestrator for markdown parsing and rendering.

Coordinates:
- Inline transformations (bold, italic, code, links)
- HTML processing (tag stripping, class mapping)
- Block extraction (paragraphs, lists, code blocks)
- Syntax highlighting
- Display event emission

Author: zOS Framework
Version: 3.0.0 (Refactored Architecture)
"""

from zOS import TYPE_CHECKING, Optional, re

from .inline_transformer import InlineTransformer
from .html_processor import HTMLProcessor
from .block_extractor import BlockExtractor


if TYPE_CHECKING:
    from ...zDisplay import zDisplay  # type: ignore  # pylint: disable=relative-beyond-top-level


class MarkdownParser:
    """
    Main markdown parser orchestrator.
    
    Converts markdown content to ANSI-formatted text for Terminal display.
    Routes content to appropriate zDisplay events.
    """

    def __init__(self):
        """Initialize parser with component modules."""
        self.inline_transformer = InlineTransformer()
        self.html_processor = HTMLProcessor()
        self.block_extractor = BlockExtractor()

    def parse_inline(self, text: str, wrap_color_ansi: str = '', link_sink=None) -> str:
        """
        Parse inline markdown and HTML.

        wrap_color_ansi: ANSI open-code for the surrounding text color (e.g.
        '\\033[38;5;75m'). Forwarded to InlineTransformer so inline code spans
        can restore the outer color after their cyan override.

        link_sink: optional callable(label, href, target) forwarded to InlineTransformer.
        When provided, navigable links are highlighted inline and deferred so the
        caller can fire display.link() prompts after the paragraph.

        Processing order:
        1. Protect backtick code spans from HTML stripping
        2. Strip HTML tags and map classes to ANSI
        3. Restore backtick code spans (literal content preserved)
        4. Transform inline markdown (code, links, bold, italic)
        """
        if not text:
            return text

        # Protect inline code spans before HTML processing so that literal
        # content like `<br>` or `<span>` is never stripped by the HTML processor.
        _inline_literals: list = []

        def _protect(m: re.Match) -> str:
            _inline_literals.append(m.group(0))  # store full `code` span
            return f'\x03INLINELIT{len(_inline_literals) - 1}\x03'

        text = re.sub(r'(?<!`)`(?!`)([^`\n]+)(?<!`)`(?!`)', _protect, text)

        # Protect inline icon tokens (<bi-name>) too: to the HTML processor they
        # look like a tag and would be stripped, so shield them here and let
        # InlineTransformer._convert_icons swap them for the terminal glyph after
        # restore. Mirrors the Bifrost seam, where the code pass shields them.
        text = re.sub(r'<bi-[a-z0-9]+(?:-[a-z0-9]+)*>', _protect, text)

        # HTML processing (now safe — backtick + icon spans are placeholders)
        text = self.html_processor.process(text)

        # Restore protected inline code spans
        for i, span in enumerate(_inline_literals):
            text = text.replace(f'\x03INLINELIT{i}\x03', span)

        # Inline markdown transformations
        text = self.inline_transformer.transform(text, wrap_color=wrap_color_ansi, link_sink=link_sink)

        return text

    def parse(self, content: str, display: 'zDisplay', indent: int = 0, color: Optional[str] = None) -> None:
        """
        Main entry point for parsing markdown content.
        
        Args:
            content: Markdown content to parse
            display: zDisplay instance for emitting events
            indent: Indentation level for all emitted events
            color: Default color for paragraphs
        """
        try:
            if not content or not isinstance(content, str):
                return

            # Resolve color name → ANSI open-code so inline spans can restore it.
            wrap_color_ansi = ''
            if color:
                try:
                    from ...basic.outputs.semantic_colors import get_semantic_color  # pylint: disable=relative-beyond-top-level
                    wrap_color_ansi = get_semantic_color(color.upper()) or ''
                except Exception:
                    pass

            # Extract blocks
            blocks = self.block_extractor.extract_blocks(content)

            if not blocks:
                return

            # Deferred link queue: inline links found in a paragraph are collected
            # here and fired via display.link() AFTER the paragraph renders so the
            # y/n prompt appears below the text rather than interrupting it.
            pending_links: list = []

            def _link_sink(label: str, href: str, target: str = None) -> None:
                pending_links.append({'label': label, 'href': href, 'target': target})

            # Process each block
            for block_type, block_content in blocks:
                try:
                    if block_type == 'code':
                        language, code_content = block_content
                        display.code(content=code_content, language=language, indent=indent)
                    elif block_type == 'heading':
                        level, text = block_content
                        parsed_text = self.parse_inline(text)
                        display.header(parsed_text, indent=level - 1)
                    elif block_type == 'blockquote':
                        self._emit_blockquote(block_content, display, indent)
                    elif block_type == 'list':
                        self._emit_list(block_content, display, indent)
                    elif block_type == 'paragraph':
                        parsed_content = self.parse_inline(
                            block_content,
                            wrap_color_ansi=wrap_color_ansi,
                            link_sink=_link_sink,
                        )
                        self._emit_paragraph(parsed_content, display, indent, color)
                        # Drain deferred links — fire display.link() for each navigable
                        # link found in this paragraph. If the user confirms navigation
                        # (returns a zLink dict), stop zMD immediately.
                        for link_data in pending_links:
                            _link_kwargs = {'label': link_data['label'], 'href': link_data['href']}
                            if link_data.get('target'):
                                _link_kwargs['target'] = link_data['target']
                            nav = display.link(**_link_kwargs)
                            if nav and isinstance(nav, dict) and 'zLink' in nav:
                                return  # User navigated away — stop rendering
                        pending_links.clear()
                except Exception as e:
                    # Fallback: emit raw content
                    indent_str = ' ' * (indent * 4) if indent > 0 else ''
                    print(f"{indent_str}{block_content}")
                    if hasattr(display, 'zos') and hasattr(display.zos, 'logger'):
                        display.zos.logger.debug(f"[MarkdownParser] Block error: {e}")
        except Exception as e:
            # Ultimate fallback
            indent_str = ' ' * (indent * 4) if indent > 0 else ''
            print(f"{indent_str}{content}")
            if hasattr(display, 'zos') and hasattr(display.zos, 'logger'):
                display.zos.logger.debug(f"[MarkdownParser] Fatal error: {e}")

    def _emit_blockquote(self, content: str, display: 'zDisplay', indent: int = 0) -> None:
        """
        Emit blockquote by delegating to display.text(semantic='blockquote').

        SemanticPrimitives.render_blockquote() handles both modes:
        - zCLI: prefixes each line with "> "
        - Bifrost: wraps in styled <blockquote> HTML

        Args:
            content: Blockquote content (lines starting with >)
            display: zDisplay instance
            indent: Indentation level
        """
        lines = content.strip().split('\n')
        quote_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('>'):
                quote_text = stripped[1:].strip()
                parsed_line = self.parse_inline(quote_text) if quote_text else ''
                quote_lines.append(parsed_line)
            elif not stripped:
                quote_lines.append('')

        quote_content = '\n'.join(quote_lines)
        display.text(quote_content, indent=indent, semantic="blockquote")

    def _emit_list(self, content: str, display: 'zDisplay', indent: int = 0) -> None:
        """
        Emit list via display.list() event.

        Supports nested lists: extract_list_items() returns nested arrays for
        indented child items (e.g. ["Parent", ["Child A", "Child B"], "Parent2"]).
        Inline markdown is applied recursively to leaf strings only.

        Args:
            content: Markdown list content
            display: zDisplay instance
            indent: Indentation level
        """
        # Styled tree — each sublist carries its OWN style (from its first
        # marker), so mixed outlines render correctly even when sibling branches
        # use different marker families at the same depth.
        root = self.block_extractor.extract_styled_list(content)

        def _apply_inline(node):
            for item in node['_items']:
                item['text'] = self.parse_inline(item['text'])
                if item['_children']:
                    _apply_inline(item['_children'])

        if not root['_items']:
            parsed_content = self.parse_inline(content)
            self._emit_paragraph(parsed_content, display, indent)
            return

        _apply_inline(root)
        display.list(root['_items'], style=root['_style'], indent=indent)

    def _emit_paragraph(self, content: str, display: 'zDisplay', indent: int = 0, color: Optional[str] = None) -> None:
        """
        Emit paragraph by delegating to display.text().

        Delegates to the existing zText event so all zCLI formatting
        (spacing, color, emoji, %variables) and Bifrost dual-mode are
        inherited automatically — no duplication.

        Soft-break sentinels (\x02, STX control char) inserted by rich_text_renderer
        for <br> tags are expanded to \n here — after inline parsing — so they
        produce a line break within a single paragraph block rather than a full
        paragraph gap. STX is used because it is invisible to the markdown inline
        transformer (no markdown syntax uses control characters).

        Args:
            content: Parsed paragraph content (inline ANSI already applied)
            display: zDisplay instance
            indent: Indentation level
            color: Optional color override
        """
        content = content.replace('\x02', '\n')
        display.text(content, indent=indent, color=color)


# Utility function for backward compatibility
def parse_markdown_inline(text: str) -> str:
    """
    Convenience function to parse inline markdown.
    
    Args:
        text: Raw markdown text
        
    Returns:
        ANSI-formatted text
    """
    parser = MarkdownParser()
    return parser.parse_inline(text)
