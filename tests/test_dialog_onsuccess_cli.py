"""zOS#128 — CLI zDialog fires sibling onSuccess after a GREEN submit."""

from unittest.mock import patch

from zOS.L2_Handling.j_zDialog.dialog_modules.dialog_submit import (
    dispatch_onsuccess_followup,
)


_SUBMIT = {"zData": {"action": "insert"}}
_SUCCESS = {"zDelta": "$zPlanner"}


def _follow(on_success, result, *, is_bifrost=False, session=None):
    return dispatch_onsuccess_followup(
        on_success,
        _SUBMIT,
        result,
        zos=object(),
        walker=object(),
        session=session,
        logger=None,
        is_bifrost=is_bifrost,
    )


def test_cli_green_dict_dispatches_and_replaces_return():
    with patch(
        "zOS.L2_Handling.j_zDialog.dialog_modules.dialog_submit.handle_zDispatch",
        return_value="navigate",
    ) as dispatch:
        assert _follow(_SUCCESS, True) == "navigate"
        dispatch.assert_called_once()
        assert dispatch.call_args.args[0] == "onSuccess"
        assert dispatch.call_args.args[1] == _SUCCESS


def test_cli_green_follow_none_keeps_submit_result():
    with patch(
        "zOS.L2_Handling.j_zDialog.dialog_modules.dialog_submit.handle_zDispatch",
        return_value=None,
    ):
        assert _follow(_SUCCESS, True) is True


def test_cli_red_does_not_dispatch():
    with patch(
        "zOS.L2_Handling.j_zDialog.dialog_modules.dialog_submit.handle_zDispatch",
    ) as dispatch:
        assert _follow(_SUCCESS, False) is False
        dispatch.assert_not_called()


def test_cli_string_call_is_ignored():
    with patch(
        "zOS.L2_Handling.j_zDialog.dialog_modules.dialog_submit.handle_zDispatch",
    ) as dispatch:
        assert _follow("zDelta($zPlanner)", True) is True
        dispatch.assert_not_called()


def test_bifrost_does_not_dispatch():
    with patch(
        "zOS.L2_Handling.j_zDialog.dialog_modules.dialog_submit.handle_zDispatch",
    ) as dispatch:
        assert _follow(_SUCCESS, True, is_bifrost=True) is True
        dispatch.assert_not_called()
