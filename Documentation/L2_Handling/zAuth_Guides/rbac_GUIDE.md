**[← Back to zAuth Guide](../zAuth_GUIDE.md)**

---

# RBAC Module Guide

**Module**: `zAuth_modules/logic/rbac/`  
**Class**: `RBAC`  
**Purpose**: Context-aware Role-Based Access Control with three-tier authentication support

---

## Overview

The **RBAC** (Role-Based Access Control) module provides context-aware access control across zAuth's three-tier authentication system. It supports role hierarchy, dynamic permissions, and intelligent OR logic in dual-mode.

### Key Features

- **Context-Aware**: Adapts to zSession, Application, or Dual-mode contexts
- **Role Hierarchy**: Admin > Moderator > User with inheritance
- **Dynamic Permissions**: Granular permission checks stored in SQLite
- **Dual-Mode OR Logic**: Either context can grant access
- **Persistent Storage**: Permissions stored in unified auth database
- **zData Integration**: Declarative database operations

---

## Architecture

### Facade Pattern with Manager Delegation

```
RBAC (Facade)
├── ContextHelpers          # Resolves authentication context
├── DatabaseManager         # Database initialization
├── RoleChecker            # Role checks with hierarchy
├── PermissionChecker      # Permission checks
└── PermissionManager      # Grant/revoke operations
```

### Module Responsibilities

| Manager | Purpose | Key Methods |
|---------|---------|-------------|
| **ContextHelpers** | Resolve current user/role/context | `_get_current_role()`, `_get_current_user_id()` |
| **DatabaseManager** | Initialize permissions database | `ensure_permissions_db()` |
| **RoleChecker** | Perform role checks | `has_role()`, `_check_role_match()` |
| **PermissionChecker** | Perform permission checks | `has_permission()` |
| **PermissionManager** | Manage permissions | `grant_permission()`, `revoke_permission()` |

---

## Role System

### Role Hierarchy

```
admin           # Highest - all permissions
  │
  ├── developer      # Technical access
  ├── moderator      # Content management
  └── premium        # Enhanced features
        │
        └── user     # Basic access (default)
```

**Inheritance**: Higher roles inherit permissions from lower roles.

### Built-in Roles

| Role | Description | Typical Permissions |
|------|-------------|---------------------|
| **admin** | Full system access | All operations |
| **developer** | Technical features | Code, debug, API access |
| **moderator** | Content management | Edit, delete, moderate content |
| **premium** | Enhanced features | Premium content, advanced tools |
| **user** | Basic access (default) | Read, create own content |

---

### Role Checking

```python
from zOS import zOS

zos = zOS()
zos.auth.login("user@zolo.com", "password")  # Role: admin

# Check single role
if zos.auth.has_role("admin"):
    print("User is admin")

# Check multiple roles (OR logic)
if zos.auth.has_role(["admin", "moderator"]):
    print("User is admin OR moderator")

# Role hierarchy (admin includes all lower roles)
if zos.auth.has_role("user"):
    print("Admin inherits user role")  # True
```

---

## Permission System

### Permission Structure

Permissions follow a **resource.action** naming convention:

```
resource.action
  │       │
  │       └─ Action: read, write, delete, publish, etc.
  └───────── Resource: data, content, users, settings, etc.
```

### Common Permissions

| Permission | Description |
|------------|-------------|
| `data.read` | Read data from system |
| `data.write` | Write/modify data |
| `data.delete` | Delete data |
| `content.create` | Create content |
| `content.publish` | Publish content |
| `users.manage` | Manage user accounts |
| `settings.modify` | Modify system settings |
| `admin.all` | Full administrative access |

---

### Permission Checking

```python
from zOS import zOS

zos = zOS()
zos.auth.login("user@zolo.com", "password")

# Check single permission
if zos.auth.has_permission("data.delete"):
    print("User can delete data")
    delete_data()

# Check multiple permissions (OR logic)
if zos.auth.has_permission(["content.publish", "admin.all"]):
    print("User can publish OR is admin")
```

