# zOS/core/L1_Foundation/a_zConfig/__init__.py
"""
zConfig - Cross-platform configuration management subsystem.

Provides hierarchical configuration loading, machine/environment detection,
session management, and logging infrastructure for the zOS framework.

Key Responsibilities:
    - Hierarchical config loading with zSpark overrides (machine/env/session)
    - Cross-platform path resolution and storage path management
    - Auto-detection of machine characteristics (OS, browser, IDE, memory, CPU)
    - Environment configuration (deployment, logging, networking, security)
    - Session lifecycle management (session ID, workspace, runtime state)
    - Logger configuration and zTraceback initialization
    - Resource limits (CPU and memory) enforcement
    - WebSocket and HTTP server configuration
    - Bootstrap system assets (system UI + migration schema) and user dirs
    - Configuration persistence for machine/environment overrides

Exports:
    zConfig: Main configuration management class
"""

from .zConfig import zConfig

__all__ = ['zConfig']
