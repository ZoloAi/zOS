**[← Back to zAuth Guide](../zAuth_GUIDE.md)**

---

# Security Module Guide

**Module**: `zAuth_modules/security/password_security.py`  
**Class**: `PasswordSecurity`  
**Purpose**: Cryptographically secure password hashing and verification using bcrypt

---

## Overview

The **PasswordSecurity** module provides industry-standard password security using the bcrypt algorithm. It is intentionally isolated from zOS dependencies to ensure maximum testability, reusability, and security auditing.

### Key Features

- **bcrypt Algorithm**: Blowfish cipher with Eksblowfish key schedule
- **Adaptive Hashing**: 12 rounds (4,096 iterations) by default
- **Automatic Salting**: Random 22-character salt per hash
- **Timing-Safe Verification**: Constant-time comparison prevents timing attacks
- **72-Byte Limit Handling**: Automatic truncation with warnings
- **Zero zOS Dependencies**: Pure security module with standard library only

---

## Architecture

### Design Pattern

```
PasswordSecurity
├── hash_password()       # Hash plaintext → bcrypt hash
├── verify_password()     # Verify plaintext against hash
└── _truncate_password()  # Helper: 72-byte truncation (private)
```

### Isolation Strategy

- **No zOS dependencies** (only bcrypt and standard library)
- **Pure functions** with explicit dependencies (logger is optional)
- **Testable in isolation** from zOS framework
- **Reusable** in other Python projects without modification

---

## bcrypt Algorithm

### Algorithm Details

**Base**: Blowfish cipher (Bruce Schneier, 1993)  
**Modification**: "Expensive Key Setup" (Eksblowfish)  
**Purpose**: Designed specifically for password hashing  
**Adaptive**: Cost factor increases hash time exponentially

### Security Properties

1. **One-Way Hash**:
   - Cannot recover plaintext from hash (irreversible)
   - Pre-image resistance (computationally infeasible to reverse)

2. **Rainbow Table Resistance**:
   - Random salt per hash (22-character base64 salt)
   - Same password produces different hashes
   - Salt embedded in hash output: `$2b$12$<salt><hash>`

3. **Brute-Force Protection**:
   - Adaptive cost factor (2^rounds iterations)
   - 12 rounds = 4,096 iterations (~0.3s per hash)
   - Moore's Law mitigation: increase rounds as hardware improves

4. **Timing-Safe Comparison**:
   - bcrypt.checkpw() uses constant-time comparison
   - Prevents timing attacks during verification

### Hash Format

```
$2b$12$<22-char-salt><31-char-hash>
│  │  │  │                │
│  │  │  │                └─ 31 characters (184-bit hash)
│  │  │  └── 22 characters (128-bit salt)
│  │  └─────── Cost factor (12 = 4,096 iterations)
│  └────────── Version (2b)
└───────────── Algorithm identifier
```

**Example**: `$2b$12$N9qo8uLOickgx2ZMRZoMye.IjefVqrEBGZdfo3QJ7A1B2E3fGQi6m`

---

## Performance Characteristics

### Hash Time (12 rounds)

- **Modern CPU (2020+)**: ~0.3 seconds per hash
- **Intentionally slow** to prevent brute-force attacks
- **Acceptable for user login** (human time scale)
- **NOT suitable for high-frequency operations** (use caching)

### Cost Factor Selection

| Rounds | Iterations | Hash Time | Use Case |
|--------|-----------|-----------|----------|
| 10 | 1,024 | ~0.1s | Testing/development |
| 12 | 4,096 | ~0.3s | Production (recommended) |
| 14 | 16,384 | ~1.2s | High-security applications |

**Rule**: Hash should take ~0.5-1.0 seconds on current hardware.

### Memory Usage

- **Minimal per-hash memory**: ~4KB
- **No memory-hard properties** (unlike Argon2)
- **Suitable for constrained environments**

---

## bcrypt Limitations

### 72-Byte Password Limit

bcrypt truncates passwords to 72 bytes:

