<!-- cursor: description="zSwiper — a carousel: a slides: list + knobs (auto_advance, delay, loop) → keyboard box (zCLI) / touch carousel (Bifrost). Reach for a slideshow or deck" alwaysApply=false -->
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
            slides:
                - Slide one — one slide at a time.
                - Slide two — arrows move, numbers jump.
                - Slide three — that is the whole deck.

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
