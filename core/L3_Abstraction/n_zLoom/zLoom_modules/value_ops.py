# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/value_ops.py
"""zLoom VALUE ops — the scalar/token half of the binding grammar.

Thin, stateful surface over the pure token SSOT (``token_resolver``): a gate
value, a render string, and a WHERE clause all read zSession through the SAME
navigator, so their semantics cannot drift. Mixed into the ``zLoom`` facade.
"""

from zOS import Any

from .token_resolver import (
    deep_nav,
    resolve_token_value as _resolve_token_value,
    resolve_token_string as _resolve_token_string,
)


class ValueOps:
    """Value-half methods for zLoom (expects ``self.zos``)."""

    zos: Any

    def resolve_value(self, expr: Any, context: Any = None) -> Any:
        """Resolve a single ``%token`` to a scalar VALUE (or None on miss).

        The *value* half of zLoom — distinct from the data-binding half
        (``build_binding_block`` / ``resolve_block_data``) which yields row reads
        consumed as ``%data.<name>``. A gate (``zRBAC``) needs ONE value, not a
        row; missing → None (fail closed).
        """
        return _resolve_token_value(expr, self.zos, context)

    def resolve_token_string(self, value: Any, context: Any = None) -> str:
        """Interpolate every ``%token`` in a render string → resolved string.

        The zLoom render entry point (zParser delegates here). Shares the token
        SSOT with ``resolve_value`` and WHERE interpolation.
        """
        return _resolve_token_string(value, self.zos, context)

    def _zsession_path(self, dotted: Any) -> Any:
        """Deep-nav the live zSession dict by a dotted path → value or None.

        Thin wrapper over the token SSOT navigator (``deep_nav``) so WHERE-clause
        interpolation shares one navigator with render tokens and gate values.
        """
        return deep_nav(self.zos.session if hasattr(self.zos, "session") else None, dotted)
