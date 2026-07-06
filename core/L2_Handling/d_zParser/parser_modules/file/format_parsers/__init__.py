# zOS/core/L2_Handling/g_zParser/parser_modules/file/format_parsers/__init__.py

"""
Format parser modules for file parsing.

Provides specialized parsers for different file formats (YAML, ZLSP, JSON, expressions)
with automatic format detection capabilities.

Public API:
    - parse_yaml: YAML file parsing
    - parse_zlsp: ZLSP/Zolo file parsing
    - parse_json: JSON file parsing
    - detect_format: Auto-detect file format from content
    - parse_json_expr: JSON expression parsing

Created: Phase 1.1 - Extract Format Parsers
Updated: Phase 1.2 - Separated ZLSP parser
"""

from .yaml_parser import parse_yaml
from .zlsp_parser import parse_zlsp
from .json_parser import parse_json
from .format_detector import detect_format
from .expr_parser import parse_json_expr

__all__ = ['parse_yaml', 'parse_zlsp', 'parse_json', 'detect_format', 'parse_json_expr']