---

### Granting Permissions

```python
from zOS import zOS

zos = zOS()
zos.auth.login("admin@zolo.com", "password")  # Must be admin

# Grant permission to user
success = zos.auth.grant_permission(
    user_id="zU_12345",
    permission="content.publish",
    granted_by="admin@zolo.com"
)

if success:
    print("Permission granted")
```

**Storage**:
```sql
-- Stored in SQLite database
INSERT INTO user_permissions (user_id, permission, granted_by, granted_at)
VALUES ('zU_12345', 'content.publish', 'admin@zolo.com', '2024-01-15T10:30:00');
```

---

### Revoking Permissions

```python
from zOS import zOS

zos = zOS()
zos.auth.login("admin@zolo.com", "password")  # Must be admin

# Revoke permission from user
success = zos.auth.revoke_permission(
    user_id="zU_12345",
    permission="content.publish"
)

if success:
    print("Permission revoked")
```

---

## Context-Aware Behavior

### zSession Context (Tier 1)

```python
zos.auth.login("admin@zolo.com", "password")  # Role: admin
zos.auth.set_active_context("zSession")

# Checks zSession role
if zos.auth.has_role("admin"):
    print("zOS admin")  # True

# Checks zSession user permissions
if zos.auth.has_permission("data.delete"):
    print("zOS user has data.delete permission")
```

**Resolution**:
- Role: `session["zAuth"]["zSession"]["role"]`
- User ID: `session["zAuth"]["zSession"]["user_id"]`
- Permissions: Query database with zSession user_id

---

### Application Context (Tier 2)

```python
zos.auth.authenticate_app_user("my_store", "token")  # Role: moderator
zos.auth.set_active_context("application")

# Checks active app role
if zos.auth.has_role("moderator"):
    print("Store moderator")  # True

# Checks active app user permissions
if zos.auth.has_permission("content.publish"):
    print("Store user can publish")
```

**Resolution**:
- Active app: `session["zAuth"]["active_app"]` (e.g., "my_store")
- Role: `session["zAuth"]["applications"]["my_store"]["role"]`
- User ID: `session["zAuth"]["applications"]["my_store"]["user_id"]`
- Permissions: Query database with app user_id

---

### Dual-Mode Context (Tier 3)

**The Power of OR Logic**:

```python
# Setup: Login to both contexts
zos.auth.login("dev@zolo.com", "password")           # zSession role: developer
zos.auth.authenticate_app_user("store", "token")     # App role: moderator
zos.auth.set_active_context("dual")

# ═══════════════════════════════════════════════════════════
# Role Checks: OR Logic (either context grants access)
# ═══════════════════════════════════════════════════════════

# Check developer role
if zos.auth.has_role("developer"):
    # True: developer in zSession
    # (even though app role is moderator)
    print("Developer access granted via zSession")

# Check moderator role
if zos.auth.has_role("moderator"):
    # True: moderator in app
    # (even though zSession role is developer)
    print("Moderator access granted via app")

# Check admin role
if zos.auth.has_role("admin"):
    # True if EITHER context has admin
    # False if neither has admin
    print("Admin in at least one context")

# ═══════════════════════════════════════════════════════════
# Permission Checks: OR Logic
# ═══════════════════════════════════════════════════════════

# Check if EITHER user has permission
if zos.auth.has_permission("data.delete"):
    # True if zSession user has data.delete
    # OR app user has data.delete
    print("Permission granted by either context")
```

**Use Case**: Store owner analyzing their store
- zOS user (admin): Full platform access, analytics
- Store user (customer): Customer perspective, testing UX
- Dual mode: Can perform admin operations while seeing customer view

---

## Database Structure

### Auth Permissions Database

**Database Label**: `"auth"`  
**Used By**: RBAC (the `user_permissions` table). Tier-1 sessions are **not** in
SQLite — they persist as the `zConfig.identity.zolo` file (see
[persistence_GUIDE.md](persistence_GUIDE.md)).

