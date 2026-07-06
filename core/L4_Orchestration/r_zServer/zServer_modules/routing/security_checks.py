# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/security_checks.py

"""
Security Checks - Path validation and access control

Handles:
- Blocked path validation (models/, zEnv files, certs, source, etc.)
- Hidden / dotfile segment blocking (.git, .env, .DS_Store, ...)
- Sensitive-extension blocking for served assets (.py, .zolo, .key, ...)
- Directory traversal prevention

GOLDEN RULE: env/config/secret/source files are loaded like dotenv into
os.environ and must NEVER be reachable over HTTP. These checks are the
defense-in-depth enforcement of that rule (independent of mount layout).
"""

import os


class SecurityChecker:
    """Security validation for HTTP requests."""

    # Blocked path prefixes (folders/files never accessible via HTTP).
    # Matched with startswith on the request path.
    BLOCKED_PATHS = [
        '/models/',       # Database schemas (may contain connection info)
        '/zConfigs/',     # Configuration files
        '/zConfig.',      # zConfig.*.zolo at root
        '/zEnv.',         # zEnv.base/development/production.zolo (dotenv-style secrets!)
        '/.zEnv',         # Legacy env file naming
        '/.env',          # Alternative env file naming
        '/certs/',        # TLS certificates and PRIVATE KEYS
        '/zSpark.',       # Deployment manifests (zSpark.*.zolo)
        '/zProject.',     # Project manifests (zProject.*.zolo)
        '/zLoom/',        # Server-side data-binding reads
        '/Data/',         # App data (CSV / SQLite ledgers)
        '/.git/',         # Version control
        '/routes/',       # Server route definitions
        '/__pycache__/',  # Python cache
        '/zCLI/',         # Framework internals (legacy name)
        '/zOS/',          # Framework internals
    ]

    # File extensions that must never be served as static/mounted assets.
    # NOTE: /UI/ zVaFiles (.zolo/.yaml/.json) are served by serve_ui_file,
    # which does NOT run this check — those are intentionally public UI.
    BLOCKED_EXTENSIONS = {
        '.py', '.pyc', '.pyo', '.pyx', '.pxd', '.so',   # source / compiled source
        '.zolo', '.yaml', '.yml', '.env',               # config / env (dotenv-style)
        '.key', '.pem', '.cert', '.crt', '.csr', '.p12', '.pfx',  # TLS material
        '.db', '.sqlite', '.sqlite3',                   # databases
    }

    @staticmethod
    def is_path_blocked(request_path: str) -> bool:
        """
        Check if request path is blocked for security reasons.

        Blocks: sensitive prefixes (BLOCKED_PATHS) AND any path containing a
        hidden segment (a path component starting with '.', e.g. '/.git/',
        '/.env', '/sub/.git/config'). The dotfile rule catches sensitive files
        nested under custom mounts that prefix matching would otherwise miss.

        Args:
            request_path: HTTP request path

        Returns:
            True if path is blocked, False if allowed
        """
        # Hidden / dotfile segment anywhere in the path (covers nested mounts).
        for segment in request_path.split('/'):
            if segment.startswith('.') and segment not in ('.', '..'):
                return True

        for blocked in SecurityChecker.BLOCKED_PATHS:
            if request_path.startswith(blocked):
                return True
        return False

    @staticmethod
    def is_blocked_extension(file_path: str) -> bool:
        """
        True if the file's extension is a source/secret type that must never
        be served as a static or mounted asset (e.g. /plugins/foo.py).

        Args:
            file_path: File path or URL path to inspect

        Returns:
            True if the extension is denylisted
        """
        return os.path.splitext(file_path)[1].lower() in SecurityChecker.BLOCKED_EXTENSIONS

    @staticmethod
    def is_path_safe(file_path: str, allowed_root: str) -> bool:
        """
        Prevent directory traversal attacks (SSOT containment check).

        Hardened over a naive ``abspath + startswith``:
          - ``realpath`` resolves symlinks, so a symlink INSIDE the root that
            points OUTSIDE it cannot escape (the old abspath kept the symlink path).
          - ``commonpath`` compares whole path components, so a sibling directory
            sharing a name prefix (``/srv/static`` vs ``/srv/static_secret``) is NOT
            treated as "inside" — the classic startswith() boundary bug.

        Args:
            file_path: File path to validate (may be relative; resolved here)
            allowed_root: Allowed root directory

        Returns:
            True if the resolved path is within allowed_root, False otherwise
        """
        real_file = os.path.realpath(file_path)
        real_root = os.path.realpath(allowed_root)
        try:
            return os.path.commonpath([real_file, real_root]) == real_root
        except ValueError:
            # Different drives (Windows) or mixed absolute/relative → not safe.
            return False
