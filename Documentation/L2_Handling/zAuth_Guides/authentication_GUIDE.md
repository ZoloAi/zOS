**[← Back to zAuth Guide](../zAuth_GUIDE.md)**

---

# Authentication Module Guide

**Module**: `zAuth_modules/logic/authentication/`  
**Class**: `Authentication`  
**Purpose**: CORE three-tier authentication implementation (zSession, Application, Dual)

---

## Overview

The **Authentication** module is the **CORE** of zAuth's three-tier authentication system. It orchestrates authentication across three distinct contexts: zSession (internal zOS users), Application (external app users), and Dual-mode (both simultaneously).

### Key Features

- **Three-Tier Model**: zSession, Application, and Dual-mode authentication
- **Multi-App Support**: Multiple simultaneous app authentications
- **Context Switching**: Dynamic context management with active user tracking
- **Remote Authentication**: zCloud handshake (sealed in zGuard; selected by `ZOLO_USE_REMOTE_API`)
- **zDisplay Integration**: All UI feedback through generic display events
- **Identity Persistence**: git-like `zConfig.identity.zolo` via the sealed `identity_store` seam

---

## Architecture

### Facade Pattern with Manager Delegation

```
Authentication (Facade)
├── RemoteAuthenticationManager   # Remote API authentication
├── LoginManager                  # zSession login operations
├── LogoutManager                 # Logout across contexts
├── ContextManager                # Context switching and state
├── CredentialManager             # Credential queries
└── AppAuthenticationManager      # Application user authentication
```

### Module Responsibilities

| Manager | Purpose | Methods |
|---------|---------|---------|
| **RemoteAuthenticationManager** | HTTPS auth via zComm | `authenticate_remote()` |
| **LoginManager** | zSession login logic | `login()` |
| **LogoutManager** | Context-aware logout | `logout()` |
| **ContextManager** | Context switching | `set_active_context()`, `switch_app()`, `get_active_user()` |
| **CredentialManager** | Auth status queries | `status()`, `is_authenticated()`, `get_credentials()`, `get_app_user()` |
| **AppAuthenticationManager** | App user auth | `authenticate_app_user()` |

---

## Three-Tier Authentication Model

### Tier 1: zSession Authentication (Internal Users)

**Purpose**: Authenticate zOS/Zolo platform users.

**Use Cases**:
- Platform developers accessing premium features
- Plugin authentication and licensing
- Cloud service integration
- Cross-application identity

**Session Structure**:
```python
session["zAuth"]["zSession"] = {
    "username": "user@zolo.com",
    "user_id": "zU_12345",
    "role": "admin",
    "api_key": "token_xyz...",
    "authenticated": True
}
```

**API Methods**:
- `login(username, password, server_url, persist)` - Login to zSession
- `logout(context="zSession", delete_persistent)` - Logout from zSession
- `is_authenticated()` - Check if any context authenticated
- `get_credentials()` - Get zSession credentials
- `status()` - Get comprehensive auth status

---

### Tier 2: Application Authentication (External Users)

**Purpose**: Authenticate end-users of applications BUILT with zOS.

**Use Cases**:
- E-commerce store customers
- Blog/forum users
- SaaS application users
- Multi-tenant applications

**Session Structure**:
```python
session["zAuth"]["applications"] = {
    "my_store": {
        "username": "customer@email.com",
        "user_id": "store_user_123",
        "role": "customer",
        "token": "app_token_abc...",
        "authenticated": True
    },
    "my_blog": {
        "username": "blogger@email.com",
        "user_id": "blog_user_456",
        "role": "author",
        "token": "blog_token_xyz...",
        "authenticated": True
    }
}
```

**API Methods**:
- `authenticate_app_user(app_name, token, config)` - Authenticate app user
- `switch_app(app_name)` - Switch active app
- `get_app_user(app_name)` - Get app user data

**Multi-App Support**: Can authenticate multiple apps simultaneously, each with independent credentials.

---

### Tier 3: Dual-Mode Authentication (Both Contexts)

**Purpose**: Both zSession AND application authenticated simultaneously.

