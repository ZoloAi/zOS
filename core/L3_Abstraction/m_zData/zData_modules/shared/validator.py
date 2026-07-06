# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validator.py
"""
Backward compatibility shim for validator module.

This module has been refactored into a modular package structure.
All functionality is now in the validators/ subdirectory:
- validators/constants.py: All constants
- validators/string_validator.py: Layer 1 - String validation
- validators/numeric_validator.py: Layer 2 - Numeric validation
- validators/pattern_validator.py: Layer 3 - Pattern validation
- validators/format_validator.py: Layer 4 - Format validation
- validators/plugin_validator.py: Layer 5 - Plugin validation
- validators/core.py: DataValidator orchestrator class

This shim maintains backward compatibility for existing imports.
"""

from .validators import DataValidator

__all__ = ["DataValidator"]
