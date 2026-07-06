# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/e_advanced/markdown/rich_text_renderer.py

"""
Rich Text Renderer - Advanced markdown-formatted text display.

Provides rich text rendering with inline markdown formatting support.
This is an advanced feature that combines markdown parsing, semantic rendering,
and dual-mode output.
"""

import logging

from zOS import Any, Optional, re

from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    DEFAULT_BREAK_MESSAGE,
    _KEY_CONTENT,
    _KEY_INDENT,
    _KEY_BREAK,
    _KEY_BREAK_MESSAGE,
)

# ZLinkResolver: Python SSOT for href classification and RBAC
try:
    from zOS.L2_Handling.h_zNavigation.navigation_modules.resolvers.resolver_zlink import (
        ZLinkResolver,
    )
    _RESOLVER_AVAILABLE = True
except ImportError:
    _RESOLVER_AVAILABLE = False


class RichTextRenderer:
    """Rich text renderer with markdown parsing support."""

    display: Any
    zPrimitives: Any

    def __init__(self, display_instance: Any) -> None:
        """Initialize RichTextRenderer with display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives

    def rich_text(
        self,
        content: str,
        indent: int = 0,
        pause: bool = False,
        break_message: Optional[str] = None,
        format_type: str = "markdown",
        **kwargs
    ) -> None:
        """Display rich text with inline formatting (markdown-style).
        
        Supports inline semantic markup using markdown syntax.
        This enables mixing bold, italic, code, and other inline styles within
        a single text block.
        
        Markdown Syntax Supported:
            - `code` -> <code> inline code
            - **bold** -> <strong> strong emphasis
            - *italic* -> <em> emphasis
            - ~~strikethrough~~ -> <del> deleted text
            - ==highlight== -> <mark> highlighted text
            - [text](url) -> <a> hyperlinks
        
        Dual-Mode Behavior:
            - Terminal: Parses markdown and displays with semantic formatting
            - Bifrost: Sends markdown with format="markdown" for HTML parsing
        
        Args:
            content: Text with markdown inline formatting
            indent: Indentation level (default: 0)
            pause: Pause for user acknowledgment (default: False)
            break_message: Custom break message if pause=True
            format_type: Format type (default: "markdown")
            **kwargs: Additional parameters passed to Bifrost (e.g., color)
        
        Returns:
            None
        
        Examples:
            # Simple inline code
            display.rich_text("Run `ls -la` to see files")
            
            # Multiple styles
            display.rich_text(
                "**Important:** Use `pip install` for *Python* packages"
            )
            
            # With indentation
            display.rich_text(
                "See the `config.yaml` file for **settings**",
                indent=1
            )
            
            # With link
            display.rich_text(
                "Visit [our docs](https://example.com) for help"
            )
        
        Note:
            Terminal mode parses markdown using MarkdownParser.
            This ensures consistency with semantic argument rendering.
        """
        # For Bifrost: RBAC-gate AND route-resolve internal inline links before
        # sending. RBAC-denied links downgrade to plain label text (same contract
        # as zURL._render_bifrost()); internal @. zPaths are resolved to their web
        # route via the SSOT resolver so the browser receives a finished URL.
        bifrost_content = self._prepare_bifrost_inline_links(content)

        # Build event dict
        event_data = {
            _KEY_CONTENT: bifrost_content,
            _KEY_INDENT: indent,
            _KEY_BREAK: pause,
            _KEY_BREAK_MESSAGE: break_message,
            "format": format_type,
            **kwargs
        }

        # Try GUI mode first - send clean event
        if self.zPrimitives.send_gui_event("rich_text", event_data):
            return

        # Terminal mode - parse markdown and display
        self._render_terminal(content, indent, pause, break_message, **kwargs)

    def _prepare_bifrost_inline_links(self, content: str) -> str:
        """
        RBAC-gate and route-resolve internal inline links for the Bifrost chunk.

        One pass over every ``[label](href)`` pattern, applying two transforms to
        internal (zPath / delta) links — external links, anchors, and placeholders
        are passed through untouched:

        1. **RBAC gate** — a link the visitor may not see is downgraded to plain
           label text (the same contract as ``zURL._render_bifrost(disabled=True)``).
        2. **zPath → route** — an internal ``@.`` zPath href is resolved to its
           canonical web route via ``ZLinkResolver.resolve_href_to_route`` (the ONE
           authority, shared with zURL / zLink / navbar). Without this the raw
           ``@.`` zPath reaches the browser, where the client's structural
           converter only understands ``@.UI.*`` and mangles ``@.zViews.*`` paths
           into ``/@/…`` dead links. ``resolve_href_to_route`` is idempotent and
           a no-op on ``$delta`` / external / anchor hrefs, so they are safe to
           route through it.

        Args:
            content: Raw markdown content (may contain inline links)

        Returns:
            Content with RBAC-denied links flattened to text and internal zPath
            links rewritten to their resolved web route.
        """
        if not _RESOLVER_AVAILABLE or not content:
            return content

        zos = getattr(self.display, 'zos', None)
        resolver = ZLinkResolver(getattr(zos, 'logger', None) or
                                  logging.getLogger(__name__))
        session = {}
        try:
            session = self.display.zos.session
        except AttributeError:
            pass

        # Delegate to the ONE inline-link scanner (SSOT, shared with the zBifrost
        # chunk path) so GUI + chunk resolve [label](@.zPath) identically.
        return resolver.resolve_inline_links(content, zos, session=session, apply_rbac=True)

    def _render_terminal(
        self,
        content: str,
        indent: int,
        pause: bool,
        break_message: Optional[str],
        **kwargs
    ) -> None:
        """Render rich text in terminal mode with markdown parsing.
        
        Args:
            content: Markdown content
            indent: Indentation level
            pause: Whether to pause after display
            break_message: Custom break message
            **kwargs: Additional parameters (color, etc.)
        """
        # Import markdown parser and content transformers
        from .markdown_parser import MarkdownParser
        from ...basic.outputs.content_transformers import (  # pylint: disable=relative-beyond-top-level
            ContentTransformers
        )

        # Step 0a: Protect FENCED code blocks (``` ... ```) from all further processing.
        # Must run before inline-code extraction so the fence chars are never consumed
        # by the single-backtick regex and restored as corrupted 4-backtick sequences.
        fenced_blocks: list = []

        def protect_fenced(m: re.Match) -> str:
            fenced_blocks.append(m.group(0))
            return f'___FENCED_BLOCK_{len(fenced_blocks) - 1}___'

        content = re.sub(r'```\w*\n[\s\S]*?```', protect_fenced, content)

        # Step 0b: Protect INLINE code (`...`) from escape-sequence decoding.
        # Only match single-backtick spans that are NOT adjacent to another backtick,
        # so triple-backtick fences (already protected above) are never touched here.
        inline_code_blocks: list = []

        def protect_inline_code(match: re.Match) -> str:
            code = match.group(1)
            placeholder = f'___INLINE_CODE_{len(inline_code_blocks)}___'
            inline_code_blocks.append(code)
            return placeholder

        content = re.sub(r'(?<!`)`(?!`)([^`\n]+)(?<!`)`(?!`)', protect_inline_code, content)

        # Step 0c: Convert HTML line-break tags to a soft-break sentinel.
        # Must run WHILE inline-code spans are still placeholders so that
        # literal `<br>` inside backtick code (e.g. `<br>`) is NOT converted —
        # the placeholder text contains no angle brackets.
        # <br> is a browser primitive; terminal has no HTML renderer.
        # The sentinel (\x02) is invisible to the markdown block extractor,
        # keeping the containing paragraph as one block. _emit_paragraph()
        # expands it to \n for a soft line break with no paragraph gap.
        # Bifrost receives the original content (pre-step-0c) — browser handles
        # <br> natively.
        #
        # TODO (Option B): also support standard Markdown soft-break syntax —
        # two trailing spaces before \n (e.g. "Line one  \nLine two") as an
        # alternative to <br>. Requires teaching block_extractor / _emit_paragraph
        # to detect trailing "  \n" and emit a single \n instead of a paragraph gap.
        content = re.sub(r'<br\s*/?>', '\x02', content, flags=re.IGNORECASE)

        # Step 1: ALWAYS decode escape sequences (Unicode + basic escapes like \n, \t)
        try:
            from zlsp.parser.basic.escape_processors import decode_unicode_escapes
            content = decode_unicode_escapes(content)
        except ImportError:
            pass  # zlsp optional — leave escapes literal rather than crash

        # Step 1.5: Restore inline code blocks (they stay literal)
        for i, code in enumerate(inline_code_blocks):
            content = content.replace(f'___INLINE_CODE_{i}___', f'`{code}`')

        # Step 1.6: Restore fenced code blocks (unchanged — escape decoding skipped)
        for i, block in enumerate(fenced_blocks):
            content = content.replace(f'___FENCED_BLOCK_{i}___', block)

        # Step 2: Convert emojis to [description] for terminal accessibility
        content_transformers = ContentTransformers(self.display)
        content = content_transformers.convert_emojis_for_terminal(content)

        # Step 3: Parse markdown (will emit list events if content is a list, otherwise prints)
        parser = MarkdownParser()
        color = kwargs.get('color', None) or ""
        parser.parse(content, display=self.display, indent=indent, color=color)

        # Auto-break if enabled
        if pause:
            message = break_message or DEFAULT_BREAK_MESSAGE
            if indent > 0:
                indent_str = content_transformers.build_indent(indent)
                message = f"{indent_str}{message}"
            self.zPrimitives.line(message)
            self.zPrimitives.read_string("")
