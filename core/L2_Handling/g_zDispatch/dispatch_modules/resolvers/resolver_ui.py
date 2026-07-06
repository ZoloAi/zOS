# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/resolvers/resolver_ui.py

"""
UI Key Resolver for zDispatch Subsystem.

This module provides the UIResolver class, which resolves plain string keys
to their corresponding values in zUI files during Bifrost mode execution.

Extracted from dispatch_launcher.py as part of Phase 2 refactoring.

Functionality:
    - Resolves plain string keys from zUI block dictionaries
    - Enables recursive command resolution (key → dict → execution)
    - Falls back to message display if resolution fails
    - Bifrost mode only (zCLI mode doesn't use this)

Usage Example:
    resolver = UIResolver(zos, logger)
    
    # Resolve plain string key in Bifrost mode
    result = resolver.resolve(
        "my_button",
        launch_callback=launcher.launch,
        context={"mode": "zBifrost"},
        walker=None
    )

Integration:
    - zLoader: Loads zUI files via zos.loader.handle()
    - zConfig: Reads zVaFile and zBlock from zspark_obj
    - CommandLauncher: Calls back to launch() for recursive execution

Thread Safety:
    - Stateless operations (no instance state mutation)
    - Safe for concurrent execution
"""

from zOS import Any, Optional, Dict, Union

# Import dispatch constants
from ..dispatch_constants import (
    KEY_ZVAFILE,
    KEY_ZBLOCK,
    KEY_MESSAGE,
    MODE_BIFROST,
    _DEFAULT_ZBLOCK,
)


class UIResolver:
    """
    Resolves plain string keys to zUI block values in Bifrost mode.
    
    This resolver enables dynamic UI resolution where plain string keys
    are looked up in the current zUI file's block dictionary and recursively
    executed if they contain commands.
    
    Attributes:
        zos: zOS framework instance (provides loader, zspark_obj)
        logger: Logger instance for debug output
    
    Methods:
        resolve(): Main entry point for UI key resolution
    
    Example:
        resolver = UIResolver(zos, logger)
        result = resolver.resolve("save_button", launcher.launch, context, walker)
    """

    def __init__(self, zos: Any, logger: Any) -> None:
        """
        Initialize UI resolver.
        
        Args:
            zos: zOS framework instance (provides loader, zspark_obj)
            logger: Logger instance for debug output
        
        Example:
            resolver = UIResolver(zos, logger)
        """
        self.zos = zos
        self.logger = logger

    def resolve(
        self,
        key: str,
        launch_callback: Any,
        context: Optional[Dict[str, Any]],
        walker: Optional[Any]
    ) -> Union[Dict[str, Any], Any]:
        """
        Resolve plain string key in Bifrost mode (attempts zUI resolution).
        
        Args:
            key: Plain string key to resolve
            launch_callback: Callback to launcher.launch() for recursive execution
            context: Context dict
            walker: Optional walker instance
        
        Returns:
            Resolved value (recursively launched) or {"message": str}
        
        Notes:
            - Attempts to resolve key from current zUI block
            - Recursively launches resolved value (could be dict with zFunc)
            - Falls back to {"message": str} if resolution fails
            - Error handling for missing zUI context
        
        Examples:
            # Successful resolution
            result = resolver.resolve("my_button", launcher.launch, context, walker)
            # If my_button → {"zFunc": "save"}, executes save function
            
            # Failed resolution
            result = resolver.resolve("unknown_key", launcher.launch, context, walker)
            # Returns {"message": "unknown_key"}
        """
        zVaFile = self.zos.zspark_obj.get(KEY_ZVAFILE)
        zBlock = self.zos.zspark_obj.get(KEY_ZBLOCK, _DEFAULT_ZBLOCK)

        if zVaFile and zBlock:
            try:
                raw_zFile = self.zos.loader.handle(zVaFile)
                if raw_zFile and zBlock in raw_zFile:
                    block_dict = raw_zFile[zBlock]

                    # Look up the key in the block
                    if key in block_dict:
                        resolved_value = block_dict[key]
                        self.logger.framework.debug(
                            f"[{MODE_BIFROST}] Resolved key '{key}' from zUI to: {resolved_value}"
                        )
                        # Recursively launch with the resolved value
                        return launch_callback(resolved_value, context=context, walker=walker)
                    else:
                        self.logger.framework.debug(
                            f"[{MODE_BIFROST}] Key '{key}' not found in zUI block '{zBlock}'"
                        )
            except Exception as e:
                self.logger.warning(f"[{MODE_BIFROST}] Error resolving key from zUI: {e}")

        # If we couldn't resolve it, return as display message
        self.logger.framework.debug(f"Plain string in {MODE_BIFROST} mode - returning as message")
        return {KEY_MESSAGE: key}
