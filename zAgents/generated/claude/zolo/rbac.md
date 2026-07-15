zGate: one word puts a doorman on any page/link/button/route — checks WHO's asking before the thing renders | server-side, so a hidden item can't be poked by a hand-built request — real, not a curtain | write once → identical gating in zCLI + zBifrost | zGate = the VERB (every yes/no), zRBAC = the identity QUESTION; sign in with zLogin, out with zLogout — ALPHA

three_whos: keep them straight — access control is only about the THIRD
    owner     — who the zOS install belongs to (set once, clears the watermark) → Foundations › zAuth (`z login`/PAT)
    session   — the visitor passing through NOW (guest or signed-in, one tag per visit) → Sessions leaf
    app_users — the MEMBERS of the app YOU built, each carrying a `role` — what zGate/zRBAC decides on
    rule      — owner ≠ session ≠ app users; zGate never touches who owns the instance

verb: ONE gate verb answers every yes/no — you write the rule, zOS enforces on the backend
    `zGate:` — the single block for every gate (auth `authed`/`role`/`require`); the same verb powers wizard `if:` + value comparisons (zLoom → Grammar › Wizard)
    identity — the doorman hands identity questions to the RBAC trust engine, which reads the LIVE session (`zGate.py` → `zAuth.check_zrbac`)
    legacy   — an older `zRBAC:` block is the verb's previous name; auto-lowers to `zGate` + logs a one-time nudge; write NEW gates as `zGate:`
    rule     — no permissions tables / role rankings; the wired model is session-only, exact-match

knobs: lines inside one `zGate:` block — fail ANY posted rule → turned away
    authed: true       — signed-in only
    authed: false      — signed-OUT only (the "guests only" — great for a Login link)
    role: [zAdmin]     — only these role(s); a LIST = any ONE gets in
    require: {tier: pro}— check ANY visitor attribute; must match (a list = membership)
    combine — stack lines → AND; fancier logic speaks `zAll`/`zAny`/`zNot`, but most pages need ONE line
    onDenied— a COMPANION BESIDE the block, never inside: `onDenied: {zLink: @.zViews…}` where to send someone turned away (a reaction, not a question — nesting it breaks the gate)

where: post the doorman at the SMALLEST door — same block, four homes
    page       — top of a zUI block, guards the whole view
    route      — in `routes/` (`zServer.*.zolo`), checked BEFORE any file opens
    nav_item   — under a navbar entry, the link only APPEARS for the allowed
    action_row — on one button/menu item, hidden AND refused for everyone else
    rule       — server-side: a hidden item can't be triggered by a forged request

denial: two refusals told apart
    not_signed_in — walked to the login page; default door set once in `zEnv` (`ZAUTH_LOGIN_ROUTE`), `onDenied` overrides per gate
    wrong_role    — NOT sent to login (already inside); a quiet 403, without revealing which role was needed, unless the gate sets `onDenied`

