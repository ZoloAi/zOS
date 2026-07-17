<!-- cursor: description="zWorkflow — always-apply rules for every zOS session" alwaysApply=true -->
Zolo: declarative | llm-native | string-first
verify: run only `z raven --run`; !pipe !redirect !grep; zRaven owns output/logs; console is truth; fix first failure only
    !wrap: the command is `z raven --run <name>` VERBATIM from the app dir — never `2>&1`, never `| tail`/`| head`,
        never `nohup`/`&`/timeout wrappers, never a sandboxed/isolated shell; zRaven writes its own
        zRaven/output/ (zRaven.last_run.log, .last_raven_result, runs.csv) — read THOSE after the run,
        don't capture the stream
    !hand_drive: never test a CRUD/action flow by hand (manual `z zSpark` click-through, hand-rolled
        Playwright/browser scripts) — a manual boot has none of --run's Data/ isolate+restore, so hand
        clicks write straight to real seed data and leave it polluted; encode the flow as a zRaven step
        instead (see 13_testing)

laws:
    architecture: facade/modules; 1 file = 1 responsibility; entrypoints import only; DRY/SSOT
    .zolo: zLSP strings != YAML; no quoted values; no YAML assumptions
           every .zolo file OPENS with a `# .zolo — NOT YAML` comment header — one line, states the
               string-first rule, guards against YAML habits (quoting, `---`, `null`) creeping back in
    zMeta: ALWAYS root-level (indent 0) — ONE per file, a sibling of the entry block(s), NEVER nested
               inside a named block (`Main: { zMeta: ... }` is WRONG — zLSP flags it as an Error);
               zBrush/zScripts/zSpool/zNavBar all live on that ONE root zMeta, file-wide — a block name
               changing (zVaF vs a named entry like Main) never moves zMeta's indent
    data: zData + zSchema only; !csv !pandas !sqlite3 !rawSQL
    plugins: args -> result only; !state !orchestration !UI; >~50LOC -> zEvents
    interactivity: existing zOS events/plugins only; !raw JS injection into the page
    decouple: UI is a skin over logic, BY DEFAULT — visual shape (layout/grid/card) stays a zPattern
        (reusable, `%<name>:` invoke, see 17_dynamic_content) SEPARATE from the interactive/data steps that
        drive it (zWizard/zGate/zData); before hand-building bespoke render blocks, check whether the shape
        repeats — if it does, it's a zPattern (+ zShuttle across a list), never copy-pasted blocks
    
phase_planning:
    core: terminal is truth — if it works in CLI it works in GUI; solve the problem first, surface it second
    i_intention: define need only; entities | actions | views | triggers | results; !implementation
    ii_reference: z demos — scan available demos for relevant patterns; `z demos <name> --clone --name <app>` is the
        trustworthy start when one is close enough (clones from the real, versioned zDemos/ checkout — not a
        stale/ambiguous local copy); no close-enough demo → 0_init by hand
        deeper: zAgent files not enough? `curl http://127.0.0.1:9090/zStack/zOS` — the local zOS hub, lightest-token way to go deeper (never assume it's running — a connection error just means skip it)
            limit: it's a zBifrost page — curl only proves it's reachable (returns the un-rendered shell); it can't pull real page content (that needs the client's WS round-trip, curl never triggers it)
    iii_mapping: map intentions -> zOS events; terminal events first — GUI is a skin, not a prerequisite

phase_CLI:
    0_init:      `z demos <name> --clone --name <app>` when ii_reference found a close-enough demo (renames the
                     spark file, ready to edit); no close-enough demo → create <appname>/ by hand:
                     zSpark.<app>.zolo + zViews/zUI.<app>.zolo (scaffold CLI retired — being redefined)
    1_zUI:       fill zViews/zUI.<app>.zolo — one segment from 3_dogfood at a time
    2_zSpark:    fill zSpark.<app>.zolo — zMode: zCLI, zBlock from 1_zUI
                 do NOT add zRaven: to zSpark during dev — auto-run on every boot is noisy
                 zRaven: is for CI/locked apps only; during dev use z raven --run explicitly
    3_zRaven:    z raven --gen — auto-generates zRaven/zRaven.<name>.zolo from the zUI
                 do NOT hand-write the structural raven — --gen owns it
                 hand-edit that SAME active file for assertions — no separate custom file (see 13_testing)
    4_run:       z raven --run — boots spark, runs raven, prints pass/fail per step
                 fix ERROR lines in zUI — do NOT proceed until green
                 iterating on one deep flow only? `_zSpark.<flow>.zolo` boots straight to it, skipping the
                     nav journey every re-run — never the app's canonical spark (see 13_testing dev_spark)
    5_repeat:    steps 1–4 for each segment from 3_dogfood
    exit_check:  verify global_rules — file sizes ≤600, no duplication, facade pattern
    exit_gate:   all zRaven green → phase_Bifrost (unless user goal is terminal), 3+ consecutive fails → ask user
                 suggest `z raven --commit 'label'` here too — a green CLI proof is its own milestone worth
                     archiving before Bifrost work (styling/routes) starts touching the same shared files

