# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/b_primitives/inputs/input_string.py

"""
String Input Primitive - Text input with dual-mode support.

Handles text input collection in both terminal (synchronous) and
Bifrost (buffered event) modes with support for various input types.
"""

import re as _re
from datetime import datetime as _dt

from zOS import Any, Union, time, TYPE_CHECKING
from ...display_constants import (
    _DEFAULT_PROMPT,
    _EVENT_READ_STRING,
    _KEY_EVENT,
    _KEY_REQUEST_ID,
    _KEY_PROMPT,
    _KEY_TIMESTAMP,
)

# Format + constraint validation is owned by field_rules (the cross-surface
# SSOT). Type presets (email/number/url/color/tel) and raw constraints
# (min/max/step/pattern/minlength/maxlength) both resolve through there, so the
# zCLI prompt and the Bifrost form enforce the same rules.
from .field_rules import resolve as _resolve_constraints, validate_value as _validate_value

# Post-validation normalizers — keyed by input type.
# Each entry: (normalize_fn: str -> str)
# Applied after validation passes in _terminal_single_line.
_TYPE_NORMALIZERS: dict = {
    'color': str.lower,
}

# Temporal input types — routed to _terminal_temporal_input instead of _terminal_single_line.
_TEMPORAL_TYPES = {'date', 'time', 'datetime-local', 'week', 'month'}

# zMachine date_format token → (strptime_no_sep, display_hint)
# Separators are stripped from user input before parsing (/, -, ., space).
# Output is always normalized to ISO 8601 YYYY-MM-DD.
_DATE_FORMAT_MAP: dict = {
    'ddmmyyyy': ('%d%m%Y', 'DD/MM/YYYY'),
    'mmddyyyy': ('%m%d%Y', 'MM/DD/YYYY'),
    'yyyymmdd': ('%Y%m%d', 'YYYY-MM-DD'),
    'ddmmyy':   ('%d%m%y', 'DD/MM/YY'),
    'mmddyy':   ('%m%d%y', 'MM/DD/YY'),
    'iso':      ('%Y%m%d', 'YYYY-MM-DD'),
}

# zMachine time_format token → (strptime_fmt, display_hint)
# Output is always normalized to HH:MM:SS (seconds default to 00 if not provided).
_TIME_FORMAT_MAP: dict = {
    'HH:MM:SS': ('%H:%M:%S', 'HH:MM:SS'),
    'HH:MM':    ('%H:%M',    'HH:MM'),
    'HHMMSS':   ('%H%M%S',   'HHMMSS'),
    'HHMM':     ('%H%M',     'HHMM'),
    '12h':      ('%I:%M %p', 'HH:MM AM/PM'),
    '12hss':    ('%I:%M:%S %p', 'HH:MM:SS AM/PM'),
}

# Wildcard MIME families → representative extension set, for `accept: image/*`
# style values. SSOT for the terminal side of the cross-surface `accept` contract
# (the browser parses MIME natively; the terminal needs concrete extensions).
_MIME_WILDCARD_EXTS: dict = {
    "image": {"png", "jpg", "jpeg", "gif", "webp", "svg", "avif", "bmp", "ico"},
    "video": {"mp4", "webm", "mov", "ogv", "m4v", "avi", "mkv"},
    "audio": {"mp3", "wav", "ogg", "m4a", "flac", "aac", "opus"},
}


def accept_to_exts(accept: Any) -> "set":
    """Normalize an `accept` value to a bare lower-case extension set.

    Accepts the HTML `accept` flavours, comma-separated:
      ".png" / "png"        → {"png"}
      "image/png"           → {"png"}
      "image/*"             → the image family set
      "*/*" / unknown "x/*" → no constraint (returns empty → caller treats as None)

    Returns a set of extensions (no dot, lower-case). Empty set means "no
    enforceable constraint" so callers must NOT reject on it (avoids false
    negatives from un-enumerable wildcards).
    """
    if not accept:
        return set()
    exts: set = set()
    for token in str(accept).split(","):
        t = token.strip().lower()
        if not t:
            continue
        if t.startswith("."):
            exts.add(t[1:])
        elif "/" in t:
            typ, _, sub = t.partition("/")
            if sub and sub != "*":
                exts.add(sub)               # image/png → png, application/pdf → pdf
            else:
                exts |= _MIME_WILDCARD_EXTS.get(typ, set())  # image/* → family; */* → none
        else:
            exts.add(t)                     # bare "png"
    return exts


if TYPE_CHECKING:
    import asyncio


