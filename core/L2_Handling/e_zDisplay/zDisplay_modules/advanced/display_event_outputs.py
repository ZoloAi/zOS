# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/e_advanced/display_event_outputs.py

"""
AdvancedOutputs - Advanced Output Events for zDisplay
======================================================

This event package provides advanced output operations with complex rendering:
- Rich text with markdown parsing
- Future: Code syntax highlighting, complex formatting

Architecture
------------
AdvancedOutputs is part of the e_advanced tier:

Layer 3: display_delegates.py (PRIMARY API)
    ↓
Layer 2: display_events.py (ORCHESTRATOR)
    ↓
Layer 2: events/display_event_outputs.py (AdvancedOutputs) ← THIS MODULE
    ↓
Layer 2: markdown/*.py (MARKDOWN PROCESSING)
    ↓
Layer 2: events/display_event_outputs.py (BasicOutputs) ← FOUNDATION
    ↓
Layer 1: display_primitives.py (FOUNDATION I/O)

Module Composition
------------------
Helper modules in markdown/ directory:

1. **RichTextRenderer** - Rich text with markdown parsing
   - Inline markdown formatting (bold, italic, code, links)
   - Dual-mode rendering (terminal + GUI)
   - Semantic markup support

Methods
-------
AdvancedOutputs provides advanced rendering methods:

1. **rich_text(content, indent, pause, format_type)** - Markdown-formatted text
   - Terminal: Parses markdown and displays with semantic formatting
   - Bifrost: Sends markdown with format="markdown" for HTML parsing
   - Supports: `code`, **bold**, *italic*, ~~strikethrough~~, ==highlight==, [links](url)

Example
-------
```python
# Via display_events orchestrator:
events = zEvents(display_instance)
events.AdvancedOutputs.rich_text("Run `ls -la` to see **all** files")

# Direct usage (rare):
advanced_outputs = AdvancedOutputs(display_instance)
advanced_outputs.rich_text("Visit [our docs](https://example.com) for help")
```

Version Info
------------
Created: Week 6.5 (Architectural refactoring - moved rich_text from c_basic)
"""

from zOS import Any, Optional

from .markdown.rich_text_renderer import RichTextRenderer


class AdvancedOutputs:
    """Advanced output operations for e_advanced tier."""

    display: Any
    RichTextRenderer: 'RichTextRenderer'

    def __init__(self, display_instance: Any) -> None:
        """Initialize AdvancedOutputs with parent display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance

        # Initialize helper modules
        self.RichTextRenderer = RichTextRenderer(display_instance)

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
        
        Advanced markdown rendering with inline semantic markup.
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
            advanced.rich_text("Run `ls -la` to see files")
            
            # Multiple styles
            advanced.rich_text(
                "**Important:** Use `pip install` for *Python* packages"
            )
            
            # With indentation
            advanced.rich_text(
                "See the `config.yaml` file for **settings**",
                indent=1
            )
            
            # With link
            advanced.rich_text(
                "Visit [our docs](https://example.com) for help"
            )
        
        Note:
            Terminal mode parses markdown using MarkdownParser.
            This ensures consistency with semantic argument rendering.
        """
        return self.RichTextRenderer.rich_text(
            content=content,
            indent=indent,
            pause=pause,
            break_message=break_message,
            format_type=format_type,
            **kwargs
        )
