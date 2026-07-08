# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/utils/launcher_utils.py

"""
Launcher Utility Functions
===========================

Helper functions extracted from dispatch_launcher.py to reduce file size.
Provides content unwrapping, data resolution, and shorthand expansion utilities.
"""

from zOS import Any, Optional, Dict


def unwrap_content_wrapper(zHorizontal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Unwrap single-key 'content' wrapper if present.
    
    Args:
        zHorizontal: Dict command
    
    Returns:
        Unwrapped dict if wrapper detected, None otherwise
    
    Example:
        Input: {"content": {"zFunc": "test"}}
        Output: {"zFunc": "test"}
    """
    if len(zHorizontal) == 1 and 'content' in zHorizontal:
        content_value = zHorizontal['content']
        if isinstance(content_value, dict):
            return content_value
    return None


def expand_nested_shorthands(params: Dict[str, Any]) -> Dict[str, Any]:
    """Expand nested shorthand keys (zL, zT, zH1-6) in items list.
    
    Args:
        params: Dict with 'items' key containing list
    
    Returns:
        Dict with expanded items
    
    Example:
        Input: {"items": [{"zL": "text"}]}
        Output: {"items": [{"zDisplay": {"event": "text", "content": "text"}}]}
    """
    from ..dispatch_constants import KEY_ZDISPLAY

    if 'items' not in params or not isinstance(params.get('items'), list):
        return params

    expanded_items = []
    for item in params['items']:
        if isinstance(item, dict) and len(item) == 1:
            shorthand_key = next(iter(item))
            shorthand_value = item[shorthand_key]

            if shorthand_key == 'zL':
                if isinstance(shorthand_value, str):
                    expanded_items.append({KEY_ZDISPLAY: {'event': 'text', 'content': shorthand_value}})
                elif isinstance(shorthand_value, dict):
                    expanded_items.append({KEY_ZDISPLAY: {'event': 'text', **shorthand_value}})
            elif shorthand_key == 'zT':
                if isinstance(shorthand_value, str):
                    expanded_items.append({KEY_ZDISPLAY: {'event': 'header', 'label': shorthand_value}})
                elif isinstance(shorthand_value, dict):
                    expanded_items.append({KEY_ZDISPLAY: {'event': 'header', **shorthand_value}})
            elif shorthand_key.startswith('zH') and len(shorthand_key) == 3 and shorthand_key[2].isdigit():
                indent_level = int(shorthand_key[2])
                if 1 <= indent_level <= 6:
                    if isinstance(shorthand_value, str):
                        expanded_items.append({
                            KEY_ZDISPLAY: {'event': 'header', 'indent': indent_level, 'label': shorthand_value}
                        })
                    elif isinstance(shorthand_value, dict):
                        expanded_items.append({
                            KEY_ZDISPLAY: {'event': 'header', 'indent': indent_level, **shorthand_value}
                        })
            else:
                expanded_items.append(item)
        else:
            expanded_items.append(item)

    return {**params, 'items': expanded_items}


def check_walker(walker: Optional[Any], command_name: str, logger: Any) -> bool:
    """Check if walker instance is available for command execution.
    
    Args:
        walker: Optional walker instance
        command_name: Name of command requiring walker
        logger: Logger instance
    
    Returns:
        bool: True if walker available, False otherwise (logs warning)
    """
    if not walker:
        logger.warning(f"{command_name} requires walker instance (not available)")
        return False
    return True


def set_default_action(req: Dict[str, Any], default_action: str) -> None:
    """Set default action in request dict if not specified.
    
    Args:
        req: Request dict (modified in place)
        default_action: Default action value (e.g., "read")
    """
    if 'action' not in req:
        req['action'] = default_action
