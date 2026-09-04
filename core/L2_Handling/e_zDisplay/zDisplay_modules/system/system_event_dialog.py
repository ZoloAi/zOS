# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/f_orchestration/system_event_dialog.py

"""
System Dialog Events - zDialog
================================

This module provides form dialog display and input collection with field-by-field
validation support. zDialog orchestrates the complete form workflow from display
to validation to data collection.

Purpose:
    - Display form dialogs with field prompts
    - Collect user input for each field
    - Validate fields against schema (if provided)
    - Retry on validation errors
    - Support both Terminal and Bifrost modes

Public Methods:
    zDialog(context, _zcli, _walker)
        Display form dialog and collect validated input

Private Helpers:
    _log_zdialog_start(context, _zcli)
        Log zDialog start (debug mode only)
        
    _try_zdialog_gui_mode(context, _zcli)
        Try to send zDialog event to Bifrost
        
    _setup_zdialog_validator(context, _zcli)
        Setup schema validator for field-by-field validation
        
    _collect_zdialog_fields(fields, validator, table_name, logger)
        Collect all form fields with validation
        
    (+ 6 more helpers for validation, error display, field parsing)

Dependencies:
    - display_constants: _EVENT_*, _KEY_*, _MSG_*, _FORMAT_*
    - display_event_helpers: try_gui_event
    - display_logging_helpers: get_display_logger
    - display_rendering_utilities: output_text_via_basics
    - zData.DataValidator: Schema validation

Extracted From:
    display_event_system.py (lines 1612-1953)
"""

from zOS import Any, Optional, Dict

# Import Tier 0 infrastructure utilities (none needed - uses primitives/basic directly)

# Import constants
from ..display_constants import (  # pylint: disable=relative-beyond-top-level
    _EVENT_ZDIALOG,
    _KEY_FIELDS,
    _KEY_MODEL,
    _MSG_FORM_INPUT,
    _MSG_FORM_COMPLETE,
    _FORMAT_FIELD_PROMPT
)

# Boolean-attr contract SSOT (zOS#92) — membership + falsy set live here
from ..io.inputs import field_rules  # pylint: disable=relative-beyond-top-level