```python
# UTF-8 encoding: multibyte characters count as multiple bytes
password = "密码" * 40  # 2 Chinese chars × 40 = 80 chars
encoded = password.encode("utf-8")
print(len(encoded))  # 240 bytes (3 bytes per Chinese char)

# bcrypt will truncate to 72 bytes
hashed = pwd_security.hash_password(password)
# Warning logged if logger provided
```

**Recommendation**:
- For passwords > 72 bytes, consider pre-hashing with SHA-256
- Current implementation: truncate and log warning
- Future consideration: SHA-256 pre-hash for long passwords

---

## Thread Safety

### Thread-Safe Operations

- **bcrypt operations**: Thread-safe ✓
- **No shared state**: Each instance is independent ✓
- **Logger requirement**: Must be thread-safe (Python logging is) ✓

### Concurrency Considerations

```python
import threading
from concurrent.futures import ThreadPoolExecutor

pwd_security = PasswordSecurity()

# bcrypt releases GIL during computation
def hash_password_task(password):
    return pwd_security.hash_password(password)

# Thread pool for multiple hashes
with ThreadPoolExecutor(max_workers=5) as executor:
    passwords = ["pass1", "pass2", "pass3", "pass4", "pass5"]
    hashes = list(executor.map(hash_password_task, passwords))
```

**Async/await pattern**:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def hash_password_async(password):
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor()
    return await loop.run_in_executor(
        executor,
        pwd_security.hash_password,
        password
    )

# Usage
hashed = await hash_password_async("my_password")
```

---

## API Reference

### Constructor

```python
PasswordSecurity(logger: Optional[Any] = None)
```

**Args**:
- `logger`: Optional logger instance for warnings and errors
  - If `None`, no logging occurs (graceful degradation)
  - Should support `.warning()` and `.error()` methods

**Example**:

```python
# Without logger (silent mode)
pwd_security = PasswordSecurity()

# With logger (production mode)
import logging
logger = logging.getLogger(__name__)
pwd_security = PasswordSecurity(logger=logger)
```

---

### hash_password()

```python
def hash_password(plain_password: str) -> str
```

Hash a plaintext password using bcrypt with automatic salting.

**Args**:
- `plain_password`: Plaintext password string to hash

**Returns**:
- `str`: bcrypt hashed password in format `$2b$12$<salt><hash>`

**Raises**:
- `ValueError`: If password is empty or None

**Performance**: ~0.3s per hash (12 rounds)

**Example**:

```python
pwd_security = PasswordSecurity()

# Hash password
hashed = pwd_security.hash_password("secure_password")
print(hashed[:7])  # $2b$12$
print(len(hashed))  # 60 characters

# Same password produces different hashes (salted)
hash1 = pwd_security.hash_password("password")
hash2 = pwd_security.hash_password("password")
print(hash1 == hash2)  # False
```

**Security**:
- Uses bcrypt with 12 rounds (4,096 iterations)
- Random salt per hash (rainbow table resistance)
- One-way hash (cannot recover plaintext)
- Passwords > 72 bytes are truncated with warning

---

### verify_password()

```python
def verify_password(plain_password: str, hashed_password: str) -> bool
```

Verify a plaintext password against a bcrypt hash with timing-safe comparison.

**Args**:
- `plain_password`: Plaintext password to verify (user input)
- `hashed_password`: bcrypt hashed password from database/storage

**Returns**:
- `bool`: True if password matches hash, False otherwise

**Performance**: ~0.3s per verification (same as hash)

**Example**:

```python
pwd_security = PasswordSecurity()
hashed = pwd_security.hash_password("correct_password")

# Correct password
is_valid = pwd_security.verify_password("correct_password", hashed)
print(is_valid)  # True

# Wrong password
is_valid = pwd_security.verify_password("wrong_password", hashed)
print(is_valid)  # False

