# zOS/core/L2_Core/g_zParser/parser_modules/parser_plugin.py

"""
BACKWARD COMPATIBILITY WRAPPER for parser_plugin.py

⚠️ This file is now a thin wrapper for backward compatibility.
The actual implementation has been refactored:

**Parsing Primitives (in zParser/plugin/):**
    - plugin_detection.py: Quick syntax detection (is_plugin_invocation)
    - plugin_syntax.py: Regex parsing (parse_plugin_invocation)
    - plugin_args.py: Argument parsing (parse_plugin_arguments)

**Execution Logic (moved to zFunc):**
    - i_zFunc/plugin_loader.py: Module loading and caching
    - i_zFunc/plugin_executor.py: Function execution with async
    - i_zFunc/plugin_resolver.py: Main orchestrator

**External Usage:**
    - zDispatch calls zParser.resolve_plugin_invocation()
    - zParser facade delegates to zFunc.execute_plugin()
    - zFunc imports parsing primitives from zParser

All function signatures remain stable for external compatibility.

Version History:
    - v1.6.0: Split primitives (zParser) from execution (zFunc), eliminated duplicates
    - v1.5.5: Split into modular structure
    - v1.5.4: Industry-grade upgrade

See Also:
    - plugin/ package: Parsing primitives
    - i_zFunc/zFunc_modules/plugin_*.py: Execution implementation
"""

# Re-export primitives only (resolve_plugin_invocation removed - now in zFunc)
from .plugin import (
    is_plugin_invocation,
    parse_plugin_invocation,
    parse_plugin_arguments,
)

__all__ = [
    'is_plugin_invocation',
    'parse_plugin_invocation',
    'parse_plugin_arguments',
]
