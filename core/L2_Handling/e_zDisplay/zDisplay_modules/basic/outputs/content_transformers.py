# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/c_basic/outputs/content_transformers.py

"""
Content Transformers - Helper module for BasicOutputs
======================================================

Provides content transformation utilities:
- Emoji conversion for terminal accessibility
- Semantic rendering (code, strong, em, etc.)
- Indentation building
- Variable and function resolution
"""

from zOS import Any, Optional

from ...display_constants import _INDENT_STR, TERMINAL_MODES  # pylint: disable=relative-beyond-top-level


class ContentTransformers:
    """Content transformation utilities for BasicOutputs."""

    def __init__(self, display_instance: Any) -> None:
        """Initialize ContentTransformers with display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance

    def build_indent(self, indent: int) -> str:
        """Build indentation string (DRY helper).
        
        Args:
            indent: Indentation level (0 = no indent)
            
        Returns:
            str: Indentation string (2 spaces per level)
        """
        return _INDENT_STR * indent

    def apply_semantic(self, content: str, semantic: str) -> str:
        """Apply semantic rendering using primitives (DRY helper).
        
        Uses SemanticRenderers to render content with semantic HTML element styling.
        This ensures consistent rendering whether using semantic argument or rich_text
        markdown parsing.
        
        Args:
            content: Text content to render
            semantic: Semantic type (e.g., "code", "strong", "em", "kbd", etc.)
            
        Returns:
            str: Formatted content with semantic styling applied
                 Returns original content if semantic type is unknown
        
        Example:
            >>> self.apply_semantic("ls -la", "code")
            '`ls -la`'
            >>> self.apply_semantic("Important", "strong")
            '**Important**'
        
        Note:
            zCLI mode: Applies markdown-style formatting
            Bifrost mode: Returns raw content (frontend wraps in HTML)
        """
        from ...advanced.markdown.semantic_renderers import SemanticPrimitives  # pylint: disable=relative-beyond-top-level

        # Get the renderer for this semantic type
        renderer = getattr(SemanticPrimitives, f"render_{semantic}", None)
        if renderer:
            # Determine mode
            mode = "terminal" if self.display.mode in TERMINAL_MODES else "bifrost"
            return renderer(content, mode)

        # Unknown semantic type - return content as-is
        return content

    def convert_emojis_for_terminal(self, text: str) -> str:
        """
        DRY helper: Convert emojis to [description] for terminal accessibility.
        
        Used by ALL output events (header, text, rich_text) to ensure consistent
        emoji handling across the display system. This is the single source of truth
        for emoji conversion in zCLI mode.
        
        Only converts in zCLI mode; Bifrost uses emojis with aria-label.
        
        Args:
            text: Content that may contain emojis
        
        Returns:
            Text with emojis converted to [description] format for Terminal
        
        Example:
            "📱 Mobile" → "[mobile phone] Mobile" (Terminal)
            "📱 Mobile" → "📱 Mobile" (Bifrost, unchanged)
        """
        # Only convert in zCLI mode
        if self.display.mode not in TERMINAL_MODES:
            return text

        try:
            # Delegate to the terminal_gate SSOT (emoji_safe): always downgrades
            # pictographs to [description] and correctly consumes trailing
            # variation-selectors / ZWJ clusters (so '❤️' → '[red heart]', not
            # '[red heart]️'). One regex, one policy, shared with the stream gate.
            from ......zSys.accessibility import emoji_safe  # pylint: disable=relative-beyond-top-level
            return emoji_safe(text)
        except Exception as e:
            # Fallback: return text unchanged if emoji system fails
            self.display.zos.logger.warning(f"Emoji conversion failed: {e}")
            return text

    def resolve_variables(self, content: str, context: Optional[dict] = None) -> str:
        """Resolve %variable references in content.
        
        Args:
            content: Text with %variable references
            context: Optional context dict for variable resolution
            
        Returns:
            Content with variables resolved
        """
        if "%" not in content:
            return content

        # type: ignore[import]
        from .....d_zParser.parser_modules.parser_functions import resolve_variables
        return resolve_variables(content, self.display.zos, context)

    def resolve_functions(self, content: str) -> str:
        """Resolve &function calls in content.
        
        Args:
            content: Text with &function calls
            
        Returns:
            Content with functions resolved
        """
        if "&" not in content:
            return content

        # type: ignore[import]
        from .....d_zParser.parser_modules.parser_functions import resolve_function_call
        return resolve_function_call(content, self.display.zos)
