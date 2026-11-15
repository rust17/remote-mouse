import ctypes
import struct
import sys
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest

from server.core import protocol
from server.services import mouse


@pytest.fixture
def mouse_input(monkeypatch):
    monkeypatch.setattr(protocol, "_left_button_held", False)
    mouse = Mock()
    for name in ("moveRel", "dragRel", "mouseDown", "mouseUp"):
        monkeypatch.setattr(protocol.pyautogui, name, getattr(mouse, name))
    return mouse


@pytest.fixture
def windows_mouse_api(monkeypatch):
    def cursor_info(pointer):
        cursor = ctypes.cast(pointer, ctypes.POINTER(mouse._CursorInfo)).contents
        assert cursor.size == (24 if ctypes.sizeof(ctypes.c_void_p) == 8 else 20)
        cursor.flags = api.cursor_flags
        return 1

    api = SimpleNamespace(cursor_flags=1, GetCursorInfo=Mock(side_effect=cursor_info))
    api.SendInput = Mock(return_value=1)
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=api), raising=False)
    return api


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
def test_drag_moves_keep_button_held_until_release(
    mouse_input, monkeypatch, platform, windows_mouse_api
):
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
    windows_mouse_api.SendInput.assert_not_called()


@pytest.mark.parametrize("flags", [0, 2])
def test_windows_hidden_cursor_receives_native_move_packet(
    mouse_input, monkeypatch, windows_mouse_api, flags
):
    def send_input(count, pointer, size):
        event = ctypes.cast(pointer, ctypes.POINTER(mouse._Input)).contents
        assert count == 1
        assert size == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
        assert event.type == 0
        assert (event.mouse.dx, event.mouse.dy, event.mouse.flags) == (10, -5, 1)
        return 1

    monkeypatch.setattr(protocol.sys, "platform", "win32")
    windows_mouse_api.cursor_flags = flags
    windows_mouse_api.SendInput.side_effect = send_input

    assert protocol.process_binary_command(struct.pack(">Bhh", protocol.OP_MOVE, 10, -5)) is True
    windows_mouse_api.SendInput.assert_called_once()
    mouse_input.moveRel.assert_not_called()


def test_windows_native_move_failure_falls_back_to_position_update(
    mouse_input, monkeypatch, windows_mouse_api
):
    monkeypatch.setattr(protocol.sys, "platform", "win32")
    windows_mouse_api.cursor_flags = 0
    windows_mouse_api.SendInput.return_value = 0

    assert protocol.process_binary_command(struct.pack(">Bhh", protocol.OP_MOVE, 10, -5)) is True
    windows_mouse_api.SendInput.assert_called_once()
    mouse_input.moveRel.assert_called_once_with(10, -5)


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
