# zOS/core/L4_Orchestration/r_zServer/zServer_modules/rendering/default_templates.py

"""
Built-in default zVaF.html (SSOT fallback for the zWalker/template render paths).

Philosophy (mirrors error_pages.py):
    - "Just Works" — no templates/zVaF.html required to boot a Bifrost app
    - Override-able — drop templates/zVaF.html in the app dir and it wins, always
    - Convention — physical file beats built-in, same rule as zViews/error/zUI.<code>

The bifrost-client <script> src is resolved through the SAME `_bifrost_client_base()`
SSOT the CSS cascade already uses (html_injectors._inject_zui_head), so the CDN↔local
dev/prod switch is a single ZBIFROST_CLIENT_BASE env var — no per-app template edits.
"""

from jinja2 import Environment, TemplateNotFound

from ..routing.html_injectors import _bifrost_client_base

# `{{ title }}` is left as literal Jinja syntax (plain string, not an f-string) so the
# shared render pipeline (_finalize_page → _inject_title) can stamp it exactly like a
# physical template. Only the bifrost-client base is resolved ahead of time in Python.
_DEFAULT_ZVAF_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
</head>
<body>
    <!-- Built-in default chrome (no templates/zVaF.html found in the app dir).
         Drop templates/zVaF.html in your app to override this — it always wins. -->
    <zVaF></zVaF>

    <script src="%(bifrost_base)s/bifrost_client.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            window.bifrostClient = new BifrostClient({});
        });
    </script>
</body>
</html>
"""


def get_default_zvaf_html() -> str:
    """Build the built-in zVaF.html source (Jinja text, `{{ title }}` unresolved).

    Resolved at CALL time (not import time) so a dev-mode ZBIFROST_CLIENT_BASE
    set later in boot (zEnv loads into os.environ after import) still applies.
    """
    return _DEFAULT_ZVAF_HTML_TEMPLATE % {"bifrost_base": _bifrost_client_base()}


def render_zvaf(templates_dir: str, template_name: str, context: dict, logger=None) -> str:
    """Render `template_name` from `templates_dir`, falling back to the built-in
    default on TemplateNotFound (SSOT for both the `template` and `zWalker` route
    handlers in page_route_handlers — the only place this fallback should live).

    Physical file always wins; the built-in default is a silent-to-the-visitor,
    loud-to-the-operator fallback (INFO log, never an error).
    """
    from jinja2 import FileSystemLoader

    # Custom templates get the same client-base SSOT the built-in chrome uses:
    # write `{{ bifrost_base }}/bifrost_client.js` — never hardcode a mount path.
    context = {**context, "bifrost_base": _bifrost_client_base()}

    env = Environment(loader=FileSystemLoader(templates_dir))
    try:
        template = env.get_template(template_name)
        return template.render(**context)
    except TemplateNotFound:
        if logger:
            logger.info(
                f"[RouteDispatcher] templates/{template_name} not found — "
                "using built-in default chrome (drop templates/zVaF.html in "
                "your app dir to customize head/meta/fonts)"
            )
        return Environment().from_string(get_default_zvaf_html()).render(**context)
