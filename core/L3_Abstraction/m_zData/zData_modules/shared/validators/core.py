# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validators/core.py
"""
DataValidator orchestrator class.

This module implements the main DataValidator class that orchestrates all 5 validation
layers for zData CRUD operations. It coordinates string, numeric, pattern, format, and
plugin validators to provide comprehensive schema-based validation.

Public API:
- validate_insert(table, data): Full validation for INSERT operations
- validate_update(table, data): Partial validation for UPDATE operations
- validate_field(table, field_name, value): Single field validation

The validator uses a fail-fast approach where validation stops at the first error
in each field, ensuring efficient validation with clear error messages.
"""

from zOS import Dict, Tuple, Optional, Any

from .constants import (
    SCHEMA_KEY_RULES,
    SCHEMA_KEY_REQUIRED,
    SCHEMA_KEY_PK,
    SCHEMA_KEY_DEFAULT,
    SCHEMA_KEY_TYPE,
    SCHEMA_KEY_ENUM,
    NUMERIC_SCHEMA_TYPES,
    TEMPORAL_SCHEMA_TYPES,
    BOOL_SCHEMA_TYPES,
    BOOL_TRUTHY_STRINGS,
    BOOL_FALSY_STRINGS,
    UUID_SCHEMA_TYPES,
    JSON_SCHEMA_TYPES,
    BLOB_SCHEMA_TYPES,
    SCHEMA_KEY_NULLABLE,
    ERR_FIELD_REQUIRED,
    ERR_INVALID_TYPE,
    ERR_INVALID_BOOL,
    ERR_INVALID_UUID,
    ERR_INVALID_JSON,
    ERR_NULL_NOT_ALLOWED,
    ERR_ENUM_VIOLATION,
    LOG_NO_SCHEMA,
    LOG_VALIDATION_FAILED,
    LOG_VALIDATION_PASSED,
)
from .string_validator import check_string_rules
from .numeric_validator import check_numeric_rules
from .pattern_validator import check_pattern_rules
from .format_validator import check_format_rules, get_format_validators
from .plugin_validator import check_plugin_validator
from .blob_validator import check_blob_rules


