# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/b_primitives/display_primitives.py

"""
Primitive I/O Operations for zDisplay - Foundation Layer (Unified Facade).

This module provides the foundational I/O primitives for the entire zDisplay subsystem.
It composes PrimitivesOutputs and PrimitivesInputs facades into a single unified interface.

Architecture:
    - Unified Facade: zPrimitives (this file) - composes inputs + outputs
    - Output Facade: display_primitives_outputs.py (PrimitivesOutputs)
    - Input Facade: display_primitives_inputs.py (PrimitivesInputs)
    - Outputs: outputs/output_*.py - output primitive implementations
    - Inputs: inputs/input_*.py - input primitive implementations
    - Each primitive is self-contained in its own file for scalability

⚠️ CRITICAL: DO NOT ADD COMPOUND OPERATIONS TO THIS TIER ⚠️

This tier represents the BINARY VALUES of the system - computer science absolutes
that map directly to terminal syscalls. These are foundational building blocks and
should RARELY be edited.

Primitives are:
    - Direct wrappers around print(), input(), getpass()
    - Pure I/O operations with no business logic
    - The absolute minimum required for terminal interaction
    - Stable, rarely-changing foundation

If you're adding functionality that involves:
    ❌ Rendering/formatting beyond raw text
    ❌ Validation or complex input handling  
    ❌ Combining multiple operations
    ❌ UI/UX concerns beyond basic I/O
    ❌ Interactive widgets or selections

Then it belongs in a HIGHER tier, not here:
    - c_basic: Formatted output (headers, signals, tables)
    - d_compounds: Compound widgets (selections, confirmations, menus)
    - e_advanced: Complex UI components (wizards, forms, dialogs)

Developer/LLM Note:
    Keep primitives pure. Build complexity in higher layers.
    This is the bedrock - don't pollute it with compound operations.

Architecture:
    zPrimitives is the foundation layer (Layer 1) that provides exclusive mode I/O:
    
    - Terminal Mode (zCLI): Direct console I/O via print/input (synchronous)
    - Bifrost Mode: WebSocket events via zComm (asynchronous)
    
    Mode is resolved ONCE at zDisplay init and never re-checked.

Terminal/Bifrost Mode Resolution:
    Mode is computed once at zDisplay.__init__():
    
    Mode Detection:
        - Reads session[SESSION_KEY_ZMODE] (set by zConfig from zSpark)
        - Terminal modes: "zCLI", "Walker", "" (empty string)
        - Bifrost modes: Everything else (e.g., "zBifrost", "WebSocket")
    
    Mode Flag (_is_bifrost):
        - Computed once: self._is_bifrost = mode not in (zCLI, Walker, empty)
        - Propagated to all primitive classes at construction
        - No per-call mode checking
    
    Exclusive Mode Behavior:
        - zCLI mode: Outputs to terminal ONLY (print/input)
        - Bifrost mode: Sends to zComm WebSocket ONLY (no terminal output)
        - Each operation routes to one path or the other, never both

Layer 1 Position:
    As a Layer 1 (Foundation) module, zPrimitives:
    
    Dependencies (Layer 0):
        - zConfig: Provides session[SESSION_KEY_ZMODE] for mode detection
        - zComm: Provides WebSocket broadcast for Bifrost output
    
    Used By (Layer 2):
        - events/display_event_outputs.py (output formatting)
        - events/display_event_signals.py (error/warning/success)
        - events/display_event_data.py (list/json display)
        - events/display_event_inputs.py (user input collection)
        - events/display_event_widgets.py (progress bars, spinners)
        - events/display_event_advanced.py (tables, complex data)
        - events/display_event_system.py (menus, dialogs)
    
    Total: 56 references from all event files (post-zAuthEvents removal)

Dual-Mode I/O Methods:
    Output Methods (synchronous):
        - raw(content, flush): Raw output, no formatting (preferred API)
        - line(content): Single line with newline (preferred API)
        - block(content): Multi-line block with final newline (preferred API)
        
        Legacy aliases (backward compatibility):
        - write_raw → raw
        - write_line → line
        - write_block → block
        
        Behavior:
            1. ALWAYS output to terminal (print)
            2. IF in Bifrost mode, ALSO send via WebSocket
    
    Input Methods (synchronous OR asynchronous):
        - read_string(prompt): Read text input
        - read_password(prompt): Read masked password input
        
        Return Types:
            - zCLI mode: Returns str (synchronous)
            - Bifrost mode: Returns asyncio.Future (asynchronous)
            - Type hint: Union[str, asyncio.Future]
        
        Note:
            - read_bool() and read_range() have been moved to d_compounds
            - They are interactive widgets, not primitives (use selection/button patterns)
            - Access via: display.zEvents.BasicInputs.read_bool() / read_range()

zBifrost Integration:
    WebSocket Output:
        - Uses zcli.bifrost.orchestrator.broadcast() for all GUI output
        - Sends JSON events with structure:
            {
                "event": "output",
                "type": "raw" | "line" | "block",
                "content": "...",
                "timestamp": <unix_time>
            }
    
    WebSocket Input:
        - Sends input request via broadcast_websocket()
        - Returns asyncio.Future that will be resolved by GUI client
        - GUI client responds via handle_input_response()
        - Request structure:
            {
                "event": "display_prompt_request",
                "requestId": "<uuid>",
                "type": "string" | "password",
                "prompt": "...",
                "timestamp": <unix_time>
            }

Thread Safety & Async:
    - Async future management for GUI input requests
    - pending_input_requests: Dict[str, Any] (unused, kept for compatibility)
    - response_futures: Dict[str, asyncio.Future] (active futures)
    - Handles RuntimeError when no event loop is running (tests)
    - Graceful fallback to terminal input if GUI request fails

Error Handling:
    - Silent failures for GUI operations (terminal fallback)
    - Comprehensive hasattr() checks prevent crashes
    - Try/except blocks around all WebSocket operations
    - GUI failures never break terminal output

zSession Integration:
    Mode Detection Chain:
        1. zConfig sets session[SESSION_KEY_ZMODE] during Layer 0 init
        2. zDisplay.__init__() reads: self.mode = session.get(SESSION_KEY_ZMODE, "zCLI")
        3. zPrimitives.is_bifrost_mode() returns the pre-computed self._is_bifrost flag
    
    Session Keys Used:
        - SESSION_KEY_ZMODE: Read via self.display.mode (not directly accessed)

Usage Pattern:
    From event files (Layer 2):
        ```python
        # Output (always synchronous) - Preferred API
        self.zPrimitives.line("Hello World")
        self.zPrimitives.raw("Loading...")
        
        # Input (synchronous OR asynchronous)
        result = self.zPrimitives.read_string("Enter name: ")
        if isinstance(result, asyncio.Future):
            # Bifrost mode - await the future
            name = await result
        else:
            # zCLI mode - use directly
            name = result
        ```

Backward-Compatible Aliases:
    Legacy methods maintained for backward compatibility:
        - .write_raw → .raw (preferred)
        - .write_line → .line (preferred)
        - .write_block → .block (preferred)
    
    Other aliases:
        - .read → .read_string
"""

