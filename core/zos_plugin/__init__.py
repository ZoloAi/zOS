"""
zos-plugin — the zOS plugin SDK for Python.

A plugin author writes *intent*; @zfunc wires it to zOS. Two jobs:

1. **Dependency injection.** @zfunc inspects the function signature and injects,
   by parameter name, whatever zOS connection points the plugin asked for —
   ``user``, ``files``, ``transfer``, ``data``, ``session``, ``log``, ``params``,
   ``zos``. No deep ``from zOS...`` imports, no manual session traversal. New
   connection points are added once (see ``context.py``) and discovered just by
   naming the parameter. This is identical whether the call came from the CLI /
   wizard (the SSOT base) or zAPI (a transport adapter that feeds the same flow).

2. **Contract + safety.** Return-value contract is preserved::

       truthy   → success (! satisfied, ^ bounces)
       falsy    → retriable failure
       "error"  → hard abort

   A ``raise ZAbort("...", status=4xx)`` becomes a structured ``ZResult`` failure
   (so HTTP/zAPI gets the right status); unhandled exceptions are logged and
   contained as ``"error"``. ``input()`` is transparently routed to the Bifrost
   WebSocket when the framework sets ``zos._sandbox_input``.

Example::

    from zos_plugin import zfunc

    @zfunc
    def upload(user, files, transfer, data):
        img = files.image("avatar", max_mb=5)
        user.require()
        stored = transfer.store(img.bytes, key=f"users/{user.id}/avatar.{img.ext}",
                                mime=img.mime, filename=img.filename)
        media = data.upsert("media", where={"user_id": user.id, "kind": "avatar"},
                            values={"storage_key": stored.key, "mime_type": img.mime,
                                    "file_size": img.size})
        data.update("users", {"avatar_media_id": media.id}, where={"id": user.id})
        return {"ok": True, "message": "Avatar updated",
                "data": {"media_id": media.id, "url": stored.cache_busted_url}}
"""

import asyncio
import builtins
import contextvars
import functools
import inspect
import logging
import threading

from .result import ZResult, ZAbort
from .context import (
    Invocation, set_env, reset_env, current_env,
    provider, register_provider, resolve_kwargs,
)
from .drivers import (
    AppSpec, Instance, ProxyTarget, ComputeDriver, LocalProcessDriver,
    register_driver, get_driver, READINESS_PATH,
)
from .swap import CutoverResult, prepare_green, commit_green, swap
from .bundle_store import (
    StoredBundle, BundleStore, LocalBundleStore,
    register_bundle_store, get_bundle_store,
)
from .session_store import (
    SessionStore, InMemorySessionStore, RedisSessionStore,
    register_session_store, get_session_store, DEFAULT_SESSION_TTL,
)
from .release import (
    ReleaseManager, ReleaseResult, instance_key,
)

__version__ = "0.8.0"
__all__ = [
    "zfunc", "ZResult", "ZAbort",
    "Invocation", "set_env", "reset_env", "current_env",
    "provider", "register_provider",
    "AppSpec", "Instance", "ProxyTarget", "ComputeDriver", "LocalProcessDriver",
    "register_driver", "get_driver", "READINESS_PATH",
    "CutoverResult", "prepare_green", "commit_green", "swap",
    "StoredBundle", "BundleStore", "LocalBundleStore",
    "register_bundle_store", "get_bundle_store",
    "SessionStore", "InMemorySessionStore", "RedisSessionStore",
    "register_session_store", "get_session_store", "DEFAULT_SESSION_TTL",
    "ReleaseManager", "ReleaseResult", "instance_key",
]

_logger = logging.getLogger("zos.plugin")

# ── Sandbox input routing (session-isolated) ──────────────────────────────────
# When the bridge runtime sets ``zos._sandbox_input`` (per session), a plugin's
# bare ``input()`` must route to *that* session's WebSocket. Patching
# ``builtins.input`` per call is process-global and races across the bridge's
# worker threads — one call could restore the original while another is mid-flight,
# or route input to the wrong session. Instead we install ONE idempotent shim that
# delegates to a ``ContextVar`` (per-thread / per-async-context), so each in-flight
# invocation resolves to its own router and falls through to real ``input`` otherwise.
_SANDBOX_INPUT: "contextvars.ContextVar" = contextvars.ContextVar(
    "zos_plugin_sandbox_input", default=None
)
_REAL_INPUT = None
_INPUT_SHIM_LOCK = threading.Lock()
_INPUT_SHIM_INSTALLED = False


