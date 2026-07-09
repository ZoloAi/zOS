<!-- cursor: description="zRaven — zOS tests its own work: z raven --gen writes the test from zSpark+zUI, --run boots + walks it green/red; string-first .zolo, one Tests: block; fix the zUI not the test" globs="**/zRaven.*.zolo,**/zRaven/**" alwaysApply=false -->
zRaven: zOS proves its own work | `--gen` writes the test from your zUI, `--run` boots+walks it green/red | one Tests: block; bare primitives infer their mode, `zAssert:`/`zMarker:` shared | terminal-first — CLI green before browser | fix the zUI, never the test

core: the loop — spark first, always
    --gen <name>   — read zSpark+zUI, WRITE zRaven/zRaven.<name>.zolo (never hand-write the skeleton)
    --run <name>   — boot that spark, walk every step, pass/fail per line, halt on first fail (default)
    --hint         — read last runs, suggest next move (rollback to archived rN, narrow scope)
    <name>         — spark middle stem (zSpark.zLogin.zolo → zLogin); optional if one spark; `--spark <path>` = full path
    scope          — one page = one zSpark that BOOTS that page; !script a journey to reach it; zOpen derived FROM spark
    RED step       — the zUI drifted: fix source + regenerate; tuned zFill/zSubmit values survive --gen
    dev            — !put `zRaven:` in zSpark during dev (auto-runs every boot, noisy) — run `--run` explicitly
    alpha          — --gen coverage still catching up to full grammar (inputs, gates, rich widgets)