# Invalid hash (graceful failure)
is_valid = pwd_security.verify_password("password", "invalid_hash")
print(is_valid)  # False
```

**Security**:
- Timing-safe comparison via bcrypt.checkpw() (constant time)
- Prevents timing attacks (cannot deduce password from timing)
- Handles invalid hashes gracefully (returns False)
- Logs errors without exposing password details
- Truncates passwords > 72 bytes to match hash_password()

**Error Handling**:
- Empty password: Returns False (no exception)
- Empty hash: Returns False (no exception)
- Invalid hash format: Returns False (logs error)
- Exception during verification: Returns False (logs error)
- Never exposes password in logs or exceptions

---

### _truncate_password() (Private)

```python
def _truncate_password(plain_password: str) -> bytes
```

Truncate password to 72 bytes if necessary (bcrypt limit).

**Args**:
- `plain_password`: Plaintext password string to truncate

**Returns**:
- `bytes`: Password encoded as UTF-8, truncated to 72 bytes if necessary

**Notes**:
- bcrypt has a hard 72-byte limit (algorithm constraint)
- UTF-8 encoding: multibyte characters count as multiple bytes
- Logs warning if truncation occurs (if logger is available)
- Consistent truncation ensures verify_password() matches hash_password()

**Example**:

```python
pwd_security = PasswordSecurity()

short = pwd_security._truncate_password("test")
print(len(short))  # 4 bytes

long = pwd_security._truncate_password("x" * 100)
print(len(long))  # 72 bytes (truncated)
```

---

## Usage Examples

### Basic Usage

```python
from zOS.L2_Handling.f_zAuth.zAuth_modules.security import PasswordSecurity

pwd_security = PasswordSecurity()

# Hash a password
hashed = pwd_security.hash_password("my_secure_password")
print(hashed[:7])  # $2b$12$

# Verify password
is_valid = pwd_security.verify_password("my_secure_password", hashed)
print(is_valid)  # True
```

### With Logger (Production)

```python
import logging
from zOS.L2_Handling.f_zAuth.zAuth_modules.security import PasswordSecurity

logger = logging.getLogger(__name__)
pwd_security = PasswordSecurity(logger=logger)

# Long password warning will be logged
long_password = "x" * 100
hashed = pwd_security.hash_password(long_password)
# WARNING: Password truncated to 72 bytes (bcrypt limit)
```

### Integration with zAuth

```python
# Used by authentication module for user login
from zOS.L2_Handling.f_zAuth.zAuth_modules import PasswordSecurity

pwd_security = PasswordSecurity(logger=zos.logger)

# Store hashed password in database
user_password_hash = pwd_security.hash_password(user_input)

# Verify during login
if pwd_security.verify_password(user_input, stored_hash):
    # Grant access
    grant_access(username)
else:
    # Deny access
    log_failed_attempt(username)
```

### Performance Testing

```python
import time
from zOS.L2_Handling.f_zAuth.zAuth_modules.security import PasswordSecurity

pwd_security = PasswordSecurity()

# Measure hash time
start = time.time()
hashed = pwd_security.hash_password("test_password")
elapsed = time.time() - start
print(f"Hash time: {elapsed:.2f}s")  # ~0.31s

# Measure verify time
start = time.time()
is_valid = pwd_security.verify_password("test_password", hashed)
elapsed = time.time() - start
print(f"Verify time: {elapsed:.2f}s")  # ~0.30s
```

---

## Constants Used

From `auth_constants.py`:

```python
# Public constants
BCRYPT_ROUNDS = 12                    # Cost factor (4,096 iterations)
BCRYPT_MAX_PASSWORD_BYTES = 72        # Truncation limit
HASH_TIME_SECONDS = 0.3              # Expected hash time

