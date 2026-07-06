**[← Back to zAuth Guide](../zAuth_GUIDE.md)**

---

# Delegates Module Guide

**Module**: `zAuth_modules/auth_delegates.py` + `zAuth_modules/api/`  
**Class**: `zAuthDelegates`  
**Purpose**: Public API composition via delegate pattern (16 methods)

---

## Overview

The **Delegates** module provides the main user-facing API for all authentication operations in zOS. It uses the **Mixin pattern** to compose the zAuth public API from multiple focused delegate classes, following the proven pattern established by zDisplay.

### Key Features

- **Mixin Pattern**: Compose public API from focused delegate classes
- **16 Public Methods**: Complete authentication API surface
- **5 Categories**: Password, Session, Application, Context, RBAC
- **Thin Wrappers**: Delegate to core modules (PasswordSecurity, Authentication, RBAC)
- **Consistent Interface**: Following zDisplay's proven architecture
- **Clean Separation**: Each delegate in its own module

---

## Architecture

### Composition Pattern

```
zAuth (Facade)
  │
  ├── zAuthDelegates (Mixin)
  │     │
  │     ├── DelegatePassword      (2 methods)
  │     ├── DelegateSession       (5 methods)
  │     ├── DelegateApplication   (3 methods)
  │     ├── DelegateContext       (2 methods)
  │     └── DelegateRBAC          (4 methods)
  │
  └── Core Modules
        ├── PasswordSecurity
        ├── Authentication
        └── RBAC
```

### Delegation Chain

```
User calls:     zos.auth.login("user", "pass")
     │
     ▼
Delegate:       DelegateSession.login(self, username, password, ...)
     │
     ▼
Core Module:    self.authentication.login(username, password, ...)
     │
     ▼
Business Logic: LoginManager.login(...)
     │
     ▼
Result:         {"success": True, "username": "user@zolo.com", ...}
```

**Key Point**: Delegates are thin wrappers that provide clean public API while keeping actual business logic in core modules.

---

## Delegate Categories

### 1. DelegatePassword (2 methods)

**Module**: `zAuth_modules/api/delegate_password.py`  
**Purpose**: Password hashing and verification  
**Delegates To**: `self.password_security` (PasswordSecurity instance)

**Methods**:
- `hash_password(plain_password)` → `str`
- `verify_password(plain_password, hashed_password)` → `bool`

**Example**:
```python
# User calls delegate
hashed = zos.auth.hash_password("secure_password")

# Delegate routes to core module
# DelegatePassword.hash_password() → PasswordSecurity.hash_password()
```

---

### 2. DelegateSession (5 methods)

**Module**: `zAuth_modules/api/delegate_session.py`  
**Purpose**: zSession authentication (Tier 1)  
**Delegates To**: `self.authentication` (Authentication instance)

**Methods**:
- `login(username, password, server_url, persist)` → `Dict`
- `logout(context, app_name, delete_persistent)` → `Dict`
- `status()` → `Dict`
- `is_authenticated()` → `bool`
- `get_credentials()` → `Optional[Dict]`

**Example**:
```python
# User calls delegate
result = zos.auth.login("user@zolo.com", "password")

# Delegate routes to core module
# DelegateSession.login() → Authentication.login() → LoginManager.login()
```

---

### 3. DelegateApplication (3 methods)

**Module**: `zAuth_modules/api/delegate_application.py`  
**Purpose**: Application authentication (Tier 2)  
**Delegates To**: `self.authentication` (Authentication instance)

**Methods**:
- `authenticate_app_user(app_name, token, config)` → `Dict`
- `switch_app(app_name)` → `bool`
- `get_app_user(app_name)` → `Optional[Dict]`

**Example**:
```python
# User calls delegate
result = zos.auth.authenticate_app_user("my_store", "token")

# Delegate routes to core module
# DelegateApplication.authenticate_app_user() → Authentication.authenticate_app_user()
```

---

