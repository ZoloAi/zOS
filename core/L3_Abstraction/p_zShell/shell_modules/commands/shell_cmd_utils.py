# zOS/core/L3_Abstraction/p_zShell/shell_modules/commands/shell_cmd_utils.py

"""
Utility command execution for zCLI (DEPRECATED and REMOVED).

⚠️ REMOVED in v1.7.0 ⚠️

This command has been REMOVED. Plugin functionality migrated to zLoader.

**Migration Guide**:
    OLD: utils hash_password mypass
    NEW: Use zFunc directly: z.zfunc.handle("&plugin.function(args)")
    OR: Use Python API: z.loader.get_plugin("plugin").function(args)

Plugin loading now happens via zLoader:
    - Boot-time: zSpark["plugins"] = ["/path/to/plugin.py"]
    - Runtime: z.loader.load_plugins(["/path/to/plugin.py"])
    - Access: z.loader.get_plugin("plugin_name")
"""

from zOS import Any, Dict

# Error message
ERROR_REMOVED: str = (
    "⚠️  COMMAND REMOVED: The 'utils' command has been removed in v1.7.0.\n"
    "   Plugin functionality migrated to zLoader.\n\n"
    "   Use zFunc for plugin execution:\n"
    "   • zfunc &plugin.function(args)\n\n"
    "   Or use Python API:\n"
    "   • plugin = z.loader.get_plugin('plugin_name')\n"
    "   • plugin.function(args)"
)


def execute_utils(zos: Any, parsed: Dict[str, Any]) -> None:
    """
    Execute utility commands (REMOVED - shows migration message).

    This function displays a removal message explaining how to use the new
    zLoader-based plugin system.

    Parameters
    ----------
    zos : Any
        zCLI instance
    parsed : Dict[str, Any]
        Parsed command dictionary (ignored)

    Returns
    -------
    None
        Displays error message via zDisplay
    """
    zos.display.error(ERROR_REMOVED)
