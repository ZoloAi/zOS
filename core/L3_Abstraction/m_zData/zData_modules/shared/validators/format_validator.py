# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validators/format_validator.py
"""
Format validation rules (Layer 4).

This module implements built-in format validators for the zData validation engine.
It provides validators for common data formats like email, URL, phone, and date/time.

Supported Formats:
- email: RFC-compliant email validation
- url: HTTP/HTTPS URL validation
- phone: International phone number validation
- date: Date format validation (uses zConfig date_format)
- time: Time format validation (uses zConfig time_format)
- datetime: Datetime format validation (uses zConfig datetime_format)

The format validator registry is built dynamically to support zos context injection
for date/time format validators that need zConfig settings.
"""

from zOS import Dict, Tuple, Optional, Any, re, datetime, Callable

from .constants import (
    FORMAT_EMAIL,
    FORMAT_URL,
    FORMAT_PHONE,
    FORMAT_DATE,
    FORMAT_TIME,
    FORMAT_DATETIME,
    FORMAT_UUID,
    PATTERN_EMAIL,
    PATTERN_URL,
    PATTERN_PHONE,
    PATTERN_PHONE_CLEAN,
    PATTERN_UUID,
    ERR_EMAIL_FORMAT,
    ERR_URL_FORMAT,
    ERR_PHONE_FORMAT,
    ERR_DATE_FORMAT,
    ERR_TIME_FORMAT,
    ERR_DATETIME_FORMAT,
    ERR_INVALID_UUID,
    RULE_KEY_FORMAT,
    RULE_KEY_ERROR_MESSAGE,
    LOG_UNKNOWN_FORMAT,
)

# ── Machine-pref → strptime maps (SSOT for validators + write-side coercion) ──
DATE_FORMAT_MAP = {
    "ddmmyyyy": "%d%m%Y", "mmddyyyy": "%m%d%Y", "yyyy-mm-dd": "%Y-%m-%d",
    "dd/mm/yyyy": "%d/%m/%Y", "mm/dd/yyyy": "%m/%d/%Y",
    "dd-mm-yyyy": "%d-%m-%Y", "mm-dd-yyyy": "%m-%d-%Y",
}
DATETIME_FORMAT_MAP = {
    "ddmmyyyy HH:MM:SS": "%d%m%Y %H:%M:%S", "mmddyyyy HH:MM:SS": "%m%d%Y %H:%M:%S",
    "yyyy-mm-dd HH:MM:SS": "%Y-%m-%d %H:%M:%S",
    "dd/mm/yyyy HH:MM:SS": "%d/%m/%Y %H:%M:%S", "mm/dd/yyyy HH:MM:SS": "%m/%d/%Y %H:%M:%S",
    "dd-mm-yyyy HH:MM:SS": "%d-%m-%Y %H:%M:%S", "mm-dd-yyyy HH:MM:SS": "%m-%d-%Y %H:%M:%S",
}
ISO_DATE = "%Y-%m-%d"
ISO_DATETIME = "%Y-%m-%d %H:%M:%S"


def coerce_temporal_iso(value: str, ftype: str, zos=None) -> str:
    """Normalize an accepted date/datetime string to its ISO canonical form.

    zOS#18: ``&zNow`` defaults come from machine prefs (``ddmmyyyy HH:MM:SS``),
    so the same app stored differently-formatted — and non-lexicographically-
    sortable — datetimes per machine, breaking ``order_by`` on the column. The
    write path calls this BEFORE validation so anything the validators accept
    lands in storage as ISO (``YYYY-MM-DD [HH:MM:SS]``), and an ISO date-only
    value is widened to midnight for a ``datetime`` column.

    Parse candidates: the machine-pref format, every other known pref format
    (unambiguous where they differ in separators/order), and ISO. Returns the
    ISO string on the first successful parse; an unparseable value is returned
    unchanged so the validator still owns the reject.
    """
    fmt_map = DATETIME_FORMAT_MAP if ftype == "datetime" else DATE_FORMAT_MAP
    pref_key = "datetime_format" if ftype == "datetime" else "date_format"
    iso_out = ISO_DATETIME if ftype == "datetime" else ISO_DATE

    candidates = []
    if zos:
        pref = zos.config.machine.get(pref_key)
        if pref in fmt_map:
            candidates.append(fmt_map[pref])
    candidates.append(iso_out)
    if ftype == "datetime":
        candidates.append(ISO_DATE)          # date-only widens to midnight
    else:
        candidates.append(ISO_DATETIME)      # datetime narrows to its date

    for fmt in candidates:
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime(iso_out)
        except ValueError:
            continue
    return value


