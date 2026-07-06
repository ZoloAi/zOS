# zOS/core/L2_Handling/d_zParser/parser_modules/plugin/__init__.py

"""
Plugin parsing primitives for zParser subsystem.

Provides stateless parsing primitives for plugin invocation syntax.
Execution logic is delegated to zFunc (i_zFunc) subsystem.

Architectural Separation
------------------------
**zParser (this package)**: Syntax detection and parsing primitives (SSOT)
**zFunc (i_zFunc)**: Discovery, loading, execution, orchestration

Public API (Primitives Only)
-----------------------------
- is_plugin_invocation: Detect plugin syntax (&Plugin.function)
- parse_plugin_invocation: Parse syntax into (plugin_name, function_name, args_str)
- parse_plugin_arguments: Parse argument string to (args, kwargs)

External Usage
--------------
The zParser facade method `resolve_plugin_invocation()` delegates to zFunc for execution:
    zParser.resolve_plugin_invocation() → zFunc.execute_plugin()

This package provides only the parsing primitives that zFunc imports.

Module Structure
----------------
- plugin_detection.py: Syntax detection (is_plugin_invocation)
- plugin_syntax.py: Regex parsing (parse_plugin_invocation)
- plugin_args.py: Argument parsing (parse_plugin_arguments)

Version History
---------------
- v1.6.0: Refactored to primitives-only, execution moved to zFunc
- v1.5.5: Full implementation including discovery/execution
- v1.5.4: Created by splitting parser_plugin.py
"""

# Import parsing primitives only
from .plugin_detection import is_plugin_invocation
from .plugin_syntax import parse_plugin_invocation
from .plugin_args import parse_plugin_arguments

__all__ = [
    'is_plugin_invocation',
    'parse_plugin_invocation',
    'parse_plugin_arguments',
]
