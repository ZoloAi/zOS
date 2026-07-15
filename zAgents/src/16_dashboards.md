<!-- cursor: description="zDash — assemble pages you already wrote into a navigable shell (side rail + swapping panels): type/folder/sidebar/default. Reach for composing many existing pages into one dashboard" alwaysApply=false -->
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
    how  — a `zGate:` block at the panel's root (`authed: true` | `role: [zAdmin]`; legacy `zRBAC:` auto-lowers)
    rail — SESSION-gated panels (role/authed) a visitor can't reach are DROPPED before the rail
        draws — on BOTH surfaces (zCLI always did; Bifrost since zGuard 1.0.9 — rail gotcha below)
    value gates — a panel-root gate over the panel's own spool (`%data.<reel>.<field>: {zIN: [...]}`)
        is DEFERRED at rail time (spool unbound there — the tab stays) and enforced at panel-content
        render, bind-before-gate on EVERY path, default panel's first paint included (1.0.9)
    split — rail visibility = session gates; panel content = value gates; a mixed gate defers whole
    real — data access underneath is enforced regardless; rail filtering is the polite front

custom: two style levers that NEVER overlap
    content — style the panel in its own file with its own `zBrush`
    shell   — `_zClass` on the `zDash` → `.zDash-container`; target `.zDash-*` to restyle rail+frame
    theme   — `.zDash-*` defaults built from `currentColor` (self-balance light/dark) — keep overrides the same

seek_as_need: only if extending the widget, not authoring
    zCLI engine  — core/.../e_zDisplay/zDisplay_modules/system/system_event_dashboard.py (panel discovery, zMeta load, numbered-menu loop, `done` exit, per-panel RBAC filter)
    bifrost render— zbifrost-client/.../composite/dashboard_renderer.js (sidebar/tabs, lazy load via `execute_walker`, mobile drawer) + zbase.css §10 (`.zDash-*`)
    icons        — panel `icon:` is a `bi-*` via IconMapper/IconRenderer SSOT (`[name]` terminal, `<i class="bi bi-*">` browser)

golden: `zDemos/zConsole` — a dev-console zDash (Overview/Snippets/Status/Hosting) proving a
    panel's OWN `zMeta.zSpool` (nested inside the panel block, not file-root — the one
    deliberate exception to "zMeta always root-level") resolves a live `%data.*` read AND a
    page-scope `zKnot` computed off it, in BOTH zCLI and Bifrost — CLI via
    `zDash._bind_panel_data`, Bifrost via `_bind_root_zinja`'s block-level `zMeta` fallback

gotcha: a panel's own same-file `zDelta` (a Refresh button, `action: zDelta($PanelName)`) silently dropped its `%data.*` binding on
    Bifrost, even though the SAME panel's initial sidebar load resolved it fine
    why      — the initial load's click carries `_renderTarget` (the dash's own lazy-load
        marker), which flags the server-side bind as `is_dashboard_panel` and triggers the
        block-level `zMeta` fallback (this file's golden note above); a plain in-panel zBtn
        click carries no such marker, so the fallback never fired even though the walker
        DID correctly re-resolve the target block against the stamped panel file
        (`_panel_zVaFile`) — the zList just rendered its raw `%item.*` template, unbound
    fix      — the server marks `is_dashboard_panel = True` whenever resolution actually
        FALLS BACK to the stamped panel file (not just when the click's own payload says
        so) — first caught by `zDemos/zRM`'s zDash capstone (Add-then-Refresh)

gotcha: over Bifrost the rail used to draw EVERY panel, gates or not (zOS #11, fixed zGuard 1.0.9)
    why      — the walker ships the authored zDash event to the client verbatim (special-event
        extraction), so the CLI engine's `_filter_accessible_panels` never ran on that path —
        drop-before-rail existed but was unreachable in exactly the mode the docs describe it for;
        content gates still held at click time, so the leak was tab NAMES only
    fix      — `_filter_zdash_sidebar` gates each listed panel's root via `zos.zgate.check` (the SAME
        SSOT every page gate uses) at BOTH the expansion seam and the extractor before the event
        ships; `default` is recomputed off the kept list; per-panel fail-open mirrors the CLI
    caveat   — a `%`-token gate would fail CLOSED here (token starves before the spool binds — a
        subscriber would lose their own Billing tab), so the rail filter DEFERS any predicate that
        references a `%` token to content render; only session gates decide rail membership

gotcha: block-level `%data.*` gates were SKIPPED on the DEFAULT panel's first paint (zOS #12, fixed zGuard 1.0.9)
    why      — the initial HTTP render reached the chunk gate BEFORE the panel's `zMeta.zSpool`
        bind (the zPick path binds first) — the `%data` token starved, the render gate failed OPEN
        by design, and both sibling blocks shipped; content interpolation still painted (it runs at
        a later seam), which is what made the skip look selective
    fix      — chunk gates now evaluate against the walker's block_context (the same surface the
        content interpolation reads) instead of a clobber-prone session stash; a genuinely starved
        token still fails open but logs at WARNING, so an ordering regression can't hide again

gotcha: a standalone (non-`%item`) `zBtn` with `action: {zModal: {...}}` — anywhere, not just in a
    zDash panel — silently swallowed its click in Bifrost
    why      — the chunked render engine treats a `zModal` action as a GATE (same family
        as `zDialog`/`zForm`) needing a `wizard_gate_submit` to resume; `zModal` is actually
        fire-and-forget client-side like `zDelta`/`zLink`/`zAlpha` — no submit ever arrives,
        so the paused generator "resumes" on the raw click and skips straight past the
        zModal dispatch without ever sending it. A zList's PER-ROW `zModal` (Delete/stage
        buttons) was never affected — those render as plain content, not chunk-engine gates
    fix      — `zModal` joined the non-gating action set (zEngine `zstride._NAV_ACTION_KEYS`)
        — a standalone `zModal` button now needs NO `zDelta`-to-a-dialog-page workaround,
        write it exactly like a per-row one (`zDemos/zRM`'s panel-level Add Contact/Company/Deal)
