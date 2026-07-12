# zOS/core/L3_Abstraction/n_zLoom/zLoom.py
"""
zLoom — the data-binding subsystem (Layer 3), sibling of zData.

zLoom owns the binding grammar; zData runs the query. Where zData is "execute
this read/write against a backend", zLoom is "resolve what a block declares it
needs" — named reads declared in `zLoom/spools/` and opted into via
`zMeta.zSpool: [name]` + `%data.<name>` (the ONE declared-source mechanism),
`%token` value/render resolution, `zList` loop expansion, and zPattern component
(structure) expansion.

Facade shape (Phase 3): the public surface is composed from single-responsibility
mixins, one file per concern, all sharing ``self.zos``:

    ValueOps      value_ops.py       — %token resolution (render + gates + WHERE)
    QueryOps      query_ops.py       — build + execute a block's declared reads
    BindingOps    binding_ops.py     — zLoom/ registry + binding assembly
    LoopOps       loop_ops.py        — zList loop expansion
    StructureOps  structure_ops.py   — zPattern component (structure) expansion
    RouteOps      route_ops.py       — dynamic-route params store (%route.*), fed by zServer
    KnotOps       knot_ops.py        — zKnot computed-value collapse ({{ a+b }} / ternary)

Pure engines behind the mixins: ``token_resolver`` (value SSOT),
``component_expand`` (structure SSOT), and ``knot_eval`` (computed-value SSOT).

Layering note: L2 consumers (zParser render, zDisplay, zDispatch, zNavigation,
zAuth gates) and L4 (zServer routes) call into ``zos.zloom`` via the runtime
``zos`` handle (a runtime attribute access, NOT an import), so there is no
import-time layer inversion.
"""


__version__ = "1.0.0"
from zOS import Any

from .zLoom_modules.value_ops import ValueOps
from .zLoom_modules.query_ops import QueryOps
from .zLoom_modules.binding_ops import BindingOps
from .zLoom_modules.loop_ops import LoopOps
from .zLoom_modules.structure_ops import StructureOps
from .zLoom_modules.route_ops import RouteOps
from .zLoom_modules.knot_ops import KnotOps


class zLoom(ValueOps, QueryOps, BindingOps, LoopOps, StructureOps, RouteOps, KnotOps):  # noqa: N801 — subsystem facade
    """Public zLoom facade — composes the value/query/binding/loop/structure/route/knot
    ops into one object, attached at boot as ``zos.zloom``."""

    def __init__(self, zos: Any) -> None:
        self.zos = zos
