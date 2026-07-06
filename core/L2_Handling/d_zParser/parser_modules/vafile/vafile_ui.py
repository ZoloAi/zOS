# zOS/core/L2_Core/g_zParser/parser_modules/vafile/vafile_ui.py

"""
BACKWARD COMPATIBILITY WRAPPER for vafile_ui.py

⚠️ This file is now a thin wrapper for backward compatibility.
The actual implementation has been split into modular files:
    - ui/ui_parser.py: Main parse_ui_file function (~175 LOC)
    - ui/ui_zblock_processor.py: zBlock processing (~265 LOC)
    - ui/ui_validator.py: Structure validation (~260 LOC)
    - ui/ui_construct_validators.py: Construct validation (~235 LOC)

External Usage (CRITICAL):
    - parser_file.py: Uses parse_ui_file for UI parsing

Function signatures remain stable for external compatibility.

Refactoring completed: Phase 5 - vafile_ui.py split
    - 847 LOC → 4 focused modules (< 270 LOC each)
    - Validator: validate_ui_structure, validate_schema_structure
    - Construct Validators: 6 UI primitive validators
    - zBlock Processor: parse_ui_zblock, parse_ui_item, identify_ui_construct
    - Parser: parse_ui_file (main orchestrator)

Version History:
    - v1.5.4 Week 3.3: RBAC integration
    - v1.5.5 Phase 5: Split into modular structure (this wrapper created)

See Also:
    - ui/ package: New modular implementation
"""

# Re-export from new modular structure for backward compatibility
from .ui import parse_ui_file, validate_ui_structure, validate_schema_structure

__all__ = ['parse_ui_file', 'validate_ui_structure', 'validate_schema_structure']
