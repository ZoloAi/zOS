# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/query_ops.py
"""zLoom QUERY ops — build + execute the reads a block declares.

Turns the three ``_data`` query forms (declarative dict, shorthand string,
explicit ``zData`` block) into zData requests, runs them silently, applies the
``fields`` whitelist, and returns a {name: value} map. Mixed into the ``zLoom``
facade; cross-calls ``self._zsession_path`` (ValueOps) for %session interpolation.
"""

from zOS import Any, Dict
# zPath grammar — Layer-0 SSOT for sigil/segment decomposition.
from zSys import zpath


class QueryOps:
    """Query build/execute methods for zLoom (expects ``self.zos``)."""

    zos: Any

    def resolve_block_data(
        self,
        data_block: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the queries in a block-level ``_data`` map (ORCHESTRATOR).

        Supports 3 forms: declarative dict ({model, where, limit}), shorthand
        string ("@.models.zSchema.contacts"), explicit {zData: {...}}. Each runs
        silently; per-query errors are isolated (→ None). A declarative ``fields``
        whitelist is applied to the result before it enters the render context.
        """
        results = {}

        for key, query_def in data_block.items():
            try:
                fields = None

                if isinstance(query_def, dict) and "model" in query_def:
                    fields = query_def.get("fields")
                    query_def = self._build_declarative_query(query_def)

                elif (isinstance(query_def, str)
                      and query_def.startswith(zpath.SIGIL_WORKSPACE)
                      and zpath.split(query_def).segments[:1] == ('models',)):
                    query_def = self._build_shorthand_query(key, query_def)

                if isinstance(query_def, dict) and "zData" in query_def:
                    result = self._execute_data_query(key, query_def, context)
                    results[key] = self._project_fields(result, fields) if fields else result
                else:
                    self.zos.logger.framework.warning(f"[zLoom] Invalid _data entry: {key}")
                    results[key] = None

            except Exception as e:  # pylint: disable=broad-except
                self.zos.logger.framework.error(f"[zLoom] Query '{key}' failed: {e}")
                results[key] = None

        return results

    def _project_fields(self, result: Any, fields: Any) -> Any:
        """Whitelist columns on a resolved read result (defense-in-depth).

        zLoom reads SELECT * at the backend; declaring ``fields: [...]`` drops
        every non-listed column from the resolved value BEFORE it enters the
        render context, keeping sensitive columns (password_hash, email, ...) out
        of anonymous/public reads. Backend-agnostic (filters the Python dicts).
        """
        if not isinstance(fields, (list, tuple, set)):
            return result
        allow = set(fields)

        def _pick(row: Any) -> Any:
            if isinstance(row, dict):
                return {k: v for k, v in row.items() if k in allow}
            return row

        if isinstance(result, list):
            return [_pick(r) for r in result]
        return _pick(result)

    def _build_declarative_query(self, query_def: Dict[str, Any]) -> Dict[str, Any]:
        """Build a zData read from the declarative form (model + where + limit).

        Interpolates ``%session.*`` in the WHERE clause; defaults to limit=1.
        """
        model = query_def.get("model")
        where_clause = query_def.get("where", {})
        interpolated_where = self._interpolate_session_values(where_clause)
        return {
            "zData": {
                "action": "read",
                "model": model,
                "options": {
                    "where": interpolated_where if interpolated_where else {},
                    "limit": query_def.get("limit", 1)
                }
            }
        }

    def _build_shorthand_query(self, key: str, model_path: str) -> Dict[str, Any]:
        """Build a zData read from the shorthand string form (backward compat).

        Auto-filters by the authenticated user id (hardcoded 'id' field); emits a
        warning nudging authors toward the declarative form with an explicit WHERE.
        """
        self.zos.logger.framework.warning(
            f"[zLoom] Shorthand syntax '{key}: \"{model_path}\"' uses hardcoded 'id' field. "
            f"Consider using declarative syntax with explicit WHERE clause."
        )
        user_id = self.zos.session.get('zVisitor', {}).get('id')
        return {
            "zData": {
                "action": "read",
                "model": model_path,
                "options": {
                    "where": {"id": user_id} if user_id else {"id": 0},
                    "limit": 1
                }
            }
        }

    def _interpolate_session_values(self, where_clause: Dict[str, Any]) -> Dict[str, Any]:
        """Interpolate ``%session.*`` (deep-nav) and ``%varname`` in a WHERE clause.

        Uses the shared navigator (``_zsession_path`` → ``deep_nav``) so WHERE
        reads zSession identically to render tokens and gate values. A missing
        path resolves to None (secure default — never the instance owner's value).
        """
        interpolated = {}
        for field, value in where_clause.items():
            if isinstance(value, str) and value.startswith("%session."):
                # _zsession_path is provided by ValueOps on the composed facade.
                session_value = self._zsession_path(value[9:])  # pylint: disable=no-member
                interpolated[field] = session_value
                self.zos.logger.framework.debug(
                    f"[zLoom] Interpolated {value} → {session_value}"
                )
            elif isinstance(value, str) and value.startswith("%route."):
                # Dynamic-route params resolve through the token SSOT (RouteOps store),
                # NOT the zVars bag — ONE navigator for render, gates, and WHERE, so a
                # %route read in a where-clause can't drift from a %route read on a page.
                resolved = self.resolve_value(value)  # pylint: disable=no-member
                interpolated[field] = resolved
                self.zos.logger.framework.debug(
                    f"[zLoom] Interpolated {value} → {resolved}"
                )
            elif isinstance(value, str) and value.startswith("%") and not value.startswith("%session.") and not value.startswith("%data."):
                # Bare `%var` (+ dotted) → resolve through the token SSOT, NOT a local
                # re-read of zVars. This heals the historical dup (WHERE used to re-read
                # session["zVars"] by hand, diverging from render/gate reads) AND, via
                # _lookup's P2 net, lets a not-yet-migrated `%username` fall back to the
                # zLoom route store now that zServer stopped copying params into zVars.
                # Miss → None (secure default; a literal %token never matched a row anyway).
                resolved = self.resolve_value(value)  # pylint: disable=no-member
                interpolated[field] = resolved
                self.zos.logger.framework.debug(
                    f"[zLoom] Interpolated {value} → {resolved}"
                )
            else:
                interpolated[field] = value
        return interpolated

    def _execute_data_query(
        self,
        key: str,
        query_def: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Execute a zData query in SILENT mode and extract the result.

        Interpolates ``where`` on BOTH the explicit ``zData`` form (aggregates put
        it at zData.where; reads at zData.options.where) so a ZLOOM aggregate honours
        %session/%var like the declarative form. Unwraps limit=1 lists to a dict.
        """
        zdata = query_def["zData"]
        zdata["silent"] = True

        if isinstance(zdata.get("where"), dict):
            zdata["where"] = self._interpolate_session_values(zdata["where"])
        options = zdata.get("options")
        if isinstance(options, dict) and isinstance(options.get("where"), dict):
            options["where"] = self._interpolate_session_values(options["where"])

        result = self.zos.data.handle_request(zdata, context)

        limit = query_def["zData"].get("options", {}).get("limit")
        if isinstance(result, list) and limit == 1 and len(result) > 0:
            final_result = result[0]
        else:
            final_result = result

        result_type = type(final_result).__name__
        result_count = len(result) if isinstance(result, list) else 1
        self.zos.logger.framework.debug(
            f"[zLoom] Query '{key}' returned {result_type} ({result_count} records)"
        )
        return final_result