class DataValidator:
    """
    Schema-based data validation engine with 5-layer architecture.
    
    This class implements a layered validation system that enforces schema rules
    before CRUD operations. It supports built-in validators (string, numeric,
    pattern, format) and extensible plugin validators for custom business logic.
    
    Validation Architecture
    ----------------------
    The validator uses a fail-fast approach with 5 layers:
    
    1. **String Rules**: min_length, max_length
    2. **Numeric Rules**: min, max
    3. **Pattern Rules**: regex matching
    4. **Format Rules**: email, url, phone, date, time, datetime
    5. **Plugin Validators**: Custom business logic via &plugin.function syntax
    
    Public API
    ---------
    - **validate_insert(table, data)**: Full validation (INSERT operations)
      - Validates all fields in data
      - Enforces required field checks
      - Returns: (is_valid: bool, errors: Dict or None)
    
    - **validate_update(table, data)**: Partial validation (UPDATE operations)
      - Validates only provided fields
      - Skips required field checks
      - Returns: (is_valid: bool, errors: Dict or None)
    
    - **validate_field(table, field_name, value)**: Single field validation
      - Validates one field value
      - Useful for progressive form validation
      - Returns: (is_valid: bool, errors: Dict or None)
    
    Format Validator Registry
    ------------------------
    The format_validators dict maps format types to validation functions:
    - 'email' → validate_email()
    - 'url' → validate_url()
    - 'phone' → validate_phone()
    - 'date' → validate_date()
    - 'time' → validate_time()
    - 'datetime' → validate_datetime()
    
    Plugin Validator Integration
    ---------------------------
    Plugin validators (Layer 5) are resolved via the plugin system.
    Requires zos instance to be provided during initialization.

    Example:
        >>> validator = DataValidator(schema, logger=logger, zos=zos)
        >>> is_valid, errors = validator.validate_insert("users", data)
        >>> if not is_valid:
        ...     print(f"Errors: {errors}")
    
    Attributes:
        schema (Dict): Schema definition with table/field structure
        logger: Logger instance for validation messages
        zos: zOS framework instance (required for plugin validator resolution)
        format_validators (Dict): Registry of format validator functions
    """

    def __init__(
        self,
        schema: Dict[str, Any],
        logger: Optional[Any] = None,
        zos: Optional[Any] = None
    ) -> None:
        """
        Initialize DataValidator with schema and optional dependencies.
        
        Args:
            schema: Schema definition with table/field structure. Format:
                {
                    "table_name": {
                        "field_name": {
                            "type": "str",
                            "required": True,
                            "rules": {
                                "min_length": 3,
                                "max_length": 50,
                                "pattern": "^[a-zA-Z]+$",
                                "format": "email",
                                "validator": "&validators.custom_check(args)"
                            }
                        }
                    }
                }
            
            logger: Optional logger instance for validation messages.
                   If provided, logs warnings for validation failures
                   and debug messages for successful validations.
            
            zos: Optional zOS framework instance. Required if using plugin validators
                  (Layer 5). Provides access to plugin cache and resolution.
        
        Example:
            Basic initialization:
                >>> validator = DataValidator(schema)
            
            With logger:
                >>> validator = DataValidator(schema, logger=my_logger)
            
            With plugin support:
                >>> validator = DataValidator(schema, logger=my_logger, zos=z)
        
        Notes:
            - schema must contain table-level definitions
            - Plugin validators gracefully degrade if zos not provided
            - Format validators are always available (no dependencies)
        """
        self.schema = schema
        self.logger = logger
        self.zos = zos  # For plugin validator resolution

        # Format validator registry (Layer 4)
        self.format_validators = get_format_validators(zos)

        # TODO: Architecture Review - Consider centralizing ALL zData parsing logic to zParser
        #       Current state: zData has its own parsers/ directory (value_parser, where_parser)
        #       Proposal: Evaluate moving format validators and value parsing to zParser subsystem
        #       Rationale: Parsing is semantically zParser territory, but zData needs domain-specific validation
        #       Decision: Keep in zData for v1.5.14 (consistent with email/url/phone), revisit in v1.6.0
        #       Reference: This architectural question raised during Step 4.3.2d cleanup (2026-01-01)

    def validate_field(
        self,
        table: str,
        field_name: str,
        value: Any
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        Validate a single field value against schema rules.
        
        This method allows field-by-field validation for progressive form input.
        It validates the field using all 5 validation layers.
        
        Args:
            table: Table name to validate against
            field_name: Name of the field to validate
            value: Value to validate
        
        Returns:
            Tuple of (is_valid, errors):
            - is_valid: True if validation passes, False otherwise
            - errors: None if valid, Dict with {field_name: error_message} if invalid
        
        Examples:
            Valid field:
                >>> is_valid, errors = validator.validate_field("users", "email", "john@acme.com")
                >>> # Returns: (True, None)
            
            Invalid field:
                >>> is_valid, errors = validator.validate_field("users", "email", "invalid")
                >>> # Returns: (False, {"email": "Invalid email address format"})
        """
        # Get table schema
        table_schema = self.schema.get(table)
        if not table_schema or not isinstance(table_schema, dict):
            return True, None  # No schema = no validation (graceful)

        # Get field definition
        field_def = table_schema.get(field_name)
        if not field_def or not isinstance(field_def, dict):
            return True, None  # No field def = no validation

        # Get rules
        rules = field_def.get(SCHEMA_KEY_RULES, {})
        has_enum = bool(field_def.get(SCHEMA_KEY_ENUM))
        if not rules and not field_def.get(SCHEMA_KEY_REQUIRED, False) and not has_enum:
            return True, None  # No rules, no enum, and not required = valid

        # Validate using internal method
        is_valid, error_msg = self._validate_field(
            field_name=field_name,
            value=value,
            rules=rules,
            field_def=field_def,
            table_name=table,
            full_data={field_name: value}
        )

        # Return in same format as validate_insert
        if is_valid:
            return True, None
        else:
            return False, {field_name: error_msg}

    def validate_insert(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        Validate data for INSERT operation (full validation).
        
        INSERT validation performs full checks including:
        - All 5 validation layers for provided fields
        - Required field enforcement (with pk/default exceptions)
        - Returns detailed error messages per field
        
        Args:
            table: Table name to validate against
            data: Dictionary of field_name → value to validate
        
        Returns:
            Tuple of (is_valid, errors):
            - is_valid: True if all validations pass, False otherwise
            - errors: None if valid, Dict of {field_name: error_message} if invalid
        
        Validation Process:
            1. Check schema exists for table
            2. Run 5-layer validation on each provided field
            3. Check required fields are present (skip pk/default)
            4. Return combined error dict or success
        
        Examples:
            Valid data:
                >>> data = {"username": "john", "email": "john@acme.com", "age": 25}
                >>> is_valid, errors = validator.validate_insert("users", data)
                >>> # Returns: (True, None)
            
            Invalid data (min_length):
                >>> data = {"username": "ab"}  # min_length: 3
                >>> is_valid, errors = validator.validate_insert("users", data)
                >>> # Returns: (False, {"username": "username must be at least 3 characters"})
            
            Missing required field:
                >>> data = {"username": "john"}  # email is required
                >>> is_valid, errors = validator.validate_insert("users", data)
                >>> # Returns: (False, {"email": "email is required"})
        
        Notes:
            - Returns (True, None) if table schema not found (graceful)
            - Skips fields without schema definition
            - Primary keys and fields with defaults skip required check
            - Plugin validators (Layer 5) executed if zos provided
        
        See Also:
            - validate_update(): Partial validation for UPDATE operations
            - _validate_field(): 5-layer validation implementation
        """
        table_schema = self.schema.get(table, {})
        if not table_schema:
            if self.logger:
                self.logger.warning(LOG_NO_SCHEMA, table)
            return True, None

        errors = {}

        # Validate provided fields (all 5 layers)
        for field_name, value in data.items():
            field_def = table_schema.get(field_name)
            if not field_def or not isinstance(field_def, dict):
                continue

            rules = field_def.get(SCHEMA_KEY_RULES, {})
            is_required = field_def.get(SCHEMA_KEY_REQUIRED, False)
            has_enum = bool(field_def.get(SCHEMA_KEY_ENUM))
            has_temporal = field_def.get(SCHEMA_KEY_TYPE, '') in TEMPORAL_SCHEMA_TYPES
            has_bool = field_def.get(SCHEMA_KEY_TYPE, '') in BOOL_SCHEMA_TYPES
            has_uuid = field_def.get(SCHEMA_KEY_TYPE, '') in UUID_SCHEMA_TYPES
            has_json = field_def.get(SCHEMA_KEY_TYPE, '') in JSON_SCHEMA_TYPES
            has_blob = field_def.get(SCHEMA_KEY_TYPE, '') in BLOB_SCHEMA_TYPES
            has_nullable_constraint = field_def.get(SCHEMA_KEY_NULLABLE, True) is False
            if not rules and not is_required and not has_enum and not has_temporal and not has_bool and not has_uuid and not has_json and not has_blob and not has_nullable_constraint:
                continue

            # Pass table_name and full_data for plugin validator context
            is_valid, error_msg = self._validate_field(
                field_name, value, rules, field_def,
                table_name=table, full_data=data
            )
            if not is_valid:
                errors[field_name] = error_msg

        # Check required fields (INSERT only)
        for field_name, field_def in table_schema.items():
            if not isinstance(field_def, dict):
                continue

            is_required = field_def.get(SCHEMA_KEY_REQUIRED, False)
            if is_required and field_name not in data:
                # Skip required check for pk and default fields
                if field_def.get(SCHEMA_KEY_PK, False) or SCHEMA_KEY_DEFAULT in field_def:
                    continue
                errors[field_name] = ERR_FIELD_REQUIRED.format(field_name=field_name)

        # Return results
        if errors:
            if self.logger:
                self.logger.warning(LOG_VALIDATION_FAILED, len(errors))
            return False, errors

        if self.logger:
            self.logger.debug(LOG_VALIDATION_PASSED, table)
        return True, None

    def validate_update(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        Validate data for UPDATE operation (partial validation).
        
        UPDATE validation performs partial checks:
        - All 5 validation layers for provided fields
        - NO required field enforcement (allows partial updates)
        - Returns detailed error messages per field
        
        Args:
            table: Table name to validate against
            data: Dictionary of field_name → value to validate (partial data)
        
        Returns:
            Tuple of (is_valid, errors):
            - is_valid: True if all validations pass, False otherwise
            - errors: None if valid, Dict of {field_name: error_message} if invalid
        
        Validation Process:
            1. Check schema exists for table
            2. Run 5-layer validation on each provided field
            3. Skip required field checks (partial update)
            4. Return combined error dict or success
        
        Examples:
            Valid partial update:
                >>> data = {"email": "newemail@acme.com"}  # Only updating email
                >>> is_valid, errors = validator.validate_update("users", data)
                >>> # Returns: (True, None)
            
            Invalid partial update:
                >>> data = {"email": "invalid-email"}  # format check fails
                >>> is_valid, errors = validator.validate_update("users", data)
                >>> # Returns: (False, {"email": "Invalid email address format"})
            
            Multiple field update:
                >>> data = {"username": "newname", "age": 30}
                >>> is_valid, errors = validator.validate_update("users", data)
                >>> # Returns: (True, None) - validates both fields
        
        Differences from validate_insert:
            - No required field enforcement
            - Only validates provided fields
            - Allows empty data dict (returns success)
        
        Notes:
            - Returns (True, None) if table schema not found (graceful)
            - Skips fields without schema definition
            - Plugin validators (Layer 5) executed if zos provided
            - Same 5-layer validation as INSERT for provided fields
        
        See Also:
            - validate_insert(): Full validation for INSERT operations
            - _validate_field(): 5-layer validation implementation
        """
        table_schema = self.schema.get(table, {})
        if not table_schema:
            if self.logger:
                self.logger.warning(LOG_NO_SCHEMA, table)
            return True, None

        errors = {}

        # Validate provided fields only (all 5 layers)
        for field_name, value in data.items():
            field_def = table_schema.get(field_name)
            if not field_def or not isinstance(field_def, dict):
                continue

            rules = field_def.get(SCHEMA_KEY_RULES, {})
            is_required = field_def.get(SCHEMA_KEY_REQUIRED, False)
            has_enum = bool(field_def.get(SCHEMA_KEY_ENUM))
            has_temporal = field_def.get(SCHEMA_KEY_TYPE, '') in TEMPORAL_SCHEMA_TYPES
            has_bool = field_def.get(SCHEMA_KEY_TYPE, '') in BOOL_SCHEMA_TYPES
            has_uuid = field_def.get(SCHEMA_KEY_TYPE, '') in UUID_SCHEMA_TYPES
            has_json = field_def.get(SCHEMA_KEY_TYPE, '') in JSON_SCHEMA_TYPES
            has_blob = field_def.get(SCHEMA_KEY_TYPE, '') in BLOB_SCHEMA_TYPES
            has_nullable_constraint = field_def.get(SCHEMA_KEY_NULLABLE, True) is False
            if not rules and not is_required and not has_enum and not has_temporal and not has_bool and not has_uuid and not has_json and not has_blob and not has_nullable_constraint:
                continue

            # Pass table_name and full_data for plugin validator context
            is_valid, error_msg = self._validate_field(
                field_name, value, rules, field_def,
                table_name=table, full_data=data
            )
            if not is_valid:
                errors[field_name] = error_msg

        # Return results (no required field check)
        if errors:
            if self.logger:
                self.logger.warning(LOG_VALIDATION_FAILED, len(errors))
            return False, errors

        if self.logger:
            self.logger.debug(LOG_VALIDATION_PASSED, table)
        return True, None

    def _validate_field(
        self,
        field_name: str,
        value: Any,
        rules: Dict[str, Any],
        field_def: Dict[str, Any],
        table_name: Optional[str] = None,
        full_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate single field against schema rules (5-layer validation).
        
        This method implements the core validation logic using a fail-fast approach.
        Each layer validates a specific aspect, stopping at the first error.
        
        Validation Order (fail-fast):
            Layer 1: String rules (min_length, max_length)
            Layer 2: Numeric rules (min, max)
            Layer 3: Pattern rules (regex)
            Layer 4: Format rules (email, url, phone, date, time, datetime)
            Layer 5: Plugin validator (custom business logic)
        
        Args:
            field_name: Name of the field being validated
            value: Value to validate (any type)
            rules: Validation rules from schema (dict of rule_key: rule_value)
            field_def: Full field definition from schema
            table_name: Table name for plugin context (optional)
            full_data: All field data for cross-field validation (optional)
        
        Returns:
            Tuple of (is_valid, error_msg):
            - is_valid: True if validation passes, False otherwise
            - error_msg: None if valid, error message string if invalid
        
        Notes:
            - None or empty string values skip validation if not required
            - Each layer only validates if relevant (e.g., string layer skips non-strings)
            - Plugin validators run last (after all built-in validators)
            - Returns at first error (fail-fast)
        """
        # Handle None/empty values
        schema_type = field_def.get(SCHEMA_KEY_TYPE, '')
        if value is None or value == "":
            if field_def.get(SCHEMA_KEY_REQUIRED, False):
                return False, ERR_FIELD_REQUIRED.format(field_name=field_name)
            # nullable: false (opt-in) — field is optional to include but must not be submitted as null/empty.
            if field_def.get(SCHEMA_KEY_NULLABLE, True) is False:
                return False, ERR_NULL_NOT_ALLOWED.format(field_name=field_name)
            # UUID fields: empty is valid — auto-generation is handled upstream in crud_insert/crud_update.
            return True, None

        # Layer 0: Type coercion

        # bool coercion — accept truthy/falsy strings; reject invalid values.
        # Null is accepted when the field is not required (handled by required check above).
        if schema_type in BOOL_SCHEMA_TYPES:
            if not isinstance(value, bool):
                str_val = str(value).strip().lower()
                if str_val in BOOL_TRUTHY_STRINGS:
                    value = True
                elif str_val in BOOL_FALSY_STRINGS:
                    value = False
                else:
                    return False, ERR_INVALID_BOOL.format(field_name=field_name, value=value)
            # bool fields don't need further layer checks — coercion is the full validation.
            return True, None

        # UUID format validation — a non-empty value must parse as a UUID of the
        # declared version (rules.version, default 4). This stays in lockstep with
        # the upstream auto-generator (crud_insert/crud_update) which emits v1 when
        # version: 1 is declared and v4 otherwise. Empty values are auto-generated
        # before this point.
        if schema_type in UUID_SCHEMA_TYPES:
            import uuid as _uuid  # pylint: disable=import-outside-toplevel
            want_version = (rules or {}).get('version', 4)
            try:
                parsed = _uuid.UUID(str(value).strip())
            except (ValueError, AttributeError, TypeError):
                return False, ERR_INVALID_UUID.format(field_name=field_name)
            if parsed.version != want_version:
                return False, ERR_INVALID_UUID.format(field_name=field_name)
            return True, None

        # JSON parsing — if a string is given it must parse as valid JSON.
        # Dicts/lists are accepted as-is; primitives (int/bool) are also valid JSON values.
        if schema_type in JSON_SCHEMA_TYPES:
            import json as _json  # pylint: disable=import-outside-toplevel
            if isinstance(value, str):
                try:
                    _json.loads(value)
                except (ValueError, TypeError):
                    return False, ERR_INVALID_JSON.format(field_name=field_name, value=value[:80])
            # dict/list/int/float/bool are already valid JSON-serialisable — accept.
            return True, None

        # Blob — binary passthrough. Value is normalised to bytes upstream
        # (coerce_blob); here we enforce size/shape only. Binary is non-comparable,
        # so it skips the string/numeric/pattern/format layers entirely.
        if schema_type in BLOB_SCHEMA_TYPES:
            error = check_blob_rules(field_name, value, rules)
            if error:
                return False, error
            return True, None

        # int/float coercion — if schema declares int/float but a string is given,
        # attempt to coerce so downstream numeric range checks receive the correct type.
        # For int types, first parse as float so '25.0' is accepted, then reject non-integers.
        if schema_type in NUMERIC_SCHEMA_TYPES and isinstance(value, str):
            try:
                if schema_type in ('float', 'double', 'numeric'):
                    value = float(value)
                else:
                    float_val = float(value)
                    if float_val != int(float_val):
                        return False, ERR_INVALID_TYPE.format(
                            field_name=field_name, expected_type='integer', value=value
                        )
                    value = int(float_val)
            except (ValueError, TypeError):
                expected = 'number' if schema_type in ('float', 'double', 'numeric') else 'integer'
                return False, ERR_INVALID_TYPE.format(
                    field_name=field_name, expected_type=expected, value=value
                )

        # Layer 0.5: Enum membership check
        enum_values = field_def.get(SCHEMA_KEY_ENUM)
        if enum_values and isinstance(enum_values, list):
            str_enum = [str(v) for v in enum_values]
            if str(value) not in str_enum:
                return False, ERR_ENUM_VIOLATION.format(
                    field_name=field_name,
                    choices=', '.join(str_enum)
                )

        # Layer 1: String rules
        error = check_string_rules(field_name, value, rules)
        if error:
            return False, error

        # Layer 2: Numeric rules
        error = check_numeric_rules(field_name, value, rules)
        if error:
            return False, error

        # Layer 3: Pattern rules
        error = check_pattern_rules(field_name, value, rules)
        if error:
            return False, error

        # Layer 4: Format rules
        # If the schema type is a temporal type (date/time/datetime) and no explicit
        # `format:` rule is set in rules, inject the type itself as the format key so
        # `type: date` alone triggers date validation via zConfig/zMachine defaults.
        if schema_type in TEMPORAL_SCHEMA_TYPES and 'format' not in rules:
            rules = dict(rules)
            rules['format'] = schema_type
        error = check_format_rules(field_name, value, rules, self.format_validators, self.logger)
        if error:
            return False, error

        # Layer 5: Plugin validator (runs AFTER all built-in validators pass)
        error = check_plugin_validator(
            field_name, value, rules,
            zos=self.zos,
            logger=self.logger,
            table_name=table_name,
            full_data=full_data
        )
        if error:
            return False, error

        return True, None
