# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/detectors/media/video_player.py
"""Video player detection and launch commands."""

from zOS import os, platform, subprocess, shutil, Optional
from ..shared import SUBPROCESS_TIMEOUT_SEC, _log_info, _log_warning

# Video player constants
VIDEO_PLAYER_MAPPING_MACOS = {
    'quicktime': 'QuickTime Player',
    'vlc': 'VLC',
    'iina': 'IINA',
    'mpv': 'mpv',
}

LINUX_VIDEO_PLAYERS = (
    "vlc",           # Cross-platform, most common
    "mpv",           # Lightweight
    "totem",         # GNOME default (Videos)
    "celluloid",     # mpv GUI
    "smplayer",      # Feature-rich
    "parole",        # XFCE
    "dragon",        # KDE
)

DEFAULT_MACOS_VIDEO_PLAYER = "QuickTime Player"
DEFAULT_LINUX_VIDEO_PLAYER = "vlc"
DEFAULT_WINDOWS_VIDEO_PLAYER = "Movies"


def detect_video_player(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Detect default video player via env var or platform-specific methods.
    
    Detection Strategy:
    - macOS: Query LaunchServices for video/mp4 handler → QuickTime Player
    - Linux: Check GUI environment (DISPLAY) → scan PATH for players → soft error if headless
    - Windows: Default to Movies & TV app
    
    Returns:
        str: Video player name (e.g., "QuickTime Player", "VLC", "Movies") or "none" if headless
    """
    # Check env var first (e.g., VIDEO_PLAYER="vlc")
    player = os.getenv("VIDEO_PLAYER")
    if player:
        return player

    system = platform.system()
    if system == "Darwin":
        player = _detect_macos_video_player(log_level, is_production)
    elif system == "Linux":
        player = _detect_linux_video_player(log_level, is_production)
    elif system == "Windows":
        player = _detect_windows_video_player(log_level, is_production)
    else:
        player = "unknown"

    return player


def _detect_macos_video_player(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Query macOS LaunchServices for default video handler, fallback to QuickTime Player.
    
    Uses same pattern as image viewer detection - queries LSHandlers for video/mp4 associations.
    """
    try:
        # Check LaunchServices for video/mp4 handler
        result = subprocess.run(
            ['defaults', 'read', 'com.apple.LaunchServices/com.apple.launchservices.secure', 'LSHandlers'],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False
        )

        output_lower = result.stdout.lower()
        for key, name in VIDEO_PLAYER_MAPPING_MACOS.items():
            if key in output_lower:
                _log_info(f"Found default video player via LaunchServices: {name}", log_level, is_production)
                return name

    except Exception as e:
        _log_warning(f"Could not query LaunchServices for video player: {e}", log_level, is_production)

    return DEFAULT_MACOS_VIDEO_PLAYER


def _detect_linux_video_player(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Query Linux for GUI video player, gracefully handle headless environments.
    
    Strategy:
    1. Check if GUI is available (DISPLAY environment variable)
    2. If headless → log soft warning, return "none"
    3. If GUI → scan PATH for common video players
    4. Fallback to vlc (most common)
    """
    # Check for GUI environment
    if not os.getenv("DISPLAY"):
        _log_warning(
            "No GUI detected (DISPLAY not set). Video playback unavailable in headless mode.",
            log_level, is_production
        )
        return "none"

    # Try xdg-mime first (freedesktop.org standard)
    try:
        result = subprocess.run(
            ['xdg-mime', 'query', 'default', 'video/mp4'],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False
        )
        if result.returncode == 0:
            desktop_file = result.stdout.strip().lower()
            # Extract player name from .desktop file (e.g., "vlc.desktop" → "vlc")
            if desktop_file:
                player_name = desktop_file.replace('.desktop', '')
                if shutil.which(player_name):
                    _log_info(f"Found video player via xdg-mime: {player_name}", log_level, is_production)
                    return player_name
    except Exception:
        pass  # Fall through to PATH scan

    # Scan PATH for common video players
    for player in LINUX_VIDEO_PLAYERS:
        if shutil.which(player):
            _log_info(f"Found video player in PATH: {player}", log_level, is_production)
            return player

    # Fallback
    _log_warning(
        f"No video player found in PATH. Defaulting to {DEFAULT_LINUX_VIDEO_PLAYER} "
        f"(may not be installed).",
        log_level, is_production
    )
    return DEFAULT_LINUX_VIDEO_PLAYER


def _detect_windows_video_player(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Detect Windows video player, default to Movies & TV app.
    
    Windows 10/11: Movies & TV app (modern)
    Fallback: Windows Media Player - always available
    """
    # Windows 10/11 Movies & TV app is default
    # We default optimistically and let zOpen handle actual invocation
    _log_info(f"Using Windows default video player: {DEFAULT_WINDOWS_VIDEO_PLAYER}", log_level, is_production)
    return DEFAULT_WINDOWS_VIDEO_PLAYER


def get_video_player_launch_command(player_name: str) -> tuple:
    """
    Get platform-specific command to launch a video player.
    
    Args:
        player_name: Player name (e.g., "QuickTime Player", "VLC", "Movies")
                    Case-insensitive, normalized internally
    
    Returns:
        Tuple of (command, args_template) where:
        - macOS: ("open", ["-a", "QuickTime Player"]) - use 'open -a "App Name"'
        - Linux: ("vlc", []) - direct executable
        - Windows: ("start", [""]) - use start command for Movies
        - Unknown/None: (None, []) - player not available
    
    Examples:
        >>> get_video_player_launch_command("QuickTime Player")
        # macOS: ("open", ["-a", "QuickTime Player"])
        
        >>> get_video_player_launch_command("vlc")
        # Linux: ("vlc", [])
        
        >>> get_video_player_launch_command("Movies")
        # Windows: ("start", [""])
    """
    if player_name == "none" or player_name == "unknown":
        return (None, [])

    system = platform.system()
    player_lower = player_name.lower()

    # macOS: GUI apps need 'open -a'
    if system == "Darwin":
        macos_apps = {
            "quicktime player": "QuickTime Player",
            "quicktime": "QuickTime Player",
            "vlc": "VLC",
            "iina": "IINA",
            "mpv": "mpv",
        }
        app_name = macos_apps.get(player_lower)
        if app_name:
            return ("open", ["-a", app_name])
        # If not in mapping, try direct command
        if shutil.which(player_lower):
            return (player_lower, [])
        return (None, [])

    # Linux: Direct executable names
    elif system == "Linux":
        # Check if player is in PATH
        if shutil.which(player_lower):
            return (player_lower, [])
        return (None, [])

    # Windows: Use 'start' command for default handlers
    elif system == "Windows":
        if player_lower == "movies":
            # Windows Movies & TV app - use 'start' with empty first arg
            return ("start", [""])
        elif player_lower == "windows media player" or player_lower == "wmplayer":
            return ("wmplayer", [])
        # Try direct command
        if shutil.which(player_lower):
            return (player_lower, [])
        return (None, [])

    return (None, [])
