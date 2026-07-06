# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/d_compounds/__init__.py

"""
d_compounds - Compound Display Operations
==========================================

This tier provides compound display operations built on top of c_basic.

Architecture:
    - Facade: CompoundsInputs (inputs facade) - unified input interface
    - Facade: CompoundsOutputs (outputs facade) - unified output interface
    - Events: display_event_*.py - event implementations in respective folders
    - Helpers: inputs/*.py, outputs/*.py - specialized helper modules

Compound Operations:
    - Interactive widgets (selection menus, sliders)
    - Structured data display (lists with recursive rendering)
    - Link handling and navigation
    - Media display operations

Dependencies:
    - c_basic: BasicInputs, BasicOutputs (foundation)
    - b_primitives: PrimitivesInputs, PrimitivesOutputs (I/O)
"""

from .display_compounds_inputs import CompoundsInputs
from .display_compounds_outputs import CompoundsOutputs

__all__ = [
    'CompoundsInputs',
    'CompoundsOutputs',
]
