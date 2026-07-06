# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validators/plugin_validator.py
"""
Plugin validator integration (Layer 5).

This module implements custom plugin validator support for the zData validation engine.
Plugin validators run AFTER all built-in validators pass and provide extensible
business logic validation using the zCLI plugin system.

Plugin Validator Syntax:
- Schema: validator: "&PluginName.function(args)"
- Example: validator: "&validators.check_email_domain(['company.com'])"

Plugin Function Signature:
    def custom_validator(user_arg1, user_arg2, ..., value, field_name, table=None, full_data=None):
        # User-provided args come first
        # value and field_name injected automatically
        # table and full_data provided as kwargs for context
        return (is_valid: bool, error_message: str or None)

Integration:
- Uses existing plugin infrastructure
- Graceful degradation if zos not provided
- Supports cross-field validation via full_data context
"""

from zOS import Dict, Optional, Any

from .constants import (
    RULE_KEY_VALIDATOR,
    RULE_KEY_ERROR_MESSAGE,
    PLUGIN_SYMBOL,
    CACHE_TYPE_PLUGIN,
    CONTEXT_KEY_TABLE,
    CONTEXT_KEY_FULL_DATA,
    ERR_PLUGIN_INVALID_RETURN,
    ERR_PLUGIN_EXECUTION,
    LOG_PLUGIN_NO_ZCLI,
    LOG_PLUGIN_INVALID_SYNTAX,
    LOG_PLUGIN_NOT_FOUND,
    LOG_PLUGIN_FUNCTION_MISSING,
    LOG_PLUGIN_INVALID_RETURN_FORMAT,
    LOG_PLUGIN_EXECUTION_ERROR,
)


def check_plugin_validator(
    field_name: str,
    value: Any,
    rules: Dict[str, Any],
    zos=None,
    logger=None,
    table_name: Optional[str] = None,
    full_data: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Check custom plugin validator (Layer 5 - business logic).
    
    Plugin validators run AFTER all built-in validators pass (layered validation).
    Uses existing zCLI plugin infrastructure (&PluginName.function(args) pattern).
    
    Args:
        field_name: Name of the field being validated
        value: Field value to validate
        rules: Validation rules from schema
        zos: zOS framework instance for plugin resolution (optional)
        logger: Logger instance for warnings/errors (optional)
        table_name: Table name for context (optional)
        full_data: All field data for cross-field validation (optional)
    
    Returns:
        None if valid or no validator, error message string if invalid
    
    Plugin Function Signature:
        def custom_validator(user_arg1, user_arg2, ..., value, field_name, table=None, full_data=None):
            # User-provided args come first
            # value and field_name injected automatically
            # table and full_data provided as kwargs for context
            return (is_valid: bool, error_message: str or None)
    
    Example schema usage:
        email:
          type: str
          rules:
            format: email  # Built-in (Layer 4)
            validator: "&validators.check_email_domain(['company.com'])"  # Plugin (Layer 5)
    
    Notes:
        - Requires zos instance (graceful degradation if missing)
        - Invalid syntax logs warning but doesn't fail
        - Missing plugins log warning but don't fail
        - Plugin execution errors return error message
    """
    validator_spec = rules.get(RULE_KEY_VALIDATOR)
    if not validator_spec:
        return None  # No plugin validator specified

    # Check if zos instance is available (required for plugin resolution)
    if not zos:
        if logger:
            logger.warning(LOG_PLUGIN_NO_ZCLI, validator_spec)
        return None  # Graceful degradation

    # Validate plugin invocation syntax (must start with &)
    if not isinstance(validator_spec, str) or not validator_spec.startswith(PLUGIN_SYMBOL):
        if logger:
            logger.warning(LOG_PLUGIN_INVALID_SYNTAX, validator_spec)
        return None  # Skip invalid syntax

    try:
        # Use existing zCLI plugin infrastructure to resolve and execute
        # Parse the plugin invocation (e.g., "&validators.check_email_domain(['company.com'])")
        # pylint: disable=import-outside-toplevel
        from zOS.L2_Handling.d_zParser.parser_modules.parser_plugin import (
            parse_plugin_invocation, parse_plugin_arguments
        )

        plugin_name, function_name, args_str = parse_plugin_invocation(validator_spec)

        # Check plugin cache first (reuse existing infrastructure)
        cached_module = zos.loader.cache.get(plugin_name, cache_type=CACHE_TYPE_PLUGIN)

        if not cached_module:
            # Plugin not found - graceful degradation
            if logger:
                logger.warning(LOG_PLUGIN_NOT_FOUND, plugin_name)
            return None  # Skip validation if plugin missing

        # Get function from cached module
        if not hasattr(cached_module, function_name):
            if logger:
                logger.warning(LOG_PLUGIN_FUNCTION_MISSING, function_name, plugin_name)
            return None  # Skip if function missing

        func = getattr(cached_module, function_name)

        # Parse user-provided arguments from schema
        user_args, user_kwargs = parse_plugin_arguments(args_str)

        # Inject validator-specific arguments:
        # User args come first, then value, field_name, then kwargs context
        final_args = list(user_args) + [value, field_name]
        final_kwargs = {
            **user_kwargs,
            CONTEXT_KEY_TABLE: table_name,
            CONTEXT_KEY_FULL_DATA: full_data or {}
        }

        # Execute validator plugin
        result = func(*final_args, **final_kwargs)

        # Validate return format (must be tuple: (is_valid, error_msg))
        if not isinstance(result, tuple) or len(result) != 2:
            if logger:
                logger.error(
                    LOG_PLUGIN_INVALID_RETURN_FORMAT,
                    plugin_name, function_name
                )
            return ERR_PLUGIN_INVALID_RETURN

        is_valid, error_msg = result

        # Return custom error_message if specified in rules, otherwise use plugin's error
        if not is_valid:
            return rules.get(RULE_KEY_ERROR_MESSAGE) or error_msg

        return None  # Validation passed

    except Exception as e:  # pylint: disable=broad-except
        # Log plugin execution errors but don't crash validation
        if logger:
            logger.error(
                LOG_PLUGIN_EXECUTION_ERROR,
                validator_spec, e, exc_info=True
            )
        return ERR_PLUGIN_EXECUTION.format(error=str(e))
