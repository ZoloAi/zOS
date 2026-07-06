# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/a_infrastructure/system_message_filter.py

"""
System Message Filter Utility
==============================

Utility function for checking if system messages should be displayed.
"""

from zOS import Any


def should_show_system_message(display: Any) -> bool:
    """
    Check if system messages should be displayed based on deployment mode.
    
    System messages (zDeclare) are conditionally displayed to prevent verbose output
    in production and testing environments. This respects zCLI's logging framework
    and deployment configuration.
    
    Args:
        display: zDisplay instance (for accessing zos.logger and zos.config)
    
    Returns:
        bool: True if system messages should be displayed, False otherwise
    
    Check Priority:
        1. Logger method:      zos.logger.should_show_sysmsg() (if available)
        2. Config deployment:  zos.config.is_production() / is_testing()
        3. Legacy debug flag:  session.get("debug") (backward compatibility)
        4. Default:            True (development mode - show messages)
    
    Deployment Rules:
        - Development: Show system messages
        - Testing:     Hide system messages (clean test output)
        - Production:  Hide system messages (clean user experience)
    
    Example:
        >>> if should_show_system_message(display):
        >>>     BasicOutputs.header("Loading Config...", color="MAIN")
    
    Notes:
        - This is a SPECIAL CASE utility that needs display access
        - Only used by zDeclare event for deployment-aware message filtering
        - All other infrastructure functions are pure (no display parameter)
    """
    if not display or not hasattr(display, 'session'):
        return True

    session = display.session

    # zFlat passive render: suppress framework breadcrumbs (zLoader/zLauncher/…)
    # so inert content renders clean (e.g. zSwiper page slides, zTable cells).
    try:
        if isinstance(session, dict) and session.get("_zflat"):
            return False
        _zsess = getattr(getattr(display, "zos", None), "session", None)
        if isinstance(_zsess, dict) and _zsess.get("_zflat"):
            return False
    except Exception:  # noqa: BLE001
        pass

    if hasattr(display, 'zos'):
        zos = display.zos

        if zos and hasattr(zos, 'logger') and hasattr(zos.logger, 'should_show_sysmsg'):
            return zos.logger.should_show_sysmsg()

        if zos and hasattr(zos, 'config'):
            if hasattr(zos.config, 'is_production') and zos.config.is_production():
                return False

            if hasattr(zos.config, 'environment') and hasattr(zos.config.environment, 'is_testing'):
                if zos.config.environment.is_testing():
                    return False

            if hasattr(zos.config, 'get_environment'):
                deployment = str(zos.config.get_environment('deployment', '')).lower()
                if deployment in ['testing', 'info', 'production']:
                    return False

            return True

    debug = session.get("debug")
    if debug is not None:
        return debug

    return True
