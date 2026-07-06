**[← Back to zAuth Guide](../zAuth_GUIDE.md)**

---

# Actions Module Guide

**Module**: `zAuth_modules/actions/`  
**Files**: `action_login.py`, `action_logout.py`  
**Purpose**: Built-in declarative login/logout handlers for zDispatch integration

---

## Overview

The **Actions** module provides declarative action handlers for authentication operations. These handlers enable login and logout functionality through zOS's declarative action system (zDispatch, zBifrost, zVaF).

### Key Features

- **Declarative Actions**: `zLogin` and `zLogout` action handlers
- **zDispatch Integration**: Execute auth actions from action queues
- **zBifrost Compatibility**: Trigger auth from web UI interactions
- **zVaF Menu Support**: Menu items with authentication triggers
- **Comprehensive Validation**: Input validation and error handling
- **zDisplay Feedback**: User-friendly success/error messages

---

## Architecture

### Action Handlers

```
actions/
├── action_login.py        # handle_zLogin() - Login action handler
├── action_logout.py       # handle_zLogout() - Logout action handler
└── __init__.py            # Export handlers
```

### Integration Points

```
Action Source → zDispatch → Action Handler → zAuth → Result
     │               │             │            │         │
     │               │             │            │         └─ Success/Error Dict
     │               │             │            └─ Perform authentication
     │               │             └─ handle_zLogin/handle_zLogout
     │               └─ Route to registered handler
     └─ zBifrost UI, zVaF menu, manual dispatch
```

---

## zLogin Action

### Action Structure

```python
action_zlogin = {
    "action": "zLogin",              # Required: Action identifier
    "username": "user@zolo.com",     # Required: Username
    "password": "secure_password",   # Required: Password
    "persist": True,                 # Optional: Save session (default: True)
    "server_url": None               # Optional: Remote auth server URL
}
```

### Handler: handle_zLogin()

**Location**: `zAuth_modules/actions/action_login.py`

**Signature**:
```python
def handle_zLogin(
    zos: Any,
    payload: Dict[str, Any]
) -> Dict[str, Any]
```

**Args**:
- `zos`: zOS instance
- `payload`: Action payload dict with keys:
  - `username` (str, required): Username for authentication
  - `password` (str, required): Password for authentication
  - `persist` (bool, optional): Save session to disk (default: True)
  - `server_url` (str, optional): Remote authentication server URL

**Returns**: `Dict` with keys:
- `success` (bool): True if login succeeded
- `action` (str): "zLogin"
- `username` (str): Authenticated username (if successful)
- `user_id` (str): User ID (if successful)
- `role` (str): User role (if successful)
- `api_key` (str): API key (if successful)
- `message` (str): Success or error message

**Process**:
1. Validate payload (username and password required)
2. Call `zos.auth.login()` with provided credentials
3. Display success/error via zDisplay
4. Return result dict

---

### Usage Examples

#### With zDispatch

```python
from zOS import zOS

zos = zOS()

# Define login action
action = {
    "action": "zLogin",
    "username": "user@zolo.com",
    "password": "secure_password",
    "persist": True
}

# Execute via zDispatch
result = zos.dispatch.execute(action)

if result["success"]:
    print(f"Logged in: {result['username']}")
    print(f"Role: {result['role']}")
else:
    print(f"Login failed: {result['message']}")
```

---

#### With zBifrost (Web UI)

```javascript
// Frontend: Send login action to server
fetch('/api/action', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        action: 'zLogin',
        username: document.getElementById('username').value,
        password: document.getElementById('password').value,
        persist: true
    })
})
.then(response => response.json())
.then(result => {
    if (result.success) {
        console.log('Logged in:', result.username);
        // Update UI to show authenticated state
    } else {
        console.error('Login failed:', result.message);
    }
});
```

```python
# Backend: zBifrost route handler
@app.route('/api/action', methods=['POST'])
def handle_action():
    payload = request.json
    result = zos.dispatch.execute(payload)
    return jsonify(result)
```

---

#### With zVaF Menu

