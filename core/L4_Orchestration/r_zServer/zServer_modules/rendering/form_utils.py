# zOS/core/L4_Orchestration/r_zServer/zServer_modules/rendering/form_utils.py

"""
Form Utilities - Declarative web form handling (zDialog pattern for web)

This module provides form parsing and processing for declarative web forms,
mirroring zDialog's pattern but for HTTP POST requests.

Philosophy:
    "Forms are data, not code" - Same as zDialog but for web routes

Architecture:
    - Parse form data from POST requests → Create zConv dict
    - Auto-validate against zSchema (via zData.DataValidator)
    - Execute onSubmit via zDispatch (same as zDialog)
    - Return redirect or error response

Integration:
    Used by handler.py and wsgi_app.py to process type: form routes

Examples:
    >>> # In routes.yaml
    >>> /contact:
    >>>   type: form
    >>>   model: "@.zSchema.contacts"
    >>>   fields: [name, email, message]
    >>>   onSubmit:
    >>>     zData: {action: create, table: contacts, data: zConv}
    >>>   onSuccess:
    >>>     redirect: /thank-you

Version: v1.5.7 Phase 1.2
"""

from urllib.parse import parse_qs, unquote_plus
from zOS import Any, Dict, Optional, Tuple, json

# =============================================================================
# MODULE CONSTANTS
# =============================================================================

# Form data keys
KEY_MODEL = "model"
KEY_FIELDS = "fields"
KEY_ON_SUBMIT = "onSubmit"
KEY_ON_SUCCESS = "onSuccess"
KEY_ON_ERROR = "onError"
KEY_REDIRECT = "redirect"
KEY_TEMPLATE = "template"

# Content types
CONTENT_TYPE_FORM = "application/x-www-form-urlencoded"
CONTENT_TYPE_MULTIPART = "multipart/form-data"
CONTENT_TYPE_JSON = "application/json"

# Log messages
LOG_MSG_PARSE_FORM = "[FormUtils] Parsing form data from %s"
LOG_MSG_CREATE_ZCONV = "[FormUtils] Created zConv with %d fields"
LOG_MSG_VALIDATION_START = "[FormUtils] Validating against schema: %s"
LOG_MSG_VALIDATION_PASS = "[FormUtils] Validation passed"
LOG_MSG_VALIDATION_FAIL = "[FormUtils] Validation failed: %s"
LOG_MSG_DISPATCH = "[FormUtils] Dispatching onSubmit"
LOG_MSG_SUCCESS = "[FormUtils] Form processing successful"
LOG_MSG_ERROR = "[FormUtils] Form processing error: %s"


# =============================================================================
# FORM PARSING FUNCTIONS
# =============================================================================

def parse_form_data(body: bytes, content_type: str, logger: Any) -> Dict[str, Any]:
    """
    Parse form data from HTTP POST body.
    
    Supports:
        - application/x-www-form-urlencoded (standard HTML forms)
        - application/json (JSON POST requests)
        - multipart/form-data (future: file uploads)
    
    Args:
        body: Raw POST body bytes
        content_type: Content-Type header value
        logger: Logger instance
    
    Returns:
        Dict[str, Any]: Parsed form data {field_name: value, ...}
    
    Examples:
        >>> body = b"name=John&email=john@example.com"
        >>> data = parse_form_data(body, "application/x-www-form-urlencoded", logger)
        >>> data
        {"name": "John", "email": "john@example.com"}
    """
    logger.debug(LOG_MSG_PARSE_FORM, content_type)

    # Handle URL-encoded forms (standard HTML forms)
    if CONTENT_TYPE_FORM in content_type:
        body_str = body.decode('utf-8')
        parsed = parse_qs(body_str, keep_blank_values=True)

        # parse_qs returns lists, we want single values
        form_data = {}
        for key, value_list in parsed.items():
            # Get first value (forms typically send single values)
            form_data[key] = value_list[0] if value_list else ""

        logger.debug(LOG_MSG_CREATE_ZCONV, len(form_data))
        return form_data

    # Handle JSON POST
    elif CONTENT_TYPE_JSON in content_type:
        try:
            form_data = json.loads(body.decode('utf-8'))
            logger.debug(LOG_MSG_CREATE_ZCONV, len(form_data))
            return form_data
        except json.JSONDecodeError as e:
            logger.error(LOG_MSG_ERROR, f"Invalid JSON: {e}")
            return {}

    # Multipart forms (file uploads)
    elif CONTENT_TYPE_MULTIPART in content_type:
        parsed = parse_multipart(body, content_type, logger)
        # parse_form_data historically returns a flat {field: value} dict; for
        # multipart we merge text fields and expose files under "_files" so
        # callers that only want scalars are unaffected.
        form_data = dict(parsed.get("fields", {}))
        if parsed.get("files"):
            form_data["_files"] = parsed["files"]
        logger.debug(LOG_MSG_CREATE_ZCONV, len(form_data))
        return form_data

    # Unknown content type
    else:
        logger.warning(f"[FormUtils] Unknown content type: {content_type}")
        return {}


