hosting: one zServer serves one app — hosting runs a HUNDRED | wake each app on demand, route the visitor to the right instance, deploy without downtime | rests on ONE swappable contract (a compute driver: wake/sleep/status) so dev↔prod swap the ENGINE, never the callers | lives in the plugin SDK (`zos_plugin`), not zServer; ALPHA — model stable, platform paths still landing

planes: answering a request vs deciding WHO answers
    data_plane    — one running app serving its pages — `zServer` (request in, page out)
    control_plane — decides WHICH app answers, wakes it if asleep, hands over — Hosting
    analogy       — Flask serves an app; k8s/Heroku/Vercel run + route a FLEET; zOS draws the same line
    rule          — kept apart: zServer never learns of other apps; the control plane never renders a page, only points

driver: the whole control plane rests on ONE contract — swap the backend, callers never change
    contract  — a `ComputeDriver` answers three: `wake(app)` (ensure up, return where to reach) · `sleep(app_id)` (tear down) · `status(app_id)` (asleep/waking/running)
    seam      — the rest of the system talks ONLY to this contract; control flow identical everywhere, only the driver differs
    dev       — `LocalProcessDriver`: each app a child `zolo` process on its own free ports (ports via OS env, tenant's project folder never mutated)
    prod      — `register_driver('k8s', K8sDriver)` and EVERY caller stays identical (`core/zos_plugin/drivers.py`)
    selection — `ZHOST_DRIVER` env → zos config → default `local`; one driver instance reused (in-process instance table survives calls)
    payoff    — test on your laptop, deploy to a cluster later — same wake/sleep/status, different engine

wake: apps sleep using nothing, a request wakes one — scale from zero
    why       — a fleet can't keep every app up; idle apps sleep (zero cost), the control plane brings one up only when asked
    flow      — request → `wake` starts the instance → WAIT until it actually answers (not just port-open) → tell the visitor where to go
    cold_start— first visitor pays a short warm-up; everyone after arrives live
    facade    — a plugin names `proxy` → `ProxyFacade.resolve(app)` → a `ProxyTarget` (`.url`, `.ready`) — wakes if asleep, waits until ready (`core/zos_plugin/facades.py`)
    handoff   — a REDIRECT, not byte-shuffling: dev sends `302` to the instance's host:port; prod returns a stable ingress URL + the reverse proxy forwards HTTP/WS (hosting never hand-rolls packet forwarding)
    proven    — driver spawns the child, instance reaches `running`, `GET /` returns 200 real HTML, `resolve` returns the same url

deploy: replace a running app without dropping anyone — blue-green, three verbs
    idea      — bring the NEW version up BESIDE the live one, then flip the front (visitors never meet a down site)
    stage     — bring up green alongside live blue; the front still points at blue, green held staged
    commit    — flip the front to green in ONE atomic move, then drain + retire blue (in-flight finish during a grace window)
    abort     — throw staged green away, blue untouched — a clean rollback
    mechanism — the front is "where do I point" → the flip is a single assignment; old visitors finish on the retiring instance, new ones land on green (`ReleaseManager`, `core/zos_plugin/release.py`, over ANY driver)
    readiness — the SAME `/zhealth` 200 probe gates the cutover; green must answer ready before blue steps aside; a green that won't come up is REAPED, blue keeps serving (fail-safe)

front_door: the ONE place a concrete platform shows up — how a URL picks an app (ALPHA)
    what          — the only platform-specific piece: a `zServer` route `type: zProxy` that reads a URL segment, looks the app up in a REGISTRY, wakes it via the driver, hands off
    generic       — zServer ships NO table/columns/status words; the registry shape is declared ON THE ROUTE:
        `/app/%slug: { type: zProxy, zProxy: { table: <your registry>, key: slug, spark_field: spark_path } }` — `table` REQUIRED (no default)
        visibility  — OPT-IN: add `visibility_field: status` + `visibility_value: live` → only matching rows resolve (a paused/unknown slug 404s); omit → any matching row resolves
    example       — zCloud's registry is the `zApps` table, keyed by slug, gated on `status: live` — an EXAMPLE, not the model; a normal app author never writes a zProxy route
    push          — pushed apps land via a `BundleStore` (unpacks to `<workspace>/_hosted/<slug>/`, same wake path); storage moves bytes, the platform owns policy — zCloud-specific, later
    status        — ALPHA: a preview of where hosting heads, not a stable surface

where_it_lives: the engine is in the SDK, not the web server
    home        — `core/zos_plugin/{drivers,facades,bundle_store,release}.py` — the plugin SDK, sibling to the data facades
    zserver_role— zServer exposes ONLY the thin `zProxy` front door that hands a request UP to this layer (never runs instances itself)
    boundary    — authoring plugins? the compute/proxy facades are the same SDK you write handlers against (Extending › Plugins)
    recap       — 1) two planes (serve one vs run many) · 2) one driver (wake/sleep/status, swappable) · 3) scale from zero (sleep→wake→redirect) · 4) blue-green (stage/commit/abort) · 5) the front door (a registry-backed route picks the app — platform-specific, alpha)
