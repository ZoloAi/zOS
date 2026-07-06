# zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/utils/confirm_gate.py

"""
Confirm Gate — SSOT y/n action gate for zCLI events
===================================================

One function for every "show the affordance, then ask y/n before acting"
pattern in zCLI: zButton, zLink, zImage/zVideo/zAudio open prompts, and the
zTerminal Run gate. Each event passes a ``kind`` key (baked into its own logic)
and a label; this helper looks up the prompt in ``CONFIRM_TEMPLATES`` (the
message SSOT), colours it, reads a validated y/n, and returns a plain bool.

zFlat
-----
``confirm_gate`` is zFlat-aware. When a host (zSwiper slide, zTable cell, future
print/export) sets ``session["_zflat"]``, the gate renders the visual affordance
inertly and returns ``False`` instead of blocking on input. This means any event
that routes its confirmation through here gets correct passive-render behaviour
for free — no per-event zFlat wrapper required.

Why one place
-------------
- DRY/SSOT: prompt wording lives in ``CONFIRM_TEMPLATES``; loop/colour/zFlat
  logic lives here. Adding a gated event is one template key + one call.
- Message control: tweak any prompt in one spot.
- Simpler zFlat: a single inert-render decision, not N hand-rolled branches.
"""

from typing import Any, Optional

from ..display_constants import CONFIRM_TEMPLATES
from ..basic.outputs.rendering_utilities import wrap_with_color

_ACCEPT = ("y", "yes")
_VALID = ("y", "yes", "n", "no", "")


def is_flat(display: Any) -> bool:
    """True when the current render is passive (zFlat). Never raises.

    Public so events with their own decline/"cancelled" feedback (zImage's
    cancel line, zTerminal's "Run cancelled") can suppress it under zFlat —
    confirm_gate already renders the inert affordance, so a second decline
    message would be noise in a passive render.
    """
    try:
        return bool(display.zos.session.get("_zflat"))
    except Exception:  # noqa: BLE001 — a probe must never break rendering
        return False


def confirm_gate(
    display: Any,
    kind: str = "default",
    label: str = "",
    color: str = "INFO",
    flat_text: Optional[str] = None,
    **fmt: Any,
) -> bool:
    """Render a y/n action gate and return the operator's decision.

    Args:
        display: zDisplay instance (provides zPrimitives, zColors, zos, error).
        kind: Key into ``CONFIRM_TEMPLATES`` selecting the prompt wording.
        label: Subject of the prompt (button text, link label, "image file"...).
        color: Semantic colour name for the prompt (PRIMARY, INFO, ...).
        flat_text: Optional inert line to print under zFlat instead of the
            default ``[ label ]`` (e.g. links pass ``"label → href"``).
        **fmt: Extra format fields for templates that need them.

    Returns:
        True only on an explicit ``y``/``yes``. Empty, ``n``/``no``, a read
        failure, or zFlat all return False (decline / inert).
    """
    template = CONFIRM_TEMPLATES.get(kind) or CONFIRM_TEMPLATES["default"]
    try:
        prompt_text = template.format(label=label, **fmt)
    except Exception:  # noqa: BLE001 — bad/missing field => degrade gracefully
        prompt_text = template

    # zFlat: show the affordance, skip the blocking prompt, decline.
    if is_flat(display):
        inert = flat_text if flat_text is not None else (
            f"[ {label} ]" if label else prompt_text.rstrip()
        )
        try:
            display.zPrimitives.line(inert)
        except Exception:  # noqa: BLE001
            pass
        return False

    colored = wrap_with_color(prompt_text, color, getattr(display, "zColors", None))

    while True:
        try:
            response = display.zPrimitives.read_string(colored).strip().lower()
        except (KeyboardInterrupt, EOFError):
            return False
        except Exception:  # noqa: BLE001 — treat read failure as decline
            return False

        if response in _VALID:
            return response in _ACCEPT

        err = getattr(display, "error", None)
        if callable(err):
            try:
                err("Invalid input — please enter 'y' or 'n'.")
            except Exception:  # noqa: BLE001
                pass
        else:
            try:
                display.zPrimitives.line("  Invalid input — please enter 'y' or 'n'.")
            except Exception:  # noqa: BLE001
                pass
