<!-- cursor: description="zForms — zDialog: gather inputs + controls into one onSubmit block (the event that COLLECTS a whole screen of fields)" globs="**/zUI.*.zolo" alwaysApply=false -->
zForms: a dialog is a conversation — collect a screen of answers, then act | zDialog gathers inputs + controls and, onSubmit, hands the lot to an action | write it once -> field-by-field in zCLI, a real form in zBifrost | inputs/controls only ASK; the zDialog owns the submit

zdialog: the first event that COLLECTS
    everything before it (inputs, controls) only ASKS one thing — a zDialog gathers a whole screen of them
    title    — the form's heading
    fields   — the things to collect (see fields)
    onSubmit — the action run when the form is submitted (see result)
    onSuccess— OPTIONAL follow-up fired only on a GREEN result (see onsuccess)
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
    tokens_in_props — a field property holding a WHOLE %token resolves NATIVELY, not as display text:
        `options: %data.<name>` → a real LIST · readonly/disabled from a bool column → a real yes/no ·
        `default:` over a NULL value → an EMPTY box (a miss on other props keeps the literal token —
        visible, debuggable)
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

onsuccess: the form's "and then" — a follow-up zEvent fired only on a GREEN result
    `onSuccess: zDelta($Block)` — a SIBLING of onSubmit; a successful submit dismisses the hosting
        modal by itself and re-walks the target block (the same self-hop a Refresh button fires) —
        the page updates live, zero manual close/refresh clicks
    failure — nothing fires: the red line renders, the form stays armed for an in-place retry
        (the follow-up can never leak on a failed submit)
    trust   — the target registers SERVER-side beside onSubmit in the dialog registry; the response
        only echoes the block name and the CLIENT re-fires its own zDelta — the server never pushes
        unsolicited content
    kin     — zLogin/zLogout carry `onSuccess: zLink(...)` (a REDIRECT → Identity); a plain zDialog's
        onSuccess is the in-place cousin (`zDelta`) — same key, the zEvent names the move
    scope   — Bifrost today; zCLI ignores the key (a terminal re-walk of the dialog's own block would
        re-prompt every field — loop-unsafe until designed)
    pattern — write-then-reread: onSubmit stamps state (a zVar, a row), the re-walked block's own
        declarative read picks it up fresh — zCloud zRM's Subscriptions toolbar (Search/Clear/Grant/
        Edit dialogs, all `onSuccess: zDelta($Subscriptions)`) is the worked example

