# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/detectors/media_apps.py
"""
Image viewer, video player, and audio player detection for zCLI.

DEPRECATED: This file is maintained for backward compatibility only.
New code should import from .media submodules directly.
"""

# Re-export all functions and constants from new module structure
from .media import (
    # Image viewer
    detect_image_viewer,
    get_image_viewer_launch_command,
    IMAGE_VIEWER_MAPPING_MACOS,
    LINUX_IMAGE_VIEWERS,
    DEFAULT_MACOS_IMAGE_VIEWER,
    DEFAULT_LINUX_IMAGE_VIEWER,
    DEFAULT_WINDOWS_IMAGE_VIEWER,
    # Video player
    detect_video_player,
    get_video_player_launch_command,
    VIDEO_PLAYER_MAPPING_MACOS,
    LINUX_VIDEO_PLAYERS,
    DEFAULT_MACOS_VIDEO_PLAYER,
    DEFAULT_LINUX_VIDEO_PLAYER,
    DEFAULT_WINDOWS_VIDEO_PLAYER,
    # Audio player
    detect_audio_player,
    get_audio_player_launch_command,
    AUDIO_PLAYER_MAPPING_MACOS,
    LINUX_AUDIO_PLAYERS,
    DEFAULT_MACOS_AUDIO_PLAYER,
    DEFAULT_LINUX_AUDIO_PLAYER,
    DEFAULT_WINDOWS_AUDIO_PLAYER,
)

__all__ = [
    # Image viewer
    'detect_image_viewer',
    'get_image_viewer_launch_command',
    'IMAGE_VIEWER_MAPPING_MACOS',
    'LINUX_IMAGE_VIEWERS',
    'DEFAULT_MACOS_IMAGE_VIEWER',
    'DEFAULT_LINUX_IMAGE_VIEWER',
    'DEFAULT_WINDOWS_IMAGE_VIEWER',
    # Video player
    'detect_video_player',
    'get_video_player_launch_command',
    'VIDEO_PLAYER_MAPPING_MACOS',
    'LINUX_VIDEO_PLAYERS',
    'DEFAULT_MACOS_VIDEO_PLAYER',
    'DEFAULT_LINUX_VIDEO_PLAYER',
    'DEFAULT_WINDOWS_VIDEO_PLAYER',
    # Audio player
    'detect_audio_player',
    'get_audio_player_launch_command',
    'AUDIO_PLAYER_MAPPING_MACOS',
    'LINUX_AUDIO_PLAYERS',
    'DEFAULT_MACOS_AUDIO_PLAYER',
    'DEFAULT_LINUX_AUDIO_PLAYER',
    'DEFAULT_WINDOWS_AUDIO_PLAYER',
]
