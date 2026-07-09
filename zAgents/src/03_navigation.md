<!-- cursor: description="zNavigation — moving through an app: menus (* ~), zAlpha/zDelta/zOmega verbs, zURL links, zCrumbs breadcrumbs (^ rewind), the navbar, the submit/dialog event gate" globs="**/zUI.*.zolo" alwaysApply=false -->
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
    !file_field — a `zDialog` with a `type: file` field has no proven path inside a `zModal` (Bifrost never wired a
        file-input's picker/upload plumbing for the overlay-carried form); give it its OWN block instead
        (`action: zDelta($Edit_X)` or a cross-file `zAlpha`) — same pattern `zDemos/zGallery`'s Add_Photo and
        `zDemos/zBlog`'s Edit_Avatar use — a page, not a glance

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