def _install_input_shim() -> None:
    """Install the contextvar-routed ``input`` shim exactly once (idempotent)."""
    global _REAL_INPUT, _INPUT_SHIM_INSTALLED  # pylint: disable=global-statement
    if _INPUT_SHIM_INSTALLED:
        return
    with _INPUT_SHIM_LOCK:
        if _INPUT_SHIM_INSTALLED:
            return
        _REAL_INPUT = builtins.input

        def _routed_input(*args, **kwargs):
            fn = _SANDBOX_INPUT.get()
            return (fn or _REAL_INPUT)(*args, **kwargs)

        builtins.input = _routed_input
        _INPUT_SHIM_INSTALLED = True

_P = inspect.Parameter
# Signature exposed to the framework's injector so it always hands us `zos`
# (and `context`) regardless of what the inner function declares.
_WRAPPER_SIGNATURE = inspect.Signature([
    _P("args", _P.VAR_POSITIONAL),
    _P("zos", _P.KEYWORD_ONLY, default=None),
    _P("context", _P.KEYWORD_ONLY, default=None),
    _P("kwargs", _P.VAR_KEYWORD),
])


def _looks_like_zos(obj) -> bool:
    return hasattr(obj, "logger") or hasattr(obj, "data") or hasattr(obj, "session")


async def _acontract(coro, fn):
    """Carry the @zfunc return/error contract through an async plugin body.

    The sync wrapper resolves DI and hands back the coroutine; this awaits it so
    an ``async def`` gets the SAME contract as a sync function — ``ZAbort`` →
    its structured result, unhandled exceptions logged + contained as ``"error"``.
    Without it, an async body's exception bypasses the wrapper (which only ever
    wrapped coroutine *creation*) and escapes the contract.
    """
    try:
        return await coro
    except ZAbort as abort:
        return abort.result
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:  # pylint: disable=broad-except
        _logger.error(
            "[zos-plugin] Unhandled exception in async '%s': %s",
            getattr(fn, "__qualname__", fn), exc, exc_info=True,
        )
        return "error"


def zfunc(fn):
    """Wrap a plugin function with signature-based DI + the zOS contract.

    Works for sync and ``async def`` plugins alike: a coroutine function gets the
    same DI and the same return/error contract, applied after the await.
    """
    is_async = asyncio.iscoroutinefunction(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        inv = current_env()

        zos = kwargs.pop("zos", None)
        context = kwargs.pop("context", None)
        if zos is None and inv is not None:
            zos = inv.zos
        if zos is None and args and _looks_like_zos(args[0]):
            zos, args = args[0], args[1:]  # tolerate a legacy positional zos

        own_token = None
        if inv is None:
            inv = Invocation(zos=zos, params=dict(kwargs))
            own_token = set_env(inv)
        elif inv.zos is None and zos is not None:
            inv.zos = zos

        sandbox_input = getattr(zos, "_sandbox_input", None)
        input_token = None
        if sandbox_input is not None:
            _install_input_shim()
            input_token = _SANDBOX_INPUT.set(sandbox_input)

        try:
            # Caller-supplied params (positional + keyword) take precedence over
            # injected providers, so explicit args always win.
            supplied = set(kwargs)
            try:
                isig = inspect.signature(fn)
                positional = [
                    n for n, p in isig.parameters.items()
                    if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                ]
                for i in range(min(len(args), len(positional))):
                    supplied.add(positional[i])
                if context is not None and "context" in isig.parameters:
                    kwargs.setdefault("context", context)
                    supplied.add("context")
            except (TypeError, ValueError):
                pass

            injected = resolve_kwargs(fn, zos, supplied)
            merged = {**injected, **kwargs}
            if is_async:
                # Hand back a coroutine that carries the contract through the await
                # (the executor awaits it — CLI via asyncio.run, Bifrost via
                # run_coroutine_threadsafe). Token cleanup still runs in the sync
                # ``finally`` below: the tokens were set in this context, so they
                # must be reset here — not across the loop thread that drives the
                # coroutine (a cross-context reset would raise).
                return _acontract(fn(*args, **merged), fn)
            return fn(*args, **merged)

        except ZAbort as abort:
            return abort.result
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:  # pylint: disable=broad-except
            _logger.error(
                "[zos-plugin] Unhandled exception in '%s': %s",
                fn.__qualname__, exc, exc_info=True,
            )
            return "error"
        finally:
            if input_token is not None:
                _SANDBOX_INPUT.reset(input_token)
            if own_token is not None:
                reset_env(own_token)

    wrapper.__signature__ = _WRAPPER_SIGNATURE
    wrapper.__zfunc__ = True
    return wrapper