roles: the names are YOURS — no fixed zOS role list
    define   — name roles in your own `zSchema.roles`; `role` checks the visitor's `users.role` against your names
    example  — zCloud uses zAdmin/zEditor/zBuilder/zViewer/zGuest/zAgent (its set, not zOS's); yours might be owner/member/billing
    matching — EXACT by name; list several → any one qualifies; NO ranking (a senior role clearing a junior gate just lists both) — `role_checker.py`, session-only
    maturing — ONE role per visitor today; multi-role (`user_roles`) on the roadmap

login: `zLogin` = the front desk turning a guest session into a signed-in one carrying a role — one block, no plugin code
    grammar  — a `zLogin:` block IS a zDialog whose submit runs the zAuth `zLogin` action (renders form, verifies, writes session) — `action_login.py`
    props    — model (user schema, required) · fields (order, e.g. `[email, password]`; `inputs` aliases) · title · zAPI: true (web form can post) · onSuccess (a zEvent, usually a zLink redirect) · zApp (label wording only)
    automatic— from `model` alone finds the table + identity field (email/username), bcrypt-checks LOCALLY against your ledger (password never lands in the session), stamps the tag
    writes   — ONE flat `session["zVisitor"]` `{authenticated, id, username, role, api_key}`; the `role` comes from the user's record — the SAME value `zRBAC`'s `role` gate reads (one SSOT)
    persist  — a durable identity token → stays signed in across reload/new tab (cookie seam → Sessions); logout clears it
    single_identity — one signed-in identity per visit; `zLogin: myapp` vs reserved `zLogin: zolo` check the SAME ledger + write the SAME session (keyword only changes welcome wording)
    scope    — APP-USER sign-in, NOT the instance owner (`z login`/PAT → Foundations › zAuth)

logout: `zLogout: <app>` is the mirror
    wipes `session["zVisitor"]` to blank + clears the durable token (reload won't bring them back), then lands home — `action_logout.py`
    gate the LINK with `zGate: {authed: true}` so only signed-in visitors see it

proven: exercised by a fresh isolated app (`Tests/zRBAC_app`, Bifrost)
    click gate matrix — every gate × guest/viewer/editor/admin: each role sees exactly what it should
    exact-name matching holds — one role in, others out
    concurrent mixed-role stress — many roles at once, ZERO cross-session bleed
    caveat — ALPHA: a clean lab run isn't a production promise; a doorman letting the wrong person through is a BUG worth reporting
    golden — `zDemos/zTeamVault`: zLogin + a gated Vault + zLogout, CLI-first then Bifrost, zRaven-covered both modes
    golden — `zDemos/zBlog`: self-service SIGNUP (a plain zDialog + `zData: {action: insert}` on the user's OWN
        schema, `zHash: bcrypt` on the password field — no zLogin needed to CREATE the account, only to sign into
        it after) + ROW-level ownership (not just page/route gating): `zGate: {%item.Posts.author_id: %session.zVisitor.id}`
        inside a `zList` each-template hides Edit/Delete unless the signed-in visitor OWNS that row — both sides of
        the comparison are `%` tokens, resolved symmetrically; the SAME id also re-checked server-side in the
        update/delete `where:` (`where: id = %item.Posts.id zAND author_id = %session.zVisitor.id`) so a forged
        request against someone else's row still bounces even if the button were somehow clicked

routing_gotcha: a gated page needs its OWN route to actually redirect in Bifrost
    rule    — `onDenied`/zLogin `onSuccess`/zLogout `onSuccess` are always a `zLink` — Bifrost resolves it to a router URL, never an in-page swap (identity moves the SESSION, so the page must move too; a plain zDialog's `onSuccess` is the opposite tool — an in-place `zDelta` re-walk → Forms `onsuccess`)
    trap    — Login/Vault/Logout as BLOCKS inside the home zVaFile share ITS one URL (14_server.md "one file = one URL"); a redirect to another block in the SAME file resolves back to `/` and silently re-renders the home block instead
    fix     — give each gated page its OWN `zUI.<Page>.zolo` file in `zViews/` so the router auto-discovers a real URL (`/Login`, `/Vault`, `/Logout`) for the zLink to land on — the pattern `zDemos/zTeamVault` and `Tests/zRBAC_app` both use

where_it_lives: trace a piece
    zGate.py (`core/L3_Abstraction/n_zLoom/`) — authored verb + lowering (legacy `zRBAC:` / wizard `if:` → one IR)
    check_zrbac (`core/L2_Handling/f_zAuth/.../logic/rbac/`) — trust engine: reads live session, honours authed/zGuest/role/require ONLY
    role_checker.py — exact-name match, session-only, no hierarchy/level
    action_login.py / action_logout.py (`f_zAuth/.../actions/`) — writes + clears `session["zVisitor"]`
    recap — 1) three whos (this = app users) · 2) one verb `zGate:` (auth → RBAC engine) · 3) knobs authed/role/require, onDenied a SIBLING · 4) four homes, server-side · 5) roles yours, exact-match, one per visitor · 6) zLogin/zLogout write the tag the gate reads
