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
        Execute data queries defined in route _data block (Flask pattern).
        
        This is the route-level equivalent of Flask's:
            @app.route('/account')
            def account():
                user = User.query.filter_by(email=session['email']).first()
                return render_template('account.html', user=user)
        
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
        results = {}

        if not zos:
            if logger:
                logger.warning("[HandlerUtils] No zOS instance - cannot resolve _data")
            return results

        for key, query_def in data_block.items():
            try:
                # Handle shorthand: user: "@.models.zSchema.contacts"
                if (isinstance(query_def, str)
                        and query_def.startswith(zpath_grammar.SIGIL_WORKSPACE)
                        and zpath_grammar.split(query_def).segments[:1] == ('models',)):
                    # Shorthand model reference - convert to zData request
                    # Auto-filter by authenticated user ID for security

                    # Get authenticated user ID from the single signed-in identity
                    user_id = zos.session.get('zVisitor', {}).get('id')

                    query_def = {
                        "zData": {
                            "action": "read",
                            "model": query_def,
                            "options": {
                                "where": f"id = {user_id}" if user_id else "1 = 0",  # Security: no ID = no results
                                "limit": 1
                            }
                        }
                    }

                # Handle explicit zData block
                if isinstance(query_def, dict) and "zData" in query_def:
                    # Execute zData query in SILENT mode (v1.5.12)
                    # Silent mode: returns rows without displaying, works in any zMode
                    query_def["zData"]["silent"] = True

                    result = zos.data.handle_request(query_def["zData"])

                    # Extract first record if limit=1 (single record query)
                    if isinstance(result, list) and query_def["zData"].get("options", {}).get("limit") == 1 and len(result) > 0:
                        results[key] = result[0]  # Return dict instead of list for single record
                    else:
                        results[key] = result

                    if logger:
                        result_type = type(results[key]).__name__
                        result_count = len(result) if isinstance(result, list) else 1
                        logger.debug(f"[HandlerUtils] Query '{key}' returned {result_type} ({result_count} records)")
                else:
                    if logger:
                        logger.warning(f"[HandlerUtils] Invalid _data entry: {key}")
                    results[key] = None

            except Exception as e:
                if logger:
                    logger.error(f"[HandlerUtils] Query '{key}' failed: {e}")
                results[key] = None

        return results
