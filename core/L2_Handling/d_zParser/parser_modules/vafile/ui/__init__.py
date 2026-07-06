# zOS/core/L2_Handling/g_zParser/parser_modules/vafile/ui/__init__.py

"""
UI parsing package for vafile subsystem.

Provides comprehensive UI file parsing with RBAC and zBlock processing.

Package Structure:
    - ui_parser.py: Main parse_ui_file function (~140 LOC)
    - ui_zblock_processor.py: zBlock processing (~235 LOC)
    - ui_validator.py: Structure validation (~240 LOC)
    - ui_construct_validators.py: Construct validation (~235 LOC)

Public API:
    - parse_ui_file: Main UI file parser (CRITICAL - used by parser_file.py)
    - validate_ui_structure: UI structure validation
    - validate_schema_structure: Schema structure validation

External Usage:
    - parser_file.py: Uses parse_ui_file for UI parsing

Created: Phase 5 - Refactor vafile_ui.py
"""

from .ui_parser import parse_ui_file
from .ui_validator import validate_ui_structure, validate_schema_structure

__all__ = [
    'parse_ui_file',
    'validate_ui_structure',
    'validate_schema_structure'
]
