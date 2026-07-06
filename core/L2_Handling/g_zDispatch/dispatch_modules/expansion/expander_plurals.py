# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/expansion/expander_plurals.py

"""
Plural Shorthand Expander for zDispatch Subsystem.

Expands plural shorthand keys (zBtns, zURLs, zTexts, zImages, etc.) into
implicit wizard structures where each named item becomes a wizard step.

Behavior:
  - Each item in the plural block expands to {zDisplay: {event: ..., ...}}
  - Defaults from PLURAL_REGISTRY are applied (item values win over defaults)
  - _zClass INSIDE the plural block is shared across all items that don't
    have their own _zClass (non-overwriting propagation)

SSOT: PLURAL_REGISTRY / PLURAL_HEADER_REGISTRY in dispatch_constants.py
"""

from zOS import Any, Dict, Optional, Tuple

from ..dispatch_constants import (
    KEY_ZDISPLAY,
    PLURAL_REGISTRY,
    PLURAL_HEADER_REGISTRY,
    PLURAL_SHORTHAND_KEYS,
)


class PluralExpander:
    """
    Expands plural shorthand keys into wizard-style navigation.

    Attributes:
        logger: Logger instance for debug output
    """

    # Derived from SSOT — do not edit directly
    PLURAL_SHORTHANDS = list(PLURAL_SHORTHAND_KEYS)

    def __init__(self, logger: Any) -> None:
        self.logger = logger

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def expand(self, zHorizontal: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Expand plural shorthands (zBtns, zURLs, zTexts, etc.) to implicit wizards.

        Plural format:
            zBtns:
                _zClass: zRounded-circle    # shared, non-overwriting
                Submit:
                    label: Submit
                    color: primary

        Expands to:
            {Submit: {zDisplay: {event: 'button', color: 'primary', _zClass: 'zRounded-circle'}}}

        Returns:
            (expanded_dict, expansion_occurred)
        """
        found_plural = None
        for plural_key in PLURAL_SHORTHAND_KEYS:
            if plural_key in zHorizontal and isinstance(zHorizontal[plural_key], dict):
                found_plural = plural_key
                break

        if not found_plural:
            return zHorizontal, False

        self.logger.debug(f"[PluralExpander] Expanding {found_plural}")

        plural_items = zHorizontal[found_plural]
        shared_class = plural_items.get('_zClass')  # shared class INSIDE the plural block

        singular_event = self._get_singular_event(found_plural)
        if not singular_event:
            return zHorizontal, False

        defaults = PLURAL_REGISTRY.get(found_plural, {}).get('defaults', {})

        expanded_wizard: Dict[str, Any] = {}
        for item_key, item_params in plural_items.items():
            if item_key.startswith('_') or not isinstance(item_params, dict):
                continue  # skip metadata keys (_zClass, _zStyle, etc.)

            merged = {**defaults, **item_params}  # item values win over defaults

            if isinstance(singular_event, tuple):
                event_type, indent = singular_event
                expanded_wizard[item_key] = {
                    KEY_ZDISPLAY: {'event': event_type, 'indent': indent, **merged}
                }
            else:
                expanded_wizard[item_key] = {KEY_ZDISPLAY: {'event': singular_event, **merged}}

        if not expanded_wizard:
            return zHorizontal, False

        # Propagate shared _zClass — only to items that don't have their own
        if shared_class:
            for item_value in expanded_wizard.values():
                if KEY_ZDISPLAY in item_value and '_zClass' not in item_value[KEY_ZDISPLAY]:
                    item_value[KEY_ZDISPLAY]['_zClass'] = shared_class

        self.logger.debug(f"[PluralExpander] Expanded {found_plural} → {len(expanded_wizard)} steps")
        return expanded_wizard, True

    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================

    def _get_singular_event(self, plural_key: str) -> Optional[Any]:
        """
        Return event string or (event, indent) tuple from SSOT registries.

        Examples:
            'zBtns'  → 'button'
            'zURLs'  → 'zURL'
            'zH1s'   → ('header', 1)
        """
        if plural_key in PLURAL_REGISTRY:
            return PLURAL_REGISTRY[plural_key]['event']
        if plural_key in PLURAL_HEADER_REGISTRY:
            return ('header', PLURAL_HEADER_REGISTRY[plural_key])
        return None
