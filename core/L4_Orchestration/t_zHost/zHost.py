"""zHost facade — the single entrypoint for control-plane operations.

Composed from small single-responsibility mixins in ``zHost_modules``:

  * FrontDoorMixin  — resolve a visitor to a reachable app URL (wake-and-hand-off)
  * InstancesMixin  — wake / sleep / inspect one app instance

The concrete engine (drivers, fleet swap, deploy) currently still lives in the
``zos_plugin`` SDK; zHost is the framework-side owner that reaches for it. The
physical relocation of that engine out of the SDK is the first task of the
zHost build phase (see memos/Development/ZHOST_EXTRACTION.notes.md).
"""

from .zHost_modules.frontdoor import FrontDoorMixin
from .zHost_modules.instances import InstancesMixin


class zHost(FrontDoorMixin, InstancesMixin):
    """Control plane: run many apps, front their traffic, ship new versions."""

    def __init__(self, zos):
        self.zos = zos
