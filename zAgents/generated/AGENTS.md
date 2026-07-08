Zolo: declarative | llm-native | string-first
verify: run only `z raven --run`; !pipe !redirect !grep; zRaven owns output/logs; console is truth; fix first failure only
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

---

zSpark: app boot config | one per app | string-first .zolo — !quotes !YAML | zOS speaks back on boot, read console

core: the keys that boot the app
    title:     My App         — display name AND machine identity (slugged → scopes auth/RBAC, API, storage); the one key never omit
    zSpace:    @.             — workspace root every @. resolves from (default: cwd)
    zMode:     zCLI | zBifrost — where it runs: terminal | web GUI; zBifrost = WS bridge to the client, !a server (that's zServer)

address: which screen opens first — read like a street address; target is ALWAYS a zUI.*.zolo
    zVaFolder: @.zViews        — folder (zPath, !trailing-slash)
    zVaFile:   zUI.myApp       — view file (!extension; always zUI.*)
    zBlock:    MyBlock         — entry block inside zVaFile

env: optional, sensible defaults
    zEnv:      development     — loads zEnv.<name>.zolo over zEnv.base.zolo
    zLog:      INFO            — DEBUG | INFO | WARNING | ERROR; z-prefix (zINFO…) adds engine trace
    zLogPath:  @.logs          — zPath

seek_as_need: !boot-critical — pull the reference when you reach the key
    zServer   — HTTP leg: host/port/routes/static (zBifrost only) -> zServer ref
    zSocket   — WebSocket leg the Bifrost bridge rides (legacy alias: websocket) -> zBifrost ref
    zCanvas   — app-wide canvas applied across pages -> zUI ref
    zPersist  — create Apps/{title}/ user-data dir -> Config ref
    zRaven*   — bind a test suite (zRaven, zRavenTimeout, zRavenPort…); !add during dev (noisy auto-run) -> 04_raven
    plugins   — list of .py loaded at boot -> plugins ref

retired: dropped keys — printed as a deprecation warning if still set
    zSwap     — was user-data persistence -> renamed zPersist (unrelated to the `z swap` CLI zero-downtime command)

---

zTypography: the word events | declare what text MEANS, theme handles how it looks | identical in zCLI + zBifrost

pick_one:
    zH0–zH6        — a heading: page title, section header (structure)
    zText          — plain words: a paragraph, label, caption (no formatting)
    zUL / zOL / zDL — a list: bullets / numbers / term-and-definition (structured, not prose)
    zIcon          — a glyph: Bootstrap bi-* icon or emoji, inline or standalone (renders as text)
    zMD            — rich text: bold/italic/code/quotes + headings + inline icons/spans/links, multi-paragraph, all in one
    rule: heading? -> zH | just words? -> zText | a list of items? -> zUL/zOL/zDL | a small glyph? -> zIcon (or <bi-*> in zMD) | words that need shape? -> zMD

zH0–zH6: seven semantic levels — real <h0..h6>, !tags !classes
    short:  zH1: Main Title
    long:   zH2: { label, color, style }
    zH0 — the showstopper above <h1>; zH6 — the whisper. reach for zH1 first, save zH0 for the one hero title
    label:  the heading text — required
    color:  PRIMARY | SECONDARY | SUCCESS | INFO | WARNING | DANGER (ERROR alias) — renders same in zCLI + zBifrost
    style:  full | single | wave | star | hash | plus — zCLI-only flair (= - ~ * # +); browser shows clean text
    _zClass on a heading -> your class wins, default color steps aside

zText: one paragraph — <p> in browser, clean line in zCLI
    short:  zText: your words           — each zText is its OWN paragraph
    long:   zText: { content, semantic, indent, pause }
    \n      — line break inside the SAME paragraph (!new paragraph)
    content — multi-line continuation folds into one paragraph (joined with spaces)
    semantic: blockquote | code | pre | label | div | span — swaps the wrapper tag, !HTML
        semantic: div + _zClass -> a styled container (card/panel with text)
    indent: a number (0, 1, 2 …) — nudge in from the left; both
    pause:  true — zCLI-only, waits for a keypress; rarely used
    color:  PRIMARY | SECONDARY | SUCCESS | INFO | WARNING | DANGER (ERROR alias) — renders same in zCLI + zBifrost

zUL / zOL / zDL: three list events — bullets / numbers / term-and-definition | structured, !markdown text | same in zCLI + zBifrost
    zUL — unordered, bullet markers | zOL — ordered, numbered | zDL — definition, term + description
    items: the entries — required
        zUL/zOL: a list of strings — rich allowed (**bold** `code` [links] all work per item)
        zDL:     {term, desc} pairs — desc = a string, OR a list of strings for multi-paragraph
        nest:    an empty `-` then indented children opens a sub-list (any depth)
    style: the marker — one value, or an array that cascades level-by-level (then cycles)
        zUL: bullet ● (default) | circle ○ | square ▪
        zOL: number 1. | letter a. | roman i.
        dash | none — accepted, but Bifrost falls back to bullet; differ only in zCLI (dash→-, none→no marker)
    _zClass / _id — Bifrost only (e.g. _zClass: zList-inline -> horizontal, marker-less row)

zIcon: a Bootstrap glyph — renders as TEXT, inherits font-size + color of its context | bi-* names from icons.getbootstrap.com
    short:  zIcon: bi-tools
    long:   zIcon: { name, color, _zClass }
    name:   the bi-* icon name — required
    color:  PRIMARY | SECONDARY | SUCCESS | INFO | WARNING | DANGER (ERROR alias) — semantic, same palette as every event
    no default size — inherits surrounding text; size/glow/flair via _zClass (your zBrush; lands on the wrapper <div>)
    inline: <bi-name> inside any zMD string -> icon mid-text (sentence, # heading, list item, cell, quote) — same source as the event
    !inline-in-zText/zH* — those render PLAIN text; a <bi-*> there shows literal. use zMD, or a standalone zIcon beside the text
    emoji:  just type them — accessible label auto-attached; the console gates EVERY glyph to [name] so legacy terminals never crash

zMD: rich text — a whole body of text in one event; same in zCLI + zBifrost
    paragraphs: multi-line folds to one | \n = fresh paragraph | <br> = line break, same paragraph
    headings:   # … ###### inside copy (six levels) — quick title only; real titles -> zH0–zH6 events
    lists:      - * + bullets · 1- a- i- ordered, indent to nest — quick inline list only; standalone -> zUL/zOL/zDL events
    emphasis:
        **bold**     — strong, the word that must land
        *italic*     — soft stress, or a title
        `code`       — mono chip: command, key, filename
        ~~strike~~   — removed / outdated
        __underline__— quiet, formal emphasis
        ==highlight==— marker-pen attention
        > line       — a set-off quote
    inline-html:
        <bi-name>          — Bootstrap icon mid-text (same source as zIcon; works in headings, lists, cells, quotes)
        <span style='…'>   — tint/weight one word; raw-HTML escape hatch, keep light — structural -> a real event or _zClass
    links: [label](href) — href = external URL | internal zPath/route | #anchor (current page)
        target: external -> new tab default | internal -> in place
        {newtab|new-tab|_blank} force new tab | {sametab|same-tab|_self} force same tab | {class} add CSS class | [*](url) footnote marker
        recommend: this is for quick prose links — real navigation (menus/buttons/breadcrumbs/routing) -> zNavigation events; read the Links leaf for how href resolves
    !tables — tabular data is structured -> zTable event (the one block zMD won't draw)
    later (Advanced/RichUI · Markdown II): full outline set, advanced link options

---

zNavigation: how a person MOVES through an app | a menu OFFERS choices, a verb MAKES the move, a zURL is what you press, crumbs are the trail back, a navbar is the same places everywhere | write once → a prompt/menu in zCLI, real links/bars in zBifrost | one engine-trail underneath drives every move, feeds zBack, fills every crumb

menus: add a mark, get a list — no prompt loop to write
    shorthand — `key*: [sibling, sibling]` — `*` makes a numbered menu; the list names which SIBLING keys are options
    `~` prefix — anchored, no Back (`~Main_Menu*`) — entry points you shouldn't step back from
    no `~`    — auto-offers a Back step
    longhand  — `zMenu: {title, zAnchor, options}` — what `*` compiles to; title (prompt) · options · zAnchor (true=no Back · false=Back)
    pick = a STARTING LINE, not a filter — a pick sets WHERE THE RUN STARTS, then the walker keeps going
        pick A → begins at A, falls through to B | pick B → only B (A was before the start line)
        rule — want an option to run ONLY its content? make it NAVIGATE AWAY (verb/block hop), not fall through
    nest      — an option can hold its own menu (nested, no `~` → auto Back) — drill-in/step-out from menus alone

verbs: four moves — where does this take you?
    zAlpha — cross-FILE: a zPath, zOS loads that file + runs from that block (behind menu picks + page buttons)
        zPath — last segment = BLOCK, segment before (after `zUI.`) = zVaFile → Cross Platform owns the grammar
        + a permissions dict → the move becomes role-gated → Identity
    zDelta — same-FILE hop: mark target with `$` (`$Block`); runs it, nothing loads, route NEVER moves; reversible with zBack
    zOmega — land on a zKey, not the top: NOT its own verb — an ADJECTIVE on a zAlpha/zDelta saying WHERE to arrive
        matches a block's DIRECT keys | browser scrolls to it · terminal opens the block at that key, skips above
    zModal — the CALL (alpha/delta are GOTOs): run a block as a DETOUR, auto-return to the firing point on completion
    rule   — different file → zAlpha | a block here → zDelta | an exact key → zOmega riding on one of the two | glance-and-return → zModal

zmodal: a modal is a glance, not a move — forward with auto-back built in
    value forms (first character routes, same as href):
        inline dict — `zModal: {zH2: Hello, zText: ...}` — the dict IS the modal, any block content
        `$Block`    — same-file block (zDelta-style resolve, incl. zUI.<name> auto-discovery)
        `@.zViews…` — cross-file (zAlpha-style zPath)
        longhand    — `zModal: {zUI: <target>, params: {...}}` — dict WITH `zUI:` = target form
    firing seams — a menu OPTION's value (opens on pick, returns to the menu) · a zBtn ACTION (opens on click):
        string action — `action: zModal($Block)` / `zModal(@.zPath)` — rides zBtn exactly like zAlpha(...)/zDelta(...)
        dict action   — `action: {zModal: {zH2: ...}}` — inline content right on the button
    contract — trail-INVISIBLE: no crumb, route never moves, zBack after return acts like the detour never happened
        completion — target finishes (zDialog onSubmit returns / content walks off its last key) → auto-return, caller resumes
        dismiss    — a zBack inside the modal closes it (same return path); pure-content modals gate on `Press Enter to close`
        fired from a `~Menu*` anchor → returns to that menu (drill-in/step-out)
    zLoom — read-only both ways: a $/@ target's file-root zSpool is pre-woven (modal renders data like a page would)
        zModal lives ONLY in zUI pages — never in zLoom/ files (data+shape only, no events)
    terminal — zCLI: a detour walk with the auto-back | zBifrost: a FLOATING overlay (backdrop + card + ×), same grammar
        Bifrost plumbing — dispatch stages the woven block (session `_zPendingModal`, the `_zPendingNavigate` pattern); the bridge
        flushes it as a `render_modal` frame; the client paints it into the overlay and owns dismissal LOCALLY (backdrop/ESC/×)
        — the route never moved server-side, so closing needs no round-trip; a menu-resume walk STOPS at the modal (anchor bounce)

zurl: the rendered, clickable link — what a person presses
    required — label + href; arrives ready, nothing to switch on
    href routing (reads the FIRST CHARACTER, same four ways as verbs):
        `@.zViews…` zPath → another file (zAlpha) · `$Block` → same-file hop (zDelta)
        `#zKey` → in-page anchor (rendered zOmega) · `https://…` → outside address · `#`/empty → placeholder (renders, no-op)
    target   — _self (default) · _blank (external gets rel noopener noreferrer auto) · window (pop-up) · _parent/_top (rare)
        `window: {width, height}` — size for `target: window` only
    properties — color (PRIMARY…, terminal-first) · _zClass (text link; add zBtn → button) · zOmega (land on a zKey) · permissions (RBAC → denied reader sees it DISABLED, not hidden → Identity)
    terminal — prints `[label]` + ASKS: page/hop → `Navigate to: {label}? (y/n)` · external → `Open {label} in browser?` · anchor/placeholder → `{label}? (y/n)`
    note     — navbar items point with `zLink:`; a zURL points with `href:` — same compiler

breadcrumbs: the ENGINE's own trail, surfacing — not a widget you build
    one_trail — every real move is written the moment you LAND; ONE record drives nav, feeds zBack, fills every crumb (a page only READS it)
        zBack — undoes your LAST step, retraces the real path in reverse (never a guessed parent/home)
        reach an earlier crumb (click / pick) → jump straight back, dropping everything after
        browser — the trail rides the TAB: reload keeps it, native Back/Forward stay in step, a 2nd tab keeps its OWN path, close = trail closes
    show — one line `zCrumbs`, one setting `show`:
        session   — `zCrumbs: true` IS `show: session` — the live trail this person walked (zBack retraces); every step, repeats and all
        manual    — `show: manual` + `trail: [zPaths]` (last = THIS page; zOS writes labels); stable every visit
        structure — `show: structure` — reads where the page LIVES (folder+file); move the page, the crumb follows
            parent — a zPath ALREADY ON THE ROUTE → trail starts at its page (trims the front only)
    contract (SSOT) — a crumb ALWAYS comes from a PATH (a zPath you declare or the page's live location); NEVER a hand-typed title or raw filename
    zMenu: true — a MODIFIER, not a show mode — makes ancestor crumbs clickable; rides any declared trail
    rewind ^ — the author-driven twin of clicking a crumb — a bulk-back your PAGE fires (zBack steps ONE key)
        `<key>^: <value>` — sugar for `zCrumbs: {show: none, zBack: <value>}`
        bare key → STRICT in-block rewind (unknown key just re-renders) · zPath → cross-block bulk-back (unwinds to that page)
        rule — a rewind is a BACK action → MUST live where a person PICKS it (menu/button), NEVER an auto-step (loops forever)
        aim the zPath at a page genuinely behind you (else treated as a plain step forward)
    styling — the ribbon won't take its own _zClass → brush a WRAPPER: `.zBreadcrumb` · `.zCrumb` · `.zCrumb-lead` (current) · `.zCrumb-om` (clickable ancestor) · `.zCrumb-ev` (plain)
    knobs — `zCrumbs: true` · show · trail · parent · zMenu · zBack · `<key>^` · header (default `zCrumbs:`)

navbar: the same places on every page — one named list, two skins (bar in zBifrost, menu in zCLI)
    inline — `zNavBar:` inside a block, list names, point each with `zLink: @path`
    zBrand — the name on the left that always goes home (zSpark root); page-level bars only
    convention — a bare top-level name → a file in root `zViews/` (zAbout → zViews/zUI.zAbout.zolo, block zAbout)
        `true` show · `false` keep line but hide · `zLink: @path` off-convention · `Name: @path` value IS target · `https://` external
    zSub — a drop-down: a LIST of child names (convention, one folder down) OR per-child BLOCK (`child: true`/`child: @path`)
    zRBAC — visibility per item, filtered on the BACKEND (CLI+Bifrost agree): authenticated: true/false · require_role: [zAdmin] → Identity
    reset — a navbar pick RESETS the trail (a bar is anchored, no Back): global page bar → FULL reset (new root) · inline block bar → SCOPED reset (keeps its page, clears below — switch dashboard tabs without leaving)
    declare_once — the same grammar can live in `ZNAVBAR` of `zEnv` under a named group (usually `Main`); a page opts in from zMeta: `zNavBar: true` (Main) / `zNavBar: [Name]` → Config / zServer
    styling — an INLINE bar can't take _zClass (renders `.zNavbar-inblock`) → hang the brush on a wrapper: `.zNavbar` · `.zNav-item` · `.zNav-link`
    knobs — zBrand · bare name + true/false · zLink · zSub · zRBAC · _zClass

gate (event): the move where the walk WAITS — hold until the person acts, then carry on
    the gate is an EVENT — a `zBtn` `type: submit` or a whole `zDialog`; the walk HOLDS, steps after don't run until you submit
    use — on the move that must land first (a sign-in, a payment, a confirm)
    NOT an error policy — a step that fails shows its error and the walk carries on (that's zForce, not the gate)
    retired — the old `!` suffix gate is GONE (2026-06); `key!` is a literal key now; gating is an event
    scope — this is the gate's nav-ux face only; the full step model (zHat, zForce, the walk) is the zWizard leaf

terminal: write once, it reads the room
    every move runs in zCLI (a prompt/menu that ASKS) and zBifrost (a real link/bar/clickable crumb) — only the skin differs
    rule — works in the terminal → works in the GUI: same trail, same picks, same destinations

---

zSignals: feedback events — tell the user HOW it went | one message, built-in meaning + colour | coloured line in zCLI, dismissible card/toast in zBifrost | the SSOT forms + dialogs reuse

pick_one:
    zSuccess — it worked          (green)
    zError   — it failed          (red)
    zWarning — proceed with care  (yellow)
    zInfo    — for your info       (cyan)
    zPrimary / zSecondary — brand emphasis, NO status meaning (use sparingly — emphasis, not feedback)
    rule: a real outcome? -> success/error/warning/info | just drawing the eye? -> primary/secondary

shorthand: the quick way — message as a plain string
    zSuccess: Record saved.     — the string IS the content; colour comes from which event you picked
    rule: reach for shorthand for a one-off line; switch to content: when it needs flush or more

zSignal: the longhand — choose the mood at runtime, not by key
    zSignal: { type, content, flush }
    type:    success | error | warning | info | primary | secondary — picks the mood when your DATA decides it
    rule: same render as the shorthands — zSuccess == zSignal type: success

props:
    content — the message shown — required (string)
    type    — which mood (zSignal longhand only)
    flush   — true -> pops as a timed top-right TOAST, slides away (click × to close); Bifrost-only, terminal keeps the line

fires:
    on load   — a signal in the chunk shows when the chunk renders
    on action — tuck one in a button's `action:` -> fires on click (the feedback a form/dialog raises when it acts)
    rule: action takes ONE event — a shorthand (zSuccess) or the zSignal longhand

canonical_classes: written by Bifrost (zbase theme) — override = restyle EVERY signal, never add by hand
    .zSignal             — the card (base)
    .zSignal-success | -error | -warning | -info | -primary | -secondary — the mood tint
    rule: zCLI renders the same meaning as a coloured line; flush is ignored there

seek_as_need: !needed to raise a signal — meet them again where feedback is raised
    forms submit / dialogs act -> that feedback IS a signal, reused -> Forms ref

---

zControls: three controls, one choice each | where an input TYPES, a control CHOOSES — press · pick · tick | write it once -> a prompt in zCLI, a real control in zBifrost | a control only TAKES the press — a container decides what happens

the_three: pick the control that fits the choice
    zBtn      — press to DO a thing (save, delete, deploy)
    zSelect   — pick from a list (dropdown · radio · multi)
    zCheckbox — a box to tick (a plain yes / no)
    rule: a thing happens -> zBtn | one of a known few -> zSelect | true/false -> zCheckbox

zbtn: a button does a thing
    shorthand: zBtn: Save Changes — the words after the colon become the label
    longhand: zBtn: { label, action, color, type, _zClass }
        label  — icon-aware: a bi-* name shows a Bootstrap Icon, alone or beside text (bi-gear Settings | Delete bi-trash)
            whitespace-joined tokens ONLY — zolo is declarative, not arithmetic string concat: never `bi-gear + Settings`
            (the `+` isn't a `bi-*` token, so it renders as a literal stray "+" character next to the icon)
        action — the &. call fired on CLICK (see zFunc) — we don't teach actions here, just that the key exists
        color  — semantic fill: primary · secondary · success · danger · warning · info
    no_action: a zBtn with no action still returns a value — true on click (Bifrost) / y (terminal) — enough to gate a step
    submit_reset: type: submit / reset are CONTAINER-only — meaningless on a lone button (nothing to submit/reset)
        they live where a container owns them — Forms / zWizard
    terminal: a button is just a y / yes confirm

zselect: one choice in three shapes
    options — the list to pick from | default — the value(s) pre-selected (a LIST when multi)
    shapes:
        dropdown (default) — tucked behind a click in Bifrost
        type: radio        — every option laid out in the open
        multi: true        — pick more than one; hands back a LIST
    inline_flags: tag an option right in the list, no extra keys
        [default] pre-selects it | [disabled] greys it out, out of reach — options: [Free, Pro [default], Enterprise [disabled]]
    terminal: every shape reads the same — a numbered menu (multi just lets you pick more than one)
    rule: dropdown vs radio is purely a Bifrost look; the answer is the same either way

zcheckbox: the simplest control — yes or no
    shorthand: zCheckbox: { prompt } — the question beside the box
    shape_it:
        checked  — start it ticked (default off)
        required — must be checked to pass (enforced on the container's SUBMIT, not at render)
        disabled — shown but locked; in a wizard it resolves instantly with its checked value, no click
        prompt / label — the words beside the box (label wins if both set)
    vs_zbtn: a checkbox is a VALUE (stores true/false that flows on) | a zBtn is an ACTION trigger (makes something happen)
        rule: something is SET -> zCheckbox | something HAPPENS -> zBtn
    terminal: a (y/n) prompt

who_submits: a control does NOT decide what's next
    on its own a control just TAKES the press — no submit appears by itself
    a zBtn can carry its own action; a pick or a tick is handed to the box around it — zDialog (one screen) / zWizard (step by step) -> Forms
    rule: validation / required enforce on the container's submit, never at control render

make_it_yours: two levers, same as everywhere
    _zClass on one control -> a one-off skin (your brush) | override a canonical class in CSS -> every control at once
    canonical_classes: written by Bifrost (zbase) — never add by hand
        button -> .zBtn (the button) · .zBtn-primary … .zBtn-info (per color) · .zBtn-outline-* / -pill / -sm / -lg (modifiers)
        choice -> .zSelect (dropdown/multi box) · .zLabel (prompt) · .zForm-check-group (radio set) · .zForm-check (one row) · .zForm-check-input (the dot) · .zForm-check-label (option text)
        check  -> .zForm-check (the row) · .zForm-check-input (the box) · .zForm-check-label (the words) · .zForm-check-disabled (a locked row)
    where_zClass_lands: not the same per control — scope your selector to match
        zBtn      — adds to the button's class list (your class sits alongside .zBtn)
        zSelect   — lands on the <select> (dropdown/multi) AND on the .zForm-check-group (radio set)
        zCheckbox — lands on BOTH the <input> and its .zForm-check row; the box is element-typed by zbase
            so scope to input.yourclass (target only the box, keep the row's flex) and use !important to beat the element rule
    terminal: none of these classes apply in zCLI — they're the Bifrost skin only

terminal: write once, it reads the room
    the same control runs in zCLI (a prompt that waits) and in Bifrost (a real button / select / checkbox) — no second version
    rule: if it works in the terminal it works in the GUI — the choice is the same, only the skin differs

---

zInputs: one event, a type for each question | write zInput once -> a prompt in zCLI, a real form field in zBifrost | an input only COLLECTS — it never submits; a container does

shorthand: the quick way — the label as a plain string
    zInput: Full name     — that one line is the whole field; the words become its label
    rule: reach for shorthand for a plain one-off; switch to the longhand to add a type, hint, default, or required

longhand: zInput: { prompt, type, … } — shape the field
    prompt      — the label beside the field
    type        — which family (default text) — see type_families
    placeholder — faint hint text inside the box
    default     — a value already filled in
    required    — true — can't be left blank (a promise checked on SUBMIT, not at render — needs a container)
    readonly    — true — shown but not editable (terminal auto-fills + moves on)
    disabled    — true — greyed out, inactive
    prefix / suffix — a chip hugging the box ($ before, @company.com after); value = prefix + typed + suffix
    datalist    — a list of suggestions; autocomplete in browser, numbered list in terminal — free text always wins
    constraints — the raw-rule escape hatch (minlength/maxlength · min/max/step · pattern) -> see constraints
    _zClass     — your class on the field -> reskin; the declaration stays untouched

type_families: same zInput, four leaves — pick the type that fits
    TextFields — text · email · url · tel · number · password · search · textarea (the everyday typed fields)
    Files      — type: file (+ multiple: true) — native picker in browser, a checked path in terminal
    Dates      — date · time · datetime-local · week · month — native pickers in, clean ISO out
    Color      — type: color — a swatch in browser, a hex code in terminal
    rule: typed words? -> TextFields | a file? -> Files | calendar/clock? -> Dates | a colour? -> Color

text_types: add type: to a plain field
    text (default) | email / url / tel (right keyboard + format check) | number (digits + steppers)
    password (masked everywhere — incl. terminal) | search (clear button) | textarea (multi-line box)

files: type: file
    multiple: true — accept a batch; comes back as a LIST (terminal: comma-separated on one line)
    terminal: asks for a zPath, verifies it EXISTS before accepting — @.folder.file (workspace) | ~.folder.file (home)
    path: extension optional (one match -> found; add .png only to pick between siblings); one bad path rejects, retry

dates: calendar / clock types
    returns ISO always — YYYY-MM-DD | HH:MM:SS | YYYY-WNN — no parsing on your end
    format: per-field override of the terminal prompt format (machine default e.g. [DD/MM/YYYY]); the value is still ISO

color: type: color
    default: #5CA9FF — a starting swatch; returns a tidy LOWERCASE hex either way (#5ca9ff)

constraints: the ESCAPE HATCH — the raw rule for when no type/property says it for you | enforced on SUBMIT (needs a container): browser checks natively, terminal re-asks until it fits
    minlength / maxlength — fewest / most characters allowed — text · textarea
    min / max            — lowest / highest value allowed — number · range · date/time
    step                 — the legal increment between values — number · range · date/time
    pattern              — a regex the value must match exactly — single-line text fields only
    rule: presets are sugar over these — email is just a pattern zOS wrote for you; no preset fits -> write the pattern yourself
    rule: same shape as _zClass (look) / _GUI (behaviour) — named event first, raw hatch only when you run out
    a constraint rides on ANY field, with or without a type, standalone or inside a container -> Forms

who_submits: an input does NOT decide what happens next
    no submit button appears on its own — a field only collects
    the container owns submit: zDialog (one screen) | zWizard (step by step) -> Forms
    rule: required / validation enforce on the container's submit, never at field render

make_it_yours: two levers, same as everywhere
    _zClass on one field -> a one-off skin (your brush) | override a canonical class in CSS -> every field at once
    canonical_classes: written by Bifrost (zbase) — never add by hand
        .zLabel         — the label text
        .zForm-control  — the box itself (input / textarea / select / swatch frame)
        .zRequired      — the red * marker on a required field
        .zInputGroup + .zInputGroup-prefix / -suffix — the affix wrapper + chips
    browser_parts: not classes — the one handle the browser gives you (reach via pseudo / zOS variable)
        files  -> ::file-selector-button (the Choose File button)
        dates  -> ::-webkit-calendar-picker-indicator — retint via --zinput-picker-filter
        color  -> ::-webkit-color-swatch (+ -wrapper) — size/shape/glow via --zswatch-* (--zswatch-size/-radius/-shadow/-gloss)
    !datalist popup — the native suggestion list isn't yours to style (no class/pseudo); need branded -> custom widget

terminal: a console asks, a browser renders
    every field is a prompt that waits for an answer, validates, then moves on (password masks; file checks the path)
    none of the canonical classes / browser parts apply in zCLI — they're the Bifrost skin only
    rule: write the field once — it reads the room (prompt vs form field) with no second version

---

zForms: a dialog is a conversation — collect a screen of answers, then act | zDialog gathers inputs + controls and, onSubmit, hands the lot to an action | write it once -> field-by-field in zCLI, a real form in zBifrost | inputs/controls only ASK; the zDialog owns the submit

zdialog: the first event that COLLECTS
    everything before it (inputs, controls) only ASKS one thing — a zDialog gathers a whole screen of them
    title    — the form's heading
    fields   — the things to collect (see fields)
    onSubmit — the action run when the form is submitted (see result)
    runs the whole exchange: zCLI asks field by field, the browser shows one real form — same block, both surfaces

fields: each entry is a bare key or a small dict
    bare    — email — the key IS the field (auto-detects type by name: email/password/tel)
    dict    — {zConv: age, type: number, label: Age} — spell it out
    identity: zConv is the canonical key; name / field are accepted aliases
        the key becomes zConv.<key> on submit — {zConv: age} -> &...(zConv.age) reads what you declared
    type picks the widget; omit it and the field name decides (email/password/tel), else text

vocabulary: a field carries the SAME keys it has on its own leaf — a zDialog just gathers them
    inputs  — text · email · url · tel · number · password · textarea · color · date · file -> Input Events
    controls— select (dropdown/radio/multi) · checkbox -> Control Events
    extras ride along unchanged: placeholder · default · required · readonly · disabled · prefix/suffix · datalist · options · multi · accept
    _zClass — lands on that field's own input/select/textarea (text/number/select/etc); radio/checkbox groups don't forward it yet
    rule: don't re-teach a field here — its own leaf owns it; the zDialog only collects it
    every answer lands in zConv as a string (a LIST for a multi-select)

constraints: the raw-rule escape hatch, on a field inside the dialog
    minlength/maxlength · min/max/step · pattern — enforced on SUBMIT -> Constraints
    rule: a type/property first; a constraint only when none of them says your rule

submit_reset: the zDialog owns its button — you never write one
    onSubmit IS the Submit — you declare only WHAT it does, not the button
    zReset: true — adds a Reset beside it (zCLI re-asks every field; Bifrost clears to defaults; nothing is sent)
    these are the submit / reset button types -> Buttons — now in the container that gives them meaning

confirm: a zDialog with NO fields is just a confirm button
    leave fields off -> one button, an onSubmit, nothing collected — "Delete this?", "Send it?"
    the action still fires and still returns its green/red line; there's just no zConv to hand over
    the pre-composed "button that does a thing" Buttons points at

result: onSubmit returns a RESULT — success or failure
    success -> a green line, the form clears for another go | failure -> a red line inline, the form STAYS, input intact
    same envelope on both surfaces (ZResult.success / ZResult.failure) — the form just renders what the action returns, never asks why
    average_joe: green line when it works, red line with your words still in the box when it doesn't — nothing breaks, nothing lost
    log_severity: a business failure (success:false) is an EXPECTED outcome — surface it inline, never a console error (that's reserved for a real exception)

onward: onSubmit is a DOORWAY — the same hook, bigger jobs
    onSubmit is always a dict — ONE key naming the subsystem, never a bare `&.` call
    `onSubmit: { zFunc: &.calc.add(zConv.a, zConv.b) }` — the simplest action, a plugin call
    zWizard  — carry the answers into a multi-step flow
    Identity — sign someone in / change the session (also what lets a submit navigate to a new page or refresh the navbar)
    zData    — save the answers as a row (see schema): `{ zData: {action: insert, model: @...} }`
    rule: zDialog's grammar never changes — only the action on the other end gets bigger

schema: let a zSchema write the fields
    model: @.models.zSchema.X + fields: [name, email, password] — name the fields; the schema supplies each one's type, label, rules
    the dialog is otherwise IDENTICAL — same onSubmit, same zConv
    defining schemas, the validation they carry, and saving to a real backend -> Data hub (Advanced), taught in full there

zconv: the bag of answers
    every field's value is gathered under its key — name -> zConv.name
    zConv is what onSubmit hands the action — &...(zConv.name) reads one, the action sees them all

terminal: write once, it reads the room
    the same zDialog runs in zCLI (a prompt per field) and in Bifrost (one real form) — no second version
    rule: if it works in the terminal it works in the GUI — same answers into zConv, only the skin differs

---

zData: describe what to remember + the rules around it — zOS keeps it | one schema = the shape, one action saves/reads/changes it | table born from schema on first write, migrations grow it later | write once → same on csv/sqlite/postgres, zCLI + zBifrost

schema: one small file — what to keep + its rules
    shape   — a `zSchema` = a `zMeta` block (where/how stored) + one named block per table holding FIELDS
    !SQL    — you describe the shape; zData sets up storage, checks each value in, builds forms, rejects misfits
    move    — same schema on every backend; `Data_Type` is the only line you touch to switch stores
    rule    — describe the destination, let zData find the road

zmeta: settings up top — where + how kept
    Data_Type:  csv | sqlite | postgresql — the day-one line; change the word later, rest keeps working
    Data_Path:  @.Data — store dir (csv/sqlite; ignored for postgres)
    Data_Label: — store's human label / file stem
    Schema_Name: zSchema.<name> — self-ref the registry resolves the model by
    zMigration: true + zMigrationVersion: vX.Y.Z — opt into migrations + stamp each change
    journey — csv (see every row) → sqlite (solid) → postgresql (outgrown); each hop is one line, never a rewrite

types: each field has a KIND that does quiet work (coerce value, pick the input, reject misfits)
    str (default) · int · float · bool (true/1/yes/on ↔ false/0/no/off) · date · time · datetime (`default: now`)
    uuid (auto when blank — v4 default, v1 via `version`) · json (parsed+validated, textarea) · blob (bytes inline on sql, sidecar file on csv)

identity: the primary key — every row's name tag
    pk: true — the one field that points at exactly THAT row
    auto_increment: true — on an int pk, hands out 1,2,3… (never blank/repeated)
    composite — `primary_key: [flight, seat]` at table level pins a row by two fields

rules: type says WHAT KIND, rules say whether it's any good — zData runs EVERY rule + returns EVERY problem at once
    field-level  — required: true · unique: true (queries backend) · enum: [a,b,c] (renders picker)
    rules: block — min_length · max_length · min · max · pattern (regex, full match) · pattern_message · format (email/url/phone/date/time/datetime/uuid)
    rules: more  — validator: &.plugin.fn (returns (ok,msg)) · error_message · max_size + blob_input (raw|base64|path) · version (uuid v1/v4)
    field extras — default: <value> (pre-fill/empty) · nullable: false (reject empty even if not required) · immutable: true (write-once) · transform: trim|lowercase|uppercase|slug|capitalize · zHash: bcrypt (scramble on insert via zAuth, plaintext never stored)
    table-level  — zConstraints → unique: [a,b] (combination unique) · check: <zFilters expr> (cross-field)

relationships: two tables hold hands — foreign keys + on_delete
    fk       — `foreign_key: customers.id` (short `fk`) — a field holding another table's pk; can't hold an id that isn't there
    on_delete— what happens to children when the parent is deleted (unsaid = safe):
        restrict (default) — refuse while children point at it · cascade — remove children then parent
        set_null — clear child's link, keep child · set_default — reset child's link to default, keep child
    depth    — delete-time effect demoed in Advanced Writes; READ joins in Advanced Queries

enforcement: two guards side by side (only matters if you poke the raw store by hand)
    in the DB    — pk, single-field unique, required, fk + on_delete
    by zData in  — everything in `rules:`, plus enum, nullable, immutable, transform, zHash, composite zConstraints
    takeaway     — write THROUGH zData → everything gets checked

insert: save a row — `action: insert`
    form    — `action: insert` + `model:` (arms coercion+validators) + `data:` (dict `field: value`, usually from a zDialog `onSubmit`)
    fill    — `data: {name: zConv.name, age: zConv.age}` (`zConv.<field>` = collected value)
    guard   — all declared types/defaults/required/unique enforced in; bad value bounces before it lands
    hooks   — onBeforeInsert: &.func (modify/abort) · onAfterInsert: &.func (side effects)
    depth   — many rows, upsert, INSERT…SELECT, RETURNING → Advanced Writes

auto_ddl: the table builds itself on first write
    first write to a missing table reads its zSchema + provisions storage (fields, types, defaults, rules)
    nothing created until that write — no setup/migration first; sql → real table rules, csv → same checks as rows flow
    reshaping an EXISTING table (add column, evolve) = migrations, below

read: ask for rows — `action: read` — zTable draws them
    minimal   — `action: read` + `model:`; queries source, hands result to zTable (sensible defaults, no display config)
    painter   — the table only SHOWS what came back; sort/filter/page/dress freely, no row at risk
    zFilters  — narrows WHICH ROWS (a WHERE dialect, no SQL): `score > 88 zAND age >= 35` (zAND/zOR/zNOT/zIN/zBETWEEN/zLIKE/zNULL/zKNOWN)
    fields    — `fields: [name, score]` narrows WHICH COLUMNS (genuinely narrower rows); omit for all
    shape     — order_by: field ASC|DESC · limit: N + offset: N ((page−1)×page_size) · distinct: true
    zTable    — inline `zTable: {limit: 5}` steers the draw; captions/pagination/styling → Tables leaf
    depth     — full dialect, joins, aggregates, windows, subqueries, CTEs, set ops, search → Advanced Queries

update: fix the row you point at — `action: update`
    form  — name `fields:` changing + `values:` + `where:` for which rows; only listed fields move
    ex    — `fields: [status]` + `values: [zConv.status]` + `where: id = 1`; same checks as insert re-run on edit
    set:  — richer than flat value: per-row zCase, computed `$inc`/zExpr, cross-table `from:` → Advanced Writes
    rule  — no `where:` updates EVERY row — always name the target

delete: remove what you name — `action: delete`
    form  — no fields/values; `action: delete` + `where:` for which rows
    ex    — `where: id = zConv.id` (any field works: `where: department = zConv.department`)
    confirm — `fields: []` renders a single Confirm button against a pre-baked `where:` (e.g. `active = false`)
    rule  — no `where:` deletes EVERY row + permanent — read first
    per_row — a bare `zBtn.action:` is a CALL, not a full zData block — a dynamic-row one-click delete (`where: id = %item.id`)
        needs a `@zfunc` (inject `data`, call `data.delete(table, where=...)`) → zFunc leaf; a `zDialog.onSubmit` CAN
        hold a real `zData: {action: delete}` block directly (no plugin needed) since a dialog submit is a full dispatch
    depth — on_delete cascades, soft delete, subquery/cross-table/time-based/RETURNING → Advanced Writes

migrations: evolve the shape without losing data — edit the zSchema to what it SHOULD be, zData finds the smallest safe path
    opt_in — frozen until `zMigration: true` + a `zMigrationVersion` stamp; bump on each change; unflagged skipped
    flow (per enabled schema):
        1 discover     — keep zMigration:true schemas, skip the rest
        2 short-circuit— schema hash == last applied → up to date, nothing runs
        3 introspect   — read store's ACTUAL shape (csv headers · sqlite PRAGMA table_info · pg information_schema), reconcile lossy sql types
        4 diff         — new table→CREATE · new col→ADD · removed→DROP · changed type→MODIFY · `renamed_from:`→RENAME · `indexes:`→CREATE/DROP INDEX · `constraints:` by kind; rows preserved
        5 apply        — run change set (unless `--dry-run`); a new col's `backfill:` fills in the SAME txn; logged to `__zmigration_<table>`
    rename   — `renamed_from: qty` → true RENAME COLUMN (sql in place, csv header); harmless to leave in
    backfill — populate a new column at birth, computed in zOS layer (same on every backend), idempotent (only cols ADDED this run, only EMPTY cells)
        `backfill: free` (literal) · `%name` (copy a column) · `{concat: [%first, " ", %last]}`; needs single-col pk; companion to `default:` (constant) vs backfill (derived)
    indexes  — add/remove an `indexes:` entry → next migrate CREATE/DROP by name (reads live indexes; declared+existing = no-op; pk/unique auto left alone; csv no-op)
    constraints — `constraints:` by kind: unique folds into index pipeline (idempotent, csv no-op); fk/check need ALTER TABLE ADD/DROP (postgres native, sqlite guards w/ message, csv no-op)
    backend_change — change `Data_Type` → zData MOVES data: export all tables to in-memory rows, open new adapter, recreate from schema, coerce, bulk-insert, validate counts (indexes don't ride — re-declare + migrate)
    cli      — `z migrate <app> --dry-run` (preview) · `--plan`/`--sql` (print DDL) · `--schema <name>` · `--auto-approve` · `--history` · `--rollback` · `--version <vX>`
        rollback — csv-first (restores each table from last backup); sql `--rollback` is a non-destructive guard (recover from DB backup or re-declare + migrate forward)
    rule     — golden habit: `--dry-run`/`--plan` before you ever apply

terminal: write once, it reads the room
    same `zData` block in zCLI (prompts + auto-drawn table) and zBifrost (form + page table) — no second version
    depth — sharper queries → Advanced Queries · heavy writes → Advanced Writes · many-at-once/all-or-nothing → Bulk & Transactions · store layer+DDL+views → Backends

---

zTable: one event for tabular data | declare columns + rows, theme draws the grid | styled <table> in zBifrost, fixed-width ASCII in zCLI — same declaration

core: the two keys that make a table
    columns: [name, role, status]   — the headers across the top
    rows:    list of rows below, in column order
    rule: pure display — describes WHAT the data is, never how to draw it; !DB access (that's zData)

rows: two shapes, same table
    list:   [Alice, admin, active]            — values in column order; quick, hand-typed
    object: {name: Alice, role: admin}        — each value named by column; the shape zData returns
    rule: list for fixed tables | object when you style cells OR rows come from data

label: optional chrome above the grid
    title:   Team                  — short heading over the table
    caption: Active members, today — sub-line under the title (what/when/source)

cells: rich text, no quoting — type it straight into the value
    **bold** *italic* `code` [links](url)  — same markdown as everywhere; real <strong>/<a> in browser
    zCLI: formatting applies; a link prints as `label (url)` — reference only, never a prompt
    rule: zTable is flat — !row-click !navigation; need action? pair with zURL / zBtn beside it

merge: repeat a value down a column without retyping
    ^^   — carries the cell above down; true rowspan in browser, clean repeat in zCLI

windowing: trim or page long lists
    limit:  4        — show N rows, append "… N more rows" footer
    offset: 2        — start further down (skips first N); pair with limit = a window
    zPages: true     — with limit, draws a pager bar (First/Prev/Next/Last + jump-to)

styling: two levers, they stack
    _zColumn: { score: col-spotlight }   — classes onto that column's th + every td under it
    cell:     {val: 98, _zClass: zText-success}  — per-cell; val shows, _zClass styles (object rows only)
    _zClass:  on the table -> lands on the inner <table> (zTable + your modifier); reskin the whole grid
    _zRows:   { odd, even, first, last }  — pattern classes onto <tr>
    rule: column = base, cell = override layered on top; color tokens = zText-success|warning|danger|info

canonical_classes: written by Bifrost (zbase theme) — your global override surface, never add by hand
    zTable-container  div   — whole unit (title + table + footer)
    .zTable-container h4     — the title
    zTable-caption    p     — caption line
    zTable-responsive div   — scroll wrapper for wide tables
    zTable            table  — the grid (borders, spacing, header tint)
    zTable-more       p      — "… N more rows" footer
    zTable-nav        div    — the zPages pager bar
    rule: _zClass/_zColumn tag ONE table from .zolo | override a canonical class = restyle EVERY table

seek_as_need: !needed to draw a table — pull when you reach it
    zData — fetches/validates live rows, hands result to zTable -> 03_data ref
    rule: one clean split — zTable draws the grid, zData brings the rows

---

zMedia: three events for things you show | declare WHAT + describe it, theme renders the right thing | real media in zBifrost, an openable block in zCLI

pick_one:
    zImage — a picture you own (any aspect ratio)
    zVideo — a clip you own (real player, native controls)
    zEmbed — a piece of the OUTSIDE web (YouTube/Vimeo/Spotify/Maps) from its ordinary link
    rule: own file, still? -> zImage | own file, moving? -> zVideo | someone else's page/player? -> zEmbed

shared: the shape every media event takes
    src      — what to show: a @.path file (zImage/zVideo) or a normal https link (zEmbed) — required
    alt_text — short description — REQUIRED, !optional; accessible by default + read by search
    caption  — optional line under it (credit, date, context)
    _zClass  — your class on the wrapper -> reskin (rounded, frame, glow, tilt); the declaration stays untouched
    short:   zImage: @.path  |  zEmbed: https://…   — one-line form when alt_text isn't needed
    spaces:  a path may contain spaces (My Reel.mov) — resolved + served fine (URL shows %20); tidy names just read cleaner
    gotcha:  a raw "/static/…" string is NOT the same as a @.path — it only resolves once a
        zServer is actually listening (needs a live host:port to become a URL); a @.path resolves
        via resolve_zfile in EVERY mode (real OS path in zCLI, web path in zBifrost) — always
        author media fields as a dotted zPath (@.static.photos.sunset.jpg), even when the value
        flows through zData/CSV rows into %item.<field>, never a hand-typed "/static/…" string

server_contract: media needs zServer LISTENING to be openable at all, not just paintable
    zCLI + media = `zServer: {enabled: true}` from phase_CLI onward — NOT just phase_Bifrost's
        c_zSpark step; zOpen's server-path detection (the terminal y/n gate) has nothing to route
        an absolute path to without it, and a raw web-relative src has nothing to route to either
    proof   — a live zServer means the served route is genuinely curl-able (200, correct
        content-type/size) — real verification, not an assumption that "it probably renders"

zImage: a still — real <img> in browser, openable block in zCLI
    keys:  src | alt_text | caption | _zClass
    aspect ratio: never reshaped — square / wide / tall / cinematic all shown as-is
    !sizing in the event — frame / shadow / tilt ride _zClass (your zBrush)

zVideo: a clip — real <video> player with native controls in browser
    keys:  src | alt_text | caption | _zClass   (same shared shape)
    poster:   a still shown before play (the cover image)
    loop:     true — restart when it ends
    muted:    true — silence the track (for a NON-autoplay player)
    autoplay: true — starts on load; browsers require muted, so zVideo MUTES it for you (don't also write muted)
    pattern:  ambient background clip = autoplay + loop (muted auto) | normal player = leave them off (+ poster)

zEmbed: the outside web — no iframe markup by hand
    src: the page's NORMAL link (youtube.com/watch?v=…) — zOS rewrites to the embeddable form per provider
    keys:  src | alt_text | caption | _zClass   (same shared shape)
    safe by default: only known providers (YouTube / Vimeo / Spotify / Maps) framed locked-down; unknown URL -> plain clickable link, never a silent iframe
    where: decided on the SERVER, not the browser — operator sets ZEMBED_MODE in zEnv: safe (allow-list, default) | trust (any https, internal app) | off
    !frameable (Stripe / PayPal / WooCommerce) -> !zEmbed; they ship a JS SDK widget -> Advanced/SDKWidgets

terminal: shared behaviour — a console can't paint media
    prints alt_text + path/address + caption, then asks: Open? (y/n) — opens in your system viewer / player / browser
    web app: y opens in YOUR new browser tab, never on the server — the media events read the room
    open_prompt: false — just print the details, no question (logs / reports)
    rule: nothing opens on its own — it always asks first

zopen_vs_media_open: two DIFFERENT gates that look similar — don't conflate them
    media event's own open — zImage/zVideo/zEmbed's terminal y/n gate (open_image/open_video/
        open_embed under the hood) — Bifrost-SAFE: delegates to the visitor's own browser (new
        tab), never touches the server; this is what the "terminal" row above describes
    bare `zOpen(...)` action — a zBtn firing the standalone dispatch primitive directly
        (`action: zOpen(%item.file)`) is a DIFFERENT code path (zOpen.handle) — local-machine-only,
        FAILS CLOSED for any Bifrost-origin request (TRUST_MODEL: a remote click must never open
        files or launch apps on the server host) — it has no client-delegation fallback
    rule: want a Bifrost-safe "open full-size" / "open original" button? use zURL/zLink
        (`href: %item.file, target: _blank`) — a real anchor, not a bare zOpen(...) action;
        reach for zOpen(...) only for genuine zCLI-only tooling (opening a local report, a config
        file) that will never run under a Bifrost visitor

---

zWizard: a handful of named steps, run in order | each step does its thing + tucks its answer under its own name — later steps reach back for it | ask, branch, loop, confirm — all just steps | write once → a prompt per step in zCLI, a progressive form in zBifrost

zwizard: named steps, run top to bottom
    block   — `zWizard:` children are STEPS, each a named key holding an event (input/button/text/function)
    run     — walked in order; smallest real wizard = 3 steps (ask · gate · say it back)
    name    — a step earns memory only by having a NAME; a bare unnamed event renders but the hat never holds it
    forward_only — a wizard only walks FORWARD; submit a gate → locks, won't fire twice; go again = send the walk back ON PURPOSE (looping)
    rule    — one key = one step; reach for a wizard when later steps LEAN on earlier answers (a flat screen of fields is a zDialog → Forms)

zhat: read a prior step's answer
    file    — finishing a step drops its answer into the hat under that step's NAME (no variables, no wiring)
    read    — `zHat[Step_Name]` (recommended) | `zHat[0]` by position
    bundle  — a step holding named sub-steps: `zHat[Get_Details][City]` · `[Get_Details][0]` · `[Get_Details]` (whole); bare inner events → by position only
    fresh   — read at the LAST moment → always the freshest answer
    miss    — a name never filed → NOTHING back, never an error

looping: a result that NAMES a step jumps there
    mechanic— every step hands back a result (its zForce); if that result IS a step name, the walk goes there
    no verb — the engine recognizes the name; `action: Get_Name` on a zBtn, or a function returning a step name, land the same
    result-driven — it's the RESULT that jumps, not the button (menu pick / computed return land identically)
    free_text — typed free-text NEVER jumps (kept as the answer, never read as a step name)
    restart — jump to the FIRST step = restart the whole wizard
    bundle  — jump to a bundle → re-runs start to finish; you can't jump INTO it (READ into a bundle, never WALK)

menu: let the PERSON pick the next step
    same jump as looping, human-driven | shorthand `Start*: [Basics, Network, Finish]` — a `*` key + SIBLING step names
    pause → pick → jump → stride ON (fall-through): pick Network → Network + everything after · pick Basics → all three
    scope — options name same-level siblings; never reach a sealed bundle; free-text doesn't count
    rule  — a menu is the looping rule with a person at the wheel; want the wizard to decide? that's `zGate:`

zGate: a step that runs only when it earns its turn
    `zGate: <predicate>` beside a step's event — tested against the hat on arrival; false → step skipped WHOLE (nothing shows/lands)
    self-judging — the test reads the hat, so each step decides from what earlier steps gathered (no branches, no else)
    canonical — same `zGate:` a page uses to gate by WHO's asking (→ Advanced RBAC); on a step it reads the hat instead of the session
    read    — `%zHat.Track` by name · `%zHat.0` by position · `%zHat.Details.0` into a bundle (by position)
    predicate_language (a declared dict, read against the hat):
        yes/no  — filled `{%zHat.Track: zSet}` · empty/never-answered `{%zHat.Track: zNotSet}` (or `{zNull: true}`)
        equality— matches `{%zHat.Track: both}` · not-equal `{zNot: {%zHat.Track: talks}}`
        order   — `{%zHat.Age: {zAbove: 18}}` · `zBelow` · a range `{zBetween: [30, 35]}`
        member  — `{%zHat.Track: {zIN: [talks, both]}}` · negate with `zNot`
        combine — all of `{zAll: [...]}` · any of `{zAny: [...]}` · nest freely (two keys on one leaf AND automatically)
        literals— text `both` · numbers `18` · lists `[a, b]`
    fences  — a declared predicate, NOT Python eval: no calls/.methods/attributes/arithmetic; `zAbove`/`zBelow`/`zBetween` compare as numbers, equality/`zIN` by value; malformed or never-answered → reads FALSE + skips (never an error, fail-closed)
    one_step_one_event — `zGate:` is a sibling MODIFIER key beside the step's single real event (`zGate: {...}` + `zSelect:` / `zText:` / …), never a second event: the step still tucks exactly ONE answer under its own name, and `zHat[Step]` on a gated step reads that SAME plain answer a plain step would give — never a wrapper, never the gate's own verdict
    legacy  — a bare `if: '<python-ish expr>'` string still lowers to this same predicate (deprecation warning, removed in a future release) — author new steps with `zGate:`

bounds: a wizard stays PUT — intra-flow moves work, hops out don't
    honored — zBack · zCrumb · menu pick (intra-flow)
    skipped — a page/block hop (zLink, zDelta, zDelegate, navigate) mid-flow = quiet no-op (ignored, not harvested, one debug line)
    terminal— `stop` / `exit` are the sanctioned enders
    two_layers — zLSP WARNS at edit time; the engine only tolerates at run time (never crashes)
    rule    — stay inside to keep the flow; leave on purpose with stop/exit

gate: where the walk WAITS for you
    a gate is an EVENT — a `zBtn` `type: submit`, or a whole `zDialog`; the walk HOLDS until the person acts, then carries on
    use     — when later steps lean on something you must do first (confirm a cart, sign in, pick)
    plain   — a `zInput`/`zText` never holds (collects/shows, strides on); a zDialog gates a whole SCREEN of fields → Forms
    not_error — a step that FAILS shows its error + the walk carries on (that's zForce, not the gate)
    retired — the old `!` suffix gate is GONE (2026-06); `key!` is a literal key; gating is an event

transaction: all-or-nothing data steps → lives in zData
    `_transaction: true` at the `zWizard:` root wraps its `zData` steps as ONE transaction (commit on success, roll back on error)
    each step names its table by the live alias `model: $teams` (not `@.models…`) so all steps share one connection
    scope   — commit/rollback lifecycle, ACID per backend, the $alias rule → Advanced › zData › Transactions

engine: what RUNS the steps
    you author the EVENT (named steps, zHat, zGate:, gates); the run model (zEngine/zWalker/zStride/zForce) → Advanced › zEngine
    a step is made of OTHER events, sequenced: field → Input · button/action → Control · function return → zFunc · multi-field → Forms

terminal: write once, it reads the room
    same zWizard in zCLI (a prompt per step) + zBifrost (a progressive form, a gate that holds the line) — no second version
    rule — works in the terminal → works in the GUI: same steps into the same hat, only the skin differs
    multi_gate — a chain of gates (zBtn submit after zBtn submit, e.g. Track_Next → Q1_Next → Q2_Next) reveals ONE segment
        per resolve, stopping at the NEXT gate each time — same as the CLI's one-prompt-at-a-time walk; a later
        zFunc/zGate step only runs once the walk genuinely reaches it, never eagerly on an earlier gate's resolve

---

zFunc: one key holds a CALL | point at a function, zOS runs it — no imports, no wiring | Python or JavaScript, same call | runs as the block renders (an action waits for a click)

the_call: a zFunc key holds a call, not a value
    `zFunc: &.calc.add(2, 3)` — zOS reaches the block, runs the function, moves on
    `&` = "a function" (like `@.`/`~.` = "a file")
    rule — happen as the block appears → zFunc | wait for a click → a zBtn action

two_sigils: where zOS looks for the function
    `&.file.func()`        — a plugin in your plugins folder (zOS searches)
    `&.folder.file.func()` — folder-aware: each dot a folder, last segment the function
    `@.path.file.func()`   — exact location by zPath (`~.` = home) — no searching
    rule — a dropped-in plugin → `&.` | a known path → `@.`/`~.`

where_&_looks: the search order for a bare `&.name`
    root → utils → plugins — FIRST match wins (so `&.calc.add` finds `plugins/calc.py` unnamed)
    rule — keep names unique across those folders, or use `@.` to be exact

arguments: pass values in the ()
    text `&.demo.greet('zOS')` · number `&.demo.report(6, 7)` · live data `%data.x` · a prior return `zHat[Step]`
    rule — simple literals for a one-off; `%data`/`zHat` when the value comes from the page

return_value: what comes back is reusable
    a return is captured as zHat — weave it into a later step or into text (a print stays behind, only return travels)

the_engine: the wizard reads what each KEY returns
    zOS walks the block tree; each key returns something the engine reads to decide what's next; zFunc is no different from zH1 except YOU own the return
    reserved_returns — FLOW CONTROL, not data:
        zBack (step back) · zLink (follow a link) · error (surface + carry on) · stop/exit (shut the app DOWN)
        rule — never return one as data; return a dict/number/text instead
    rules_of_thumb — value back → return it · pure side effect → leave the return empty · avoid stop/exit as a casual return

languages: same call, two runtimes
    `.py` — runs INSIDE zOS (injection + side effects, the in-process default)
    `.js` — a Node subprocess (pure logic, gated; browser-only JS errors there)
    bifrost — a client-side `.js` ACTION can run in the browser with `this` bound to the button (GUI effects)
    rule — data/logic with zOS access → Python | pure compute or browser GUI → JavaScript

signals: a return surfaces as feedback
    a plain return → a zSignal (success by default, the detail as message); an error (raise/"error") → the error signal (terminal prints + skips on, Bifrost graceful)
    rule — don't hand-roll feedback; return the outcome, let the signal render it → zSignals ref

builtins: dot-less `&` tokens — filled in, not run
    `&zNow` — date+time per zConfig (`&zNow('date')` · `&zNow('time')` · `&zNow(custom_format='yyyy-mm-dd')`)
    `&zUUID()` — a fresh UUID v4
    tell — dot-less is a token (`&zNow`), dotted is a plugin call (`&.calc.add`); drops into any content/label/zMD, resolves at load

zos_plugin: want the contract handled for you? the SDK on top of `&.`
    one `@zfunc` decorator does TWO jobs — inject what you name + turn your return into the outcome
    injection — name a parameter, get the live connection point (no imports, no session walking):
        user — signed-in identity (user.id, user.require() gates a step → 401)
        files — uploads (files.image('field', max_mb=5) → validated image or 4xx)
        transfer — blob storage (transfer.store(bytes, key=...) → where it landed)
        data — zData CRUD (select/first read, insert/update/upsert/delete write; Rows: row.id)
        session | log | params | zos — live session, logger, raw args, the framework
        rule — a caller-supplied arg WINS over an injected provider
    contract — what you RETURN tells zOS what happened:
        truthy → success · falsy → retriable failure · "error" → hard abort
        `raise ZAbort("...", status=4xx)` → structured ZResult with that code (API answers right)
        an unhandled exception → logged + contained as "error" (a crashing plugin never takes the page down)
    async — decorate an `async def` and nothing changes (injection + contract carry through the await)
    seek — full door → Advanced › Extending › zos-plugin

sdk_widgets: the SECOND embed lane — a provider that refuses to be iframed
    the choice is theirs — "embed this URL" → zEmbed (lane one) | "add our script, call our SDK" → SDK widget (lane two)
    some (PayPal, Stripe) forbid framing → they ship a JS SDK that draws itself into a slot
    three_parts — script (name the plugin in `zMeta.zScripts`) · slot (a plain block with a class the plugin recognizes, empty to start) · plugin (a `.js` in `@.plugins` that loads the provider's SDK + mounts it)
    boundary — the provider's code lives in `@.plugins`, NEVER inside zOS (zOS serves `/plugins/` + runs what zScripts named)
    frame_gate — most SDKs frame their own origin, blocked by zServer's CSP until opted in: `zEnv ZEMBED_SDK: [paypal]` unlocks vetted origins (known: paypal, stripe; unset → none, fail-closed)
    seek — full door → Advanced › Extending › SDK Widgets

zfunc_vs_action: same grammar, different MOMENT
    zFunc runs on RENDER (as the block appears) · a zBtn action runs on CLICK (waits for the user) · same `&.` call — pick the moment, not a syntax

async: it just works
    write the function `async` and `await` inside as normal — zOS handles the loop, no special wiring

terminal: write once, it reads the room
    same zFunc in zCLI (in-flight call, console feedback) + Bifrost (toast/GUI) — no second version
    rule — works in the terminal → works in the GUI: the call is the same, only the skin differs

---

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

---

zServer: one key turns the terminal app into a website | folders→URLs, files mount, misses show YOUR page, every response guarded, 2nd visit instant, live edits drop no one, actions open to machines | still DECLARED, never plumbed | write once → identical in zCLI + zBifrost; the live socket is zBifrost (its own subsystem)

enable: one key flips app → website
    key      — `zSpark.zServer.enabled: true` then `z zApp` — server starts, reads `zViews/`, serves it
    !wire    — you never write a route table or web-server config; the runtime finds pages + answers requests
    rule     — the app is the app; zServer only changes HOW it's reached — flip the key, rebuild nothing
    template — `templates/zVaF.html` (app-authored Jinja): the ONE zWalker/template chrome, OPTIONAL override
        — missing file → zServer renders a BUILT-IN default (same `<zVaF></zVaF>` + bifrost-client `<script>`), logs INFO, `z raven --run` warns `⚠ No templates/zVaF.html`
        — physical file ALWAYS wins — author once per app to customize `<head>`/meta/fonts, then treat as chrome (do NOT rewrite per segment)
        — must mount `<zVaF></zVaF>` (the only required tag) + load the bifrost-client `<script>`
        — dev: point the script/CSS at a local checkout via `ZBIFROST_CLIENT_BASE` + `zServer.mounts` (zEnv) instead of the CDN — zero npm/CDN propagation lag; unset in prod to fall back to the CDN `@1` channel
        — routing (zVaFolder/zVaFile/zBlock) still comes from zSpark; the template is chrome, never page content

going_live: shipping = a ONE-WORD change
    runners       — zServer ships two, you NAME which (never call directly): `dev` (built-in, instant restart, loud logs, localhost default) | `waitress` (production, pure-Python, real traffic)
    pick          — `ZSERVER_TYPE: waitress` (unset → dev) — nothing else changes
    parity        — both answer through the SAME pipeline (routing, RBAC, private-file block, styled errors); waitress swaps TRANSPORT not rules
    per_env       — settings stack: `zEnv.base` → `zEnv.development` → `zEnv.production` → `zSpark` (final say + names active env)
    selector      — `zEnv: development` in zSpark = the whole build↔live switch
    holds         — dev: `ZOLO_LOGGER: zDEBUG` (loud) | prod: `ZSERVER_TYPE: waitress` + `ZOLO_LOGGER: PROD` (quiet) + storage
    address       — `HTTP_HOST`/`HTTP_PORT`, most-specific first: zSpark → zEnv → DEFAULT 127.0.0.1:8080; usually set in zEnv.base
    localhost     — dev-only reach; in prod the public `https://` edge sits IN FRONT + forwards, so keep binding locally
    the_flip      — 1) `ZSERVER_TYPE: waitress` (+quiet) in prod file · 2) `zEnv: development`→`production` · 3) restart
    habits        — machine paths + secrets in the env file, never a page; dev is plain http by design; prod https handled in front (no certs in zOS)
    escape_hatch  — run servers for a living? expose `zServer.get_wsgi_app()` to nginx/gunicorn/container; everyone else flips ZSERVER_TYPE

routing: your folders become the routes — take the wheel only when you want
    contract  — routes live in `zServer.*.zolo`; zServer finds EVERY one (app root + `routes/`) + merges at boot — no import/registry, the `zServer.` prefix IS the contract
    smart     — default: declare the anchor ONCE, folders fan into URLs
        `routes: { /: { type: zSpark } }` — serve this app's home (borrows the spark's page)
        walks `zViews/` → every page a URL: `zUI.Home.zolo`→`/` · `About/zUI.About.zolo`→`/About`; `_`-folders + `error/` stay private
        omit `/` and zServer adds the anchor for you — true zero-config: NO `zServer.*.zolo` file at all needed
        just to serve the zSpark homepage; add one only when you need routes BEYOND that (extra pages/webhooks/API)
    manual    — a URL + a `type:` (reads like Flask):
        `zWalker` — one page: name `zVaFolder`/`zVaFile` (+opt `zBlock`)
        `static`  — a disk file untouched: `file: public/landing.html`
        `template`— your Jinja from `templates/`: `template: about.html` (navbar+styles still injected)
    param     — a URL carrying a value, one `%placeholder`:
        `{ type: zLoom, zLoom: @.…spool, zUI: @.…PublicProfile }` — reads matching row + renders, else 404
        capture vs read — `%username` in URL = CAPTURE (routing) → read back as `%route.username` (zLoom)
    endpoint  — a URL that is NOT a page (webhook/CLI/service), answers JSON: `{ type: zAPI, kind: zFunc, handler: &.zpush.push }`
    blueprints— split by concern (`zServer.routes.zolo` + `.api.zolo` + `.themes.zolo`); all registered+merged, live on next reload
    catalog   — `zSpark` (home `/`) · `zWalker` (one page) · `zLoom` (page+row) · `zAPI` (JSON from action/plugin) · `static` (disk file) · `template` (Jinja)
    !scope    — `zProxy` (hand to ANOTHER hosted app) is hosting-level → Advanced › Hosting
    retired   — dropped `content`/`json`/`form`/`dynamic`/`redirect` (2026-06); standalone `type: zFunc` route (2026-07, now zAPI + zFunc handler kind)

mounts: routes answer with PAGES, mounts answer with FILES — a prefix → a folder
    idea      — one promise: THIS prefix lives in THAT folder; `/static/logo.png` → `static/logo.png`, content-type guessed, bytes sent (no render)
    overlap   — longer prefix wins (specific beats broad)
    reserved  — always on, un-repointable: `/static/`→`static/` · `/templates/`→`templates/` · `/zViews/`→`zViews/` (client fetches screens)
    conditional— mounted only if folder exists: `/styles/`→`styles/` · `/plugins/`→`plugins/` (so `_zScripts: some.js` → `/plugins/some.js` just works)
    custom    — `zServer: { mounts: { downloads: @.downloads, shared: ~/shared-assets, vendor: /opt/... } }` (`@.` root · `~` home · abs); same block in zSpark/zEnv
    guard     — point a mount at static/templates/zViews → REFUSED + warned (config can't hijack asset roots)
    never_served — zServer reads env/keys/db/source to RUN, refuses to hand them back:
        PATHS (`models/`·`routes/`·`certs/`·`Data/`·`zEnv.*`·`zSpark.*`·`.git/`) · DOTFILES (any segment starting `.`) · TYPES (`.py`·`.zolo`·`.yaml`·`.key`·`.pem`·`.db`·`.sqlite`)
        golden — zEnv is a secret vault → NEVER a URL; `../` traversal refused; exception: `zViews/` `.zolo` ARE served (public UI by design)

errors: a miss shows YOUR page — one zolo file per code
    convention— make `zViews/error/` + drop a file per code; served the instant it exists (RESERVED folder, not browsable)
    files     — `error/zUI.404.zolo` · `zUI.403.zolo` · `zUI.500.zolo`
    renders   — SAME walker as every page (navbar/zBrush/styling), sent with the real HTTP status
    rules     — block name is FREE (renders file's FIRST top-level block; name it `NotFound`, a bare number isn't a valid key); `zMeta` sets title + navbar
    codes     — `404` Not Found · `403` Access Denied (RBAC role missing) · `500` Server Error · `502` Bad Gateway (hosted app failed) · `503` Warming Up (hosted app booting)
    fallback  — skip a code → plain built-in page; custom file UPGRADES it (brand 404/403 first)
    offline   — server ANSWERS 404/403 = real error, styled page; only a DEAD socket triggers the client's offline notice

safety: baseline rides every response — you wrote none of it (identical dev + prod, one SSOT)
    headers   — always, no opt-in: `X-Content-Type-Options: nosniff` · `X-Frame-Options: SAMEORIGIN` · `Referrer-Policy: strict-origin-when-cross-origin`; request-built header values stripped of CR/LF (no response-splitting)
    cors      — OFF (same-origin only); opt in ONE origin `ZSERVER_CORS_ORIGIN: https://app.site.com` (or `zServer.cors_origin`), NEVER `*`; preflight answers the EXACT verbs routes accept
    framing   — no site-wide CSP by design (CDN client+theme+inline would break); always-on CSP is `frame-src` ONLY, mirrors `zEmbed` allow-list (`ZEMBED_MODE` → Media › Embedding); per-route can go stricter
    health    — `GET /zhealth` → `200 {status: ready, routes: N}` (booted + can serve, not just port-open); LBs send users only on 200; also gates the zero-downtime swap

caching: 2nd visit instant — browser keeps what's unchanged, zServer says what changed
    wire      — ETag (per-version fingerprint from content/mtime) + 304 check (unchanged → `304`, zero bytes); static files 304 on revalidate; PAGES always rebuild fresh + ETag but never 304 (never stale)
    parse     — zOS keeps PARSED pages in memory (zLoader cache); first visitor warms, rest ride free
    policy    — prod defaults: static 1h/shareable · API 5m/private · pages+templates always re-checked · favicon 1d
    dev       — NOTHING cached while building (no ghost changes); tightens once live
    proofs    — parse cache: `&.demos.cache_probe.run()` cold ~8ms → warm ~0.4ms (~20x) · wire cache: Network panel static `304 · 0 bytes`

lifecycle: start / change / stop — without dropping anyone
    single_process — HTTP + the one Bifrost WS bridge share ONE process (same view); scale by running MORE copies behind a LB
    boot      — pick runner, bind address, REGISTER (port+name in a pidfile) so `z reload` from another terminal finds this instance
    soft_reload — everyday: edit a page, reload, site keeps serving (no error/logout)
        refreshes AUTHORED half, rebuilt aside + atomically swapped: pages(`zViews/`) · patterns+spools(`zLoom/`) · routes+zAPIs(`routes/`) · schemas(`models/`, defn only — stored-shape change needs `z migrate`) · config(`zEnv`, re-injected)
        NO reload: plugins(`.py`) hot-reload on next call · styles/static/templates served from disk each request
        trigger — `z reload` from a 2nd terminal · a tooling signal · `Ctrl+R` in the server; one server → reloads it, several → numbered pick (or `--port <n>`)
        CANNOT move — the bound PORT + zOS's own code (baked at boot) → those need zSwap
    zSwap     — deeper: the CODE ITSELF changed (new zOS version/patched engine)
        `z swap` REPLACES the process: fresh copy co-binds SAME port (`SO_REUSEPORT`), waits its `/zhealth`, hands over, retires old (new pid, in-flight finish on old, sessions on disk → all stay signed in)
        `z swap` (pick if several) · `--port 9090` · `--all` (every local instance) · `SIGUSR2`; Windows → restart
        vs `z patch` — swap RE-LAUNCHES what's on disk (installs nothing); patch INSTALLS (via `uv`); `z patch --live` = install then swap `--all`
        rule — new code already on disk → `z swap`; still need to fetch → `z patch --live`
    resilience— reload hitting a syntax error keeps the previous route table + reports "aborted"; a swap that won't come ready is REAPED, old keeps serving; worst case = "change didn't apply", never "site down"

zapi: your buttons as an API — a TRANSPORT ADAPTER, not a second codebase
    what      — the action already reads/writes/runs a plugin; zAPI points HTTP at that handler; flip a flag → route registered at boot, action unchanged
    enable    — add `zAPI` to any event that has a handler: `onSubmit: { zAPI: true, zData: { action: insert } }` (still a form, now also an API); `zAPI: {method: POST}` overrides; `zAPI: {autoConnect: false}` = WIP
    discovery — boot scanner walks zUI, looks in FOUR event keys — `onSubmit`·`onClick`·`onLoad`·`onChange` — for a `zAPI` flag beside a handler
    path      — DERIVED not written: `{prefix}/{app}/{file}/{block}` → `/api/zCloud/Contacts/Add_Contact` (prefix `/api` default; app from spark; file from zUI stem; block from action key)
    method    — inferred: `read`/`search`→GET · `insert`/`create`→POST · `update`→PUT · `delete`→DELETE · `zFunc`→POST; override with `method`
    envelope  — success `ok: true` + fit: read/search GET 200 `{ok, data:[], count}` · insert POST 201 `{ok, action, result}` · delete DELETE 200 `{ok, action, deleted}`
    gap       — NOT uniform yet: transport/auth errors return bare `{error}` (+status), flow failures carry `message`; a single `ok: true|false` everywhere is the direction
    kinds     — the handler behind the adapter: `zData` (declarative read/write, verb inferred) · `zFunc` (plugin call `&.plugin.fn`, Py or JS) · flows (a `zLogin`/`zDialog` fronted directly; zLogin verifies headless → API + page sign in the same)
    explicit  — no page (CLI/webhook): declare it, still `type: zAPI` + `kind: zFunc` + `handler`; the door is always zAPI (zFunc = handler kind, never a route type)
    auth      — same-origin call from your page RIDES the session; machine endpoint gates on a key → set `auth` + `auth_model`, pass `X-API-Key`/`Bearer`; fails CLOSED (missing→401, unknown→403, auth w/o auth_model→refused) → Advanced › Identity
    boundary  — the live two-way socket is NOT zAPI — that's zBifrost (Advanced)

---

zGate: one word puts a doorman on any page/link/button/route — checks WHO's asking before the thing renders | server-side, so a hidden item can't be poked by a hand-built request — real, not a curtain | write once → identical gating in zCLI + zBifrost | zGate = the VERB (every yes/no), zRBAC = the identity QUESTION; sign in with zLogin, out with zLogout — ALPHA

three_whos: keep them straight — access control is only about the THIRD
    owner     — who the zOS install belongs to (set once, clears the watermark) → Foundations › zAuth (`z login`/PAT)
    session   — the visitor passing through NOW (guest or signed-in, one tag per visit) → Sessions leaf
    app_users — the MEMBERS of the app YOU built, each carrying a `role` — what zGate/zRBAC decides on
    rule      — owner ≠ session ≠ app users; zGate never touches who owns the instance

verb: ONE gate verb answers every yes/no — you write the rule, zOS enforces on the backend
    `zGate:` — the single block for every gate (auth `authed`/`role`/`require`); the same verb powers wizard `if:` + value comparisons (zLoom → Grammar › Wizard)
    identity — the doorman hands identity questions to the RBAC trust engine, which reads the LIVE session (`zGate.py` → `zAuth.check_zrbac`)
    legacy   — an older `zRBAC:` block is the verb's previous name; auto-lowers to `zGate` + logs a one-time nudge; write NEW gates as `zGate:`
    rule     — no permissions tables / role rankings; the wired model is session-only, exact-match

knobs: lines inside one `zGate:` block — fail ANY posted rule → turned away
    authed: true       — signed-in only
    authed: false      — signed-OUT only (the "guests only" — great for a Login link)
    role: [zAdmin]     — only these role(s); a LIST = any ONE gets in
    require: {tier: pro}— check ANY visitor attribute; must match (a list = membership)
    combine — stack lines → AND; fancier logic speaks `zAll`/`zAny`/`zNot`, but most pages need ONE line
    onDenied— a COMPANION BESIDE the block, never inside: `onDenied: {zLink: @.zViews…}` where to send someone turned away (a reaction, not a question — nesting it breaks the gate)

where: post the doorman at the SMALLEST door — same block, four homes
    page       — top of a zUI block, guards the whole view
    route      — in `routes/` (`zServer.*.zolo`), checked BEFORE any file opens
    nav_item   — under a navbar entry, the link only APPEARS for the allowed
    action_row — on one button/menu item, hidden AND refused for everyone else
    rule       — server-side: a hidden item can't be triggered by a forged request

denial: two refusals told apart
    not_signed_in — walked to the login page; default door set once in `zEnv` (`ZAUTH_LOGIN_ROUTE`), `onDenied` overrides per gate
    wrong_role    — NOT sent to login (already inside); a quiet 403, without revealing which role was needed, unless the gate sets `onDenied`

roles: the names are YOURS — no fixed zOS role list
    define   — name roles in your own `zSchema.roles`; `role` checks the visitor's `users.role` against your names
    example  — zCloud uses zAdmin/zEditor/zBuilder/zViewer/zGuest/zAgent (its set, not zOS's); yours might be owner/member/billing
    matching — EXACT by name; list several → any one qualifies; NO ranking (a senior role clearing a junior gate just lists both) — `role_checker.py`, session-only
    maturing — ONE role per visitor today; multi-role (`user_roles`) on the roadmap

login: `zLogin` = the front desk turning a guest session into a signed-in one carrying a role — one block, no plugin code
    grammar  — a `zLogin:` block IS a zDialog whose submit runs the zAuth `zLogin` action (renders form, verifies, writes session) — `action_login.py`
    props    — model (user schema, required) · fields (order, e.g. `[email, password]`; `inputs` aliases) · title · zAPI: true (web form can post) · onSuccess (a zEvent, usually a zLink redirect) · zApp (label wording only)
    automatic— from `model` alone finds the table + identity field (email/username), bcrypt-checks LOCALLY against your ledger (password never lands in the session), stamps the tag
    writes   — ONE flat `session["zVisitor"]` `{authenticated, id, username, role, api_key}`; the `role` comes from the user's record — the SAME value `zRBAC`'s `role` gate reads (one SSOT)
    persist  — a durable identity token → stays signed in across reload/new tab (cookie seam → Sessions); logout clears it
    single_identity — one signed-in identity per visit; `zLogin: myapp` vs reserved `zLogin: zolo` check the SAME ledger + write the SAME session (keyword only changes welcome wording)
    scope    — APP-USER sign-in, NOT the instance owner (`z login`/PAT → Foundations › zAuth)

logout: `zLogout: <app>` is the mirror
    wipes `session["zVisitor"]` to blank + clears the durable token (reload won't bring them back), then lands home — `action_logout.py`
    gate the LINK with `zGate: {authed: true}` so only signed-in visitors see it

proven: exercised by a fresh isolated app (`Tests/zRBAC_app`, Bifrost)
    click gate matrix — every gate × guest/viewer/editor/admin: each role sees exactly what it should
    exact-name matching holds — one role in, others out
    concurrent mixed-role stress — many roles at once, ZERO cross-session bleed
    caveat — ALPHA: a clean lab run isn't a production promise; a doorman letting the wrong person through is a BUG worth reporting

where_it_lives: trace a piece
    zGate.py (`core/L3_Abstraction/n_zLoom/`) — authored verb + lowering (legacy `zRBAC:` / wizard `if:` → one IR)
    check_zrbac (`core/L2_Handling/f_zAuth/.../logic/rbac/`) — trust engine: reads live session, honours authed/zGuest/role/require ONLY
    role_checker.py — exact-name match, session-only, no hierarchy/level
    action_login.py / action_logout.py (`f_zAuth/.../actions/`) — writes + clears `session["zVisitor"]`
    recap — 1) three whos (this = app users) · 2) one verb `zGate:` (auth → RBAC engine) · 3) knobs authed/role/require, onDenied a SIBLING · 4) four homes, server-side · 5) roles yours, exact-match, one per visitor · 6) zLogin/zLogout write the tag the gate reads

---

zDash: a dashboard you don't build, you ASSEMBLE | point it at a FOLDER of pages you already wrote + list them, it wires the rail, links, and panel switching | two faces: numbered menu in the terminal, tabbed sidebar in the browser | a compiler one level up — builds on all the other events

core: the block — four keys
    type:    sidebar             — layout shape; `sidebar` = left-rail-plus-content
    folder:  @.path.to.panels    — where the panel pages live (`@.` path)
    sidebar: [Overview, Stats]   — the panels, IN ORDER; each name = a page in `folder`
    default: Overview            — which opens first; omit → the FIRST in the list

shape: a zVaFile block, string-first .zolo
    zVaF:
        zDash:
            type:    sidebar
            folder:  @.zViews.myApp.panels
            sidebar: [Overview, Stats, Settings]
            default: Overview

panels: each name in `sidebar` is its OWN complete zUI page
    resolve — `Stats` + `folder: @.zViews.myApp.panels` → `folder.zUI.Stats` (block also named `Stats`)
    body    — ordinary Grammar; a panel renders fine standalone (zDash just borrows it)
    zMeta   — OPTIONAL per-panel, dresses the rail item:
        title:       Stats         — friendly name (rail + numbered menu); DEFAULTS to panel name
        icon:        bi-graph-up   — a Bootstrap `bi-*`, same vocab as zIcon/zMenu (glyph in browser, `[name]` in terminal)
        description: Platform stats— hover tooltip + accessible label (browser)

faces: one block, two renders — never branch on zMode
    zCLI    — a NUMBERED menu; one panel at a time; loops until you type `done`
    bifrost — a tabbed SIDEBAR; panels lazy-load on first click; narrow screen → menu drawer
    rule    — TERMINAL IS THE TRUTH; the browser is the skin

rbac: panels gate themselves
    how  — a `zRBAC` block at the panel's root: `authenticated: true` | `require_role: zAdmin`
    rail — panels a visitor can't reach are DROPPED before the rail draws
    real — data access underneath is enforced regardless; rail filtering is the polite front

custom: two style levers that NEVER overlap
    content — style the panel in its own file with its own `zBrush`
    shell   — `_zClass` on the `zDash` → `.zDash-container`; target `.zDash-*` to restyle rail+frame
    theme   — `.zDash-*` defaults built from `currentColor` (self-balance light/dark) — keep overrides the same

seek_as_need: only if extending the widget, not authoring
    zCLI engine  — core/.../e_zDisplay/zDisplay_modules/system/system_event_dashboard.py (panel discovery, zMeta load, numbered-menu loop, `done` exit, per-panel RBAC filter)
    bifrost render— zbifrost-client/.../composite/dashboard_renderer.js (sidebar/tabs, lazy load via `execute_walker`, mobile drawer) + zbase.css §10 (`.zDash-*`)
    icons        — panel `icon:` is a `bi-*` via IconMapper/IconRenderer SSOT (`[name]` terminal, `<i class="bi bi-*">` browser)

---

zLoom — dynamic content: mark a spot with `%` and zLoom weaves in what's LIVE, REPEATED, or COMPUTED | a value always has a declared source — one sigil covers them all | declared, never hardcoded | write once → resolved before the render split, identical in zCLI + zBifrost

from_jinja: same jobs, one sigil
    `{{ x }}` output      → `%token`   (spool — a live value)
    `{{ x | f }}` filter  → `%x | f`    (zDye — a finish)
    `{% macro %}` reuse   → `%name:`    (zPattern — a shape)
    `{% for %}` loop      → `zShuttle`  (one shape across a list)
    `{{ a+b }}`/ternary   → `zKnot`     (a value computed in place)
    `{% if %}`/tests      → `zGate`     (its own subsystem — Identity/gating)
    `{% set %}`           → `zVar`      (a durable value)
    skipped — `{% raw %}` (a `%word` needs no escape; single-pass) · `extends`/`block` (every leaf already extends the runtime shell)

the_sigil: the whole subsystem is one character — `%`, read by POSITION
    value  `%token`  → a live VALUE, woven at render time (spool · dye · knot)
    key    `%name:`  → a reusable SHAPE, woven at load time (pattern · shuttle)
    miss   — a token that finds nothing is LEFT LITERAL in text (a visible clue) / resolves to nothing in a decision — never a crash
    single_pass — a token INSIDE a resolved value is never re-scanned (user data can't smuggle a second token — safe by construction)

spool: where a live value comes from — the reel a `%` thread pulls off
    `%data.<name>.<field>` — read a field off a named reel (the dotted path digs into the record)
    declare — ALWAYS a file under `zLoom/spools/` (each top-level key IS a reel); a block opts in with `zMeta.zSpool: [name]`
    no inline form — `_data:` (a sibling on the block) is RETIRED; every read, even a one-off used by a single
        block, gets its own `zLoom/spools/` reel — one declared-source mechanism, no shortcut duplicate
    ambient (always carried) — `%session.*` · `%auth.*` · `%route.<param>` (request-scoped) · `%item.<field>` (loop row) · `%var.<name>` (durable)
    full ref— `@.zLoom.spools.zUI.<file>.<reel>` to point at the exact def
    boundary— zLoom owns the binding grammar; `zData` ONLY runs the query; the raw row executes server-side, never ships to the browser
    rule    — a value ALWAYS has a declared source (one sigil covers a DB read, session, route param, loop row alike)
    migrate — a reel's `fields:` is a hand-written list, NOT auto-synced to its model — a schema migration that adds a
        column (see zData migrations) is invisible to the page until the matching reel also lists the new field

dye: finish a value on its way to the page — the `|` pipe
    `%value | dye` — send through a step; chain freely (`%x | trim | title`), left-to-right
    set — default(text) · upper · lower · title · trim · truncate(n) · round(n) · date(fmt)
    default — runs BEFORE the literal-on-miss rule, so it rescues missing/blank (never a real `0`/`false`)
    unknown — `| typo` left as plain text (a clue), never silently eaten
    rule — a dye only FINISHES one value, never fetches (the reel is the spool, the finish is the dye)

pattern: a shape you write once and reuse — `{% macro %}` / `{% include %}`
    define — under `zLoom/patterns/` (each top-level key IS a pattern); a `%<param>` marks a slot
    invoke — a `%<name>:` key (KEY position) with slots as children → expands IN PLACE at LOAD time
    slots  — a value EXACTLY `%param` is replaced whole (scalar OR a whole block subtree); `%param` inside a longer string is textual
    passthrough — a `%session.*`/`%data.*` inside a pattern is NOT a slot (left for render)
    fails open — unknown `%name:` left as-is + warning; a missing slot leaves its `%param` literal

shuttle: one pattern across a whole list — `{% for %}`
    `zShuttle: {zSpool: <list reel>, zPattern: <name>}` — one copy per row
    auto-fill — reads the pattern's slots, feeds each `%item.<slot>` from the matching COLUMN (you never write `%item`)
    per-row filter — add `zGate:` → only passing rows get a block: bare `zGate: %item.stock` (truthy) · dict `zGate: {%item.category: audio}` (by value)
    lowers to — `zList: {source: %data.<reel>, each: {%pattern: {slots}}}` at load (each `%item.*` baked in at bind — no render-time loop)
    raw form — write `zList` directly (`source:` + `each:`) for a hand-wired per-row structure

knot: a value COMPUTED on the spot — `{{ a+b }}` / ternary
    a `zKnot` ties `%` threads + literals into ONE value, declared as a step (no formula string, no eval)
    ops — zAdd · zSub · zMul · zDiv (÷0 → empty) · zJoin (concat, optional `sep`) · zIf (ternary)
    operands — `%` threads, literals, or NESTED knots: `{zJoin: [Buy 2 for $, {zMul: [%item.price_usd, 2]}]}`
    ternary — a `zIf` CONDITION is a `zGate` predicate; zKnot only SELECTS then/else (so zAbove/zSet/zAll work inside)
    two forms — prose slots (`content`/`label`) slurp a value into text → write a knot as a `zKnot:` CHILD (result written into `content`, siblings like `_zClass` kept); non-prose slot uses the short VALUE form (`label: {zAdd: [%a, %b]}`)
    fail-safe — bad op / missing operand / non-number / ÷0 → empty, never a wrong value or crash

var: a durable value set once and reused — `{% set %}`
    lives in the session — read `%var.<name>` (or bare `%name`), written by a `zVar:` event or the `shortcut` command; author/session scope, NOT a render computation
    contrast — `%route.*` is request-scoped, `%item.*` is loop-scoped (both zLoom-owned reels, neither is a zVar)

boundaries: zLoom is the thin declarative layer — borrows the muscle, owns only the grammar
    declares — the `%` threads, named reels, the loop, pattern slots, knot ops (touches no DB/file itself)
    delegates — a spool query → zData · a zIf/per-row filter → zGate · a `%session.*` → the live session (Identity)
    render — resolved before the split, so terminal + browser weave byte-identical content
    rule — declare what's LIVE/REPEATED/COMPUTED, let zLoom weave it; never hardcode what changes per user/row/calc

---

zData advanced: when one table + one filter aren't enough | shape + combine what comes back, at scale, atomically | still DESCRIBED — no query language, no plumbing — same on csv/sqlite/postgres | builds on the CRUD actions (read/insert/update/delete), not a new grammar

queries: harder questions — across tables, summarized, ranked, in steps
    every advanced read is still `action: read` (or `aggregate`/`window`/`set`) with more keys — no SQL, no second dialect; result → zTable

filters_deep: the full zFilters dialect (Read leaf gave a taste)
    string — `age zBETWEEN 30 zAND 35 zAND score > 88` · presence `zKNOWN`/`zNULL` · parens for precedence `(country = USA zOR country = Ireland) zAND score > 85`
    dict   — each field a line, every line an AND: zAbove · zBelow · zIs · zIN: [..] · zBetween: [a,b] · zNull · zKnown · zIncludes · zStarts · zEnds
    ex     — `zFilters: {age: {zBetween: [25,40]}, country: {zIN: [Italy, USA]}, occupation: {zIncludes: eng}}`

joins: stitch related rows into one result
    manual — `tables: [users, orders]` + `joins: [{type: INNER, table: orders, on: users.id = orders.user_id}]`
    types  — INNER (both) · LEFT (all left, null-fill) · RIGHT · FULL · CROSS (every combo)
    columns— after join each carries its table name → filter by qualified `table.column` (csv + sql both resolve the dotted key)
    auto   — `auto_join: true` reads the FK from schema (defaults LEFT); `auto_join: left|right|inner|full` names a type, no `on:`

aggregate: many rows → one answer — `action: aggregate`
    function — count · count_distinct · sum · avg · min · max · median · stddev · variance · group_concat (string_agg); non-count takes `field:`
    group_by — `<field>` (one per group) · `[country, occupation]` (per combination) · `alias:` names the computed column
    filter   — `having: total > 1` (by aggregate) · `where: <expr>` (which rows count) · `distinct: true`

window: an answer per row, keep every row — `action: window`
    rank/offset — row_number · rank · dense_rank · percent_rank · cume_dist · ntile (+buckets: 4) · lag/lead (+field:, offset: 1)
    value/agg OVER — first_value · last_value · nth_value · avg/sum/count/min/max (running with order_by)
    scope — partition_by: (within group) · order_by: score DESC · alias: (new column) · frame: ROWS BETWEEN 2 PRECEDING AND CURRENT ROW (UNBOUNDED/n FOLLOWING work)

subquery: nest a `zData` inside `where` — one query answers another
    IN     — `where: {country: {zData: {action: read, ..., where: score > 90, distinct: true}}}` (inner runs first)
    NOT IN — add `zNot: true` beside the nested zData
    scalar — `where: {score: {$gt: {zData: {action: aggregate, function: avg, field: score}}}}`
    correlated — `%outer.<field>` inside inner (above THEIR OWN country avg: `where: country = %outer.country`)
    presence — `where: {zExists: {zData: {...}}}` (has a match) · `zNotExists` (empty) — `where: user_id = %outer.id`

cte: a big question as a stack of named steps
    `with: {high_scorers: {model, fields, where}}` then `from: high_scorers`
    chained — a later step reads `from:` an earlier one (high_scorers → top_5)
    recursive — self-referential walk (org chart/tree): `with: {org: {recursive: true, anchor: {table: members, where: {id: 1}}, step: {table: members}, link: {parent: id, child: manager_id}}}`

set: stack two whole result sets — `action: set`
    type — union (merge+dedupe) · union_all (keep copies) · intersect (in both) · except (first minus second)
    `queries: {q1: {model, where, fields}, q2: {...}}` — rule: every query shows the SAME columns via `fields:`

search: a ranked search box over rows
    `search: italy engineer` + `search_fields: [name, country, occupation]` + `search_mode: any | all | phrase`
    zOS tokenizes+scores, best first; surface rank with the `_score` field in `fields:`

advanced_writes: batches, returns, referential rules — same declared style + validation as CRUD

returning: any write hands back the rows it touched
    `returning: true` (all) | `[id, name, score]` (subset) — insert → new row (auto-id) · update → post-write rows · delete → snapshot taken BEFORE removal (ids captured before write, safe even when the changed field is in `where:`)

insert_select: seed a table from a read — no manual entry
    `select:` on `action: insert` → `select: {model, where, fields}`; reads source, auto-projects to target schema, runs each row through the full insert pipeline, one pass

upsert: insert-or-update per row — `action: upsert`
    `conflict_fields: [...]` (or `conflict_key:`) decides the match; pairs with a list (bulk) + `returning:`

update_advanced: more than a flat value in `set:`
    zCase — per-row, first match: `set: {role: {zCase: [{when: score zABOVE 8, then: admin}, {when: score zABOVE 5, then: editor}], else: viewer}}` (when speaks zFilters; no else → unmatched keep value)
    computed — `{$inc: n}` · `{$dec: n}` · `{$mul: n}` · `{$div: n}` · `{zExpr: price * qty}` (math over the row's own columns, never code)
    cross-table — `from: {model, on: a.x = b.y}` then reach with `%table.field`; inner-join (no partner → untouched); `%row.field` = the row being written
    hooks — onBeforeUpdate/onAfterUpdate: &.func · re-validates unique, guards immutable, applies transform on edit

delete_advanced: remove by relationship, not just id
    on_delete — deleting a parent checks every child `fk:` field: cascade (children first) · restrict (block while children exist) · set_null/set_default (re-point); multi-hop recurses the fk chain
    soft — `soft_delete: true` routes `action: delete` to stamp `deleted_at` (same call site, no data lost)
    subquery — `where: {user_id: {zData: {action: read, ..., where: active = false}}}`
    cross-table — `using: {model, on, where}` (delete from A by a match in B)
    time purge — `where: joined_date zBELOW zNow()` · capture with `returning: true`

bulk: many rows in one call — no loop
    insert — `data:` a LIST OF DICTS switches to bulk; every row validates, batch aborts as a whole if any fails
    upsert — `action: upsert` + `conflict_key:` + a list (+ `returning:`)
    update — `where: id zIN (1,3)` or `where: <expr>` — SAME value across the set (per-row = zCase)
    delete — `where: id zIN (...)`; no where → clears every row (id counter keeps climbing); `action: truncate` empties AND resets id to 1 (blocked while a table points at it — clear children first)
    ui_selection — a `zWizard` `zSelect` `multi: true` returns ticked values as a LIST kept as `zHat[Select]`; next step spends `where: {id: zHat[Select]}` (bare `zHat` keeps type → one `IN (…)`, one write)

transactions: many STEPS as one — commit all, or nothing
    home — on a `zWizard`: `_transaction: true` → every `zData` across steps shares ONE connection
    $alias — bind each model dollar-prefixed (`model: $orders`) to keep it on the shared connection; a `@.models…` path opens a fresh AUTO-COMMIT connection per step (a later failure can't undo earlier writes)
    cross-step — `zHat[StepName]` carries an earlier step's value (a fresh id from `returning:`) into a later `where:`/`data:`
    lifecycle — no manual commit/rollback: reach the final step cleanly → commit · any step fails/aborts → rewind
    acid — sqlite+postgres: true atomic ACID · csv: best-effort snapshot restore (same visible outcome)
    savepoints — mark an OPTIONAL step's zData `_savepoint: true` → on fail rewinds ONLY that step, wizard continues (native SAVEPOINT/RELEASE/ROLLBACK TO on sql, snapshot on csv)
    alpha — under zServer/zBifrost schemas load at boot so `$<table>` resolves; a bare zCLI run with no server can't resolve a cold `$<table>` → transaction quietly no-ops
    !scope — isolation/row-locking (SERIALIZABLE, FOR UPDATE) + distributed/2PC — single-connection, one writer — not goals

backends: one schema, three interchangeable stores — swap the store, keep every declaration
    pick — `Data_Type` in `zMeta`, resolved from a registry at load; shared `type_mapping` makes uuid/json/datetime mean the same everywhere
        csv — flat files, demos/tiny, zero setup, best-effort ACID, live introspection (reads headers)
        sqlite — single-file DB, local/dev→prod, full ACID
        postgresql — networked DB, multi-node/concurrent/production, full ACID
    connection — `Data_Path` = the store dir for csv/sqlite; networked keeps creds in `.zEnv` via `Data_Source` (never hard-coded), zServer reads the URL at boot
    ddl (structural, shown as syntax) —
        `action: create` (from schema; skips existing; `tables: []` builds ALL — first-run bootstrap) · `action: drop` (table + data)
        `action: head` (declared shape) · `action: list_tables` (SHOW TABLES / \dt) — pure introspection · `action: truncate` (wipe + reset id)
    indexes — declared `indexes: [status]` or `[{fields: [team_id, role], unique: true, name: uq_...}]`, built at create (real CREATE INDEX on sql, no-op csv)
        later on existing table — `action: index` / `action: drop_index` with the same field/dict `index:` spec (idempotent, IF [NOT] EXISTS)
    views — a named saved read: a schema entry carries `view:` instead of `fields:`; read the NAME, zData swaps in the saved read (no CREATE VIEW dialect)
        virtual (default) — re-resolved every read, always live: `active_admins: {view: {tables: [members], where: {role: admin}, fields: [name, role]}}`
        materialized — `view: {materialized: true, into: admin_cache, tables, where, fields}` stores rows; `action: refresh` recomputes (fast read, stale until refresh)
        read like any read (`table:`/`model:` at its name); extra `where:` AND-merges with the view's filter; read-only (writes refused), nests recursively (depth cap + cycle guard)
    evolution — add/drop/rename column, ALTER in place, change backend → migrations (zData CRUD › migrations)

---

zSwiper: a deck of slides, shown one at a time — a carousel | hand it a `slides:` list + a few knobs, it builds the deck AND the navigation | two faces: keyboard box in the terminal, touch carousel in the browser | terminal is the truth — same block both places

core: the block — one required key, rest optional
    slides:       [a, b, c]      — the cards, one per slide; the ONLY must-have (strings; may hold HTML on the web); empty/absent → nothing
    label:        A short title   — above the deck; omit for untitled
    auto_advance: true | false    — own timer vs wait for a nudge (DEFAULT on)
    delay:        3               — seconds per slide before auto-advancing (only with auto_advance)
    loop:         true | false    — wrap last→first (DEFAULT off; without it a manual deck stops at ends, an auto deck halts at last)
    folder:       @.path.to.pages — ADVANCED, zCLI-only: each slide name → a real zUI page (see `pages`)

shape: a zVaFile block, string-first .zolo
    zVaF:
        zSwiper:
            label:        A three-slide tour
            auto_advance: false
            loop:         true
            slides: [
                Slide one — one slide at a time.,
                Slide two — arrows move, numbers jump.,
                Slide three — that is the whole deck.,
            ]

faces: one block, two renders — never branch on zMode
    zCLI    — a bordered box repainted IN PLACE (feed above never scrolls off); keyboard-driven; a plain sequential print of every slide when there's no TTY (CI/piped)
    bifrost — a touch carousel (one slide visible, chevron prev/next, dot indicators, JS auto-advance + loop); zbase.css §12, currentColor (self-balances light/dark)
    rule    — TERMINAL IS THE TRUTH; the browser is the skin

keys: driving a deck in the terminal (the box is the remote)
    ◀ ▶ — step prev/next · 1–9 — jump to a slide by number · p — pause/resume auto-advance · q — close + move on
    web — same idea: click chevrons/dots; arrow + number keys also work

pages: the zCLI showpiece — a deck of whole PAGES (`folder:`)
    what    — each name in `slides:` is a real zUI page in `folder`, loaded FLAT (inert) like a zDash panel (carousel never blocked by the page's own inputs)
    resolve — `slides: [Stats, Settings]` + `folder: @.zViews.myApp.panels` → each renders `folder.zUI.<name>` (block `<name>`), zMeta/zRBAC stripped
    zBounce — press `o`/Enter on a page-slide → run that page in its REAL interactive flow, then fall back into the deck (read-paced → page decks are manual)
    web     — NOT on Bifrost yet; browser side is text/HTML slides only (ALPHA)

seek_as_need: only if extending the widget, not authoring
    zCLI engine  — core/.../e_zDisplay/zDisplay_modules/advanced/timebased_swiper.py (box render, in-place repaint, keyboard loop, page/zBounce mode)
    bifrost render— zbifrost-client/.../composite/swiper_renderer.js (zCarousel build) + zbase.css §12
    wire         — `zSwiper:` → shorthand_expander → `{zDisplay: {event: swiper}}`; Bifrost renders INLINE (`swiper` case → SwiperRenderer.renderInline); imperative `display.swiper()` emits a `swiper_init` WS event

---

zTerminal: a code sample that can come to life — a snippet with Copy, and (when allowed) a Run that executes inline + streams output | you write title + fenced content + zRun; whether it CAN run is one zEnv dial (ZTERMINAL_MODE), readonly by default | two faces: asks-then-prints in terminal, a Copy/Run card in browser | the DIAL is the safety, not the fence

core: the block — three keys you author
    title:   zUI.myApp.zolo   — label above the block (often the source file); DEFAULTS to `Terminal`
    content: ```lang … ```    — the code in a fenced block; the FENCE names the language (```python, ```zui, ```bash)
    zRun:    true | false      — offer a Run button? DEFAULT true; false = show-and-copy only
    !mode    — you never author the run mode here; it's stamped server-side from zEnv (see `dial`)

shape: a zVaFile block, string-first .zolo
    zVaF:
        zTerminal:
            title:   A live snippet
            content: ```python
                import math
                print(math.factorial(5))
                ```

dial: ZTERMINAL_MODE — ONE zEnv switch, set once, decides if ANY block on the machine may run
    readonly — DEFAULT (also unset/empty/unknown): show + copy, NEVER run — safe stance for code you didn't write
    sandbox  — run but fenced: Python-only, restricted builtins; best-effort, NOT a real security sandbox
    trust    — local desktop: Python runs freely (bash unimplemented in open-core)
    web      — over Bifrost `trust` CLAMPED to sandbox server-side; Run shows ONLY in sandbox for python/zui; readonly never runs; bash never web-runnable
    real     — the SAFETY is the readonly default, not the fence — never point sandbox/trust at content you don't trust (Security leaf)

langs: the name after the ``` decides what runs
    python — runs: maths/dates/json + the LIVE app as `z`; never os/files/network
    zui    — renders a little Grammar page from the snippet (live preview in place)
    bash   — shown, NEVER run (shell exec is a sealed path, not open-core)
    other  — displays (highlight + Copy), no Run button

faces: one block, two renders — never branch on zMode
    zCLI    — a highlighted box; when runnable it asks yes/no first, then prints inline below
    bifrost — a card: Copy always, a constant MODE BADGE (the dial), a Run when dial+lang allow, output streaming live
    rule    — TERMINAL IS THE TRUTH: reads+runs in the console → the browser card is the nicer coat

seek_as_need: only if extending the widget, not authoring
    zCLI engine  — core/.../e_zDisplay/zDisplay_modules/sandbox/terminal_executor.py (ZTERMINAL_MODE gate, python/zui exec, readonly default) + sandbox_policy.py (restricted builtins + import allow-list)
    trust seam   — display_trust.verify_terminal_exec (zGuard attestation before any run; web clamps trust→sandbox, sealed-core)
    bifrost render— zbifrost-client/.../composite/terminal_renderer.js (card, Copy/Run, mode badge, fence parse, `_isRunnable`) + zbase.css §13 (`.zTerminal-*`)
    wire         — `zTerminal:` → shorthand_expander → `{zDisplay: {event: zTerminal}}`; Bifrost `zTerminal` case → TerminalRenderer.render; a Run rides WS (`execute_code` → streamed output / `sandbox_input_request`)

---

zProgress: a labelled bar showing how far along something is | give it a total → FILLS to a percent (a bar); omit total → just says *working* (a spinner) | one snapshot alone, or drop it inside a zWizard and it CLIMBS as you clear steps | two faces: an ANSI bar in the terminal, a .zProgress bar in the browser

core: the block — a label + how far along
    label:   Processing files   — words above the bar (WHAT is working)
    current: 60                 — how far now (DEFAULTS to 0)
    total:   100                — finish line; leave OFF → spinner instead of bar
    color:   primary            — fill colour (primary/success/…), optional
    note     — percent is DERIVED (current/total); you never write "60%"

shape: string-first .zolo, one small block
    Demo:
        zProgress:
            label:   Processing files
            current: 60
            total:   100
            color:   primary
    note — one block = ONE frame (a snapshot); it doesn't move on its own (see `live`)

spinner: no finish line — drop `total`, stop pretending to know the percent
    when    — a task with no countable end (waiting on a server, open-ended job)
    bifrost — a striped sliding marquee (`zProgress--indeterminate`)
    zCLI    — a small braille spinner
    rule    — an indeterminate bar NEVER shows 0% and never "completes" on its own — says *working* until replaced

live: the climb — a `zProgress` chrome INSIDE a zWizard, filling as you clear steps
    write   — `zProgress: {label, color}` as a SIBLING of the wizard's steps (chrome, not a step)
    counts  — the wizard counts steps: 4 steps, parked at gate on step 2 → 50%
    click   — clear the gate (a `zBtn` submit) → post-gate steps reveal, bar fills to 100% IN PLACE
    proven  — live on Bifrost (Continue → 50%→100%); runtime mints a stable `wizprog-` id + replays the fill
    why     — no hand-set percentages; the flow's own step math is the denominator

journey: the fourth form — a `zProgress` beside a `zFunc`/action, filling while work runs
    zCLI    — a live step-journey; zProbe = denominator oracle (zDispatch → zFunc → done), parks on EXECUTE then snaps to done
    type    — `bar` (DEFAULT) fills done/total across probe stops · `spinner` = same count as an animated glyph
    bifrost — honest gap: client re-dispatches the bare zFunc (execute_zfunc), drops the sibling — wiring it is the deeper pass
    note    — for a live browser climb TODAY, prefer the `live` wizard form (proven cross-face)

faces: one block, two renders — never branch on zMode
    zCLI    — an ANSI bar redrawn in place with carriage-return (`[████░░░] 60%`), or braille spinner when indeterminate
    bifrost — a `.zProgress` DOM bar with width transition — striped+animated when indeterminate, theme-agnostic fill
    rule    — TERMINAL IS THE TRUTH; the browser bar is the nicer coat

seek_as_need: only if extending the widget, not authoring
    zCLI engine  — core/.../e_zDisplay/zDisplay_modules/advanced/timebased_progress.py (ANSI bar, braille spinner, total None never completes) + delegates/delegate_widgets_media.py::progress_bar (current default 0)
    bifrost render— zbifrost-client/.../display/feedback/progressbar_renderer.js (renderInline, width transition, indeterminate marquee, % suppressed) + zbase.css § Progress bar (`.zProgress-*`)
    journey      — core/.../g_zDispatch/dispatch_modules/handlers/handler_routing.py::_route_zfunc_with_progress + progress_journey.py (_run_cli / _run_bifrost) + zprobe.py (stop-count denominator)
    wizard climb — zGuard message_walker._unwrap_zwizard_for_render (mints `wizprog-<gate_id>`, gate-pos/total, parks post-gate, replays fill to 100% on resolve)
    wire         — `zProgress:` → shorthand_expander → `{zDisplay: {event: progress_bar}}`; imperative API `display.progress_bar(current, total, label, color, …)`

---

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