**Use Case Example**: Store owner analyzing their store
- Authenticated as zOS user (platform access, analytics, admin tools)
- Authenticated as store user (customer perspective, testing UX)

**Session Structure**:
```python
session["zAuth"]["dual_mode"] = True
session["zAuth"]["active_context"] = "dual"

# Both contexts active:
session["zAuth"]["zSession"] = { ... }
session["zAuth"]["applications"]["my_store"] = { ... }
```

**RBAC Behavior**: Uses **OR logic** - either context can grant access:
```python
zos.auth.set_active_context("dual")

# Checks BOTH zSession role AND active app role
if zos.auth.has_role("admin"):
    # True if admin in zSession OR admin in active app
    pass
```

---

## Login Flow (zSession)

### Process Overview

```
1. User calls login()
   │
2. Validate inputs (username, password — prompted if omitted)
   │
3. ZOLO_USE_REMOTE_API=true ?
   │   yes → remote zCloud handshake (sealed in zGuard)
   │   no  → local-ledger verify (authenticate_zolo_credentials — open-core SSOT)
   │
4. Verify password against the ledger row (bcrypt verify_password)
   │
5. Persist identity (if persist=True)
   │   - _persist_zsession_identity() → save_identity(...)
   │   - writes zConfig.identity.zolo (NO SQLite session DB)
   │
6. Update in-memory session
   │   - session["zAuth"]["zSession"] = user_data
   │   - session["zAuth"]["active_context"] = "zSession"
   │
7. Display success (via zDisplay)
   │
8. Return {"status": "success"|"fail", "user": {...}}
```

### Code Example

```python
from zOS import zOS

zos = zOS()

# Local-ledger login by default; set ZOLO_USE_REMOTE_API=true for zCloud (sealed)
result = zos.auth.login(
    username="user@zolo.com",
    password="secure_password",
    server_url="https://auth.zolo.com/api/login",  # Optional (remote path only)
    persist=True  # Record identity to zConfig.identity.zolo
)

if result["status"] == "success":
    user = result["user"]
    print(f"Logged in: {user['username']} ({user['role']}, id={user['user_id']})")
else:
    print("Login failed: invalid credentials")
```

---

## Logout Flow

### Context-Aware Logout

```python
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
# - zSession and other apps remain active

# Logout all contexts
result = zos.auth.logout(context="all")
# - Clears zSession
# - Clears all application contexts
# - Resets to clean state

# Delete persistent identity (default: delete_persistent=True)
result = zos.auth.logout(delete_persistent=True)
# - Clears in-memory session
# - Deletes the zConfig.identity.zolo file (git-like sign-out)
```

---

## Application Authentication

### Multi-App Authentication

```python
from zOS import zOS

zos = zOS()

# Authenticate multiple apps
apps = [
    ("store_app", "store_token_xyz", {"auth_endpoint": "https://store.com/auth"}),
    ("blog_app", "blog_token_abc", {"auth_endpoint": "https://blog.com/auth"}),
    ("forum_app", "forum_token_123", {"auth_endpoint": "https://forum.com/auth"})
]

for app_name, token, config in apps:
    result = zos.auth.authenticate_app_user(
        app_name=app_name,
        token=token,
        config=config
    )
    
    if result["status"] == "success":
        print(f"{app_name}: Authenticated as {result['user']['username']}")

# Check status
status = zos.auth.status()
print(f"Active apps: {list(status['applications'].keys())}")
```

---

### Switch Active Application

```python
# Switch context to specific app
success = zos.auth.switch_app("blog_app")

if success:
    active_user = zos.auth.get_active_user()
    print(f"Active: {active_user['username']} in {active_user['app_name']}")
    
    # RBAC checks now use blog_app role
    if zos.auth.has_role("author"):
        print("User is blog author")
```

---

## Context Management

### Context Switching

