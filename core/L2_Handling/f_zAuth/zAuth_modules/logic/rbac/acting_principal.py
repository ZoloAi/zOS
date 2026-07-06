# zOS/core/L2_Handling/f_zAuth/zAuth_modules/logic/rbac/acting_principal.py
"""
Request-scoped acting principal — thread/async-safe RBAC identity override.

zRBAC normally resolves identity from the ambient ``zos.session`` (zCLI: one
process, one logged-in user). A multi-client front door (zBifrost WS) shares a
single zOS instance across many concurrent connections, so the session cannot
represent "who is asking" for a given request.

This module lets a caller bind the *connection's* authenticated identity for the
duration of one dispatched request, WITHOUT mutating the shared session:

    with acting_as({P_AUTHENTICATED: True, P_ROLE: "admin", P_USER_ID: "u1"}):
        handle_zDispatch(...)        # zData access guard now sees this principal

Isolation: ``contextvars.ContextVar`` copies per asyncio task and per worker
thread spawned via ``asyncio.to_thread`` / ``run_in_executor``, so concurrent
requests never observe each other's principal. Unset (default ``None``) means
"fall back to the ambient session" — i.e. unchanged zCLI behavior.

SSOT: ``ContextHelpers`` is the only reader; every role/permission/auth check
funnels through it, so a single override governs the whole RBAC contract.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, Optional

# Principal dict keys (stable wire-agnostic contract for callers)
P_AUTHENTICATED = "authenticated"
P_ROLE = "role"
P_USER_ID = "user_id"

# Default None => RBAC reads the ambient zos.session (zCLI behavior).
_ACTING_PRINCIPAL: "ContextVar[Optional[Dict[str, Any]]]" = ContextVar(
    "zauth_acting_principal", default=None
)


def get_acting_principal() -> Optional[Dict[str, Any]]:
    """Return the request-scoped acting principal, or None when unset."""
    return _ACTING_PRINCIPAL.get()


def make_principal(
    authenticated: bool,
    role: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a normalized principal dict for :func:`acting_as`."""
    return {
        P_AUTHENTICATED: bool(authenticated),
        P_ROLE: role,
        P_USER_ID: user_id,
    }


@contextmanager
def acting_as(principal: Optional[Dict[str, Any]]) -> Iterator[None]:
    """
    Bind ``principal`` as the acting identity for the enclosed block.

    Always restores the prior value on exit (including on exception). Passing
    ``None`` explicitly clears any inherited principal for the block, which is
    the correct fail-closed choice for an unauthenticated/guest connection
    (so it can never inherit an ambient server identity).
    """
    token = _ACTING_PRINCIPAL.set(principal)
    try:
        yield
    finally:
        _ACTING_PRINCIPAL.reset(token)
