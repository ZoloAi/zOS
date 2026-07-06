# zSys/errors/validation.py
"""Runtime validation utilities for zOS subsystems."""

__all__ = ["validate_zos_instance", "validate_zcli_instance"]


def validate_zos_instance(zos, subsystem_name, require_session=True):
    """Validate zOS instance is properly initialized (catches init order issues early)."""
    if zos is None:
        raise ValueError(
            f"{subsystem_name} received None for zOS instance. "
            f"This indicates an initialization order issue - subsystems must be "
            f"initialized with a valid zOS instance."
        )

    if require_session and not hasattr(zos, 'session'):
        raise ValueError(
            f"{subsystem_name} requires zOS instance with 'session' attribute. "
            f"Ensure zOS is fully initialized before creating {subsystem_name}."
        )

# Backward compatibility alias
validate_zcli_instance = validate_zos_instance