```yaml
# menu_config.yaml
menu:
  - id: login_item
    label: Login
    action: zLogin
    action_params:
      username: prompt  # Prompt user for username
      password: prompt  # Prompt user for password
      persist: true
    
  - id: quick_login
    label: Quick Login (Demo)
    action: zLogin
    action_params:
      username: demo@zolo.com
      password: demo_password
      persist: false
```

---

#### Manual Handler Call

```python
from zOS import zOS
from zOS.L2_Handling.f_zAuth.zAuth_modules.actions import handle_zLogin

zos = zOS()

# Call handler directly
payload = {
    "username": "user@zolo.com",
    "password": "secure_password",
    "persist": True,
    "server_url": "https://auth.zolo.com/api/login"
}

result = handle_zLogin(zos, payload)

if result["success"]:
    print(f"Logged in: {result['username']}")
```

---

### Error Handling

The `handle_zLogin` handler validates inputs and provides clear error messages:

```python
# Missing username
result = handle_zLogin(zos, {"password": "pass"})
# Returns: {"success": False, "message": "Username required"}

# Missing password
result = handle_zLogin(zos, {"username": "user"})
# Returns: {"success": False, "message": "Password required"}

# Invalid credentials
result = handle_zLogin(zos, {
    "username": "user@zolo.com",
    "password": "wrong_password"
})
# Returns: {"success": False, "message": "Invalid credentials"}

# Network error (remote auth)
result = handle_zLogin(zos, {
    "username": "user@zolo.com",
    "password": "password",
    "server_url": "https://unreachable.com"
})
# Returns: {"success": False, "message": "Authentication server unreachable"}
```

---

## zLogout Action

### Action Structure

```python
action_zlogout = {
    "action": "zLogout",             # Required: Action identifier
    "context": "zSession",           # Optional: Context to logout ("zSession", "application", "all")
    "app_name": None,                # Optional: App name (required if context="application")
    "delete_persistent": False       # Optional: Delete session from disk
}
```

### Handler: handle_zLogout()

**Location**: `zAuth_modules/actions/action_logout.py`

**Signature**:
```python
def handle_zLogout(
    zos: Any,
    payload: Dict[str, Any]
) -> Dict[str, Any]
```

**Args**:
- `zos`: zOS instance
- `payload`: Action payload dict with keys:
  - `context` (str, optional): Context to logout from ("zSession", "application", "all"). Default: "zSession"
  - `app_name` (str, optional): Application name (required if context="application")
  - `delete_persistent` (bool, optional): Delete persistent session from disk. Default: False

**Returns**: `Dict` with keys:
- `success` (bool): True if logout succeeded
- `action` (str): "zLogout"
- `message` (str): Success or error message

**Process**:
1. Validate payload (app_name required if context="application")
2. Call `zos.auth.logout()` with provided parameters
3. Display success/error via zDisplay
4. Return result dict

---

### Usage Examples

#### Logout zSession (Default)

```python
from zOS import zOS

zos = zOS()

# Logout zSession only
action = {
    "action": "zLogout"
}

result = zos.dispatch.execute(action)

if result["success"]:
    print("Logged out successfully")
```

---

#### Logout Specific Application

```python
from zOS import zOS

zos = zOS()

# Logout from specific app
action = {
    "action": "zLogout",
    "context": "application",
    "app_name": "my_store"
}

result = zos.dispatch.execute(action)

if result["success"]:
    print("Logged out from my_store")
```

---

#### Logout All Contexts

```python
from zOS import zOS

zos = zOS()

# Logout from all contexts
action = {
    "action": "zLogout",
    "context": "all",
    "delete_persistent": True  # Also delete from disk
}

result = zos.dispatch.execute(action)

if result["success"]:
    print("Logged out from all contexts")
```

---

#### With zBifrost (Web UI)

```javascript
// Frontend: Send logout action
fetch('/api/action', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        action: 'zLogout',
        context: 'all',
        delete_persistent: true
    })
})
.then(response => response.json())
.then(result => {
    if (result.success) {
        console.log('Logged out');
        // Redirect to login page
        window.location.href = '/login';
    }
});
```

---

#### With zVaF Menu

