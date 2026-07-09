<!-- cursor: description="Dynamic content (zLoom) — the % sigil weaves live/repeated/computed content pre-render: %token values (zSpool/%session…), %name: patterns (zShuttle loops a list, zKnot computes), zDye pipes" globs="**/zUI.*.zolo,**/zLoom/**/*.zolo" alwaysApply=false -->
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
    !where_form — a reel scoped to the visitor (`currentUser: {zData: {..., where: <expr>}}`) needs `where:` as a
        DICT (`where: {id: %session.zVisitor.id}`), not a `field = value` STRING — a spool's `%session.*` interpolation
        only runs on the dict shape; a string `where` ships the literal token text and the read silently returns
        nothing (no error, just an empty reel) — `zDemos/zBlog`'s Profile page is the worked example
    freshness — a `zMeta.zSpool` is re-resolved on EVERY landed render (boot, zLink, zDelta alike) — a list-backed
        reel always reflects a write made moments earlier on a DIFFERENT screen, same session
    golden   — `zDemos/zBooking`'s My_Bookings: a `zList` reel joining 3 tables, freshly re-read after a `zDelta`
        hop away and back (New_Booking's own insert) — zero plugins, availability itself is a `zNotExists` read
        (see Advanced Queries), conflict validation a plain `unique: true` (see Data CRUD)
    expansion_freshness — the SPOOL resolve (`%data.<name>`) re-runs on every landed render, but the `zList` LOOP
        EXPANSION into concrete `%item`-baked rows used to run only ONCE per block: `zDelta`'s target is a LIVE
        reference into the loader's cached parse (not a fresh copy), and expansion used to consume its own `zList`
        directive outright — a block whose FIRST visit saw 0 rows (an empty History/My_Bookings on first paint)
        would never re-expand on a later revisit, freezing empty forever even after a real insert. Fixed core-side
        (zLoom `LoopOps`): the original directive is stashed (as a JSON STRING — a dict-valued stash gets misread
        as one more phantom child block by any render path that recurses on a bare `isinstance(val, dict)` check)
        so a revisit re-weaves against CURRENT rows, clearing any stale ones first. `zDemos/zDarkroom`'s History
        is the worked example (an empty-at-boot list that grows after a `zDelta($Add)` → submit → `zDelta($Main)`
        round trip) — no zolo authoring change needed, this was a framework gap, not a usage mistake

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
    ops — zAdd · zSub · zMul · zDiv (÷0 → empty) · zRound (2-decimal money math) · zJoin (concat, optional `sep`) · zIf (ternary)
    operands — `%` threads, literals, or NESTED knots: `{zJoin: [Buy 2 for $, {zMul: [%item.price_usd, 2]}]}`
    zRound — `{zRound: [<value>, <digits>]}` fixes float-precision drift (0.1+0.2 style) before it ever hits the page; wrap the outer arithmetic knot, not just the final display
    money_gotcha — the render layer collapses an INTEGRAL float to a plain int (24.0 -> displays `$24`, not `$24.00`) — a `zRound` knot doesn't stop this, it only fixes precision on non-whole values; accept the inconsistency for MVP or format explicitly (`zJoin` + a padded-decimal dye) if exact 2dp everywhere matters
    ternary — a `zIf` CONDITION is a `zGate` predicate; zKnot only SELECTS then/else (so zAbove/zSet/zAll work inside)
    two forms — prose slots (`content`/`label`) slurp a value into text → write a knot as a `zKnot:` CHILD (result written into `content`, siblings like `_zClass` kept); non-prose slot uses the short VALUE form (`label: {zAdd: [%a, %b]}`)
    fail-safe — bad op / missing operand / non-number / ÷0 → empty, never a wrong value or crash
    golden — `zDemos/zShop`'s cart/checkout: subtotal is a live `SUM(line_total)` aggregate (no group_by → a single
        scalar, not a `.0.total` row), tax/shipping/total chain `zMul`/`zAdd` wrapped in `zRound` at both the Review
        display AND the PlaceOrder insert (same computed value written and shown, never re-derived twice)

var: a durable value set once and reused — `{% set %}`
    lives in the session — read `%var.<name>` (or bare `%name`), written by a `zVar:` event or the `shortcut` command; author/session scope, NOT a render computation
    contrast — `%route.*` is request-scoped, `%item.*` is loop-scoped (both zLoom-owned reels, neither is a zVar)

boundaries: zLoom is the thin declarative layer — borrows the muscle, owns only the grammar
    declares — the `%` threads, named reels, the loop, pattern slots, knot ops (touches no DB/file itself)
    delegates — a spool query → zData · a zIf/per-row filter → zGate · a `%session.*` → the live session (Identity)
    render — resolved before the split, so terminal + browser weave byte-identical content
    rule — declare what's LIVE/REPEATED/COMPUTED, let zLoom weave it; never hardcode what changes per user/row/calc
