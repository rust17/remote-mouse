import struct
import sys
from unittest.mock import Mock, call, patch

import pytest

from server.core import protocol


@pytest.fixture
def mouse_input(monkeypatch):
    monkeypatch.setattr(protocol, "_left_button_held", False)
    mouse = Mock()
    for name in ("moveRel", "dragRel", "mouseDown", "mouseUp"):
        monkeypatch.setattr(protocol.pyautogui, name, getattr(mouse, name))
    return mouse


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
def test_drag_moves_keep_button_held_until_release(mouse_input, monkeypatch, platform):
    monkeypatch.setattr(protocol.sys, "platform", platform)
    move = struct.pack(">Bhh", protocol.OP_MOVE, 10, -5)
    assert protocol.process_binary_command(move) is True
    assert protocol.process_binary_command(bytes([protocol.OP_DRAG, 1])) is True
    assert protocol.process_binary_command(move) is True
    assert protocol.process_binary_command(move) is True
    assert protocol.process_binary_command(bytes([protocol.OP_DRAG, 0])) is True
    assert protocol.process_binary_command(move) is True
    assert mouse_input.mock_calls == [
        call.moveRel(10, -5),
        call.mouseDown(button="left"),
        call.dragRel(10, -5, button="left", mouseDownUp=False),
        call.dragRel(10, -5, button="left", mouseDownUp=False),
        call.mouseUp(button="left"),
        call.moveRel(10, -5),
    ]


def test_failed_release_keeps_dragging_until_cleanup_succeeds(mouse_input):
    move = struct.pack(">Bhh", protocol.OP_MOVE, 10, -5)
    assert protocol.process_binary_command(bytes([protocol.OP_DRAG, 1])) is True
    mouse_input.mouseUp.side_effect = [RuntimeError("release failed"), None]
    assert protocol.process_binary_command(bytes([protocol.OP_DRAG, 0])) is False
    assert protocol.process_binary_command(move) is True
    mouse_input.dragRel.assert_called_once_with(10, -5, button="left", mouseDownUp=False)
    assert protocol.process_binary_command(bytes([protocol.OP_DRAG, 0])) is True
    assert protocol.process_binary_command(move) is True
    mouse_input.moveRel.assert_called_once_with(10, -5)


def test_failed_press_retains_state_until_cleanup(mouse_input):
    mouse_input.mouseDown.side_effect = RuntimeError("press failed")
    assert protocol.process_binary_command(bytes([protocol.OP_DRAG, 1])) is False
    assert protocol._left_button_held is True
    assert protocol.process_binary_command(bytes([protocol.OP_DRAG, 0])) is True
    assert protocol._left_button_held is False


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires native macOS Quartz")
def test_drag_packets_produce_native_drag_events_without_posting_to_desktop(monkeypatch):
    import Quartz

    monkeypatch.setattr(protocol, "_left_button_held", False)
    monkeypatch.setattr(protocol.pyautogui, "mouseDown", Mock())
    monkeypatch.setattr(protocol.pyautogui, "mouseUp", Mock())
    monkeypatch.setattr(protocol.pyautogui, "position", lambda: (100, 100))
    monkeypatch.setattr(protocol.pyautogui.platformModule, "_position", lambda: (100, 100))
    monkeypatch.setattr(protocol.pyautogui, "DARWIN_CATCH_UP_TIME", 0)
    events = []
    monkeypatch.setattr(Quartz, "CGEventPost", lambda tap, event: events.append(event))
    move = struct.pack(">Bhh", protocol.OP_MOVE, 10, -5)
    for packet in (
        move,
        bytes([protocol.OP_DRAG, 1]),
        move,
        move,
        bytes([protocol.OP_DRAG, 0]),
        move,
    ):
        assert protocol.process_binary_command(packet) is True

    assert [Quartz.CGEventGetType(event) for event in events] == [
        Quartz.kCGEventMouseMoved,
        Quartz.kCGEventLeftMouseDragged,
        Quartz.kCGEventLeftMouseDragged,
        Quartz.kCGEventMouseMoved,
    ]
    assert all(tuple(Quartz.CGEventGetLocation(event)) == (110, 95) for event in events)
    protocol.pyautogui.mouseDown.assert_called_once_with(button="left")
    protocol.pyautogui.mouseUp.assert_called_once_with(button="left")


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