```yaml
# menu_config.yaml
menu:
  - id: logout_zsession
    label: Logout
    action: zLogout
    action_params:
      context: zSession
      delete_persistent: true
    
  - id: logout_all
    label: Logout All
    action: zLogout
    action_params:
      context: all
      delete_persistent: true
```

---

### Error Handling

```python
# Missing app_name when context="application"
result = handle_zLogout(zos, {
    "context": "application"
    # Missing app_name
})
# Returns: {"success": False, "message": "app_name required for application context"}

# Invalid context
result = handle_zLogout(zos, {
    "context": "invalid_context"
})
# Returns: {"success": False, "message": "Invalid context: invalid_context"}
```

---

## Action Registration

### Automatic Registration

The zLogin and zLogout actions are **automatically registered** when zAuth initializes:

```python
# In zAuth.__init__()
from .zAuth_modules.actions import handle_zLogin, handle_zLogout

# Register actions with zDispatch
self.zos.dispatch.register_action("zLogin", handle_zLogin)
self.zos.dispatch.register_action("zLogout", handle_zLogout)
```

**No manual registration required!** Just use the actions.

---

### Manual Registration (Advanced)

For custom action dispatchers:

```python
from zOS import zOS
from zOS.L2_Handling.f_zAuth.zAuth_modules.actions import (
    handle_zLogin,
    handle_zLogout
)

zos = zOS()

# Register with custom dispatcher
my_dispatcher.register("zLogin", lambda payload: handle_zLogin(zos, payload))
my_dispatcher.register("zLogout", lambda payload: handle_zLogout(zos, payload))
```

---

## Integration Patterns

### Pattern 1: Login Form Flow

```python
# 1. User submits login form (web UI)
# 2. Frontend sends zLogin action to backend
# 3. Backend executes action via zDispatch
# 4. Action handler calls zos.auth.login()
# 5. Result returned to frontend
# 6. Frontend updates UI based on result

# Backend route
@app.route('/login', methods=['POST'])
def login():
    action = {
        "action": "zLogin",
        "username": request.form['username'],
        "password": request.form['password'],
        "persist": request.form.get('remember_me', False)
    }
    
    result = zos.dispatch.execute(action)
    
    if result["success"]:
        session['user_id'] = result['user_id']
        return redirect('/dashboard')
    else:
        flash(result['message'], 'error')
        return redirect('/login')
```

---

### Pattern 2: Protected Menu Items

```yaml
# menu_config.yaml
menu:
  # Public item (no auth)
  - id: home
    label: Home
    
  # Protected item (requires auth)
  - id: dashboard
    label: Dashboard
    require_auth: true
    
  # Login item (visible when not authenticated)
  - id: login
    label: Login
    action: zLogin
    action_params:
      username: prompt
      password: prompt
    visible_when: not_authenticated
    
  # Logout item (visible when authenticated)
  - id: logout
    label: Logout
    action: zLogout
    visible_when: authenticated
```

---

### Pattern 3: Action Chaining

```python
from zOS import zOS

zos = zOS()

# Execute multiple actions in sequence
actions = [
    # 1. Login
    {
        "action": "zLogin",
        "username": "user@zolo.com",
        "password": "password"
    },
    # 2. Load user data
    {
        "action": "zLoadUserData",
        "user_id": "${prev.user_id}"  # Reference previous result
    },
    # 3. Initialize dashboard
    {
        "action": "zInitDashboard"
    }
]

for action in actions:
    result = zos.dispatch.execute(action)
    if not result.get("success"):
        print(f"Action failed: {action['action']}")
        break
```

---

## Best Practices

### Security

1. **Never log passwords**:
   ```python
   # Good
   logger.info(f"Login attempt: {payload.get('username')}")
   
   # Bad
   # logger.info(f"Login: {payload}")  # Contains password!
   ```

2. **Validate inputs thoroughly**:
   ```python
   # Always check required fields
   if "username" not in payload or "password" not in payload:
       return {"success": False, "message": "Missing credentials"}
   ```

3. **Use HTTPS for remote auth**:
   ```python
   # Good
   server_url = "https://auth.zolo.com"
   
   # Bad
   # server_url = "http://auth.zolo.com"  # Insecure
   ```

