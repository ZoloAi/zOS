# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/e_advanced/advanced_table.py
"""
Table Events - Database Query Result Display
==============================================

This module provides table rendering events for displaying database query
results with pagination, column headers, and dual-mode rendering (Terminal
ASCII tables vs. Bifrost clean JSON events).

Purpose:
    - Display tabular data from database queries
    - Handle pagination with limit/offset
    - Format columns with fixed width and truncation
    - Support both Terminal (ASCII) and Bifrost (JSON) modes

Public Methods:
    zTable(title, columns, rows, limit, offset, show_header, interactive)
        Display data table with optional pagination

Dependencies:
    - advanced_pagination: Pagination utility for data slicing
    - display_event_helpers: is_bifrost_mode, emit_websocket_event
    - display_primitives: zPrimitives for terminal I/O
    - display_constants: Event names, keys, defaults

Extracted From:
    display_event_advanced.py (lines 501-1049)
"""

import re

from zOS import Any, Optional, List, Union, Dict  # Union used for truncate type
from zOS.L3_Abstraction.m_zData.zData_modules.shared.chunk_bridge import (
    capture,
    chunking_active,
)

# Import pagination utility
from .advanced_pagination import (  # pylint: disable=relative-beyond-top-level
    Pagination,
    KEY_SHOWING_START,
    KEY_SHOWING_END,
    KEY_HAS_MORE,
    DEFAULT_OFFSET
)

# No infrastructure imports needed (uses primitives directly)

# zTable event dictionary keys
KEY_TITLE: str = "title"
KEY_CAPTION: str = "caption"
KEY_COLUMNS: str = "columns"
KEY_ROWS: str = "rows"
KEY_LIMIT: str = "limit"
KEY_OFFSET: str = "offset"
KEY_SHOW_HEADER: str = "show_header"
KEY_TRUNCATE: str = "truncate"

# Default values
DEFAULT_COL_WIDTH: int = 15          # fallback width used only when col_widths unavailable
DEFAULT_TRUNCATE_SUFFIX: str = "..."

# truncate=False (default): content-fit columns, no clipping
# truncate=N (int): fixed N-char columns with "..." suffix
DEFAULT_TRUNCATE: bool = False

# Colors and styles
DEFAULT_HEADER_COLOR: str = "CYAN"
DEFAULT_TABLE_STYLE: str = "full"

# Messages
MSG_NO_COLUMNS: str = "No columns defined for table"
MSG_NO_ROWS: str = "No rows to display"
MSG_MORE_ROWS: str = "... {count} more rows"
MSG_SHOWING_RANGE: str = "{title} (showing {start}-{end} of {total})"

# Characters
CHAR_SEPARATOR: str = "─"
_CHAR_SPACE: str = " "

# Strips ANSI SGR codes so column widths/padding count VISIBLE characters only.
# Markdown rendering removes markers (** ` *) and adds invisible ANSI — both would
# otherwise corrupt content-fit width math. Compiled once.
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

# Navigation constants (interactive mode)
NAV_PROMPT: str = "Navigate: [n]ext | [p]revious | [f]irst | [l]ast | [#] jump | [q]uit: "
NAV_INVALID: str = "Invalid command. Use: n, p, f, l, # (page number), or q"
NAV_ALREADY_FIRST: str = "Already on first page"
NAV_ALREADY_LAST: str = "Already on last page"
NAV_INVALID_PAGE: str = "Invalid page. Enter 1-{total_pages}"


