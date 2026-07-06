# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/e_advanced/markdown/semantic_renderers.py

"""
Semantic HTML Renderers for Markdown/Rich Text - Advanced Layer.

This module provides semantic HTML element rendering for markdown and rich text features.
It serves as the SINGLE SOURCE OF TRUTH for how semantic elements render in
zCLI vs Bifrost mode.

Architecture Position:
    Tier: e_advanced/markdown (Advanced rendering)
    - Used by: BasicOutputs (for semantic argument) AND MarkdownParser (for inline parsing)
    - Purpose: DRY - Prevent duplicate rendering logic
    - NOT a primitive: Contains formatting/rendering logic, not raw I/O

Design Philosophy:
    Each semantic element has ONE renderer function that:
    1. zCLI Mode: Returns markdown-style syntax (readable, no ANSI yet)
    2. Bifrost Mode: Returns raw content (frontend wraps in HTML)
    
    This ensures:
    - display.text("code", semantic="code") → renders as `code`
    - display.rich_text("Run `code`") → renders as Run `code`
    - BOTH use SemanticPrimitives.render_code() - NO DUPLICATION!

Semantic Elements Supported (16 total):
    Inline Formatting:
        - code: Inline code
        - strong: Strong emphasis/bold
        - em: Emphasis/italic
        - mark: Highlighted text
        - del: Deleted/strikethrough text
    
    Structural:
        - blockquote: Block quotation
        - pre: Preformatted text
        - code_block: Multi-line code blocks with optional language
    
    Interactive/Metadata:
        - kbd: Keyboard input
        - cite: Citation
        - q: Inline quote
        - abbr: Abbreviation
        - time: Time/date
    
    Typography:
        - small: Small print
        - sub: Subscript
        - sup: Superscript

Usage Example:
    >>> from display_semantic_primitives import SemanticPrimitives
    >>> 
    >>> # zCLI mode
    >>> SemanticPrimitives.render_code("ls -la", mode="terminal")
    '`ls -la`'
    >>> 
    >>> # Bifrost mode
    >>> SemanticPrimitives.render_code("ls -la", mode="bifrost")
    'ls -la'  # Frontend wraps in <code>

Notes:
    - All methods are @staticmethod (no instance needed)
    - Mode parameter: "terminal" or "bifrost"
    - Terminal: Returns markdown-style formatted string
    - Bifrost: Returns raw content (HTML wrapping done by frontend)
"""


