# zOS/core/L1_Foundation/b_zComm/zComm_modules/comm_http.py
"""
HTTP client for zComm subsystem.

Provides a complete HTTP client for making web requests (GET, POST, PUT, PATCH, DELETE).
This is a pure communication layer with no authentication logic - auth should be handled
by the caller (e.g., zAuth subsystem).
"""

from zOS import Any, Dict, Optional, requests
from .comm_constants import HTTP_DEFAULT_TIMEOUT

# Module Constants

# Logging
_LOG_PREFIX = "[HTTPClient]"

# Log Messages
_LOG_REQUEST = "Making HTTP {method} request to {url}"
_LOG_REQUEST_PAYLOAD = "Request payload: {data}"
_LOG_REQUEST_PARAMS = "Query parameters: {params}"
_LOG_RESPONSE_RECEIVED = "Response received [status={status}]"

# Error Messages
_ERROR_REQUEST_FAILED = "HTTP {method} request failed to {url}: {error}"
_ERROR_INVALID_URL = "Invalid URL provided: {url}"
_ERROR_INVALID_TIMEOUT = "Timeout must be positive, got: {timeout}"


class HTTPClient:
    """
    HTTP client for making web requests (GET, POST, PUT, PATCH, DELETE).
    
    This is a pure communication layer with no authentication logic.
    Authentication should be handled by the caller (e.g., zAuth subsystem).
    
    Example:
        >>> client = HTTPClient(logger)
        >>> response = client.get("https://api.example.com/users")
        >>> response = client.post("https://api.example.com/users", 
        ...                        data={"name": "Alice"}, 
        ...                        timeout=5)
        >>> if response:
        ...     print(f"Status: {response.status_code}")
    """

    def __init__(self, logger: Any) -> None:
        """
        Initialize HTTP client.
        
        Args:
            logger: Logger instance for debug/error output
        """
        self.logger = logger

    def _validate(self, url: str, timeout: int) -> None:
        """
        Validate URL and timeout (raises ValueError on failure).

        Args:
            url: Target URL (must be a non-empty http(s) string)
            timeout: Positive integer timeout in seconds

        Raises:
            ValueError: If url is empty/invalid or timeout is not positive
        """
        if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
            error_msg = _ERROR_INVALID_URL.format(url=url)
            self.logger.error(f"{_LOG_PREFIX} {error_msg}")
            raise ValueError(error_msg)

        if not isinstance(timeout, int) or timeout <= 0:
            error_msg = _ERROR_INVALID_TIMEOUT.format(timeout=timeout)
            self.logger.error(f"{_LOG_PREFIX} {error_msg}")
            raise ValueError(error_msg)

    def _request(self, method: str, url: str, *,
                 params: Optional[Dict[str, Any]] = None,
                 data: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None,
                 timeout: int = HTTP_DEFAULT_TIMEOUT) -> Optional[Any]:
        """
        Core request dispatcher shared by all verbs (SSOT for HTTP I/O).

        Pure communication layer - no auth logic. Validates inputs, logs the
        request/response, and normalizes error handling (timeout vs other).

        Args:
            method: HTTP verb ("GET", "POST", "PUT", "PATCH", "DELETE")
            url: Target URL (must start with http:// or https://)
            params: Optional query parameters (URL-encoded)
            data: Optional JSON body (dict serialized to JSON)
            headers: Optional custom headers
            timeout: Request timeout in seconds (must be positive)

        Returns:
            Response object on success, None on request failure

        Raises:
            ValueError: If url is empty/invalid or timeout is not positive
        """
        self._validate(url, timeout)

        self.logger.debug(f"{_LOG_PREFIX} {_LOG_REQUEST.format(method=method, url=url)}")
        if params:
            self.logger.debug(f"{_LOG_PREFIX} {_LOG_REQUEST_PARAMS.format(params=params)}")
        if data:
            self.logger.debug(f"{_LOG_PREFIX} {_LOG_REQUEST_PAYLOAD.format(data=data)}")

        try:
            response = requests.request(
                method, url, params=params, json=data, headers=headers, timeout=timeout
            )
            self.logger.debug(
                f"{_LOG_PREFIX} {_LOG_RESPONSE_RECEIVED.format(status=response.status_code)}"
            )
            return response

        except requests.Timeout:
            error_msg = _ERROR_REQUEST_FAILED.format(method=method, url=url, error=f"Timeout after {timeout}s")
            self.logger.error(f"{_LOG_PREFIX} {error_msg}")
            return None

        except requests.RequestException as e:
            error_msg = _ERROR_REQUEST_FAILED.format(method=method, url=url, error=str(e))
            self.logger.error(f"{_LOG_PREFIX} {error_msg}")
            return None

    def get(self, url: str, params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: int = HTTP_DEFAULT_TIMEOUT) -> Optional[Any]:
        """Make HTTP GET request - pure communication, no auth logic."""
        return self._request("GET", url, params=params, headers=headers, timeout=timeout)

    def post(self, url: str, data: Optional[Dict[str, Any]] = None,
             timeout: int = HTTP_DEFAULT_TIMEOUT) -> Optional[Any]:
        """Make HTTP POST request - pure communication, no auth logic."""
        return self._request("POST", url, data=data, timeout=timeout)

    def put(self, url: str, data: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: int = HTTP_DEFAULT_TIMEOUT) -> Optional[Any]:
        """Make HTTP PUT request - pure communication, no auth logic."""
        return self._request("PUT", url, data=data, headers=headers, timeout=timeout)

    def patch(self, url: str, data: Optional[Dict[str, Any]] = None,
              headers: Optional[Dict[str, str]] = None,
              timeout: int = HTTP_DEFAULT_TIMEOUT) -> Optional[Any]:
        """Make HTTP PATCH request - pure communication, no auth logic."""
        return self._request("PATCH", url, data=data, headers=headers, timeout=timeout)

    def delete(self, url: str, headers: Optional[Dict[str, str]] = None,
               timeout: int = HTTP_DEFAULT_TIMEOUT) -> Optional[Any]:
        """Make HTTP DELETE request - pure communication, no auth logic."""
        return self._request("DELETE", url, headers=headers, timeout=timeout)
