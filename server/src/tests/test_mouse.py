import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from server.services import mouse


@pytest.fixture
def quartz(monkeypatch):
    def create_event(source, kind, position, button):
        return {"kind": kind, "position": position, "button": button}

    api = SimpleNamespace(
        kCGEventLeftMouseDown=1,
        kCGEventLeftMouseUp=2,
        kCGMouseButtonLeft=0,
        kCGMouseEventClickState=1,
        kCGHIDEventTap=0,
        CGEventCreate=Mock(return_value=object()),
        CGEventGetLocation=Mock(return_value=(-120.5, 340.25)),
        CGEventCreateMouseEvent=Mock(side_effect=create_event),
        CGEventSetIntegerValueField=Mock(
            side_effect=lambda event, field, value: event.update(count=value)
        ),
        CGEventPost=Mock(),
    )
    monkeypatch.setitem(sys.modules, "Quartz", api)
    monkeypatch.setattr(mouse.sys, "platform", "darwin")
    monkeypatch.setattr(mouse.time, "sleep", Mock())
    monkeypatch.setattr(mouse.pyautogui, "doubleClick", Mock())
    return api


def test_macos_double_click_has_native_counts_and_one_cursor_location(quartz):
    mouse.double_click()
    events = [call.args[1] for call in quartz.CGEventPost.call_args_list]
    assert [(e["kind"], e["count"]) for e in events] == [(1, 1), (2, 1), (1, 2), (2, 2)]
    assert all(e["position"] == (-120.5, 340.25) and e["button"] == 0 for e in events)
    assert all(call.args[0] == quartz.kCGHIDEventTap for call in quartz.CGEventPost.call_args_list)
    quartz.CGEventGetLocation.assert_called_once()
    mouse.time.sleep.assert_called_once_with(0.12)
    mouse.pyautogui.doubleClick.assert_not_called()


@pytest.mark.parametrize("failure", ["cursor", "down", "up"])
def test_macos_event_creation_failure_does_not_post_clicks(quartz, failure):
    if failure == "cursor":
        quartz.CGEventCreate.return_value = None
    else:
        quartz.CGEventCreateMouseEvent.side_effect = [None, {}] if failure == "down" else [{}, None]
    with pytest.raises(RuntimeError):
        mouse.double_click()
    quartz.CGEventPost.assert_not_called()


def test_macos_post_failure_still_releases_mouse(quartz):
    quartz.CGEventPost.side_effect = [RuntimeError("post failed"), None]
    with pytest.raises(RuntimeError, match="post failed"):
        mouse.double_click()
    assert [call.args[1]["kind"] for call in quartz.CGEventPost.call_args_list] == [1, 2]


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_other_platforms_keep_pyautogui_double_click(monkeypatch, platform):
    click = Mock()
    monkeypatch.setattr(mouse.sys, "platform", platform)
    monkeypatch.setattr(mouse.pyautogui, "doubleClick", click)
    mouse.double_click()
    click.assert_called_once_with(button="left", interval=0.12)


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires native macOS Quartz")
def test_native_quartz_event_fields_without_posting_to_desktop(monkeypatch):
    import Quartz

    events = []
    monkeypatch.setattr(Quartz, "CGEventPost", lambda tap, event: events.append(event))
    monkeypatch.setattr(mouse.time, "sleep", Mock())
    mouse.double_click()
    assert [Quartz.CGEventGetType(event) for event in events] == [
        Quartz.kCGEventLeftMouseDown,
        Quartz.kCGEventLeftMouseUp,
        Quartz.kCGEventLeftMouseDown,
        Quartz.kCGEventLeftMouseUp,
    ]
    assert [
        Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventClickState)
        for event in events
    ] == [1, 1, 2, 2]
    assert len({tuple(Quartz.CGEventGetLocation(event)) for event in events}) == 1
