# zOS/tests/test_zlist_position.py
"""zOS#50 — zList rows weave at their DECLARED position, and several lists
coexist on one block.

Before the fix, ``_expand_zlist_into`` appended woven ``zListItem__N`` keys at
the parent dict's tail ("list above a details panel" rendered below it), and
``shuttle_expand``'s ``out.update({"zList": ...})`` silently overwrote a
sibling authored ``zList`` (the "second list kills the page" shape).
"""

import unittest

from zOS.L3_Abstraction.n_zLoom.zLoom_modules.loop_ops import LoopOps
from zOS.L3_Abstraction.n_zLoom.zLoom_modules.shuttle_expand import expand_shuttles
from zOS.L3_Abstraction.n_zLoom.zLoom_modules.token_resolver import LOOP_FRAME_KEY


class _Loop(LoopOps):
    """LoopOps isolated from the facade: minimal source lookup + %item binding."""

    def __init__(self):
        self.zos = None

    def _lookup_list_source(self, src, data):
        return data.get(src.replace('%data.', ''), None)

    def _row_passes_gate(self, gate, ctx):
        return True

    def _prune_denied_subtrees(self, node, ctx):
        pass

    def _resolve_item_tokens(self, node, ctx):
        import copy
        frame = {}
        stack = ctx.get(LOOP_FRAME_KEY) if isinstance(ctx, dict) else None
        if isinstance(stack, list) and stack:
            frame = stack[-1]

        def bind(v):
            if isinstance(v, str):
                for k, val in frame.items():
                    v = v.replace(f"%item.{k}", str(val))
                return v
            if isinstance(v, dict):
                return {k: bind(x) for k, x in v.items()}
            if isinstance(v, list):
                return [bind(x) for x in v]
            return v
        return bind(copy.deepcopy(node))


class _WarnLog:
    def __init__(self):
        self.messages = []

    def warning(self, msg):
        self.messages.append(msg)


class _Zos:
    def __init__(self):
        self.logger = type('L', (), {})()
        self.logger.framework = _WarnLog()


class TestPositionalWeave(unittest.TestCase):
    """Rows land where the directive was declared — not at the dict tail."""

    def setUp(self):
        self.loop = _Loop()
        self.data = {'items': [{'name': 'A'}, {'name': 'B'}]}

    def test_rows_between_siblings(self):
        block = {
            'zH1': 'Top',
            'zList': {'source': '%data.items', 'each': {'zText': '%item.name'}},
            'Panel': {'zText': 'details'},
        }
        self.loop.expand_list_bindings(block, self.data, {})
        keys = list(block.keys())
        self.assertEqual(
            keys,
            ['zH1', '__zListSource', 'zListItem__0', 'zListItem__1', 'Panel'],
        )
        self.assertEqual(block['zListItem__0'], {'zText': 'A'})
        self.assertEqual(block['zListItem__1'], {'zText': 'B'})

    def test_revisit_reweaves_in_place(self):
        block = {
            'zH1': 'Top',
            'zList': {'source': '%data.items', 'each': {'zText': '%item.name'}},
            'Panel': {'zText': 'details'},
        }
        self.loop.expand_list_bindings(block, self.data, {})
        self.data['items'].append({'name': 'C'})
        self.loop.expand_list_bindings(block, self.data, {})
        keys = list(block.keys())
        self.assertEqual(
            keys,
            ['zH1', '__zListSource', 'zListItem__0', 'zListItem__1',
             'zListItem__2', 'Panel'],
        )
        self.assertEqual(block['zListItem__2'], {'zText': 'C'})

    def test_empty_source_keeps_position_for_stash(self):
        block = {
            'zH1': 'Top',
            'zList': {'source': '%data.missing', 'each': {'zText': '%item.name'}},
            'Panel': {'zText': 'details'},
        }
        self.loop.expand_list_bindings(block, self.data, {})
        self.assertEqual(list(block.keys()), ['zH1', '__zListSource', 'Panel'])


