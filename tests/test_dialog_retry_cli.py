"""zDialog retry: true — stay-armed on a RED onSubmit (zCLI)."""

from unittest.mock import MagicMock, patch

from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_ZMODE
from zOS.L2_Handling.j_zDialog.dialog_modules.dialog_constants import flag_on
from zOS.L2_Handling.j_zDialog.dialog_modules.submit_result import submit_failed
from zOS.L2_Handling.j_zDialog.zDialog import zDialog
from zOS.zVocabulary import ZMODE_ZBIFROST

_SUBMIT = {"zData": {"action": "insert"}}


def test_flag_on_truthy_spellings():
    assert flag_on(True) is True
    for spelling in ("true", "YES", "1", "on"):
        assert flag_on(spelling) is True
    assert flag_on(False) is False
    assert flag_on("false") is False
    assert flag_on(None) is False
    assert flag_on("") is False


def test_submit_failed_red_is_retryable():
    assert submit_failed(_SUBMIT, False) is True


def test_submit_failed_green_is_not_retryable():
    assert submit_failed(_SUBMIT, True) is False


def test_submit_failed_hop_is_a_leave():
    assert submit_failed(_SUBMIT, "navigate") is False
    assert submit_failed(_SUBMIT, {"zDelta": "$zPlanner"}) is False


def _dialog(session=None):
    zcli = MagicMock()
    zcli.session = session if session is not None else {}
    zcli.logger = MagicMock()
    zcli.display = MagicMock()
    zcli.zparser = MagicMock()
    return zDialog(zcli, walker=MagicMock())


def _spec(*, retry=True):
    dialog = {
        "title": "Add",
        "fields": [{"zConv": "name", "type": "text"}],
        "onSubmit": _SUBMIT,
    }
    if retry:
        dialog["retry"] = True
    return {"zDialog": dialog}


def test_retry_yes_recollects_then_succeeds():
    dlg = _dialog()
    dlg.display.zDialog.side_effect = [{"name": "bad"}, {"name": "good"}]
    dlg.display.button.return_value = True
    with patch(
        "zOS.L2_Handling.j_zDialog.zDialog.handle_submit",
        side_effect=[False, True],
    ) as hs, patch(
        "zOS.L2_Handling.j_zDialog.zDialog.dispatch_onsuccess_followup",
        return_value="navigate",
    ) as follow:
        assert dlg.handle(_spec()) == "navigate"
    assert dlg.display.zDialog.call_count == 2
    assert dlg.display.button.call_count == 1
    assert hs.call_count == 2
    follow.assert_called_once()
    assert follow.call_args.args[2] is True


def test_retry_no_leaves():
    dlg = _dialog()
    dlg.display.zDialog.return_value = {"name": "bad"}
    dlg.display.button.return_value = False
    with patch(
        "zOS.L2_Handling.j_zDialog.zDialog.handle_submit",
        return_value=False,
    ) as hs, patch(
        "zOS.L2_Handling.j_zDialog.zDialog.dispatch_onsuccess_followup",
        return_value=False,
    ) as follow:
        assert dlg.handle(_spec()) is False
    assert dlg.display.zDialog.call_count == 1
    assert dlg.display.button.call_count == 1
    assert hs.call_count == 1
    follow.assert_called_once()


def test_absent_retry_returns_fail():
    dlg = _dialog()
    dlg.display.zDialog.return_value = {"name": "bad"}
    with patch(
        "zOS.L2_Handling.j_zDialog.zDialog.handle_submit",
        return_value=False,
    ) as hs, patch(
        "zOS.L2_Handling.j_zDialog.zDialog.dispatch_onsuccess_followup",
        return_value=False,
    ) as follow:
        assert dlg.handle(_spec(retry=False)) is False
    assert dlg.display.zDialog.call_count == 1
    assert hs.call_count == 1
    dlg.display.button.assert_not_called()
    follow.assert_called_once()


def test_retry_does_not_loop_websocket_payload():
    dlg = _dialog({SESSION_KEY_ZMODE: ZMODE_ZBIFROST})
    with patch(
        "zOS.L2_Handling.j_zDialog.zDialog.handle_submit",
        return_value=False,
    ) as hs, patch(
        "zOS.L2_Handling.j_zDialog.zDialog.dispatch_onsuccess_followup",
        return_value=False,
    ):
        assert dlg.handle(
            _spec(),
            context={"websocket_data": {"data": {"name": "dup"}}},
        ) is False
    assert hs.call_count == 1
    dlg.display.zDialog.assert_not_called()
    dlg.display.button.assert_not_called()