```python
from zOS import zOS

zos = zOS()

# Login to zSession
zos.auth.login("dev@zolo.com", "password")

# Authenticate to app
zos.auth.authenticate_app_user("my_app", "token")

# ═══════════════════════════════════════════════════════════
# Context: zSession
# ═══════════════════════════════════════════════════════════

zos.auth.set_active_context("zSession")
user = zos.auth.get_active_user()
print(f"Active: {user['username']} (zSession)")

# RBAC checks use zSession role
if zos.auth.has_role("admin"):
    print("zOS admin")

# ═══════════════════════════════════════════════════════════
# Context: Application
# ═══════════════════════════════════════════════════════════

zos.auth.set_active_context("application")
user = zos.auth.get_active_user()
print(f"Active: {user['username']} (my_app)")

# RBAC checks use app role
if zos.auth.has_role("moderator"):
    print("App moderator")

# ═══════════════════════════════════════════════════════════
# Context: Dual (Both)
# ═══════════════════════════════════════════════════════════

zos.auth.set_active_context("dual")

# RBAC checks use OR logic
if zos.auth.has_role("admin"):
    # True if admin in zSession OR app
    print("Admin in either context")
```

---

## Remote Authentication (zCloud) — sealed

Selected when `ZOLO_USE_REMOTE_API=true`; otherwise login uses the local ledger.

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

**The instance → zCloud handshake is sealed in zGuard (Type A2).** Open-core
selects the remote path; the wire handshake mechanism (and the PAT zCloud returns)
is the `remote_authentication` seam. Without zGuard the remote path is unavailable
and local-ledger login still works.

> Mechanism: private zGuard docs `zGuard/Documentation/auth/remote_authentication_GUIDE.md`.
> Requires zGuard — contact admin / `z patch`.

---

## API Reference

### login()

```python
def login(
    username: Optional[str] = None,
    password: Optional[str] = None,
    server_url: Optional[str] = None,
    persist: bool = True
) -> Dict[str, Any]
```

Authenticate zOS/Zolo user to zSession context.

**Args**:
- `username`: Username/email (prompted if None)
- `password`: Password (prompted if None)
- `server_url`: Optional remote authority URL (remote path only)
- `persist`: Record identity to `zConfig.identity.zolo` (default: True)

**Returns**: `Dict`:
- `status` (str): `"success"` or `"fail"`
- `user` (Dict): `{username, user_id, role}` on success

**Example**:
```python
result = zos.auth.login("user@zolo.com", "password", persist=True)
if result["status"] == "success":
    print(f"Logged in as: {result['user']['username']}")
```

---

### logout()

```python
def logout(
    context: str = "zSession",
    app_name: Optional[str] = None,
    delete_persistent: bool = False
) -> Dict[str, Any]
```

Clear session authentication (context-aware).

**Args**:
- `context`: Context to logout from ("zSession", "application", "all")
- `app_name`: Required if context="application"
- `delete_persistent`: Delete session from disk (default: False)

**Returns**: `Dict` with keys:
- `success` (bool): True if logged out
- `message` (str): Confirmation message

**Example**:
```python
# Logout zSession
zos.auth.logout()

# Logout specific app
zos.auth.logout(context="application", app_name="my_store")

# Logout all with cleanup
zos.auth.logout(context="all", delete_persistent=True)
```

---

### status()

```python
def status() -> Dict[str, Any]
```

Show current authentication status (all contexts).

**Returns**: `Dict` with keys:
- `is_authenticated` (bool): True if any context authenticated
- `active_context` (str): Current active context
- `zsession` (Dict|None): zSession user data if authenticated
- `applications` (Dict): Dict of app_name → user_data
- `dual_mode` (bool): True if dual mode active

**Example**:
```python
status = zos.auth.status()
print(f"Authenticated: {status['is_authenticated']}")
print(f"Active Context: {status['active_context']}")

if status['zsession']:
    print(f"zSession: {status['zsession']['username']}")

for app_name, user in status['applications'].items():
    print(f"App {app_name}: {user['username']}")
```

---

### is_authenticated()

```python
def is_authenticated() -> bool
```

Check if user is currently authenticated in ANY context.

**Returns**: `bool` - True if authenticated in zSession OR any application

**Example**:
```python
if zos.auth.is_authenticated():
    print("User is authenticated")
else:
    print("User is not authenticated")
```

---

### get_credentials()

