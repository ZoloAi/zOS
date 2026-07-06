# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/d_compounds/inputs/link_handler.py

"""
Link Handler - Helper module for BasicInputs
=============================================

Provides link handling logic:
- Extract labels from link configurations
- Execute link actions (open URL, navigate)
- GUI mode link selection
"""

from zOS import Any, List, Dict, Optional, Union, asyncio
import re


class LinkHandler:
    """Link handling logic for BasicInputs."""

    def __init__(self, display_instance: Any) -> None:
        """Initialize LinkHandler with display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives

    def parse_option_string(self, option_str: str) -> Dict[str, Any]:
        """Parse option string for inline modifiers like [disabled] or [default].
        
        Args:
            option_str: Option string to parse
            
        Returns:
            Dict with keys: clean_label, is_disabled, is_default
        """
        clean_label = option_str
        is_disabled = False
        is_default = False
        
        # Check for [disabled] suffix
        disabled_match = re.search(r'^(.*?)\s*\[disabled\]\s*$', option_str, re.IGNORECASE)
        if disabled_match:
            clean_label = disabled_match.group(1).strip()
            is_disabled = True
        
        # Check for [default] suffix
        default_match = re.search(r'^(.*?)\s*\[default\]\s*$', clean_label, re.IGNORECASE)
        if default_match:
            clean_label = default_match.group(1).strip()
            is_default = True
        
        return {
            'clean_label': clean_label,
            'is_disabled': is_disabled,
            'is_default': is_default
        }

    def extract_option_labels(
        self,
        options: List[Union[str, Dict[str, Any]]]
    ) -> tuple:
        """Extract display labels from options (strings or link dicts).
        
        Parses string options for inline modifiers like [disabled] and [default].
        Filters out disabled options for terminal mode display.
        
        Args:
            options: List of strings or link dictionaries
            
        Returns:
            tuple: (display_options, link_configs)
                - display_options: List[str] - Labels to show user (clean, no modifiers)
                - link_configs: List[Dict] or None - Link configs if present
        """
        if not options:
            return ([], None)

        # Check if first item is a dict (link config)
        if isinstance(options[0], dict):
            # Extract labels from link dicts
            labels = [opt.get('label', str(opt)) for opt in options]
            return (labels, options)
        else:
            # Parse plain strings for modifiers and extract clean labels
            clean_labels = []
            for opt in options:
                parsed = self.parse_option_string(opt)
                if parsed['is_disabled']:
                    clean_labels.append(f"{parsed['clean_label']} [disabled]")
                else:
                    clean_labels.append(parsed['clean_label'])
            return (clean_labels, None)

    def try_gui_mode_links(
        self,
        prompt: str,
        link_configs: List[Dict[str, Any]],
        style: str
    ) -> Optional['asyncio.Future']:
        """Try to handle link selection in GUI mode (Bifrost).
        
        Args:
            prompt: Selection prompt text
            link_configs: List of link configuration dicts
            style: Display style
            
        Returns:
            Optional[asyncio.Future]: Future that resolves when link is clicked,
                                      or None if not in GUI mode
        """
        if not self.zPrimitives.is_bifrost_mode():
            return None

        # Send link selection as special GUI event
        gui_future = self.zPrimitives._send_input_request(  # pylint: disable=protected-access
            'selection_links',
            prompt,
            links=link_configs,
            style=style
        )

        return gui_future

    def execute_link_action(
        self,
        selected: str,
        display_options: List[str],
        link_configs: List[Dict[str, Any]],
        renderer: Any,
        basic_outputs: Optional[Any] = None
    ) -> None:
        """Execute link action after selection in terminal mode.
        
        Args:
            selected: Selected option string
            display_options: List of display labels
            link_configs: List of link configuration dicts
            renderer: SelectionRenderer instance
            basic_outputs: BasicOutputs instance (optional)
        """
        if not selected or not link_configs:
            return

        # Find the index of the selected option
        try:
            index = display_options.index(selected)
            link_config = link_configs[index]
        except (ValueError, IndexError):
            renderer.display_feedback(
                f"Error: Could not find link config for '{selected}'",
                basic_outputs=basic_outputs
            )
            return

        # Extract link properties
        href = link_config.get('href', '#')
        label = link_config.get('label', selected)

        # Execute link based on type
        if href == '#':
            # Placeholder link
            renderer.output_text(
                f"'{label}' is a placeholder link (no action)",
                break_after=False,
                basic_outputs=basic_outputs
            )
            return

        # Detect link type and execute
        if href.startswith('http://') or href.startswith('https://') or href.startswith('www.'):
            # External URL - use zOpen module
            self._open_external_url(href, label, renderer, basic_outputs)
        elif href.startswith('$') or href.startswith('@'):
            # Internal navigation - use zNavigation
            self._navigate_internal(href, label, renderer, basic_outputs)
        else:
            # Unknown link type
            renderer.output_text(f"Link: {href}", break_after=False, basic_outputs=basic_outputs)

    def _open_external_url(
        self,
        href: str,
        label: str,
        renderer: Any,
        basic_outputs: Optional[Any] = None
    ) -> None:
        """Open external URL in browser.
        
        Args:
            href: URL to open
            label: Link label
            renderer: SelectionRenderer instance
            basic_outputs: BasicOutputs instance (optional)
        """
        if hasattr(self.display, 'zos') and hasattr(self.display.zos, 'open'):
            renderer.output_text(
                f"Opening '{label}' in browser...",
                break_after=False,
                basic_outputs=basic_outputs
            )
            # Import the open_url function from the zOpen module
            from ....k_zOpen.open_modules.open_urls import open_url
            open_url(href, self.display.zos.session, self.display, self.display.zos.logger)
        else:
            renderer.output_text(f"Link: {href}", break_after=False, basic_outputs=basic_outputs)

    def _navigate_internal(
        self,
        href: str,
        label: str,
        renderer: Any,
        basic_outputs: Optional[Any] = None
    ) -> None:
        """Navigate to internal location.
        
        Args:
            href: Internal navigation path
            label: Link label
            renderer: SelectionRenderer instance
            basic_outputs: BasicOutputs instance (optional)
        """
        if hasattr(self.display, 'zos') and hasattr(self.display.zos, 'navigation'):
            renderer.output_text(
                f"Navigating to '{label}'...",
                break_after=False,
                basic_outputs=basic_outputs
            )
            renderer.output_text(
                f"Internal navigation: {href}",
                break_after=False,
                basic_outputs=basic_outputs
            )
        else:
            renderer.output_text(f"Link: {href}", break_after=False, basic_outputs=basic_outputs)
