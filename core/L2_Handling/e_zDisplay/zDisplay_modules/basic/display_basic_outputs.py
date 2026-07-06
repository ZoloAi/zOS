# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/c_basic/display_basic_outputs.py

"""
BasicOutputs - Foundation Event Package for zDisplay (FACADE v2.0)
===================================================================

REFACTORING v2.0 (Facade Pattern):
    - Decomposed monolith (836 lines) into 3 specialized helper modules
    - Extracted ContentTransformers for emoji/semantic/variable processing
    - Extracted HeaderRenderer for header rendering logic
    - Extracted TextRenderer for text and rich_text rendering
    - Composition pattern: BasicOutputs orchestrates specialized modules
    - Uses MarkdownParser from e_advanced.markdown (block-level parsing)

This is the MOST CRITICAL event package in the zDisplay subsystem. ALL 7 other
event packages depend on BasicOutputs for fundamental display operations.

Foundation Role
---------------
BasicOutputs is the FOUNDATION of the entire events system:
- **0 dependencies** - true foundation layer
- **59 references** across 7 event files
- **Used by ALL 7 other event packages** (100% dependency)

This makes BasicOutputs the highest-impact file in the events system. Any change
here affects every other event package.

Architecture - Dual-Mode I/O Pattern
------------------------------------
BasicOutputs implements the dual-mode I/O pattern that all events follow:

1. **GUI Mode (Bifrost):** Try to send clean JSON event via send_gui_event()
   - Returns True if successful
   - Event sent via WebSocket to GUI frontend
   - Structured data (label, color, style, etc.)

2. **zCLI Mode (Fallback):** Build formatted text output
   - If GUI mode not available or fails
   - Format text with colors, styles, indentation
   - Output via write_line() primitive

This pattern ensures:
- GUI users get rich, interactive displays
- Terminal users get formatted text with colors
- Graceful degradation (always works in terminal)

Layer Position
--------------
BasicOutputs occupies the Event Layer in the zDisplay architecture:

```
Layer 3: display_delegates.py (PRIMARY API)
    ↓
Layer 2: display_events.py (ORCHESTRATOR)
    ↓
Layer 2: events/display_event_outputs.py (BasicOutputs) ← THIS MODULE (FACADE)
    ↓
Layer 2: outputs/*.py (HELPER MODULES)
    ↓
Layer 1: display_primitives.py (FOUNDATION I/O)
    ↓
Layer 0: zConfig (session) + zComm (WebSocket)
```

Dependency Graph
----------------
ALL 7 other event packages depend on BasicOutputs:

```
display_event_outputs.py (BasicOutputs) ← FOUNDATION (0 dependencies)
    ↑
    ├── display_event_inputs.py (BasicInputs)
    │   Uses: header() for selection prompts
    │
    ├── display_event_signals.py (Signals)
    │   Uses: header() for error/warning/success headers
    │
    ├── display_event_data.py (BasicData)
    │   Uses: header() for list/json display headers
    │
    ├── display_event_timebased.py (TimeBased)
    │   Uses: text() for progress bar labels
    │
    ├── display_event_advanced.py (AdvancedData)
    │   Uses: header() for zTable titles and pagination
    │
    ├── [REMOVED] display_event_auth.py (zAuthEvents)
    │   Auth UI now composed in zAuth subsystem using generic display events
    │
    └── display_event_system.py (zSystem)
        Uses: header() + text() for zDeclare, zSession, zCrumbs, zMenu, zDialog
```

Module Decomposition (v2.0)
----------------------------
Helper modules in outputs/ directory:

1. **ContentTransformers** - Content transformation utilities
   - Emoji conversion for terminal accessibility
   - Semantic rendering (code, strong, em, etc.)
   - Variable and function resolution
   - Indentation building

2. **HeaderRenderer** - Header rendering logic
   - Label resolution (variables, functions, semantic, emoji)
   - GUI mode event sending
   - Terminal mode rendering with width-safe formatting
   - Color and style application

4. **TextRenderer** - Text and rich_text rendering
   - Text rendering with indentation and pause
   - Rich text with markdown parsing
   - Variable and function resolution

Methods
-------
BasicOutputs provides 7 fundamental display methods:

**Core Output:**
1. **header(label, color, indent, style)** - Formatted section headers
2. **text(content, indent, break_after, break_message)** - Display text

**Signal Methods (colored feedback):**
3. **error(content, indent)** - Red error messages
4. **warning(content, indent)** - Yellow warning messages
5. **success(content, indent)** - Green success messages
6. **info(content, indent)** - Cyan informational messages
7. **zMarker(label, color, indent)** - Visual workflow markers

Note: rich_text moved to e_advanced/AdvancedOutputs (advanced markdown rendering)

zCLI Integration
----------------
- **Initialized by:** display_events.py (zEvents.__init__)
- **Accessed via:** zcli.display.zEvents.BasicOutputs
- **Used by:** All 7 other event packages (composition)
- **No session access** - delegates to primitives layer

Usage Statistics
----------------
- **59 total references** across zDisplay codebase
- **7 dependent packages** (100% of other event packages)
- **3 fundamental methods** (header + text + rich_text)
- **~250 lines** facade + ~450 lines helpers = ~700 total (v2.0)

Thread Safety
-------------
Not thread-safe. All display operations should occur on the main thread or
with appropriate synchronization.

Example
-------
```python
# Via display_events orchestrator:
events = zEvents(display_instance)
events.BasicOutputs.header("Section Title", color="CYAN", style="full")
events.BasicOutputs.text("Some content", indent=1, break_after=True)
events.BasicOutputs.rich_text("Run `ls -la` to see **all** files")

# Direct usage (rare):
basic_outputs = BasicOutputs(display_instance)
basic_outputs.header("Error", color="RED", style="single")
```
"""