### 4. DelegateContext (2 methods)

**Module**: `zAuth_modules/api/delegate_context.py`  
**Purpose**: Context management (Tier 3)  
**Delegates To**: `self.authentication` (Authentication instance)

**Methods**:
- `set_active_context(context)` → `bool`
- `get_active_user()` → `Optional[Dict]`

**Example**:
```python
# User calls delegate
success = zos.auth.set_active_context("dual")

# Delegate routes to core module
# DelegateContext.set_active_context() → Authentication.set_active_context()
```

---

### 5. DelegateRBAC (4 methods)

**Module**: `zAuth_modules/api/delegate_rbac.py`  
**Purpose**: Role-Based Access Control  
**Delegates To**: `self.rbac` (RBAC instance)

**Methods**:
- `has_role(required_role)` → `bool`
- `has_permission(required_permission)` → `bool`
- `grant_permission(user_id, permission, granted_by)` → `bool`
- `revoke_permission(user_id, permission)` → `bool`

**Example**:
```python
# User calls delegate
has_access = zos.auth.has_role("admin")

# Delegate routes to core module
# DelegateRBAC.has_role() → RBAC.has_role() → RoleChecker.has_role()
```

---

## Mixin Pattern Explained

### What is a Mixin?

A **mixin** is a class designed to be inherited by other classes to add methods, without being a standalone class itself.

```python
# Mixin class (not used directly)
class DelegatePassword:
    def hash_password(self, plain_password: str) -> str:
        return self.password_security.hash_password(plain_password)

# Parent class uses mixin via multiple inheritance
class zAuthDelegates(
    DelegatePassword,
    DelegateSession,
    DelegateApplication,
    DelegateContext,
    DelegateRBAC
):
    pass  # All methods provided by mixins
```

---

### Why Use Mixins?

1. **Separation of Concerns**: Each delegate handles one category
2. **Optimal File Sizes**: Each delegate ~80-220 lines
3. **Easy Extension**: Add new categories without modifying existing code
4. **Clear Responsibility**: Single responsibility per module
5. **Consistent Pattern**: Same architecture as zDisplay

---

### Mixin Composition

```python
# zAuth inherits from zAuthDelegates
class zAuth(zAuthDelegates):
    def __init__(self, zos: Any) -> None:
        # Initialize core modules
        self.password_security = PasswordSecurity(logger=self.logger)
        self.authentication = Authentication(zos)
        self.rbac = RBAC(zos)
        
        # zAuthDelegates methods now available
        # via multiple inheritance

# Usage
zos = zOS()
zos.auth.login("user", "pass")  # From DelegateSession
zos.auth.has_role("admin")      # From DelegateRBAC
```

---

## Method Reference

### Complete API Surface (16 Methods)

#### Password Security (2 methods)

```python
# Hash password
hashed: str = zos.auth.hash_password(plain_password: str)

# Verify password
is_valid: bool = zos.auth.verify_password(
    plain_password: str,
    hashed_password: str
)
```

---

#### zSession Authentication (5 methods)

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

---

#### Application Authentication (3 methods)

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

---

#### Context Management (2 methods)

```python
# Set active context
success: bool = zos.auth.set_active_context(
    context: str  # "zSession", "application", "dual"
)

# Get active user
user: Optional[Dict] = zos.auth.get_active_user()
```

---

#### RBAC (4 methods)

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

## Implementation Pattern

### Delegate Class Structure

Each delegate class follows a consistent pattern:

