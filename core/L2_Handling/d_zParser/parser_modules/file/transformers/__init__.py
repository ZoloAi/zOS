# zOS/core/L2_Handling/g_zParser/parser_modules/file/transformers/__init__.py

"""
Transformer modules for file parsing.

Provides RBAC transformation and file type detection for parsed content.

Public API:
    - transform_parsed_ui_for_walker: RBAC structure transformation for zWalker
    - detect_ui_file: UI file detection
    - detect_server_file: Server file detection

Created: Phase 1.2 - Extract Transformers from parser_file.py
"""

from .rbac_transformer import transform_parsed_ui_for_walker
from .file_type_detector import detect_ui_file, detect_server_file

__all__ = ['transform_parsed_ui_for_walker', 'detect_ui_file', 'detect_server_file']
