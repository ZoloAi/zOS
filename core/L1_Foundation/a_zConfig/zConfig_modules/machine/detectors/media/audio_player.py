# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/detectors/media/audio_player.py
"""Audio player detection and launch commands."""

from zOS import os, platform, subprocess, shutil, Optional
from ..shared import SUBPROCESS_TIMEOUT_SEC, _log_info, _log_warning

# Audio player constants
AUDIO_PLAYER_MAPPING_MACOS = {
    'music': 'Music',
    'itunes': 'iTunes',
    'vlc': 'VLC',
    'quicktime': 'QuickTime Player',
}

LINUX_AUDIO_PLAYERS = (
    "vlc",           # Cross-platform, most common
    "audacious",     # Lightweight
    "rhythmbox",     # GNOME default
    "clementine",    # Feature-rich
    "deadbeef",      # Minimal
    "mpv",           # Terminal-friendly
    "totem",         # Videos (also plays audio)
)

DEFAULT_MACOS_AUDIO_PLAYER = "Music"
DEFAULT_LINUX_AUDIO_PLAYER = "vlc"
DEFAULT_WINDOWS_AUDIO_PLAYER = "Music"


def detect_audio_player(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Detect default audio player via env var or platform-specific methods.
    
    Detection Strategy:
    - macOS: Query LaunchServices for audio/mp3 handler → Music.app
    - Linux: Check GUI environment (DISPLAY) → scan PATH for players → soft error if headless
    - Windows: Default to Music (Groove Music) app
    
    Returns:
        str: Audio player name (e.g., "Music", "VLC", "Audacious") or "none" if headless
    """
    # Check env var first (e.g., AUDIO_PLAYER="vlc")
    player = os.getenv("AUDIO_PLAYER")
    if player:
        return player

    system = platform.system()
    if system == "Darwin":
        player = _detect_macos_audio_player(log_level, is_production)
    elif system == "Linux":
        player = _detect_linux_audio_player(log_level, is_production)
    elif system == "Windows":
        player = _detect_windows_audio_player(log_level, is_production)
    else:
        player = "unknown"

    return player


def _detect_macos_audio_player(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Query macOS LaunchServices for default audio handler, fallback to Music.app.
    
    Uses same pattern as image/video - queries LSHandlers for audio/mp3 associations.
    """
    try:
        # Check LaunchServices for audio/mp3 handler
        result = subprocess.run(
            ['defaults', 'read', 'com.apple.LaunchServices/com.apple.launchservices.secure', 'LSHandlers'],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False
        )

        output_lower = result.stdout.lower()
        for key, name in AUDIO_PLAYER_MAPPING_MACOS.items():
            if key in output_lower:
                _log_info(f"Found default audio player via LaunchServices: {name}", log_level, is_production)
                return name

    except Exception as e:
        _log_warning(f"Could not query LaunchServices for audio player: {e}", log_level, is_production)

    return DEFAULT_MACOS_AUDIO_PLAYER


def _detect_linux_audio_player(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Query Linux for GUI audio player, gracefully handle headless environments.
    
    Strategy:
    1. Check if GUI is available (DISPLAY environment variable)
    2. If headless → log soft warning, return "none"
    3. If GUI → scan PATH for common audio players
    4. Fallback to vlc (most common)
    """
    # Check for GUI environment
    if not os.getenv("DISPLAY"):
        _log_warning(
            "No GUI detected (DISPLAY not set). Audio playback unavailable in headless mode.",
            log_level, is_production
        )
        return "none"

    # Try xdg-mime first (freedesktop.org standard)
    try:
        result = subprocess.run(
            ['xdg-mime', 'query', 'default', 'audio/mpeg'],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False
        )
        if result.returncode == 0:
            desktop_file = result.stdout.strip().lower()
            # Extract player name from .desktop file
            if desktop_file:
                player_name = desktop_file.replace('.desktop', '')
                if shutil.which(player_name):
                    _log_info(f"Found audio player via xdg-mime: {player_name}", log_level, is_production)
                    return player_name
    except Exception:
        pass  # Fall through to PATH scan

    # Scan PATH for common audio players
    for player in LINUX_AUDIO_PLAYERS:
        if shutil.which(player):
            _log_info(f"Found audio player in PATH: {player}", log_level, is_production)
            return player

    # Fallback
    _log_warning(
        f"No audio player found in PATH. Defaulting to {DEFAULT_LINUX_AUDIO_PLAYER} "
        f"(may not be installed).",
        log_level, is_production
    )
    return DEFAULT_LINUX_AUDIO_PLAYER


def _detect_windows_audio_player(log_level: Optional[str] = None, is_production: bool = False) -> str:
    """
    Detect Windows audio player, default to Groove Music app.
    
    Windows 10/11: Groove Music (modern)
    Fallback: Windows Media Player - always available
    """
    # Windows 10/11 Groove Music app is default
    _log_info(f"Using Windows default audio player: {DEFAULT_WINDOWS_AUDIO_PLAYER}", log_level, is_production)
    return DEFAULT_WINDOWS_AUDIO_PLAYER


def get_audio_player_launch_command(player_name: str) -> tuple:
    """
    Get platform-specific command to launch an audio player.
    
    Args:
        player_name: Player name (e.g., "Music", "VLC", "Audacious")
                    Case-insensitive, normalized internally
    
    Returns:
        Tuple of (command, args_template) where:
        - macOS: ("open", ["-a", "Music"]) - use 'open -a "App Name"'
        - Linux: ("vlc", []) - direct executable
        - Windows: ("start", [""]) - use start command for Music
        - Unknown/None: (None, []) - player not available
    
    Examples:
        >>> get_audio_player_launch_command("Music")
        # macOS: ("open", ["-a", "Music"])
        
        >>> get_audio_player_launch_command("audacious")
        # Linux: ("audacious", [])
        
        >>> get_audio_player_launch_command("Music")
        # Windows: ("start", [""])
    """
    if player_name == "none" or player_name == "unknown":
        return (None, [])

    system = platform.system()
    player_lower = player_name.lower()

    # macOS: GUI apps need 'open -a'
    if system == "Darwin":
        macos_apps = {
            "music": "Music",
            "itunes": "iTunes",
            "vlc": "VLC",
            "quicktime player": "QuickTime Player",
            "quicktime": "QuickTime Player",
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
        if player_lower == "music":
            # Windows Groove Music app - use 'start' with empty first arg
            return ("start", [""])
        elif player_lower == "windows media player" or player_lower == "wmplayer":
            return ("wmplayer", [])
        # Try direct command
        if shutil.which(player_lower):
            return (player_lower, [])
        return (None, [])

    return (None, [])
