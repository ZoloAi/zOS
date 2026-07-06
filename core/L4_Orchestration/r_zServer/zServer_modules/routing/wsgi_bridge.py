# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/wsgi_bridge.py

"""
WSGIBridgeHandler — one pipeline for every transport.

This is the seam that lets the WSGI runners (Waitress / external WSGI hosts) serve through
the EXACT same request pipeline as the development http.server: the same
SecurityChecker (path/extension blocking), the same StaticFileHandler, the same
RouteDispatcher (route matching, RBAC, every route type), and the same
``send_error`` (styled error pages). "Trust zServer like Flask" means dev and
prod must be byte-for-byte the same code path — only the transport differs.

It works by subclassing the dev handler and bypassing the socket-bound
``BaseHTTPRequestHandler.__init__`` (which would try to read/write a real
socket). Instead we synthesize the request from a WSGI ``environ`` and override
ONLY the four socket primitives (``send_response`` / ``send_header`` /
``end_headers`` / ``wfile``) to buffer the response. Everything else — the
``do_GET`` / ``do_POST`` flow and all delegate logic — is inherited unchanged.
"""

from io import BytesIO
from http import HTTPStatus
from email.message import Message

from .handler import LoggingHTTPRequestHandler
from .http_headers import build_response_headers

# Fallback cap if no config is threaded through (defense-in-depth; the real
# SSOT is HttpServerConfig.max_body_bytes, mirrored on the config object below).
_DEFAULT_MAX_BODY_BYTES = 25 * 1024 * 1024  # 25 MB


class WSGIBridgeHandler(LoggingHTTPRequestHandler):
    """A handler that drives the dev pipeline from a WSGI environ, buffering output.

    Construct one per request, call :meth:`dispatch`, then read
    :attr:`status_line`, :attr:`response_headers`, and :attr:`body`.
    """

    def __init__(self, environ, *, logger, router, mount_manager, cache_manager, config=None):
        # NOTE: we intentionally DO NOT call super().__init__ — the parent
        # BaseHTTPRequestHandler.__init__ binds to a socket and handles the
        # request inline. We wire the attributes its methods rely on by hand.
        self.logger = logger
        self.router = router
        self.mount_manager = mount_manager
        self.cache_manager = cache_manager
        self.config = config

        # Backward-compat accessors used by delegates
        self.serve_path = mount_manager.serve_path if mount_manager else "."
        self.static_mounts = mount_manager.get_all_mounts() if mount_manager else {}

        # Delegates — identical wiring to LoggingHTTPRequestHandler.__init__
        from .security_checks import SecurityChecker
        from ..rendering.static_file_handler import StaticFileHandler
        from .route_dispatcher import RouteDispatcher
        self.security = SecurityChecker()
        self.static_handler = StaticFileHandler(self)
        self.route_dispatcher = RouteDispatcher(self) if router else None

        # ── Request line / metadata synthesized from the WSGI environ ──────────
        self.command = environ.get("REQUEST_METHOD", "GET").upper()
        self.path = self._build_path(environ)
        self.request_version = environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        self.requestline = f"{self.command} {self.path} {self.request_version}"
        self.client_address = (environ.get("REMOTE_ADDR", ""), 0)
        self.headers = self._build_headers(environ)
        self.rfile = self._read_body(environ)
        self.wfile = BytesIO()

        # Response capture
        self._status_code = 200
        self._status_message = None
        self._headers = []
        self._headers_sent = False

    # ── WSGI request construction ─────────────────────────────────────────────

    @staticmethod
    def _build_path(environ):
        """Reconstruct the raw request path (with query) the dev handler would see."""
        # SCRIPT_NAME is normally empty for our mounts; PATH_INFO carries the route.
        path = environ.get("PATH_INFO", "/") or "/"
        if not path.startswith("/"):
            path = "/" + path
        query = environ.get("QUERY_STRING", "")
        return f"{path}?{query}" if query else path

    @staticmethod
    def _build_headers(environ):
        """Build a case-insensitive header object matching ``BaseHTTPRequestHandler.headers``."""
        msg = Message()
        ctype = environ.get("CONTENT_TYPE")
        if ctype:
            msg["Content-Type"] = ctype
        clen = environ.get("CONTENT_LENGTH")
        if clen:
            msg["Content-Length"] = clen
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-").title()
                msg[header_name] = value
        return msg

    def _read_body(self, environ):
        """Read the request body into a seekable buffer, bounded by the config cap.

        The oversize *rejection* (413) happens in the inherited do_<METHOD> guard
        (_reject_if_oversize); this bound just stops a hostile Content-Length from
        being read into memory before that guard runs.
        """
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            return BytesIO(b"")
        cap = getattr(self.config, "max_body_bytes", 0) if self.config else 0
        if not cap or cap <= 0:
            cap = _DEFAULT_MAX_BODY_BYTES
        to_read = min(length, cap)
        stream = environ.get("wsgi.input")
        data = stream.read(to_read) if stream is not None else b""
        return BytesIO(data)

    # ── Socket primitive overrides (buffer instead of writing to a socket) ─────

    def send_response(self, code, message=None):
        # Parent also stamps Server/Date and logs; we only need status capture.
        self._status_code = int(code)
        self._status_message = message
        self.log_request(code)

    def send_response_only(self, code, message=None):
        self._status_code = int(code)
        self._status_message = message

    def send_header(self, keyword, value):
        self._headers.append((str(keyword), str(value)))

    def end_headers(self):
        # Same shared header policy the dev handler emits (security headers + CORS
        # when configured) — single SSOT in http_headers, no per-transport copy.
        cors_origin = getattr(self.config, "cors_origin", "") if self.config else ""
        for name, value in build_response_headers(cors_origin):
            self._headers.append((name, value))
        self._headers_sent = True

    def flush_headers(self):  # no-op: nothing is socket-bound here
        pass

    def log_request(self, code="-", size="-"):  # avoid socket-era logging path
        if self.logger:
            self.logger.debug(f"[WSGI] {self.command} {self.path} -> {code}")

    def log_message(self, fmt, *args):
        if self.logger:
            self.logger.debug(f"[WSGI] {fmt % args}")

    # ── Dispatch + response assembly ───────────────────────────────────────────

    def dispatch(self):
        """Run the inherited do_<METHOD> flow (same as dev) and capture the response."""
        method_handler = getattr(self, f"do_{self.command}", None)
        if method_handler is None:
            self.send_error(HTTPStatus.NOT_IMPLEMENTED, f"Unsupported method ({self.command})")
        else:
            method_handler()

    @property
    def status_line(self):
        message = self._status_message
        if message is None:
            try:
                message = HTTPStatus(self._status_code).phrase
            except ValueError:
                message = ""
        return f"{self._status_code} {message}".rstrip()

    @property
    def response_headers(self):
        return list(self._headers)

    @property
    def body(self):
        return self.wfile.getvalue()
