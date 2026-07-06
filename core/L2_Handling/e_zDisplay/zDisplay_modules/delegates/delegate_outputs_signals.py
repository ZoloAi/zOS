# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/delegates/delegate_outputs_signals.py

"""
Output & Signal Convenience Delegates
======================================

Extracted from display_events.py to reduce file size and improve maintainability.
Contains convenience delegate methods for BasicOutputs and signal operations.

Methods:
- header(): Display formatted header
- text(): Display plain text
- rich_text(): Display rich text with markdown
- error(): Display error message
- warning(): Display warning message
- success(): Display success message
- info(): Display info message
- zMarker(): Display visual marker
- json_data(): Display JSON with formatting
- list(): Display list with bullets/numbers
"""

from zOS import Any, Optional, List


class OutputSignalDelegates:
    """Mixin providing convenience delegates for BasicOutputs and signals.
    
    This class is designed to be mixed into zEvents via multiple inheritance.
    It provides backward-compatible convenience methods that delegate to
    the appropriate event packages.
    
    Required Attributes (provided by zEvents):
        - BasicOutputs: BasicOutputs package instance
        - CompoundData: CompoundData package instance
    """

    def header(
        self, label: str, color: str = "RESET", indent: int = 0,
        style: str = "full", semantic: Optional[str] = None, **kwargs
    ) -> Any:
        """Display formatted header with styling.
        
        Args:
            label: Header text to display
            color: Color name for styling (default: RESET)
            indent: Indentation level (default: 0)
            style: Header style (default: full)
            semantic: Optional semantic HTML element type
            **kwargs: Additional parameters
            
        Returns:
            Result from BasicOutputs.header method
        """
        return self.BasicOutputs.header(label, color, indent, style, semantic=semantic, **kwargs)

    def text(
        self,
        content: str,
        indent: int = 0,
        pause: bool = False,
        break_message: Optional[str] = None,
        break_after: Optional[bool] = None,
        semantic: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Display plain text content.
        
        Args:
            content: Text content to display
            indent: Indentation level (default: 0)
            pause: Pause for user acknowledgment (default: False)
            break_message: Optional break message
            break_after: Legacy parameter - use 'pause' instead
            semantic: Optional semantic HTML element type
            **kwargs: Additional parameters (e.g., _context)
            
        Returns:
            Result from BasicOutputs.text method
        """
        return self.BasicOutputs.text(
            content,
            indent=indent,
            pause=pause,
            break_message=break_message,
            break_after=break_after,
            semantic=semantic,
            **kwargs
        )

    def rich_text(
        self,
        content: str,
        indent: int = 0,
        pause: bool = False,
        break_message: Optional[str] = None,
        format_type: str = "markdown",
        **kwargs
    ) -> Any:
        """Display rich text with inline formatting.
        
        Args:
            content: Text with markdown inline formatting
            indent: Indentation level (default: 0)
            pause: Pause for user acknowledgment (default: False)
            break_message: Optional break message
            format_type: Format type (default: "markdown")
            **kwargs: Additional parameters
            
        Returns:
            Result from AdvancedOutputs.rich_text method
        """
        return self.AdvancedOutputs.rich_text(
            content,
            indent=indent,
            pause=pause,
            break_message=break_message,
            format_type=format_type,
            **kwargs
        )

    def code(
        self,
        content: str,
        language: Optional[str] = None,
        indent: int = 0,
        **kwargs
    ) -> Any:
        """Display a code block with syntax highlighting.

        Args:
            content: Raw code content
            language: Programming language (e.g. 'python', 'js', 'zolo')
            indent: Indentation level (default: 0)
            **kwargs: Additional parameters forwarded to the GUI event

        Returns:
            Result from BasicOutputs.code method
        """
        return self.BasicOutputs.code(content, language=language, indent=indent, **kwargs)

    def error(self, content: str, indent: int = 0, flush: bool = False) -> Any:
        """Display error message with ERROR styling.
        
        Args:
            content: Error message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed toast. Ignored in terminal.
            
        Returns:
            Result from BasicOutputs.error method
        """
        return self.BasicOutputs.error(content, indent, flush=flush)

    def warning(self, content: str, indent: int = 0, flush: bool = False) -> Any:
        """Display warning message with WARNING styling.
        
        Args:
            content: Warning message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed toast. Ignored in terminal.
            
        Returns:
            Result from BasicOutputs.warning method
        """
        return self.BasicOutputs.warning(content, indent, flush=flush)

    def success(self, content: str, indent: int = 0, flush: bool = False) -> Any:
        """Display success message with SUCCESS styling.
        
        Args:
            content: Success message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed toast. Ignored in terminal.
            
        Returns:
            Result from BasicOutputs.success method
        """
        return self.BasicOutputs.success(content, indent, flush=flush)

    def info(self, content: str, indent: int = 0, flush: bool = False) -> Any:
        """Display info message with INFO styling.
        
        Args:
            content: Info message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed toast. Ignored in terminal.
            
        Returns:
            Result from BasicOutputs.info method
        """
        return self.BasicOutputs.info(content, indent, flush=flush)

    def primary(self, content: str, indent: int = 0, flush: bool = False) -> Any:
        """Display a primary-brand emphasis signal (non-status).

        Args:
            content: Message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed toast. Ignored in terminal.

        Returns:
            Result from BasicOutputs.primary method
        """
        return self.BasicOutputs.primary(content, indent, flush=flush)

    def secondary(self, content: str, indent: int = 0, flush: bool = False) -> Any:
        """Display a secondary-brand emphasis signal (non-status).

        Args:
            content: Message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed toast. Ignored in terminal.

        Returns:
            Result from BasicOutputs.secondary method
        """
        return self.BasicOutputs.secondary(content, indent, flush=flush)

    def zMarker(self, label: str = "Marker", color: str = "MAGENTA", indent: int = 0) -> Any:
        """Display visual marker for debugging/tracking.
        
        Args:
            label: Marker label text (default: Marker)
            color: Marker color (default: MAGENTA)
            indent: Indentation level (default: 0)
            
        Returns:
            Result from BasicOutputs.zMarker method
        """
        return self.BasicOutputs.zMarker(label, color, indent)

    def json_data(self, data: Any, indent_size: int = 2, indent: int = 0, color: bool = False) -> None:
        """Display JSON with pretty formatting and optional syntax coloring.
        
        Args:
            data: Data to serialize as JSON
            indent_size: JSON indentation size (default: 2)
            indent: Base indentation level (default: 0)
            color: Enable syntax coloring for terminal (default: False)
            
        Returns:
            None
        """
        return self.BasicOutputs.json_data(data, indent_size, indent, color)

    def list(self, items: List[Any], style: str = "bullet", indent: int = 0, **kwargs) -> Optional[Any]:
        """Display list of items with formatting.
        
        Args:
            items: List of items to display
            style: List style (default: bullet)
            indent: Indentation level (default: 0)
            **kwargs: Additional parameters (e.g., _context)
            
        Returns:
            Navigation signal (zLink dict) if user clicked a link, None otherwise
        """
        return self.CompoundData.list(items, style, indent, **kwargs)