def parse_multipart(body: bytes, content_type: str, logger: Any) -> Dict[str, Any]:
    """
    Parse a multipart/form-data POST body (dependency-free, stdlib only).

    Returns:
        {
          "fields": {name: str, ...},          # plain text form fields
          "files":  {name: {filename, content_type, data: bytes, size}, ...}
        }

    Notes:
        - cgi.FieldStorage is deprecated/removed in modern Python, so this does
          a careful manual boundary split on the raw bytes (never decode the
          whole body — file parts are binary).
        - On a malformed body it returns whatever it could parse plus logs.
    """
    result: Dict[str, Any] = {"fields": {}, "files": {}}

    # Extract boundary from the Content-Type header: ...; boundary=----xyz
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("boundary="):
            boundary = part[len("boundary="):].strip().strip('"')
            break
    if not boundary:
        logger.warning("[FormUtils] multipart: no boundary in Content-Type")
        return result

    delimiter = b"--" + boundary.encode("latin-1")
    # Split on the delimiter; first chunk is the preamble, last is the closing "--".
    sections = body.split(delimiter)
    for section in sections:
        # Trim the leading CRLF and skip empties / the closing "--\r\n".
        section = section.strip(b"\r\n")
        if not section or section == b"--":
            continue

        # Split part headers from the part body on the first blank line.
        header_blob, _, part_body = section.partition(b"\r\n\r\n")
        if not _:
            header_blob, _, part_body = section.partition(b"\n\n")
        headers = _parse_part_headers(header_blob)

        disposition = headers.get("content-disposition", "")
        name = _disposition_param(disposition, "name")
        if not name:
            continue
        filename = _disposition_param(disposition, "filename")

        if filename is not None:
            # File part — keep raw bytes.
            result["files"][name] = {
                "filename": filename,
                "content_type": headers.get("content-type", "application/octet-stream"),
                "data": part_body,
                "size": len(part_body),
            }
        else:
            # Plain text field.
            try:
                result["fields"][name] = part_body.decode("utf-8")
            except UnicodeDecodeError:
                result["fields"][name] = part_body.decode("latin-1", errors="replace")

    logger.debug(
        "[FormUtils] multipart parsed: %d field(s), %d file(s)",
        len(result["fields"]), len(result["files"]),
    )
    return result


def _parse_part_headers(blob: bytes) -> Dict[str, str]:
    """Parse a multipart part's header block into a lowercased dict."""
    headers: Dict[str, str] = {}
    for line in blob.split(b"\r\n"):
        if not line:
            continue
        try:
            text = line.decode("latin-1")
        except Exception:  # pylint: disable=broad-except
            continue
        if ":" in text:
            key, _, val = text.partition(":")
            headers[key.strip().lower()] = val.strip()
    return headers


def _disposition_param(disposition: str, param: str) -> Optional[str]:
    """Extract a parameter (name= / filename=) from a Content-Disposition value."""
    for piece in disposition.split(";"):
        piece = piece.strip()
        if piece.lower().startswith(param.lower() + "="):
            return piece[len(param) + 1:].strip().strip('"')
    return None


def extract_query_params(path: str) -> Dict[str, str]:
    """
    Extract query parameters from URL path.
    
    Used for GET requests with query strings (e.g., /search?q=test)
    
    Args:
        path: URL path with optional query string
    
    Returns:
        Dict[str, str]: Query parameters {key: value, ...}
    
    Examples:
        >>> extract_query_params("/search?q=test&page=2")
        {"q": "test", "page": "2"}
    """
    if "?" not in path:
        return {}

    _, query_string = path.split("?", 1)
    parsed = parse_qs(query_string, keep_blank_values=True)

    # Convert lists to single values
    params = {}
    for key, value_list in parsed.items():
        params[key] = value_list[0] if value_list else ""

    return params


# =============================================================================
# FORM PROCESSING FUNCTIONS
# =============================================================================

