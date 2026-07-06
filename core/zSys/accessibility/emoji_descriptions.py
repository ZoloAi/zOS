"""
Emoji Descriptions Module

Provides emoji → human-readable description mappings for accessibility.
Uses official Unicode CLDR (Common Locale Data Repository) data.

Features:
- Lazy loading (no file access until first use)
- Singleton pattern (shared instance)
- Fallback behavior (returns emoji if description not found)
- Multiple input formats (emoji char, codepoint string)
- Terminal-friendly formatting

Usage:
    from zSys.accessibility import get_emoji_descriptions
    
    emoji_desc = get_emoji_descriptions()
    
    # Get description
    print(emoji_desc.emoji_to_description("📱"))  # "mobile phone"
    
    # From codepoint
    print(emoji_desc.codepoint_to_description("1F4F1"))  # "mobile phone"
    
    # Terminal format
    print(emoji_desc.format_for_terminal("📱"))  # "[mobile phone]"

Author: zOS Framework
Version: 1.0.0
Date: 2026-01-19
"""

import json
from typing import Optional, Dict

from ._data import load_data_json, EMOJI_A11Y_FILE


class EmojiDescriptions:
    """
    Emoji accessibility descriptions with lazy loading.
    
    Loads emoji → description mappings from emoji-a11y.en.json on first access.
    Cached in memory for performance.
    
    Attributes:
        _data: Dictionary of emoji → description mappings (None until loaded)
        _loaded: Whether data has been loaded from disk
    """

    def __init__(self):
        """Initialize with lazy loading (no file access yet)."""
        self._data: Optional[Dict[str, str]] = None
        self._loaded: bool = False

    def load(self) -> None:
        """
        Load emoji descriptions from JSON file (if not already loaded).
        
        Only loads once per instance (singleton pattern).
        Falls back gracefully if file not found or invalid.
        """
        # Already loaded - return immediately
        if self._loaded:
            return

        # Shared loader resolves zSys/data and degrades to {} on any error.
        self._data = load_data_json(EMOJI_A11Y_FILE)
        self._loaded = True

    def emoji_to_description(self, emoji: str) -> str:
        """
        Convert emoji character to human-readable description.
        
        Args:
            emoji: Emoji character (e.g., "📱", "😀")
            
        Returns:
            Human-readable description, or emoji itself if not found
            
        Examples:
            >>> emoji_desc.emoji_to_description("📱")
            "mobile phone"
            
            >>> emoji_desc.emoji_to_description("💻")
            "laptop"
            
            >>> emoji_desc.emoji_to_description("🤷")  # If not in data
            "🤷"
        """
        # Ensure data is loaded
        self.load()

        # Handle empty input
        if not emoji:
            return emoji

        # Strip variation selectors (U+FE0F) - common in emoji rendering
        # Example: ❤️ (with VS) → ❤ (base character)
        emoji_clean = emoji.replace('\uFE0F', '')

        # Lookup description (fallback to emoji itself)
        if self._data is None:
            return emoji
        return self._data.get(emoji_clean, emoji)

    def codepoint_to_description(self, codepoint: str) -> str:
        """
        Convert Unicode codepoint to description.
        
        Supports multiple formats:
        - Hex string: "1F4F1" or "0001F4F1"
        - With U+ prefix: "U+1F4F1"
        - With \\U prefix: "\\U0001F4F1"
        
        Args:
            codepoint: Unicode codepoint as hex string
            
        Returns:
            Human-readable description, or original string if invalid
            
        Examples:
            >>> emoji_desc.codepoint_to_description("1F4F1")
            "mobile phone"
            
            >>> emoji_desc.codepoint_to_description("U+1F4F1")
            "mobile phone"
            
            >>> emoji_desc.codepoint_to_description("\\U0001F4F1")
            "mobile phone"
        """
        # Ensure data is loaded
        self.load()

        # Handle empty input
        if not codepoint:
            return codepoint

        try:
            # Strip common prefixes
            codepoint_clean = codepoint.upper()
            codepoint_clean = codepoint_clean.replace('U+', '')
            codepoint_clean = codepoint_clean.replace('\\U', '')
            codepoint_clean = codepoint_clean.replace('0X', '')

            # Handle multi-codepoint sequences (ZWJ emojis, flags)
            # Example: "1F468_200D_1F4BB" (man technologist)
            if '_' in codepoint_clean or '-' in codepoint_clean:
                # Split and convert each part
                parts = codepoint_clean.replace('-', '_').split('_')
                emoji = ''.join(chr(int(part, 16)) for part in parts if part)
            else:
                # Single codepoint
                emoji = chr(int(codepoint_clean, 16))

            # Get description
            return self.emoji_to_description(emoji)

        except (ValueError, OverflowError):
            # Invalid codepoint - return original string
            return codepoint

    def format_for_terminal(self, emoji: str) -> str:
        """
        Format emoji for Terminal display as [description].
        
        Used in zCLI mode where emoji rendering may be incorrect
        or invisible. Converts emoji to text description in brackets.
        
        Args:
            emoji: Emoji character
            
        Returns:
            "[description]" or emoji itself if not found
            
        Examples:
            >>> emoji_desc.format_for_terminal("📱")
            "[mobile phone]"
            
            >>> emoji_desc.format_for_terminal("💻")
            "[laptop]"
            
            >>> emoji_desc.format_for_terminal("🤷")  # Not in data
            "🤷"  # Fallback to emoji itself
        """
        description = self.emoji_to_description(emoji)

        # Only wrap if we found a description (not fallback)
        if description != emoji:
            return f"[{description}]"
        else:
            # Fallback: return emoji as-is
            return emoji

    def has_description(self, emoji: str) -> bool:
        """
        Check if an emoji has a description in the database.
        
        Args:
            emoji: Emoji character
            
        Returns:
            True if description exists, False otherwise
            
        Examples:
            >>> emoji_desc.has_description("📱")
            True
            
            >>> emoji_desc.has_description("🤷‍♂️")  # Might not be in base data
            False
        """
        self.load()

        # Strip variation selectors
        emoji_clean = emoji.replace('\uFE0F', '')

        return emoji_clean in (self._data or {})

    def get_stats(self) -> dict:
        """
        Get statistics about loaded emoji data.
        
        Returns:
            Dict with keys: total_emojis, loaded, data_size_kb
            
        Examples:
            >>> emoji_desc.get_stats()
            {'total_emojis': 1966, 'loaded': True, 'data_size_kb': 47}
        """
        self.load()

        return {
            'total_emojis': len(self._data) if self._data else 0,
            'loaded': self._loaded,
            'data_size_kb': len(json.dumps(self._data)) // 1024 if self._data else 0,
        }


# Global singleton instance
_emoji_descriptions: Optional[EmojiDescriptions] = None


def get_emoji_descriptions() -> EmojiDescriptions:
    """
    Get the global emoji descriptions singleton instance.
    
    Creates instance on first call, reuses for subsequent calls.
    Ensures only one copy of emoji data in memory.
    
    Returns:
        Global EmojiDescriptions instance
        
    Examples:
        >>> from zSys.accessibility import get_emoji_descriptions
        >>> emoji_desc = get_emoji_descriptions()
        >>> print(emoji_desc.emoji_to_description("📱"))
        "mobile phone"
    """
    global _emoji_descriptions  # pylint: disable=global-statement

    if _emoji_descriptions is None:
        _emoji_descriptions = EmojiDescriptions()

    return _emoji_descriptions
