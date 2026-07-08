# zOS/core/L1_Foundation/b_zComm/zComm_modules/comm_storage.py
"""
Object Storage Client for zOS - Hierarchical Config Aware.

Provides unified interface to storage backends with automatic config
resolution through zConfig's layered hierarchy.

Hierarchy (lowest → highest priority):
    1. System defaults: STORAGE_BACKEND=local (zConfig defaults)
    2. User config: User's storage preferences
    3. .zEnv: STORAGE_BACKEND=s3, STORAGE_S3_BUCKET=my-bucket
    4. zSpark: {"storage_backend": "s3"} (runtime override)

Usage:
    # Backend auto-detected from config hierarchy
    zos.comm.storage.put("path/to/file.jpg", data)
    
    # Config examples (.zEnv):
    STORAGE_BACKEND=local
    STORAGE_LOCAL_ROOT=storage/
"""

from zOS import Path, Union, BinaryIO, Any, Callable
from .comm_constants import (
    STORAGE_DEFAULT_BACKEND,
    STORAGE_SUPPORTED_BACKENDS,
    STORAGE_CONFIG_KEY_BACKEND,
    STORAGE_CONFIG_KEY_LOCAL_ROOT,
    STORAGE_CONFIG_KEY_PUBLIC_BASE,
    STORAGE_CONFIG_KEY_S3_BUCKET,
    STORAGE_CONFIG_KEY_S3_REGION
)

# Module Constants
_LOG_PREFIX = "[StorageClient]"


class StorageKeyError(ValueError):
    """Raised when a storage key is unsafe (absolute or path-escaping).

    Fail-closed: a denied key never reaches a backend. This is a baseline
    open-core boundary (Type-B user protection), not zGuard proprietary policy —
    it works with or without zGuard installed.
    """


def _validate_storage_key(key: str) -> str:
    """Validate + normalize a storage key before any backend sees it (SSOT gate).

    Storage keys are *relative* locations inside the configured root/bucket. An
    absolute key or one containing ``..`` segments could escape that root on
    filesystem backends (path traversal → arbitrary read/write/delete). Reject
    both up front, regardless of which backend is active. Callers that pass a
    user-supplied / remote (Bifrost upload) key are contained here.

    Returns the normalized key (forward slashes, ``.``-segments stripped).
    Raises ``StorageKeyError`` on an unsafe key.
    """
    if not key or not isinstance(key, str):
        raise StorageKeyError(f"Invalid storage key: {key!r}")

    norm = key.replace("\\", "/").strip()

    # Reject POSIX-absolute ("/x") and Windows-drive-absolute ("C:/x") keys.
    if norm.startswith("/") or (len(norm) >= 2 and norm[1] == ":"):
        raise StorageKeyError(f"Absolute storage keys are not allowed: {key!r}")

    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise StorageKeyError(f"Path traversal in storage key is not allowed: {key!r}")

    return "/".join(parts)


