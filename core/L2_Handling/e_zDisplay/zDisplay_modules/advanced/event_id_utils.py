# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/e_advanced/event_id_utils.py

"""
Event ID Generator Utility for Time-Based Widgets
==================================================

Pure utility function for generating unique event IDs for time-based display
events (progress bars, spinners, swipers).

Moved from a_infrastructure to e_advanced as it's only used by time-based
widgets in this tier.
"""

import uuid


def generate_event_id(prefix: str, label: str) -> str:
    """
    Generate a unique event ID using a prefix, sanitized label, and short UUID.
    
    Creates human-readable but globally unique IDs for tracking active display
    events (progress bars, spinners, swipers) in Bifrost mode.
    
    Args:
        prefix: Short string indicating event type (e.g., "progress", "spinner", "swiper")
        label: Human-readable label for the event
    
    Returns:
        str: Unique event ID (e.g., "spinner_Loading_Data_1a2b3c4d")
    
    Format:
        {prefix}_{sanitized_label}_{uuid8}
        - prefix: Event type identifier
        - sanitized_label: Label with spaces replaced by underscores
        - uuid8: First 8 chars of UUID4 (collision-resistant)
    
    Examples:
        >>> generate_event_id("progress", "Processing Files")
        "progress_Processing_Files_7f3a2b1c"
        
        >>> generate_event_id("spinner", "Loading Data")
        "spinner_Loading_Data_9d4e5f6a"
    """
    sanitized_label = label.replace(' ', '_')
    return f"{prefix}_{sanitized_label}_{str(uuid.uuid4())[:8]}"
