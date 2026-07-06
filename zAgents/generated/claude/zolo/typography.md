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