```python
def get_credentials() -> Optional[Dict[str, Any]]
```

Get current zSession authentication data.

**Returns**: `Dict|None` with keys:
- `username` (str): Username
- `user_id` (str): User ID
- `role` (str): User role
- `api_key` (str): API key
- `authenticated` (bool): True if authenticated

Returns `None` if not authenticated.

**Example**:
```python
creds = zos.auth.get_credentials()
if creds:
    print(f"Username: {creds['username']}")
    print(f"API Key: {creds['api_key']}")
```

---

### authenticate_app_user()

```python
def authenticate_app_user(
    app_name: str,
    token: str,
    config: Optional[Dict[str, str]] = None
) -> Dict[str, Any]
```

Authenticate user to a specific application (Tier 2).

**Args**:
- `app_name`: Unique application identifier
- `token`: Authentication token from application
- `config`: Optional config dict with keys:
  - `auth_endpoint` (str): App authentication endpoint URL
  - `timeout` (int): Request timeout in seconds

**Returns**: `Dict` with keys:
- `success` (bool): True if authenticated
- `username` (str): App username
- `user_id` (str): App user ID
- `role` (str): App user role
- `app_name` (str): Application name

**Example**:
```python
result = zos.auth.authenticate_app_user(
    app_name="my_store",
    token="zk_…",            # a PAT (verified via the sealed seam)
    config={"user_model": "@.models.zSchema.users"}
)

if result["status"] == "success":
    print(f"Authenticated: {result['user']['username']}")
```

---

### switch_app()

```python
def switch_app(app_name: str) -> bool
```

Switch focus to a different authenticated application.

**Args**:
- `app_name`: Application name to switch to

**Returns**: `bool` - True if switched successfully

**Example**:
```python
# Switch to blog app
if zos.auth.switch_app("blog_app"):
    print("Switched to blog_app")
    user = zos.auth.get_active_user()
    print(f"Active: {user['username']}")
```

---

### get_app_user()

```python
def get_app_user(app_name: str) -> Optional[Dict[str, Any]]
```

Get authentication info for a specific application.

**Args**:
- `app_name`: Application name

**Returns**: `Dict|None` with user data if authenticated to that app

**Example**:
```python
store_user = zos.auth.get_app_user("my_store")
if store_user:
    print(f"Store user: {store_user['username']}")
    print(f"Role: {store_user['role']}")
```

---

### set_active_context()

```python
def set_active_context(context: str) -> bool
```

Set the active authentication context.

**Args**:
- `context`: Context to activate ("zSession", "application", "dual")

**Returns**: `bool` - True if context set successfully

**Example**:
```python
# Set to zSession
zos.auth.set_active_context("zSession")

# Set to application
zos.auth.set_active_context("application")

# Set to dual (both)
zos.auth.set_active_context("dual")
```

---

### get_active_user()

```python
def get_active_user() -> Optional[Dict[str, Any]]
```

Get user data for the current active authentication context.

**Returns**: `Dict|None` with user data for active context

**Example**:
```python
user = zos.auth.get_active_user()
if user:
    print(f"Active user: {user['username']}")
    print(f"Context: {user.get('context', 'unknown')}")
```

---

### authenticate_remote()

```python
def authenticate_remote(
    username: str,
    password: str,
    server_url: Optional[str] = None
) -> Dict[str, Any]
```

Authenticate via remote Flask API (called internally by login()).

**Args**:
- `username`: Username for authentication
- `password`: Password for authentication
- `server_url`: Optional remote server URL

**Returns**: `Dict` with authentication result

**Note**: Typically called internally by `login()`. Direct use is for advanced scenarios.

---

## Integration with zOS Subsystems

### zConfig Integration

```python
# All session/auth constants from zConfig
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
    SESSION_KEY_ZAUTH,           # "zAuth"
    ZAUTH_KEY_ZSESSION,          # "zSession"
    ZAUTH_KEY_APPLICATIONS,      # "applications"
    ZAUTH_KEY_ACTIVE_CONTEXT,    # "active_context"
    ZAUTH_KEY_ACTIVE_APP,        # "active_app"
    CONTEXT_ZSESSION,            # "zSession"
    CONTEXT_APPLICATION,         # "application"
    CONTEXT_DUAL,                # "dual"
)

# Consistent session structure across subsystems
session["zAuth"]["zSession"] = { ... }
```

