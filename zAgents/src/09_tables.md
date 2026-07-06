<!-- cursor: description="zTable — columns + rows → a styled grid (Bifrost) / ASCII table (zCLI)" globs="**/zUI.*.zolo" alwaysApply=false -->
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
