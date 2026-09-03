<!-- cursor: description="Shipping — zProject manifest + zolo login/push: one file names the app, one word ships it to zCloud under the machine's signed-in identity. Reach for when an app leaves the machine" globs="**/zProject.*.zolo" alwaysApply=false -->
zShipping: how an app LEAVES the machine | one manifest (`zProject.<name>.zolo`) beside the spark answers what-is-this / what-ships / who-wakes-it | `zolo login` signs the MACHINE in once, `zolo push` ships under that identity | everything under the folder ships minus `ignore`; zCloud wakes `spark`

manifest: `zProject.<name>.zolo` — the distribution manifest, sibling of the spark
    slug:       ledger              — REQUIRED: the public handle; the app's hosted address (`/users/<you>/<slug>`) + card identity — your username claims the namespace, so slugs never collide globally
    spark:      zSpark.zLedger.zolo — REQUIRED: the boot file zCloud wakes on the other side (the same spark you run locally)
    name:       zLedger             — display name on the feed card
    version:    1.0.0               — your own release label (for readers; not enforced)
    visibility: public | unlisted | private — who finds it hosted: feed / by-link / yours
        seed_only — a FIRST-push seed; after that the owner's dashboard toggle rules — a re-push never flips visibility back
    tagline / tags / cover — the FEED CARD (photo + one-line pitch + filing): manifest-authoritative per push, but an ABSENT key leaves the zApps column alone (dashboard edits survive a meta-less re-push); omit `cover` → server generates a slug-seeded default
        cover rides the multipart BESIDE the bundle (a served blob, never app code) — list it in `ignore` so it stays out of the app/ slice
    ignore:     [logs/*, zRaven/output/*, "*.db-journal"] — what never ships; shell wildcards, matched on the full relative path AND each segment (a bare `__pycache__` prunes at any depth)
        always_pruned — `.git` · `__pycache__` · `*.pyc` · `.DS_Store` ship NEVER, no matter what
        guarded — `#>`/`<#` comment markers in the manifest MUST pair; an unterminated `#>`, an orphan
            `<#`, or a comment marker inside an ignore entry FAILS the push (fail-closed) — zLSP
            underlines an unclosed `#>` as you type
    include:    [docs/spec.pdf]     — dormant extras packed as attachments/ alongside the app — stored, never executed; a missing path FAILS the bundle
    rule — required = slug + spark; everything else defaults sensibly or is card dressing

what_ships: pack light, but ship the TEACHING
    golden_convention — SHIP the zRaven test file (+ seed scripts/upload_bank) as teaching material; prune only RUN artifacts (zRaven/output/*, zShots/*, zVersions/*, logs/*, `_zSpark.*` dev flows, `.zpush_*`)
    Data/ SHIPS when the seeds ARE the demo (a pre-seeded ledger/blog is the product); machine-local env files (`zEnv.development.zolo` carrying an absolute dev mount) NEVER ship — hosted instances must fall back to the pinned CDN client
    zEnv.base MUST ship when it carries `zRequirements:` — the hosted child refuses to boot until the deps are importable (boot verifies, never installs → 01_zspark)

login: `zolo login` — sign the MACHINE in, once (git-/gh-style; no app/instance required)
    interactive — `zolo login <email>` prompts for the password, verifies against the platform ledger, PERSISTS the identity (zOwnership) — clears the watermark, scopes every later push
    token       — `z login --token <PAT>` — non-interactive; the PAT comes from the account page / the desktop launcher handoff / the Foundations install command
    single_key  — ONE live PAT per account: minting/logging-in ROTATES it, killing the previously issued key (an installed machine's stored PAT dies when a new one is minted — by design, not a bug)
    device      — `z login --device` (gh/gcloud-style browser flow) is NOT YET SERVED by zolo.media (zOS#119):
        the CLI half exists and answers honestly — "Device sign-in isn't available on <server> yet" — never a
        crash or a retry-shaped 404 (zOS#65, 1.7.3). `--server <url>` drives the full flow against a
        registrar that does implement `/api/zAuth/device/*`; password + `--token` are the live paths today
    scope       — this is the INSTANCE OWNER (Tier-1), not an app's own users — that's zLogin/zGate → 15_rbac three_whos

push: `zolo push` — the verb; bundle the slice, upload, come up hosted
    resolve  — bare `zolo push` finds the lone manifest in cwd · `zolo push <name>` picks by manifest name · a folder arg resolves the manifest inside it
    identity — authenticated by the machine's persisted PAT (`zolo login`); `--token <PAT>` overrides for one push; not signed in → clean FAIL naming the fix
        auth_first — auth is checked FIRST: a stale/rotated PAT 401s naming the re-mint path, and any
            username/slug/data findings surface only once the token is valid
    flags    — `--dry-run` full file plan, nothing uploads (ALWAYS run it before a first ship) · `--slug <s>` one-push slug override · `--url <base>` target zCloud (default https://zolo.media; `ZOLO_ZCLOUD_URL` env too) · `-v` every shipped file · `--yes` skip the first-public confirm
    first_public — the FIRST push of a `visibility: public` app asks `[y/N]` before shipping (zOS#64 —
        a wrong-cwd push once put an unrelated demo on the zFeed); fires only at a TTY with no receipt,
        so pipelines/CI flow untouched (they get a one-line note); `--yes` is the scripted consent
    data_guard — a push that would DELETE Data/ files present in the live build is REFUSED (409 names
        the exact files); `--replace-data` is the explicit consent when the wipe IS intended
    builds   — each push is a NEW build; the previous is kept server-side, so a bad ship rolls back instead of ruining your day
        retained builds keep their files until purged — the owner's MyApps push history purges a
        superseded/failed build's files on demand
    server   — zCloud upserts the zApps row bound to your account (owner_id), unpacks the slice, wakes `spark` via the hosting control plane (wake/sleep/status → 22_hosting)
    rule     — the manifest is written ONCE; from then on shipping is one word

pull: `zolo pull --slug <slug>` — the verb home: clone YOUR hosted app back to any machine
    dest     — `--dest <dir>` picks the folder (default ./<slug>); it must be EMPTY or new — pull never merges into existing work
    data     — WITHOUT Data/ by default (live data stays safely on the server); `--with-data` snapshots it explicitly, with a loud warning that it's a copy, not a sync
    receipt  — writes the linked `.zpush` receipt into the clone, so it is push-ready as the SAME app (app id survives renames); pull-then-push is the round trip
    identity — the same machine PAT as push; `--url <base>` targets another zCloud
    rule     — dev verb for the CLI crowd; the dashboard's Download stays the average-joe door

apps: `zolo apps` — manage what your account hosts, from the terminal (zOS#64)
    list           — `zolo apps list`: every app you host — slug, status, visibility, URL (the "what did I ship?" answer)
    delete         — `zolo apps delete <slug>`: SOFT delete, the drawer's ritual over the wire — type-the-slug
        confirm (enforced SERVER-side; the prompt is just the messenger), child slept, front door 404s, build
        bytes freed; the row stays, so a re-push of the same slug REVIVES the app · `--yes` skips the prompt
        for scripts · hard-forget (purge) stays dashboard-only by design
    set-visibility — `zolo apps set-visibility <slug> public|unlisted|private`: explicit target value, not a
        toggle (idempotent, scriptable); after the first push this column is the OWNER's — a re-push never re-seeds it
    identity — the same machine PAT as push/pull; `--url <base>` targets another zCloud; ownership re-checked
        server-side per verb (someone else's slug reads as absent, never 403-probes)

seek_as_need: !authoring a manifest — only if extending the pipeline
    resolver+bundle — zguard/push/project_resolver.py (manifest contract, required keys) · bundle.py (_DEFAULT_IGNORE, segment matching, attachments/)
    upload    — zguard/push/command.py (PAT resolve → multipart Bearer POST); server side — zCloud plugins/zpush.py (upsert + seed semantics)
    pull seam — zguard/pull/command.py (ZIP download + traversal-safe extract + receipt); server side — zCloud plugins/zpull.py (GET /api/apps/pull)
    apps seam — zguard/apps/command.py (Bearer JSON verbs); server side — zCloud plugins/apps.py cli_* (+ routes /api/apps/cli/*)
    cli seam  — core/zSys/cli/push_command.py (public shim; no zguard → "run z patch") + args/push_args.py · pull_command.py + args/pull_args.py · apps_command.py + args/apps_args.py