---

### zDisplay Integration

```python
# All authentication feedback uses zDisplay
self.zos.display.success("Logged in successfully")
self.zos.display.error("Invalid credentials")
self.zos.display.warning("Session expired")
self.zos.display.text(f"Welcome back, {username}!")
```

---

### zComm Integration

zComm is only the HTTP transport for the **sealed** remote handshake — the zCloud
handshake semantics live in `zguard.auth.remote_authentication`, not here.

---

### Identity Persistence Integration

```python
# Recording identity is internal to login(persist=True):
#   _persist_zsession_identity() -> save_identity({username, user_id, role, api_key})
# Restore at boot is the sealed boot_identity cascade -> identity_store.load_identity()
# There is no session_persistence / SQLite session API.
```

See [persistence_GUIDE.md](persistence_GUIDE.md).

---

## Best Practices

### Authentication Flow

1. **Always use persist=True for better UX**:
   ```python
   zos.auth.login(username, password, persist=True)
   ```

2. **Check authentication before protected operations**:
   ```python
   if not zos.auth.is_authenticated():
       raise PermissionError("Authentication required")
   
   # Perform protected operation
   ```

3. **Handle login failures gracefully**:
   ```python
   result = zos.auth.login(username, password)
   if result["status"] != "success":
       logger.error("Login failed: invalid credentials")
       # Show user-friendly error
   ```

### Multi-App Management

1. **Use meaningful app names**:
   ```python
   # Good
   zos.auth.authenticate_app_user("ecommerce_store", token)
   
   # Bad
   # zos.auth.authenticate_app_user("app1", token)
   ```

2. **Switch context explicitly**:
   ```python
   # Good: Explicit context switch
   zos.auth.set_active_context("application")
   zos.auth.switch_app("store_app")
   
   # Bad: Implicit context
   # Assuming context without setting it
   ```

3. **Track active applications**:
   ```python
   status = zos.auth.status()
   active_apps = list(status['applications'].keys())
   print(f"Active apps: {', '.join(active_apps)}")
   ```

### Security

1. **Never log passwords**:
   ```python
   # Good
   logger.info(f"Login attempt for: {username}")
   
   # Bad
   # logger.info(f"Login: {username} / {password}")  # DON'T
   ```

2. **Use HTTPS for remote auth**:
   ```python
   # Good
   server_url = "https://auth.zolo.com/api/login"
   
   # Bad
   # server_url = "http://auth.zolo.com/api/login"  # Insecure
   ```

3. **Cleanup on logout**:
   ```python
   # Full cleanup
   zos.auth.logout(context="all", delete_persistent=True)
   ```

---

## Troubleshooting

### Common Issues

**1. Login fails with "Invalid credentials"**

```python
# Check username/password
result = zos.auth.login(username, password)
print(result)  # Contains error details

# Check network connectivity (remote auth)
# Check server_url if using remote auth
```

**2. Identity not restored on restart**

```python
# Ensure persist=True (writes zConfig.identity.zolo)
zos.auth.login(username, password, persist=True)

# Boot restore is the sealed identity_store seam — a no-op without zGuard,
# so an open-core build always boots anonymous. Verify the file exists at:
#   <user_config>/zConfigs/zConfig.identity.zolo
```

**3. Multi-app context confusion**

```python
# Check active context
status = zos.auth.status()
print(f"Context: {status['active_context']}")
print(f"Active app: {status.get('active_app')}")

# Set context explicitly
zos.auth.set_active_context("application")
zos.auth.switch_app("my_app")
```

**4. RBAC checks failing**

```python
# Check which context is active
status = zos.auth.status()
print(f"Context: {status['active_context']}")

# Verify user role in active context
user = zos.auth.get_active_user()
print(f"Role: {user.get('role')}")
```

---

**[← Back to zAuth Guide](../zAuth_GUIDE.md)**
