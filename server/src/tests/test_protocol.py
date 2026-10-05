from unittest.mock import patch

import pytest
from server.core import protocol


@pytest.mark.parametrize(
    ("platform", "modifier"), [("darwin", "command"), ("win32", "ctrl"), ("linux", "ctrl")]
)
def test_select_all_uses_controlled_computer_platform(platform, modifier):
    with (
        patch.object(protocol.sys, "platform", platform),
        patch.object(protocol.pyautogui, "hotkey") as hotkey,
        patch.object(protocol.pyautogui, "press") as press,
    ):
        protocol.process_binary_command(bytes([protocol.OP_KEY_ACTION, 0]) + b"select_all")

    hotkey.assert_called_once_with(modifier, "a")
    press.assert_not_called()


def test_regular_key_keeps_existing_modifier_behavior():
    with (
        patch.object(protocol.pyautogui, "hold") as hold,
        patch.object(protocol.pyautogui, "press") as press,
        patch.object(protocol.pyautogui, "hotkey") as hotkey,
    ):
        protocol.process_binary_command(bytes([protocol.OP_KEY_ACTION, 3]) + b"enter")

    assert [call.args for call in hold.call_args_list] == [("ctrl",), ("shift",)]
    press.assert_called_once_with("enter")
    hotkey.assert_not_called()
