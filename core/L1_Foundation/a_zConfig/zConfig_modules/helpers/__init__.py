# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/__init__.py
"""
Helper modules for zConfig functionality.

This package provides utility functions that support zConfig's hierarchical configuration system:

1. **detectors/** - Auto-detection of machine capabilities and user preferences
   - Organized by category: browser, IDE, media apps, hardware, system
   - Creates machine-specific configuration files with detected values
   - Provides fallback detection for cross-platform compatibility

2. **environment_helpers.py** - Environment configuration management
   - Creates default environment config files (deployment, network, security, logging)
   - Provides templates for environment-specific settings
   - Supports deployment profiles (Debug, Info, Production)

3. **config_helpers.py** - Generic configuration loading and override patterns
   - Loads YAML config files with hierarchical override behavior
   - Creates config files on first run if missing
   - Provides consistent file loading across all config modules

These helpers separate detection/creation logic from configuration data management,
enabling clean architecture, testability, and reusability across zConfig subsystems.
"""

from .config_helpers import (
    ensure_user_directories,
    ensure_app_directory,
    initialize_system_ui,
    load_config_with_override,
    slugify_app_id,
    resolve_app_id,
)

__all__ = [
    "ensure_user_directories",
    "ensure_app_directory",
    "initialize_system_ui",
    "load_config_with_override",
    "slugify_app_id",
    "resolve_app_id",
]
