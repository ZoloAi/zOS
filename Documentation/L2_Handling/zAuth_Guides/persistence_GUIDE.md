**[← Back to zAuth Guide](../zAuth_GUIDE.md)**

---

# Persistence Module Guide

**Module**: `zAuth_modules/persistence/identity_store.py` (sealed seam)
**Purpose**: Persist the signed-in Tier-1 (zSession) identity for this machine

> **Heads-up:** the old SQLite `SessionPersistence` / `SessionStore` /
> `SessionDatabase` design has been **retired**. Tier-1 identity is now a single
> declarative file, read once at boot — there is no SQLite session DB and no
> expiry sweep. (RBAC *permissions* still use SQLite — see
> [rbac_GUIDE.md](rbac_GUIDE.md).)

---

## Overview

Login persistence is a single small record — "which zolo account is signed in on
this machine" — so it lives as one declarative file, git/ssh-style:

```
<user_config>/zConfigs/zConfig.identity.zolo
```
```yaml
# zOS machine identity — the signed-in zolo account for this machine.
zIdentity:
    username: user@zolo.com
    user_id: zU_123
    role: admin
    api_key: zk_…
    issued_at: 2026-05-31T12:00:00Z
```

- **Machine-scoped** (one signed-in account per box, like `git config --global` /
  `gh auth`).
- **zCloud stays the authority** and user ledger; this file only records the
  *result* of a successful login.
- Written **owner-only** (`chmod 0o600`) — it is a credential file.

## Open / closed split

`persistence/identity_store.py` in open-core is a **shim**. The real read/write/
clear (and OS-keychain sealing in production) is the sealed
`zguard.auth.identity_store` (Type A2).

| Function | Open-core (no zGuard) | With zGuard |
|----------|-----------------------|-------------|
| `load_identity(zos)` | `None` | parse `zConfig.identity.zolo` → `zIdentity` block |
| `save_identity(zos, identity)` | `False` | write the file (0o600) |
| `clear_identity(zos)` | `False` | delete the file |
| `identity_path(zos)` | `None` | absolute path to the file |
| `IDENTITY_FILENAME` / `IDENTITY_BLOCK` | mirrored constants | mirrored constants |

So **without zGuard the machine simply boots anonymous** — nothing is persisted or
restored. Imports never break (the shim mirrors the public names).

## How it's used

- `login(persist=True)` → after a successful verify, `_persist_zsession_identity()`
  calls `save_identity({username, user_id, role, api_key})`.
- Boot → the sealed `boot_identity` cascade calls `load_identity()` first
  (persistent tier) to restore "already logged in".
- `logout(delete_persistent=True)` (the default) → `clear_identity()` signs the
  machine out.

```python
# All via the public facade — no direct module access needed:
zos.auth.login("user@zolo.com", "pw", persist=True)   # records identity
zos.auth.is_authenticated()                             # True after boot restore
zos.auth.logout(delete_persistent=True)                 # sign-out (removes file)
```

## Mechanism (sealed)

The file format, path resolution, permission hardening, `.zolo` parse-back, and
production keychain sealing are documented in the **private zGuard** docs:
`zGuard/Documentation/auth/identity_store_GUIDE.md`. Open-core only needs the
contract above.

> Requires zGuard for actual persistence — contact admin / `z patch`.

---

**[← Back to zAuth Guide](../zAuth_GUIDE.md)**
