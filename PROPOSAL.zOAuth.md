# PROPOSAL: zOAuth — provider sign-in (Google / Facebook) for the credential lane

Status: ENGINE HALF BUILT + PINNED (2026-09-07, same day as the green light).
`action_oauth.py` (f_zAuth) + `oauth_endpoints.py` (r_zServer) + dispatcher
hook; 17 pytest pins green (tests/test_zoauth.py), full zOS suite 389 passed;
live smoke on zPlanner's always-on 9091: `/zauth/google/start` answers
302 → `/?zauth_error=provider_unavailable` (correct — no creds configured).
Remaining before DONE: real Google dev credentials smoke, the consuming app's
ledger columns (zPlanner board carries it), and the optional zLogin
`providers:` button sugar. Target: 1.7.5 — NOT on the 1.7.4 critical path.

## The gap

`f_zAuth` has exactly one way in: bcrypt against a local ledger (zLogin).
Every consumer-facing zApp (zPlanner's landing being the driver) needs
"Continue with Google/Facebook" — and the engine has zero provider trace.
This is a new lane, not a tweak.

## What already exists (and is reused wholesale — no new mechanics)

The bring-up mapping found the hard parts are ALREADY BUILT:

- **Per-request session + durable cookie**: every routed HTTP request runs in
  its own session unit with a `zsid` cookie minted/rehydrated
  (`route_dispatcher._enter_request_session`). The callback request therefore
  holds `session["_zsid"]` with zero new transport work.
- **Identity stamping SSOT**: `action_login._apply_zvisitor(user, …)` writes
  `session["zVisitor"]`, regenerates the session hash, clears UI caches for
  RBAC re-eval, and write-throughs the identity into the session_store under
  the caller's `_zsid` — so the NEXT page load / WS resume rehydrates
  signed-in. OAuth's callback calls the same function with a ledger row it
  verified via the provider instead of via bcrypt. One login SSOT, two doors.
- **Ledger auto-discovery**: `ZAUTH_USER_MODEL` (zEnv) → model path → table,
  the same resolution zLogin uses.

## Grammar: NONE (string-first, by design)

No new zolo grammar for the MVP. The sign-in buttons are plain links:

    zURL: /zauth/google/start
    zURL: /zauth/facebook/start?next=/Settings

`/zauth/<provider>/start` and `/zauth/<provider>/callback` are BUILT-IN
endpoints (same seam as /robots.txt and /api/route-config: served when the
app has no explicit route for the path — an app can shadow them). A later
`providers: [google]` sugar on the zLogin block can render the buttons, but
that is client polish, not engine.

## The flow

1. **start** — mint `state` (CSRF token) + PKCE verifier (S256, Google), stash
   `{provider, verifier, next, zsid, ts}` in an in-process TTL registry keyed
   by state (10 min; single-process server — no store round-trip needed), 302
   to the provider's authorize URL. `next` is same-origin-path-only
   (must start with single `/`).
2. **callback** — `?code&state`: state must exist, be fresh, and have been
   minted for the SAME `zsid` cookie (binds the browser that started to the
   one that finishes). Exchange code→token server-side (stdlib urllib, 10s
   timeout, no new deps), fetch userinfo over TLS — the userinfo response IS
   the identity truth (no JWT signature dependency; the token came straight
   from the provider over TLS in the same breath).
3. **link** — find-or-create in the app's OWN ledger (`ZAUTH_USER_MODEL`):
   - match on `(oauth_provider, oauth_subject)` — two columns the ledger MUST
     declare, or zOAuth refuses with a clear log (misconfig, not a 500).
   - first sign-in CREATES a row: username from email local-part (uniquified),
     `email`/`person` filled when the schema has them, `password` set to a
     LOCKED random bcrypt hash when the schema requires one (an OAuth-born
     user cannot sign in locally), role left to the SCHEMA DEFAULT — least
     privilege, never owner. Google identities with `email_verified: false`
     are refused.
4. **stamp** — `_apply_zvisitor(row, …)` + 302 to `next` (default `/`).
   Durability comes free via the existing `_zsid` write-through.
   Failures 302 to `/?zauth_error=<code>` (reason logged server-side, never
   leaked to the URL beyond a coarse code).

## Config (zEnv, git-ignored layer — same discipline as PayPal keys)

    ZOAUTH_GOOGLE_CLIENT_ID / ZOAUTH_GOOGLE_SECRET
    ZOAUTH_FACEBOOK_CLIENT_ID / ZOAUTH_FACEBOOK_SECRET

A provider is live iff both halves are present. Endpoint URLs have env
overrides (`ZOAUTH_GOOGLE_AUTH_URL` …) — that's the test seam AND the escape
hatch for future/self-hosted providers. Redirect URI is derived from the
request base (proxy-aware: X-Forwarded-Host/Proto) + `/zauth/<p>/callback`;
`http://localhost:<port>/…` is a valid Google dev redirect.

## Security posture

- `state`: unguessable, single-use, TTL 10 min, zsid-bound.
- PKCE S256 on Google (Facebook doesn't support it; omitted there).
- Provider tokens are used once (userinfo) and DROPPED — never stored, never
  in the session.
- Subjects are provider-scoped ids (Facebook's are app-scoped) — the
  `(provider, subject)` pair is the only linking key; email is display data,
  never a join key (email reuse across providers must not merge accounts).
- Secrets live in the git-ignored zEnv layer; the engine never logs them.

## Out of scope (deliberately)

- Account MERGING (same human, local + OAuth rows) — a later, owner-driven
  flow; automatic email-based merging is an account-takeover vector.
- id_token JWT validation / JWKS — not needed while userinfo-over-TLS is the
  truth source; revisit if a provider without a userinfo endpoint lands.
- zCLI: no behavior (the links render as text; the lane is browser-only).

## Proof plan

- pytest (zOS suite): fake provider via the endpoint-override env seam +
  monkeypatched HTTP fetch — start hop pins the authorize URL contract
  (client_id, redirect_uri, state, PKCE), callback pins state misuse
  (missing/expired/wrong-zsid), ledger contract refusal, first-sign-in row
  creation shape, and the zVisitor stamp.
- Manual Google smoke on zPlanner's 9091 instance once dev credentials exist
  (needs the Users ledger's two oauth columns — filed on the zPlanner board).
