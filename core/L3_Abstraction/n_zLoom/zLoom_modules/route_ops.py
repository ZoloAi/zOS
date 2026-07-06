# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/route_ops.py
"""zLoom ROUTE ops — the owner of dynamic-route params.

zLoom owns the binding of every ``%token``; a dynamic route's captured segment
(``/users/%username`` → ``{username: "alice"}``) is just one more binding source,
so it lives HERE — not in a session bag written from zServer. zServer only FEEDS
this store via ``set_route_params``; zLoom owns the store, its lifetime, and its
read (the ``%route.*`` namespace, resolved by ``token_resolver``).

Store: ``session[SESSION_KEY_ZROUTE]`` (its OWN key — deliberately NOT ``zVars``,
so a URL segment can never collide with or go stale against a durable user var).
Request-scoped by intent: rebuilt each hop (see ``set_route_params`` replace-not-
merge), which is what makes the old "stale param re-renders the last page" bug
impossible by construction. Mixed into the ``zLoom`` facade.
"""

from zOS import Any, Dict

from zOS.zVocabulary import SESSION_KEY_ZROUTE


class RouteOps:
    """Route-param methods for zLoom (expects ``self.zos``)."""

    zos: Any

    def set_route_params(self, params: Any) -> None:
        """Seat this request's captured route params as the ``%route.*`` store.

        REPLACES (not merges) the store so a new hop can never inherit the previous
        route's params — the request-scoped contract. zServer calls this once per
        matched dynamic route, handing over ``route["_route_params"]``; that is the
        ONLY writer (the three old ``session["zVars"].update(...)`` bridges collapse
        into this single seam). A non-dict / empty payload clears the store.
        """
        if not hasattr(self.zos, "session"):
            return
        self.zos.session[SESSION_KEY_ZROUTE] = dict(params) if isinstance(params, dict) else {}

    def get_route_params(self) -> Dict[str, Any]:
        """The current request's route params (``{}`` when none) — read-only view."""
        if not hasattr(self.zos, "session"):
            return {}
        store = self.zos.session.get(SESSION_KEY_ZROUTE)
        return store if isinstance(store, dict) else {}

    def clear_route_params(self) -> None:
        """Drop the route store (end-of-request / no-param route)."""
        if hasattr(self.zos, "session"):
            self.zos.session[SESSION_KEY_ZROUTE] = {}