---

### User Experience

1. **Provide clear feedback**:
   ```python
   # Display success/error messages
   if result["success"]:
       zos.display.success(f"Welcome back, {result['username']}!")
   else:
       zos.display.error(f"Login failed: {result['message']}")
   ```

2. **Handle common errors gracefully**:
   ```python
   # Friendly error messages
   error_messages = {
       "Invalid credentials": "Incorrect username or password",
       "Server unreachable": "Cannot connect to authentication server",
       "Session expired": "Your session has expired. Please login again"
   }
   ```

3. **Persist sessions by default**:
   ```python
   # Default to persist=True for better UX
   action = {
       "action": "zLogin",
       "username": username,
       "password": password,
       "persist": True  # Remember user
   }
   ```

---

### Integration

1. **Register actions once**:
   ```python
   # Good: Register in initialization
   def init_auth():
       zos.dispatch.register_action("zLogin", handle_zLogin)
       zos.dispatch.register_action("zLogout", handle_zLogout)
   
   # Bad: Register repeatedly
   # for _ in range(10):
   #     zos.dispatch.register_action("zLogin", handle_zLogin)
   ```

2. **Use action payloads consistently**:
   ```python
   # Good: Consistent structure
   action = {
       "action": "zLogin",
       "username": username,
       "password": password
   }
   
   # Bad: Inconsistent keys
   # action = {"type": "login", "user": username, "pass": password}
   ```

3. **Handle action results properly**:
   ```python
   result = zos.dispatch.execute(action)
   
   # Always check success
   if result.get("success"):
       # Handle success
       pass
   else:
       # Handle failure
       print(result.get("message", "Unknown error"))
   ```

---

## Troubleshooting

### Common Issues

**1. Action not found**

```python
# Error: Action 'zLogin' not registered

# Solution: Ensure zAuth initialized
zos = zOS()  # zAuth registers actions automatically

# Or register manually
from zOS.L2_Handling.f_zAuth.zAuth_modules.actions import handle_zLogin
zos.dispatch.register_action("zLogin", handle_zLogin)
```

**2. Missing required fields**

```python
# Error: "Username required"

# Solution: Check payload structure
action = {
    "action": "zLogin",
    "username": "user@zolo.com",  # Required
    "password": "password"         # Required
}
```

**3. Logout fails for application context**

```python
# Error: "app_name required for application context"

# Solution: Provide app_name
action = {
    "action": "zLogout",
    "context": "application",
    "app_name": "my_store"  # Required for application context
}
```

**4. Action succeeds but UI not updated**

```python
# Solution: Handle result in frontend
fetch('/api/action', {...})
.then(response => response.json())
.then(result => {
    if (result.success) {
        // Update UI to reflect authentication state
        updateAuthUI(result.username, result.role);
    }
});
```

---

## Advanced Topics

### Custom Action Handlers

Create custom authentication actions:

```python
def handle_zSwitchUser(zos: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Custom action: Switch between authenticated users."""
    
    # Validate
    new_username = payload.get("username")
    if not new_username:
        return {"success": False, "message": "Username required"}
    
    # Logout current
    zos.auth.logout()
    
    # Login new (assumes stored credentials)
    stored_password = get_stored_password(new_username)
    result = zos.auth.login(new_username, stored_password)
    
    return result

# Register custom action
zos.dispatch.register_action("zSwitchUser", handle_zSwitchUser)
```

---

### Action Middleware

Add middleware to wrap authentication actions:

```python
def auth_action_middleware(handler):
    """Middleware: Log all authentication actions."""
    
    def wrapper(zos: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Before
        action = payload.get("action")
        logger.info(f"Auth action started: {action}")
        
        # Execute
        result = handler(zos, payload)
        
        # After
        logger.info(f"Auth action completed: {action} (success={result.get('success')})")
        
        return result
    
    return wrapper

# Wrap handlers
handle_zLogin = auth_action_middleware(handle_zLogin)
handle_zLogout = auth_action_middleware(handle_zLogout)
```

---

**[← Back to zAuth Guide](../zAuth_GUIDE.md)**
