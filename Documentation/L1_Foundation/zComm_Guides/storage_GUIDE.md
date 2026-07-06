# zComm Storage Module Guide

> **Module:** `comm_storage.py`  
> **Purpose:** Multi-backend object storage with hierarchical config resolution

---

## Overview

The storage module provides a unified interface to multiple storage backends (local filesystem, S3, Azure, GCS) with automatic backend selection from zConfig's layered hierarchy. Config values are resolved via zConfig's own accessors (`environment.get()` → `get_env_var()`), not by reading the env dict or `os.environ` directly — keeping the storage client consistent with the rest of the framework (SSOT).

**Supported Backends:**
- ✅ Local filesystem
- ✅ AWS S3 (requires `boto3`)
- 🔄 Azure Blob Storage (planned)
- 🔄 Google Cloud Storage (planned)

**Key Features:**
- Backend auto-detection from config hierarchy
- Unified API across all backends
- Presigned URLs for temporary access (S3)
- Hierarchical config resolution (defaults → machine → environment → .zEnv → zSpark)

---

## StorageClient Class

### Initialization

```python
from zOS import zOS

z = zOS()
storage = z.comm.storage  # StorageClient instance
```

**Auto-Initialization:**
- Reads `storage_backend` from config hierarchy
- Creates appropriate adapter (LocalAdapter, S3Adapter, etc.)
- Validates backend is supported
- Falls back to "local" if unknown backend

---

## Configuration

### Backend Selection

**Via .zEnv:**
```bash
STORAGE_BACKEND=local  # or s3, azure, gcs
```

**Via zSpark:**
```python
zSpark = {"storage_backend": "s3"}
z = zOS(zSpark)
```

**Priority (highest to lowest):**
1. zSpark runtime override
2. Environment variables (`STORAGE_BACKEND`)
3. .zEnv file
4. zConfig.environment.zolo
5. System defaults (`"local"`)

---

### Local Backend Config

```bash
# .zEnv
STORAGE_BACKEND=local
STORAGE_LOCAL_ROOT=./storage  # Default: app_root or ./storage
```

---

### S3 Backend Config

```bash
# .zEnv
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=my-bucket
STORAGE_S3_REGION=us-west-2

# AWS credentials (standard AWS credential chain)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

**Credential Sources (boto3 auto-detection):**
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM role (if running on EC2/ECS/Lambda)

---

## Storage Operations

### Upload File

```python
# Upload bytes
data = b"Hello, World!"
path = storage.put("uploads/hello.txt", data)
# Returns: full path or URL

# Upload file-like object
with open("image.jpg", "rb") as f:
    path = storage.put("uploads/image.jpg", f)
```

**Parameters:**
- `key` (str): Storage key/path
- `data` (bytes | BinaryIO): File data

**Returns:** `str` - Full path (local) or URL (S3)

---

### Download File

```python
data = storage.get("uploads/hello.txt")
# Returns: bytes

# Save to file
with open("downloaded.txt", "wb") as f:
    f.write(data)
```

**Raises:** `FileNotFoundError` if file doesn't exist

---

### Delete File

```python
success = storage.delete("uploads/hello.txt")
# Returns: True if deleted, False if not found
```

---

### Check Existence

```python
if storage.exists("uploads/hello.txt"):
    print("File exists")
```

---

### Get URL

```python
# Local: Returns file path
url = storage.get_url("uploads/hello.txt")
# /path/to/storage/uploads/hello.txt

# S3: Returns presigned URL (expires in 1 hour)
url = storage.get_url("uploads/hello.txt", expires_in=3600)
# https://my-bucket.s3.amazonaws.com/uploads/hello.txt?X-Amz-...
```

**Parameters:**
- `key` (str): Storage key
- `expires_in` (int): URL expiration in seconds (default: 3600)

---

## Key Safety (Path Containment)

Every public operation (`put`/`get`/`delete`/`exists`/`get_url`) runs the storage
`key` through a single fail-closed validation gate **before any backend sees it**.
Keys are *relative* locations inside the configured root/bucket — so an absolute
key or one containing `..` segments is rejected, raising `StorageKeyError`:

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import StorageKeyError

storage.put("uploads/user.jpg", data)     # ok → normalized to "uploads/user.jpg"
storage.put("../../etc/passwd", data)      # raises StorageKeyError (traversal)
storage.put("/etc/passwd", data)           # raises StorageKeyError (absolute)
```

