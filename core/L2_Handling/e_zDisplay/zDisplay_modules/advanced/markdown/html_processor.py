"""
HTML Processor - Strips HTML tags and maps zTheme classes to ANSI codes.

Handles:
- <span class="zText-error">text</span> → red ANSI text
- <span class="zText-error zFont-bold">text</span> → red + bold ANSI
- Nested HTML tags (recursive processing)
- Anchor tags with href and class attributes

Author: zOS Framework
Version: 3.0.0
"""

from zOS import re


class HTMLProcessor:
    """Processes HTML tags and maps zTheme classes to ANSI codes."""

    def process(self, text: str) -> str:
        """
        Strip HTML tags and map zTheme classes to ANSI colors.
        
        Args:
            text: Text potentially containing HTML tags
            
        Returns:
            Text with HTML stripped and classes mapped to ANSI
        """
        if not text or '<' not in text:
            return text

        # Import color mapper
        try:
            from zSys.formatting.ztheme_to_ansi import (
                map_ztheme_classes_to_ansi,
                get_reset_code
            )
        except ImportError:
            # Fallback: just strip tags without color mapping
            return self._strip_all_tags(text)

        # Recursively process nested HTML tags
        pattern = r'<(\w+)((?:\s+[^>]*)?)>(.+?)</\1>'

        def process_tag(match):
            """Process a single HTML tag (recursively handles nested tags)."""
            tag_name = match.group(1)
            attrs_str = match.group(2) or ''
            content = match.group(3)

            # Recursively process nested tags first
            if '<' in content:
                content = self.process(content)

            # Extract attributes
            class_match = re.search(r'class=["\']([^"\']+)["\']', attrs_str)
            classes_str = class_match.group(1) if class_match else ''

            # Handle anchor tags
            if tag_name == 'a':
                if classes_str:
                    classes = classes_str.split()
                    ansi_codes = map_ztheme_classes_to_ansi(classes)
                    if ansi_codes:
                        return f"{ansi_codes}{content}{get_reset_code()}"
                return content

            # Handle other tags with class attributes
            if classes_str:
                classes = classes_str.split()
                ansi_codes = map_ztheme_classes_to_ansi(classes)
                if ansi_codes:
                    return f"{ansi_codes}{content}{get_reset_code()}"

            # No recognized classes - return content without tags
            return content

        # Process all HTML tags recursively
        max_iterations = 10  # Safety limit
        iteration = 0
        while '<' in text and iteration < max_iterations:
            new_text = re.sub(pattern, process_tag, text)
            if new_text == text:
                break
            text = new_text
            iteration += 1

        # Clean up any remaining tags
        text = self._strip_all_tags(text)

        return text

    def _strip_all_tags(self, text: str) -> str:
        """
        Strip all HTML tags without processing.
        
        Args:
            text: Text with HTML tags
            
        Returns:
            Text with all HTML tags removed
        """
        return re.sub(r'<[^>]+>', '', text)
