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
    steps     — mode is INFERRED from the primitive (zPick/zFill/zWizard → zCLI; zOpen/zWait/zShot/zClick → zBifrost)
    wrappers  — `zCLI:`/`zBifrost:` still honored; only needed when vocabulary is ambiguous (zLogger-only step, dict zSubmit)
    zSubmit   — scalar value → zCLI stdin; dict {path, gate, value} → zBifrost WS gate
    shared    — `zAssert:`/`zMarker:`/`zLogger:` run in both modes (scope with a wrapper if not intended)
    first     — TERMINAL IS TRUTH: CLI green, then flip to zBifrost (the coat, not a second test)

drive_cli: zCLI step primitives
    zPick: Option            — send that menu option's number (`^opt`, `zBack`, `_`→space work)
    zSubmit: value           — type at the prompt; `$Var` refs resolve from captures
    zFill: {field: value}    — declarative form fill: per field assert prompt → submit value; tuned values survive --gen
    zVar: Name               — on a zSubmit, remember value as `$Name`
    zAllowError: true        — permit an ERROR: line after this submit (default: ERROR fails)
    zExpect: deny            — prove a gate HOLDS: pair with zPick; PASS when denied, FAIL if let in
    zCapture: {var, pattern} — regex output → `$var` (group 1 or whole; ANSI stripped)
    zMenu / zWizard          — containers: nest zPick/zAssert (zMenu) or sub-steps (zWizard)
    zSetup:                  — soft first block (fixtures); failures are ⚠ warnings, uncounted
    zMarker: done            — close stdin, end run; put LAST

drive_web: zBifrost step primitives (Playwright + WS + HTTP)
    zOpen: zSpark            — homepage `/`; or `@.UI.Page` route; or `{type, zLoom|zUI, params}`
    zViewport: desktop       — desktop|tablet|mobile | `[w,h]` | device name; fresh context each change
    zWait: {selector, state} — state: visible|hidden|attached|detached|enabled; timeout ms
    zClick: {selector}       — `button[data-key='X']`, `button:has-text('Label')`
    zType: {selector, value} — `~email`/`~name`/`~uuid`/… generate unique; `$Ref` reuses
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
    how     — a zViewport step then a zShot step; repeat per viewport in ONE browser block
    sizes   — desktop 1280×720 · tablet 768×1024 · mobile 390×844 (`[w,h]`/device name also)
    review  — DONE ≠ tests pass; it's shots that look shippable at all three — LOOK at them
    opts    — full_page, format(png/jpeg/webp)+quality, selector, delay, resolution, burst {every, count}

history: every --gen is reversible — archive + replay
    archive — before overwrite, --gen copies active → {app}/zVersions/tests/zRaven.<name>[uiVer]_rN.zolo (skipped when byte-identical to last rN)
    name    — [uiVer] = source zUIVersion; _rN = revision (1,2,3… per uiVer)
    edits   — active drifted from last archive → --gen prints "manual edits — archived as rN"
    replay  — --run --r N (revision) | --run --v <uiVer> (latest rN for UI) | --v <uiVer> --r N (exact)
    resolve — none → active | --v only → highest rN for UI | --r only → that rN on newest UI
    drift   — --run pre-flights raven `# zRavenVersion:` vs UI zUIVersion; WARNS (not blocks)
    output  — zRaven/output/ (.last_raven_result, zRaven.last_run.log, runs.csv) — what --hint reads
    data    — Data/ snapshot-isolated per run, restored after — no manual reset

options: `zRavenOptions:` / `zMeta:` block at top (all optional)
    stop_on_error: true      — halt on first fail (DEFAULT); false = run all, print full map
    strict: true             — unknown/empty steps fail (DEFAULT); false = allow no-op
    allow_external: false    — zFetch/zOpen same-origin only (DEFAULT); true = cross-origin
    timestamp_shots: false   — dated shot history instead of overwrite
    timeout: (zMeta)         — per-step timeout, seconds
    zConnect: {ws, http}     — URL overrides for standalone `zraven` entry (ignored by `z raven --run`)

seek_as_need: !authoring a test — only if extending zRaven
    generator  — core/zSys/cli/raven_generator.py (zUI→steps; preserves zFill/zSubmit values; archives) + raven_command.py (--gen/--run/--hint, revision resolve)
    runners    — core/L4_Orchestration/s_zRaven: cli/cli_runner.py (stdin/stdout, strict leaf) · ws/ws_runner.py (Playwright+WS, `_BIFROST_PRIMITIVE_ORDER`, zScreenshot→zShot) · base_runner.py (mode, counters)
    asserts    — assertions/evaluator.py (evaluate_assert dom/style/api/result, evaluate_logger_assert)
    parse+guard— utils/parser.py (parse_raven_file) · utils/validator.py (zUI↔zRaven check, vocab from zlsp token_registry) · utils/viewport.py (sizes, block split)
    orchestrate— runner.py (ZRavenRunner: CLI/WS dispatch, zOpen route table, Data/ isolation) · utils/hint_rules.py (--hint over runs.csv)