**Why:** a `key` may originate from user input or a remote upload (e.g. a Bifrost
client filename). Without containment, `root / key` could escape the storage root
and read/write/delete arbitrary files. The `LocalAdapter` additionally re-checks
the *resolved* path stays under the root (defense-in-depth against symlinks).

This is a **baseline open-core boundary** (it protects the operator's machine with
or without zGuard) — not zGuard's proprietary policy. zGuard may seal additional
allowed-root / signature policy on top; the containment here always applies.

> Catch `StorageKeyError` (a `ValueError` subclass) if you accept untrusted keys
> and want to surface a clean validation error rather than a 500.

---

## Backend-Specific Details

### Local Adapter

**Storage Location:**
1. `STORAGE_LOCAL_ROOT` (if configured)
2. `app_root` (if app-specific storage enabled)
3. `./storage` (fallback)

**Features:**
- Automatic directory creation
- Returns local file paths (not URLs)
- Path-contained: resolved key must stay under the storage root (see [Key Safety](#key-safety-path-containment))

---

### S3 Adapter

**Requirements:**
```bash
pip install boto3
```

**Features:**
- Presigned URLs for temporary access
- Automatic credential detection
- Bucket validation on init
- Comprehensive error handling

**Error Handling:**
- `NoCredentialsError`: AWS credentials not found
- `ClientError 404`: Bucket doesn't exist
- `ClientError 403`: Access denied (check IAM permissions)

---

## Usage Patterns

### Pattern 1: File Upload

```python
# Upload user avatar
with open("avatar.jpg", "rb") as f:
    path = z.comm.storage.put(f"users/{user_id}/avatar.jpg", f)
    print(f"Uploaded to: {path}")
```

---

### Pattern 2: Temporary Access URL

```python
# Generate URL that expires in 5 minutes
url = z.comm.storage.get_url(
    f"users/{user_id}/avatar.jpg",
    expires_in=300
)
# Send URL to client (valid for 5 minutes)
```

---

### Pattern 3: File Cleanup

```python
# Delete old files
if z.comm.storage.exists("temp/old_file.txt"):
    z.comm.storage.delete("temp/old_file.txt")
```

---

### Pattern 4: Backend-Agnostic Code

```python
# Works with any backend (local, S3, Azure, GCS)
def save_user_file(user_id, filename, data):
    key = f"users/{user_id}/{filename}"
    path = z.comm.storage.put(key, data)
    return path

# Backend is configured via .zEnv
# No code changes needed to switch backends
```

---

## Constants Reference

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import (
    STORAGE_DEFAULT_BACKEND,         # "local"
    STORAGE_SUPPORTED_BACKENDS,      # ["local", "s3", "azure", "gcs"]
    STORAGE_CONFIG_KEY_BACKEND,      # "storage_backend"
    STORAGE_CONFIG_KEY_LOCAL_ROOT,   # "storage_local_root"
    STORAGE_CONFIG_KEY_S3_BUCKET,    # "storage_s3_bucket"
    STORAGE_CONFIG_KEY_S3_REGION,    # "storage_s3_region"
)
```

---

## Best Practices

### 1. Use Environment-Specific Backends

```bash
# .zEnv.development
STORAGE_BACKEND=local
STORAGE_LOCAL_ROOT=./dev_storage

# .zEnv.production
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=prod-bucket
```

---

### 2. Store Credentials Securely

```bash
# ✅ .zEnv file (add to .gitignore)
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=yyy

# ❌ Hardcoded in code
storage = S3Adapter(access_key="xxx")  # Never do this!
```

---

### 3. Handle Errors

```python
from zOS.L1_Foundation.b_zComm.zComm_modules import StorageKeyError

try:
    data = storage.get(untrusted_key)
except StorageKeyError:
    print("Rejected unsafe key (absolute or path-escaping)")
except FileNotFoundError:
    print("File not found")
```

---

### 4. Use Presigned URLs for Client Access

```python
# ✅ Generate temporary URL
url = storage.get_url(key, expires_in=300)
# Send URL to client (secure, time-limited)

# ❌ Download and serve via app
data = storage.get(key)
return Response(data)  # Wastes bandwidth
```

---

## See Also

- [zComm Main Guide](../zComm_GUIDE.md)
- [HTTP Client Guide](http_GUIDE.md)
- [Services Guide](services_GUIDE.md)
