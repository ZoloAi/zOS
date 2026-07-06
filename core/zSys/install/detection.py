# zSys/install/detection.py
"""
Installation detection utilities (Layer 0 - System Foundation).

Provides portable installation type detection for zOS without any
framework dependencies. Used by main.py bootstrap logger and info banner.
"""

from pathlib import Path
import os


def detect_installation_type(zos_package, detailed: bool = False) -> str:
    """
    Detect zOS installation type in a portable way.
    
    Args:
        zos_package: The imported zOS package (for __file__ access)
        detailed: If True, return detailed path info; if False, return simple type string
    
    Returns:
        str: Installation type ("editable", "standard", "uv", etc.)
    
    Examples:
        >>> import zOS as zos_package
        >>> detect_installation_type(zos_package, detailed=False)
        'editable'
        >>> detect_installation_type(zos_package, detailed=True)
        'editable (pip -e) at /Users/you/Projects/ZoloMedia/zOS'
    
    Detection Logic:
        1. Not in site-packages → editable install (pip install -e .)
        2. VIRTUAL_ENV with 'uv' → uv environment
        3. VIRTUAL_ENV set → virtual environment
        4. Otherwise → standard (site-packages)
    
    Notes:
        - Portable across Windows, Mac, Linux
        - Based on Python packaging standards
        - No hardcoded paths or system assumptions
    """
    try:
        zos_path = Path(zos_package.__file__).resolve()
        is_site_packages = 'site-packages' in str(zos_path)
        venv_path = os.getenv('VIRTUAL_ENV')

        # Determine type and detail
        if not is_site_packages:
            install_type = "editable"
            detail = f"editable (pip -e) at {zos_path.parent}"
        elif venv_path and 'uv' in venv_path.lower():
            install_type = "uv"
            detail = f"uv environment at {venv_path}"
        elif venv_path:
            install_type = "venv"
            detail = f"venv at {venv_path}"
        else:
            install_type = "standard"
            detail = f"standard (site-packages) at {zos_path.parent}"

        return detail if detailed else install_type

    except Exception as e:
        return f"unknown (detection failed: {e})" if detailed else "unknown"
