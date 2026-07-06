# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/display_events.py

"""
zEvents - Event Orchestrator for zDisplay Subsystem
===================================================

Orchestrates 10 event packages with cross-reference wiring and provides
convenience delegate methods via multiple inheritance.

Architecture:
- Package initialization and cross-reference wiring
- Convenience delegates via OutputSignalDelegates + WidgetMediaDelegates mixins
- Layer 2 orchestrator composing specialized event packages

Event Packages:
1. BasicOutputs - Formatted output (header, text)
2. BasicInputs - User input collection
3. InteractiveInputs - Interactive widgets
4. CompoundData - Structured lists
5. AdvancedData - Complex data (zTable)
6. AdvancedOutputs - Rich text
7. zSystem - System UI (zDeclare, zCrumbs, zMenu, zDialog)
8. TimeBased - Progress/spinners
9. MediaEvents - Images/video/audio
10. LinkEvents - Semantic links

Convenience Delegates:
- Provided via multiple inheritance from OutputSignalDelegates + WidgetMediaDelegates
- Extracted to separate files to maintain <600 LOC limit
- See: delegates/delegate_outputs_signals.py, delegates/delegate_widgets_media.py
"""

from zOS import Any

from .basic.display_basic_outputs import BasicOutputs
from .basic.display_basic_inputs import BasicInputs
from .compounds.inputs.display_event_inputs import InteractiveInputs
from .compounds.outputs.display_event_data import CompoundData
from .compounds.outputs.display_event_media import MediaEvents
from .compounds.outputs.display_event_links import LinkEvents
from .advanced.display_event_advanced import AdvancedData
from .advanced.display_event_outputs import AdvancedOutputs
from .advanced.display_event_timebased import TimeBased
from .system.display_event_system import zSystem
from .delegates import OutputSignalDelegates, WidgetMediaDelegates


class zEvents(OutputSignalDelegates, WidgetMediaDelegates):
    """Event orchestrator with cross-referenced packages and delegated convenience methods.
    
    Architecture:
        - Composition: Instantiates 10 specialized event packages
        - Cross-Reference: Wires packages for inter-dependencies
        - Delegation: Inherits convenience methods from mixin classes
    
    Event Packages:
        - BasicOutputs: Foundation output methods
        - BasicInputs: Basic input operations
        - InteractiveInputs: Interactive widgets
        - CompoundData: List display with recursion
        - AdvancedData: Table display with pagination
        - AdvancedOutputs: Rich text rendering
        - zSystem: System UI (zDeclare, zCrumbs, zMenu, zDialog)
        - TimeBased: Progress bars and spinners
        - MediaEvents: Media rendering (image, video, audio)
        - LinkEvents: Semantic link rendering
    
    Usage:
        # Direct package access
        events.BasicOutputs.header("Title")
        
        # Via inherited delegates (backward compatible)
        events.header("Title")
    """

    # Type hints for instance attributes
    display: Any
    BasicOutputs: Any
    BasicInputs: Any
    InteractiveInputs: Any
    CompoundData: Any
    AdvancedData: Any
    AdvancedOutputs: Any
    zSystem: Any
    TimeBased: Any
    MediaEvents: Any
    LinkEvents: Any

    def __init__(self, display_instance: Any) -> None:
        """Initialize event orchestrator with all packages and cross-references.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance

        # Initialize all 10 event packages
        self.BasicOutputs = BasicOutputs(display_instance)
        self.BasicInputs = BasicInputs(display_instance)
        self.InteractiveInputs = InteractiveInputs(display_instance)
        self.CompoundData = CompoundData(display_instance)
        self.AdvancedData = AdvancedData(display_instance)
        self.AdvancedOutputs = AdvancedOutputs(display_instance)
        self.zSystem = zSystem(display_instance)
        self.TimeBased = TimeBased(display_instance)
        self.MediaEvents = MediaEvents(display_instance)
        self.LinkEvents = LinkEvents(display_instance)

        # Wire cross-references (enable package composition)
        self.InteractiveInputs.BasicOutputs = self.BasicOutputs
        self.CompoundData.BasicOutputs = self.BasicOutputs
        self.AdvancedData.BasicOutputs = self.BasicOutputs
        self.zSystem.BasicOutputs = self.BasicOutputs
        self.zSystem.BasicInputs = self.BasicInputs
        self.zSystem.InteractiveInputs = self.InteractiveInputs
        self.zSystem._update_cross_references()
        self.TimeBased.BasicOutputs = self.BasicOutputs
        self.MediaEvents.BasicOutputs = self.BasicOutputs
        self.MediaEvents.InteractiveInputs = self.InteractiveInputs
        self.LinkEvents.BasicOutputs = self.BasicOutputs
        self.LinkEvents.InteractiveInputs = self.InteractiveInputs
