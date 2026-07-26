"""zOS#48 — the parse cache must never hold an unexpanded %pattern tree.

THE BUG: the boot-time zAPI/RBAC sweep loads route files before the zLoom
pattern registry (zLoom/patterns/*.zolo) is readable. expand_components()
short-circuits on the empty registry and hands back the tree with its
%-pattern KEYS intact — and the loader cached that poisoned parse for the
whole server life (zCloud's Advanced page: "Eleven doors" grid empty after
every restart until a manual `z reload`).

THE FIX (two rails):
  • has_component_keys(tree) — KEY-position % is unambiguous grammar, so a
    surviving %-key IS the "expansion didn't happen" signal. The loader
    consults it at cache-fill time and skips cache.set for such trees; the
    first post-boot render re-parses with the registry ready and caches the
    good tree.
  • expand_components warns (instead of silence) when the registry is empty
    but %-keys exist — the "app has no patterns" fast path is no longer
    indistinguishable from the boot-order failure.
"""
import logging
from types import SimpleNamespace

from zOS.L3_Abstraction.n_zLoom.zLoom_modules.component_expand import (
    expand_components,
    has_component_keys,
)

log = logging.getLogger(__name__)


def _fake_zos():
    """Just enough zos for expand_components' logging rail."""
    return SimpleNamespace(logger=SimpleNamespace(framework=log))


# ── has_component_keys: the "don't cache" signal ────────────────────────────

def test_pattern_key_detected_at_any_depth():
    tree = {
        "Advanced": {
            "Doors": {
                "Grid": {"%doorCard": {"icon": "bi-gear", "title": "zLoom"}},
            },
        },
    }
    assert has_component_keys(tree) is True


def test_render_tokens_are_not_pattern_keys():
    # VALUE-position % (render tokens, dyes) must NOT trip the guard —
    # every normal page is full of these and must stay cacheable.
    tree = {
        "Page": {
            "Who": {"zText": {"content": "%session.zVisitor.id"}},
            "When": {"zText": {"content": "%item.created_at | date(YYYY-MM-DD)"}},
            "List": {"zList": {"source": "%data.hosting_requests"}},
        },
    }
    assert has_component_keys(tree) is False


def test_lists_are_walked():
    tree = {"Rows": [{"ok": 1}, {"%leafNav": {"active": "zSpark"}}]}
    assert has_component_keys(tree) is True


# ── expand_components: empty-registry behavior ──────────────────────────────

def test_empty_registry_returns_tree_untouched_with_pattern_keys():
    tree = {"Grid": {"%doorCard": {"title": "x"}}}
    out = expand_components(tree, _fake_zos(), registry={})
    assert out is tree                      # untouched (the documented fast path)
    assert has_component_keys(out) is True  # and still flagged uncacheable


def test_expansion_clears_the_guard():
    registry = {"doorCard": {"Card": {"zText": {"content": "%title"}}}}
    tree = {"Grid": {"%doorCard": {"title": "Eleven doors"}}}
    out = expand_components(tree, _fake_zos(), registry=registry)
    assert has_component_keys(out) is False
    assert out["Grid"]["Card"]["zText"]["content"] == "Eleven doors"


def test_unknown_component_stays_flagged():
    # Unknown names survive expansion (fail-open) — such trees re-parse per
    # load instead of freezing a broken render into the cache.
    registry = {"doorCard": {"Card": {}}}
    tree = {"Grid": {"%noSuchPattern": {"title": "x"}}}
    out = expand_components(tree, _fake_zos(), registry=registry)
    assert has_component_keys(out) is True
