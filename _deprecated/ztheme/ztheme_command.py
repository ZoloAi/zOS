# zSys/cli/ztheme_command.py
"""
zTheme build command.
"""
from pathlib import Path


def handle_ztheme_command(boot_logger, verbose: bool = False):
    """
    Handle ztheme build command.

    Args:
        boot_logger: BootstrapLogger instance
        verbose: If True, show detailed build output
    """
    # Import the build function from zTheme/build.py
    import sys
    from importlib import import_module
    
    # Get the zOS root directory (go up from core/zSys/cli to zOS root)
    zos_root = Path(__file__).parent.parent.parent.parent
    ztheme_dir = zos_root / 'zTheme'
    
    if not ztheme_dir.exists():
        boot_logger.error(f"❌ zTheme directory not found at: {ztheme_dir}")
        return 1
    
    # Add zTheme directory to sys.path temporarily
    sys.path.insert(0, str(ztheme_dir))
    
    try:
        # Import and run the build function
        build_module = import_module('build')
        if verbose:
            boot_logger.info("Building zTheme CSS framework...")
        
        build_module.build_ztheme()
        
        if verbose:
            boot_logger.info("✨ zTheme build complete!")
        
        return 0
        
    except Exception as e:
        boot_logger.error(f"❌ Build failed: {e}")
        if verbose:
            import traceback
            boot_logger.error(traceback.format_exc())
        return 1
        
    finally:
        # Clean up sys.path
        if str(ztheme_dir) in sys.path:
            sys.path.remove(str(ztheme_dir))