### Table: user_permissions

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Auto-increment ID |
| `user_id` | TEXT | User ID (zSession or app user) |
| `permission` | TEXT | Permission string (resource.action) |
| `granted_by` | TEXT | Who granted the permission |
| `granted_at` | TEXT | ISO timestamp when granted |

**Indexes**:
- `idx_user_permission`: (user_id, permission) for fast lookups

---

## API Reference

### has_role()

```python
def has_role(required_role: Optional[Union[str, List[str]]]) -> bool
```

Check if the current user has the required role (context-aware).

**Args**:
- `required_role`: Role(s) to check. Can be:
  - `str`: Single role (e.g., "admin")
  - `List[str]`: Multiple roles (OR logic, e.g., ["admin", "moderator"])
  - `None`: Always returns True (no requirement)

**Returns**: `bool` - True if user has required role

**Context Behavior**:
- **zSession**: Checks `session["zAuth"]["zSession"]["role"]`
- **Application**: Checks active app role
- **Dual**: Checks BOTH (OR logic - either can grant)

**Example**:

```python
# Single role
if zos.auth.has_role("admin"):
    print("User is admin")

# Multiple roles (OR logic)
if zos.auth.has_role(["admin", "moderator"]):
    print("User is admin OR moderator")

# No requirement (always True)
if zos.auth.has_role(None):
    print("No role required")

# Check specific context
zos.auth.set_active_context("zSession")
if zos.auth.has_role("developer"):
    print("zOS developer")
```

**Role Hierarchy**: Higher roles inherit lower roles
```python
# Admin inherits all roles
zos.auth.login("admin@zolo.com", "password")  # Role: admin
zos.auth.has_role("user")      # True (admin includes user)
zos.auth.has_role("moderator") # True (admin includes moderator)
```

---

### has_permission()

```python
def has_permission(required_permission: Union[str, List[str]]) -> bool
```

Check if the current user has the required permission (context-aware).

**Args**:
- `required_permission`: Permission(s) to check. Can be:
  - `str`: Single permission (e.g., "data.delete")
  - `List[str]`: Multiple permissions (OR logic)

**Returns**: `bool` - True if user has required permission

**Context Behavior**:
- **zSession**: Queries database with zSession user_id
- **Application**: Queries database with active app user_id
- **Dual**: Queries BOTH user_ids (OR logic - either can grant)

**Example**:

```python
# Single permission
if zos.auth.has_permission("data.delete"):
    print("User can delete data")
    delete_data()

# Multiple permissions (OR logic)
if zos.auth.has_permission(["content.publish", "admin.all"]):
    print("User can publish OR is admin")

# Check before operation
if not zos.auth.has_permission("settings.modify"):
    raise PermissionError("Cannot modify settings")

modify_settings()
```

**Database Query**:
```sql
-- Single context
SELECT permission FROM user_permissions
WHERE user_id = 'zU_12345'
AND permission = 'data.delete';

-- Dual context (OR logic)
SELECT permission FROM user_permissions
WHERE user_id IN ('zU_12345', 'app_user_456')
AND permission = 'data.delete';
```

---

### grant_permission()

```python
def grant_permission(
    user_id: str,
    permission: str,
    granted_by: Optional[str] = None
) -> bool
```

Grant a permission to a user (admin-only operation).

**Args**:
- `user_id`: User ID to grant permission to
- `permission`: Permission string (resource.action)
- `granted_by`: Optional username who granted permission

**Returns**: `bool` - True if granted successfully

**Requirements**:
- Caller must be authenticated
- Caller must have admin role or admin.all permission

**Example**:

```python
# Must be admin
zos.auth.login("admin@zolo.com", "password")

# Grant permission
success = zos.auth.grant_permission(
    user_id="zU_12345",
    permission="content.publish",
    granted_by="admin@zolo.com"
)

if success:
    print("Permission granted")
else:
    print("Failed: Not authorized or database error")
```

**Storage**:
```sql
INSERT INTO user_permissions (user_id, permission, granted_by, granted_at)
VALUES ('zU_12345', 'content.publish', 'admin@zolo.com', '2024-01-15T10:30:00');
```

