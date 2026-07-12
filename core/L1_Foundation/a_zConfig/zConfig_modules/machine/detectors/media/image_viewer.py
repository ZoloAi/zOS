# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/detectors/media/image_viewer.py
"""Image viewer detection and launch commands."""

from zOS import os, platform, subprocess, shutil, Optional
from ..shared import SUBPROCESS_TIMEOUT_SEC, OS_DEFAULT_HANDLER, _log_info, _log_warning

# Image viewer constants
IMAGE_VIEWER_MAPPING_MACOS = {
    'preview': 'Preview',
    'pixelmator': 'Pixelmator Pro',
    'affinity': 'Affinity Photo',
    'photoshop': 'Adobe Photoshop',
    'gimp': 'GIMP',
    'xnview': 'XnView',
}

LINUX_IMAGE_VIEWERS = (
    "eog",           # Eye of GNOME (GNOME default)
    "gwenview",      # KDE default
    "feh",           # Lightweight
    "gthumb",        # GNOME
    "ristretto",     # XFCE
    "gpicview",      # LXDE
    "nomacs",        # Cross-platform
    "geeqie",        # Lightweight
    "gimp",          # Power user
)

DEFAULT_MACOS_IMAGE_VIEWER = "Preview"
DEFAULT_LINUX_IMAGE_VIEWER = "eog"
DEFAULT_WINDOWS_IMAGE_VIEWER = "Photos"


