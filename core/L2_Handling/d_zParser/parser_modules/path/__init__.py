# zOS/core/L2_Handling/g_zParser/parser_modules/path/__init__.py

"""
Path resolution package for zParser subsystem.

Provides comprehensive path resolution, file identification, and zMachine path
handling. Refactored from monolithic parser_path.py into modular structure with
resolvers, detection, and extraction subdirectories.

Public API:
    - zPath_decoder: Main path resolver (CRITICAL - used by zLoader)
    - identify_zFile: File type identification (CRITICAL - used by zLoader)
    - resolve_zmachine_path: zMachine path resolution
    - resolve_symbol_path: Symbol-based path resolution (@, ~)

Architecture:
    - path_decoder.py: Main zPath_decoder implementation
    - file_identifier.py: File type identification
    - resolvers/: Symbol, zMachine, and path building
    - detection/: zVaFile, extension, and file validation
    - extraction/: Filename extraction and UI mode handling

External Usage (CRITICAL):
    - zLoader.py: Resolve file paths before loading UI/Schema/Config files
    - zShell/load_executor.py: Shell command path resolution

Signature Stability:
    - zPath_decoder(zSession, logger, zPath=None, zType=None, display=None)
    - identify_zFile(filename, full_zFilePath, logger, display=None)
    Must remain stable for external compatibility.

Created: Phase 4 - Refactor parser_path.py
"""

# Import from new modular structure (Phase 3 refactoring complete)
from .path_decoder import zPath_decoder
from .file_identifier import identify_zFile
from .resolvers import resolve_zmachine_path, resolve_symbol_path
from .detection import is_zvafile_type

__all__ = [
    'zPath_decoder',
    'identify_zFile',
    'resolve_zmachine_path',
    'resolve_symbol_path',
    'is_zvafile_type'
]