class DialogEvents:
    """
    Form dialog with field-by-field validation.
    
    Provides zDialog event for displaying forms and collecting validated
    user input in both Terminal and Bifrost modes.
    
    Composition:
        - DeclareEvents: For form header/footer (set after zSystem init)
        - Signals: For error messages (set after zSystem init)
        - zPrimitives: For input collection (from display)
    
    Usage:
        # Via zSystem coordinator
        context = {"fields": ["username", "email", "role"], "model": "@.zSchema.users"}
        data = zos.display.zEvents.zSystem.zDialog(context, _zos=zos)
    """

    # Class-level type declarations
    display: Any                     # Parent zDisplay instance
    zPrimitives: Any                 # Primitives for input collection
    BasicOutputs: Optional[Any]      # BasicOutputs for text rendering
    DeclareEvents: Optional[Any]     # DeclareEvents (for form headers)
    Signals: Optional[Any]           # Signals (for error messages)

    def __init__(self, display_instance: Any) -> None:
        """
        Initialize DialogEvents with reference to parent zDisplay instance.
        
        Args:
            display_instance: Parent zDisplay instance
        
        Returns:
            None
        
        Notes:
            - DeclareEvents and Signals are set to None initially
            - Will be populated by zSystem after all event packages instantiated
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives
        self.BasicOutputs = (
            getattr(display_instance.zEvents, 'BasicOutputs', None)
            if hasattr(display_instance, 'zEvents') else None
        )
        self.DeclareEvents = None  # Will be set after zSystem initialization
        self.Signals = None        # Will be set after zSystem initialization

    def _get_logger(self) -> Optional[Any]:
        """Get logger instance from display hierarchy."""
        if not self.display:
            return None
        if hasattr(self.display, 'zos') and hasattr(self.display.zos, 'logger'):
            return self.display.zos.logger
        if hasattr(self.display, 'logger'):
            return self.display.logger
        return None

    def zDialog(
        self,
        context: Dict[str, Any],
        _zcli: Optional[Any] = None,
        _walker: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Display form dialog and collect validated input (Terminal or Bifrost mode).
        
        ORCHESTRATOR METHOD - Coordinates form display and collection workflow.
        
        Args:
            context: Form context dict containing:
                    - _KEY_FIELDS: List of field names to collect
                    - _KEY_MODEL: Optional schema path for validation
            _zcli: zCLI instance for logging integration
            _walker: zWalker instance for navigation (reserved for future use)
        
        Returns:
            Dict[str, Any]: Collected form data {field_name: value, ...}
                           Empty dict {} if GUI mode (async collection)
        
        Bifrost Mode:
            - Sends _EVENT_ZDIALOG event with form context
            - Frontend displays interactive form UI
            - Returns empty dict (data sent back via WebSocket)
        
        zCLI Mode:
            - Displays form header
            - Collects text input for each field
            - Validates against schema (if provided)
            - Displays form complete footer
            - Returns collected data dict
        
        Usage:
            context = {_KEY_FIELDS: ["username", "email", "role"]}
            data = display.zEvents.zSystem.zDialog(context)
        """
        # 1. Debug logging
        self._log_zdialog_start(context, _zcli)

        # 2. Try Bifrost (GUI) mode first
        if self._try_zdialog_gui_mode(context, _zcli):
            return {}  # GUI event sent successfully

        # 3. zCLI mode - display header
        fields = context.get(_KEY_FIELDS, [])
        if self.DeclareEvents:
            self.DeclareEvents.zDeclare(_MSG_FORM_INPUT, indent=0)

        # 4. Setup schema validation (if available)
        validator, table_name, logger = self._setup_zdialog_validator(context, _zcli)

        # 5. Collect form fields with validation
        zConv = self._collect_zdialog_fields(fields, validator, table_name, logger)

        # 6. Display footer
        if self.DeclareEvents:
            self.DeclareEvents.zDeclare(_MSG_FORM_COMPLETE, indent=0)

        return zConv

    # ZDIALOG HELPER METHODS (Private)

    def _log_zdialog_start(self, context: Dict[str, Any], _zcli: Optional[Any]) -> None:
        """Log zDialog start (debug mode only)."""
        logger = self._get_logger()
        if not logger:
            return

        logger.debug(f"\n{'='*80}")
        logger.debug(f"[zDialog] 📋 ZDIALOG CALLED - Context: {list(context.keys())}")
        logger.debug(f"[zDialog] Fields: {context.get('fields', [])}")
        logger.debug(f"[zDialog] Model: {context.get('model', 'N/A')}")
        logger.debug(f"[zDialog] Has onSubmit: {bool(context.get('onSubmit'))}")
        logger.debug(f"{'='*80}\n")

    def _try_zdialog_gui_mode(self, context: Dict[str, Any], _zcli: Optional[Any]) -> bool:
        """Try to send zDialog event to Bifrost (GUI) mode. Returns True if GUI mode active.

        Field rules are resolved to native HTML attrs downstream at the single
        GUI chokepoint (display_primitives.send_gui_event), so every zDialog
        emission — interactive here or inline page streaming — stays SSOT.
        """
        gui_sent = self.display.zPrimitives.try_gui_event(_EVENT_ZDIALOG, context)

        logger = self._get_logger()
        if logger:
            logger.debug(f"[zDialog] GUI event sent: {gui_sent}")

        return gui_sent

    def _setup_zdialog_validator(
        self,
        context: Dict[str, Any],
        _zcli: Optional[Any]
    ) -> tuple:
        """
        Setup schema validator for field-by-field validation.
        
        Returns:
            tuple: (validator, table_name, logger) or (None, None, logger) if validation disabled
        """
        model = context.get(_KEY_MODEL)
        logger = self._get_logger()

        if logger:
            logger.debug(f"[zDialog] Field-by-field validation setup - model: {model}")

        # Check if validation is possible
        if not (model and isinstance(model, str) and model.startswith('@') and _zcli):
            self._log_validation_disabled_reason(model, _zcli, logger)
            return None, None, logger

        # Try to load schema and create validator
        try:
            validator, table_name = self._load_zdialog_schema_validator(model, _zcli, logger)
            if validator and table_name:
                return validator, table_name, logger
            else:
                self._display_schema_error(f"Schema not found: {model}", logger)
                return None, None, logger
        except Exception as e:
            self._display_schema_error(f"Failed to load schema: {e}", logger)
            return None, None, logger

    def _log_validation_disabled_reason(
        self,
        model: Optional[str],
        _zcli: Optional[Any],
        logger: Optional[Any]
    ) -> None:
        """Log why validation is disabled."""
        if not logger:
            return

        if not model:
            logger.debug("[zDialog] No model specified - validation disabled")
        elif not model.startswith('@'):
            logger.debug(f"[zDialog] Model doesn't start with '@' - validation disabled: {model}")
        elif not _zcli:
            logger.debug("[zDialog] No zcli instance - validation disabled")

    def _load_zdialog_schema_validator(
        self,
        model: str,
        _zcli: Any,
        logger: Optional[Any]
    ) -> tuple:
        """
        Load schema and create validator.
        
        Returns:
            tuple: (validator, table_name) or (None, None) if schema not found
        """
        if logger:
            logger.debug(f"[zDialog] Loading schema from: {model}")

        # Load schema for validation — mirror zDialog.handle() by splitting
        # the model path into (file_path, block_name) before calling loader.
        from zOS.L3_Abstraction.m_zData.zData_modules.shared.validator import DataValidator
        from zOS.L3_Abstraction.m_zData.zData_modules.schema_manager import parse_schema_model_path
        schema_file_path, path_block = parse_schema_model_path(model)
        load_path = schema_file_path or model
        schema_dict = _zcli.loader.handle(load_path) if hasattr(_zcli, 'loader') else None

        if logger:
            logger.debug(f"[zDialog] Schema loaded: {bool(schema_dict)}")

        if not schema_dict:
            return None, None

        # Extract table name: explicit block from path, or last segment of original model
        table_name = path_block or model.split('.')[-1]
        if logger:
            logger.debug(f"[zDialog] Table name extracted: {table_name}")
            logger.debug(f"[zDialog] Schema fields: {list(schema_dict.get(table_name, {}).keys())}")

        # Create validator
        validator_logger = logger or (_zcli.logger if hasattr(_zcli, 'logger') else None)
        if validator_logger:
            validator = DataValidator(schema_dict, validator_logger)
            if logger:
                logger.info(f"[zDialog] ✅ Field-by-field validation ENABLED for table: {table_name}")
            return validator, table_name

        return None, None

    def _display_schema_error(self, error_msg: str, logger: Optional[Any]) -> None:
        """Display schema loading error to user."""
        if logger:
            logger.error(f"[zDialog] {error_msg}")
        if self.Signals:
            self.BasicOutputs.error(f"[ERROR] {error_msg}", indent=0)
            self.BasicOutputs.text("", indent=0, break_after=False)
            self.BasicOutputs.error("Form cannot proceed without schema validation.", indent=1)

    def _collect_zdialog_fields(
        self,
        fields: list,
        validator: Optional[Any],
        table_name: Optional[str],
        logger: Optional[Any]
    ) -> Dict[str, Any]:
        """
        Collect all form fields with validation.
        
        Returns:
            Dict[str, Any]: Collected field data {field_name: value, ...}
        """
        zConv = {}

        for field in fields:
            # Add newline before each field (except first)
            # BasicOutputs may be None if DialogEvents was constructed before
            # zEvents.BasicOutputs was wired (early-init path); skip the spacer.
            if zConv and self.BasicOutputs:
                self.BasicOutputs.text("", indent=0, break_after=False)

            # Parse field metadata
            field_name, field_type, field_label = self._parse_zdialog_field(field)

            # Route enum/select fields to numbered pick-list collector.
            # `multi: true` → multi-pick (comma-separated) returning a LIST, parity
            # with the browser's checkbox-group multi-select.
            if field_type == 'select':
                options = field.get('options', []) if isinstance(field, dict) else []
                default = field.get('default') if isinstance(field, dict) else None
                if isinstance(field, dict) and self._is_truthy_flag(field.get('multi')):
                    value = self._collect_multiselect_field(field_name, field_label, options, default, logger)
                else:
                    value = self._collect_select_field(field_name, field_label, options, default, logger)
                zConv[field_name] = value
                continue

            # Route boolean fields (radio + checkbox) to the numbered true/false[/null]
            # pick-list. A single checkbox is semantically a boolean toggle, so in
            # zCLI it reads as a true/false choice — parity with the browser's
            # checked/unchecked. Without this, `checkbox` fell through to a plain
            # text prompt (the bug). Multi-option checkbox (browser multi-select) is
            # a separate, rarer case not handled here.
            if field_type in ('radio', 'checkbox'):
                options = field.get('options', ['true', 'false']) if isinstance(field, dict) else ['true', 'false']
                default = field.get('default') if isinstance(field, dict) else None
                value = self._collect_select_field(field_name, field_label, options, default, logger)
                # Normalise value back to Python bool / None before storing
                if value == 'true':
                    value = 'true'
                elif value == 'false':
                    value = 'false'
                # 'null' is left as the string 'null' so the Bifrost form handler can decide
                zConv[field_name] = value
                continue

            # Promote field_type based on schema-declared type so input_string.py
            # can route to the correct terminal handler (numeric coercion, temporal prompt hint).
            if field_type == 'text' and validator and table_name:
                schema_type = self._get_schema_field_type(validator, table_name, field_name)
                if schema_type in ('int', 'float', 'integer', 'numeric', 'number'):
                    field_type = 'number'
                elif schema_type in ('date', 'time', 'datetime'):
                    field_type = schema_type  # routes to _terminal_temporal_input → shows [DD/MM/YYYY] hint
                elif schema_type in ('bool', 'boolean'):
                    # Inline resolution — reuse select picker with true/false[/null] options
                    is_required = self._get_schema_field_required(validator, table_name, field_name)
                    bool_options = ['true', 'false'] if is_required else ['true', 'false', 'null']
                    field_default = self._get_schema_field_default(validator, table_name, field_name)
                    field_default_str = str(field_default).lower() if field_default is not None else None
                    value = self._collect_select_field(field_name, field_label, bool_options, field_default_str, logger)
                    zConv[field_name] = value
                    continue
                elif schema_type == 'uuid':
                    # UUID: show hint, accept blank (auto-generated upstream) or a user-provided v4 UUID.
                    prompt = f"  {field_label} [uuid — leave blank to auto-generate]: "
                    raw = self.zPrimitives.read_string(prompt).strip()
                    zConv[field_name] = raw   # empty → auto-gen in crud; non-empty → validated in crud
                    continue
                elif schema_type == 'json':
                    # JSON: single-line hint prompt (one-liner JSON is practical in zCLI/zTerminal).
                    # Bifrost live form gets a real <textarea> via server-side enrichment.
                    prompt = f"  {field_label} [json — e.g. {{\"key\": \"value\"}}]: "
                    raw = self.zPrimitives.read_string(prompt).strip()
                    zConv[field_name] = raw
                    continue

            # Field-level attributes (the declared vocabulary on this field). For pure
            # forms (no model) these ARE the contract — required / default / placeholder /
            # affix / datalist / accept etc. are honored straight from the zUI.
            field_attrs = field if isinstance(field, dict) else {}

            # Resolve default — field-level wins, schema default as fallback. Used for the
            # prompt hint and the empty-input fallback below.
            field_default = field_attrs.get('default')
            if field_default is None and validator and table_name:
                field_default = self._get_schema_field_default(validator, table_name, field_name)

            # Required is a declared semantic, not a schema-only concern: enforce it even
            # without a model (field-level `required:` wins, else schema-declared).
            is_required = self._field_is_required(
                field_attrs, validator, table_name, field_name
            )

            # Collect field value with validation loop
            value = self._collect_single_field_with_validation(
                field_name, field_type, field_label, validator, table_name, logger,
                field_default=field_default, field_attrs=field_attrs,
                is_required=is_required
            )

            # Apply schema default when value is empty and field has a default
            if (value == '' or value is None) and field_default is not None:
                if logger:
                    logger.debug(f"[zDialog] Field '{field_name}' empty → applying default '{field_default}'")
                value = str(field_default)

            # Save collected value
            zConv[field_name] = value

        return zConv

    def _parse_zdialog_field(self, field: Any) -> tuple:
        """
        Parse field specification into (name, type, label).
        
        Returns:
            tuple: (field_name, field_type, field_label)
        """
        if isinstance(field, dict):
            # Identity key (the zConv binding). Canonical: `zConv:`. `name:`/`field:`
            # are silent back-compat aliases. The resolved value is BOTH the form
            # field identity and the zConv key (zConv[field_name] = value).
            field_name = field.get('zConv', field.get('name', field.get('field', 'unknown')))
            field_type = field.get('type', None)
            field_label = field.get('label', field_name)
        else:
            field_name = str(field)
            field_type = None
            field_label = field_name

        # Auto-detect type from the field name when none is declared — SSOT parity
        # with the Bifrost FormRenderer (_createFieldGroup) so a bare `email` /
        # `phone` / `password` field behaves identically at the zCLI prompt and in
        # the browser (same validation / masking), honoring the page's promise.
        if field_type is None:
            lower = field_name.lower()
            if 'password' in lower:
                field_type = 'password'
            elif 'email' in lower:
                field_type = 'email'
            elif lower in ('tel', 'phone') or 'phone' in lower:
                field_type = 'tel'
            else:
                field_type = 'text'

        return field_name, field_type, field_label

    def _get_schema_field_type(
        self,
        validator: Any,
        table_name: str,
        field_name: str
    ) -> Optional[str]:
        """Return the schema-declared type string for a field, or None."""
        try:
            table_schema = validator.schema.get(table_name, {})
            field_def = table_schema.get(field_name, {})
            return field_def.get('type') if isinstance(field_def, dict) else None
        except Exception:
            return None

    def _get_schema_field_default(
        self,
        validator: Any,
        table_name: str,
        field_name: str
    ) -> Optional[Any]:
        """Return the schema-declared default value for a field, or None."""
        try:
            table_schema = validator.schema.get(table_name, {})
            field_def = table_schema.get(field_name, {})
            return field_def.get('default') if isinstance(field_def, dict) else None
        except Exception:
            return None

    def _get_schema_field_required(
        self,
        validator: Any,
        table_name: str,
        field_name: str
    ) -> bool:
        """Return True if the schema marks the field as required."""
        try:
            table_schema = validator.schema.get(table_name, {})
            field_def = table_schema.get(field_name, {})
            return bool(field_def.get('required', False)) if isinstance(field_def, dict) else False
        except Exception:
            return False

    def _field_is_required(
        self,
        field_attrs: Dict[str, Any],
        validator: Optional[Any],
        table_name: Optional[str],
        field_name: str
    ) -> bool:
        """Resolve whether a field is required, model-independently.

        Field-level `required:` (declared in the zUI) is authoritative — a pure
        form with no schema still enforces it. Only when the field omits the key
        do we fall back to the schema's `required` flag (when a model is bound).
        """
        if 'required' in field_attrs:
            return bool(field_attrs.get('required'))
        if validator and table_name:
            return self._get_schema_field_required(validator, table_name, field_name)
        return False

    # Field vocabulary keys forwarded verbatim to read_string so a field inside a
    # zDialog behaves like a standalone zInput (the InputEvents leaves' contract).
    # `type` is added separately; `required`/`default` are handled by the collector.
    _PASSTHROUGH_FIELD_KEYS = (
        'placeholder', 'prefix', 'suffix', 'datalist',
        'multiple', 'accept', 'format', 'readonly', 'disabled',
        # Raw field constraints — enforced by field_rules in the input hub
        # (apply with or without a type). SSOT with CONSTRAINT_KEYS there.
        'pattern', 'min', 'max', 'step', 'minlength', 'maxlength',
    )

    # Attrs whose semantic is boolean: presence-as-True downstream. A resolved
    # bool arrives as False (or the strings "False"/"false" from a string-first
    # zolo file) — Python truthiness would read "False" as ON, locking every
    # row (zOS#92). Coerce here: falsy → the attr is simply absent.
    # Membership + falsy set come from the field_rules SSOT; this surface
    # deliberately EXCLUDES 'required' — the collector owns the required gate
    # (see _PASSTHROUGH_FIELD_KEYS note above), so it must not leak into kwargs.
    _BOOLISH_FIELD_KEYS = tuple(
        k for k in field_rules.BOOLISH_ATTR_KEYS if k != 'required'
    )

    def _build_input_kwargs(self, field_attrs: Dict[str, Any], field_type: str) -> Dict[str, Any]:
        """Build the read_string kwargs for a dialog field from its declared attrs."""
        kwargs: Dict[str, Any] = {'type': field_type}
        for key in self._PASSTHROUGH_FIELD_KEYS:
            value = field_attrs.get(key)
            if value is None:
                continue
            if key in self._BOOLISH_FIELD_KEYS:
                if field_rules.is_falsy_attr(value):
                    continue  # falsy bool → attr absent (the falsy state)
                kwargs[key] = True
                continue
            kwargs[key] = value
        return kwargs

    @staticmethod
    def _is_empty_value(value: Any) -> bool:
        """True for None, blank/whitespace strings, and empty lists/tuples."""
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        if isinstance(value, (list, tuple)):
            return len(value) == 0
        return False

    def _collect_select_field(
        self,
        field_name: str,
        field_label: str,
        options: list,
        default: Optional[Any],
        logger: Optional[Any]
    ) -> str:
        """
        Collect a select/enum field via a numbered terminal pick-list.

        Displays numbered options, accepts index (1-N) or direct value.
        Empty input uses the default when one is defined.
        """
        if logger:
            logger.debug(f"[zDialog] Collecting select field '{field_name}' options={options} default={default}")

        # Display options list
        self.zPrimitives.line(f"\n  {field_label}:")
        for i, opt in enumerate(options, 1):
            suffix = "  (default)" if str(opt) == str(default) else ""
            self.zPrimitives.line(f"    {i}. {opt}{suffix}")

        default_hint = f" [{default}]" if default is not None else ""
        prompt = f"  Select (1–{len(options)}){default_hint}: "

        str_options = [str(o) for o in options]

        while True:
            raw = self.zPrimitives.read_string(prompt).strip()

            # Empty → use default
            if not raw and default is not None:
                if logger:
                    logger.debug(f"[zDialog] Select '{field_name}' → default '{default}'")
                return str(default)

            # Numeric index input
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(str_options):
                    if logger:
                        logger.debug(f"[zDialog] Select '{field_name}' → index {idx + 1} = '{str_options[idx]}'")
                    return str_options[idx]

            # Direct value input
            if raw in str_options:
                if logger:
                    logger.debug(f"[zDialog] Select '{field_name}' → direct value '{raw}'")
                return raw

            self.zPrimitives.line(f"\n  ⚠ Invalid choice. Enter a number (1–{len(options)}) or one of: {', '.join(str_options)}\n")

    @staticmethod
    def _is_truthy_flag(value: Any) -> bool:
        """Normalise a string-first boolean flag (`multi: true`) to a Python bool."""
        if value is True:
            return True
        return isinstance(value, str) and value.strip().lower() in ('true', '1', 'yes', 'on')

    @staticmethod
    def _normalise_default_list(default: Any) -> list:
        """Coerce a multi-select default (list, or comma-joined string) into a list."""
        if isinstance(default, list):
            return [str(d).strip() for d in default if str(d).strip()]
        if default is not None and str(default).strip():
            return [s.strip() for s in str(default).split(',') if s.strip()]
        return []

    def _collect_multiselect_field(
        self,
        field_name: str,
        field_label: str,
        options: list,
        default: Optional[Any],
        logger: Optional[Any]
    ) -> list:
        """
        Collect a multi-select field via a numbered terminal pick-list.

        Displays numbered options, accepts a comma-separated mix of indices (1-N)
        and/or direct values, and returns a LIST (order-preserving, de-duplicated).
        Empty input falls back to the default list. Browser parity: checkbox group.
        """
        str_options = [str(o) for o in options]
        default_list = self._normalise_default_list(default)

        if logger:
            logger.debug(
                f"[zDialog] Collecting multi-select '{field_name}' options={str_options} default={default_list}"
            )

        self.zPrimitives.line(f"\n  {field_label}:")
        for i, opt in enumerate(str_options, 1):
            suffix = "  (default)" if opt in default_list else ""
            self.zPrimitives.line(f"    {i}. {opt}{suffix}")

        default_hint = f" [{', '.join(default_list)}]" if default_list else ""
        prompt = f"  Select one or more (1–{len(str_options)}, comma-separated){default_hint}: "

        while True:
            raw = self.zPrimitives.read_string(prompt).strip()

            # Empty → default list (may be empty)
            if not raw:
                return default_list

            picks = [p.strip() for p in raw.split(',') if p.strip()]
            resolved = []
            valid = True
            for pick in picks:
                if pick.isdigit():
                    idx = int(pick) - 1
                    if 0 <= idx < len(str_options):
                        resolved.append(str_options[idx])
                    else:
                        valid = False
                        break
                elif pick in str_options:
                    resolved.append(pick)
                else:
                    valid = False
                    break

            if valid and resolved:
                # De-duplicate, preserve order
                seen = set()
                deduped = [x for x in resolved if not (x in seen or seen.add(x))]
                if logger:
                    logger.debug(f"[zDialog] Multi-select '{field_name}' → {deduped}")
                return deduped

            self.zPrimitives.line(
                f"\n  ⚠ Invalid choice. Enter numbers 1–{len(str_options)} "
                f"(comma-separated) or option names: {', '.join(str_options)}\n"
            )

    def _collect_single_field_with_validation(
        self,
        field_name: str,
        field_type: str,
        field_label: str,
        validator: Optional[Any],
        table_name: Optional[str],
        logger: Optional[Any],
        field_default: Optional[Any] = None,
        field_attrs: Optional[Dict[str, Any]] = None,
        is_required: bool = False
    ) -> Any:
        """
        Collect a single field value with validation retry loop.
        
        Returns:
            Any: The validated field value
        """
        field_attrs = field_attrs or {}
        has_default = field_default is not None and str(field_default).strip() != ""

        while True:
            # Collect input
            value = self._read_field_input(field_type, field_label, logger, field_name,
                                           field_default=field_default,
                                           field_attrs=field_attrs)

            # Required gate — model-independent. Honors the declared `required:` semantic
            # for pure forms: empty answer with no default → re-prompt (matches the
            # form-submit promise without depending on a schema validator).
            if is_required and self._is_empty_value(value) and not has_default:
                self._display_field_error(
                    f"{field_label} is required — please enter a value.",
                    logger, field_name
                )
                continue

            # Validate if validator available
            if validator and table_name:
                is_valid, error_msg = self._validate_field_value(
                    field_name, value, validator, table_name, logger
                )

                if is_valid:
                    if logger:
                        logger.info(f"[zDialog] ✅ Field '{field_name}' validation passed")
                    return value
                else:
                    # Display error and retry
                    self._display_field_error(error_msg, logger, field_name)
            else:
                # No model/schema validation — type-format validation already ran in the
                # input primitive. Accept the value (pure-form path).
                if logger:
                    logger.debug(f"[zDialog] No model validation for field '{field_name}' - accepting value")
                return value

    def _read_field_input(
        self,
        field_type: str,
        field_label: str,
        logger: Optional[Any],
        field_name: str,
        field_default: Optional[Any] = None,
        field_attrs: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Read input for a single field based on type.

        Forwards the field's declared vocabulary (placeholder, prefix/suffix,
        datalist, accept, multiple, format, …) to read_string so a field inside a
        zDialog behaves identically to a standalone zInput.
        """
        field_attrs = field_attrs or {}
        default_hint = f" [{field_default}]" if field_default is not None else ""
        input_kwargs = self._build_input_kwargs(field_attrs, field_type)

        # TODO(ssot): replace self.zPrimitives.read_password() with self.read_password()
        # to route through tier-2 event API (_event_map seam) instead of calling primitive directly.
        # Audit in context of zDialog testing — do not change before zDialog test coverage exists.
        if field_type == 'password':
            prompt = _FORMAT_FIELD_PROMPT.format(label=f"{field_label}{default_hint}")
            value = self.zPrimitives.read_password(prompt)
        elif any(k in input_kwargs for k in ('prefix', 'suffix', 'placeholder', 'datalist')):
            # Prompt-decorating attrs present — hand read_string the bare label and let
            # build_prompt (the SSOT prompt formatter) append the affix/placeholder + ": ".
            value = self.zPrimitives.read_string(f"{field_label}{default_hint}", **input_kwargs)
        else:
            prompt = _FORMAT_FIELD_PROMPT.format(label=f"{field_label}{default_hint}")
            value = self.zPrimitives.read_string(prompt, **input_kwargs)

        if logger:
            log_value = '********' if field_type == 'password' else value
            logger.debug(f"[zDialog] Field '{field_name}' input received: '{log_value}' (type: {field_type})")

        return value

    def _validate_field_value(
        self,
        field_name: str,
        value: Any,
        validator: Any,
        table_name: str,
        logger: Optional[Any]
    ) -> tuple:
        """
        Validate a field value against schema.
        
        Returns:
            tuple: (is_valid: bool, error_msg: Optional[str])
        """
        if logger:
            logger.debug(f"[zDialog] Validating field '{field_name}' against table '{table_name}'")

        if logger:
            logger.info(f"[zDialog] Validating '{field_name}': received value={value!r} (type={type(value).__name__})")

        is_valid, errors = validator.validate_field(table_name, field_name, value)

        if logger:
            logger.info(f"[zDialog] Validation result for '{field_name}': valid={is_valid}, errors={errors}")

        if not is_valid and field_name in errors:
            error_msg = errors[field_name]
            if logger:
                logger.info(f"[zDialog] Field '{field_name}' validation failed: {error_msg}")
            return False, error_msg

        return True, None

    def _display_field_error(
        self,
        error_msg: str,
        _logger: Optional[Any],
        _field_name: str
    ) -> None:
        """Display field validation error to user."""
        self.zPrimitives.line(f"\n⚠  {error_msg}\n")
