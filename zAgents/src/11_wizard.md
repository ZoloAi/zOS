<!-- cursor: description="zWizard — multi-step flow: named steps run in order, zHat reads prior answers, if:/menu/gate steer the walk. Reach for when a later step depends on an earlier answer (a flat set of fields is a zDialog)" alwaysApply=false -->
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
    rule  — a menu is the looping rule with a person at the wheel; want the wizard to decide? that's `if:`

if: a step that runs only when it earns its turn
    `if: <expr>` beside a step's event — tested against the hat on arrival; false → step skipped WHOLE (nothing shows/lands)
    self-judging — the test reads the hat, so each step decides from what earlier steps gathered (no branches, no else)
    test_language (read against the hat):
        read    — `zHat[Track]` · `zHat[0]` · `zHat[Details][0]` (into a bundle by POSITION)
        yes/no  — `zHat[Track]` · `not zHat[Track]`
        equality— `== 'both'` · `!= 'talks'`
        order   — `>` `<` `>=` `<=` · chained `zHat[A] == zHat[B] == 'same'`
        member  — `in ['talks','both']` · `not in [...]` · `zHat[Pick] in zHat[Allowed]`
        combine — `and` · `or` · parens `(zHat[A] or zHat[B]) and zHat[C]`
        literals— `'both'` · `18` · `['a','b']`
    fences  — an allowlist, NOT Python eval: no calls/.methods/attributes/arithmetic; every hat answer is TEXT (`>`/`<` compare as text); malformed or missing → reads FALSE + skips (never an error)
    not_rbac— gating a step by WHO's asking is zRBAC, not `if:` → Advanced

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
    you author the EVENT (named steps, zHat, if:, gates); the run model (zEngine/zWalker/zStride/zForce) → Advanced › zEngine
    a step is made of OTHER events, sequenced: field → Input · button/action → Control · function return → zFunc · multi-field → Forms

terminal: write once, it reads the room
    same zWizard in zCLI (a prompt per step) + zBifrost (a progressive form, a gate that holds the line) — no second version
    rule — works in the terminal → works in the GUI: same steps into the same hat, only the skin differs