class StorageClient:
    """
    Unified object storage interface with hierarchical config resolution.
    
    Automatically selects backend based on zConfig's layered hierarchy.
    """

    def __init__(self, zos: Any):
        """
        Initialize storage client with auto-detected backend.
        
        Args:
            zos: zOS instance (provides access to config hierarchy)
        """
        self.zos = zos
        self.logger = zos.logger

        # Get backend from config hierarchy (auto-cascades through zConfig layers)
        backend = self._get_config(STORAGE_CONFIG_KEY_BACKEND, STORAGE_DEFAULT_BACKEND)

        # Validate backend
        if backend not in STORAGE_SUPPORTED_BACKENDS:
            self.logger.warning(
                f"{_LOG_PREFIX} Unknown backend '{backend}', falling back to 'local'"
            )
            backend = "local"

        # Initialize appropriate adapter
        self.backend = backend
        self.adapter = self._create_adapter(backend)

        self.logger.framework.info(f"{_LOG_PREFIX} Initialized with backend: {backend}")

    def _get_config(self, key: str, default: Any = None) -> Any:
        """
        Get config value via zConfig's own accessors (SSOT cascade).

        Delegates resolution to zConfig instead of poking the env dict /
        os.environ directly, so the storage client stays consistent with the
        rest of the framework's config hierarchy.

        Args:
            key: Config key (e.g., "storage_backend")
            default: Default value if not found

        Returns:
            Config value from highest priority layer
        """
        env = self.zos.config.environment

        # zConfig-managed environment (supports dotted nested keys)
        value = env.get(key)
        if value is not None:
            return value

        # OS environment fallback (uppercase, e.g. STORAGE_BACKEND)
        value = env.get_env_var(key.upper())
        if value is not None:
            return value

        return default

    def _create_adapter(self, backend: str):
        """Create storage adapter based on backend type."""
        if backend == "local":
            return LocalAdapter(self.zos, self._get_config)
        elif backend == "s3":
            return S3Adapter(self.zos, self._get_config)
        elif backend == "azure":
            return AzureBlobAdapter(self.zos, self._get_config)
        elif backend == "gcs":
            return GCSAdapter(self.zos, self._get_config)
        else:
            # Fallback
            return LocalAdapter(self.zos, self._get_config)

    # ═══════════════════════════════════════════════════════════
    # Public API (Backend-Agnostic)
    # ═══════════════════════════════════════════════════════════

    def put(self, key: str, data: Union[bytes, BinaryIO]) -> str:
        """
        Upload file to storage.
        
        Args:
            key: Storage key (e.g., "storage/users/00/01/2345/avatar.jpg")
            data: File data (bytes or file-like object)
        
        Returns:
            str: Full path or URL to stored file
        """
        return self.adapter.put(_validate_storage_key(key), data)

    def get(self, key: str) -> bytes:
        """
        Download file from storage.
        
        Args:
            key: Storage key
        
        Returns:
            bytes: File data
        """
        return self.adapter.get(_validate_storage_key(key))

    def delete(self, key: str) -> bool:
        """
        Delete file from storage.
        
        Args:
            key: Storage key
        
        Returns:
            bool: True if deleted, False if not found
        """
        return self.adapter.delete(_validate_storage_key(key))

    def exists(self, key: str) -> bool:
        """
        Check if file exists in storage.
        
        Args:
            key: Storage key
        
        Returns:
            bool: True if exists, False otherwise
        """
        return self.adapter.exists(_validate_storage_key(key))

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generate URL for file access.
        
        Args:
            key: Storage key
            expires_in: URL expiration in seconds (default: 1 hour)
        
        Returns:
            str: Public or presigned URL
        """
        return self.adapter.get_url(_validate_storage_key(key), expires_in)


# ═══════════════════════════════════════════════════════════
# Storage Adapters (Backend Implementations)
# ═══════════════════════════════════════════════════════════

class StorageAdapter:
    """Abstract base class for storage adapters."""

    def put(self, key: str, data: Union[bytes, BinaryIO]) -> str:
        """Upload file to storage."""
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        """Download file from storage."""
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        """Delete file from storage."""
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        """Check if file exists in storage."""
        raise NotImplementedError

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate URL for file access."""
        raise NotImplementedError


