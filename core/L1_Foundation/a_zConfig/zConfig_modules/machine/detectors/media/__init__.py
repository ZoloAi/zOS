# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/detectors/media/__init__.py
"""Media application detection modules (image, video, audio)."""

from .image_viewer import (
    detect_image_viewer,
    get_image_viewer_launch_command,
    IMAGE_VIEWER_MAPPING_MACOS,
    LINUX_IMAGE_VIEWERS,
    DEFAULT_MACOS_IMAGE_VIEWER,
    DEFAULT_LINUX_IMAGE_VIEWER,
    DEFAULT_WINDOWS_IMAGE_VIEWER,
)

from .video_player import (
    detect_video_player,
    get_video_player_launch_command,
    VIDEO_PLAYER_MAPPING_MACOS,
    LINUX_VIDEO_PLAYERS,
    DEFAULT_MACOS_VIDEO_PLAYER,
    DEFAULT_LINUX_VIDEO_PLAYER,
    DEFAULT_WINDOWS_VIDEO_PLAYER,
)

from .audio_player import (
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