from zOS import Any, Optional

# Import constants from centralized module
from ..display_constants import (  # pylint: disable=relative-beyond-top-level
    DEFAULT_COLOR,  # PUBLIC
)

# Import helper modules (v2.0 Decomposition)
from .outputs import (
    ContentTransformers,
    HeaderRenderer,
    TextRenderer,
    CodeRenderer,
    JsonRenderer,
    FieldRenderer,
)

# Module-specific style constants (public API for external use)
DEFAULT_STYLE_FULL = "full"
DEFAULT_STYLE_SINGLE = "single"
DEFAULT_STYLE_WAVE = "wave"
DEFAULT_STYLE_STAR = "star"
DEFAULT_STYLE_HASH = "hash"
DEFAULT_STYLE_PLUS = "plus"


class BasicOutputs:
    """Foundation event package providing fundamental output methods (FACADE v2.0).
    
    This is the MOST CRITICAL event class in zDisplay. ALL 7 other event
    packages depend on BasicOutputs for their display operations.
    
    **Foundation Status:**
    - 0 dependencies (true foundation)
    - 59 references across 7 event files
    - Used by ALL 7 other event packages
    
    **Methods:**
    - header(): Formatted section headers (used by ALL 7 packages)
    - text(): Display text with break/pause (used by zSystem + TimeBased)
    - rich_text(): Display rich text with markdown (NEW)
    
    **Pattern:**
    All methods implement dual-mode I/O (GUI-first, terminal fallback).
    
    **Architecture (v2.0):**
    This class is now a FACADE that orchestrates specialized helper modules:
    - ContentTransformers: Emoji/semantic/variable processing
    - HeaderRenderer: Header rendering logic
    - TextRenderer: Text and rich_text rendering
    """

    # Type hints for instance attributes
    display: Any  # Parent zDisplay instance
    zPrimitives: Any  # Primitives instance for I/O operations
    zColors: Any  # Colors instance for terminal styling

    # Helper modules (v2.0 Composition) - using Any to avoid circular type references
    ContentTransformers: Any
    HeaderRenderer: Any
    TextRenderer: Any
    CodeRenderer: Any
    JsonRenderer: Any
    FieldRenderer: Any

    def __init__(self, display_instance: Any) -> None:
        """Initialize BasicOutputs with parent display reference.
        
        Args:
            display_instance: Parent zDisplay instance providing primitives and colors
            
        Note:
            This is called by display_events.py (zEvents.__init__) during
            display initialization.
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives
        self.zColors = display_instance.zColors

        # Instantiate helper modules (v2.0 Decomposition)
        self.ContentTransformers = ContentTransformers(display_instance)
        self.HeaderRenderer = HeaderRenderer(display_instance)
        self.TextRenderer = TextRenderer(display_instance)
        self.CodeRenderer = CodeRenderer(display_instance)
        self.JsonRenderer = JsonRenderer(display_instance)
        self.FieldRenderer = FieldRenderer(display_instance)

    # Public API Methods - Delegate to specialized helper modules

    def header(
        self,
        label: str,
        color: str = DEFAULT_COLOR,
        indent: int = 0,
        style: str = DEFAULT_STYLE_FULL,
        semantic: Optional[str] = None,
        **kwargs
    ) -> None:
        """Display formatted section header with styling.
        
        FOUNDATION METHOD - Used by ALL 7 other event packages for displaying
        section headers with consistent styling.
        
        Delegates to HeaderRenderer for implementation.
        
        Args:
            label: Header text to display
            color: Color name for styling (default: RESET)
            indent: Indentation level (default: 0)
            style: Header line style - "full", "single", "wave", "star", "hash", "plus" (default: "full")
            semantic: DEPRECATED - Use _zHTML kwarg instead (backward compatibility)
            **kwargs: Additional parameters for GUI mode:
                _zHTML: Semantic HTML element type (e.g., "code", "strong")
                _context: Context dict for %variable resolution
        
        Returns:
            None
        
        Example:
            self.BasicOutputs.header("Section Title", color="CYAN", style="full")
            self.BasicOutputs.header("Error", color="RED", style="single")
            self.BasicOutputs.header("Code: %filename", _zHTML="code", _context={"filename": "app.py"})
        
        Note:
            Used by ALL 7 other event packages (Signals, BasicInputs, BasicData,
            TimeBased, AdvancedData, zSystem).
        """
        self.HeaderRenderer.render_header(
            label=label,
            color=color,
            indent=indent,
            style=style,
            semantic=semantic,
            kwargs=kwargs,
            content_transformers=self.ContentTransformers
        )

    def text(
        self,
        content: str,
        indent: int = 0,
        pause: bool = False,
        break_message: Optional[str] = None,
        break_after: Optional[bool] = None,
        semantic: Optional[str] = None,
        _context: Optional[dict] = None,
        color: Optional[str] = None,
        **kwargs
    ) -> None:
        """Display text with optional indentation and pause.
        
        FOUNDATION METHOD - Used extensively by zSystem events and TimeBased for
        displaying content with optional user acknowledgment.
        
        Delegates to TextRenderer for implementation.
        
        Implements dual-mode I/O pattern:
        1. GUI Mode: Send clean JSON event with pause metadata
        2. zCLI Mode: Display text, optionally pause for Enter key
        
        Args:
            content: Text content to display
            indent: Indentation level (default: 0, each level = 2 spaces)
            pause: Pause for user acknowledgment (default: False)
            break_message: Custom break message (default: "Press Enter to continue...")
            break_after: Legacy parameter - use 'pause' instead (backward compatibility)
            semantic: DEPRECATED - Use _zHTML kwarg instead (backward compatibility)
            _context: Context dict for %variable resolution (e.g., {"user": "Alice"})
            color: Optional color name (e.g. PRIMARY, SUCCESS, ERROR, WARNING, INFO, SECONDARY)
            **kwargs: Additional parameters (e.g., 'class' for zBifrost CSS classes)
        
        Returns:
            None
        
        Example:
            self.BasicOutputs.text("Operation complete")
            self.BasicOutputs.text("Details...", indent=1, pause=False)
            self.BasicOutputs.text("Warning!", pause=True, break_message="Press Enter to proceed")
            self.BasicOutputs.text("Styled text", indent=0, class="zLead")
            self.BasicOutputs.text("pip install requests", semantic="code")
            self.BasicOutputs.text("Press Enter", semantic="kbd")
            self.BasicOutputs.text("Hello %user!", _context={"user": "Alice"})
            self.BasicOutputs.text("All good!", color="SUCCESS")
        
        Note:
            Used by: zSystem (zDeclare, zSession, zCrumbs, zMenu),
                     TimeBased (progress bar labels, spinner text)
        """
        self.TextRenderer.render_text(
            content=content,
            indent=indent,
            pause=pause,
            break_message=break_message,
            break_after=break_after,
            semantic=semantic,
            _context=_context,
            color=color,
            kwargs=kwargs,
            content_transformers=self.ContentTransformers,
        )

    def code(
        self,
        content: str,
        language: Optional[str] = None,
        indent: int = 0,
        **kwargs
    ) -> None:
        """Display a code block with syntax highlighting.

        Delegates to CodeRenderer for implementation.

        Implements dual-mode I/O pattern:
        1. GUI Mode (Bifrost): Sends clean JSON 'code' event with content + language
        2. zCLI Mode: Renders a 100-char box with syntax-highlighted code lines

        Args:
            content: Raw code content to display
            language: Programming language for syntax highlighting (e.g. 'python', 'js')
            indent: Indentation level (default: 0)
            **kwargs: Additional parameters forwarded to the GUI event

        Example:
            self.BasicOutputs.code("print('hello')", language="python")
            self.BasicOutputs.code(code_str, language="zolo", indent=1)
        """
        self.CodeRenderer.render_code(
            content=content,
            language=language,
            indent=indent,
            **kwargs,
        )

    def json_data(
        self,
        data: Any,
        indent_size: int = 2,
        indent: int = 0,
        color: bool = False
    ) -> None:
        """Display JSON with pretty formatting and optional syntax coloring.
        
        FOUNDATION METHOD - Provides professional JSON display with syntax coloring
        for data visualization across all display contexts.
        
        Delegates to JsonRenderer for implementation.
        
        Implements dual-mode I/O pattern:
        1. GUI Mode: Send clean JSON event with data
        2. zCLI Mode: Format JSON with optional syntax coloring
        
        Args:
            data: Data to serialize as JSON (dict, list, or any JSON-serializable type)
            indent_size: JSON indentation size (default: 2)
            indent: Base indentation level (default: 0, each level = 2 spaces)
            color: Enable syntax coloring for terminal (default: False)
                   - Cyan: JSON keys
                   - Green: String values
                   - Yellow: Numeric values
                   - Magenta: Booleans and null
        
        Returns:
            None
        
        Example:
            data = {"name": "John", "age": 30, "active": True}
            self.BasicOutputs.json_data(data, color=True, indent_size=2)
            # Output (colored):
            #   {
            #     "name": "John",    (keys in cyan, values in green)
            #     "age": 30,         (number in yellow)
            #     "active": true     (boolean in magenta)
            #   }
        
        Note:
            Used by: display_delegates, zOpen, zFunc, zShell, zAuth
            Composes with: JsonRenderer for serialization and coloring
        """
        if data is None:
            return

        # Try GUI mode first
        if self.JsonRenderer.try_json_gui_mode(data, indent_size, indent):
            return

        # zCLI mode - render with JsonRenderer
        self.JsonRenderer.render_json_terminal(
            data,
            indent_size,
            indent,
            color,
            output_callback=self.text  # Pass text method as callback
        )

    # Signal Methods (colored feedback messages)

    def error(self, content: str, indent: int = 0, flush: bool = False) -> None:
        """Display error message with red color (semantic feedback).
        
        Args:
            content: Error message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed .zAlert block instead of an
                inline colored line. Ignored in terminal mode.
        
        Example:
            outputs.error("Operation failed")
            outputs.error("Invalid input detected", indent=1)
        """
        # Try GUI mode first
        if self.zPrimitives.send_gui_event("error", {
            "content": content,
            "indent": indent,
            "flush": flush
        }):
            return

        # Terminal mode - apply red color (flush is GUI-only, ignored here)
        colored = f"{self.zColors.RED}{content}{self.zColors.RESET}"
        self.text(colored, indent=indent, break_after=False)

    def warning(self, content: str, indent: int = 0, flush: bool = False) -> None:
        """Display warning message with yellow color (semantic feedback).
        
        Args:
            content: Warning message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed .zAlert block instead of an
                inline colored line. Ignored in terminal mode.
        
        Example:
            outputs.warning("Deprecated feature in use")
        """
        # Try GUI mode first
        if self.zPrimitives.send_gui_event("warning", {
            "content": content,
            "indent": indent,
            "flush": flush
        }):
            return

        # Terminal mode - apply yellow color (flush is GUI-only, ignored here)
        colored = f"{self.zColors.YELLOW}{content}{self.zColors.RESET}"
        self.text(colored, indent=indent, break_after=False)

    def success(self, content: str, indent: int = 0, flush: bool = False) -> None:
        """Display success message with green color (semantic feedback).
        
        Args:
            content: Success message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed .zAlert block instead of an
                inline colored line. Ignored in terminal mode.
        
        Example:
            outputs.success("Operation completed successfully")
        """
        # Try GUI mode first
        if self.zPrimitives.send_gui_event("success", {
            "content": content,
            "indent": indent,
            "flush": flush
        }):
            return

        # Terminal mode - apply green color (flush is GUI-only, ignored here)
        colored = f"{self.zColors.GREEN}{content}{self.zColors.RESET}"
        self.text(colored, indent=indent, break_after=False)

    def info(self, content: str, indent: int = 0, flush: bool = False) -> None:
        """Display info message with cyan color (semantic feedback).
        
        Args:
            content: Info message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed .zAlert block instead of an
                inline colored line. Ignored in terminal mode.
        
        Example:
            outputs.info("Hint: Use --verbose for more details")
        """
        # Try GUI mode first
        if self.zPrimitives.send_gui_event("info", {
            "content": content,
            "indent": indent,
            "flush": flush
        }):
            return

        # Terminal mode - apply cyan color (flush is GUI-only, ignored here)
        colored = f"{self.zColors.CYAN}{content}{self.zColors.RESET}"
        self.text(colored, indent=indent, break_after=False)

    def primary(self, content: str, indent: int = 0, flush: bool = False) -> None:
        """Display a primary-brand emphasis signal (non-status).

        Not one of the four status verdicts — a branded emphasis line using the
        primary palette colour. Same dual-mode contract as the status signals.

        Args:
            content: Message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed toast instead of an inline
                card. Ignored in terminal mode.
        """
        # Try GUI mode first
        if self.zPrimitives.send_gui_event("primary", {
            "content": content,
            "indent": indent,
            "flush": flush
        }):
            return

        # Terminal mode - apply primary color (flush is GUI-only, ignored here)
        colored = f"{self.zColors.PRIMARY}{content}{self.zColors.RESET}"
        self.text(colored, indent=indent, break_after=False)

    def secondary(self, content: str, indent: int = 0, flush: bool = False) -> None:
        """Display a secondary-brand emphasis signal (non-status).

        The companion to primary — a branded emphasis line using the secondary
        palette colour. Same dual-mode contract as the status signals.

        Args:
            content: Message text
            indent: Indentation level (default: 0)
            flush: GUI-only — render as a flushed toast instead of an inline
                card. Ignored in terminal mode.
        """
        # Try GUI mode first
        if self.zPrimitives.send_gui_event("secondary", {
            "content": content,
            "indent": indent,
            "flush": flush
        }):
            return

        # Terminal mode - apply secondary color (flush is GUI-only, ignored here)
        colored = f"{self.zColors.SECONDARY}{content}{self.zColors.RESET}"
        self.text(colored, indent=indent, break_after=False)

    def zMarker(self, label: str = "Marker", color: str = "MAGENTA", indent: int = 0) -> None:
        """Display visual workflow marker (flow control signal).
        
        Args:
            label: Marker label text (default: "Marker")
            color: Color name for label (default: "MAGENTA")
            indent: Indentation level (default: 0)
        
        Example:
            outputs.zMarker("Processing Stage 1")
            outputs.zMarker("Validation Phase", color="CYAN")
        """
        # Try GUI mode first
        if self.zPrimitives.send_gui_event("zMarker", {
            "label": label,
            "color": color,
            "indent": indent
        }):
            return

        # Terminal mode - create visual marker with separator lines
        color_code = getattr(self.zColors, color.upper(), self.zColors.MAGENTA)
        marker_line = "─" * 80
        colored_label = f"{color_code}{label}{self.zColors.RESET}"

        # Output marker with blank lines
        self.text("", indent=indent, break_after=False)
        self.text(marker_line, indent=indent, break_after=False)
        self.text(colored_label, indent=indent, break_after=False)
        self.text(marker_line, indent=indent, break_after=False)
        self.text("", indent=indent, break_after=False)
