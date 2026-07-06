"""
Output Helper Modules for BasicOutputs
=======================================

This package contains specialized helper modules for the BasicOutputs facade:
- content_transformers: Emoji, semantic, and variable resolution
- header_renderer: Header rendering logic
- text_renderer: Text and rich_text rendering logic
- json_renderer: JSON serialization and syntax coloring
- field_renderer: Field and section rendering (render_field, render_section_title)
- rendering_utilities: Shared rendering utilities (color wrapping, indentation, config access)
- semantic_colors: Semantic color name to ANSI code mapping
"""

from .content_transformers import ContentTransformers
from .header_renderer import HeaderRenderer
from .text_renderer import TextRenderer
from .code_renderer import CodeRenderer
from .json_renderer import JsonRenderer
from .field_renderer import FieldRenderer
from .rendering_utilities import (
    get_config_value,
    wrap_with_color,
    apply_indent_to_lines,
    check_prefix_match
)
from .semantic_colors import get_semantic_color

__all__ = [
    'ContentTransformers',
    'HeaderRenderer',
    'TextRenderer',
    'CodeRenderer',
    'JsonRenderer',
    'FieldRenderer',
    'get_config_value',
    'wrap_with_color',
    'apply_indent_to_lines',
    'check_prefix_match',
    'get_semantic_color',
]