def process_form_submission(
    route: Dict[str, Any],
    form_data: Dict[str, Any],
    zcli: Any,
    logger: Any
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Process declarative form submission (zDialog pattern for web).
    
    Workflow:
        1. Create zConv from form_data
        2. Validate against zSchema (if model starts with '@')
        3. Execute onSubmit via zDispatch (if validation passes)
        4. Return redirect URL or error
    
    Args:
        route: Form route definition from routes.yaml
        form_data: Parsed form data from parse_form_data()
        zcli: zCLI instance (for dispatch, validation, etc.)
        logger: Logger instance
    
    Returns:
        Tuple[bool, Optional[str], Optional[str]]:
            - success: True if form processed successfully, False if validation failed
            - redirect_url: URL to redirect to (from onSuccess or onError)
            - error_message: Error message if validation failed
    
    Examples:
        >>> route = {
        ...     "model": "@.zSchema.contacts",
        ...     "fields": ["name", "email"],
        ...     "onSubmit": {"zData": {"action": "create", "table": "contacts", "data": "zConv"}},
        ...     "onSuccess": {"redirect": "/thank-you"}
        ... }
        >>> form_data = {"name": "John", "email": "john@example.com"}
        >>> success, redirect, error = process_form_submission(route, form_data, zcli, logger)
    """
    # Create zConv (same pattern as zDialog)
    zConv = form_data.copy()
    logger.debug(LOG_MSG_CREATE_ZCONV, len(zConv))

    # Get model for validation
    model = route.get(KEY_MODEL)

    # Validate if model starts with '@' (schema reference)
    if model and model.startswith('@'):
        logger.debug(LOG_MSG_VALIDATION_START, model)

        # Validate using zData.DataValidator (same as zDialog)
        is_valid, errors = _validate_form_data(model, zConv, zcli, logger)

        if not is_valid:
            logger.info(LOG_MSG_VALIDATION_FAIL, errors)

            # Get error redirect or template
            on_error = route.get(KEY_ON_ERROR, {})
            error_redirect = on_error.get(KEY_REDIRECT)

            # Format error message
            error_msg = _format_validation_errors(errors)

            return False, error_redirect, error_msg

        logger.debug(LOG_MSG_VALIDATION_PASS)

    # Execute onSubmit via zDispatch
    on_submit = route.get(KEY_ON_SUBMIT)
    if on_submit:
        logger.debug(LOG_MSG_DISPATCH)

        # Create context for dispatch (same as zDialog)
        context = {
            "model": model,
            "fields": route.get(KEY_FIELDS, []),
            "zConv": zConv
        }

        try:
            # Dispatch via zCLI (same pattern as zDialog.handle_submit)
            _execute_dispatch(on_submit, context, zcli, logger)
            logger.info(LOG_MSG_SUCCESS)
        except Exception as e:
            logger.error(LOG_MSG_ERROR, str(e))

            # Get error redirect
            on_error = route.get(KEY_ON_ERROR, {})
            error_redirect = on_error.get(KEY_REDIRECT)

            return False, error_redirect, str(e)

    # Get success redirect
    on_success = route.get(KEY_ON_SUCCESS, {})
    success_redirect = on_success.get(KEY_REDIRECT)

    return True, success_redirect, None


def _validate_form_data(
    model: str,
    zConv: Dict[str, Any],
    zcli: Any,
    logger: Any
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Validate form data against zSchema (same as zDialog).
    
    Args:
        model: Schema path (e.g., "@.zSchema.contacts")
        zConv: Form data dict
        zcli: zCLI instance
        logger: Logger instance
    
    Returns:
        Tuple[bool, Optional[Dict]]: (is_valid, errors)
    """
    # TODO: Integrate with zData.DataValidator
    # For now, just return True (validation will be added when zData integration is complete)
    logger.debug("[FormUtils] Validation integration pending - skipping for now")
    return True, None


def _format_validation_errors(errors: Optional[Dict[str, Any]]) -> str:
    """
    Format validation errors for display.
    
    Args:
        errors: Validation errors from DataValidator
    
    Returns:
        str: Formatted error message
    """
    if not errors:
        return "Validation failed"

    # Format errors (same pattern as zDialog)
    error_messages = []
    for field, error_list in errors.items():
        if isinstance(error_list, list):
            for error in error_list:
                error_messages.append(f"{field}: {error}")
        else:
            error_messages.append(f"{field}: {error_list}")

    return "; ".join(error_messages)


def _execute_dispatch(
    on_submit: Dict[str, Any],
    context: Dict[str, Any],
    zcli: Any,
    logger: Any
) -> Any:
    """
    Execute onSubmit via zDispatch (same as zDialog.handle_submit).
    
    Args:
        on_submit: onSubmit expression from route definition
        context: Context with model, fields, zConv
        zcli: zCLI instance
        logger: Logger instance
    
    Returns:
        Any: Result from zDispatch
    """
    # Import zDialog's submission handler to reuse logic
    from zOS.L2_Handling.j_zDialog.dialog_modules.dialog_submit import handle_submit

    # Create a minimal walker-like object for handle_submit
    class MinimalWalker:
        def __init__(self, zcli_instance):
            self.zcli = zcli_instance
            self.display = zcli_instance.display

    walker = MinimalWalker(zcli)

    # Use zDialog's handle_submit (same logic, zero duplication)
    return handle_submit(on_submit, context, logger, walker)