live: `zLive: true` — an AMBIENT form: typing IS the submit (search-as-you-type)
    the flag flips three behaviors at once, nothing else about the dialog changes:
    no button — the Submit button is not rendered; every debounced keystroke (300ms; `zLive: <ms>`
        to tune) fires onSubmit quietly — green stays silent, a red failure still renders inline
    never gates — the chunk engine walks PAST a live dialog (an ambient filter repeats forever by
        design; gating it would stand every sibling below it — the very table it filters)
    scoped repaint — its `onSuccess: zDelta($Block)` re-walks ONLY that block's on-page container
        (no history entry, no scroll reset) — the search input sits OUTSIDE the target, so focus
        and the half-typed term survive every repaint
    layout — author the live dialog as a SIBLING of the content it filters, never inside the
        zDelta target (a repaint that swallows its own search bar eats the user's focus)
    fields-less + zLive — a one-click AMBIENT confirm ("Clear filter"): same quiet repeat-forever
        contract, rendered as a plain button
    in-flight keystrokes coalesce client-side (one submit at a time per dialog, last term wins);
        zCLI ignores the key (a terminal prompt is already gated — live has no meaning there)

zvar_submit: `onSubmit: {zVar: {<var>: zConv.<field>}}` — a DECLARATIVE session-var write, no zfunc
    the zero-plugin filter pattern: the WRITE side stamps `zVars` through the dispatch SSOT; the
        READ side is the target block's own `search: %<var>` / `where: {col: %<var>}` — one token,
        so the label, the query, and the box can never drift
    repeatable — a zVar submit NEVER consumes the dialog registration (a filter re-stamps per
        keystroke by design); one-shot actions (zData inserts) still retire on success
    always green — a session write cannot business-fail; empty value = clear (`{zVar: {q: }}`)
    unset token — a `search: %<var>` that finds no session value resolves to NOTHING → the read
        stays UNFILTERED (first render shows everything, before any term exists)
golden — `zGuard/zLedger` (zDemo-bound): live search bar (`zLive` + `zVar` + scoped
    `zDelta($Main.Ledger)`), one-click Clear (fields-less zLive confirm), modal New/Void/Restore
    all `onSuccess: zDelta($Main.Ledger)` — table, stats, aggregates, and voided list repaint
    together; zero plugins, raven-proven on csv AND sqlite

onward: onSubmit is a DOORWAY — the same hook, bigger jobs
    onSubmit is always a dict — ONE key naming the subsystem, never a bare `&.` call
    `onSubmit: { zFunc: &.calc.add(zConv.a, zConv.b) }` — the simplest action, a plugin call
    zWizard  — carry the answers into a multi-step flow
    Identity — sign someone in / change the session (also what lets a submit navigate to a new page or refresh the navbar)
    zData    — save the answers as a row (see schema): `{ zData: {action: insert, model: @...} }`
        insert needs `data:` — `data: zConv` writes the WHOLE form dict (field names == column
        names); without it the insert has nothing to write and fails red
    zVar     — stamp the answers into session vars (see zvar_submit) — the filter/live pattern
    rule: zDialog's grammar never changes — only the action on the other end gets bigger

schema: let a zSchema write the fields
    model: @.models.zSchema.X + fields: [name, email, password] — name the fields; the schema supplies each one's type, label, rules
    the dialog is otherwise IDENTICAL — same onSubmit, same zConv
    defining schemas, the validation they carry, and saving to a real backend -> Data hub (Advanced), taught in full there

zconv: the bag of answers
    every field's value is gathered under its key — name -> zConv.name
    zConv is what onSubmit hands the action — &...(zConv.name) reads one, the action sees them all
    empty_is_empty — a field left blank (an OPTIONAL select left unpicked included) hands the action
        an EMPTY value; a `zConv.<field>` reference with no submitted value substitutes empty in the
        action string

terminal: write once, it reads the room
    the same zDialog runs in zCLI (a prompt per field) and in Bifrost (one real form) — no second version
    rule: if it works in the terminal it works in the GUI — same answers into zConv, only the skin differs

!page_dialog_key — a page-level (non-modal) zDialog must be its block's DIRECT event key (`zDialog:` itself,
    not `SomeName: {zDialog: {...}}`) — zCLI's walker reads onSubmit off either shape fine, but Bifrost's
    form-submit binding only resolves it off that exact direct path; wrapped under a custom name, submit
    fails client-side with "No onSubmit action specified" even though the CLI proof of the identical zolo
    passed. A zModal's inner zDialog is unaffected (different binding path) — see `zDemos/zBlog`'s Add_Post
    for the correct shape
golden — `zDemos/zBooking`'s New_Booking: a page-level zDialog (`fields: [slot_id, customer_name]`) whose
    onSubmit is a bare `zData: {action: insert}` — the unique-constraint rejection renders inline, form
    intact, in both zCLI and Bifrost, zero plugins
!wizard_step_zdialog — the SAME binding rule bites a moment you'd expect to be safe: a named `zWizard` step
    (`Shipping: {zDialog: {...}}`) IS a wrapped shape (a step's name is mandatory, so it can't be the direct
    key) — a multi-field screen mid-wizard wants flat `zInput` steps + a shared `zBtn type: submit` gate
    instead, never a step-level zDialog → zWizard `!zdialog_step_conflict`, `zDemos/zShop`'s checkout