```python
# Example: DelegatePassword

from zOS import Optional, Any

class DelegatePassword:
    """
    Password security delegate methods.
    
    This mixin provides password hashing and verification methods that
    delegate to the PasswordSecurity module.
    
    Mixin Pattern: This class is designed to be inherited by zAuth via
    zAuthDelegates. It does not initialize any state and relies on the
    parent class's password_security instance.
    
    Methods:
        - hash_password(plain_password) -> str
        - verify_password(plain_password, hashed_password) -> bool
    """
    
    # Type hints for IDE support (set by parent class)
    password_security: Any  # PasswordSecurity instance
    
    def hash_password(self, plain_password: str) -> str:
        """
        Hash a plaintext password using bcrypt.
        
        Delegates to PasswordSecurity.hash_password()
        
        Args:
            plain_password: Plaintext password to hash
        
        Returns:
            str: bcrypt hashed password ($2b$12$...)
        
        Example:
            >>> hashed = zos.auth.hash_password("secure_password")
            >>> print(hashed[:7])
            '$2b$12$'
        """
        return self.password_security.hash_password(plain_password)
    
    def verify_password(
        self,
        plain_password: str,
        hashed_password: str
    ) -> bool:
        """
        Verify a plaintext password against a bcrypt hash.
        
        Delegates to PasswordSecurity.verify_password()
        
        Args:
            plain_password: Plaintext password to verify
            hashed_password: bcrypt hashed password from database
        
        Returns:
            bool: True if password matches hash
        
        Example:
            >>> is_valid = zos.auth.verify_password("password", hashed)
            >>> print(is_valid)
            True
        """
        return self.password_security.verify_password(
            plain_password,
            hashed_password
        )
```

---

### Key Patterns

1. **Docstrings**: Each method documents:
   - What it does
   - What it delegates to
   - Args and return type
   - Usage example

2. **Type Hints**: For IDE autocomplete and type checking

3. **Thin Wrappers**: No business logic, just delegation

4. **Consistent Naming**: Same method names as core modules

5. **Mixin Design**: No `__init__`, relies on parent class

---

## Best Practices

### For Users

1. **Use delegate methods, not core modules directly**:
   ```python
   # Good: Use delegate (public API)
   zos.auth.login("user", "pass")
   
   # Bad: Access core module directly
   # zos.auth.authentication.login("user", "pass")  # Don't
   ```

2. **Trust the abstraction**:
   ```python
   # Delegates handle all complexity
   # Just use the simple API
   result = zos.auth.login("user", "pass")
   if result["status"] == "success":
       # Done!
   ```

3. **Follow method signatures**:
   ```python
   # All delegate methods have clear signatures
   # Use IDE autocomplete for help
   zos.auth.  # <-- IDE shows all 16 methods with docs
   ```

---

### For Developers

1. **Keep delegates thin**:
   ```python
   # Good: Simple delegation
   def login(self, username, password, ...):
       return self.authentication.login(username, password, ...)
   
   # Bad: Business logic in delegate
   # def login(self, username, password, ...):
   #     # Validate...
   #     # Hash password...
   #     # etc...  # DON'T do this here
   ```

2. **Document delegation**:
   ```python
   def has_role(self, required_role):
       """
       Check if user has required role.
       
       Delegates to RBAC.has_role()  # Clear delegation
       
       Args: ...
       Returns: ...
       """
       return self.rbac.has_role(required_role)
   ```

3. **Add new delegates for new categories**:
   ```python
   # Adding new authentication method (e.g., OAuth)
   
   # 1. Create new delegate
   # api/delegate_oauth.py
   class DelegateOAuth:
       def oauth_login(self, provider, token):
           return self.authentication.oauth_login(provider, token)
   
   # 2. Add to zAuthDelegates
   class zAuthDelegates(
       DelegatePassword,
       DelegateSession,
       DelegateApplication,
       DelegateContext,
       DelegateRBAC,
       DelegateOAuth  # New delegate
   ):
       pass
   
   # 3. Now available on zAuth
   zos.auth.oauth_login("google", token)
   ```

---

## Comparison with zDisplay

The delegate pattern in zAuth follows the proven architecture from zDisplay:

| Aspect | zDisplay | zAuth |
|--------|----------|-------|
| **Facade Class** | `zDisplay` | `zAuth` |
| **Mixin Class** | `zDisplayDelegates` | `zAuthDelegates` |
| **Delegate Count** | 5 categories | 5 categories |
| **Method Count** | 25 methods | 16 methods |
| **Pattern** | Mixin composition | Mixin composition |
| **Benefit** | Clean, maintainable API | Clean, maintainable API |

