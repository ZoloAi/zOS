# Ports — the pinned-vs-unpinned doctrine

**Module:** `core/L4_Orchestration/r_zServer/zServer_modules/lifecycle/` ·
**Config SSOT:** `core/L1_Foundation/a_zConfig/zConfig_modules/network/`
**Since:** 1.7.0 (zOS #43, #22, #28)

One rule decides every port question in zOS: **is the port pinned?**

| | Pinned | Unpinned |
|---|---|---|
| Who decided | You (spark/env) or the platform (hosted) | zOS |
| Port taken | **Fail loud** (`OSError`, boot stops) | **Hunt** the window for a free port |
| Guarantee | The port you named or nothing | *A* port, announced on stdout |

## What counts as a pin

- `zSpark.zServer.port` / `zSpark.websocket.port` — the author's pin
- `HTTP_PORT` / `WEBSOCKET_PORT` env (including `.zEnv`) — the operator's pin
- Driver-injected ports on a hosted instance (`ZHOST_MANAGED=1`) — the platform's pin

Anything that can't prove it's huntable is treated as pinned — fail loud beats
guessing. Pins are sacred because bookmarks, launchd units, proxies and Caddy
routes all point at them; a pinned service silently moving one port over would
be worse than a crash.

## What unpinned boots do

No pin anywhere → zOS decides: start at the preferred default (`8080` HTTP /
`8765` WS) and walk a deterministic window (default + 19, i.e. `8080–8099`)
for the first free port. The chosen port is **announced on stdout** in a
machine-readable line:

```
[zOS] app  http://127.0.0.1:8081
[zOS] sync ws://127.0.0.1:8765
```

Launchers, ravens and scripts should parse that line rather than assume 8080.
If the whole window is full, boot fails loud — hunting must never turn a full
house into a silent hang.

## The full cascade (host and port, symmetric)

```
hosted driver env (only under ZHOST_MANAGED=1)   ← platform wins on its own infra
  → zSpark.zServer.{host,port}                   ← author is king locally
    → HTTP_HOST / HTTP_PORT env floor (.zEnv)    ← operator floor
      → defaults (127.0.0.1 / 8080)
```

Details: [network_GUIDE.md](../../L1_Foundation/zConfig_Guides/network_GUIDE.md)
(Configuration Hierarchy). Self-replace (`z reload`) never re-hunts — a live
service keeps its port.

## See Also

- [lifecycle_GUIDE.md](lifecycle_GUIDE.md) — runners, troubleshooting
- [compute_GUIDE.md](../../L0_Core/zPlugin_Guides/compute_GUIDE.md) — how the
  zHost driver injects per-instance ports into tenant children