def detect_image_viewer(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Detect default image viewer via env var or platform-specific methods.
    
    Detection Strategy:
    - macOS: Query LaunchServices for image/png handler → Preview
    - Linux: Check GUI environment (DISPLAY) → scan PATH for viewers → soft error if headless
    - Windows: Default to Photos → Paint fallback
    
    Returns:
        str: Image viewer name (e.g., "Preview", "eog", "Photos") or "none" if headless
    """
    # Check env var first (e.g., IMAGE_VIEWER="feh")
    viewer = os.getenv("IMAGE_VIEWER")
    if viewer:
        return viewer

    system = platform.system()
    if system == "Darwin":
        viewer = _detect_macos_image_viewer(log_level, is_production)
    elif system == "Linux":
        viewer = _detect_linux_image_viewer(log_level, is_production)
    elif system == "Windows":
        viewer = _detect_windows_image_viewer(log_level, is_production)
    else:
        viewer = "unknown"

    return viewer


def _detect_macos_image_viewer(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Query macOS LaunchServices for default image handler, fallback to Preview.
    
    Uses same pattern as browser detection - queries LSHandlers for image/png associations.
    """
    try:
        # Check LaunchServices for image/png handler
        result = subprocess.run(
            ['defaults', 'read', 'com.apple.LaunchServices/com.apple.launchservices.secure', 'LSHandlers'],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False
        )

        output_lower = result.stdout.lower()
        for key, name in IMAGE_VIEWER_MAPPING_MACOS.items():
            if key in output_lower:
                _log_info(f"Found default image viewer via LaunchServices: {name}", log_level, is_production)
                return name

    except Exception as e:
        _log_warning(f"Could not query LaunchServices for image viewer: {e}", log_level, is_production)

    return DEFAULT_MACOS_IMAGE_VIEWER


def _detect_linux_image_viewer(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Query Linux for GUI image viewer, gracefully handle headless environments.
    
    Strategy:
    1. Check if GUI is available (DISPLAY environment variable)
    2. If headless → log soft warning, return "none"
    3. If GUI → scan PATH for common image viewers
    4. Fallback to eog (most common)
    """
    # Check for GUI environment (X11 or Wayland)
    from ..shared import linux_gui_available
    if not linux_gui_available():
        _log_warning(
            "No GUI detected (DISPLAY/WAYLAND_DISPLAY not set). Image viewing unavailable in headless mode.",
            log_level, is_production
        )
        return "none"

    # Try xdg-mime first (freedesktop.org standard)
    try:
        result = subprocess.run(
            ['xdg-mime', 'query', 'default', 'image/png'],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False
        )
        if result.returncode == 0:
            desktop_file = result.stdout.strip().lower()
            # Extract viewer name from .desktop file (e.g., "eog.desktop" → "eog")
            if desktop_file:
                viewer_name = desktop_file.replace('.desktop', '')
                if shutil.which(viewer_name):
                    _log_info(f"Found image viewer via xdg-mime: {viewer_name}", log_level, is_production)
                    return viewer_name
    except Exception:
        pass  # Fall through to PATH scan

    # Scan PATH for common image viewers
    for viewer in LINUX_IMAGE_VIEWERS:
        if shutil.which(viewer):
            _log_info(f"Found image viewer in PATH: {viewer}", log_level, is_production)
            return viewer

    # Fallback
    _log_warning(
        f"No image viewer found in PATH. Defaulting to {DEFAULT_LINUX_IMAGE_VIEWER} "
        f"(may not be installed).",
        log_level, is_production
    )
    return DEFAULT_LINUX_IMAGE_VIEWER


def _detect_windows_image_viewer(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Detect Windows image viewer, default to Photos app.
    
    Windows 10/11: Photos app (modern)
    Fallback: Paint (mspaint) - always available
    """
    # Windows 10/11 Photos app is default
    # We default optimistically and let zOpen handle actual invocation
    _log_info(f"Using Windows default image viewer: {DEFAULT_WINDOWS_IMAGE_VIEWER}", log_level, is_production)
    return DEFAULT_WINDOWS_IMAGE_VIEWER


def get_image_viewer_launch_command(viewer_name: str) -> tuple:
    """
    Get platform-specific command to launch an image viewer.
    
    Args:
        viewer_name: Viewer name (e.g., "Preview", "eog", "Photos")
                    Case-insensitive, normalized internally
    
    Returns:
        Tuple of (command, args_template) where:
        - macOS: ("open", ["-a", "Preview"]) - use 'open -a "App Name"'
        - Linux: ("eog", []) - direct executable
        - Windows: ("start", [""]) - use start command for Photos
        - Unknown/None: (None, []) - viewer not available
    
    Examples:
        >>> get_image_viewer_launch_command("Preview")
        # macOS: ("open", ["-a", "Preview"])
        
        >>> get_image_viewer_launch_command("eog")
        # Linux: ("eog", [])
        
        >>> get_image_viewer_launch_command("Photos")
        # Windows: ("start", [""])
    """
    if viewer_name == "none" or viewer_name == "unknown":
        return (None, [])

    system = platform.system()
    viewer_lower = viewer_name.lower()

    # macOS: GUI apps need 'open -a'
    if system == "Darwin":
        macos_apps = {
            "preview": "Preview",
            "pixelmator": "Pixelmator Pro",
            "affinity": "Affinity Photo",
            "photoshop": "Adobe Photoshop",
            "gimp": "GIMP",
            "xnview": "XnView",
        }
        app_name = macos_apps.get(viewer_lower)
        if app_name:
            return ("open", ["-a", app_name])
        # If not in mapping, try direct command
        if shutil.which(viewer_lower):
            return (viewer_lower, [])
        return (None, [])

    # Linux: Direct executable names
    elif system == "Linux":
        # Check if viewer is in PATH
        if shutil.which(viewer_lower):
            return (viewer_lower, [])
        return (None, [])

    # Windows: Use 'start' command for default handlers
    elif system == "Windows":
        if viewer_lower == "photos":
            # Windows default handler — launcher translates to os.startfile()
            return (OS_DEFAULT_HANDLER, [])
        elif viewer_lower == "paint" or viewer_lower == "mspaint":
            return ("mspaint", [])
        # Try direct command
        if shutil.which(viewer_lower):
            return (viewer_lower, [])
        return (None, [])

    return (None, [])