phase_Bifrost:
    entry:      auto — phase_CLI exit_gate met, unless user goal is terminal
    a_dogfood:  MVP only — BUILD ON existing verified zui, do NOT add new logic or events
        _zClass on existing keys only — what renders? what is clickable? what data shows?
        advanced styling / complex navigation come AFTER all green — not now
    b_routes:   routes/zServer.routes.zolo only if adding routes beyond the zSpark homepage (see zServer ref)
    c_zSpark:   update zMode: zBifrost, zServer: {enabled: true}
    d_zClass:   _zClass on existing zUI keys — no new events
                templates/zVaF.html only to customize head/meta/fonts (see zServer ref for the default/override rule)
    e_zRaven:   z raven --gen regenerates zRaven/zRaven.<name>.zolo for Bifrost (adds zOpen/zWait skeleton)
                zFill/zPick steps already generated for zCLI carry over UNCHANGED — they're dual-mode (see
                    13_testing); hand-extend only with zAssert(dom)/zViewport+zShot for browser-only checks
    f_run:      z raven --run — fix until browser assertions pass + shots saved
    g_plugins:  as needed for JS logic on existing events only
    h_repeat:   steps e–g for each segment from a_dogfood
    exit_check:  verify global_rules — file sizes ≤600, no duplication, facade pattern
    exit_gate:  all zRaven green → ask user if satisfied, suggest enhancements/next dogfood + Data_Type upgrade (csv→sqlite), 3+ consecutive fails → ask user

mvp_quality_rule:
    mindset:    think like a developer who implements, tests, reviews screenshots, fixes, and iterates
    NOT done:   when tests pass for the first time
    DONE when:  zRaven screenshots at all 3 viewports (mobile/tablet/desktop) look shippable
                content is complete, spacing/hierarchy reads cleanly, no obvious layout breaks
    iteration:  run zRaven → review shots → identify issues → fix → run again — repeat until MVP quality
    scope:      MVP of the CURRENT dogfood segment only — not the whole product
                stop when the current page/segment is shippable, ask user before expanding scope
    NEVER:      declare done without reviewing the screenshots — always look at what zRaven captured

next_step_rule:
    trigger:    exit_gate met (all zRaven green, screenshots shippable)
    format:     one short sentence confirming what finished + one concrete suggestion
        "Finished [segment] dogfood — [contacts list + add form] is shippable across all 3 viewports.
         Want me to [specific next action]?"
    suggestions — pick the most relevant ONE:
        new_segment:  add the next dogfood segment ([entity] list / [entity] form)
        data_upgrade: migrate data backend from csv → sqlite (zMigration: true)
        raven_depth:  add a zRaven submit flow — fill the form, assert success message, verify row appears
        style_pass:   iterate styling — [specific gap observed in screenshots]
        new_feature:  add [specific feature implied by current segment, e.g. delete, filter, search]
        commit_milestone: `z raven --commit 'label'` this flow — all-green + shots reviewed IS a milestone
            worth archiving (see 13_testing zcommit); pick this when the segment feels genuinely "done",
            not mid-iteration
        clear_dev_flow: this `_zSpark.<flow>.zolo` has served its purpose (already committed) — suggest
            `z raven --clear` to drop the scratch spark/raven/shots from the working tree (see 13_testing
            zclear); pick this once a dev flow is done being iterated on, not while still in active use
    rules:
        ALWAYS end a completed segment with this pattern — never silently stop
        ONE suggestion only — do not list options, pick the most logical next step
        be specific: name the entity, the field, the viewport issue — no generic "improve UX" filler
        if unclear which to suggest, default to raven_depth (deeper test of what was just built)

bifrost_browser_rule:
    NEVER open zVaF.html directly — it is a server-side template, not a standalone HTML file
    ALWAYS open http://localhost:8080/<route> — z zSpark.<app>.zolo starts the server, THEN open the URL