dev_spark: `_zSpark.<flow>.zolo` — an isolated entry point, NOT the app's canonical spark
    why       — deep-testing one flow (e.g. a dialog three clicks past Main) shouldn't pay the nav tax every
        --run; a dev spark boots straight to the flow's own block, skipping the journey to reach it
    name      — single segment, flow-named (NOT block-named, NOT app-named — the app is already the folder):
        `_zSpark.add_contact.zolo`, `_zSpark.empty_state.zolo` — same fields as a real zSpark, `zBlock:`
        points at wherever the flow starts
    isolation — the `_` prefix makes it invisible to every `zSpark.*.zolo` glob (auto-discovery, `z demos`,
        --gen's default target resolution) by construction — no engine change, no special-casing, it just
        never matches; boots ONLY by its full filename (`z _zSpark.add_contact.zolo` or
        `z raven --run --spark _zSpark.add_contact.zolo`), never the `z <name>` shorthand
    pairing   — `z raven --gen --spark _zSpark.add_contact.zolo` writes `zRaven/zRaven.add_contact.zolo` —
        the raven name is everything after the FIRST dot in the spark filename, so the flow name carries
        through automatically; that raven file has no underscore itself (nothing scans zRaven/ for
        candidates, so it needs none)
    never     — a dev spark's `zRaven:` never gets merged into or replaces the app's canonical raven; it's
        its own file, own history row, own archive lineage — a scratch tool, not a shortcut around
        writing the real app-level raven
    !manual_mutate — a manually-booted `z zSpark.<name>.zolo` (fine for LOOKING during style/UX dev, see
        bifrost_browser_rule) has NONE of --run's isolate/restore safety net — any add/toggle/delete/submit
        clicked by hand writes straight to REAL Data/ and stays there. Never drive CRUD by hand to "test" a
        flow, in a browser or via a hand-rolled script (Playwright et al.) — that's what --run is for. Add
        the flow as a step in zRaven/zRaven.<name>.zolo and `--run` it; that's the only isolated, restorable,
        reproducible way to exercise or inspect app behavior.

shape: string-first .zolo, one block of named steps — top→bottom, `zMarker: done` closes
    Tests:
        Open_Home:                       #> compound: primitives run in fixed order <#
            zOpen: zSpark
            zAssert:
                dom: {selector: h1, contains: I intend}
        Read_FAQ:
            zPick: FAQ                   #> bare primitive — mode inferred (zCLI) <#
        Add_Contact:
            zFill:                       #> declarative form fill — 1 line per field <#
                name: Ada Lovelace
                email: ada@test.local
        Done:
            zMarker: done

modes: two runners, one grammar — zMode in zSpark picks
    zCLI      — drives terminal stdin/stdout; fast, no browser; START here
    zBifrost  — drives headless Chromium (Playwright) + WS leg; screenshots live here
    blocks    — `CLI_*` CLI-only | `Browser_*`/`Bifrost_*`/`zBifrost_*` browser-only | other name = BOTH
    steps     — mode is INFERRED from the primitive: zWizard → zCLI-only; zOpen/zWait/zShot/zClick/zType/zDrag/
        zUpload/zHistory → zBifrost-only (no terminal equivalent); everything else below is DUAL-MODE
    dual_mode — `zFill`/`zPick` are ONE primitive, not two: cli_runner drives stdin (prompt-by-field / menu
        index), ws_runner translates the SAME step to the rendered DOM — `zFill` → `[name='<field>']` per
        key then clicks the enclosing form's `button[type='submit']` (mirrors the zCLI dialog's own
        implicit last-field-submits flow); `zPick: Option` → `button[data-zkey='Option']` (data-zkey = the
        zUI option/action key). Write the step ONCE against zUI field/option names — no selectors, no
        hand-swap, no CLI/Bifrost fork. --gen emits it once and it is correct for whichever zMode runs it.
    wrappers  — `zCLI:`/`zBifrost:` still honored; only needed when vocabulary is truly ambiguous (zLogger-only
        step, dict zSubmit) or to force a one-off hand-picked CSS selector instead of the field/option name
    !data_zkey_depth — `data-zkey` is stamped per rendered key, but only reliably a `zClick: "[data-zkey='Key']"`
        target when that key is a DIRECT child of its block (top-level button, e.g. zBlog's NewPost) — one level
        under a plain organizational wrapper (a grouping block with no zGate, just structure) or inside a zList's
        `each:` it's unreliable; reach for the element's own `_zClass` instead (zBlog's Edit/Delete buttons under
        OwnerActions, zBooking's per-row Cancel under a zList row, zShop's Nav-wrapped Cart button under
        `NavCart` → `.zShop-nav-cart-btn`)
    zSubmit   — scalar value → zCLI stdin; dict {path, gate, value} → zBifrost WS gate
    shared    — `zAssert:`/`zMarker:`/`zLogger:` run in both modes (scope with a wrapper if not intended)
    first     — TERMINAL IS TRUTH: CLI green, then flip to zBifrost (the coat, not a second test)

drive_dual: dual-mode primitives — ONE step, both runners (write once, no fork)
    zPick: Option            — zCLI: send that menu option's number (`^opt`, `zBack`, `_`→space work)
                               zBifrost: click `button[data-zkey='Option']` (the zUI option/action key)
    zFill: {field: value}    — zCLI: per field assert prompt → submit value; tuned values survive --gen
                               zBifrost: per field set `[name='field']`, then click the form's Submit button
    zSubmit: value           — scalar only here (a dict zSubmit is the zBifrost-only WS-gate form, see drive_web)
                               zCLI: type at the prompt; `$Var` refs resolve from captures — zBifrost: same $Var resolution, no browser action

drive_cli: zCLI-only step primitives (zWizard has no Bifrost translation yet)
    zVar: Name               — on a zSubmit, remember value as `$Name`
    zAllowError: true        — permit an ERROR: line after this submit (default: ERROR fails)
    zExpect: deny            — prove a gate HOLDS: pair with zPick; PASS when denied, FAIL if let in
    zCapture: {var, pattern} — regex output → `$var` (group 1 or whole; ANSI stripped)
    zMenu / zWizard          — containers: nest zPick/zAssert (zMenu) or sub-steps (zWizard)
    zSetup:                  — soft first block (fixtures); failures are ⚠ warnings, uncounted
    zMarker: done            — close stdin, end run; put LAST (shared — also closes out a zBifrost run)

drive_web: zBifrost-only step primitives (Playwright + WS + HTTP; no terminal equivalent)
    zOpen: zSpark            — homepage `/`; or `@.UI.Page` route; or `{type, zLoom|zUI, params}`
    zViewport: desktop       — desktop|tablet|mobile | `[w,h]` | device name; fresh context each change
    zWait: {selector, state} — state: visible|hidden|attached|detached|enabled; timeout ms
    zClick: {selector}       — hand-picked selector escape hatch when a bare `zPick` name won't do
    zType: {selector, value} — hand-picked selector escape hatch when a bare `zFill` field name won't do
                               `~email`/`~name`/`~uuid`/… generate unique; `$Ref` reuses
    zUpload: {selector, path}— set a file (relative paths resolve to app dir)
    zDrag: {selector, from, to} — drag by pixel offsets
    zHistory: back|forward   — browser Back/Forward (popstate); follow with zWait
    zShot: {full_page, …}    — → zRaven/zShots/<name>/<viewport>/ (format/quality/delay/selector/burst)
    ws_leg                   — zBoot (walk a zUI block) · zExecute (run a zFunc) · zSubmit ({path, gate, value}) — need zGuard
    http_leg                 — zFetch ({url, method, headers, params, body}) · zClean ({model, match}) trims a CSV mid-run
    compound                 — a step may hold several; run fixed order (viewport→open→interact→wait→shot)
    !zScreenshot             — DEPRECATED alias of zShot (shoots + warns)

assert: zAssert — check the outcome (empty = pass)
    contains / not_contains  — substring of output/last response (case-insensitive, `_`→space in CLI)
    success: true            — no ERROR: in output/response
    dom: {selector, property, contains|equals|matches} — inspect a node (property default innerText)
    dom: {selector, count|min_count|max_count}         — how MANY nodes match (count: 1 = rendered once)
    style: {selector, property, value}                 — substring of computed CSS
    api: {status, status_not, json_key|json_keys, body_contains} — a zFetch response (json_key: {key, equals, contains, not_null})
    zLogger: msg             — an app log line was emitted (string | {message, level})
    !strict                  — unknown/empty step FAILS by default (opt out zRavenOptions.strict: false)

shots: the shippable bar = 3 viewports that read cleanly
    where   — zRaven/zShots/<name>/<viewport>/<step>.png (viewport = desktop|tablet|mobile)
    how     — zViewport tears down to a FRESH blank context (no URL loaded) — always follow it with
              zOpen: zSpark + zWait before zShot, or the shot captures a blank page; repeat per viewport
    sizes   — desktop 1280×720 · tablet 768×1024 · mobile 390×844 (`[w,h]`/device name also)
    review  — DONE ≠ tests pass; it's shots that look shippable at all three — LOOK at them
    opts    — full_page, format(png/jpeg/webp)+quality, selector, delay, resolution, burst {every, count}
    on_fail — ALWAYS get a screenshot, even red: a compound step (e.g. zOpen+zWait+zShot) halts at its
              FIRST failing primitive and never reaches its own zShot line — Bifrost auto-captures
              `<step>_FAILED.png` the instant any primitive/exception fails (best-effort, never masks
              the real error) — a blank/broken screenshot on a red step is itself the diagnostic;
              never author a workaround (split shot into its own step) to get one, it's automatic

history: every --gen is reversible — archive + replay
    archive — before overwrite, --gen copies active → {app}/zVersions/tests/zRaven.<name>[uiVer]_rN.zolo (skipped when byte-identical to last rN)
    name    — [uiVer] = source zUIVersion; _rN = revision (1,2,3… per uiVer)
    edits   — active drifted from last archive → --gen prints "manual edits — archived as rN"
    replay  — --run --r N (revision) | --run --v <uiVer> (latest rN for UI) | --v <uiVer> --r N (exact)
    resolve — none → active | --v only → highest rN for UI | --r only → that rN on newest UI
    drift   — --run pre-flights raven `# zRavenVersion:` vs UI zUIVersion; WARNS (not blocks)
    output  — zRaven/output/ (.last_raven_result, zRaven.last_run.log, runs.csv) — what --hint reads
    data    — Data/ snapshot-isolated per `--run` invocation only, restored after — no manual reset; a
        hand-run `z zSpark...` outside `--run` gets none of this and writes straight to real Data/
    fs_gap  — isolation covers ONLY Data/ — a step whose own action writes elsewhere on disk (e.g. a
        zFunc plugin copying an uploaded file into static/) is NOT restored; that write is real and
        permanent even inside `--run`, and re-running the SAME flow again multiple times can pile up
        collision-safe duplicates (`name_2.ext`, `name_3.ext`, …) if the plugin never overwrites — clean
        stray copies by hand between iterations, same as any other non-Data/ side effect a flow performs

zcommit: `z raven --commit 'label'` — archive a milestone snapshot of ONE flow (spark + raven)
    what     — additive only, nothing in the working tree moves or deletes; NOT git — no branches, no
        merges, no truncation, just numbered folders that are written once and never mutated
    scope    — always one flow: the current `zSpark.<app>.zolo` OR a `_zSpark.<flow>.zolo` dev spark
        (`--spark` selects which); `z raven --commit` with no `--spark` targets the app's canonical spark
    gate     — blocks unless the flow's LAST run passed (0 failed steps); `--force` overrides — a commit
        is a milestone claim, an unproven/broken state needs an explicit override to record one
    where    — `zVersions/commits/<flow>/c1/, c2/, …` — cN increments per flow, never reused
    contents — `snapshot/` full raw copy of the flow's OWN files (spark + active raven) PLUS the project's
        shared text-source state at that moment (models/, zLoom/, zViews/, routes/ — whatever exists);
        `diff.txt` plain unified diff vs the PREVIOUS commit of this SAME flow (agent-only changelog,
        absent on the genesis c1); `shots/` raw copy of that flow's zShots (Bifrost only); `<title>.log`
        raw copy of the run log; `manifest.json` records which snapshot paths are `flow_owned` (spark +
        raven — the ONLY paths zRevive ever restores) vs `shared` (historical record, never restored)
    ledger   — `zVersions/commits.csv` — one project-wide row per commit (id, flow, commit, label,
        timestamp, spark_file, raven_file, steps_total/passed/failed, path) — full commit history in one read
    when     — suggest after an exit_gate (all zRaven green, shots reviewed+shippable) — see 00_workflow

zclear: `z raven --clear` — remove committed dev-flow scratch files + orphaned zRaven output
    what     — the subtractive counterpart to zcommit; ONLY removes what's either backed up by a real
        commit, or unreferenced junk nothing points to anymore — never a guess, never a "probably fine"
    dev flows — `_zSpark.<flow>.zolo` + its `zRaven/zRaven.<flow>.zolo` are removed ONLY when: (1) a
        commit exists for that flow, AND (2) the commit's flow-owned snapshot is byte-identical to the
        current working copy — no silent loss of not-yet-committed edits
    --force  — skips check (2) (drift is OK, you're choosing to lose it) but NEVER check (1) — clearing
        something with zero backup anywhere is refused even with --force, no exceptions
    canonical — a real `zSpark.<name>.zolo` (no underscore) is NEVER touched, committed or not; multiple
        canonical sparks in one app are a deliberate developer choice, not zClear's business
    shots    — `zRaven/zShots/<X>/` is NEVER source, only disposable proof output the next `--run`
        regenerates from scratch — WIPED unconditionally for every flow on every `--clear`, canonical or
        dev, committed or not (already-archived inside a zCommit if one was ever made); the
        spark/raven ownership protection above never extends to shots
    orphans  — a `zRaven/zShots/<X>/` matching no zSpark OR _zSpark file at all is wiped the same way —
        nothing references it, always safe
    scope    — `--clear` scans every `_zSpark.*.zolo` in cwd; `--clear <flow>` scopes to one
    preview  — `--dry-run` prints what would be cleared/skipped (+ why) without deleting anything
    ledger   — `zVersions/clears.csv` — one project-wide row per clear/skip (id, timestamp, flow, action, reason)
    when     — suggest after a successful zcommit of a dev flow that's served its purpose — see 00_workflow

zrevive: `z raven --revive <flow>` — restore a flow's OWN files from a zCommit back into the working tree
    what      — the read-back counterpart to zcommit; stricter on purpose — restores ONLY the flow-owned
        snapshot paths (spark + active raven) recorded in the commit's manifest.json; the shared
        project text-source captured alongside them (schemas/zLoom/zUI/routes) is NEVER written back,
        not even with --force — it's a historical record for the agent to read, not a restore target
    which commit — no argument = latest commit for that flow; `--r N` targets cN specifically — zRevive
        doesn't care about "ahead" commits, there's no history to rewind through, just a folder to copy
    conflict  — if a flow-owned file ALREADY exists in the working tree and differs from the target
        commit, zRevive REFUSES by default and names the diverging path(s) + how to proceed (commit
        current state first, or `--force` to overwrite); identical files are a silent no-op
    drift note — a shared file that moved on since the commit is reported as an FYI (never restored,
        never blocks) — e.g. "zViews/zUI.x.zolo changed since c1" is informational only
    list      — `z raven --revive` with no flow name lists every commit across the whole project
        (flow/commit/label/timestamp) — a starting point when you don't remember the exact flow name
    ledger    — `zVersions/revives.csv` — one project-wide row per attempt, success or conflict

options: `zRavenOptions:` / `zMeta:` block at top (all optional)
    stop_on_error: true      — halt on first fail (DEFAULT); false = run all, print full map
    strict: true             — unknown/empty steps fail (DEFAULT); false = allow no-op
    allow_external: false    — zFetch/zOpen same-origin only (DEFAULT); true = cross-origin
    timestamp_shots: true    — mm-dd-HH-MM prefix per shot filename (DEFAULT); false = overwrite in place.
        ON by default so a re-run's shot never silently overwrites the last one in an image viewer/IDE
        preview with zero visual diff to notice
    zshots_retain: 2         — how many recent timestamped runs to keep PER step name (DEFAULT); older
        groups auto-delete after each shot write; set on `zRavenOptions:` or per-step `shot.retain`
    z raven --clear <flow>   — scoped to that flow's OWN zShots/<flow>/ only; other live flows'
        shot folders (e.g. canonical app a dev flow fed into) are untouched by design — the CLI
        prints their file counts as a hint; use `z raven --clear` (no flow) to sweep every live flow
    timeout: (zMeta)         — per-step timeout, seconds
    content_ready_timeout: 12000 — ms zOpen waits for first WS-rendered content before the empty-page
        gate fails it (DEFAULT 12000); raise on a slow/CPU-constrained box or a heavy first render
    zConnect: {ws, http}     — URL overrides for standalone `zraven` entry (ignored by `z raven --run`)

seek_as_need: !authoring a test — only if extending zRaven
    generator  — core/zSys/cli/raven_generator.py (zUI→steps; preserves zFill/zSubmit values; archives) + raven_command.py (--gen/--run/--hint/--commit, revision resolve)
    commit     — core/L4_Orchestration/s_zRaven/zRaven_modules/utils/commit_manager.py (create_commit: gate, snapshot, diff, shots/log copy, ledger)
    clear      — core/L4_Orchestration/s_zRaven/zRaven_modules/utils/clear_manager.py (clear_workspace: commit-match gate, dev-flow removal, orphan zShots sweep, ledger)
    revive     — core/L4_Orchestration/s_zRaven/zRaven_modules/utils/revive_manager.py (revive_flow: commit lookup, conflict gate, flow-owned restore, shared drift note, ledger)
    runners    — core/L4_Orchestration/s_zRaven: cli/cli_runner.py (stdin/stdout, strict leaf) · ws/ws_runner.py (Playwright+WS, `_BIFROST_PRIMITIVE_ORDER`, zScreenshot→zShot, `_capture_failure_shot` on any step fail) · base_runner.py (mode, counters)
    asserts    — assertions/evaluator.py (evaluate_assert dom/style/api/result, evaluate_logger_assert)
    parse+guard— utils/parser.py (parse_raven_file) · utils/validator.py (zUI↔zRaven check, vocab from zlsp token_registry) · utils/viewport.py (sizes, block split)
    orchestrate— runner.py (ZRavenRunner: CLI/WS dispatch, zOpen route table, Data/ isolation) · utils/hint_rules.py (--hint over runs.csv)