# Internal constants (private)
_ENCODING_UTF8 = "utf-8"              # Text encoding
_LOG_PREFIX_PASSWORD = "[PasswordSec]"  # Log message prefix
_LOG_TRUNCATION_WARNING = "Password truncated to 72 bytes (bcrypt limit)"
_LOG_VERIFICATION_ERROR = "Password verification error"
_ERR_EMPTY_PASSWORD = "Password cannot be empty"
```

---

## Best Practices

### Security

1. **Always use bcrypt for passwords**:
   ```python
   # Good
   hashed = pwd_security.hash_password(user_input)
   
   # Bad - never store plaintext
   # password = user_input  # DON'T DO THIS
   ```

2. **Never log sensitive data**:
   ```python
   # Good
   logger.info(f"Password hashed for user: {username}")
   
   # Bad
   # logger.info(f"Password: {password}")  # DON'T
   ```

3. **Use consistent hashing**:
   ```python
   # Always use same PasswordSecurity instance
   pwd_security = PasswordSecurity(logger=logger)
   
   # Hash on registration
   hashed = pwd_security.hash_password(new_password)
   
   # Verify on login
   is_valid = pwd_security.verify_password(login_password, hashed)
   ```

### Performance

1. **Cache authentication results**:
   ```python
   # Don't hash repeatedly for same session
   if user_id not in authenticated_cache:
       is_valid = pwd_security.verify_password(password, stored_hash)
       if is_valid:
           authenticated_cache[user_id] = True
   ```

2. **Use async for concurrent operations**:
   ```python
   # Process multiple password hashes concurrently
   async def hash_all_passwords(passwords):
       tasks = [hash_password_async(pwd) for pwd in passwords]
       return await asyncio.gather(*tasks)
   ```

### Error Handling

1. **Handle all verification results**:
   ```python
   is_valid = pwd_security.verify_password(user_input, stored_hash)
   
   if is_valid:
       grant_access()
   else:
       # Could be wrong password OR invalid hash
       log_failed_attempt()
       deny_access()
   ```

2. **Validate inputs before hashing**:
   ```python
   if not password or len(password) < MIN_PASSWORD_LENGTH:
       raise ValueError("Password too short")
   
   hashed = pwd_security.hash_password(password)
   ```

---

## Troubleshooting

### Common Issues

**1. Hash time too long**
```python
# Reduce rounds for testing (not production!)
# Edit auth_constants.py: BCRYPT_ROUNDS = 10
# Hash time: ~0.1s (less secure)
```

**2. Password > 72 bytes warning**
```python
# Check password length in bytes
password = "my_long_password"
byte_length = len(password.encode("utf-8"))
print(f"Password bytes: {byte_length}")

# Consider enforcing max length
MAX_PASSWORD_LENGTH = 50  # Characters, not bytes
if len(password) > MAX_PASSWORD_LENGTH:
    raise ValueError(f"Password too long (max {MAX_PASSWORD_LENGTH} chars)")
```

**3. Verification always returns False**
```python
# Check hash format
print(hashed[:7])  # Should be "$2b$12$"

# Check password encoding
# Both hash and verify must use same encoding (UTF-8)

# Check hash storage
# Ensure hash isn't truncated in database (60 chars required)
```

**4. Performance issues**
```python
# bcrypt is intentionally slow (~0.3s)
# For high-frequency operations:
# 1. Cache authentication results
# 2. Use session tokens (don't re-verify every request)
# 3. Consider async/parallel processing for batch operations
```

---

## Comparison with Other Algorithms

| Algorithm | Speed | Memory | Security | Adaptive |
|-----------|-------|--------|----------|----------|
| **bcrypt** | Slow (~0.3s) | Low (4KB) | High | Yes (rounds) |
| MD5 | Fast (<0.001s) | Low | **Broken** | No |
| SHA-256 | Fast (<0.001s) | Low | Low (no salt) | No |
| Argon2 | Slow (~0.5s) | High (MB) | **Highest** | Yes (time+mem) |
| PBKDF2 | Slow (~0.2s) | Low | High | Yes (iterations) |

**Why bcrypt?**
- Industry standard for password hashing
- Good balance of security and performance
- Wide adoption and battle-tested
- Available in Python standard libraries
- Low memory requirements (suitable for zOS)

**When to consider Argon2?**
- Maximum security required
- Memory-hard resistance needed
- Modern systems with available RAM

---

**[← Back to zAuth Guide](../zAuth_GUIDE.md)**
