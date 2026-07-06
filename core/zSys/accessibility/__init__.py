"""
zSys Accessibility Module

Provides accessibility features across the zOS framework, including:
- Emoji descriptions for screen readers and zCLI mode (emoji_descriptions)
- Bootstrap Icons mapping for mode-aware icon rendering (icon_mapper)
- Allowlist sanitizers for safe HTML emission of icon names / class hints (sanitize)

Author: zOS Framework
Version: 1.0.0
"""

from .emoji_descriptions import (
    EmojiDescriptions,
    get_emoji_descriptions,
)
from .icon_mapper import (
    IconMapper,
    get_icon_mapper,
)
from .sanitize import (
    safe_icon_name,
    safe_class_attr,
)
from .terminal_gate import (
    supports_emoji,
    set_supports_emoji,
    emoji_safe,
    install_stream_gate,
)

__all__ = [
    'EmojiDescriptions',
    'get_emoji_descriptions',
    'IconMapper',
    'get_icon_mapper',
    'safe_icon_name',
    'safe_class_attr',
    'supports_emoji',
    'set_supports_emoji',
    'emoji_safe',
    'install_stream_gate',
]
