# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/structure_ops.py
"""zLoom STRUCTURE ops — load-time structural transforms.

The key-position ``%`` half of the sigil, plus its loop companion:
    • ``expand_components`` — reusable zUI structures with named slots (zPattern).
    • ``expand_shuttles``   — lower ``zShuttle`` (the ``{% for %}`` loop) to the
      proven ``zList`` + ``%pattern`` form, with slot auto-fill.
Both run at the loader post-parse seam; both idempotent + render-token-safe. The
engines live in ``component_expand`` / ``shuttle_expand``; this mixin is the facade.
"""

from zOS import Any

from .component_expand import expand_components as _expand_components
from .shuttle_expand import expand_shuttles as _expand_shuttles


class StructureOps:
    """zPattern + zShuttle structural transforms for zLoom (expects ``self.zos``)."""

    zos: Any

    def expand_shuttles(self, tree: Any, registry: Any = None) -> Any:
        """Lower ``zShuttle`` loops to ``zList`` + a ``%pattern`` invocation (with
        slot auto-fill). MUST run BEFORE ``expand_components`` so the emitted
        ``%pattern`` is then expanded. Idempotent + a no-op when no shuttle present.
        """
        return _expand_shuttles(tree, self.zos, registry)

    def expand_components(self, tree: Any, registry: Any = None) -> Any:
        """Expand zPattern ``%<component>`` invocations in a parsed zVaFile (structure
        SSOT). Invoked by the loader post-parse seam; idempotent + render-safe.
        ``registry`` is optional (injected for tests); else loaded from zLoom/patterns/.
        """
        return _expand_components(tree, self.zos, registry)
