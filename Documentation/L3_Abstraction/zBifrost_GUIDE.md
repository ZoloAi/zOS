**[← Back to zData Guide](zData_GUIDE.md) | [Home](../../README.md) | [Next: zShell Guide →](zShell_GUIDE.md)**

---

# zBifrost

**zBifrost** is the **Terminal↔Web bridge** of **zOS** (Layer 3 — Abstraction).
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

In one sentence: the *same* `.zolo` declaration that runs in your terminal also
renders live in a browser — zBifrost streams the rendered output over a WebSocket
and routes the browser's actions back to your code, with **no API layer, no
frontend framework, and no page reloads**.

You never write WebSocket plumbing, event wiring, or authentication handshakes.
You declare *what should happen*; zBifrost handles *how* it reaches the web.

---

## What zBifrost is in charge of

- **Mirroring the terminal to the web** — every `z.display.*` call renders in the
  browser too, automatically, from the same code.
- **Routing the web back** — clicks, form submits, and menu choices in the browser
  arrive back in your workflow as ordinary input.
- **Authenticating connections** — a three-tier model (below) decides who may
  connect and under whose identity their commands run.
- **Keeping clients in sync** — session, user, and data state are cached and pushed
  to connected clients as they change.
- **Managing the connection lifecycle** — start/auto-start, health checks, client
  tracking, and graceful shutdown.

---

## The behavior to expect

zBifrost adapts to *where* a `.zolo` app is running, from **one** declaration:

- **In the terminal (zCLI):** the bridge is dormant; your app runs as a normal
  blocking terminal program.
- **On the web (zBifrost mode):** the bridge is live. The page streams out
  progressively as the workflow builds it, *pauses* at a menu or a gated step
  (e.g. a form), and resumes when the browser sends the answer back — nothing
  blocks the server, and concurrent visitors stay isolated.

That dual behavior — one source of truth, two runtimes — is the whole point: you
author once and it behaves correctly in both places. You should expect the *same
results and ordering*; only the timing (blocking vs. streaming) differs.

Turn the bridge on declaratively via `zSpark`:

```python
from zOS import zOS

# Terminal-only (default): bridge dormant until you call z.bifrost.start()
z = zOS()

# Web mode: bridge auto-starts on initialization
z = zOS({"zMode": "zBifrost"})
```

---

## Three-tier authentication

A connecting client is placed in exactly one context, configured with
`websocket.auth_tier` in `zSpark`:

| Tier | Who | How they connect |
|------|-----|------------------|
| **zSession** | internal zCLI user (your own terminal app) | session token |
| **Application** | external web user | API key issued via `z.auth` |
| **Dual** | both at once on the same bridge | `?token=` *or* `?api_key=` |

The authenticated identity is carried through to every command the client issues,
so the data layer enforces **that user's** permissions — never the server's.
Unauthenticated/guest connections stay fail-closed: they can see public content
but cannot inherit privileged access.

---

## The seam: why the mechanism stays on the server

The browser client (`zbifrost-client`) is deliberately **thin**. The server
encodes display events into compact wire opcodes and the client only *decodes and
renders* them — it never sees the zolo authoring model, the workflow engine, or
the routing logic. Everything that makes zOS *zOS* stays server-side; the open JS
client is a renderer, not a copy of the runtime.

That seam is what lets zOS deliver a live web GUI from a single declaration while
remaining a single, verifiable product rather than something that can be lifted
out of the browser.

---

## Under the hood

zBifrost's runtime — the WebSocket bridge orchestrator, the three-tier auth
manager, the session/user/data cache fabric, the event/opcode router, and the
connection monitor — is a **sealed ZoloMedia component shipped as part of
zGuard**. It cannot be replicated, forked, or impersonated, and it installs with
every zOS runtime (`z patch`). The open-core repository carries only the seam (a
~26-line fail-closed shim) that connects to it; without zGuard the shim refuses to
run rather than degrading to an insecure bridge.

**For implementation details, integration questions, or commercial use, email
[gal@zolo.media](mailto:gal@zolo.media).**

---

## Try it

The runnable demos (Levels 0–4: start modes, display sync, auth tiers, caching,
monitoring) live in the public demos repo:

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/ZoloAi/zolo-zcli.git
cd zolo-zcli && git sparse-checkout set Demos
# demos: Demos/Layer_2/zBifrost_Demo/
```

> Building on zBifrost: raw WebSocket primitives are in the
> [zComm Guide](../L1_Foundation/zComm_GUIDE.md); HTTP/static serving is in the
> [zServer Guide](../L4_Orchestration/zServer_GUIDE.md); terminal rendering is in the
> [zDisplay Guide](../L2_Handling/zDisplay_GUIDE.md).

---

**[← Back to zData Guide](zData_GUIDE.md) | [Home](../../README.md) | [Next: zShell Guide →](zShell_GUIDE.md)**