class SemanticPrimitives:
    """
    Foundational semantic rendering primitives.
    
    Single source of truth for semantic HTML element rendering across
    Terminal and Bifrost modes. Used by both semantic argument (entire element)
    and rich_text markdown parsing (inline mixing).
    
    All methods are static - no instance state needed.
    """

    # Inline Formatting Semantics

    @staticmethod
    def render_code(content: str, mode: str = "terminal") -> str:
        """
        Render inline code semantic.
        
        Terminal: `content`
        Bifrost: content (wrapped in <code> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            return f"`{content}`"
        return content

    @staticmethod
    def render_strong(content: str, mode: str = "terminal") -> str:
        """
        Render strong/bold semantic.
        
        Terminal: **content**
        Bifrost: content (wrapped in <strong> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            return f"**{content}**"
        return content

    @staticmethod
    def render_em(content: str, mode: str = "terminal") -> str:
        """
        Render emphasis/italic semantic.
        
        Terminal: *content*
        Bifrost: content (wrapped in <em> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            return f"*{content}*"
        return content

    @staticmethod
    def render_mark(content: str, mode: str = "terminal") -> str:
        """
        Render highlight/mark semantic.
        
        Terminal: ==content==
        Bifrost: content (wrapped in <mark> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            return f"=={content}=="
        return content

    @staticmethod
    def render_del(content: str, mode: str = "terminal") -> str:
        """
        Render deleted/strikethrough semantic.
        
        Terminal: ~~content~~
        Bifrost: content (wrapped in <del> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            return f"~~{content}~~"
        return content

    # Structural Semantics

    @staticmethod
    def render_blockquote(content: str, mode: str = "terminal") -> str:
        """
        Render blockquote semantic.
        
        Terminal: > content (prefix each line with "> ")
        Bifrost: <blockquote> HTML element with zTheme styling
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            # Prefix each line with "> "
            lines = content.split('\n')
            return '\n'.join(f"> {line}" for line in lines)

        # Bifrost mode: Generate styled <blockquote> HTML
        # Apply zReboot styling: left border, light background, padding
        return (
            f'<blockquote class="zp-3 zmy-3" '
            f'style="border-left: 4px solid var(--color-primary); '
            f'background: #f5f5f5;">'
            f'<p class="zmt-0 zmb-0">{content}</p></blockquote>'
        )

    @staticmethod
    def render_pre(content: str, mode: str = "terminal") -> str:
        """
        Render preformatted text semantic.
        
        Terminal: │ content (pipe-prefix per line — visually distinct, lighter than code_block box)
        Bifrost: content (wrapped in <pre> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content (whitespace preserved)
        """
        if mode == "terminal":
            lines = content.split('\n')
            return '\n'.join(f"│ {line}" for line in lines)
        return content

    @staticmethod
    def render_code_block(content: str, language: str = "", mode: str = "terminal") -> str:
        """
        Render code block semantic (multi-line code with optional language).
        
        Terminal: 
            ┌─ [language] ────
            │ code line 1
            │ code line 2
            └─────────────────
        
        Bifrost: ```language\ncontent\n``` (markdown preserved for frontend parsing)
        
        Args:
            content: Code content to render
            language: Optional language identifier (e.g., "python", "html", "css")
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted code block
        """
        if mode == "terminal":
            # Terminal: Render with box-drawing characters for visual separation
            lines = content.split('\n')

            # Build header with optional language
            lang_label = f" [{language}] " if language else " "
            header = f"┌─{lang_label}{'─' * (60 - len(lang_label))}"

            # Indent each line with box character
            body_lines = [f"│ {line}" for line in lines]

            # Footer
            footer = "└" + "─" * 60

            # Combine all parts
            return '\n'.join([header] + body_lines + [footer])

        # Bifrost: Preserve markdown triple-backtick syntax (frontend will parse)
        if language:
            return f"```{language}\n{content}\n```"
        return f"```\n{content}\n```"

    # Interactive/Metadata Semantics

    @staticmethod
    def render_kbd(content: str, mode: str = "terminal") -> str:
        """
        Render keyboard input semantic.
        
        Terminal: [content]
        Bifrost: content (wrapped in <kbd> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            return f"[{content}]"
        return content

    @staticmethod
    def render_cite(content: str, mode: str = "terminal") -> str:
        """
        Render citation semantic.
        
        Terminal: — content (em dash prefix)
        Bifrost: content (wrapped in <cite> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            return f"— {content}"
        return content

    @staticmethod
    def render_q(content: str, mode: str = "terminal") -> str:
        """
        Render inline quote semantic.
        
        Terminal: "content"
        Bifrost: content (wrapped in <q> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            return f'"{content}"'
        return content

    @staticmethod
    def render_abbr(content: str, _mode: str = "terminal") -> str:
        """
        Render abbreviation semantic.
        
        Terminal: content (no special formatting, tooltip only in Bifrost)
        Bifrost: content (wrapped in <abbr> with title attribute by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        # Abbreviations don't have visual terminal representation
        # Tooltip/title is Bifrost-only feature
        return content

    @staticmethod
    def render_time(content: str, _mode: str = "terminal") -> str:
        """
        Render time/date semantic.
        
        Terminal: content (no special formatting, datetime attribute only in Bifrost)
        Bifrost: content (wrapped in <time> with datetime attribute by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        # Time elements don't have visual terminal representation
        # datetime attribute is Bifrost-only feature
        return content

    # Typography Semantics

    @staticmethod
    def render_small(content: str, _mode: str = "terminal") -> str:
        """
        Render small print semantic.
        
        Terminal: content (no size change in terminal)
        Bifrost: content (wrapped in <small> by frontend for smaller font)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        # Small text doesn't have terminal representation
        # Font size is Bifrost-only feature
        return content

    @staticmethod
    def render_sub(content: str, mode: str = "terminal") -> str:
        """
        Render subscript semantic.
        
        Terminal: content_subscript (underscore prefix)
        Bifrost: content (wrapped in <sub> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            return f"_{content}"
        return content

    @staticmethod
    def render_sup(content: str, mode: str = "terminal") -> str:
        """
        Render superscript semantic.
        
        Terminal: content^superscript (caret prefix)
        Bifrost: content (wrapped in <sup> by frontend)
        
        Args:
            content: Text content to render
            mode: "terminal" or "bifrost"
            
        Returns:
            str: Formatted content
        """
        if mode == "terminal":
            return f"^{content}"
        return content
