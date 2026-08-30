"""zBrand → navbar HTML seam tests (issue #67).

SPA navigation rebuilds the navbar server-side on every arrival. The builder
used to take ``brand`` as a plain string, so a rich zBrand (logo/icon) survived
only the first full-page load and reverted to bare zSpark.title text the moment
you clicked a navbar item. These pin the dict-or-string contract:

* rich dict  → <img class="zNavbar-brand-logo"> + label + navigate attrs
* string     → legacy text-only brand (label shorthand)
* icon-only  → Bootstrap Icons <i>, no <img>
* None       → no brand element at all
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from L4_Orchestration.r_zServer.zServer_modules.routing.nav_html_builder import (  # noqa: E402
    build_nav_html,
)

ITEMS = ["zHome", "zAbout"]


class TestNavHtmlBrand(unittest.TestCase):
    """build_nav_html(brand=...) accepts the zBrand dict AND the string shorthand."""

    def test_rich_dict_renders_logo_label_and_navigate_attrs(self):
        html = build_nav_html(
            ITEMS,
            brand={
                "label": "Chevra Kadisha",
                "icon": "house",
                "logo": "/static/brand/logo.png",
                "href": "/",
            },
        )
        self.assertIn('<img src="/static/brand/logo.png"', html)
        self.assertIn('class="zNavbar-brand-logo"', html)
        self.assertIn('alt="Chevra Kadisha"', html)
        # Label always renders alongside the logo.
        self.assertIn("Chevra Kadisha</a>", html)
        # Logo wins over icon — no <i> glyph when both are declared.
        self.assertNotIn("zNavbar-brand-icon", html)
        # SPA nav, not a bare href — this is what survives client-side routing.
        self.assertIn('data-nav-action="navigate"', html)
        self.assertIn('data-nav-href="/"', html)

    def test_string_brand_keeps_legacy_text_form(self):
        html = build_nav_html(ITEMS, brand="zCloud")
        self.assertIn('class="zNavbar-brand"', html)
        self.assertIn(">zCloud</a>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("zNavbar-brand-icon", html)

    def test_logoless_dict_renders_bootstrap_icon(self):
        html = build_nav_html(
            ITEMS, brand={"label": "zCloud", "icon": "cloud", "logo": None}
        )
        self.assertIn('<i class="bi bi-cloud zNavbar-brand-icon"></i>', html)
        self.assertIn("zCloud</a>", html)
        self.assertNotIn("<img", html)

    def test_icon_accepts_bi_prefixed_value(self):
        html = build_nav_html(ITEMS, brand={"label": "zCloud", "icon": "bi-cloud"})
        self.assertIn('<i class="bi bi-cloud zNavbar-brand-icon"></i>', html)

    def test_custom_href_is_honored(self):
        html = build_nav_html(
            ITEMS, brand={"label": "Home", "logo": "/l.png", "href": "/zHome"}
        )
        self.assertIn('data-nav-href="/zHome"', html)
        self.assertIn('href="/zHome" class="zNavbar-brand"', html)

    def test_none_brand_renders_no_brand_element(self):
        html = build_nav_html(ITEMS, brand=None)
        self.assertNotIn("zNavbar-brand\"", html)
        self.assertNotIn("zNavbar-brand-logo", html)
        # The nav itself still renders.
        self.assertIn('class="zNavbar-nav"', html)

    def test_empty_dict_renders_no_brand_element(self):
        for empty in ({}, {"href": "/"}, {"label": None, "icon": None, "logo": None}):
            with self.subTest(brand=empty):
                html = build_nav_html(ITEMS, brand=empty)
                self.assertNotIn("zNavbar-brand-logo", html)
                self.assertNotIn('class="zNavbar-brand"', html)

    def test_brand_values_are_escaped(self):
        html = build_nav_html(
            ITEMS, brand={"label": '<script>"x"', "logo": '/a.png"><b>'}
        )
        self.assertNotIn("<script>", html)
        self.assertNotIn('/a.png"><b>', html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
