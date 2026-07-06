"""
Invocation environment + provider registry — the dependency-injection core.

A plugin is invoked the same way everywhere (CLI/wizard is the SSOT base; zAPI is
just a transport adapter that feeds the same flow). Each entry point establishes
an :class:`Invocation` — a transport-agnostic bag holding ``zos`` plus the
request-shaped context (files, params, session) — on a context var. @zfunc then
inspects the plugin signature and injects, by parameter name, whatever
*providers* the plugin asked for.

Adding a new connection point later = one ``@provider("name")`` here. Plugins
discover it simply by naming the parameter; no zOS internals leak in.
"""

from __future__ import annotations

import contextvars
import inspect
import mimetypes
import os
from typing import Any, Callable, Dict, Optional

from .facades import (
    DataFacade, FilesFacade, InstanceFacade, ProxyFacade, TransferFacade, UserCtx,
)

__all__ = [
    "Invocation", "set_env", "reset_env", "current_env",
    "provider", "register_provider", "PROVIDERS", "resolve_kwargs",
]

_ENV: "contextvars.ContextVar[Optional[Invocation]]" = contextvars.ContextVar(
    "zos_plugin_invocation", default=None
)


class Invocation:
    """One plugin call's environment, independent of how it was triggered."""

    __slots__ = ("zos", "files", "params", "_session", "app", "meta")

    def __init__(
        self,
        zos: Any = None,
        files: Optional[dict] = None,
        params: Optional[dict] = None,
        session: Optional[dict] = None,
        app: Optional[str] = None,
        meta: Optional[dict] = None,
    ):
        self.zos = zos
        self.files = files or {}
        self.params = params or {}
        self._session = session
        self.app = app
        self.meta = meta or {}

    @property
    def session(self) -> Optional[dict]:
        if self._session is not None:
            return self._session
        return getattr(self.zos, "session", None)

    @classmethod
    def from_paths(cls, paths: Dict[str, str], zos: Any = None, **kw) -> "Invocation":
        """Build an env whose ``files`` come from local paths (CLI-local source).

        ``paths`` maps a field name → filesystem path. Each file is read into the
        same raw shape multipart parsing produces, so plugins (and FilesFacade)
        behave identically whether the bytes arrived over HTTP or from disk.
        """
        files: Dict[str, Any] = {}
        for field, path in (paths or {}).items():
            with open(path, "rb") as fh:
                data = fh.read()
            mime, _ = mimetypes.guess_type(path)
            files[field] = {
                "data": data,
                "filename": os.path.basename(path),
                "content_type": mime or "application/octet-stream",
                "size": len(data),
            }
        return cls(zos=zos, files=files, **kw)


def set_env(inv: Invocation):
    """Install ``inv`` as the current invocation; returns a reset token."""
    return _ENV.set(inv)


def reset_env(token) -> None:
    try:
        _ENV.reset(token)
    except Exception:  # pylint: disable=broad-except
        pass


def current_env() -> Optional[Invocation]:
    return _ENV.get()


# ─────────────────────────────────────────────────────────────────────────────
# Provider registry — name → fn(zos, inv) -> value
# ─────────────────────────────────────────────────────────────────────────────

PROVIDERS: Dict[str, Callable[[Any, Optional[Invocation]], Any]] = {}


def provider(name: str):
    def deco(fn: Callable):
        PROVIDERS[name] = fn
        return fn
    return deco


def register_provider(name: str, fn: Callable) -> None:
    PROVIDERS[name] = fn


@provider("zos")
def _p_zos(zos, inv):
    return zos


@provider("log")
def _p_log(zos, inv):
    # Ergonomic app-level emitter (zos.log); falls back to the raw logger.
    return getattr(zos, "log", None) or getattr(zos, "logger", None)


@provider("session")
def _p_session(zos, inv):
    return inv.session if inv else getattr(zos, "session", None)


@provider("user")
def _p_user(zos, inv):
    session = inv.session if inv else getattr(zos, "session", None)
    app = inv.app if inv else None
    return UserCtx.from_session(session, app=app)


@provider("files")
def _p_files(zos, inv):
    return FilesFacade(inv.files if inv else {})


@provider("params")
def _p_params(zos, inv):
    return dict(inv.params) if inv else {}


@provider("data")
def _p_data(zos, inv):
    return DataFacade(zos)


@provider("transfer")
def _p_transfer(zos, inv):
    return TransferFacade(zos)


@provider("instance")
def _p_instance(zos, inv):
    return InstanceFacade(zos)


@provider("proxy")
def _p_proxy(zos, inv):
    return ProxyFacade(zos)


def resolve_kwargs(fn: Callable, zos: Any, supplied: set) -> Dict[str, Any]:
    """Build the provider kwargs to inject into ``fn``.

    For each declared parameter that (a) is not already supplied by the caller
    and (b) names a registered provider, resolve and inject it. Parameters the
    caller already filled (positionally or by keyword) are left untouched, so
    explicit args always win and double-injection is impossible.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return {}

    inv = current_env()
    out: Dict[str, Any] = {}
    for name, p in sig.parameters.items():
        if name in supplied:
            continue
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        prov = PROVIDERS.get(name)
        if prov is not None:
            out[name] = prov(zos, inv)
    return out
