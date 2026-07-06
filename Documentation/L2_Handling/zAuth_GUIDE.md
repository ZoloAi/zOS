**[← Back to e_zDisplay Guide](zDisplay_GUIDE.md) | [Home](../../README.md) | [Next: g_zDispatch Guide →](zDispatch_GUIDE.md)**

---

# f_zAuth

**f_zAuth** is the **third Layer 2 subsystem** in **zOS** (Layer 2: Handling) - providing authentication and authorization.
> Located at: `zOS/core/L2_Handling/f_zAuth/`
> See [**zArchitecture**](../README.md#the-zarchitecture) for full context.

It provides a **three-tier authentication model** with **bcrypt password security**, a **git-like persistent machine identity**, and **context-aware RBAC** (Role-Based Access Control). All **Layer 2+ subsystems** can rely on **f_zAuth** for secure user management.

You get:

- **Three-tier authentication** (zSession, Application, Dual-mode)
- **Zero configuration** security with industry-standard bcrypt
- **Persistent machine identity** — one signed-in account per box (git/ssh-style, `zConfig.identity.zolo`)
- **Context-aware RBAC** with dynamic permissions (SQLite-backed permissions)
- **Multi-app support** (simultaneous authentication)
- **Declarative actions** (zLogin, zLogout)

> **Open-core vs. zGuard.** The local pieces here — bcrypt, local-ledger login,
> RBAC, contexts, actions — work standalone. The **ecosystem-auth** pieces (zCloud
> remote login, Personal Access Tokens, identity-at-rest, the boot cascade) are
> **sealed in zGuard** (Type A2) and fail closed without it. See
> [Trust Model & zGuard Seams](#trust-model--zguard-seams) below.

## Architecture Overview

**f_zAuth** is composed of specialized modules organized in a layered architecture:

| Module | Purpose | Guide |
|--------|---------|-------|
| **security** | bcrypt password hashing and verification | [security_GUIDE.md](zAuth_Guides/security_GUIDE.md) |
| **persistence** | Machine identity at rest (`zConfig.identity.zolo`) — sealed seam | [persistence_GUIDE.md](zAuth_Guides/persistence_GUIDE.md) |
| **authentication** | Three-tier auth logic (zSession, App, Dual) | [authentication_GUIDE.md](zAuth_Guides/authentication_GUIDE.md) |
| **rbac** | Context-aware role and permission management (SQLite) | [rbac_GUIDE.md](zAuth_Guides/rbac_GUIDE.md) |
| **actions** | Declarative login/logout handlers | [actions_GUIDE.md](zAuth_Guides/actions_GUIDE.md) |
| **delegates** | Public API facade (16 methods) | [delegates_GUIDE.md](zAuth_Guides/delegates_GUIDE.md) |

This guide provides a **facade overview** of f_zAuth. For deep dives into specific modules, see the guides in `zAuth_Guides/`.

> **Note on persistence:** Tier-1 identity persists git-like to a single
> `zConfig.identity.zolo` file (read once at boot) — **not** a SQLite session DB.
> The older `SessionPersistence`/SQLite-sessions path has been retired. RBAC
> *permissions* still use SQLite.

---

## Three-Tier Authentication Model

f_zAuth implements a sophisticated three-tier authentication system that handles different authentication contexts:

### Tier 1: zSession Authentication (Internal Users)

**Purpose**: Authenticate zOS/Zolo platform users for premium features, plugins, and cloud services.

**Use Cases**:
- zOS developer accessing premium features
- Plugin authentication and licensing
- Cloud service integration
- Cross-application identity

**Session Key**: `session["zAuth"]["zSession"]`

### Tier 2: Application Authentication (External Users)

**Purpose**: Authenticate end-users of applications BUILT with zOS.

**Features**:
- Independent user database per application
- Multiple simultaneous app authentications
- App-specific credentials and sessions
- Isolated security contexts

**Session Key**: `session["zAuth"]["applications"][app_name]`

### Tier 3: Dual-Mode Authentication (Both Contexts)

**Purpose**: Both zSession AND application authenticated simultaneously.

**Example**: Store owner analyzing their store as both:
- zOS user (platform access)
- Store user (application access)

**RBAC Behavior**: Uses OR logic - either context can grant access

**Session Key**: `session["zAuth"]["dual_mode"] = True`

---

## Trust Model & zGuard Seams

f_zAuth is the first subsystem split **open / closed** by design. The split is
along the *authority*: anything local and standard is open-core; anything that is
ecosystem (zCloud) auth is sealed in **zGuard** (Type A2 — commercially licensed
binary wheel).

| Capability | Where | Without zGuard |
|------------|-------|----------------|
| bcrypt password hashing/verify | **open-core** | works |
| local-ledger login (`login()` default) | **open-core** | works |
| RBAC roles & permissions | **open-core** | works |
| contexts, multi-app session bookkeeping, actions | **open-core** | works |
| **PAT** issue/verify/authenticate (`api_key_auth`) | **sealed** | `ImportError` "z patch" |
| **Remote** zCloud handshake (`remote_authentication`) | **sealed** | unavailable (local login still works) |
| **Identity at rest** (`identity_store`, OS keychain) | **sealed** | no-op → boots anonymous |
| **Boot identity cascade** (`boot_identity`) | **sealed** | unavailable |

Key properties:

- **The sealed seams fail closed.** They raise a clear "requires zGuard / `z patch`"
  (or degrade to anonymous) — they never fabricate an identity. Tier-2
  `authenticate_app_user` routes through the PAT seam for exactly this reason.
- **One verification SSOT.** zGuard does not re-implement credential checking; it
  reuses the open-core `action_login` path (`authenticate_zolo_credentials` /
  `_apply_zsession`). There is exactly one place a password is checked.
- **zGuard binary ≠ login.** With the binary present, anonymous (not-logged-in)
  users still get the full runtime; login is a separate trust tier, never a gate
  on general use.

> Mechanism docs for the sealed seams live in the **private zGuard** docs
> (`zGuard/Documentation/auth/`), not here — per the docs-split rule. Open-core
> documents the seam **contract** and the "ask admin / `z patch`" pointer only.

---

## Initialization

When **zOS** loads the **f_zAuth** subsystem (Layer 2: Handling), it automatically:

**Layer 1 (Foundation):**
1. **zConfig** - Configuration management
2. **zComm** - Communication infrastructure
3. **zLoader** - Dynamic module loading

**Layer 2 (Handling):**
1. **d_zParser** - Command and file parsing
2. **e_zDisplay** - Display and UI rendering
3. **f_zAuth** - Authentication subsystem:
   - Initializes three core modules:
     - `PasswordSecurity` - bcrypt hashing with 12 rounds
     - `Authentication` - Three-tier auth logic
     - `RBAC` - Context-aware access control (SQLite permissions)
   - Tier-1 identity persists via `persistence/identity_store` (the
     `zConfig.identity.zolo` file; the at-rest/keychain mechanism is sealed in zGuard)
   - Defers permissions-DB initialization until first use (lazy loading)
   - Displays ready message via e_zDisplay
   - Composes public API via delegate pattern (16 methods)

No setup required. Just import and use:

```python
from zOS import zOS

# Initialize zOS (includes f_zAuth)
zos = zOS()

# f_zAuth is ready to use
zos.auth.login("user@zolo.com", "secure_password")
```

---

## Tutorials

**Learn by doing!**

The tutorials below are organized in a bottom-up fashion. Every tutorial has working demos you can run and modify.

**A Note on Learning zOS:**  
Each tutorial (lvl1, lvl2, lvl3...) progressively introduces more complex features of **this subsystem**. The early tutorials start with familiar imperative patterns (think Django-style conventions) to meet you where you are as a developer.

As you progress through zOS's subsystems, you'll notice a gradual shift from imperative to declarative patterns. This intentional journey helps reshape your mental model from imperative to declarative thinking. Only when you reach **Layer 3 (Orchestration)** will you see subsystems used **fully declaratively** as intended in production.

Get the demos:

```bash
# Clone only the Demos folder
git clone --depth 1 --filter=blob:none --sparse https://github.com/ZoloAi/zolo-zcli.git
cd zolo-zcli
git sparse-checkout set Demos
```

> All f_zAuth demos are in: `Demos/Layer_2/zAuth_Demo/`

---

# **f_zAuth - Level 1** (Basic Authentication)

## **i. Password Security**

Secure password hashing with bcrypt:

```python
from zOS import zOS

zos = zOS()

# Hash a password (12 rounds, ~0.3s)
hashed = zos.auth.hash_password("secure_password")
print(f"Hash: {hashed[:20]}...")  # $2b$12$...

# Verify password
is_valid = zos.auth.verify_password("secure_password", hashed)
print(f"Valid: {is_valid}")  # True

# Wrong password
is_valid = zos.auth.verify_password("wrong_password", hashed)
print(f"Valid: {is_valid}")  # False
```

**What happened?**
- bcrypt with 12 rounds (4,096 iterations)
- Random salt per hash (rainbow table resistant)
- Timing-safe verification (prevents timing attacks)
- ~0.3 seconds per operation (brute-force protection)

---

## **ii. zSession Authentication (Tier 1)**

Login as a zOS/Zolo platform user:

```python
from zOS import zOS

zos = zOS()

# Login (zSession context)
result = zos.auth.login(
    username="user@zolo.com",
    password="secure_password",
    persist=True  # Record identity to disk (zConfig.identity.zolo)
)

# login() returns {"status": "success"|"fail", "user": {...}}
if result["status"] == "success":
    user = result["user"]
    print(f"Logged in as: {user['username']}")
    print(f"Role: {user['role']}")
    print(f"User ID: {user['user_id']}")

# Check authentication status
if zos.auth.is_authenticated():
    print("User is authenticated!")

# Get current credentials
creds = zos.auth.get_credentials()
print(f"Username: {creds['username']}")

# Logout
result = zos.auth.logout()
print(f"Logged out: {result['status']}")
```

**What happened?**
- Verified against the **local user ledger** by default (same SSOT path as `zolo login`); set `ZOLO_USE_REMOTE_API=true` to authenticate against the zCloud authority instead (sealed in zGuard)
- On success, identity written to `session["zAuth"]["zSession"]`
- With `persist=True`, the identity is recorded to `zConfig.identity.zolo` (the git-like "already logged in" record read at boot) — no SQLite session DB
- Active context set to "zSession"

---

## **iii. Check Authentication Status**

Query current authentication state:

```python
from zOS import zOS

zos = zOS()

# Get comprehensive status
# status() -> {"status": "authenticated"|"not_authenticated", "user": {...},
#              "zsession": {...}, "applications": {...}, "active_context": ..., "dual_mode": bool}
status = zos.auth.status()

print(f"Authenticated: {status['status'] == 'authenticated'}")
print(f"Active Context: {status['active_context']}")

if status['zsession']:
    print(f"zSession User: {status['zsession']['username']}")
    print(f"Role: {status['zsession']['role']}")

if status['applications']:
    print(f"Active Apps: {list(status['applications'].keys())}")
```

---

# **f_zAuth - Level 2** (Multi-Tier Authentication)

## **i. Application Authentication (Tier 2)**

Authenticate an app-scoped user by **token**. The token is a **Personal Access
Token (PAT)** verified against the user ledger; verification is **sealed in
zGuard** (Type A2) and **fails closed** without it — it never fabricates an
identity.

```python
from zOS import zOS

zos = zOS()

# Authenticate app user by PAT
result = zos.auth.authenticate_app_user(
    app_name="my_store",
    token="zk_…",          # a PAT issued for a ledger user
    config=None             # optional: {"user_model": "@.…", "id": "id", ...}
)

# returns {"status": "success", "app_name": ..., "user": {...}, "context": ...}
#      or {"status": "error",   "app_name": ..., "reason": ...}
if result["status"] == "success":
    print(f"App user authenticated: {result['user']['username']}")
    print(f"Store: {result['app_name']}")

# Get app user info
app_user = zos.auth.get_app_user("my_store")
if app_user:
    print(f"Store user: {app_user['username']} ({app_user.get('role')})")
```

**What happened?**
- The token was verified via the sealed PAT seam (`api_key_auth.verify_api_key`,
  i.e. `sha256(token)` looked up in the ledger). The **real** user row is stored
  in `session["zAuth"]["applications"]["my_store"]` — no placeholder identity.
- **Without zGuard** the seam raises "z patch" and `authenticate_app_user` returns
  `{"status": "error", ...}`. App-token auth is an ecosystem (zCloud) capability.
- Multi-app support: multiple apps can be authenticated simultaneously.

> See [Trust Model & zGuard Seams](#trust-model--zguard-seams) and the private
> zGuard PAT docs for the mechanism.

---

## **ii. Multi-App Authentication**

Authenticate multiple applications simultaneously:

```python
from zOS import zOS

zos = zOS()

# Authenticate user for multiple apps
apps = [
    ("store_app", "token_store_xyz"),
    ("blog_app", "token_blog_abc"),
    ("forum_app", "token_forum_123")
]

for app_name, token in apps:
    result = zos.auth.authenticate_app_user(
        app_name=app_name,
        token=token
    )
    print(f"{app_name}: {result['status']}")

# Get status shows all active apps
status = zos.auth.status()
print(f"Active apps: {list(status['applications'].keys())}")

# Switch active app
zos.auth.switch_app("blog_app")
active_user = zos.auth.get_active_user()
print(f"Active: {active_user['username']} in {active_user['app_name']}")
```

---

## **iii. Context Management**

Switch between authentication contexts:

```python
from zOS import zOS

zos = zOS()

# Login as zOS user
zos.auth.login("dev@zolo.com", "password")

# Authenticate as app user
zos.auth.authenticate_app_user("my_app", "token")

# Set context to zSession
zos.auth.set_active_context("zSession")
user = zos.auth.get_active_user()
print(f"Active: {user['username']} (zSession)")

# Set context to application
zos.auth.set_active_context("application")
user = zos.auth.get_active_user()
print(f"Active: {user['username']} (my_app)")

# Set context to dual (both)
zos.auth.set_active_context("dual")
# Now RBAC checks use OR logic (either context grants access)
```

**Available Contexts**:
- `"zSession"` - zOS/Zolo user context (Tier 1)
- `"application"` - Active app user context (Tier 2)
- `"dual"` - Both contexts active (Tier 3)

---

# **f_zAuth - Level 3** (RBAC - Role-Based Access Control)

## **i. Role Checks**

Check if user has required role(s):

```python
from zOS import zOS

zos = zOS()

# Login with role
zos.auth.login("admin@zolo.com", "password")  # Role: admin

# Check single role
if zos.auth.has_role("admin"):
    print("User is admin!")

# Check multiple roles (OR logic)
if zos.auth.has_role(["admin", "moderator"]):
    print("User is admin OR moderator")

# Common roles
roles = ["user", "admin", "moderator", "developer", "premium"]
```

**Context-Aware Behavior**:
- `"zSession"` context: Checks zSession role
- `"application"` context: Checks active app user role
- `"dual"` context: Checks both (OR logic - either can grant)

---

## **ii. Permission Checks**

Check granular permissions:

```python
from zOS import zOS

zos = zOS()

# Check permission
if zos.auth.has_permission("data.delete"):
    print("User can delete data")

# Grant permission (requires user_id)
success = zos.auth.grant_permission(
    user_id="zU_12345",
    permission="content.publish",
    granted_by="admin@zolo.com"
)

# Revoke permission
success = zos.auth.revoke_permission(
    user_id="zU_12345",
    permission="content.publish"
)

# Permission naming convention
permissions = [
    "data.read",
    "data.write",
    "data.delete",
    "content.create",
    "content.publish",
    "admin.users",
    "admin.settings"
]
```

**Permission Storage**:
- Stored in SQLite database (the `user_permissions` table, via zData)
- Persistent across restarts
- User-specific granular control
- Context-aware in dual mode

---

## **iii. RBAC with Multi-App**

RBAC works across all three authentication tiers:

```python
from zOS import zOS

zos = zOS()

# Login as zOS user (admin)
zos.auth.login("admin@zolo.com", "password")  # Role: admin

# Authenticate as app user (moderator)
zos.auth.authenticate_app_user(
    app_name="forum",
    token="token"  # App returns role: moderator
)

# zSession context - checks zOS role
zos.auth.set_active_context("zSession")
print(zos.auth.has_role("admin"))      # True (zOS role)
print(zos.auth.has_role("moderator"))  # False

# Application context - checks app role
zos.auth.set_active_context("application")
print(zos.auth.has_role("admin"))      # False
print(zos.auth.has_role("moderator"))  # True (app role)

# Dual context - OR logic
zos.auth.set_active_context("dual")
print(zos.auth.has_role("admin"))      # True (zOS grants)
print(zos.auth.has_role("moderator"))  # True (app grants)
print(zos.auth.has_role(["admin", "moderator"]))  # True (either)
```

---

# **f_zAuth - Level 4** (Persistent Identity & Remote Auth)

## **i. Persistent Machine Identity**

The signed-in identity persists git/ssh-style — one signed-in account per machine,
read once at boot:

```python
from zOS import zOS

# First run - login with persist=True
zos1 = zOS()
zos1.auth.login(
    username="user@zolo.com",
    password="password",
    persist=True  # Record identity to zConfig.identity.zolo
)
print("Identity recorded to disk")

# Later run - identity restored at boot
zos2 = zOS()
# identity_store reads zConfig.identity.zolo during the boot cascade

if zos2.auth.is_authenticated():
    creds = zos2.auth.get_credentials()
    print(f"Restored identity: {creds['username']} ({creds['role']})")
```

**Identity Details**:
- A single declarative file: `<user_config>/zConfigs/zConfig.identity.zolo`
  (`zIdentity:` block), written owner-only (`0o600`) — **not** a SQLite session DB
- Machine-scoped (like `git config --global` / `gh auth`); zCloud stays the authority
- Only the zSession (Tier-1) identity persists; app (Tier-2) auth is transient
- `logout(delete_persistent=True)` (the default) removes the file (sign-out)

> The at-rest persistence (and OS-keychain sealing in production) lives in the
> **sealed** `identity_store` seam — see [persistence_GUIDE.md](zAuth_Guides/persistence_GUIDE.md)
> and the private zGuard docs.

---

## **ii. Remote Authentication (zCloud)**

By default `login()` verifies against the **local user ledger**. To authenticate
against the remote **zCloud authority**, set `ZOLO_USE_REMOTE_API=true` (or pass
`server_url`):

```python
import os
from zOS import zOS

os.environ["ZOLO_USE_REMOTE_API"] = "true"
zos = zOS()

result = zos.auth.login(
    username="user@zolo.com",
    password="password",
    server_url="https://auth.zolo.com/api/login"  # optional; else ZOLO_API_URL/default
)

if result["status"] == "success":
    print(f"Authenticated remotely: {result['user']['username']}")
```

**The remote handshake is sealed in zGuard (Type A2).** Open-core selects the
remote path and exposes the `authenticate_remote` seam contract; the actual
instance→zCloud wire handshake (and the PAT it returns) is the zGuard mechanism.
Without zGuard, the remote path is unavailable — local-ledger login still works.

> Requires zGuard, contact admin / `z patch`. Mechanism: private zGuard auth docs
> (`remote_authentication`).

---

## **iii. Logout Options**

Multiple logout behaviors:

```python
from zOS import zOS

zos = zOS()
zos.auth.login("user@zolo.com", "password", persist=True)

# Logout zSession only (default)
result = zos.auth.logout()
# - Clears session["zAuth"]["zSession"]
# - App sessions remain active

# Logout specific app
result = zos.auth.logout(
    context="application",
    app_name="my_store"
)
# - Clears session["zAuth"]["applications"]["my_store"]

# Logout all contexts
result = zos.auth.logout(context="all")
# - Clears zSession and all app sessions

# Delete persistent identity from disk (this is the default)
result = zos.auth.logout(delete_persistent=True)
# - Clears in-memory session
# - Deletes the zConfig.identity.zolo file (git-like sign-out)
```

---

# **f_zAuth - Level 5** (Declarative Actions & Integration)

## **i. Built-in Actions**

f_zAuth provides declarative login/logout actions:

```python
from zOS import zOS

zos = zOS()

# These actions are automatically registered
# Use with zDispatch, zBifrost, or zVaF

# Action: zLogin
action_zlogin = {
    "action": "zLogin",
    "username": "user@zolo.com",
    "password": "password",
    "persist": True,
    "server_url": None  # Optional
}

# Action: zLogout
action_zlogout = {
    "action": "zLogout",
    "context": "zSession",  # or "application", "all"
    "app_name": None,       # Required if context="application"
    "delete_persistent": False
}

# Dispatch actions
zos.dispatch.execute(action_zlogin)
zos.dispatch.execute(action_zlogout)
```

**Integration Points**:
- **zDispatch**: Execute auth actions from action queues
- **zBifrost**: Trigger login/logout from UI interactions
- **zVaF**: Menu items with `require_auth`, `require_role`, `require_permission`

---

## **ii. zVaF Menu Protection**

Protect menu items with auth directives:

```yaml
# menu_config.yaml
menu:
  - id: home
    label: Home
    # Public - no auth required
    
  - id: dashboard
    label: Dashboard
    require_auth: true
    # Requires any authentication
    
  - id: admin_panel
    label: Admin Panel
    require_role: admin
    # Requires admin role
    
  - id: delete_data
    label: Delete Data
    require_permission: data.delete
    # Requires specific permission
    
  - id: premium_features
    label: Premium Features
    require_role: [premium, admin]
    # Requires premium OR admin role
```

zWizard automatically checks auth requirements and hides/disables protected items.

---

## **iii. Integration with zOS Subsystems**

f_zAuth integrates seamlessly with other zOS subsystems:

```python
from zOS import zOS

zos = zOS()

# Layer 1 Dependencies:
# - zConfig: Session structure and constants
#   - SESSION_KEY_ZAUTH = "zAuth"
#   - ZAUTH_KEY_ZSESSION = "zSession"
#   - ZAUTH_KEY_APPLICATIONS = "applications"
#   - All auth data stored in session["zAuth"]
#
# - zComm: Remote authentication transport (HTTP primitive)
#   - The zCloud handshake itself is sealed in zGuard (Type A2)
#   zos.auth.login("user", "pass", server_url="https://...")  # ZOLO_USE_REMOTE_API=true

# Layer 2 Sibling Dependencies:
# - e_zDisplay: All UI feedback
zos.auth.login("user", "pass")
# -> e_zDisplay.success("Logged in successfully")
# -> e_zDisplay.error("Invalid credentials")

# Layer 3+ Dependencies:
# - zData: Persistent storage
#   - The user ledger + RBAC permissions are stored via zData (SQLite)
#   - Tier-1 identity is the zConfig.identity.zolo file, NOT a SQLite session
#   - Declarative operations (no raw SQL)
#
# - zWizard: Access control
#   - Menu items protected by has_role() and has_permission()
#   - Automatic integration via require_auth/role/permission
#
# - zBifrost: Web UI authentication
#   - Login forms trigger zLogin action
#   - Protected routes check is_authenticated()
```

---

## API Reference

### Password Security (2 methods)

```python
# Hash password
hashed: str = zos.auth.hash_password(plain_password: str)

# Verify password
is_valid: bool = zos.auth.verify_password(
    plain_password: str,
    hashed_password: str
)
```

### zSession Authentication (5 methods)

```python
# Login
result: Dict = zos.auth.login(
    username: str,
    password: str,
    server_url: Optional[str] = None,
    persist: bool = True
)

# Logout
result: Dict = zos.auth.logout(
    context: str = "zSession",
    app_name: Optional[str] = None,
    delete_persistent: bool = False
)

# Get status
status: Dict = zos.auth.status()

# Check authentication
is_authed: bool = zos.auth.is_authenticated()

# Get credentials
creds: Optional[Dict] = zos.auth.get_credentials()
```

### Application Authentication (3 methods)

```python
# Authenticate app user
result: Dict = zos.auth.authenticate_app_user(
    app_name: str,
    token: str,
    config: Optional[Dict] = None
)

# Switch active app
success: bool = zos.auth.switch_app(app_name: str)

# Get app user
user: Optional[Dict] = zos.auth.get_app_user(app_name: str)
```

### Context Management (2 methods)

```python
# Set active context
success: bool = zos.auth.set_active_context(
    context: str  # "zSession", "application", "dual"
)

# Get active user
user: Optional[Dict] = zos.auth.get_active_user()
```

### RBAC (4 methods)

```python
# Check role
has_role: bool = zos.auth.has_role(
    required_role: Union[str, List[str]]
)

# Check permission
has_perm: bool = zos.auth.has_permission(
    required_permission: str
)

# Grant permission
success: bool = zos.auth.grant_permission(
    user_id: str,
    permission: str,
    granted_by: str
)

# Revoke permission
success: bool = zos.auth.revoke_permission(
    user_id: str,
    permission: str
)
```

---

## Module Guides

Deep dive into specific modules:

- **[security_GUIDE.md](zAuth_Guides/security_GUIDE.md)** - bcrypt password hashing, timing-safe verification, 72-byte limit handling
- **[persistence_GUIDE.md](zAuth_Guides/persistence_GUIDE.md)** - machine identity at rest (`zConfig.identity.zolo`); sealed `identity_store` seam (replaces retired SQLite sessions)
- **[authentication_GUIDE.md](zAuth_Guides/authentication_GUIDE.md)** - Three-tier model, multi-app support, local vs. sealed-remote auth, context switching
- **[rbac_GUIDE.md](zAuth_Guides/rbac_GUIDE.md)** - Context-aware roles, permissions, dual-mode OR logic, database management
- **[actions_GUIDE.md](zAuth_Guides/actions_GUIDE.md)** - Declarative zLogin/zLogout handlers for zDispatch integration
- **[delegates_GUIDE.md](zAuth_Guides/delegates_GUIDE.md)** - Public API composition, delegation pattern, facade architecture

---

## Best Practices

### Security

1. **Always use bcrypt for passwords**:
   ```python
   # Good
   hashed = zos.auth.hash_password(user_input)
   
   # Bad - never store plaintext
   # password = user_input  # DON'T DO THIS
   ```

2. **Never log sensitive data**:
   ```python
   # Good
   logger.info(f"Login attempt for user: {username}")
   
   # Bad
   # logger.info(f"Login: {username} / {password}")  # DON'T
   ```

3. **Use persistent sessions for better UX**:
   ```python
   # Recommended
   zos.auth.login(username, password, persist=True)
   ```

### Multi-Tier Authentication

1. **Use appropriate context for checks**:
   ```python
   # Check zOS user role
   zos.auth.set_active_context("zSession")
   if zos.auth.has_role("admin"):
       # zOS admin actions
   
   # Check app user role
   zos.auth.set_active_context("application")
   if zos.auth.has_role("moderator"):
       # App-specific actions
   ```

2. **Use dual mode when both contexts matter**:
   ```python
   # Store owner analyzing their store
   zos.auth.set_active_context("dual")
   # Either zOS admin OR store owner can access
   ```

3. **Clean up on logout**:
   ```python
   # Full cleanup
   zos.auth.logout(context="all", delete_persistent=True)
   ```

### RBAC

1. **Use permissions for granular control**:
   ```python
   # Better than role checks for specific actions
   if zos.auth.has_permission("data.delete"):
       delete_data()
   ```

2. **Use consistent permission naming**:
   ```python
   # Convention: resource.action
   permissions = [
       "data.read",
       "data.write",
       "content.publish",
       "admin.users"
   ]
   ```

3. **Grant permissions explicitly**:
   ```python
   # Track who granted permissions
   zos.auth.grant_permission(
       user_id="zU_123",
       permission="content.publish",
       granted_by=admin_username
   )
   ```

---

## Thread Safety

**f_zAuth is NOT thread-safe by design**.

Each thread should use its own zOS instance:

```python
import threading
from zOS import zOS

def thread_task():
    # Create zOS instance per thread
    zos = zOS()
    zos.auth.login("user", "pass")
    # Thread-safe within this instance

threads = [
    threading.Thread(target=thread_task)
    for _ in range(5)
]

for t in threads:
    t.start()
```

**Why?** f_zAuth operates on `zos.session` dictionary, which is not thread-safe. Multi-app authentication within a SINGLE session is fully supported.

---

## Advanced Topics

### Persistent Identity File

Tier-1 identity is a single declarative file (no SQLite session DB, no expiry
sweep). Management is via the normal login/logout API:

```python
# Record the current identity (also done by login(persist=True))
zos.auth.login(username, password, persist=True)

# Sign out this machine (deletes zConfig.identity.zolo)
zos.auth.logout(delete_persistent=True)   # delete_persistent defaults to True

# Path (for inspection/debugging)
# <user_config>/zConfigs/zConfig.identity.zolo  →  zIdentity: { username, user_id, role, api_key, issued_at }
```

The read/write/clear of this file is the **sealed** `identity_store` seam; the OS
keychain sealing in production is a zGuard mechanism. See
[persistence_GUIDE.md](zAuth_Guides/persistence_GUIDE.md).

### Personal Access Tokens (sealed)

Non-interactive auth (CI, `zolo --push`, hosted instances) uses PATs:

```python
# Sealed in zGuard (Type A2) — raise "z patch" without it
token = zos.auth.issue_api_key("user@zolo.com")  # plaintext shown once
user  = zos.auth.verify_api_key(token)            # ledger row or None
role  = zos.auth.authenticate_api_key(token)      # headless Tier-1 login
zos.auth.revoke_api_key("user@zolo.com")
```

> Mechanism: private zGuard auth docs (`api_key_auth`).

### Permissions Database Access

```python
# RBAC permissions DO use SQLite (via zData)
zos.auth.rbac.ensure_permissions_db()
results = zos.data.select("user_permissions", where={"user_id": "zU_123"})
```

---

## Troubleshooting

### Common Issues

**1. Login fails with "Invalid credentials"**
```python
# Check username/password
# Check server_url if using remote auth
# Check network connectivity (zComm)
result = zos.auth.login(username, password)
print(result)  # Contains error details
```

**2. Identity not persisting across restarts**
```python
# Ensure persist=True (records zConfig.identity.zolo)
zos.auth.login(username, password, persist=True)

# Inspect the identity file:
#   <user_config>/zConfigs/zConfig.identity.zolo
# If absent after a successful login, check user_config dir write perms.
# (Restore-at-boot via identity_store is a sealed seam — no-op without zGuard.)
```

**3. RBAC checks failing in dual mode**
```python
# Verify active_context
status = zos.auth.status()
print(f"Context: {status['active_context']}")

# Ensure both contexts authenticated
print(f"zSession: {status['zsession']}")
print(f"Apps: {status['applications']}")
```

**4. Permissions not working**
```python
# Ensure permissions database initialized
zos.auth.rbac.ensure_permissions_db()

# Check permission grants
# (Query directly via zData)
```

---

## Performance Considerations

### bcrypt Hash Time

- **Hash/verify**: ~0.3s per operation (12 rounds)
- **By design**: Protects against brute-force attacks
- **Recommendation**: Cache authentication results, don't hash repeatedly

### Identity Persistence

- **Identity file write**: <5ms (single small `.zolo` file)
- **Boot restore**: one file read + parse at startup (no DB)
- **Sign-out**: single file unlink

### RBAC Checks

- **In-memory**: <1ms for role checks
- **Database**: <10ms for permission checks
- **Recommendation**: Cache permission checks if checking frequently

---

**[← Back to e_zDisplay Guide](zDisplay_GUIDE.md) | [Home](../../README.md) | [Next: g_zDispatch Guide →](zDispatch_GUIDE.md)**
