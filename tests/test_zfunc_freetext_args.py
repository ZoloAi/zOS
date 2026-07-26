"""Free text in zFunc call strings must round-trip verbatim (2026-07-26).

THE BUG (root-caused in zCloud's newsletter, re-bitten by the alpha request
dialogs): dialog_context.inject_placeholders spliced string zConv values into
an onSubmit "&.plugin.fn(zConv.field)" string as f"'{value}'" — zero escaping.
An apostrophe closed the quote, a newline broke the ^...$ invocation regex,
and the whole submit died with "Invalid plugin invocation syntax".

THE FIX: inside plugin invocation host strings ('&' sigil) string values ride
as json.dumps literals — double-quoted, escaped, newline-free — and the arg
parser (smart_split_arguments / parse_argument_value) understands JSON string
tokens. Everything else (SQL-ish embedded strings, authored single-quoted
args) keeps its legacy behavior bit-for-bit.
"""
import logging

import pytest

from zOS.L2_Handling.j_zDialog.dialog_modules.dialog_context import inject_placeholders
from zOS.L2_Handling.d_zParser.parser_modules.plugin.plugin_syntax import parse_plugin_invocation
from zOS.L2_Handling.d_zParser.parser_modules.plugin.plugin_args import parse_plugin_arguments

log = logging.getLogger(__name__)

TEMPLATE = "&.subscription.request_free(zConv.building, zConv.heard, zConv.contact, zConv.note)"


def _round_trip(values):
    injected = inject_placeholders(TEMPLATE, {"zConv": dict(values)}, log)
    plugin, fn, args_str = parse_plugin_invocation(injected)
    assert (plugin, fn) == ("subscription", "request_free")
    args, kwargs = parse_plugin_arguments(args_str)
    assert kwargs == {}
    return args


def test_hostile_prose_round_trips_verbatim():
    values = {
        "building": "I'm building a recipe app\nfor my mom (v1) — she types, it \"cooks\"",
        "heard": "a friend's demo, at Dedi's — don't blink",
        "contact": "maya+alpha@example.com",
        "note": "back\\slash & 'nested' quotes, commas, ()",
    }
    assert _round_trip(values) == [
        values["building"], values["heard"], values["contact"], values["note"],
    ]


def test_empty_optionals_survive():
    values = {"building": "plain text", "heard": "x", "contact": "", "note": ""}
    assert _round_trip(values) == ["plain text", "x", "", ""]


def test_legacy_authored_args_unchanged():
    args, kwargs = parse_plugin_arguments(
        "'Alice', \"Hello, World\", 42, active=True, note='x'"
    )
    assert args == ["Alice", "Hello, World", 42]
    assert kwargs == {"active": True, "note": "x"}


def test_non_plugin_hosts_keep_single_quote_splice():
    sql = inject_placeholders(
        "WHERE name = zConv.name", {"zConv": {"name": "Alice"}}, log
    )
    assert sql == "WHERE name = 'Alice'"


def test_raw_backslash_double_quoted_token_falls_back():
    # Authored (non-JSON) double-quoted arg with an invalid JSON escape
    # (\z is not a JSON escape): json.loads fails, legacy strip-the-quotes
    # behavior must preserve the raw text.
    args, _ = parse_plugin_arguments('"C:\\zpath"')
    assert args == ["C:\\zpath"]