class LocalAdapter(StorageAdapter):
    """Local filesystem storage adapter."""

    def __init__(self, zos: Any, get_config: Callable[[str, Any], Any]):
        self.zos = zos
        self.logger = zos.logger
        self.get_config = get_config

        # Get root from config (Layer 4: .zEnv, Layer 5: zSpark)
        root_path = self.get_config(STORAGE_CONFIG_KEY_LOCAL_ROOT, None)

        if root_path:
            self.root = Path(root_path)
        elif zos.config.app_root:
            # Use app-specific storage (Phase 1.1)
            self.root = zos.config.app_root
        else:
            # Fallback: current directory
            self.root = Path.cwd() / "storage"

        # Web base the root is served under (app policy, e.g. "/static/media").
        # Unset + relative root → the root's own path doubles as the URL base,
        # since a relative root lives inside the served app dir. Absolute root
        # with no declared base has no derivable URL (get_url falls back to path).
        public_base = self.get_config(STORAGE_CONFIG_KEY_PUBLIC_BASE, None)
        if public_base:
            self.public_base = "/" + str(public_base).strip("/")
        elif root_path and not Path(root_path).is_absolute():
            self.public_base = "/" + Path(root_path).as_posix().strip("/")
        else:
            self.public_base = None

        self.logger.framework.debug(
            f"{_LOG_PREFIX} LocalAdapter root: {self.root} (public base: {self.public_base})"
        )

    def _resolve(self, key: str) -> Path:
        """Resolve ``key`` under the storage root and assert it stays inside it.

        Defense-in-depth on top of ``_validate_storage_key`` (which already
        rejects ``..``/absolute keys): re-checks the *resolved* path so symlinks
        or odd inputs cannot escape the root. Fail-closed.
        """
        root = self.root.resolve()
        file_path = (self.root / key).resolve()
        if file_path != root and root not in file_path.parents:
            raise StorageKeyError(f"Storage key escapes root: {key!r}")
        return file_path

    def put(self, key: str, data: Union[bytes, BinaryIO]) -> str:
        """Save file to local filesystem."""
        file_path = self._resolve(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            file_path.write_bytes(data)
        else:
            file_path.write_bytes(data.read())

        self.logger.framework.debug(f"{_LOG_PREFIX} Saved: {file_path}")
        return str(file_path)

    def get(self, key: str) -> bytes:
        """Read file from local filesystem."""
        file_path = self._resolve(key)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {key}")
        return file_path.read_bytes()

    def delete(self, key: str) -> bool:
        """Delete file from local filesystem."""
        file_path = self._resolve(key)
        if file_path.exists():
            file_path.unlink()
            self.logger.framework.debug(f"{_LOG_PREFIX} Deleted: {file_path}")
            return True
        return False

    def exists(self, key: str) -> bool:
        """Check if file exists."""
        return self._resolve(key).exists()

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Return the web URL the stored key is served at.

        Uses the configured/derived public base (see __init__). Only when no
        base is derivable (absolute root, no STORAGE_PUBLIC_BASE declared) does
        this fall back to the filesystem path — a server path must never be the
        default answer for a web-facing URL.
        """
        if self.public_base:
            return f"{self.public_base}/{key}"
        return str(self._resolve(key))


class S3Adapter(StorageAdapter):
    """
    AWS S3 storage adapter (Phase 1.3b).
    
    Uses boto3 for S3 operations with automatic credential detection:
    1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    2. AWS credentials file (~/.aws/credentials)
    3. IAM role (if running on EC2/ECS/Lambda)
    """

    def __init__(self, zos: Any, get_config: Callable[[str, Any], Any]):
        self.zos = zos
        self.logger = zos.logger
        self.get_config = get_config

        # Import boto3 (lazy import - only when S3 backend is used)
        try:
            import boto3  # type: ignore[import-not-found]
            from botocore.exceptions import ClientError, NoCredentialsError  # type: ignore[import-not-found]
            self.boto3 = boto3
            self.ClientError = ClientError
            self.NoCredentialsError = NoCredentialsError
        except ImportError as exc:
            self.logger.error(f"{_LOG_PREFIX} boto3 not installed! Run: pip install boto3")
            raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3") from exc

        # Get S3 configuration from zConfig hierarchy
        self.bucket = self.get_config(STORAGE_CONFIG_KEY_S3_BUCKET, None)
        self.region = self.get_config(STORAGE_CONFIG_KEY_S3_REGION, 'us-east-1')

        if not self.bucket:
            raise ValueError("STORAGE_S3_BUCKET must be configured in .zEnv for S3 backend")

        # Initialize S3 client (credentials auto-detected from environment)
        try:
            self.client = boto3.client('s3', region_name=self.region)

            # Verify bucket exists and we have access
            self.client.head_bucket(Bucket=self.bucket)

            self.logger.framework.info(
                f"{_LOG_PREFIX} S3Adapter initialized: s3://{self.bucket} (region: {self.region})"
            )
        except self.NoCredentialsError:
            self.logger.error(
                f"{_LOG_PREFIX} AWS credentials not found! Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .zEnv"
            )
            raise
        except self.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                self.logger.error(f"{_LOG_PREFIX} S3 bucket '{self.bucket}' does not exist!")
            elif error_code == '403':
                self.logger.error(f"{_LOG_PREFIX} Access denied to bucket '{self.bucket}'. Check IAM permissions.")
            else:
                self.logger.error(f"{_LOG_PREFIX} S3 error: {e}")
            raise

    def put(self, key: str, data: Union[bytes, BinaryIO]) -> str:
        """Upload file to S3."""
        try:
            # Convert BinaryIO to bytes if needed
            if not isinstance(data, bytes):
                data = data.read()

            # Upload to S3
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data
            )

            self.logger.framework.debug(f"{_LOG_PREFIX} Uploaded: s3://{self.bucket}/{key}")
            return f"s3://{self.bucket}/{key}"

        except self.ClientError as e:
            self.logger.error(f"{_LOG_PREFIX} Failed to upload {key}: {e}")
            raise

    def get(self, key: str) -> bytes:
        """Download file from S3."""
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            data = response['Body'].read()

            self.logger.framework.debug(f"{_LOG_PREFIX} Downloaded: s3://{self.bucket}/{key}")
            return data

        except self.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise FileNotFoundError(f"File not found in S3: {key}") from e
            else:
                self.logger.error(f"{_LOG_PREFIX} Failed to download {key}: {e}")
                raise

    def delete(self, key: str) -> bool:
        """Delete file from S3."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)

            self.logger.framework.debug(f"{_LOG_PREFIX} Deleted: s3://{self.bucket}/{key}")
            return True

        except self.ClientError as e:
            self.logger.error(f"{_LOG_PREFIX} Failed to delete {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if file exists in S3."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            else:
                self.logger.error(f"{_LOG_PREFIX} Error checking existence of {key}: {e}")
                raise

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generate presigned URL for temporary access.
        
        Args:
            key: S3 object key
            expires_in: URL expiration in seconds (default: 1 hour)
        
        Returns:
            Presigned URL that expires after expires_in seconds
        """
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expires_in
            )

            self.logger.framework.debug(
                f"{_LOG_PREFIX} Generated presigned URL for {key} (expires in {expires_in}s)"
            )
            return url

        except self.ClientError as e:
            self.logger.error(f"{_LOG_PREFIX} Failed to generate presigned URL for {key}: {e}")
            raise


class AzureBlobAdapter(StorageAdapter):
    """Azure Blob Storage adapter (future)."""

    def __init__(self, zos: Any, _get_config: Callable[[str, Any], Any]):
        self.logger = zos.logger
        self.logger.framework.warning(f"{_LOG_PREFIX} AzureBlobAdapter not yet implemented!")

    def put(self, key: str, data: Union[bytes, BinaryIO]) -> str:
        raise NotImplementedError("Azure support coming later")

    def get(self, key: str) -> bytes:
        raise NotImplementedError("Azure support coming later")

    def delete(self, key: str) -> bool:
        raise NotImplementedError("Azure support coming later")

    def exists(self, key: str) -> bool:
        raise NotImplementedError("Azure support coming later")

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        raise NotImplementedError("Azure support coming later")


class GCSAdapter(StorageAdapter):
    """Google Cloud Storage adapter (future)."""

    def __init__(self, zos: Any, _get_config: Callable[[str, Any], Any]):
        self.logger = zos.logger
        self.logger.framework.warning(f"{_LOG_PREFIX} GCSAdapter not yet implemented!")

    def put(self, key: str, data: Union[bytes, BinaryIO]) -> str:
        raise NotImplementedError("GCS support coming later")

    def get(self, key: str) -> bytes:
        raise NotImplementedError("GCS support coming later")

    def delete(self, key: str) -> bool:
        raise NotImplementedError("GCS support coming later")

    def exists(self, key: str) -> bool:
        raise NotImplementedError("GCS support coming later")

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        raise NotImplementedError("GCS support coming later")
