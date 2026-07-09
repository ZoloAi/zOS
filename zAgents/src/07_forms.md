<!-- cursor: description="zForms — zDialog: gather inputs + controls into one onSubmit block (the event that COLLECTS a whole screen of fields)" globs="**/zUI.*.zolo" alwaysApply=false -->
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
