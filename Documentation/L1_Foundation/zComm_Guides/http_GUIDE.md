# zComm HTTP Client Module Guide

> **Module:** `zOS/core/L1_Foundation/b_zComm/zComm_modules/comm_http.py`  
> **Purpose:** Synchronous HTTP client for making web requests (GET, POST, PUT, PATCH, DELETE)

---

## Overview

The `comm_http` module provides a complete HTTP client for zOS applications. It wraps the `requests` library with consistent error handling, logging, and validation while maintaining a pure communication layer (no authentication logic).

**Key Features:**
- All RESTful HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Automatic JSON serialization for request bodies
- Configurable timeouts with validation
- Graceful error handling (returns `None` on failure)
- Comprehensive logging (request/response tracking)
- URL validation (requires `http://` or `https://`)

---

## Architecture

### Design Philosophy

**Pure Communication Layer:**
- No authentication logic (handled by caller, e.g., zAuth)
- No session management
- No retry logic
- Focus: reliable HTTP request/response primitives

**Error Handling:**
- Returns `None` on all failures (timeout, connection error, DNS failure)
- HTTP error codes (404, 500) return Response object (check `.status_code`)
- Validates inputs before making requests (fail-fast)

**Single Request Core (SSOT):**
- All five verbs are thin wrappers over one private `_request(method, url, ...)`
- `_validate(url, timeout)` does the fail-fast checks once; `_request` handles
  logging, dispatch (`requests.request`), and timeout/exception normalization
- Adding a verb or changing error/logging behavior touches one place, not five

---

## HTTPClient Class

### Initialization

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import HTTPClient

client = HTTPClient(logger)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `logger` | Any | Logger instance for debug/error output (required) |

**Attributes:**
- `logger`: Logger instance for request/response tracking

---

## HTTP Methods

### GET Request

Retrieve data from a server.

```python
response = client.get(
    url="https://api.example.com/users",
    params={"limit": 10, "offset": 0},
    headers={"Authorization": "Bearer token"},
    timeout=10
)

if response:
    data = response.json()
    print(f"Status: {response.status_code}")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | Target URL (must start with `http://` or `https://`) |
| `params` | dict | None | Query parameters (URL-encoded automatically) |
| `headers` | dict | None | Custom HTTP headers |
| `timeout` | int | 10 | Request timeout in seconds (must be positive) |

**Returns:**
- `Response` object on success
- `None` on failure (timeout, connection error, DNS failure)

**Raises:**
- `ValueError`: If URL is invalid or timeout is not positive

---

### POST Request

Create a new resource on the server.

