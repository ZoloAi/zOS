"""
Icon Renderer - Bootstrap Icons for zCLI and Bifrost

Renders Bootstrap Icons appropriately based on rendering mode:
- zBifrost (web): HTML <i> tags with Bootstrap Icons classes
- zCLI (terminal): Emoji fallbacks or Unicode characters

Features:
- Mode-aware rendering
- Color support (Bifrost only); sizing via _zClass
- Emoji fallbacks for common icons (terminal UX)
- Graceful degradation

Author: zOS Framework
Version: 1.0.0
Date: 2026-03-24
"""

from zOS import Any, Dict, Optional

from ...display_constants import MODE_ZCLI, MODE_BIFROST  # pylint: disable=relative-beyond-top-level


class IconRenderer:
    """
    Render Bootstrap Icons for zCLI and Bifrost modes.
    
    Provides mode-aware icon rendering with support for size/color styling
    in Bifrost mode and emoji fallbacks for terminal mode.
    """

    def __init__(self, display_instance: Any):
        """
        Initialize IconRenderer.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.logger = display_instance.logger if hasattr(display_instance, 'logger') else None
        self._icon_mapper = None  # Lazy load
    
    @property
    def icon_mapper(self):
        """Lazy-load icon mapper to avoid module-level import issues."""
        if self._icon_mapper is None:
            from ......zSys.accessibility import get_icon_mapper  # pylint: disable=relative-beyond-top-level
            self._icon_mapper = get_icon_mapper()
        return self._icon_mapper

    def render_icon(self, event_data: Dict[str, Any]) -> Optional[str]:
        """
        Render icon event.
        
        Args:
            event_data: Icon event dictionary with keys:
                - name: Icon name (required) - e.g., "bi-tools", "tools"
                - color: Color class (optional) - e.g., "zText-primary"
                - _zClass: Additional CSS classes (optional, Bifrost only) — also
                           the channel for sizing
        
        Returns:
            Rendered icon string, or None if name missing
        
        Examples:
            >>> event = {"name": "tools"}
            >>> renderer.render_icon(event)  # zBifrost mode
            '<i class="bi bi-tools"></i>'
            
            >>> event = {"name": "tools", "color": "zText-primary"}
            >>> renderer.render_icon(event)  # zBifrost mode
            '<span class="zText-primary"><i class="bi bi-tools"></i></span>'
            
            >>> event = {"name": "tools"}
            >>> renderer.render_icon(event)  # zCLI mode
            '🔧'
        """
        # Extract icon name
        icon_name = event_data.get('name')
        if not icon_name:
            if self.logger:
                self.logger.warning("[IconRenderer] Icon event missing 'name' property")
            return None

        # Get rendering mode
        mode = self._get_rendering_mode()

        # Extract styling (Bifrost only). Sizing is governed by _zClass — 'size'
        # is no longer a zIcon property.
        color = event_data.get('color')

        # Render icon
        rendered = self.icon_mapper.render_for_mode(
            icon_name=icon_name,
            mode=mode,
            color=color
        )

        # Handle additional _zClass in Bifrost mode
        if mode == MODE_BIFROST and '_zClass' in event_data:
            additional_classes = event_data['_zClass']
            if isinstance(additional_classes, str):
                # Sanitize foreign class hints before interpolating into markup
                # (single source of truth: zSys.accessibility.sanitize).
                from ......zSys.accessibility.sanitize import safe_class_attr  # pylint: disable=relative-beyond-top-level,import-outside-toplevel
                safe_classes = safe_class_attr(additional_classes)
                if safe_classes:
                    rendered = f'<span class="{safe_classes}">{rendered}</span>'

        return rendered

    def _get_rendering_mode(self) -> str:
        """
        Get current rendering mode from display instance.
        
        Returns:
            "zBifrost" or "zCLI"
        """
        if hasattr(self.display, 'mode'):
            mode = self.display.mode
            if mode and mode.lower() == MODE_BIFROST.lower():
                return MODE_BIFROST
        return MODE_ZCLI


def render_icon_event(display_instance: Any, event_data: Dict[str, Any]) -> Optional[str]:
    """
    Standalone function to render icon event.
    
    Args:
        display_instance: zDisplay instance
        event_data: Icon event dictionary
    
    Returns:
        Rendered icon string
    
    Example:
        >>> from zOS.core.L2_Handling.e_zDisplay.zDisplay_modules.basic.outputs.icon_renderer import render_icon_event
        >>> result = render_icon_event(display, {"name": "tools", "color": "zText-primary"})
    """
    renderer = IconRenderer(display_instance)
    return renderer.render_icon(event_data)