---

## Advanced Topics

### Extending the Delegate Pattern

Add new authentication features by creating new delegates:

```python
# Example: Add biometric authentication

# 1. Create core module
# zAuth_modules/logic/biometric/biometric_auth.py
class BiometricAuth:
    def authenticate_fingerprint(self, fingerprint_data):
        # Biometric authentication logic
        pass

# 2. Create delegate
# zAuth_modules/api/delegate_biometric.py
class DelegateBiometric:
    def authenticate_fingerprint(self, fingerprint_data):
        """Delegate to BiometricAuth.authenticate_fingerprint()"""
        return self.biometric_auth.authenticate_fingerprint(fingerprint_data)

# 3. Add to zAuthDelegates
class zAuthDelegates(
    DelegatePassword,
    DelegateSession,
    DelegateApplication,
    DelegateContext,
    DelegateRBAC,
    DelegateBiometric  # New
):
    pass

# 4. Initialize in zAuth
class zAuth(zAuthDelegates):
    def __init__(self, zos):
        # ...existing modules...
        self.biometric_auth = BiometricAuth(zos)

# 5. Use new delegate
zos.auth.authenticate_fingerprint(fingerprint_data)
```

---

### Type Safety with Protocols

For strict type checking, define protocols:

```python
from typing import Protocol, Any, Dict

class AuthenticationProtocol(Protocol):
    """Protocol defining authentication interface."""
    
    def login(
        self,
        username: str,
        password: str,
        server_url: str | None = None,
        persist: bool = True
    ) -> Dict[str, Any]: ...
    
    def logout(
        self,
        context: str = "zSession",
        app_name: str | None = None,
        delete_persistent: bool = False
    ) -> Dict[str, Any]: ...

# Use in delegate
class DelegateSession:
    authentication: AuthenticationProtocol  # Type-safe
    
    def login(self, username, password, ...):
        return self.authentication.login(username, password, ...)
```

---

## Troubleshooting

### Common Issues

**1. "AttributeError: 'zAuth' object has no attribute 'password_security'"**

```python
# Cause: Core modules not initialized

# Solution: Ensure zAuth.__init__() completes
# Check for errors during initialization
zos = zOS()  # Should initialize all modules
```

**2. "Method not found on zAuth"**

```python
# Cause: Delegate not added to zAuthDelegates

# Solution: Check zAuthDelegates inheritance
class zAuthDelegates(
    DelegatePassword,  # Provides hash_password, verify_password
    DelegateSession,   # Provides login, logout, etc.
    # ... other delegates
):
    pass
```

**3. "Linter warning: Instance attribute not defined"**

```python
# Cause: Mixin pattern confuses linters

# Solution: Add type hints in mixin
class DelegatePassword:
    password_security: Any  # Tell linter this exists
    
    def hash_password(self, plain_password):
        return self.password_security.hash_password(plain_password)
```

---

## Summary

The **Delegates** module provides zAuth's clean, user-facing API through:

- **16 public methods** organized into 5 categories
- **Mixin pattern** for composition and extensibility
- **Thin wrappers** that delegate to core modules
- **Consistent interface** following zDisplay's architecture
- **Clear separation** between API and implementation

**Primary Interaction**: Users interact with delegates, not core modules directly.

```python
# User's view (simple, clean API)
zos.auth.login("user", "pass")
zos.auth.has_role("admin")
zos.auth.grant_permission(user_id, permission, granted_by)

# Behind the scenes (complex, well-organized)
# DelegateSession → Authentication → LoginManager
# DelegateRBAC → RBAC → RoleChecker
# DelegateRBAC → RBAC → PermissionManager
```

---

**[← Back to zAuth Guide](../zAuth_GUIDE.md)**
