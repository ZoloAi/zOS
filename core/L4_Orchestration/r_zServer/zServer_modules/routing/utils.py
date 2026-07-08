# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/utils.py

"""
Handler Utilities - Helper functions for request handling

Handles:
- zPath to URL conversion
- zPath construction from zVaFolder + zVaFile (SSOT)
- Content-type guessing (SSOT)
- Route data resolution (Flask _data pattern)
- Common utilities shared across handlers
"""

import mimetypes

from ..utils.zserver_constants import FOLDER_UI

# zPath grammar — Layer-0 SSOT (aliased; this module has a local var named `zpath`).
from zSys import zpath as zpath_grammar

_DEFAULT_CONTENT_TYPE = "application/octet-stream"


class HandlerUtils:
    """Utility functions for HTTP request handling."""

    @staticmethod
    def build_zpath(zVaFolder: str, zVaFile: str) -> str:
        """
        Construct an absolute zPath from a route's zVaFolder + zVaFile (SSOT).

        Several handlers used to hand-roll
        ``'@.' + '.'.join(zVaFolder.lstrip('@.').split('.') + zVaFile.split('.'))``
        inline; this centralizes that one mapping so all routes resolve the same way.

        Example:
            zVaFolder="@.zViews", zVaFile="zUI.zAbout" → "@.zViews.zUI.zAbout"
        """
        return zpath_grammar.join(zpath_grammar.SIGIL_WORKSPACE, zVaFolder, zVaFile)

    @staticmethod
    def guess_content_type(file_path: str) -> str:
        """
        Guess a response Content-Type from a file path (SSOT for static serving).

        Returns ``application/octet-stream`` when the type can't be determined,
        so callers don't each re-implement the guess + fallback.
        """
        content_type, _ = mimetypes.guess_type(file_path)
        return content_type or _DEFAULT_CONTENT_TYPE

    @staticmethod
    def convert_zpath_to_url(zpath: str, ui_folder: str = FOLDER_UI) -> str:
        """
        Convert zOS zPath to URL path for client-side fetching.
        
        Args:
            zpath: zOS path, can be:
                - Absolute: "@.UI.zUI.index.zVaF" (workspace/UI/zUI.index.zolo)
                - Relative: "zUI.index.zVaF" (assumes UI folder)
            ui_folder: UI folder name (default: "UI")
        
        Returns:
            str: URL path like "/UI/zUI.index.zolo" (or .yaml for legacy files)
        
        Note:
            The UI folder prefix is stripped since /UI/* already maps to UI/ folder.
            Dots in filenames are preserved. Supports .zolo, .yaml, .json formats.
        """
        original_path = zpath

        # Remove @ prefix (absolute path marker) via the grammar SSOT.
        if zpath.startswith(zpath_grammar.SIGIL_WORKSPACE):
            zpath = zpath_grammar.strip_symbol(zpath)

        # Remove .zVaF suffix if present
        if zpath.endswith(".zVaF"):
            zpath = zpath[:-5]

        # Strip UI folder prefix if present (since /UI/* already maps to UI/)
        # Handles: "UI.zUI.index" or "UI/zUI.index"
        if zpath.startswith(f"{ui_folder}."):
            zpath = zpath[len(ui_folder)+1:]  # Remove "UI."
        elif zpath.startswith(f"{ui_folder}/"):
            zpath = zpath[len(ui_folder)+1:]  # Remove "UI/"

        # Add extension if not present (supports .zolo, .yaml, .json)
        # Note: This maintains backward compatibility while supporting new formats
        if not any(zpath.endswith(ext) for ext in ['.zolo', '.yaml', '.json', '.yml']):
            # Default to .yaml for backward compatibility
            # In production, client should request the actual extension or
            # server should use extension detection via zParser
            zpath += ".yaml"

        # Build URL path (dots are preserved as part of filename)
        # Use actual ui_folder name for URL (case-sensitive)
        url_path = f"/{ui_folder}/{zpath}"

        return url_path

    @staticmethod
    def resolve_route_data(data_block: dict, zos: any, logger: any = None) -> dict:
        """
        Execute data queries defined in a route's _data block (Flask pattern).

        This is the route-level equivalent of Flask's:
            @app.route('/account')
            def account():
                user = User.query.filter_by(email=session['email']).first()
                return render_template('account.html', user=user)

        Delegates entirely to ``zos.zloom.resolve_block_data`` — the SAME
        orchestrator dispatch/zDash use for a block's ``zMeta.zSpool`` reads —
        so a route-level query and a block-level query never drift (same 3
        supported forms, same %session/%route interpolation, same silent-mode
        + limit=1 unwrap, same `fields` whitelist).

        Args:
            data_block: _data section from route definition
            zos: zOS instance for data access
            logger: Optional logger instance

        Returns:
            Dictionary of query results: {"user": {...}, "stats": [...]}

        Examples:
            # In zServer.routes.yaml:
            routes:
              "/account":
                _data:
                  user: "@.models.zSchema.contacts"  # Model reference
                  # OR
                  stats:
                    zData:  # Explicit query
                      action: read
                      model: "@.models.zSchema.user_stats"
        """
        if not zos or not hasattr(zos, "zloom"):
            if logger:
                logger.warning("[HandlerUtils] No zOS/zLoom instance - cannot resolve _data")
            return {}
        return zos.zloom.resolve_block_data(data_block, {})