```python
response = client.post(
    url="https://api.example.com/users",
    data={"username": "alice", "email": "alice@example.com"},
    timeout=10
)

if response and response.status_code == 201:
    created_user = response.json()
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | Target URL |
| `data` | dict | None | Request body (JSON-serialized automatically) |
| `timeout` | int | 10 | Request timeout in seconds |

**Returns:**
- `Response` object on success
- `None` on failure

**Note:** Data is automatically serialized to JSON with `Content-Type: application/json` header.

---

### PUT Request

Replace an entire resource on the server.

```python
response = client.put(
    url="https://api.example.com/users/123",
    data={"username": "alice", "email": "alice@example.com", "role": "admin"},
    headers={"Authorization": "Bearer token"},
    timeout=10
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | Target URL |
| `data` | dict | None | Complete resource data (JSON-serialized) |
| `headers` | dict | None | Custom HTTP headers |
| `timeout` | int | 10 | Request timeout in seconds |

**Returns:**
- `Response` object on success
- `None` on failure

---

### PATCH Request

Partially update a resource on the server.

```python
response = client.patch(
    url="https://api.example.com/users/123",
    data={"email": "newemail@example.com"},  # Only update email
    headers={"Authorization": "Bearer token"},
    timeout=10
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | Target URL |
| `data` | dict | None | Partial resource data (JSON-serialized) |
| `headers` | dict | None | Custom HTTP headers |
| `timeout` | int | 10 | Request timeout in seconds |

**Returns:**
- `Response` object on success
- `None` on failure

**Use Case:** Update specific fields without sending the entire resource.

---

### DELETE Request

Remove a resource from the server.

```python
response = client.delete(
    url="https://api.example.com/users/123",
    headers={"Authorization": "Bearer token"},
    timeout=10
)

if response and response.status_code == 204:
    print("User deleted successfully")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | Target URL |
| `headers` | dict | None | Custom HTTP headers |
| `timeout` | int | 10 | Request timeout in seconds |

**Returns:**
- `Response` object on success
- `None` on failure

**Note:** DELETE requests typically return status code 204 (No Content) on success.

---

## Error Handling

### Return Values

The HTTP client uses a consistent error handling pattern:

| Scenario | Return Value | How to Check |
|----------|--------------|--------------|
| **Success** | `Response` object | `if response:` |
| **Timeout** | `None` | `if response is None:` |
| **Connection error** | `None` | `if response is None:` |
| **DNS failure** | `None` | `if response is None:` |
| **Invalid URL** | Raises `ValueError` | Caught before request |
| **HTTP error (404, 500)** | `Response` object | `response.status_code >= 400` |

### Example: Comprehensive Error Handling

```python
try:
    response = client.get("https://api.example.com/users/123", timeout=5)
    
    if response is None:
        # Network error, timeout, or connection failure
        print("Request failed - check network connection")
    elif response.status_code == 200:
        # Success
        user = response.json()
        print(f"User: {user}")
    elif response.status_code == 404:
        # Resource not found
        print("User not found")
    elif response.status_code >= 500:
        # Server error
        print("Server error - try again later")
    else:
        # Other HTTP errors
        print(f"HTTP error: {response.status_code}")
        
except ValueError as e:
    # Invalid URL or timeout value
    print(f"Invalid request parameters: {e}")
```

---

## Validation

### URL Validation

All methods validate URLs before making requests:

```python
# Valid URLs
client.get("https://api.example.com/users")  # ✅ HTTPS
client.get("http://localhost:8080/api")      # ✅ HTTP

# Invalid URLs
client.get("api.example.com/users")          # ❌ Missing protocol
client.get("ftp://example.com/file")         # ❌ Wrong protocol
client.get("")                                # ❌ Empty URL
```

**Raises:** `ValueError` with descriptive message if URL is invalid.

---

### Timeout Validation

Timeout must be a positive integer:

```python
# Valid timeouts
client.get(url, timeout=10)   # ✅ 10 seconds
client.get(url, timeout=1)    # ✅ 1 second

# Invalid timeouts
client.get(url, timeout=0)    # ❌ Must be positive
client.get(url, timeout=-5)   # ❌ Must be positive
client.get(url, timeout=3.5)  # ❌ Must be integer
```

**Raises:** `ValueError` if timeout is not a positive integer.

---

## Logging

The HTTP client logs all requests and responses at appropriate levels:

### Debug Level

```python
# Request logging
[HTTPClient] Making HTTP GET request to https://api.example.com/users
[HTTPClient] Query parameters: {'limit': 10, 'offset': 0}
[HTTPClient] Request payload: {'username': 'alice'}

# Response logging
[HTTPClient] Response received [status=200]
```

### Error Level

```python
# Timeout errors
[HTTPClient] HTTP GET request failed to https://api.example.com: Timeout after 10s

# Connection errors
[HTTPClient] HTTP POST request failed to https://api.example.com: Connection refused

# Validation errors
[HTTPClient] Invalid URL provided: api.example.com
```

---

## Response Object

The `requests.Response` object provides:

### Status Code

```python
response.status_code  # 200, 404, 500, etc.
```

### JSON Parsing

```python
data = response.json()  # Parse JSON response body
```

### Text Content

```python
text = response.text  # Raw response body as string
```

### Headers

```python
content_type = response.headers.get('Content-Type')
```

### Success Check

```python
if response.ok:  # True if status_code < 400
    print("Request successful")
```

---

## Usage Patterns

### Pattern 1: Simple GET Request

```python
response = client.get("https://api.example.com/users")
if response:
    users = response.json()
    for user in users:
        print(user['username'])
```

---

### Pattern 2: POST with Error Handling

```python
response = client.post(
    "https://api.example.com/users",
    data={"username": "alice", "email": "alice@example.com"}
)

if response is None:
    print("Network error")
elif response.status_code == 201:
    print("User created successfully")
elif response.status_code == 400:
    errors = response.json()
    print(f"Validation errors: {errors}")
```

---

### Pattern 3: Authenticated Request

```python
# Add authentication header
headers = {"Authorization": f"Bearer {token}"}

response = client.get(
    "https://api.example.com/protected",
    headers=headers
)

if response and response.status_code == 401:
    print("Authentication failed")
```

---

### Pattern 4: Custom Timeout

```python
# Short timeout for health checks
response = client.get("https://api.example.com/health", timeout=2)

# Long timeout for file uploads
response = client.post("https://api.example.com/upload", data=large_file, timeout=60)
```

---

## Integration with zComm

The HTTP client is accessed via the zComm facade:

```python
from zOS import zOS

z = zOS()

# HTTP methods available via z.comm
response = z.comm.http_get("https://api.example.com/users")
response = z.comm.http_post("https://api.example.com/users", data={...})
response = z.comm.http_put("https://api.example.com/users/123", data={...})
response = z.comm.http_patch("https://api.example.com/users/123", data={...})
response = z.comm.http_delete("https://api.example.com/users/123")
```

**Note:** The facade methods delegate directly to `HTTPClient` methods.

---

## Constants Reference

Defined in `comm_http.py`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `_LOG_PREFIX` | `"[HTTPClient]"` | Log message prefix |
| `_LOG_REQUEST` | `"Making HTTP {method} request to {url}"` | Request log template |
| `_LOG_RESPONSE_RECEIVED` | `"Response received [status={status}]"` | Response log template |
| `_ERROR_REQUEST_FAILED` | `"HTTP {method} request failed to {url}: {error}"` | Error template |
| `_ERROR_INVALID_URL` | `"Invalid URL provided: {url}"` | URL validation error |
| `_ERROR_INVALID_TIMEOUT` | `"Timeout must be positive, got: {timeout}"` | Timeout validation error |

**Note:** Constants are module-private (prefixed with `_`) and not exported.

---

## Best Practices

### 1. Always Check for None

```python
response = client.get(url)
if response:  # Check before accessing
    data = response.json()
```

### 2. Handle HTTP Error Codes

```python
if response and response.status_code >= 400:
    print(f"HTTP error: {response.status_code}")
```

### 3. Use Appropriate Timeouts

```python
# Health checks: short timeout
client.get(url, timeout=2)

# Data fetching: moderate timeout
client.get(url, timeout=10)

# File operations: long timeout
client.post(url, data=large_file, timeout=60)
```

### 4. Add Authentication Headers

```python
headers = {"Authorization": f"Bearer {token}"}
response = client.get(url, headers=headers)
```

### 5. Validate URLs Before Use

```python
if not url.startswith(("http://", "https://")):
    url = f"https://{url}"  # Add protocol
```

---

## Limitations

### No Built-in Features

The HTTP client intentionally omits:
- **Authentication**: Use zAuth or add headers manually
- **Session management**: Create new client per session
- **Retry logic**: Implement in application layer
- **Rate limiting**: Handle in application layer
- **Request caching**: Use external caching layer

**Rationale:** Keep the communication layer pure and focused.

---

## See Also

- [zComm Main Guide](../zComm_GUIDE.md) - Complete zComm overview
- [WebSocket Guide](websocket_GUIDE.md) - Real-time bidirectional communication
- [Network Utils Guide](network_GUIDE.md) - Port checking and network utilities