class TableEvents:
    """
    Table rendering events for database query results.
    
    Provides zTable() for displaying tabular data with pagination,
    column headers, and dual-mode rendering.
    
    Composition:
        - zPrimitives: For terminal I/O
        - zColors: For colored output
        - BasicOutputs: For header/text rendering (set after zEvents init)
        - Signals: For warning/info messages (set after zEvents init)
        - Pagination: For data slicing
    
    Usage:
        # Via AdvancedData coordinator
        display.zTable(
            title="Query Results",
            columns=["id", "name", "email"],
            rows=[{"id": 1, "name": "Alice", "email": "alice@example.com"}],
            limit=20,
            offset=0
        )
    """

    # Class-level type declarations
    display: Any
    zPrimitives: Any
    zColors: Any
    BasicOutputs: Optional[Any]
    Signals: Optional[Any]
    pagination: Pagination

    def __init__(self, display_instance: Any) -> None:
        """
        Initialize TableEvents with reference to parent display instance.
        
        Args:
            display_instance: Parent display instance (AdvancedData or zDisplay)
        
        Returns:
            None
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives if hasattr(display_instance, 'zPrimitives') else None
        self.zColors = display_instance.zColors if hasattr(display_instance, 'zColors') else None
        self.BasicOutputs = None  # Will be set after zEvents initialization
        self.Signals = None       # Will be set after zEvents initialization
        self.pagination = Pagination()
        # zMD inline SSOT engines — lazily built on first cell render (see
        # _parse_inline_markdown) to avoid import cycles during display init.
        self._md_parser = None
        self._content_transformers = None

    def zTable(
        self,
        title: Optional[str] = None,
        columns: Optional[List[str]] = None,
        rows: Optional[List[Union[Dict[str, Any], List[Any]]]] = None,
        limit: Optional[int] = None,
        offset: int = DEFAULT_OFFSET,
        show_header: bool = True,
        zPages: bool = False,
        caption: Optional[str] = None,
        truncate: Union[bool, int] = DEFAULT_TRUNCATE,
        _zColumn: Optional[Dict[str, str]] = None,
        **passthrough: Any,
    ) -> None:
        """
        Display data table with optional pagination and formatting for zCLI/Bifrost modes.

        Pure display primitive — renders whatever columns/rows are passed in.
        Data fetching is the responsibility of the caller (e.g. zData: read).

        Args:
            title: Table title/heading
            columns: List of column names
            rows: List of rows (dicts or lists)
            limit: Maximum rows to display (None=all)
            offset: Starting row index (0-based)
            show_header: Show column headers (default: True)
            zPages: Enable paginated navigation controls
            caption: Optional table caption
            truncate: Column width control (zCLI only):
                - False (default): content-fit columns — no clipping
                - int (e.g. 15, 20): fixed N-char columns, values clipped with "..."
            _zColumn: Per-column style overrides

        Returns:
            None

        zCLI Mode:
            Renders formatted ASCII table with headers, separators, content-fit or fixed columns

        Bifrost Mode:
            Sends clean JSON event with raw data for frontend rendering (truncate ignored)

        Usage:
            display.zTable(
                title="Users",
                columns=["id", "name", "email"],
                rows=[{"id": 1, "name": "Alice", "email": "alice@example.com"}],
                limit=20,
                truncate=20
            )
        """
        rows = rows or []
        columns = columns or []

        # Auto-derive columns from first row when columns are omitted
        if not columns and rows and isinstance(rows[0], dict):
            columns = list(rows[0].keys())
        # Bifrost mode - send clean JSON event (truncate is zCLI-only, not included)
        if self.display.zPrimitives.is_bifrost_mode():
            event_data = {
                "event": "zTable",
                KEY_COLUMNS: columns,
                KEY_ROWS: rows,
                KEY_LIMIT: limit,
                KEY_OFFSET: offset,
                KEY_SHOW_HEADER: show_header,
                "zPages": zPages,
            }
            if title:
                event_data[KEY_TITLE] = title
            if caption:
                event_data[KEY_CAPTION] = caption
            if _zColumn:
                event_data['_zColumn'] = _zColumn
            # Forward any extra display props (_zClass, _zStyle, etc.) as JSON pass-through
            if passthrough:
                event_data.update(passthrough)
            # During a chunked render, hand the payload to the contract: a live read
            # is buffered for inline injection, a static declaration is dropped (it is
            # already inline). Otherwise emit it as a standalone event.
            zos = self.display.zos if hasattr(self.display, 'zos') else None
            if chunking_active(zos):
                capture(zos, event_data, only_live=True)
            else:
                self.display.zPrimitives.emit_websocket_event(event_data)
            return

        # zCLI mode: auto-fetch rows when model is declared but no rows supplied.
        # zTable: {model: '@.models...'} is SSOT — same syntax works in both CLI and Bifrost.
        model_ref = passthrough.get('model') if passthrough else None
        if model_ref and not rows:
            zos = self.display.zos if hasattr(self.display, 'zos') else None
            if zos:
                try:
                    fetched = zos.dispatch.handle(
                        'zData',
                        {'action': 'read', 'model': model_ref, 'silent': True},
                        walker=getattr(zos, 'walker', None)
                    )
                    if isinstance(fetched, list):
                        rows = fetched
                        if not columns and rows and isinstance(rows[0], dict):
                            columns = list(rows[0].keys())
                except Exception:  # pylint: disable=broad-except
                    pass

        # zCLI mode - render ASCII table
        # Validate columns
        if not columns:
            if self.Signals:
                self.BasicOutputs.warning(MSG_NO_COLUMNS)
            return

        # Paginate rows
        page_info = self.pagination.paginate(rows, limit=limit, offset=offset)
        paginated_rows = page_info["items"]

        # Check if we have rows to display
        if not paginated_rows:
            if self.Signals:
                self.BasicOutputs.info(MSG_NO_ROWS)
            return

        # Display table header with pagination info
        if title and page_info["total"] > len(paginated_rows):
            # Show pagination range in title
            title_with_range = MSG_SHOWING_RANGE.format(
                title=title,
                start=page_info[KEY_SHOWING_START],
                end=page_info[KEY_SHOWING_END],
                total=page_info["total"]
            )
        else:
            title_with_range = title

        # Render table
        self._render_table_page(title_with_range, columns, paginated_rows, show_header, caption, truncate)

        # Show "more rows" footer if paginated
        if page_info[KEY_HAS_MORE]:
            remaining = page_info["total"] - page_info[KEY_SHOWING_END]
            more_msg = MSG_MORE_ROWS.format(count=remaining)
            if self.Signals:
                self.BasicOutputs.info(more_msg)

        # Interactive navigation loop (Terminal-only)
        if zPages and limit and limit > 0:
            total_rows = len(rows)
            total_pages = (total_rows + limit - 1) // limit  # ceiling division
            current_page = (offset // limit) + 1

            while True:
                command = self.zPrimitives.read_string(NAV_PROMPT).strip().lower()

                if command == "q":
                    break
                elif command == "n":
                    if current_page < total_pages:
                        current_page += 1
                    else:
                        if self.Signals:
                            self.BasicOutputs.warning(NAV_ALREADY_LAST)
                        continue
                elif command == "p":
                    if current_page > 1:
                        current_page -= 1
                    else:
                        if self.Signals:
                            self.BasicOutputs.warning(NAV_ALREADY_FIRST)
                        continue
                elif command == "f":
                    current_page = 1
                elif command == "l":
                    current_page = total_pages
                elif command.isdigit():
                    page_num = int(command)
                    if 1 <= page_num <= total_pages:
                        current_page = page_num
                    else:
                        if self.Signals:
                            self.BasicOutputs.warning(
                                NAV_INVALID_PAGE.format(total_pages=total_pages)
                            )
                        continue
                else:
                    if self.Signals:
                        self.BasicOutputs.warning(NAV_INVALID)
                    continue

                # Re-paginate and re-render
                current_offset = (current_page - 1) * limit
                page_info = self.pagination.paginate(rows, limit=limit, offset=current_offset)
                paginated_rows = page_info["items"]

                title_with_range = MSG_SHOWING_RANGE.format(
                    title=title,
                    start=page_info[KEY_SHOWING_START],
                    end=page_info[KEY_SHOWING_END],
                    total=page_info["total"]
                ) if title else None
                self._render_table_page(title_with_range, columns, paginated_rows, show_header, caption, truncate)

                if page_info[KEY_HAS_MORE]:
                    remaining = page_info["total"] - page_info[KEY_SHOWING_END]
                    if self.Signals:
                        self.BasicOutputs.info(MSG_MORE_ROWS.format(count=remaining))

    def _render_table_page(
        self,
        title: str,
        columns: List[str],
        rows: List[Union[Dict[str, Any], List[Any]]],
        show_header: bool,
        caption: Optional[str] = None,
        truncate: Union[bool, int] = DEFAULT_TRUNCATE,
    ) -> None:
        """Render a single page of table data in zCLI mode."""
        # Compute per-column widths and truncation mode.
        # NOTE: bool is a subclass of int in Python — must check bool first so
        # truncate=False (the default) never enters the integer branch.
        if isinstance(truncate, bool) or truncate is None:
            # Content-fit mode: expand each column to its widest value (no clipping).
            # Width is measured on the RENDERED cell (markdown markers gone, ANSI stripped)
            # so a cell like **zTable** sizes to its visible 6 chars, not the raw 10.
            all_raw = [self._extract_raw_values(row, columns) for row in rows]
            col_widths = [
                max(
                    len(col),
                    max((self._visible_width(raw[i]) for raw in all_raw if i < len(raw)), default=0)
                )
                for i, col in enumerate(columns)
            ]
            do_truncate = False
        else:
            # Fixed-width mode: all columns at the specified char count
            col_widths = [int(truncate)] * len(columns)
            do_truncate = True

        # Table header (skipped when no title is provided — title is optional)
        if title and self.BasicOutputs:
            self.BasicOutputs.header(title, color=DEFAULT_HEADER_COLOR, style=DEFAULT_TABLE_STYLE)

        # Caption (if provided) - display after title, styled as muted text
        if caption and self.BasicOutputs:
            self.BasicOutputs.text(caption, color="MUTE", indent=0)

        # Column headers
        if show_header:
            header_cells = [
                col[:col_widths[i]].ljust(col_widths[i])
                for i, col in enumerate(columns)
            ]
            header_row = _CHAR_SPACE.join(header_cells)
            self._output_text(header_row, break_after=False)

            # Separator matches actual header width
            separator = CHAR_SEPARATOR * len(header_row)
            self._output_text(separator, break_after=False)

        # Data rows with ^^ merge support
        previous_row_values = None
        for row in rows:
            formatted_row = self._format_row(row, columns, previous_row_values, col_widths, do_truncate)
            self._output_text(formatted_row, break_after=False)
            # Carry forward the RESOLVED values (^^ replaced with the merged value) so a
            # ^^ two rows down copies the real value, not another ^^.
            previous_row_values = self._resolve_row_values(row, columns, previous_row_values)

    def _parse_inline_markdown(self, text: str) -> str:
        """Render a table cell's inline markdown via the zMD SSOT.

        A cell is a zMD *inline* context, so it delegates to MarkdownParser.parse_inline
        — the same engine rich_text/zMD uses — instead of re-implementing bold/italic/
        code/link/HTML here. Cells therefore inherit the FULL inline vocabulary
        (==highlight==, ~~strike~~, __bold__/_italic_, colour-restoring `code`, HTML
        class→ANSI) and stay in lockstep with zMD (DRY/SSOT). Previously this method
        forked a partial copy that silently dropped highlight/strike/underline.

        Links are INERT by construction: parse_inline runs WITHOUT a link_sink, so a
        cell never fires an interactive y/n prompt — exactly the reference-only
        behaviour a dense grid needs. Emojis run through the shared safe-emoji util
        first (terminal a11y), matching every other zCLI output event.

        Args:
            text: Cell value with potential markdown / HTML / emoji

        Returns:
            str: ANSI-formatted inline text (markers resolved, emojis described)
        """
        if not text or not isinstance(text, str):
            return text

        # Lazily build the shared engines once (avoids import cycles at construction).
        if self._md_parser is None:
            from .markdown.markdown_parser import MarkdownParser
            from ..basic.outputs.content_transformers import ContentTransformers
            self._md_parser = MarkdownParser()
            self._content_transformers = ContentTransformers(self.display)

        # Strip outer quotes left by YAML string parsing (table-local input cleaning).
        text = text.strip('"').strip("'")
        # Safe-emoji util (SSOT) — emoji → [description] for terminal accessibility.
        text = self._content_transformers.convert_emojis_for_terminal(text)
        # zMD inline SSOT — no link_sink ⇒ inert, reference-only links.
        return self._md_parser.parse_inline(text)

    def _visible_width(self, raw: str) -> int:
        """Display width of a cell after markdown render — markers gone, ANSI stripped.

        Used for content-fit column sizing so markup never inflates the math.
        """
        return len(_ANSI_RE.sub("", self._parse_inline_markdown(raw)))

    def _extract_raw_values(
        self,
        row: Union[Dict[str, Any], List[Any]],
        columns: List[str]
    ) -> List[str]:
        """Extract raw string values from a row before formatting."""
        values = []

        if isinstance(row, dict):
            for col in columns:
                value = row.get(col, "")
                # Cell descriptor: {val: ..., _zClass: '...'} — extract val only for terminal
                if isinstance(value, dict) and 'val' in value:
                    value = value['val']
                value_str = str(value) if value is not None else ""
                values.append(value_str)
        elif isinstance(row, list):
            values = [str(v) if v is not None else "" for v in row]
        else:
            values = [str(row)]

        return values

    def _resolve_row_values(
        self,
        row: Union[Dict[str, Any], List[Any]],
        columns: List[str],
        previous_row_values: Optional[List[str]] = None,
    ) -> List[str]:
        """Extract a row's raw string values, resolving ^^ against the row above.

        A ^^ cell becomes the value it merges with — this is the carry-forward truth,
        so the next ^^ in the same column copies the real value, never another ^^.
        """
        resolved: List[str] = []

        if isinstance(row, dict):
            for col_idx, col in enumerate(columns):
                value = row.get(col, "") or ""
                # Cell descriptor: {val: ..., _zClass: '...'} — extract val only for terminal
                if isinstance(value, dict) and 'val' in value:
                    value = value['val']
                value_str = str(value)
                if value_str == "^^" and previous_row_values and col_idx < len(previous_row_values):
                    value_str = previous_row_values[col_idx]
                resolved.append(value_str)
        elif isinstance(row, list):
            for col_idx, v in enumerate(row):
                value_str = str(v) if v is not None else ""
                if value_str == "^^" and previous_row_values and col_idx < len(previous_row_values):
                    value_str = previous_row_values[col_idx]
                resolved.append(value_str)
        else:
            resolved = [str(row)]

        return resolved

    def _format_row(
        self,
        row: Union[Dict[str, Any], List[Any]],
        columns: List[str],
        previous_row_values: Optional[List[str]] = None,
        col_widths: Optional[List[int]] = None,
        do_truncate: bool = False,
    ) -> str:
        """Format a single row for terminal display with markdown support and ^^ merge logic.

        Uses raw string lengths for width/padding calculations so ANSI escape codes
        (added by _parse_inline_markdown) never inflate visible-width accounting.
        """
        # Step 1: Resolve raw values (shared helper handles ^^ merge against prev row)
        raw_values = self._resolve_row_values(row, columns, previous_row_values)

        # Ensure widths list covers all columns (fallback to DEFAULT_COL_WIDTH)
        widths = col_widths if col_widths else [DEFAULT_COL_WIDTH] * len(raw_values)

        # Step 2: Format each cell — truncate raw OR parse markdown + pad by raw length
        formatted_values = []
        for i, raw_str in enumerate(raw_values):
            width = widths[i] if i < len(widths) else DEFAULT_COL_WIDTH
            if do_truncate and len(raw_str) > width:
                # Clip the raw string — no point applying markdown to a truncated cell
                formatted_values.append(
                    raw_str[:width - len(DEFAULT_TRUNCATE_SUFFIX)] + DEFAULT_TRUNCATE_SUFFIX
                )
            else:
                # Apply inline markdown, then pad by the cell's VISIBLE width (markers
                # removed, ANSI stripped) so columns line up regardless of markup.
                parsed = self._parse_inline_markdown(raw_str)
                visible_len = len(_ANSI_RE.sub("", parsed))
                padding = max(0, width - visible_len)
                formatted_values.append(parsed + _CHAR_SPACE * padding)

        return _CHAR_SPACE.join(formatted_values)

    def _output_text(self, content: str, indent: int = 0, break_after: bool = False) -> None:
        """Output text using BasicOutputs or zPrimitives fallback."""
        if self.BasicOutputs:
            # _compact=True suppresses the paragraph-spacing \n that text_renderer
            # emits after every BasicOutputs.text() call in zCLI mode.
            # Table rows are dense data — no paragraph gap between them.
            self.BasicOutputs.text(content, indent=indent, break_after=break_after, _compact=True)
        elif self.zPrimitives:
            self.zPrimitives.line(content)
