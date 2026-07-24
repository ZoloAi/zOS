# zos-plugin Hosting Guide

> **Modules:** `core/zos_plugin/bundle_store.py`, `session_store.py`, `release.py`
> **Purpose:** The zCloud hosting seams — persist a pushed app bundle, externalize sessions so they survive scale-to-zero / blue-green, and roll a new build live with zero downtime. Each is env-selected (local now, cloud later) with policy left to the caller.

**[← Back to zos-plugin Guide](../zPlugin_GUIDE.md) | [Home](../../../README.md)**

---

## BundleStore — persist a pushed app (`zolo push`)

A `BundleStore` persists a pushed bundle and exposes its app slice. The store only **moves bytes**; *policy* (who may push, registry upsert) stays with the caller (zCloud's push plugin).

| Member | Behaviour |
|--------|-----------|
| `unpack(slug, tar_bytes, spark=None, build_id=None)` | persist the bundle → `StoredBundle`; `build_id` unpacks into a per-version subtree (`builds/<id>/`) so blue/green coexist |
| `remove(slug)` | delete a stored bundle (all versions) |
| `prune(slug, keep_build_ids)` | drop build dirs not in the keep set |

`StoredBundle` carries what the registry needs: `slug`, `app_dir`, `rel_root`, `spark`, file counts, and `zspark_path` (`rel_root/spark`) — which matches `AppSpec.from_spark_path` so the zProxy front door + driver resolve it identically ([compute_GUIDE](compute_GUIDE.md)).

### LocalBundleStore — unpack safety

Unpacking a client-supplied `tar.gz` is **untrusted input**, so the dev store fails closed:

- **Path containment** — `_safe_join` resolves each member under the build dir with `realpath`+`relative_to`; traversal/absolute members are skipped. Only regular files are written — **sym/hardlinks are never extracted**.
- **Resource caps** — a member-count ceiling (`ZHOST_MAX_BUNDLE_FILES`, default 10,000) and an uncompressed total-bytes cap (`ZHOST_MAX_BUNDLE_BYTES`, default 512 MiB) are checked *before* writing, so a decompression bomb is rejected (`ValueError`) rather than OOMing the host.
- **Atomic-ish replace + cleanup** — a build dir is replaced wholesale; on any rejection the half-written dir is removed, never left behind.
- `app/` contents land at the build root (the spark's cwd); `attachments/` land beside it under `_attachments/` (dormant payload, never executed); bundle-root metadata (`zProject.json`) is skipped.

---

## SessionStore — externalize Tier-2 sessions

So a hosted app can **scale-to-zero** (sleep when idle) and **blue-green** (a new instance replaces the old) without dropping signed-in users, the session must outlive any single process. A `SessionStore` is keyed by `full_session_id` (`zS_<spark>:zB_<bridge>`); the store moves the opaque blob, the caller decides *what* goes in it (the zBifrost connect/cleanup/resume path).

```python
get(id) -> dict|None   set(id, data, ttl=)   delete(id) -> bool   touch(id, ttl=) -> bool   exists(id)
```

| Backend | Use |
|---------|-----|
| `InMemorySessionStore` | dev/single-process default — a dict with lazy per-key TTL, thread-safe (`RLock`), hands back copies so callers can't mutate the stored blob; behaviourally identical to "no store" through the same API |
| `RedisSessionStore` | local Redis → ElastiCache in prod (same class, different URL); one JSON blob per session, native key TTL; `redis` imported lazily so the SDK stays dependency-free |

`DEFAULT_SESSION_TTL` is 7 days; env (`ZSESSION_STORE`) → `zos.config('session_store')` → `memory` selects the backend (a per-name singleton, since it holds live state).

---

## ReleaseManager — blue/green rollout (`zRelease`)

> **Naming (SSOT):** `zRelease` is a zCloud hosting/release concept (make a versioned build live for a slug) — deliberately distinct from the zSpark `zPersist` key (app storage / hot-reload).

`ReleaseManager.deploy(...)` runs the dance over *any* `ComputeDriver` (local dev → k8s later), so the control flow never changes:

```
1. WAKE GREEN   start the new build as its own instance (key slug#<build>)
2. DRAIN-IN     driver.wake blocks until green serves; if it never comes up →
                stop green, abort, leave blue intact
3. FLIP         call the caller's `flip()` callback to repoint the registry → green
                (the single atomic "now live" act; raising here rolls back green)
4. DRAIN-OUT    grace period (DEFAULT_DRAIN_GRACE) so in-flight blue requests finish
5. SLEEP BLUE   stop the old instance (failure here is a leak, not an outage)
```

Ownership of *state* stays with the caller: the manager never touches the registry directly — it invokes `flip` — so storage/DB policy stays in zCloud and orchestration here. `deploy()` never raises for operational failures; it returns a `ReleaseResult` (`ok`, `flipped`, `blue_stopped`, `reason`, `instance`). `rollback(slug, build_id)` stops a build's instance best-effort. `instance_key(slug, build_id)` (`slug#<build>`) keeps two versions distinct in the driver table.

---

## The front door above these seams

The control plane that *drives* these seams in production is
`t_zHost` (L4): slug ingress (`<slug>.<domain>` via Caddy), the `slug#<build>`
instance table, **owner-scoped tenants** (a tenant's instances are keyed to
their owner — one user's apps can't shadow another's slugs), and the **waking
interstitial** (a sleeping app's first visitor gets a "waking…" page instead of
a timeout while `driver.wake` runs). Wake *failures* land in a declarative
failure sink with the dead child's log tail captured — see
[compute_GUIDE](compute_GUIDE.md).

---

## Why these live in the SDK

`bundle_store` / `session_store` / `release` mirror the `drivers` pattern: a swappable backend chosen by env, with **policy left to the caller**. "Persist a pushed app", "hold a session across processes", and "roll a build live" are *general* zOS capabilities, so they sit beside the compute driver in the SDK rather than inside any one app — a `register_*` call swaps in the prod backend (S3, Redis/DynamoDB, k8s) with no change to callers.

---

## Troubleshooting

**`bundle exceeds size/file-count cap`** — the pushed tar is over the limit (likely a bomb or a stray large asset); raise `ZHOST_MAX_BUNDLE_BYTES`/`ZHOST_MAX_BUNDLE_FILES` deliberately if legitimate.

**`RedisSessionStore requires the 'redis' package`** — install `redis` or set `ZSESSION_STORE=memory`.

**Release reports `green unhealthy` / `flip failed`** — green is torn down and blue stays live (safe); check the green instance log via the driver.

---

## See Also

- [zos-plugin Guide](../zPlugin_GUIDE.md) · [compute_GUIDE.md](compute_GUIDE.md) (the driver these build on)
- [contract_GUIDE.md](contract_GUIDE.md) · [facades_GUIDE.md](facades_GUIDE.md)
