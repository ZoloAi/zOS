# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validators/__init__.py
"""
Schema-based data validation engine for zData CRUD operations.

This module implements a 5-layer validation architecture that enforces schema rules
before data operations (INSERT/UPDATE). Validation is fail-fast and extensible via
plugin validators.

Architecture Position
--------------------
- **Layer**: Tier 0 - Foundation
- **Dependencies**: Parsers (indirect), plugin system (optional)
- **Used By**: CRUD operations (insert, update), data_operations
- **Purpose**: Enforce data integrity before backend operations

5-Layer Validation Architecture
-------------------------------
The validator uses a layered approach where each layer validates specific aspects
of the data. Validation stops at the first failure (fail-fast):

**Layer 1: String Rules**
- min_length: Minimum string length
- max_length: Maximum string length

**Layer 2: Numeric Rules**
- min: Minimum numeric value
- max: Maximum numeric value

**Layer 3: Pattern Rules**
- pattern: Regex pattern matching

**Layer 4: Format Rules**
- email: RFC-compliant email validation
- url: HTTP/HTTPS URL validation
- phone: International phone number validation
- date: Date format validation (uses zConfig date_format)
- time: Time format validation (uses zConfig time_format)
- datetime: Datetime format validation (uses zConfig datetime_format)

**Layer 5: Plugin Validators**
- Custom business logic via zCLI plugin system
- Cross-field validation support
- Reusable validation functions

Supported Schema Rules
---------------------
**Field-Level Rules:**
- required: Field must be present (INSERT only)
- min_length: Minimum string length
- max_length: Maximum string length
- min: Minimum numeric value
- max: Maximum numeric value
- pattern: Regex pattern (with optional pattern_message)
- format: Built-in format validator (email, url, phone, date, time, datetime)
- validator: Plugin validator (&plugin.function syntax)
- error_message: Custom error message (overrides default)

**Field Attributes:**
- pk: Primary key (auto-skips required check)
- default: Has default value (auto-skips required check)

INSERT vs UPDATE Validation
---------------------------
**INSERT (Full Validation):**
- All layers (1-5) executed
- Required field checking enforced
- All fields in data validated

**UPDATE (Partial Validation):**
- All layers (1-5) executed
- Required field checking SKIPPED
- Only provided fields validated

This allows partial updates without requiring all fields.

Plugin Validator Integration
----------------------------
Layer 5 validators use the zCLI plugin system (&plugin.function syntax):

Schema example:
    email:
      type: str
      rules:
        format: email              # Layer 4: Built-in email format
        validator: "&validators.check_company_domain(['acme.com'])"  # Layer 5: Plugin

Plugin function signature:
    def check_company_domain(allowed_domains, value, field_name, table=None, full_data=None):
        # allowed_domains: User-provided args from schema
        # value: Field value being validated
        # field_name: Name of field
        # table: Table name (context)
        # full_data: All field data (for cross-field validation)
        
        if value.split('@')[1] not in allowed_domains:
            return (False, f"{field_name} must use company email domain")
        return (True, None)

Plugin validators must return: (is_valid: bool, error_message: str or None)

Usage Examples
-------------
INSERT validation (full):
    >>> validator = DataValidator(schema, logger=logger, zos=zos)
    >>> data = {"username": "john", "email": "john@acme.com", "age": 25}
    >>> is_valid, errors = validator.validate_insert("users", data)
    >>> if not is_valid:
    ...     print(f"Validation failed: {errors}")

UPDATE validation (partial):
    >>> data = {"email": "newemail@acme.com"}  # Only updating email
    >>> is_valid, errors = validator.validate_update("users", data)
    >>> # No required field errors, only validates provided fields

Format validator:
    >>> # Schema: email: { rules: { format: email } }
    >>> data = {"email": "invalid-email"}
    >>> is_valid, errors = validator.validate_insert("users", data)
    >>> # Returns: (False, {"email": "Invalid email address format"})

Plugin validator:
    >>> # Schema: email: { rules: { validator: "&validators.check_domain(['acme.com'])" } }
    >>> data = {"email": "user@badsite.com"}
    >>> is_valid, errors = validator.validate_insert("users", data)
    >>> # Returns: (False, {"email": "email must use company email domain"})

Integration
----------
This validator is used by:
- crud_insert.py: Pre-insert validation
- crud_update.py: Pre-update validation
- crud_upsert.py: Pre-upsert validation
- data_operations.py: Validation orchestration

See Also
--------
- crud_insert.py: Uses validate_insert() before INSERT
- crud_update.py: Uses validate_update() before UPDATE
- zParser plugin system: Plugin resolution mechanism

Module Structure
---------------
The validators package is organized by validation layer:
- constants.py: All constants (schema keys, error messages, patterns)
- string_validator.py: Layer 1 - String length validation
- numeric_validator.py: Layer 2 - Numeric range validation
- pattern_validator.py: Layer 3 - Regex pattern validation
- format_validator.py: Layer 4 - Built-in format validators
- plugin_validator.py: Layer 5 - Plugin validator integration
- core.py: DataValidator orchestrator class
"""

from .core import DataValidator
from .constants import *

__all__ = ["DataValidator"]
