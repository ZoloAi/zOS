"""
Syntax Highlighter - Provides syntax highlighting for code blocks.

Features:
- Pygments-based syntax highlighting (fallback to mono-color)
- Custom .zolo language coloring
- ANSI 256-color terminal support

Author: zOS Framework
Version: 3.0.0
"""

from zOS import re, Optional


class SyntaxHighlighter:
    """Handles syntax highlighting for code blocks."""

    def __init__(self):
        """Initialize highlighter."""
        self.ANSI_RESET = '\033[0m'
        self.ANSI_CYAN = '\033[36m'  # Fallback color

    def highlight(self, code: str, language: Optional[str] = None) -> str:
        """
        Apply syntax highlighting to code.
        
        Args:
            code: Code content to highlight
            language: Programming language (e.g., 'python', 'javascript', 'zolo')
            
        Returns:
            Highlighted code with ANSI codes
        """
        if not code:
            return code

        # Special handling for .zolo language
        if language and language.lower() == 'zolo':
            return self._highlight_zolo(code)

        # Try Pygments for other languages
        try:
            from pygments import highlight
            from pygments.lexers import get_lexer_by_name, TextLexer
            from pygments.formatters import Terminal256Formatter
            from pygments.util import ClassNotFound

            try:
                lexer = get_lexer_by_name(language or 'text', stripall=True)
            except (ClassNotFound, ImportError):
                lexer = TextLexer()

            formatter = Terminal256Formatter(style='monokai')
            return highlight(code, lexer, formatter)

        except (ImportError, Exception):
            # Fallback to mono-color cyan
            return f"{self.ANSI_CYAN}{code}{self.ANSI_RESET}"

    def _highlight_zolo(self, code: str) -> str:
        """
        Apply fast ANSI coloring to .zolo syntax.
        
        Color scheme (monokai-inspired):
        - Root keys (capitalized): Pink/Magenta
        - Display events (z*): Cyan
        - Metadata (_z*): Yellow
        - Properties (lowercase): Green
        - Comments: Dim gray
        """
        ANSI_RESET = '\033[0m'
        ANSI_PINK = '\033[95m'
        ANSI_CYAN = '\033[96m'
        ANSI_YELLOW = '\033[93m'
        ANSI_GREEN = '\033[92m'
        ANSI_DIM_GRAY = '\033[2m\033[37m'

        lines = code.split('\n')
        colored_lines = []

        for line in lines:
            # Preserve empty lines
            if not line.strip():
                colored_lines.append(line)
                continue

            # Comments
            stripped = line.lstrip()
            if stripped.startswith('#'):
                colored_lines.append(f"{ANSI_DIM_GRAY}{line}{ANSI_RESET}")
                continue

            # Key: value pattern
            match = re.match(r'^(\s*)([_~^]?[a-zA-Z][a-zA-Z0-9_]*)(\([^)]+\))?([\*!]?)\s*:\s*(.*)', line)
            if match:
                indent, key, type_hint, modifier, value = match.groups()

                # Determine key color
                if key[0].isupper():
                    key_color = ANSI_PINK  # Root key
                elif key.startswith('z') and len(key) > 1 and key[1].isupper():
                    key_color = ANSI_CYAN  # Display event
                elif key.startswith('_z'):
                    key_color = ANSI_YELLOW  # Metadata
                else:
                    key_color = ANSI_GREEN  # Property

                # Rebuild line with colors
                colored_line = f"{indent}{key_color}{key}{ANSI_RESET}"
                if type_hint:
                    colored_line += f"{ANSI_DIM_GRAY}{type_hint}{ANSI_RESET}"
                if modifier:
                    colored_line += f"{ANSI_YELLOW}{modifier}{ANSI_RESET}"
                colored_line += f": {value}"

                colored_lines.append(colored_line)
            else:
                colored_lines.append(line)

        return '\n'.join(colored_lines)