class TestTwoListsOneBlock(unittest.TestCase):
    """A second list (``zList__dupN``) weaves independently at its own spot."""

    def setUp(self):
        self.loop = _Loop()
        self.data = {
            'items': [{'name': 'A'}, {'name': 'B'}],
            'others': [{'name': 'X'}],
        }

    def test_both_lists_weave_at_their_positions(self):
        block = {
            'zH1': 'Top',
            'zList': {'source': '%data.items', 'each': {'zText': '%item.name'}},
            'Mid': {'zText': 'between'},
            'zList__dup2': {'source': '%data.others', 'each': {'zText': '%item.name'}},
        }
        self.loop.expand_list_bindings(block, self.data, {})
        self.assertEqual(
            list(block.keys()),
            ['zH1', '__zListSource', 'zListItem__0', 'zListItem__1',
             'Mid', '__zListSource__dup2', 'zListItem__dup2_0'],
        )
        self.assertEqual(block['zListItem__dup2_0'], {'zText': 'X'})

    def test_revisit_never_cross_cleans(self):
        block = {
            'zList': {'source': '%data.items', 'each': {'zText': '%item.name'}},
            'zList__dup2': {'source': '%data.others', 'each': {'zText': '%item.name'}},
        }
        self.loop.expand_list_bindings(block, self.data, {})
        # shrink the FIRST list only; second must survive its sibling's re-weave
        self.data['items'] = [{'name': 'A'}]
        self.loop.expand_list_bindings(block, self.data, {})
        self.assertEqual(
            list(block.keys()),
            ['__zListSource', 'zListItem__0',
             '__zListSource__dup2', 'zListItem__dup2_0'],
        )
        self.assertEqual(block['zListItem__0'], {'zText': 'A'})
        self.assertEqual(block['zListItem__dup2_0'], {'zText': 'X'})

    def test_row_ownership_predicate(self):
        self.assertTrue(_Loop._row_belongs('zListItem__0', ''))
        self.assertTrue(_Loop._row_belongs('zListItem__12', ''))
        self.assertFalse(_Loop._row_belongs('zListItem__dup2_0', ''))
        self.assertTrue(_Loop._row_belongs('zListItem__dup2_0', 'dup2'))
        self.assertFalse(_Loop._row_belongs('zListItem__0', 'dup2'))
        self.assertFalse(_Loop._row_belongs('Panel', ''))


class TestShuttleLoweringCollision(unittest.TestCase):
    """zShuttle no longer overwrites a sibling authored zList (zOS#50)."""

    def setUp(self):
        self.zos = _Zos()
        self.registry = {'card': {'zText': '%name'}}

    def test_shuttle_after_authored_zlist(self):
        tree = {'Main': {
            'zList': {'source': '%data.items', 'each': {'zText': '%item.name'}},
            'Sep': {'zText': 'divider'},
            'zShuttle': {'zSpool': 'others', 'zPattern': 'card'},
        }}
        out = expand_shuttles(tree, self.zos, self.registry)
        self.assertEqual(list(out['Main'].keys()), ['zList', 'Sep', 'zList__dup2'])
        self.assertEqual(out['Main']['zList__dup2']['source'], '%data.others')

    def test_shuttle_before_authored_zlist(self):
        tree = {'Main': {
            'zShuttle': {'zSpool': 'others', 'zPattern': 'card'},
            'zList': {'source': '%data.items', 'each': {'zText': '%item.name'}},
        }}
        out = expand_shuttles(tree, self.zos, self.registry)
        # authored zList keeps ITS key; the shuttle takes the suffixed one
        self.assertEqual(list(out['Main'].keys()), ['zList__dup2', 'zList'])
        self.assertEqual(out['Main']['zList']['source'], '%data.items')
        self.assertEqual(out['Main']['zList__dup2']['source'], '%data.others')

    def test_lone_shuttle_keeps_legacy_key(self):
        tree = {'Main': {'zShuttle': {'zSpool': 'others', 'zPattern': 'card'}}}
        out = expand_shuttles(tree, self.zos, self.registry)
        self.assertEqual(list(out['Main'].keys()), ['zList'])


class TestShuttleThenWeaveEndToEnd(unittest.TestCase):
    """Lowered shuttle + authored list, woven together: both render, in order."""

    def test_full_pipeline_order(self):
        zos = _Zos()
        registry = {'card': {'zText': '%name'}}
        tree = {'Main': {
            'zH1': 'Shop',
            'zList': {'source': '%data.items', 'each': {'zText': '%item.name'}},
            'Sep': {'zText': 'divider'},
            'zShuttle': {'zSpool': 'others', 'zPattern': 'card'},
            'Footer': {'zText': 'end'},
        }}
        lowered = expand_shuttles(tree, zos, registry)
        loop = _Loop()
        data = {'items': [{'name': 'A'}], 'others': [{'name': 'X'}, {'name': 'Y'}]}
        loop.expand_list_bindings(lowered['Main'], data, {})
        keys = [k for k in lowered['Main'] if not k.startswith('__zListSource')]
        self.assertEqual(
            keys,
            ['zH1', 'zListItem__0', 'Sep',
             'zListItem__dup2_0', 'zListItem__dup2_1', 'Footer'],
        )


if __name__ == '__main__':
    unittest.main()
