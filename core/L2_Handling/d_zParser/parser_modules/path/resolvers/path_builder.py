# zOS/core/L2_Handling/g_zParser/parser_modules/path/resolvers/path_builder.py

"""
Path building utilities for path package.

Provides safe path joining and construction helpers.

Public API:
    - build_path: Safe path joining with normalization
    - build_zvafile_path: Build zVaFile path

Dependencies:
    - os: Path operations

Created: Phase 3.1 - Extract Resolvers from parser_path.py
"""

from zOS import os


def build_path(*parts: str) -> str:
    """
    Safe path joining with normalization.
    
    Joins path components with OS-specific separators and normalizes the result.
    
    Args:
        *parts: Path components to join
    
    Returns:
        str: Joined and normalized path
    
    Examples:
        >>> build_path('app', 'config', 'data')
        'app/config/data'
        
        >>> build_path('/etc', 'config')
        '/etc/config'
    
    Notes:
        - Uses os.path.join for OS-specific separators
        - Normalizes result path
        - Handles empty parts gracefully
    """
    return os.path.normpath(os.path.join(*parts))


def build_zvafile_path(base_path: str, filename: str) -> str:
    """
    Build zVaFile path from base and filename.
    
    Joins base directory path with zVaFile filename.
    
    Args:
        base_path: Base directory path
        filename: zVaFile filename
    
    Returns:
        str: Complete zVaFile path (without extension)
    
    Examples:
        >>> build_zvafile_path('/app/config', 'zUI.users')
        '/app/config/zUI.users'
        
        >>> build_zvafile_path('/etc', 'zSchema.db')
        '/etc/zSchema.db'
    
    Notes:
        - Uses os.path.join for OS-specific separators
        - Does not add file extension
        - Caller responsible for extension resolution
    """
    return os.path.join(base_path, filename)
