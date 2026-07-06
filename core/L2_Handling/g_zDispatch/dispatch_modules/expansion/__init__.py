# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/expansion/__init__.py

"""
Shorthand Expansion for zDispatch Subsystem.

This package provides shorthand expansion logic that transforms compact
UI notation into full zDisplay event dictionaries.

Components:
    - ShorthandExpander: Main expansion orchestrator (core)
    - UIElementExpander: UI element shorthand (zText, zImage, zTable, etc.)
    - PluralExpander: Plural to singular transformation (zImages → zImage)
    - OrganizationalExpander: Layout structures (zRow, zCol, zCard, etc.)

Examples:
    zText: "Hello" → {"zDisplay": {"event": "text", "content": "Hello"}}
    zImages: [...] → {"zImage": item1}, {"zImage": item2}, ...
"""

from .expander_plurals import PluralExpander
from .expander_organizational import OrganizationalHandler
from .shorthand_element_expanders import ShorthandElementExpanders

__all__ = ['PluralExpander', 'OrganizationalHandler', 'ShorthandElementExpanders']