---

### revoke_permission()

```python
def revoke_permission(user_id: str, permission: str) -> bool
```

Revoke a permission from a user (admin-only operation).

**Args**:
- `user_id`: User ID to revoke permission from
- `permission`: Permission string to revoke

**Returns**: `bool` - True if revoked successfully

**Requirements**:
- Caller must be authenticated
- Caller must have admin role or admin.all permission

**Example**:

```python
# Must be admin
zos.auth.login("admin@zolo.com", "password")

# Revoke permission
success = zos.auth.revoke_permission(
    user_id="zU_12345",
    permission="content.publish"
)

if success:
    print("Permission revoked")
else:
    print("Failed: Not authorized or database error")
```

**Deletion**:
```sql
DELETE FROM user_permissions
WHERE user_id = 'zU_12345'
AND permission = 'content.publish';
```

---

### ensure_permissions_db()

```python
def ensure_permissions_db() -> None
```

Ensure the permissions database is initialized.

**Process**:
1. Load schema from `zSchema.auth.yaml` via zParser
2. Create `user_permissions` table if not exists
3. Create indexes for performance

**Example**:

```python
# Initialize database
zos.auth.rbac.ensure_permissions_db()

# Safe to call multiple times (idempotent)
zos.auth.rbac.ensure_permissions_db()
```

**Notes**:
- Called automatically by RBAC on first permission operation
- Uses the `"auth"` database label (permissions only; sessions are not in SQLite)
- Uses zData for declarative operations

---

## Usage Examples

### Basic Role Checking

```python
from zOS import zOS

zos = zOS()
zos.auth.login("user@zolo.com", "password")  # Role: admin

# Simple role check
if zos.auth.has_role("admin"):
    print("Admin access granted")
    perform_admin_operation()

# Multiple roles (OR logic)
if zos.auth.has_role(["admin", "moderator"]):
    print("Can moderate content")
    moderate_content()

# Role hierarchy
if zos.auth.has_role("user"):
    print("Basic user access")  # True for admin (includes user)
```

---

### Permission-Based Access Control

```python
from zOS import zOS

zos = zOS()
zos.auth.login("user@zolo.com", "password")

# Check permission before operation
if zos.auth.has_permission("data.delete"):
    delete_data()
else:
    print("Permission denied: data.delete required")

# Multiple permissions (OR logic)
if zos.auth.has_permission(["content.publish", "admin.all"]):
    publish_content()
```

---

### Granting and Revoking Permissions

```python
from zOS import zOS

zos = zOS()
zos.auth.login("admin@zolo.com", "password")

# Grant permission
zos.auth.rbac.ensure_permissions_db()

success = zos.auth.grant_permission(
    user_id="zU_12345",
    permission="content.publish",
    granted_by="admin@zolo.com"
)

if success:
    print("User can now publish content")

# Later: Revoke permission
success = zos.auth.revoke_permission(
    user_id="zU_12345",
    permission="content.publish"
)

if success:
    print("Permission revoked")
```

---

### Multi-Context RBAC

```python
from zOS import zOS

zos = zOS()

# Login to both contexts
zos.auth.login("dev@zolo.com", "password")           # Role: developer
zos.auth.authenticate_app_user("store", "token")     # Role: customer

# ═══════════════════════════════════════════════════════════
# Check zSession role
# ═══════════════════════════════════════════════════════════

zos.auth.set_active_context("zSession")
if zos.auth.has_role("developer"):
    print("zOS developer")  # True

# ═══════════════════════════════════════════════════════════
# Check application role
# ═══════════════════════════════════════════════════════════

zos.auth.set_active_context("application")
if zos.auth.has_role("customer"):
    print("Store customer")  # True

# ═══════════════════════════════════════════════════════════
# Check both (dual mode OR logic)
# ═══════════════════════════════════════════════════════════

zos.auth.set_active_context("dual")
if zos.auth.has_role(["developer", "customer"]):
    print("Developer OR customer")  # True (both match)
```

