# zOS/core/L4_Orchestration/r_zServer/zServer_modules/utils/http_cache_utils.py

"""
HTTP Cache Utilities - Low-level helpers for ETag and HTTP date formatting

This module provides pure utility functions for HTTP caching primitives.
Higher-level caching logic (policy, validation, statistics) is handled by CacheManager.

Functions:
    - generate_etag(): Create ETag from content or mtime
    - format_http_date(): Format timestamp as HTTP date string
    - should_return_304(): Check if conditional request should return 304
    - send_304_response(): Send 304 Not Modified response

Note: Cache policy and management moved to CacheManager.
      This module contains only stateless utility functions.

Version: 2.0.0 (Refactored for CacheManager integration)
"""

from zOS import Optional, Dict
import hashlib
from email.utils import formatdate


# =============================================================================
# ETAG GENERATION
# =============================================================================

def generate_etag(content: bytes = None, mtime: float = None) -> str:
    """
    Generate ETag for HTTP caching.
    
    Uses weak ETags (W/"...") for mtime-based generation (semantic equivalence)
    and strong ETags ("...") for content-based generation (byte-for-byte match).
    
    Args:
        content: File content bytes (for content-based ETag)
        mtime: File modification time (for mtime-based ETag)
    
    Returns:
        str: ETag string in format W/"..." or "..."
    
    Raises:
        ValueError: If neither content nor mtime provided
    
    Examples:
        >>> generate_etag(mtime=1234567890.123)
        'W/"1234567890.123"'
        
        >>> generate_etag(content=b"hello world")
        '"5eb63bbbe01eeed093cb22bb8f5acdc3"'
    
    Note:
        - Weak ETags (W/"...") indicate semantic equivalence, not byte-for-byte
        - Strong ETags ("...") indicate exact byte-for-byte match
        - Prefer mtime-based for performance (no hashing needed)
    """
    if content is not None:
        # Content-based: Strong ETag (byte-for-byte match)
        content_hash = hashlib.md5(content).hexdigest()
        return f'"{content_hash}"'
    
    elif mtime is not None:
        # Mtime-based: Weak ETag (semantic equivalence)
        # Use high-precision float to avoid collisions
        return f'W/"{mtime}"'
    
    else:
        raise ValueError("Either content or mtime must be provided")


def format_http_date(timestamp: float) -> str:
    """
    Format Unix timestamp as HTTP date string (RFC 7231).
    
    Args:
        timestamp: Unix timestamp (seconds since epoch)
    
    Returns:
        str: HTTP date string (e.g., "Thu, 01 Jan 2024 00:00:00 GMT")
    
    Examples:
        >>> format_http_date(1234567890.0)
        'Fri, 13 Feb 2009 23:31:30 GMT'
    """
    return formatdate(timeval=timestamp, localtime=False, usegmt=True)


# =============================================================================
# CONDITIONAL REQUEST VALIDATION
# =============================================================================

def should_return_304(
    request_headers: Dict[str, str],
    etag: str,
    last_modified: float = None
) -> bool:
    """
    Check if request should return 304 Not Modified.
    
    Validates conditional request headers (If-None-Match, If-Modified-Since)
    against current resource state (ETag, Last-Modified).
    
    Args:
        request_headers: HTTP request headers (case-insensitive dict)
        etag: Current resource ETag
        last_modified: Current resource modification time (optional)
    
    Returns:
        bool: True if should return 304, False otherwise
    
    Examples:
        >>> headers = {'If-None-Match': 'W/"1234567890.123"'}
        >>> should_return_304(headers, 'W/"1234567890.123"')
        True
        
        >>> headers = {'If-None-Match': 'W/"999"'}
        >>> should_return_304(headers, 'W/"1234567890.123"')
        False
    
    Note:
        - If-None-Match takes precedence over If-Modified-Since (RFC 7232)
        - Weak ETag comparison allows W/"123" to match W/"123" or "123"
        - Strong ETag comparison requires exact match
    """
    # Case-insensitive header lookup
    headers_lower = {k.lower(): v for k, v in request_headers.items()}
    
    # Check If-None-Match (ETag validation)
    if_none_match = headers_lower.get("if-none-match")
    if if_none_match:
        # Parse multiple ETags (comma-separated)
        client_etags = [tag.strip() for tag in if_none_match.split(',')]
        
        # Check if any client ETag matches current ETag
        for client_etag in client_etags:
            if _etags_match(client_etag, etag):
                return True
        
        # If-None-Match present but no match - return False
        # (Don't check If-Modified-Since per RFC 7232)
        return False
    
    # Check If-Modified-Since (timestamp validation)
    if_modified_since = headers_lower.get("if-modified-since")
    if if_modified_since and last_modified is not None:
        try:
            # Parse HTTP date to timestamp
            from email.utils import parsedate_to_datetime
            client_time = parsedate_to_datetime(if_modified_since).timestamp()
            
            # Compare timestamps (allow 1 second tolerance for float precision)
            if abs(last_modified - client_time) < 1.0:
                return True
        except (ValueError, TypeError):
            # Invalid date format - ignore
            pass
    
    return False


def _etags_match(etag1: str, etag2: str) -> bool:
    """
    Compare two ETags for equality (weak comparison).
    
    Weak comparison: W/"123" matches W/"123" or "123"
    Strong comparison: "123" only matches "123"
    
    Args:
        etag1: First ETag
        etag2: Second ETag
    
    Returns:
        bool: True if ETags match
    
    Examples:
        >>> _etags_match('W/"123"', 'W/"123"')
        True
        
        >>> _etags_match('W/"123"', '"123"')
        True
        
        >>> _etags_match('"123"', '"456"')
        False
    """
    # Strip weak prefix for comparison (W/"..." → "...")
    val1 = etag1.replace('W/"', '"')
    val2 = etag2.replace('W/"', '"')
    
    return val1 == val2


# =============================================================================
# 304 RESPONSE HELPERS
# =============================================================================

def send_304_response(handler, etag: str = None, last_modified: float = None, cache_control: str = None) -> None:
    """
    Send 304 Not Modified response.
    
    Sends minimal response with status code, ETag, Last-Modified, and
    Cache-Control headers. No body is sent (per RFC 7232).
    
    Args:
        handler: HTTP request handler instance
        etag: ETag to include in response (optional)
        last_modified: Last-Modified timestamp to include (optional)
        cache_control: Cache-Control header value (optional)
    
    Examples:
        >>> send_304_response(handler, etag='W/"123"', last_modified=1234567890.0, cache_control="no-store")
    
    Note:
        - 304 responses MUST NOT contain a message body
        - Must include ETag and/or Last-Modified if present in 200 response
        - Cache-Control should match what would be sent in 200 response
        - Called by CacheManager._send_304_response()
    """
    handler.send_response(304)  # 304 Not Modified
    
    # Add Cache-Control if provided (must be after send_response)
    if cache_control:
        handler.send_header("Cache-Control", cache_control)
    
    # Add ETag if provided
    if etag:
        handler.send_header("ETag", etag)
    
    # Add Last-Modified if provided
    if last_modified:
        handler.send_header("Last-Modified", format_http_date(last_modified))
    
    handler.end_headers()
    # No body for 304 responses
