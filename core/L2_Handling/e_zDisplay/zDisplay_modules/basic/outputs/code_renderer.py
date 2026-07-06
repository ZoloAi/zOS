# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/c_basic/outputs/code_renderer.py

"""
Code Renderer - Helper module for BasicOutputs
===============================================

Provides code block rendering logic for the `zCode` typography event:
- zCLI: SyntaxHighlighter + 100-char box-drawing border
- Bifrost: send_gui_event('code', {content, language, indent})

This is the SSOT for code rendering shared by:
- zTerminal preview (terminal_executor.py)
- zMD code fences (markdown_parser.py)
- Direct zCode shorthand usage
"""

from zOS import Any, Optional, re

from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    _EVENT_NAME_CODE,
    _KEY_CONTENT,
    _KEY_INDENT,
)

_ANSI_RESET = '\033[0m'
_ANSI_DIM = '\033[2m'
_ANSI_CYAN = '\033[36m'
_ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')

_BOX_WIDTH = 100
_CONTENT_WIDTH = 98


def _visible_length(text: str) -> int:
    """Return the visible (non-ANSI) length of a string."""
    return len(_ANSI_ESCAPE.sub('', text))


class CodeRenderer:
    """Code block rendering logic for BasicOutputs."""

    def __init__(self, display_instance: Any) -> None:
        """Initialize CodeRenderer with display reference.

        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives

        # Import SyntaxHighlighter here to avoid circular imports at module level
        from ...advanced.markdown.syntax_highlighter import SyntaxHighlighter  # pylint: disable=relative-beyond-top-level
        self.syntax_highlighter = SyntaxHighlighter()

    def render_code(
        self,
        content: str,
        language: Optional[str] = None,
        indent: int = 0,
        **kwargs
    ) -> None:
        """Render a code block.

        Dispatches to GUI mode (Bifrost) or terminal mode (zCLI/Walker).

        Args:
            content: Raw code content (no ANSI codes)
            language: Programming language for syntax highlighting
            indent: Indentation level
            **kwargs: Additional parameters forwarded to the GUI event
        """
        if not content:
            return

        event_data = {
            _KEY_CONTENT: content,
            _KEY_INDENT: indent,
        }
        if language:
            event_data['language'] = language
        event_data.update(kwargs)

        if self.zPrimitives.send_gui_event(_EVENT_NAME_CODE, event_data):
            return

        self._render_code_terminal(content, language, indent)

    def _render_code_terminal(
        self,
        content: str,
        language: Optional[str],
        indent: int,
    ) -> None:
        """Render code block for zCLI/Walker with box-drawing and syntax highlighting."""
        indent_str = ' ' * (indent * 4) if indent > 0 else ''

        highlighted = self.syntax_highlighter.highlight(content, language)
        lines = highlighted.rstrip().split('\n')

        print(f"{indent_str}{_ANSI_DIM}╭{'─' * _BOX_WIDTH}╮{_ANSI_RESET}")

        if language:
            lang_label = f" {language} "
            print(
                f"{indent_str}{_ANSI_DIM}│{_ANSI_RESET}{_ANSI_CYAN}"
                f"{lang_label.ljust(_BOX_WIDTH)}{_ANSI_RESET}{_ANSI_DIM}│{_ANSI_RESET}"
            )
            print(f"{indent_str}{_ANSI_DIM}├{'─' * _BOX_WIDTH}┤{_ANSI_RESET}")

        for line in lines:
            vis_len = _visible_length(line)
            if vis_len > _CONTENT_WIDTH:
                display_line = line[:_CONTENT_WIDTH - 3] + '...'
                padding = ''
            else:
                display_line = line
                padding = ' ' * (_CONTENT_WIDTH - vis_len)
            print(
                f"{indent_str}{_ANSI_DIM}│{_ANSI_RESET} {display_line}{padding} "
                f"{_ANSI_DIM}│{_ANSI_RESET}"
            )

        print(f"{indent_str}{_ANSI_DIM}╰{'─' * _BOX_WIDTH}╯{_ANSI_RESET}")
