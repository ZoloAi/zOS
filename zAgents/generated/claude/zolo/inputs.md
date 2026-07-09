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
    !modal: a file field's zDialog wants its OWN page (zDelta/zAlpha), never a zModal detour -> Navigation zmodal

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