class StringInput:
    """String input primitive - read text input with dual-mode support."""

    display: Any
    _is_bifrost: bool

    def __init__(self, display_instance: Any, is_bifrost: bool) -> None:
        """Initialize with parent display instance and mode flag.
        
        Args:
            display_instance: Parent zDisplay instance
            is_bifrost: Pre-computed mode flag (True if Bifrost mode)
        """
        self.display = display_instance
        self._is_bifrost = is_bifrost

    def read_string(self, prompt: str = _DEFAULT_PROMPT, label: str = "", **kwargs) -> Union[str, 'asyncio.Future']:
        """Read string input - terminal (synchronous) or GUI (buffered event).
        
        Critical dual-mode method with different return types based on mode:
            - Terminal mode: Returns str directly (synchronous)
            - Bifrost mode: Buffers display_prompt_request event, returns empty string (non-blocking)
        
        Args:
            prompt: Prompt text to display (default: empty string)
            **kwargs: Additional parameters:
                - type: Input type (text, email, number, tel, url, textarea, file)
                - placeholder: Placeholder text
                - required: Whether input is required
                - default: Default value
                - prefix: Text prefix (e.g., '$', 'https://')
                - suffix: Text suffix (e.g., '@company.com', '.com')
                - disabled: Display only (no interaction)
                - readonly: Display value, no editing
                - datalist: List of suggestions
                - multiple: Multiple file selection (for type='file')
        
        Returns:
            Union[str, asyncio.Future]: 
                - str if in terminal mode (actual user input with prefix/suffix concatenated)
                - str if in Bifrost mode (empty string, actual input handled by frontend)
        
        Notes:
            - Bifrost: Buffers display_prompt_request event for frontend rendering
            - Terminal: Synchronous input() with prefix/suffix shown in prompt
            - Prefix/suffix are concatenated with user input: prefix + input + suffix
            - Always has terminal fallback if GUI request fails
            - Strips whitespace from Terminal input
        
        Example:
            # Basic input
            result = primitives.read_string("Enter name:", type="text")
            # Terminal: "Enter name: " → Returns "John"
            # Bifrost: Returns "" (input rendered on frontend)
            
            # Input with prefix/suffix (input groups)
            result = primitives.read_string("Email:", suffix="@company.com")
            # Terminal: "Email [...@company.com]: " → User types "sarah" → Returns "sarah@company.com"
            # Bifrost: Returns "" (rendered as <span>@company.com</span><input>)
        """
        if label:
            prompt = label
        self._enrich_temporal_placeholder(kwargs)
        if self._is_bifrost:
            return self._bifrost_input(prompt, **kwargs)
        return self._terminal_input(prompt, **kwargs)

    def _terminal_input(self, prompt: str, **kwargs) -> str:
        """Handle terminal input with various input types.
        
        Args:
            prompt: Prompt text
            **kwargs: Input parameters
            
        Returns:
            str: User input from terminal
        """
        input_type = kwargs.get('type', 'text')
        disabled = kwargs.get('disabled', False)
        readonly = kwargs.get('readonly', False)
        placeholder = kwargs.get('placeholder', '')
        default_value = kwargs.get('default', '')

        # Handle disabled inputs (display only, no interaction)
        if disabled:
            display_value = default_value or placeholder
            if prompt:
                print(f"{prompt} [disabled]: {display_value}")
            else:
                print(f"[disabled] {display_value}")
            return display_value

        # Handle readonly inputs (display value, no editing)
        if readonly:
            if prompt:
                print(f"{prompt} [readonly]: {default_value}")
            else:
                print(f"[readonly] {default_value}")
            return default_value

        # Password input — delegate to PasswordInput primitive (masked getpass)
        if input_type == 'password':
            pw_placeholder = '•' * 8 if placeholder else ''
            pw_prompt = self.build_prompt(prompt, placeholder=pw_placeholder)
            return self.display.zPrimitives.read_password(pw_prompt)

        # Multi-line textarea input (Ctrl+D to finish)
        if input_type == 'textarea':
            return self._terminal_textarea(prompt, **kwargs)

        # File input (terminal mode: enter file path with validation)
        if input_type == 'file':
            return self._terminal_file_input(prompt, **kwargs)

        # Temporal inputs (date / time / datetime-local / week / month)
        if input_type in _TEMPORAL_TYPES:
            return self._terminal_temporal_input(prompt, **kwargs)

        # Datalist input (terminal mode: show numbered options, allow free text)
        datalist_options = kwargs.get('datalist', None)
        if datalist_options and isinstance(datalist_options, list):
            return self._terminal_datalist(prompt, datalist_options, **kwargs)

        # Single-line input (all other types)
        return self._terminal_single_line(prompt, **kwargs)

    def _terminal_textarea(self, prompt: str, **kwargs) -> str:
        """Handle multi-line textarea input.

        Two surfaces, one IO seam:
        - Real zCLI (TTY *or* piped stdin, e.g. heredoc tests): loop ``input()``
          until EOF (Ctrl+D) for true multi-line capture.
        - zTerminal sandbox: bare ``input()`` is NOT bridged (only ``_read_raw``
          is), and the sandbox swaps ``sys.stdin`` for an empty EOF stub — so a
          bare loop returns '' instantly with no prompt (the observed
          misalignment). The bridge patches ``_read_raw`` as an *instance* attr,
          so its presence in ``__dict__`` reliably signals the sandbox without
          touching zGuard. There, issue ONE bridged read (``type=textarea``) so
          the browser renders a textarea and the whole value returns in one shot.
        """
        # Length constraints apply to multi-line text too (minlength/maxlength).
        # Pattern/min/max/step are single-line semantics, so we enforce ONLY the
        # length subset here — parity with the browser <textarea>, which honours
        # minlength/maxlength but not pattern. field_rules stays the SSOT.
        resolved = _resolve_constraints(kwargs)
        length_constraints = {k: resolved[k] for k in ('minlength', 'maxlength') if k in resolved}

        def _collect() -> str:
            # Sandbox bridge active → single bridged read (no Ctrl+D in the browser).
            if '_read_raw' in self.__dict__:
                meta = {k: v for k, v in kwargs.items() if k != 'type'}
                return self._read_raw(prompt, type='textarea', **meta)
            if prompt:
                print(prompt)
                print("  (Press Ctrl+D on empty line to finish)")
            lines = []
            try:
                while True:
                    lines.append(input())
            except EOFError:
                pass
            return '\n'.join(lines)

        while True:
            value = _collect()
            ok, error_msg = _validate_value(value, length_constraints)
            if not ok:
                self.display.error(error_msg)
                continue
            return value

    def _terminal_file_input(self, prompt: str, **kwargs):
        """Handle file input with path validation."""
        import os
        multiple = kwargs.get('multiple', False)
        # Cross-surface `accept` contract (SSOT): the same value that filters the
        # browser picker drives terminal disambiguation + type validation. Empty
        # set = no enforceable constraint (don't reject).
        allowed_exts = accept_to_exts(kwargs.get('accept')) or None

        def resolve_and_validate_path(path_str: str) -> tuple:
            """Resolve and validate a file path.

            zInput file is one of the extension-aware zPath events (alongside
            zImage / zVideo / zAudio src). It uses the SSOT resolver
            ``zparser.resolve_zfile``:
            the zPath stays plain dotted (NO new grammar) and the extension is
            OPTIONAL — omitted, the single file with that stem in the directory is
            auto-detected; included, ``stem.ext`` is used to disambiguate
            same-stem siblings. When `accept` is set, its extensions both narrow
            that auto-detect (resolve_zfile) and gate the final type below.

            Dotted zPaths (``@.…`` / ``~.…``) resolve via the SSOT. A literal OS
            path the user types (absolute, ``~/…`` home, ``./rel``) is honoured
            verbatim via expanduser.
            """
            try:
                p = path_str.strip()

                if p.startswith(('@.', '~.')):
                    if hasattr(self.display, 'zos') and hasattr(self.display.zos, 'zparser'):
                        resolved_path = self.display.zos.zparser.resolve_zfile(p, allowed_exts)
                    else:
                        return None, False, "zParser not available"
                else:
                    # Literal native OS path (absolute / ~/home / ./relative).
                    resolved_path = os.path.expanduser(p)

                if not os.path.exists(resolved_path):
                    return resolved_path, False, f"File does not exist: {path_str}"

                # Type gate — the resolved file's extension must be in `accept`.
                if allowed_exts:
                    ext = os.path.splitext(resolved_path)[1].lstrip('.').lower()
                    if ext not in allowed_exts:
                        return resolved_path, False, (
                            f"File type .{ext} not allowed — expected: "
                            f"{', '.join(sorted(allowed_exts))}"
                        )

                return resolved_path, True, None
            except Exception as e:
                return None, False, f"Path resolution error: {str(e)}"

        def _validate_paths(path_list: list) -> tuple:
            """Validate a list of path strings. Returns (valid_resolved, invalid_pairs)."""
            valid, invalid = [], []
            for path in path_list:
                resolved, is_valid, error_msg = resolve_and_validate_path(path)
                if is_valid:
                    valid.append(resolved)
                else:
                    invalid.append((path, error_msg))
            return valid, invalid

        while True:
            if prompt:
                file_prompt = prompt if prompt.endswith(' ') else prompt + ' '
                print(file_prompt.strip())
                if multiple:
                    print("  (Enter file paths, comma-separated for multiple files)")
                    print("  (zPath: @.folder.file  (ext optional)  |  native: ~/path/file.txt)")
                else:
                    print("  (zPath: @.folder.file  (ext optional)  |  native: ~/path/file.txt)")

            user_input = input("  Path: " if prompt else "").strip()

            if not user_input:
                print("  ❌ Error: File path cannot be empty. Please try again.")
                continue

            # Handle multiple files (comma-separated)
            if multiple:
                paths = [p.strip() for p in user_input.split(',') if p.strip()]
                if not paths:
                    print("  ❌ Error: No valid paths entered. Please try again.")
                    continue

                valid_paths, invalid_paths = _validate_paths(paths)

                # All invalid → full retry, no partial state to keep
                if not valid_paths:
                    print("  ❌ All paths are invalid:")
                    for path, error_msg in invalid_paths:
                        print(f"     - {path}: {error_msg}")
                    print("  Please re-enter all paths.")
                    continue

                # Mixed → show results and offer partial-proceed
                if invalid_paths:
                    print()
                    for resolved in valid_paths:
                        print(f"  ✅ {resolved}")
                    for path, error_msg in invalid_paths:
                        print(f"  ❌ {path} — {error_msg}")
                    print()
                    fix_choice = input("  Fix invalid paths? [y/n]: ").strip().lower()
                    if fix_choice == 'n':
                        print(f"  [ok] Proceeding with {len(valid_paths)} valid file(s).")
                        return valid_paths
                    # y or anything else → re-collect only the invalid ones
                    print(f"  Re-enter {len(invalid_paths)} invalid path(s), comma-separated:")
                    while True:
                        retry_input = input("  Path: ").strip()
                        retry_paths = [p.strip() for p in retry_input.split(',') if p.strip()]
                        if not retry_paths:
                            print("  ❌ No paths entered. Try again.")
                            continue
                        retry_valid, retry_invalid = _validate_paths(retry_paths)
                        if retry_invalid:
                            print("  ❌ Still invalid:")
                            for path, error_msg in retry_invalid:
                                print(f"     - {path}: {error_msg}")
                            fix_again = input("  Fix again? [y/n]: ").strip().lower()
                            if fix_again == 'n':
                                valid_paths.extend(retry_valid)
                                print(f"  [ok] Proceeding with {len(valid_paths)} valid file(s).")
                                return valid_paths
                            continue
                        valid_paths.extend(retry_valid)
                        print(f"  [ok] {len(valid_paths)} file(s) selected.")
                        return valid_paths

                # All valid
                print(f"  [ok] {len(valid_paths)} file(s) selected.")
                return valid_paths
            else:
                # Single file
                resolved, is_valid, error_msg = resolve_and_validate_path(user_input)
                if is_valid:
                    print(f"  [ok] Valid: {resolved}")
                    return resolved
                else:
                    print(f"  ❌ Error: {error_msg}")
                    print("  Please try again.")
                    continue

    def _get_machine_format(self, config_key: str, fallback: str) -> str:
        """Read a format token from zMachine config, falling back to provided default."""
        try:
            zos = getattr(self.display, 'zos', None)
            if zos and hasattr(zos, 'config') and hasattr(zos.config, 'machine'):
                return zos.config.machine.get(config_key, fallback)
        except Exception:
            pass
        return fallback

    @staticmethod
    def _strip_date_seps(value: str) -> str:
        """Remove common date separators for format-agnostic strptime parsing."""
        return value.replace('/', '').replace('-', '').replace('.', '').replace(' ', '')

    # ------------------------------------------------------------------
    # Parse primitives — SSOT for date/time/datetime-local parsing.
    # Each returns an ISO string on success or None on invalid input.
    # Used by terminal loops, _normalize_temporal_output, and the
    # zTerminal sandbox validation path.
    # ------------------------------------------------------------------

    def _parse_date_value(self, raw: str, format_token: str) -> str:
        """Parse a raw date string → 'YYYY-MM-DD', or None if invalid.

        Tries the configured format first (after stripping separators), then
        falls back to ISO 8601 (YYYY-MM-DD) — which is what browser date
        pickers always return via zTerminal input responses.
        """
        fmt_entry = _DATE_FORMAT_MAP.get(format_token) or _DATE_FORMAT_MAP['ddmmyyyy']
        strptime_fmt, _ = fmt_entry
        clean = self._strip_date_seps(raw)
        try:
            return _dt.strptime(clean, strptime_fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
        # ISO 8601 fallback — browser <input type="date"> always returns YYYY-MM-DD.
        if strptime_fmt != '%Y-%m-%d':
            try:
                return _dt.strptime(raw.strip(), '%Y-%m-%d').strftime('%Y-%m-%d')
            except ValueError:
                pass
        return None

    def _parse_time_value(self, raw: str) -> str:
        """Parse a raw time string → 'HH:MM:SS', or None if invalid.

        Accepts 24h (HH:MM, HH:MM:SS) and 12h (H:MM AM/PM, H:MM:SS AM/PM).
        Seconds default to :00 when not provided.
        """
        for fmt in ('%H:%M:%S', '%H:%M', '%I:%M:%S %p', '%I:%M %p'):
            try:
                return _dt.strptime(raw, fmt).strftime('%H:%M:%S')
            except ValueError:
                continue
        return None

    def _parse_datetime_local_value(self, raw: str, date_token: str) -> str:
        """Parse a raw datetime-local string → 'YYYY-MM-DDTHH:MM:SS', or None if invalid.

        Composes _parse_date_value + _parse_time_value. Accepts:
          - ISO browser format:  YYYY-MM-DDTHH:MM  /  YYYY-MM-DDTHH:MM:SS
          - Localized format:    DD/MM/YYYY HH:MM  /  DD/MM/YYYY 2:30 PM
          - T or space as separator between date and time parts.
        """
        if not raw:
            return None
        # ISO path first (browser native datetime-local value)
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M'):
            try:
                return _dt.strptime(raw, fmt).strftime('%Y-%m-%dT%H:%M:%S')
            except ValueError:
                continue
        # Localized path: split on T or first space (preserves "2:30 PM" as one token)
        parts = raw.replace('T', ' ').split(' ', 1)
        if len(parts) != 2:
            return None
        date_str = self._parse_date_value(parts[0].strip(), date_token)
        time_str = self._parse_time_value(parts[1].strip())
        if date_str and time_str:
            return f"{date_str}T{time_str}"
        return None

    def _parse_temporal(self, input_type: str, raw: str, **kwargs) -> str:
        """Dispatch raw input to the right parse primitive.

        Returns the ISO-normalized string on success, or None if invalid.
        Used by both terminal loops and the zTerminal sandbox validation path.
        """
        if input_type == 'date':
            token = kwargs.get('format') or self._get_machine_format('date_format', 'ddmmyyyy')
            return self._parse_date_value(raw, token)
        if input_type == 'time':
            return self._parse_time_value(raw)
        if input_type == 'datetime-local':
            token = kwargs.get('format') or self._get_machine_format('date_format', 'ddmmyyyy')
            return self._parse_datetime_local_value(raw, token)
        if input_type == 'week':
            return self._parse_week_value(raw)
        if input_type == 'month':
            return self._parse_month_value(raw)
        return raw

    # ------------------------------------------------------------------
    # Terminal input loops — use parse primitives, no inline parsing.
    # ------------------------------------------------------------------

    def _terminal_temporal_input(self, prompt: str, **kwargs) -> str:
        """Handle temporal inputs: date / time / datetime-local / week / month.

        Priority for format resolution:
          1. `format` kwarg on the zInput field (per-field override)
          2. zMachine.date_format / time_format (machine SSOT)
          3. Hard-coded fallback ('ddmmyyyy' / 'HH:MM:SS')

        Output is always ISO 8601:
          date           → YYYY-MM-DD
          time           → HH:MM:SS
          datetime-local → YYYY-MM-DDTHH:MM:SS
          week           → YYYY-WNN
          month          → YYYY-MM
        """
        input_type = kwargs.get('type', 'date')
        default_value = kwargs.get('default', '')

        if input_type == 'week':
            return self._terminal_week_input(prompt, default_value, **kwargs)
        if input_type == 'month':
            return self._terminal_month_input(prompt, default_value, **kwargs)
        if input_type == 'datetime-local':
            return self._terminal_datetime_local_input(prompt, **kwargs)

        if input_type == 'date':
            format_token = kwargs.get('format') or self._get_machine_format('date_format', 'ddmmyyyy')
            _, display_hint = _DATE_FORMAT_MAP.get(format_token) or _DATE_FORMAT_MAP['ddmmyyyy']
            hint_prompt = f"{prompt.rstrip()} [{display_hint}]: " if prompt else f"[{display_hint}]: "
            while True:
                user_input = self._read_raw(hint_prompt, **kwargs).strip()
                if not user_input and default_value:
                    return default_value
                if not user_input:
                    self.display.error(f"Date is required — enter a date in {display_hint} format.")
                    continue
                result = self._parse_date_value(user_input, format_token)
                if result is None:
                    self.display.error(f"Invalid date — expected format: {display_hint}")
                    continue
                return result

        if input_type == 'time':
            format_token = kwargs.get('format') or self._get_machine_format('time_format', 'HH:MM:SS')
            _, display_hint = _TIME_FORMAT_MAP.get(format_token) or _TIME_FORMAT_MAP['HH:MM:SS']
            hint_prompt = f"{prompt.rstrip()} [{display_hint}]: " if prompt else f"[{display_hint}]: "
            while True:
                user_input = self._read_raw(hint_prompt, **kwargs).strip()
                if not user_input and default_value:
                    return default_value
                if not user_input:
                    self.display.error(f"Time is required — enter a time in {display_hint} format.")
                    continue
                result = self._parse_time_value(user_input)
                if result is None:
                    self.display.error(f"Invalid time — expected format: {display_hint} (e.g. 14:30)")
                    continue
                return result

        # Fallback (should not reach here for valid temporal types)
        return self._terminal_single_line(prompt, **kwargs)

    def _terminal_datetime_local_input(self, prompt: str, **kwargs) -> str:
        """Handle datetime-local — composes _parse_datetime_local_value for full validation."""
        date_token = kwargs.get('format') or self._get_machine_format('date_format', 'ddmmyyyy')
        _, date_hint = _DATE_FORMAT_MAP.get(date_token) or _DATE_FORMAT_MAP['ddmmyyyy']
        default_value = kwargs.get('default', '')
        hint_prompt = (
            f"{prompt.rstrip()} [{date_hint} HH:MM]: " if prompt
            else f"[{date_hint} HH:MM]: "
        )
        while True:
            user_input = self._read_raw(hint_prompt, **kwargs).strip()
            if not user_input and default_value:
                return default_value
            if not user_input:
                self.display.error(f"Required — enter date and time: {date_hint} HH:MM")
                continue
            result = self._parse_datetime_local_value(user_input, date_token)
            if result is None:
                self.display.error(
                    f"Invalid — enter '{date_hint} HH:MM' or '{date_hint} 2:30 PM' "
                    f"(e.g. 29/04/2026 14:30)"
                )
                continue
            return result

    _WEEK_RE = _re.compile(r'^(\d{4})-?W(\d{1,2})$', _re.IGNORECASE)

    def _parse_week_value(self, raw: str) -> str:
        """Parse and validate a week string.

        Accepts: YYYY-WNN or YYYY-WN (with or without dash, case-insensitive W).
        Returns: YYYY-WNN (zero-padded) on success, or None if invalid.
        """
        if not raw:
            return None
        match = self._WEEK_RE.match(raw.strip())
        if not match:
            return None
        year, week = int(match.group(1)), int(match.group(2))
        if not 1 <= week <= 53:
            return None
        return f'{year}-W{week:02d}'

    def _parse_month_value(self, raw: str) -> str:
        """Parse and validate a month string.

        Accepts: MM/YYYY or YYYY-MM.
        Returns: YYYY-MM on success, or None if invalid.
        """
        if not raw:
            return None
        for fmt in ('%m/%Y', '%Y-%m'):
            try:
                return _dt.strptime(raw.strip(), fmt).strftime('%Y-%m')
            except ValueError:
                continue
        return None

    def _terminal_week_input(self, prompt: str, default_value: str = '', **kwargs) -> str:
        """Handle week input — always ISO format YYYY-WNN (e.g. 2026-W17)."""
        hint_prompt = f"{prompt.rstrip()} [YYYY-WNN]: " if prompt else "[YYYY-WNN]: "

        while True:
            user_input = self._read_raw(hint_prompt, **kwargs).strip()
            if not user_input and default_value:
                return default_value
            if not user_input:
                self.display.error("Week is required — enter a week in YYYY-WNN format (e.g. 2026-W17)")
                continue
            result = self._parse_week_value(user_input)
            if result is None:
                self.display.error("Invalid week — expected YYYY-WNN, week must be 01–53 (e.g. 2026-W17)")
                continue
            return result

    def _terminal_month_input(self, prompt: str, default_value: str = '', **kwargs) -> str:
        """Handle month input — accepts MM/YYYY or YYYY-MM, outputs YYYY-MM."""
        hint_prompt = f"{prompt.rstrip()} [MM/YYYY or YYYY-MM]: " if prompt else "[MM/YYYY or YYYY-MM]: "

        while True:
            user_input = self._read_raw(hint_prompt, **kwargs).strip()
            if not user_input and default_value:
                return default_value
            if not user_input:
                self.display.error("Month is required — enter MM/YYYY or YYYY-MM (e.g. 04/2026 or 2026-04)")
                continue
            result = self._parse_month_value(user_input)
            if result is None:
                self.display.error("Invalid month — enter MM/YYYY or YYYY-MM (e.g. 04/2026 or 2026-04)")
                continue
            return result

    def _terminal_datalist(self, prompt: str, datalist_options: list, **kwargs) -> str:
        """Handle datalist input with numbered suggestion shortcuts.

        Numbers 1–N select a suggestion; anything else is accepted as free text.
        Out-of-range numbers show a warning and re-prompt (they are not free text).
        Required fields retry on empty input.
        """
        required = kwargs.get('required', False)

        while True:
            if prompt:
                print(self.build_prompt(prompt, **kwargs))
            print("  (Enter a number to pick a suggestion, or type free text.)")
            for idx, option in enumerate(datalist_options, 1):
                print(f"  {idx}. {option}")

            user_input = self._read_raw("  ", **kwargs).strip()

            # Empty input
            if not user_input:
                if required:
                    self.display.error("This field is required — enter a value or pick a number.")
                    continue
                return user_input

            # Numeric input — treat as suggestion shortcut
            if user_input.isdigit():
                option_num = int(user_input)
                if 1 <= option_num <= len(datalist_options):
                    return datalist_options[option_num - 1]
                self.display.error(
                    f"Invalid selection — enter a number between 1 and {len(datalist_options)}, or type free text."
                )
                continue

            # Free text
            return user_input

    @staticmethod
    def _format_affix(value) -> str:
            """Format prefix/suffix values, handling numbers intelligently."""
            if not value and value != 0:
                return ''
            if isinstance(value, bool):
                return str(value)
            if isinstance(value, (int, float)):
                if isinstance(value, float) and 0 <= abs(value) < 1:
                    return f"{value:.2f}".lstrip('0') or '0'
                return str(value)
            return str(value)

    def build_prompt(self, prompt: str, **kwargs) -> str:
        """Build the display prompt string for terminal/sandbox rendering.

        Single source of truth for prompt formatting — used by both real zCLI
        (_terminal_single_line) and the zTerminal sandbox in bridge_event_client.
        Applies placeholder hint and prefix/suffix group context.
        """
        prefix = self._format_affix(kwargs.get('prefix'))
        suffix = self._format_affix(kwargs.get('suffix'))
        placeholder = kwargs.get('placeholder', '')
        default_value = self._format_affix(kwargs.get('default', ''))

        # Fallback: use placeholder as prompt when no prompt provided
        if not prompt and placeholder:
            prompt = str(placeholder)

        if not prompt:
            return ''

        # Within affix context: placeholder fills the slot; default fills it if
        # no placeholder; bare '...' only when neither is available.
        if prefix or suffix:
            mid = placeholder or default_value or '...'
            if prefix and suffix:
                return f"{prompt} [{prefix}{mid}{suffix}]: "
            if prefix:
                return f"{prompt} [{prefix}{mid}]: "
            return f"{prompt} [{mid}{suffix}]: "

        # No affixes — default hint takes precedence over placeholder hint
        if default_value:
            return f"{prompt} [{default_value}]: "
        if placeholder:
            return f"{prompt} [{placeholder}]: "
        return prompt if prompt.endswith(' ') else prompt + ' '

    def _read_raw(self, prompt: str, **meta) -> str:
        """Raw IO hook — patched by sandbox to intercept without touching validation."""
        return input(prompt)

    def _terminal_single_line(self, prompt: str, **kwargs) -> str:
        """Handle single-line input with prefix/suffix support."""
        prefix = self._format_affix(kwargs.get('prefix'))
        suffix = self._format_affix(kwargs.get('suffix'))
        default_value = self._format_affix(kwargs.get('default', ''))
        input_type = kwargs.get('type', 'text')

        # Resolve the field's rules ONCE (type preset + any raw constraints).
        constraints = _resolve_constraints(kwargs)
        normalizer = _TYPE_NORMALIZERS.get(input_type)
        terminal_prompt = self.build_prompt(prompt, **kwargs)

        while True:
            user_input = self._read_raw(terminal_prompt, **kwargs).strip() if terminal_prompt else self._read_raw('', **kwargs).strip()

            # Accept default when user hits Enter without typing
            if not user_input and default_value:
                return f"{prefix}{default_value}{suffix}"

            # Format + constraint validation (type-agnostic — raw constraints
            # enforce even when no type is declared).
            if user_input:
                ok, error_msg = _validate_value(user_input, constraints)
                if not ok:
                    self.display.error(error_msg)
                    continue

            if user_input and normalizer:
                user_input = normalizer(user_input)

            return f"{prefix}{user_input}{suffix}"

    def _normalize_temporal_output(self, input_type: str, value: str) -> str:
        """Normalize a temporal value to its canonical ISO form via parse primitives.

        - time           → HH:MM:SS  (via _parse_time_value)
        - datetime-local → YYYY-MM-DDTHH:MM:SS  (via _parse_datetime_local_value;
                           handles both ISO browser values and localized zTerminal input)
        - date, week, month → returned as-is (browser already ISO)
        """
        if not value:
            return value
        if input_type == 'time':
            return self._parse_time_value(value) or value
        if input_type == 'datetime-local':
            date_token = self._get_machine_format('date_format', 'ddmmyyyy')
            return self._parse_datetime_local_value(value, date_token) or value
        return value

    def _enrich_temporal_placeholder(self, kwargs: dict) -> None:
        """Inject format hint into kwargs['placeholder'] for temporal input types.

        Mutates kwargs in-place. Called once in read_string() (normal path) and
        once in the sandbox monkey-patch (zTerminal path) so the logic lives here.
        """
        input_type = kwargs.get('type', 'text')
        if input_type not in _TEMPORAL_TYPES:
            return
        hint = self._temporal_format_hint(input_type, **kwargs)
        if not hint:
            return
        existing = kwargs.get('placeholder', '') or ''
        kwargs['placeholder'] = f"{existing} ({hint})".strip() if existing else hint

    def _temporal_format_hint(self, input_type: str, **kwargs) -> str:
        """Return the display format hint string for a temporal input type.

        Used by both zCLI (prompt suffix) and zBifrost (placeholder injection).
        Priority: `format` kwarg → zMachine config → hard-coded fallback.
        """
        if input_type == 'week':
            return 'YYYY-WNN'
        if input_type == 'month':
            return 'MM/YYYY or YYYY-MM'

        if input_type == 'date':
            token = kwargs.get('format') or self._get_machine_format('date_format', 'ddmmyyyy')
            _, hint = _DATE_FORMAT_MAP.get(token) or _DATE_FORMAT_MAP['ddmmyyyy']
            return hint

        if input_type == 'time':
            token = kwargs.get('format') or self._get_machine_format('time_format', 'HH:MM:SS')
            _, hint = _TIME_FORMAT_MAP.get(token) or _TIME_FORMAT_MAP['HH:MM:SS']
            return hint

        if input_type == 'datetime-local':
            date_token = kwargs.get('format') or self._get_machine_format('date_format', 'ddmmyyyy')
            _, date_hint = _DATE_FORMAT_MAP.get(date_token) or _DATE_FORMAT_MAP['ddmmyyyy']
            return f'{date_hint} HH:MM'

        return ''

    def _bifrost_input(self, prompt: str, **kwargs) -> str:
        """Buffer input request event for Bifrost mode.
        
        Args:
            prompt: Prompt text
            **kwargs: Input parameters
            
        Returns:
            str: Empty string (frontend handles actual input)
        """
        request_id = self.display.zPrimitives._generate_request_id()  # pylint: disable=protected-access
        request_event = {
            _KEY_EVENT: _EVENT_READ_STRING,
            _KEY_REQUEST_ID: request_id,
            _KEY_PROMPT: prompt,
            _KEY_TIMESTAMP: time.time(),
            **kwargs
        }

        # Buffer the input request
        if self.display and hasattr(self.display, 'buffer_event'):
            self.display.buffer_event(request_event)

        return ""
