# zos-plugin Contract Guide

> **Modules:** `core/zos_plugin/__init__.py` (`zfunc`), `context.py`, `result.py`
> **Purpose:** The authorship core — how `@zfunc` injects dependencies by parameter name, establishes the per-call invocation environment, preserves the return contract, and routes `input()` safely per session.

**[← Back to zos-plugin Guide](../zPlugin_GUIDE.md) | [Home](../../../README.md)**

---

## `@zfunc` — the wrapper

`zfunc(fn)` wraps a plugin function so the framework can call it uniformly. It:

1. Resolves the `zos` handle (from kwargs, the current `Invocation`, or a tolerated legacy positional).
2. Establishes an `Invocation` on a `ContextVar` if none exists yet (own-token bookkeeping for clean teardown).
3. Injects providers the function declared but the caller didn't supply.
4. Runs the function and maps the result/exception to the contract.

It exposes a fixed `__signature__` (`*args, zos=None, context=None, **kwargs`) so the framework's injector always hands it `zos`/`context` regardless of the inner signature, and marks the wrapper with `__zfunc__ = True`.

### Return contract

| Plugin returns | Framework sees |
|----------------|----------------|
| truthy | success (`!` satisfied, `^` bounces) |
| falsy (`None`/`False`/`""`) | retriable failure |
| `"error"` | hard abort (wizard sentinel) |
| `raise ZAbort("msg", status=4xx)` | structured `ZResult` failure with that status |
| unhandled `Exception` | logged with traceback, contained as `"error"` |

`KeyboardInterrupt`/`SystemExit` are re-raised, never swallowed.

---

## Dependency injection (`context.py`)

A plugin names parameters; `@zfunc` injects them. Resolution rules (`resolve_kwargs`): for each declared parameter that the caller did **not** supply and that names a registered provider, resolve and inject it. **Caller-supplied args (positional or keyword) always win** — double-injection is impossible.

### Built-in providers

| Param | Yields |
|-------|--------|
| `zos` | the live zOS handle (escape hatch / god object) |
| `log` | `zos.log` (app emitter) or the raw logger |
| `session` | the invocation session, else `zos.session` |
| `user` | `UserCtx` resolved from the session ([facades](facades_GUIDE.md#user)) |
| `files` | `FilesFacade` over this call's uploads |
| `params` | a copy of the invocation params dict |
| `data` | `DataFacade` over `zos.data` |
| `transfer` | `TransferFacade` over the zTransfer engine |
| `instance` | `InstanceFacade` (compute lifecycle) |
| `proxy` | `ProxyFacade` (wake-and-resolve addressing) |

Add a new connection point with one `@provider("name")` — plugins discover it just by naming the parameter; no zOS internals leak in.

```python
from zos_plugin import provider

@provider("clock")
def _clock(zos, inv):
    import time
    return time.time
```

---

## The invocation environment (`Invocation`)

`Invocation` is a transport-agnostic bag (`zos`, `files`, `params`, `session`, `app`, `meta`) held on a `ContextVar`, so concurrent/async calls each see their own. Every entry point establishes one; CLI-local file sources use `Invocation.from_paths({field: path})` to read disk files into the *same* raw shape multipart parsing produces — so a plugin behaves identically whether bytes arrived over HTTP or from a path.

`set_env` / `current_env` / `reset_env` manage the contextvar (the wrapper handles tokens for you).

---

## Session-safe `input()`

When the bridge runtime sets `zos._sandbox_input` (per session), a plugin's bare `input()` must reach *that* session's WebSocket. The SDK installs **one** idempotent shim over `builtins.input` that delegates to a `ContextVar` set per invocation — so concurrent plugin calls on the bridge's worker threads each route to their own session and fall through to the real `input` when unset. (A per-call global patch would race — one call could restore the original while another is mid-flight, or cross-route input.)

---

## `ZResult` / `ZAbort` (`result.py`)

`ZResult` is the structured envelope — `ok`, `data`, `message`, `error`, `status`, `meta` — with `to_dict()` / `to_http()` and constructors `success()` / `failure()`. `ZResult.coerce(value)` normalises any plugin/handler return (explicit `{ok: ...}`, legacy `{success: ...}`, a plain data dict, or a bare value) into a `ZResult`, so imperative plugins keep returning plain dicts while the framework gets structured feedback. The open-core **zAPI** handler (`q_zServer`) consumes `coerce()` to turn a plugin return into a JSON HTTP response.

`ZAbort(error, status=4xx)` lets guard/validation code stay linear (`raise ZAbort(...)`); the wrapper catches it and surfaces `.result`.

---

## Troubleshooting

**A provider isn't injected** — the parameter name must match a registered provider exactly, and the caller must not already supply it.

**Plugin "succeeds" with no effect** — returning `None`/`False` is a *retriable failure*, not success; return a truthy value or a `{"ok": True, ...}` dict.

**Wrong HTTP status on failure** — `raise ZAbort("msg", status=...)` instead of returning a bare dict, so zAPI emits the intended code.

---

## See Also

- [zos-plugin Guide](../zPlugin_GUIDE.md) — facade overview
- [facades_GUIDE.md](facades_GUIDE.md) — the injected connection points
- [compute_GUIDE.md](compute_GUIDE.md) · [hosting_GUIDE.md](hosting_GUIDE.md)
