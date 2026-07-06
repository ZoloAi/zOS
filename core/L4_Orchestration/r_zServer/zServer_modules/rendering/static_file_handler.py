# zOS/core/L4_Orchestration/r_zServer/zServer_modules/rendering/static_file_handler.py

"""
Static File Handler - File serving operations

Handles:
- Default favicon serving
- /static/* files (Flask convention)
- Custom mount points (/bifrost/, /plugins/, etc.)
- /UI/* files (zVaF files)
"""

from zOS import os
from urllib.parse import unquote

from ..routing.security_checks import SecurityChecker
from ..routing.utils import HandlerUtils


class StaticFileHandler:
    """Static file serving for HTTP requests."""

    def __init__(self, handler):
        """
        Initialize static file handler.
        
        Args:
            handler: Parent HTTP request handler instance
        """
        self.handler = handler
        self.logger = getattr(handler, 'logger', None)

    # ── shared file serving (Range-aware, chunked, disconnect-safe) ───────────
    # Media (esp. video) seeks via HTTP Range; without it the browser aborts the
    # full-file response → BrokenPipe → a bogus 500. This helper answers Range
    # with 206, streams in chunks (no whole-file read into memory), and treats a
    # client disconnect as benign. SSOT for static + mounted serving.

    _STREAM_CHUNK = 64 * 1024  # 64 KiB

    @staticmethod
    def _parse_range(range_header, file_size):
        """Parse a single 'bytes=start-end' range. Returns (start, end) inclusive,
        or (None, None) if unsatisfiable/unsupported."""
        try:
            units, _, spec = range_header.partition('=')
            if units.strip().lower() != 'bytes':
                return None, None
            # Only the first range of a (rare) multi-range request is honored.
            spec = spec.split(',', 1)[0].strip()
            start_s, _, end_s = spec.partition('-')
            if start_s == '':
                # Suffix range: last N bytes.
                n = int(end_s)
                if n <= 0:
                    return None, None
                start = max(0, file_size - n)
                end = file_size - 1
            else:
                start = int(start_s)
                end = int(end_s) if end_s else file_size - 1
            end = min(end, file_size - 1)
            if start > end or start >= file_size:
                return None, None
            return start, end
        except (ValueError, AttributeError):
            return None, None

    def _stream_range(self, file_path, start, length):
        """Stream `length` bytes from `start`; swallow client disconnects."""
        remaining = length
        try:
            with open(file_path, 'rb') as f:
                f.seek(start)
                while remaining > 0:
                    chunk = f.read(min(self._STREAM_CHUNK, remaining))
                    if not chunk:
                        break
                    self.handler.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            # Client aborted (seek/close/tab navigation) — benign.
            if self.logger:
                self.logger.debug(f"[StaticFileHandler] Client disconnected mid-stream: {self.handler.path}")

    def _serve_file_content(self, file_path, content_type, cache_type, mtime=None):
        """Serve a file body with Range support + chunked streaming.
        Caller handles existence/security checks and the 304 cache short-circuit."""
        file_size = os.path.getsize(file_path)
        if mtime is None:
            mtime = os.path.getmtime(file_path)
        range_header = self.handler.headers.get('Range') if self.handler.headers else None

        if range_header:
            start, end = self._parse_range(range_header, file_size)
            if start is None:
                self.handler.send_response(416)
                self.handler.send_header("Content-Range", f"bytes */{file_size}")
                self.handler.send_header("Accept-Ranges", "bytes")
                self.handler.end_headers()
                return
            length = end - start + 1
            self.handler.send_response(206)
            self.handler.send_header("Content-type", content_type)
            self.handler.send_header("Accept-Ranges", "bytes")
            self.handler.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.handler.send_header("Content-length", str(length))
            # Range responses are cacheable too — without these the browser
            # re-streams media (esp. looping/autoplay video) on every player and
            # navigation. Mirrors the 200 branch so video caches like images do.
            self.handler.cache_manager.add_cache_headers(self.handler, file_path, cache_type, mtime=mtime)
            self.handler.end_headers()
            self._stream_range(file_path, start, length)
            return

        # Full response — advertise Range so the browser knows it can seek.
        self.handler.send_response(200)
        self.handler.send_header("Content-type", content_type)
        self.handler.send_header("Accept-Ranges", "bytes")
        self.handler.send_header("Content-length", str(file_size))
        self.handler.cache_manager.add_cache_headers(self.handler, file_path, cache_type, mtime=mtime)
        self.handler.end_headers()
        self._stream_range(file_path, 0, file_size)

    def _send_error_safe(self, code, message):
        """send_error that never explodes if the socket is already gone."""
        try:
            return self.handler.send_error(code, message)
        except (BrokenPipeError, ConnectionResetError):
            return None

    def serve_default_favicon(self):
        """Serve default zolo favicon from zServer static folder."""
        # Path to default favicon in zServer static folder
        zserver_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        favicon_path = os.path.join(zserver_dir, 'static', 'favicon.ico')

        if not os.path.exists(favicon_path):
            # No default favicon, return 404
            return self.handler.send_error(404, "Favicon not found")

        try:
            # Check cache and serve 304 if valid
            should_serve, sent = self.handler.cache_manager.check_and_serve_cached(
                self.handler, favicon_path, "favicon"
            )
            if sent:
                return  # 304 already sent
            
            # Serve full response
            with open(favicon_path, 'rb') as f:
                favicon_data = f.read()

            mtime = os.path.getmtime(favicon_path)
            
            self.handler.send_response(200)
            self.handler.send_header("Content-type", "image/x-icon")
            self.handler.send_header("Content-length", len(favicon_data))
            self.handler.cache_manager.add_cache_headers(self.handler, favicon_path, "favicon", mtime=mtime)
            self.handler.end_headers()
            self.handler.wfile.write(favicon_data)

        except Exception as e:
            if self.logger:
                self.logger.error(f"[StaticFileHandler] Error serving favicon: {e}")
            return self.handler.send_error(500, f"Error serving favicon: {str(e)}")

    def serve_zsys_asset(self, filename):
        """
        Serve a whitelisted zSys accessibility data file (SSOT) to the browser.

        The emoji a11y JSON has ONE on-disk home inside zOS (zSys/accessibility/
        data/). Rather than copying it into every app's static/, the server streams
        that canonical file here so the Bifrost client and the zCLI consume the
        exact same data. Only the explicit allow-list below is reachable.
        """
        from .....zSys.accessibility._data import data_file_path

        allowed = {"emoji-a11y.en.json", "bootstrap-icons.json"}
        if filename not in allowed:
            return self.handler.send_error(404, "Unknown zSys asset")

        asset_path = str(data_file_path(filename))
        if not os.path.exists(asset_path):
            return self.handler.send_error(404, "zSys asset not found")

        try:
            should_serve, sent = self.handler.cache_manager.check_and_serve_cached(
                self.handler, asset_path, "static"
            )
            if sent:
                return

            with open(asset_path, 'rb') as f:
                data = f.read()

            mtime = os.path.getmtime(asset_path)

            self.handler.send_response(200)
            self.handler.send_header("Content-type", "application/json; charset=utf-8")
            self.handler.send_header("Content-length", len(data))
            self.handler.cache_manager.add_cache_headers(self.handler, asset_path, "static", mtime=mtime)
            self.handler.end_headers()
            self.handler.wfile.write(data)

        except (BrokenPipeError, ConnectionResetError):
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"[StaticFileHandler] Error serving zSys asset: {e}")
            return self._send_error_safe(500, f"Error serving zSys asset: {str(e)}")

    def serve_static_file(self):
        """
        Auto-serve files from /static/* (Flask convention).
        
        Maps /static/js/hello.js → {serve_path}/static/js/hello.js
        """
        # Remove /static/ prefix to get relative path
        relative_path = self.handler.path[8:]  # Remove '/static/'

        # Decode URL encoding (e.g., %20 → space)
        relative_path = unquote(relative_path)

        # Build absolute path using MountManager
        static_folder_path = self.handler.mount_manager.get_folder_path("static")
        file_path = os.path.join(static_folder_path, relative_path)

        # Security: Prevent directory traversal (SSOT containment: realpath + commonpath)
        if not SecurityChecker.is_path_safe(file_path, static_folder_path):
            return self.handler.send_error(403, "Access denied")
        file_path = os.path.realpath(file_path)

        # Security: never serve source/secret/config file types as assets
        if SecurityChecker.is_blocked_extension(file_path):
            return self.handler.send_error(403, "Access denied")

        # Check if file exists
        if not os.path.exists(file_path):
            return self.handler.send_error(404, f"File not found: {self.handler.path}")

        # Check if it's a directory (not allowed)
        if os.path.isdir(file_path):
            return self.handler.send_error(403, "Directory listing is disabled")

        # Serve the file
        try:
            range_header = self.handler.headers.get('Range') if self.handler.headers else None

            # Cache 304 short-circuit — skipped for Range requests (seek/partial).
            if not range_header:
                should_serve, sent = self.handler.cache_manager.check_and_serve_cached(
                    self.handler, file_path, "static"
                )
                if sent:
                    return  # 304 already sent

            content_type = HandlerUtils.guess_content_type(file_path)
            self._serve_file_content(file_path, content_type, "static")

            if self.logger:
                self.logger.debug(f"[StaticFileHandler] Served static file: {self.handler.path}")

        except (BrokenPipeError, ConnectionResetError):
            # Client aborted before/while headers were sent — benign, no 500.
            if self.logger:
                self.logger.debug(f"[StaticFileHandler] Client disconnected: {self.handler.path}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"[StaticFileHandler] Error serving static file: {e}")
            return self._send_error_safe(500, f"Error serving file: {str(e)}")

    def serve_mounted_file(self, url_prefix: str, fs_root: str):
        """
        Serve file from a custom mount point.
        
        Generic mount handler that serves files from any configured filesystem location.
        Each mount has its own security boundary (directory traversal protection).
        
        Args:
            url_prefix: URL prefix (e.g., "/bifrost/", "/shared/")
            fs_root: Filesystem root path (absolute)
        
        Example:
            url_prefix="/bifrost/", fs_root="/Users/gal/bifrost/"
            Request: /bifrost/src/client.js
            Serves: /Users/gal/bifrost/src/client.js
        
        Security:
            - Directory traversal protection per mount
            - No directory listing
            - Validates file exists and is readable
        """
        # Remove URL prefix to get relative path within mount
        relative_path = self.handler.path[len(url_prefix):]

        # Decode URL encoding (e.g., %20 → space)
        relative_path = unquote(relative_path)

        # Build absolute path within mount
        file_path = os.path.join(fs_root, relative_path)

        # Security: Prevent directory traversal (SSOT containment: realpath + commonpath)
        if not SecurityChecker.is_path_safe(file_path, fs_root):
            if self.logger:
                self.logger.warning(f"[StaticFileHandler] Directory traversal attempt blocked: {self.handler.path}")
            return self.handler.send_error(403, "Access denied")
        file_path = os.path.realpath(file_path)

        # Security: never serve source/secret/config file types from a mount
        # (e.g. /plugins/*.py server-side logic must stay private).
        if SecurityChecker.is_blocked_extension(file_path):
            if self.logger:
                self.logger.warning(f"[StaticFileHandler] Blocked sensitive extension: {self.handler.path}")
            return self.handler.send_error(403, "Access denied")

        # Check if file exists
        if not os.path.exists(file_path):
            return self.handler.send_error(404, f"File not found: {self.handler.path}")

        # Check if it's a directory (not allowed)
        if os.path.isdir(file_path):
            return self.handler.send_error(403, "Directory listing is disabled")

        # Serve the file
        try:
            # CSS/styles files are treated as UI (no-cache) — they change during development
            # like zVaFiles and must not be browser-cached between edits.
            cache_type = "ui" if file_path.endswith(".css") else "static"

            range_header = self.handler.headers.get('Range') if self.handler.headers else None

            # Cache 304 short-circuit — skipped for Range requests (seek/partial).
            if not range_header:
                should_serve, sent = self.handler.cache_manager.check_and_serve_cached(
                    self.handler, file_path, cache_type
                )
                if sent:
                    return  # 304 already sent

            content_type = HandlerUtils.guess_content_type(file_path)
            self._serve_file_content(file_path, content_type, cache_type)

            if self.logger:
                self.logger.debug(f"[StaticFileHandler] Served from mount {url_prefix}: {self.handler.path}")

        except (BrokenPipeError, ConnectionResetError):
            # Client aborted before/while headers were sent — benign, no 500.
            if self.logger:
                self.logger.debug(f"[StaticFileHandler] Client disconnected: {self.handler.path}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"[StaticFileHandler] Error serving mounted file {self.handler.path}: {e}")
            return self._send_error_safe(500, f"Error serving file: {str(e)}")

    def serve_ui_file(self):
        """
        Auto-serve zVaFiles from /UI/* (zUI convention).
        
        Maps /UI/zUI.index.zolo → {serve_path}/UI/zUI.index.zolo
        Supports .zolo, .yaml, .json formats.
        """
        # Remove /UI/ prefix to get relative path (case-insensitive match)
        ui_folder_name = self.handler.mount_manager.get_folder_name("UI")
        ui_prefix = f'/{ui_folder_name}/'
        ui_prefix_len = len(ui_prefix)

        # Handle both exact case and lowercase URLs
        if self.handler.path.startswith(ui_prefix):
            relative_path = self.handler.path[ui_prefix_len:]
        else:
            # Case-insensitive fallback
            relative_path = self.handler.path[ui_prefix_len:]

        # Decode URL encoding (e.g., %20 → space)
        relative_path = unquote(relative_path)

        # Build absolute path using MountManager
        ui_folder_path = self.handler.mount_manager.get_folder_path("UI")
        file_path = os.path.join(ui_folder_path, relative_path)

        # Security: Prevent directory traversal (SSOT containment: realpath + commonpath)
        if not SecurityChecker.is_path_safe(file_path, ui_folder_path):
            return self.handler.send_error(403, "Access denied")
        file_path = os.path.realpath(file_path)

        # Check if file exists
        if not os.path.exists(file_path):
            return self.handler.send_error(404, f"UI file not found: {self.handler.path}")

        # Check if it's a directory (not allowed)
        if os.path.isdir(file_path):
            return self.handler.send_error(403, "Directory listing is disabled")

        # Serve the zVaFile
        try:
            # Check cache and serve 304 if valid
            should_serve, sent = self.handler.cache_manager.check_and_serve_cached(
                self.handler, file_path, "ui"
            )
            if sent:
                return  # 304 already sent
            
            # Serve full response
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            mtime = os.path.getmtime(file_path)
            content_bytes = content.encode('utf-8')
            
            # Determine content type based on extension
            if file_path.endswith('.json'):
                content_type = 'application/json'
            elif file_path.endswith('.zolo'):
                content_type = 'application/x-yaml'  # .zolo uses YAML syntax
            else:
                content_type = 'application/x-yaml'  # Legacy .yaml files

            self.handler.send_response(200)
            self.handler.send_header("Content-type", content_type)
            self.handler.send_header("Content-length", len(content_bytes))
            self.handler.cache_manager.add_cache_headers(self.handler, file_path, "ui", mtime=mtime)
            self.handler.end_headers()
            self.handler.wfile.write(content_bytes)

            if self.logger:
                self.logger.debug(f"[StaticFileHandler] Served UI file: {self.handler.path}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"[StaticFileHandler] Error serving UI file: {e}")
            return self.handler.send_error(500, f"Error serving UI file: {str(e)}")