---

### Protecting Operations

```python
from zOS import zOS

def delete_user_data(user_id: str):
    """Delete user data (requires admin permission)."""
    
    # Check permission
    if not zos.auth.has_permission("data.delete"):
        raise PermissionError("data.delete permission required")
    
    # Check role
    if not zos.auth.has_role("admin"):
        raise PermissionError("admin role required")
    
    # Perform operation
    print(f"Deleting data for user: {user_id}")
    # ... actual deletion logic

# Usage
zos = zOS()
zos.auth.login("admin@zolo.com", "password")

try:
    delete_user_data("zU_12345")
except PermissionError as e:
    print(f"Access denied: {e}")
```

---

## Best Practices

### Role Design

1. **Use role hierarchy effectively**:
   ```python
   # Good: Admin inherits all lower permissions
   # Don't duplicate permissions across roles
   
   # Bad: Granting user permissions to admin
   # (admin already includes user via hierarchy)
   ```

2. **Choose appropriate default role**:
   ```python
   # Default role: "user" (basic access)
   # Elevate to "premium", "moderator", or "admin" as needed
   ```

3. **Use roles for broad access levels**:
   ```python
   # Roles: admin, moderator, user
   # Permissions: Granular resource.action controls
   ```

---

### Permission Design

1. **Follow resource.action convention**:
   ```python
   # Good
   permissions = [
       "data.read",
       "data.write",
       "content.publish",
       "users.manage"
   ]
   
   # Bad
   # permissions = ["read_data", "writeData"]  # Inconsistent
   ```

2. **Grant minimal permissions**:
   ```python
   # Good: Grant only what's needed
   zos.auth.grant_permission(user_id, "content.create")
   
   # Bad: Grant excessive permissions
   # zos.auth.grant_permission(user_id, "admin.all")
   ```

3. **Document permission requirements**:
   ```python
   def publish_content(content_id: str):
       """
       Publish content to site.
       
       Requires: content.publish permission OR admin role
       """
       if not zos.auth.has_permission("content.publish"):
           raise PermissionError("content.publish required")
   ```

---

### Context Management

1. **Set context explicitly**:
   ```python
   # Good: Explicit context
   zos.auth.set_active_context("zSession")
   if zos.auth.has_role("admin"):
       # Check zSession admin
   
   # Bad: Implicit context
   # if zos.auth.has_role("admin"):  # Which context?
   ```

2. **Use dual mode for combined access**:
   ```python
   # Store owner analyzing store
   zos.auth.set_active_context("dual")
   # Can perform admin ops while seeing customer view
   ```

3. **Track active context**:
   ```python
   status = zos.auth.status()
   print(f"Active context: {status['active_context']}")
   ```

---

## Troubleshooting

### Common Issues

**1. Permission checks always return False**

```python
# Check database initialization
zos.auth.rbac.ensure_permissions_db()

# Check if permission exists
results = zos.data.select(
    db_label="auth",
    table="user_permissions",
    where={"user_id": user_id, "permission": permission}
)
print(f"Permission records: {results}")
```

**2. Role checks failing unexpectedly**

```python
# Check active context
status = zos.auth.status()
print(f"Context: {status['active_context']}")

# Check user role in active context
user = zos.auth.get_active_user()
print(f"Role: {user.get('role')}")

# Verify role hierarchy
# admin should pass user check
```

**3. Dual mode not working as expected**

```python
# Ensure both contexts authenticated
status = zos.auth.status()
print(f"zSession: {status['zsession']}")
print(f"Apps: {status['applications']}")

# Set dual context explicitly
zos.auth.set_active_context("dual")
```

**4. Grant/revoke permission fails**

```python
# Must be admin
if not zos.auth.has_role("admin"):
    print("Must be admin to manage permissions")

# Check database connection
if not hasattr(zos, 'data'):
    print("zData not initialized")

# Initialize database
zos.auth.rbac.ensure_permissions_db()
```

---

**[← Back to zAuth Guide](../zAuth_GUIDE.md)**