def validate_email(value: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email address format (RFC-compliant).
    
    Format rules:
    - Username: alphanumeric, dots, underscores, hyphens, plus signs
    - @ symbol required
    - Domain: alphanumeric, dots, hyphens
    - TLD: 2+ letters
    
    Args:
        value: Email address string to validate
    
    Returns:
        Tuple of (is_valid, error_msg):
        - (True, None) if valid email
        - (False, error_message) if invalid
    
    Examples:
        >>> validate_email("user@example.com")
        (True, None)
        
        >>> validate_email("invalid-email")
        (False, "Invalid email address format")
    """
    if re.match(PATTERN_EMAIL, value):
        return True, None
    return False, ERR_EMAIL_FORMAT


def validate_url(value: str) -> Tuple[bool, Optional[str]]:
    """
    Validate URL format (HTTP/HTTPS only).
    
    Format rules:
    - Protocol: http:// or https:// (case-insensitive)
    - Domain: valid characters (no whitespace)
    - Path/query: any non-whitespace
    
    Args:
        value: URL string to validate
    
    Returns:
        Tuple of (is_valid, error_msg):
        - (True, None) if valid URL
        - (False, error_message) if invalid
    
    Examples:
        >>> validate_url("https://example.com")
        (True, None)
        
        >>> validate_url("ftp://example.com")
        (False, "Invalid URL format")
    """
    if re.match(PATTERN_URL, value, re.IGNORECASE):
        return True, None
    return False, ERR_URL_FORMAT


def validate_phone(value: str) -> Tuple[bool, Optional[str]]:
    """
    Validate phone number format (international).
    
    Format rules:
    - Optional + prefix
    - 10-15 digits
    - Formatting characters removed (spaces, dashes, parentheses, dots)
    
    Args:
        value: Phone number string to validate
    
    Returns:
        Tuple of (is_valid, error_msg):
        - (True, None) if valid phone
        - (False, error_message) if invalid
    
    Examples:
        >>> validate_phone("+1 (555) 123-4567")
        (True, None)
        
        >>> validate_phone("123")
        (False, "Invalid phone number format")
    
    Notes:
        - Accepts various formatting styles
        - Strips formatting before validation
        - Requires 10-15 digits after cleaning
    """
    # Remove formatting characters
    cleaned = re.sub(PATTERN_PHONE_CLEAN, '', value)

    # Validate cleaned number
    if re.match(PATTERN_PHONE, cleaned):
        return True, None
    return False, ERR_PHONE_FORMAT


def validate_date(value: str, zos=None) -> Tuple[bool, Optional[str]]:
    """
    Validate date format against zConfig settings.
    
    Args:
        value: Date string to validate
        zos: zOS framework instance for accessing config (optional)
    
    Returns:
        Tuple of (is_valid, error_msg):
        - (True, None) if valid date
        - (False, error_message) if invalid
    
    Notes:
        - Uses zConfig date_format setting if zos provided
        - Defaults to "ddmmyyyy" (matches zMachine DEFAULT_DATE_FORMAT)
        - Always accepts ISO 8601 (YYYY-MM-DD) as a valid fallback —
          HTML <input type="date"> always returns this format regardless of locale.
    """
    date_format = "ddmmyyyy"  # Default matches zMachine DEFAULT_DATE_FORMAT
    if zos:
        date_format = zos.config.machine.get('date_format', date_format)

    strptime_format = DATE_FORMAT_MAP.get(date_format, "%Y-%m-%d")

    try:
        datetime.strptime(value, strptime_format)
        return True, None
    except ValueError:
        pass

    # Browser <input type="date"> always returns ISO 8601 (YYYY-MM-DD); accept it universally.
    if strptime_format != ISO_DATE:
        try:
            datetime.strptime(value, ISO_DATE)
            return True, None
        except ValueError:
            pass

    return False, f"{ERR_DATE_FORMAT} (expected: {date_format})"


def validate_time(value: str, zos=None) -> Tuple[bool, Optional[str]]:
    """
    Validate time format against zConfig settings.
    
    Args:
        value: Time string to validate
        zos: zOS framework instance for accessing config (optional)
    
    Returns:
        Tuple of (is_valid, error_msg):
        - (True, None) if valid time
        - (False, error_message) if invalid
    
    Notes:
        - Uses zConfig time_format setting if zos provided
        - Defaults to "HH:MM:SS" format
    """
    time_format = "HH:MM:SS"  # Default
    if zos:
        time_format = zos.config.machine.get('time_format', time_format)

    format_map = {
        "HH:MM:SS": "%H:%M:%S", "HH:MM": "%H:%M",
        "hh:mm:ss": "%I:%M:%S", "hh:mm": "%I:%M",
    }
    strptime_format = format_map.get(time_format, "%H:%M:%S")

    try:
        datetime.strptime(value, strptime_format)
        return True, None
    except ValueError:
        return False, f"{ERR_TIME_FORMAT} (expected: {time_format})"


def validate_datetime(value: str, zos=None) -> Tuple[bool, Optional[str]]:
    """
    Validate datetime format against zConfig settings.
    
    Args:
        value: Datetime string to validate
        zos: zOS framework instance for accessing config (optional)
    
    Returns:
        Tuple of (is_valid, error_msg):
        - (True, None) if valid datetime
        - (False, error_message) if invalid
    
    Notes:
        - Uses zConfig datetime_format setting if zos provided
        - Defaults to "yyyy-mm-dd HH:MM:SS" format
        - Always accepts ISO 8601 (YYYY-MM-DD HH:MM:SS) as a valid fallback —
          write_prep.apply_defaults() shapes a `default: now` datetime to this
          format regardless of locale, same reasoning as validate_date's fallback.
        - Also accepts ISO date-only (YYYY-MM-DD) — an `&zNow(custom_format=
          'yyyy-mm-dd')` value is MORE standard than the machine-pref form and
          used to be the one that failed (zOS#18); write-side coercion widens it
          to midnight before storage.
    """
    datetime_format = "yyyy-mm-dd HH:MM:SS"  # Default
    if zos:
        datetime_format = zos.config.machine.get('datetime_format', datetime_format)

    strptime_format = DATETIME_FORMAT_MAP.get(datetime_format, ISO_DATETIME)

    # Machine-pref format, then the universal ISO fallbacks (full + date-only).
    accepted = [strptime_format]
    if strptime_format != ISO_DATETIME:
        accepted.append(ISO_DATETIME)
    accepted.append(ISO_DATE)

    for fmt in accepted:
        try:
            datetime.strptime(value, fmt)
            return True, None
        except ValueError:
            continue

    return False, f"{ERR_DATETIME_FORMAT} (expected: {datetime_format})"


def validate_uuid(value: str) -> Tuple[bool, Optional[str]]:
    """
    Validate UUID v4 format.

    Accepts the canonical 8-4-4-4-12 hex format with hyphens.
    Case-insensitive.

    Examples:
        >>> validate_uuid("550e8400-e29b-41d4-a716-446655440000")
        (True, None)

        >>> validate_uuid("not-a-uuid")
        (False, "... must be a valid UUID v4 ...")
    """
    if re.match(PATTERN_UUID, str(value).strip().lower()):
        return True, None
    return False, ERR_INVALID_UUID.format(field_name='value')


def get_format_validators(zos=None) -> Dict[str, Callable]:
    """
    Build format validator registry with zos context.

    Creates a registry mapping format type identifiers to validation functions.
    Date/time validators are wrapped with lambdas to inject zos context.

    Args:
        zos: zOS framework instance for date/time format configuration (optional)

    Returns:
        Dict mapping format types to validator functions

    Example:
        >>> validators = get_format_validators(zos)
        >>> is_valid, error = validators['email']("test@example.com")
    """
    return {
        FORMAT_EMAIL: validate_email,
        FORMAT_URL: validate_url,
        FORMAT_PHONE: validate_phone,
        FORMAT_DATE: lambda v: validate_date(v, zos),
        FORMAT_TIME: lambda v: validate_time(v, zos),
        FORMAT_DATETIME: lambda v: validate_datetime(v, zos),
        FORMAT_UUID: validate_uuid,
    }


def check_format_rules(
    field_name: str,  # pylint: disable=unused-argument
    value: Any,
    rules: Dict[str, Any],
    format_validators: Dict[str, Callable],
    logger=None
) -> Optional[str]:
    """
    Check built-in format validation rules (Layer 4).
    
    Validates:
    - format: Built-in format validators (email, url, phone, date, time, datetime)
    
    Supported formats:
    - email: RFC-compliant email validation
    - url: HTTP/HTTPS URL validation
    - phone: International phone number validation
    - date: Date format validation (uses zConfig)
    - time: Time format validation (uses zConfig)
    - datetime: Datetime format validation (uses zConfig)
    
    Args:
        field_name: Name of field (unused, kept for signature consistency)
        value: Value to validate (only checks if string)
        rules: Validation rules dict
        format_validators: Format validator registry from get_format_validators()
        logger: Logger instance for warnings (optional)
    
    Returns:
        None if valid or no format rule, error message string if invalid
    
    Examples:
        >>> validators = get_format_validators()
        >>> rules = {"format": "email"}
        >>> check_format_rules("contact", "invalid-email", rules, validators)
        "Invalid email address format"
        
        >>> check_format_rules("contact", "valid@example.com", rules, validators)
        None
    
    Notes:
        - Format type is case-insensitive
        - Custom error_message overrides default format error
        - Unknown format types log warning but don't fail
    """
    format_type = rules.get(RULE_KEY_FORMAT)
    if not format_type or not isinstance(value, str):
        return None

    # Look up format validator (case-insensitive)
    validator = format_validators.get(format_type.lower())
    if validator:
        is_valid, error = validator(value)
        if not is_valid:
            # Use custom error_message if provided, otherwise use validator's error
            return rules.get(RULE_KEY_ERROR_MESSAGE) or error
    else:
        # Unknown format type - log but don't fail
        if logger:
            logger.warning(LOG_UNKNOWN_FORMAT, format_type)

    return None
