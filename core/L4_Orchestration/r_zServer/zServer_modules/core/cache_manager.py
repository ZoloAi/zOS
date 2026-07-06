# zOS/core/L4_Orchestration/r_zServer/zServer_modules/core/cache_manager.py

"""
CacheManager - HTTP cache policy and validation for zServer

Handles:
- Cache policy configuration (max-age, public/private per file type)
- ETag generation and validation
- 304 Not Modified response handling
- Cache statistics tracking (hits, misses, bandwidth saved)

Centralizes all HTTP caching logic that was previously scattered across
StaticFileHandler and RouteDispatcher.
"""

from zOS import os, Optional, Tuple, Dict, Any

from ..utils import http_cache_utils


class CacheManager:
    """
    Manages HTTP caching policy, validation, and statistics for zServer.
    
    Single source of truth for all cache-related operations. Provides
    unified interface for checking cache validity and adding cache headers.
    """

    # Default cache policies (max_age in seconds)
    DEFAULT_POLICIES = {
        "static": {"max_age": 3600, "public": True},      # 1 hour, public
        "api": {"max_age": 300, "public": False},         # 5 minutes, private
        "ui": {"max_age": 0, "public": False},            # Always revalidate
        "template": {"max_age": 0, "public": False},      # Always revalidate
        "favicon": {"max_age": 86400, "public": True}     # 1 day, public
    }

    def __init__(self, config_manager, logger):
        """
        Initialize CacheManager.
        
        Args:
            config_manager: ConfigManager instance (for deployment mode)
            logger: zOS logger instance
        """
        self.config = config_manager
        self.logger = logger
        
        # Load cache policies (use defaults for now, extensible for config override)
        self.policies = self.DEFAULT_POLICIES.copy()
        
        # Initialize statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "bytes_saved": 0,
            "by_type": {
                file_type: {"hits": 0, "misses": 0}
                for file_type in self.policies.keys()
            }
        }
        
        self.logger.debug("[CacheManager] Initialized with default policies")

    def check_and_serve_cached(
        self, 
        handler, 
        file_path: Optional[str] = None,
        file_type: str = "static",
        mtime: Optional[float] = None,
        content: Optional[bytes] = None
    ) -> Tuple[bool, bool]:
        """
        Check if cached response is valid and serve 304 if so.
        
        Single entry point for all cache validation. Handles ETag generation,
        conditional request checking, and 304 response if cache is valid.
        
        Args:
            handler: HTTP request handler instance
            file_path: Path to file being served (for mtime lookup if mtime not provided)
            file_type: File type category (static, api, ui, template, favicon)
            mtime: File modification time (optional, will be looked up if file_path provided)
            content: File content bytes (optional, for content-based ETag)
        
        Returns:
            Tuple[bool, bool]: (should_serve_full_response, response_already_sent)
            - (False, True): 304 sent, don't serve full response
            - (True, False): Cache miss, serve full response
        
        Examples:
            >>> should_serve, sent = cache_manager.check_and_serve_cached(
            ...     handler, "/path/to/file.css", "static"
            ... )
            >>> if sent:
            ...     return  # 304 already sent
            >>> # ... serve full response
        """
        try:
            # Get mtime if not provided
            if mtime is None and file_path and os.path.exists(file_path):
                mtime = os.path.getmtime(file_path)
            
            # Generate ETag
            if content is not None:
                etag = http_cache_utils.generate_etag(content=content)
            elif mtime is not None:
                etag = http_cache_utils.generate_etag(mtime=mtime)
            else:
                # No cache info available
                self._record_miss(file_type)
                return (True, False)
            
            # Build cache control directive
            cache_control = self._build_cache_control(file_type)
            
            # Check if should return 304
            if self._should_return_304(handler.headers, etag, mtime):
                # Send 304 response
                self._send_304_response(handler, etag, mtime, cache_control)
                
                # Record cache hit
                self._record_hit(file_type, content)
                
                return (False, True)  # Don't serve full response, 304 sent
            
            # Cache miss - serve full response
            self._record_miss(file_type)
            return (True, False)
            
        except Exception as e:
            self.logger.debug(f"[CacheManager] Cache check failed: {e}")
            self._record_miss(file_type)
            return (True, False)  # Serve full response on error

    def add_cache_headers(
        self,
        handler,
        file_path: Optional[str] = None,
        file_type: str = "static",
        content: Optional[bytes] = None,
        mtime: Optional[float] = None
    ) -> None:
        """
        Add HTTP cache headers to response (ETag, Last-Modified, Cache-Control).
        
        Call this after sending response code and content headers, before end_headers().
        
        Args:
            handler: HTTP request handler instance
            file_path: Path to file being served (for mtime lookup)
            file_type: File type category (static, api, ui, template, favicon)
            content: File content bytes (for content-based ETag)
            mtime: File modification time (optional, will be looked up if file_path provided)
        
        Examples:
            >>> handler.send_response(200)
            >>> handler.send_header("Content-type", "text/css")
            >>> cache_manager.add_cache_headers(handler, file_path, "static")
            >>> handler.end_headers()
        """
        try:
            # Get mtime if not provided
            if mtime is None and file_path and os.path.exists(file_path):
                mtime = os.path.getmtime(file_path)
            
            # Generate ETag
            if content is not None:
                etag = http_cache_utils.generate_etag(content=content)
            elif mtime is not None:
                etag = http_cache_utils.generate_etag(mtime=mtime)
            else:
                # No cache info - skip cache headers
                return
            
            # Build cache control directive
            cache_control = self._build_cache_control(file_type)
            
            # Add headers
            handler.send_header("ETag", etag)
            if mtime is not None:
                handler.send_header("Last-Modified", http_cache_utils.format_http_date(mtime))
            handler.send_header("Cache-Control", cache_control)
            
        except Exception as e:
            self.logger.debug(f"[CacheManager] Failed to add cache headers: {e}")

    def get_cache_policy(self, file_type: str) -> Dict[str, Any]:
        """
        Get cache policy for a file type.
        
        Args:
            file_type: File type category (static, api, ui, template, favicon)
        
        Returns:
            dict: Cache policy with keys: max_age, public
        """
        return self.policies.get(file_type, {"max_age": 0, "public": False})

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            dict: Statistics with keys: hits, misses, bytes_saved, by_type
        """
        return self.stats.copy()

    def reset_statistics(self) -> None:
        """Reset cache statistics (useful for testing)."""
        self.stats = {
            "hits": 0,
            "misses": 0,
            "bytes_saved": 0,
            "by_type": {
                file_type: {"hits": 0, "misses": 0}
                for file_type in self.policies.keys()
            }
        }
        self.logger.debug("[CacheManager] Statistics reset")

    # =========================================================================
    # Internal Methods (delegate to http_cache_utils or implement policy)
    # =========================================================================

    def _build_cache_control(self, file_type: str) -> str:
        """
        Build Cache-Control header value based on file type and deployment.
        
        Args:
            file_type: File type category
        
        Returns:
            str: Cache-Control directive
        """
        # Get deployment mode
        environment = self.config.get_deployment_mode()
        
        # Development: Always no-cache (force revalidation)
        if environment.lower() in ["development", "testing", "debug"]:
            return "no-cache"
        
        # Production: Use policy-based cache control
        policy = self.get_cache_policy(file_type)
        max_age = policy["max_age"]
        is_public = policy["public"]
        
        if max_age == 0:
            return "no-cache"
        
        visibility = "public" if is_public else "private"
        return f"{visibility}, max-age={max_age}, must-revalidate"

    def _should_return_304(
        self,
        request_headers: Dict[str, str],
        etag: str,
        last_modified: Optional[float] = None
    ) -> bool:
        """
        Check if request should return 304 Not Modified.
        
        Delegates to http_cache_utils for validation logic.
        
        Args:
            request_headers: HTTP request headers
            etag: Current resource ETag
            last_modified: Current resource modification time
        
        Returns:
            bool: True if should return 304
        """
        return http_cache_utils.should_return_304(request_headers, etag, last_modified)

    def _send_304_response(
        self,
        handler,
        etag: str,
        last_modified: Optional[float] = None,
        cache_control: str = None
    ) -> None:
        """
        Send 304 Not Modified response.
        
        Delegates to http_cache_utils for response sending.
        
        Args:
            handler: HTTP request handler
            etag: ETag value
            last_modified: Last-Modified timestamp
            cache_control: Cache-Control directive
        """
        http_cache_utils.send_304_response(handler, etag, last_modified, cache_control)

    def _record_hit(self, file_type: str, content: Optional[bytes] = None) -> None:
        """
        Record cache hit in statistics.
        
        Args:
            file_type: File type category
            content: Content bytes (for bandwidth calculation)
        """
        self.stats["hits"] += 1
        
        if file_type in self.stats["by_type"]:
            self.stats["by_type"][file_type]["hits"] += 1
        
        # Estimate bandwidth saved (approximate)
        if content:
            self.stats["bytes_saved"] += len(content)

    def _record_miss(self, file_type: str) -> None:
        """
        Record cache miss in statistics.
        
        Args:
            file_type: File type category
        """
        self.stats["misses"] += 1
        
        if file_type in self.stats["by_type"]:
            self.stats["by_type"][file_type]["misses"] += 1