from zOS import os, shutil, subprocess, Any, Optional, Dict, time, asyncio
from ..display_constants import (
    _TERMINAL_COLS_DEFAULT,
    _TERMINAL_COLS_MIN,
    _TERMINAL_COLS_MAX,
    _DEFAULT_PROMPT,
    _EVENT_TYPE_DISPLAY_PROMPT_REQUEST,
    _EVENT_TYPE_OUTPUT,
    _KEY_EVENT,
    _KEY_REQUEST_ID,
    _KEY_TYPE,
    _KEY_PROMPT,
    _KEY_CONTENT,
    _KEY_TIMESTAMP,
)

# Import primitive facades
from .display_primitives_outputs import PrimitivesOutputs
from .display_primitives_inputs import PrimitivesInputs


class zPrimitives:
    """Primitive I/O operations unified facade - composes input and output facades.
    
    Architecture:
        This class composes PrimitivesOutputs and PrimitivesInputs into a single
        unified interface for all primitive I/O operations.
        
        Output Primitives (via PrimitivesOutputs):
            - raw() → outputs/output_raw.py
            - line() → outputs/output_line.py
            - block() → outputs/output_block.py
        
        Input Primitives (via PrimitivesInputs):
            - read_string() → inputs/input_string.py
            - read_password() → inputs/input_password.py
    """

    # Type hints for instance attributes
    display: Any  # Parent zDisplay instance
    _is_bifrost: bool  # Pre-computed mode flag (resolved at init)

    # Facade instances
    _outputs: PrimitivesOutputs
    _inputs: PrimitivesInputs

    def __init__(self, display_instance: Any) -> None:
        """Initialize zPrimitives facade with output and input facades.
        
        Args:
            display_instance: Parent zDisplay instance (provides mode, zcli access)
        """
        self.display = display_instance

        # Store pre-computed mode flag (resolved once at zDisplay init)
        self._is_bifrost = display_instance._is_bifrost

        # Instantiate output and input facades
        self._outputs = PrimitivesOutputs(display_instance)
        self._inputs = PrimitivesInputs(display_instance)

    def get_terminal_columns(self) -> int:
        """Detect terminal width (columns) at print time and clamp it.
        
        Rules:
            - Detect dynamically (env COLUMNS, shutil.get_terminal_size, tput cols)
            - Clamp to [60–120]
            - Fallback to 80 when detection is unavailable
        """
        cols: Optional[int] = None

        # 1) $COLUMNS (fast path)
        try:
            env_cols = os.environ.get("COLUMNS", "").strip()
            if env_cols.isdigit():
                cols = int(env_cols)
        except Exception:
            cols = None

        # 2) Equivalent: shutil.get_terminal_size
        if not cols:
            try:
                cols = int(shutil.get_terminal_size(fallback=(_TERMINAL_COLS_DEFAULT, 24)).columns)
            except Exception:
                cols = None

        # 3) tput cols (best-effort)
        if not cols:
            try:
                result = subprocess.run(
                    ["tput", "cols"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                out = (result.stdout or "").strip()
                if out.isdigit():
                    cols = int(out)
            except Exception:
                cols = None

        if not cols or cols <= 0:
            cols = _TERMINAL_COLS_DEFAULT

        # Clamp
        if cols < _TERMINAL_COLS_MIN:
            cols = _TERMINAL_COLS_MIN
        elif cols > _TERMINAL_COLS_MAX:
            cols = _TERMINAL_COLS_MAX

        return cols

    # Output Primitives - Delegate to PrimitivesOutputs facade

    def raw(self, content: str, flush: bool = True) -> None:
        """Write raw content with no formatting or newline.
        
        Delegates to: PrimitivesOutputs.raw()
        """
        self._outputs.raw(content, flush)

    def line(self, content: str) -> None:
        """Write single line, ensuring newline.
        
        Delegates to: PrimitivesOutputs.line()
        """
        self._outputs.line(content)

    def block(self, content: str) -> None:
        """Write multi-line block, ensuring final newline.
        
        Delegates to: PrimitivesOutputs.block()
        """
        self._outputs.block(content)

    # Input Primitives - Delegate to PrimitivesInputs facade

    def read_string(self, prompt: str = "", **kwargs):
        """Read string input - terminal (synchronous) or GUI (buffered event).
        
        Delegates to: PrimitivesInputs.read_string()
        """
        return self._inputs.read_string(prompt, **kwargs)

    def read_password(self, prompt: str = "") -> str:
        """Read password input - terminal (synchronous) or GUI (buffered event).
        
        Delegates to: PrimitivesInputs.read_password()
        """
        return self._inputs.read_password(prompt)

    # Bifrost Output Helper (shared by output primitives)

    def _send_to_bifrost(self, content: str, write_type: str) -> None:
        """Send output event to Bifrost via zComm WebSocket.
        
        Shared helper for output primitives (raw, line, block) in Bifrost mode.
        
        Args:
            content: Text content to send (newlines already stripped)
            write_type: Type of write operation (_WRITE_TYPE_RAW, _WRITE_TYPE_LINE, _WRITE_TYPE_BLOCK)
        """
        if not self.display or not hasattr(self.display, 'zos'):
            return

        zos = self.display.zos
        if not hasattr(zos, 'comm') or not hasattr(zos.comm, 'websocket_events'):
            return

        # Remove trailing newlines for JSON
        content = content.rstrip('\n') if content else ""

        # Create output event
        event_data = {
            _KEY_EVENT: _EVENT_TYPE_OUTPUT,
            _KEY_TYPE: write_type,
            _KEY_CONTENT: content,
            _KEY_TIMESTAMP: time.time()
        }

        # Delegate to zComm
        zos.comm.websocket_events.send_event(event_data)

    # Legacy / Deprecated Methods (kept for backward compatibility)

    def _generate_request_id(self) -> str:
        """Generate unique request ID - delegate to zComm.
        
        Returns:
            str: UUID string for tracking input request/response pairs
        """
        if self.display and hasattr(self.display, 'zos'):
            zos = self.display.zos
            if hasattr(zos, 'comm') and hasattr(zos.comm, 'websocket_input'):
                return zos.comm.websocket_input.generate_request_id()

        # Fallback (shouldn't happen, but safe)
        import uuid
        return str(uuid.uuid4())

    def _send_input_request(
        self, request_type: str, prompt: str = _DEFAULT_PROMPT, **kwargs
    ) -> Optional['asyncio.Future']:
        """Common GUI input primitive - delegate to zComm WebSocket input API.
        
        Creates an asyncio.Future that will be resolved when the GUI client responds.
        
        Args:
            request_type: Type of input (_INPUT_TYPE_STRING or _INPUT_TYPE_PASSWORD)
            prompt: Prompt text to display to user
            **kwargs: Additional request parameters (e.g., masked=True for passwords)
        
        Returns:
            Optional[asyncio.Future]: Future that will resolve to user input,
                                      or None if GUI request fails (use terminal fallback)
        
        Architecture:
            This is now a thin delegation layer. The actual input coordination
            logic lives in zComm (L1_Foundation), where it belongs.
        """
        # Access zos through display instance
        if not self.display or not hasattr(self.display, 'zos'):
            return None

        zos = self.display.zos
        if not hasattr(zos, 'comm') or not hasattr(zos.comm, 'websocket_input'):
            return None

        # Create future via zComm's input handler
        future = zos.comm.websocket_input.create_request(request_type, prompt, **kwargs)
        if not future:
            return None

        # Also send the input request event for GUI rendering
        request_id = zos.comm.websocket_input.generate_request_id()
        request_event = {
            _KEY_EVENT: _EVENT_TYPE_DISPLAY_PROMPT_REQUEST,
            _KEY_REQUEST_ID: request_id,
            _KEY_TYPE: request_type,
            _KEY_PROMPT: prompt,
            _KEY_TIMESTAMP: time.time(),
            **kwargs
        }

        # Broadcast input request event
        zos.comm.websocket_events.send_event(request_event)

        return future

    def handle_input_response(self, request_id: str, value: Any) -> None:
        """Handle input response from GUI client - delegate to zComm.
        
        Resolves the asyncio.Future associated with the given request_id.
        Called by zComm when GUI client sends input response.
        
        Args:
            request_id: UUID of the original input request
            value: User's input value from GUI client
        
        Architecture:
            This is now a thin delegation layer. The actual input coordination
            logic lives in zComm (L1_Foundation), where it belongs.
        """
        # Delegate to zComm WebSocket input handler
        if not self.display or not hasattr(self.display, 'zos'):
            return

        zos = self.display.zos
        if not hasattr(zos, 'comm') or not hasattr(zos.comm, 'websocket_input'):
            return

        # Use zComm's input coordination API
        zos.comm.websocket_input.resolve_input(request_id, value)

    def send_gui_event(self, event_name: str, data: Dict[str, Any]) -> bool:
        """GUI primitive - delegate to zComm WebSocket events API.
        
        Used by event handlers to send structured events directly to GUI clients.
        Events are buffered and broadcasted via zComm's WebSocket infrastructure.
        
        Args:
            event_name: Name of the display event (e.g., "header", "error")
            data: Event data dictionary to send to GUI
        
        Returns:
            bool: True if event was sent/buffered successfully, False otherwise
        
        Notes:
            - Only works in Bifrost mode (returns False in terminal mode)
            - Delegates to zComm.websocket_events for actual implementation
            - Events are captured in buffer AND broadcasted immediately
            - Example: send_gui_event("header", {"label": "Test", "color": "BLUE"})
        
        Architecture:
            This is now a thin delegation layer. The actual WebSocket communication
            logic lives in zComm (L1_Foundation), where it belongs.
        """
        # Only works in GUI mode
        if not self._is_bifrost:
            return False

        # Delegate to zComm WebSocket events API
        if not self.display or not hasattr(self.display, 'zos'):
            return False

        zos = self.display.zos
        if not hasattr(zos, 'comm') or not hasattr(zos.comm, 'websocket_events'):
            return False

        # Resolve field rules to native HTML attrs so the browser enforces the
        # SAME rule the zCLI input hub runs (e.g. a type preset's regex).
        #
        # DUAL-PATH TRUTH: this chokepoint only sees RUNTIME/interactive dialogs
        # (display.zDialog → here). INLINE page forms do NOT pass through here —
        # they stream as raw zUI metadata via the display-tree path
        # (zdisplay_orchestrator → renderForm) and never hit send_gui_event. The
        # client mirrors these rules in form_renderer._resolveFieldRules to cover
        # BOTH routes; this server pass is the belt to that client suspenders for
        # the interactive route. Terminal mode already returned above, so this is
        # purely a client concern and never touches the zCLI prompt messages.
        if event_name == 'zDialog':
            data = self._resolve_dialog_field_rules(data)

        # Use zComm's high-level event API
        return zos.comm.websocket_events.send_display_event(
            event_name,
            data,
            special_events=['zDash', 'zMenu', 'zDialog']
        )

    def _resolve_dialog_field_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of a zDialog payload whose fields carry resolved attrs.

        Uses field_rules.html_attrs (the SSOT shared with the zCLI prompt) to
        fill native HTML attributes — notably a type preset's ``pattern`` — that
        the browser enforces. Author-declared keys always win; bare-string
        fields become dicts so the attrs can ride along (the FormRenderer still
        auto-detects their type from the name). The original (cached) field
        objects are never mutated.
        """
        fields = data.get('fields') if isinstance(data, dict) else None
        if not isinstance(fields, list) or not fields:
            return data

        from .inputs.field_rules import html_attrs  # SSOT for field rules

        enriched = []
        changed = False
        for field in fields:
            attrs = html_attrs(field)
            if not attrs:
                enriched.append(field)
                continue
            base = dict(field) if isinstance(field, dict) else {'zConv': str(field)}
            for key, value in attrs.items():
                if key not in base:
                    base[key] = value
                    changed = True
            enriched.append(base)

        if not changed:
            return data
        out = dict(data)
        out['fields'] = enriched
        return out

    @property
    def write_raw(self):
        """Backward-compatible alias for raw().
        
        Note: Prefer using .raw() for cleaner API calls.
        
        Returns:
            Callable: The raw method
        """
        return self.raw

    @property
    def write_line(self):
        """Backward-compatible alias for line().
        
        Note: Prefer using .line() for cleaner API calls.
        
        Returns:
            Callable: The line method
        """
        return self.line

    @property
    def write_block(self):
        """Backward-compatible alias for block().
        
        Note: Prefer using .block() for cleaner API calls.
        
        Returns:
            Callable: The block method
        """
        return self.block

    @property
    def read(self):
        """Alias for read_string.
        
        Returns:
            Callable: The read_string method
        """
        return self.read_string

    # Bifrost/WebSocket Helpers (Display-Aware)

    def is_bifrost_mode(self) -> bool:
        """Check if running in Bifrost/GUI mode (vs zCLI mode).
        
        Returns pre-computed mode flag resolved at zDisplay init.
        
        Returns:
            bool: True if in Bifrost/GUI mode (needs WebSocket output),
                  False if in zCLI mode (print/input only)
        """
        return self._is_bifrost

    def emit_websocket_event(self, event_data: Dict[str, Any]) -> None:
        """Emit a WebSocket event for zBifrost mode.
        
        Thin wrapper that delegates to zComm's WebSocket event system (L1 Foundation).
        This maintains proper layer separation: L2 (zDisplay) → L1 (zComm).
        
        Args:
            event_data: Event dictionary with 'event' key and payload
        
        Returns:
            None
        
        Example event_data:
            {
                "event": "progress_bar",
                "progressId": "progress_Processing_Files",
                "current": 60,
                "total": 100,
                "label": "Processing Files"
            }
        
        Notes:
            - Only sends if in Bifrost mode (pre-computed at init)
            - Delegates to zComm.websocket_events.send_event() (L1 Foundation)
            - Thread-safe: zComm handles asyncio coordination
            - Graceful failure: Silent return if zComm not available
        """
        if not self._is_bifrost:
            return

        zos = self.display.zos if hasattr(self.display, 'zos') else None
        if not zos or not hasattr(zos, 'comm'):
            return

        if hasattr(zos.comm, 'websocket_events'):
            zos.comm.websocket_events.send_event(event_data)

    def try_gui_event(self, event_name: str, data: Dict[str, Any]) -> bool:
        """Try to send GUI event to Bifrost mode.
        
        Attempts to send a GUI event via WebSocket to the frontend. Returns True
        if the event was sent (Bifrost mode), False if in zCLI mode.
        
        Args:
            event_name: WebSocket event name (e.g., "zSession", "zDash")
            data: Event data dictionary to send to frontend
        
        Returns:
            bool: True if GUI mode succeeded (message sent), False if zCLI mode
        
        Usage:
            if self.display.zPrimitives.try_gui_event("zSession", {"session": data}):
                return  # GUI handled it
            # Fall back to zCLI mode rendering
        
        Notes:
            - Delegates to send_gui_event()
            - Used by orchestration events (zSystem) for dual-mode rendering
            - Safe to call in any mode (returns False if not Bifrost)
        """
        return self.send_gui_event(event_name, data)

    # Expose PrimitivesOutputs and PrimitivesInputs for direct access if needed
    @property
    def Outputs(self):
        """Access to PrimitivesOutputs facade.
        
        Returns:
            PrimitivesOutputs: Output primitives facade
        """
        return self._outputs

    @property
    def Inputs(self):
        """Access to PrimitivesInputs facade.
        
        Returns:
            PrimitivesInputs: Input primitives facade
        """
        return self._inputs
