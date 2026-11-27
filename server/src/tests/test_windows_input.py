"""Regression coverage for the privileged boundary without sending desktop input."""

import ctypes
import importlib
import struct
import sys
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from server.core import protocol
from server.windows import input as support


@pytest.mark.parametrize("data", [b"", b"\x01" * 64, bytes(8), support.packet(99)])
def test_service_rejects_unknown_or_malformed_messages(data):
    with pytest.raises(ValueError):
        support.decode(data)


@pytest.mark.parametrize(
    "data",
    [
        support.packet(support.CLICK, button=3),
        support.packet(support.DRAG, button=2),
        support.packet(support.CLICK, button=1, modifiers=16),
        support.packet(support.RELEASE, x=1),
        support.packet(support.MOVE, modifiers=1),
    ],
)
def test_service_rejects_invalid_command_fields(data):
    with pytest.raises(ValueError):
        support.decode(data)


def test_service_preserves_signed_coordinates_and_modifiers():
    assert support.decode(support.packet(support.MOVE, x=-32768, y=32767)) == (
        support.MOVE,
        -32768,
        32767,
        0,
        0,
    )
    assert support.decode(support.packet(support.CLICK, button=2, modifiers=15)) == (
        support.CLICK,
        0,
        0,
        2,
        15,
    )


@pytest.mark.parametrize("result", [True, False])
def test_uac_click_is_never_replayed_by_ordinary_backend(monkeypatch, result):
    route, click = Mock(return_value=result), Mock()
    monkeypatch.setattr(support, "route", route)
    monkeypatch.setattr(protocol.pyautogui, "click", click)
    assert protocol.process_binary_command(bytes((protocol.OP_CLICK, 2, 3))) is result
    route.assert_called_once_with(support.CLICK, button=2, modifiers=3)
    click.assert_not_called()


@pytest.fixture
def fake_native(monkeypatch):
    import server.windows

    monkeypatch.setattr(support, "_secure_input_active", False)
    monkeypatch.setattr(support, "_ordinary_drag", False)

    api = SimpleNamespace(
        c=ctypes,
        PTR=ctypes.c_void_p,
        DWORD=ctypes.c_uint32,
        SYSTEM_SID="S-1-5-18",
        foreground_elevated=Mock(return_value=False),
        bind=lambda *args: Mock(),
        GetThreadDesktop=Mock(return_value=10),
        GetCurrentThreadId=Mock(return_value=1),
        OpenInputDesktop=Mock(return_value=20),
        CloseDesktop=Mock(),
        SetThreadDesktop=Mock(return_value=True),
        check=lambda value: value if value else (_ for _ in ()).throw(OSError("Win32 failed")),
    )

    def desktop_name(desktop, kind, text, size, needed):
        text.value = "Default"
        return True

    api.GetUserObjectInformation = Mock(side_effect=desktop_name)
    monkeypatch.setitem(sys.modules, "server.windows.native", api)
    monkeypatch.setattr(server.windows, "native", api, raising=False)
    return api


def test_default_desktop_keeps_original_input_backend(monkeypatch, fake_native):
    monkeypatch.setattr(support.sys, "platform", "win32")
    request = Mock()
    monkeypatch.setattr(support.client, "request", request)
    assert support.route(support.MOVE, x=12, y=-3) is None
    request.assert_not_called()
    fake_native.CloseDesktop.assert_called_once_with(20)


def test_secure_move_uses_virtual_screen_pixels_without_acceleration(
    monkeypatch, worker, fake_native
):
    desktop = worker.DesktopMouse()
    desktop.name = "Winlogon"
    monkeypatch.setattr(desktop, "refresh", Mock())
    monkeypatch.setattr(desktop, "consent", lambda: True)
    send = Mock()
    monkeypatch.setattr(desktop, "send", send)

    def position(pointer):
        point = ctypes.cast(pointer, ctypes.POINTER(worker.w.POINT)).contents
        point.x, point.y = -100, 50
        return True

    dimensions = {76: -1920, 77: 0, 78: 3840, 79: 1080}
    fake_native.bind = (
        lambda dll, name, *args: position if name == "GetCursorPos" else dimensions.get
    )
    assert desktop.execute(support.packet(support.MOVE, x=10, y=-100)) == support.HANDLED
    event = send.call_args.args[0][0].mouse
    assert event.flags == 0xC001
    assert event.dx == (1830 * 65536 + 32768) // 3840
    assert event.dy == 32768 // 1080


def test_inaccessible_secure_desktop_uses_service_without_fallback(monkeypatch, fake_native):
    monkeypatch.setattr(support.sys, "platform", "win32")
    fake_native.OpenInputDesktop.return_value = None
    request = Mock(return_value=support.FAILED)
    monkeypatch.setattr(support.client, "request", request)
    assert support.route(support.CLICK, button=1) is False
    request.assert_called_once_with(support.packet(support.CLICK, button=1))


@pytest.fixture
def worker(monkeypatch, fake_native):
    monkeypatch.delitem(sys.modules, "server.windows.worker", raising=False)
    module = importlib.import_module("server.windows.worker")
    yield module
    sys.modules.pop("server.windows.worker", None)
    import server.windows

    delattr(server.windows, "worker")


def test_uac_disappearing_between_double_clicks_stops_second_click(monkeypatch, worker):
    desktop = worker.DesktopMouse()
    monkeypatch.setattr(desktop, "refresh", Mock())
    desktop.name = "Winlogon"
    monkeypatch.setattr(desktop, "consent", Mock(side_effect=[True, True, False]))
    send = Mock()
    monkeypatch.setattr(desktop, "send", send)
    monkeypatch.setattr(worker.time, "sleep", Mock())
    assert desktop.execute(support.packet(support.DOUBLE_CLICK)) == support.FAILED
    assert send.call_count == 1
    assert desktop.held == []


def test_partial_click_failure_still_releases_modifiers_and_button(monkeypatch, worker):
    desktop = worker.DesktopMouse()
    desktop.name = "Winlogon"
    monkeypatch.setattr(desktop, "refresh", Mock())
    monkeypatch.setattr(desktop, "consent", Mock(return_value=True))
    send = Mock(side_effect=[None, OSError("partial send"), None])
    monkeypatch.setattr(desktop, "send", send)
    with pytest.raises(OSError, match="partial send"):
        desktop.execute(support.packet(support.CLICK, button=1, modifiers=1))
    assert send.call_count == 3
    assert len(send.call_args.args[0]) == 2
    assert desktop.held == []


def test_lock_screen_rejects_input(monkeypatch, worker):
    desktop = worker.DesktopMouse()
    desktop.name = "Winlogon"
    monkeypatch.setattr(desktop, "refresh", Mock())
    monkeypatch.setattr(desktop, "consent", Mock(return_value=False))
    send = Mock()
    monkeypatch.setattr(desktop, "send", send)
    assert desktop.execute(support.packet(support.MOVE, x=1)) == support.FAILED
    send.assert_not_called()


def test_release_keeps_pending_state_if_windows_rejects_it(monkeypatch, worker):
    desktop = worker.DesktopMouse()
    desktop.held = [worker.mouse(4)]
    monkeypatch.setattr(desktop, "send", Mock(side_effect=OSError("rejected")))
    with pytest.raises(OSError):
        desktop.release()
    assert len(desktop.held) == 1


def test_pipe_client_identity_must_match_registration(monkeypatch, worker, fake_native):
    fake_native.GetNamedPipeClientProcessId = Mock(return_value=True)
    fake_native.ImpersonateNamedPipeClient = Mock(return_value=True)
    fake_native.OpenThreadToken = Mock(return_value=True)
    fake_native.GetCurrentThread = Mock()
    fake_native.token_sid = Mock(return_value="another-user")
    fake_native.handle = lambda value: nullcontext(value)
    fake_native.RevertToSelf = Mock(return_value=True)
    assert worker.authorized(1, {"sid": "registered-user"}) is False
    fake_native.RevertToSelf.assert_called_once()


def test_drag_route_retains_ownership_for_release(monkeypatch):
    monkeypatch.setattr(protocol, "_left_button_held", False)
    monkeypatch.setattr(support, "route", Mock(return_value=True))
    assert protocol.process_binary_command(bytes((protocol.OP_DRAG, 1)))
    assert protocol._left_button_held
    assert protocol.process_binary_command(struct.pack(">Bhh", protocol.OP_MOVE, 20, -10))
    assert protocol.process_binary_command(bytes((protocol.OP_DRAG, 0)))
    assert not protocol._left_button_held


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows ABI check")
def test_native_windows_structures_without_sending_input():
    from server.windows import native, worker
    from server.windows.service import ProcessInfo, StartupInfo
    from server.windows.transport import Overlapped

    assert ctypes.sizeof(worker.Input) == 40
    assert ctypes.sizeof(StartupInfo) == 104
    assert ctypes.sizeof(ProcessInfo) == 24
    assert ctypes.sizeof(Overlapped) == 32
    assert native.process_sid().startswith("S-")
    assert native.session_id() >= 0


@pytest.fixture
def setup_manager(monkeypatch, fake_native, tmp_path, worker):
    from server.windows import manage

    directory = tmp_path / "protected"
    directory.mkdir()
    helper = tmp_path / "helper.exe"
    helper.write_bytes(b"new helper")
    app = tmp_path / "RemoteMouse.exe"
    app.write_bytes(b"client")
    fake_native.system_directory = lambda: tmp_path
    monkeypatch.setitem(sys.modules, "server.windows.service", SimpleNamespace(wait_stopped=Mock()))
    monkeypatch.setattr(manage, "install_directory", lambda sid: directory)
    monkeypatch.setattr(manage.sys, "executable", str(helper))
    monkeypatch.setattr(manage.subprocess, "run", Mock())
    calls = Mock(return_value=0)
    monkeypatch.setattr(manage, "sc", calls)
    return manage, directory, app, calls


def test_upgrade_rolls_back_helper_and_registration_if_start_fails(setup_manager):
    manage, directory, app, calls = setup_manager
    executable = directory / "RemoteMouseInput.exe"
    registration = directory / "registration.json"
    executable.write_bytes(b"old helper")
    registration.write_bytes(b"old registration")
    attempts = 0

    def sc(*args, **kwargs):
        nonlocal attempts
        if args[0] == "start":
            attempts += 1
            if attempts == 1:
                raise OSError("service start failed")
        return 0

    calls.side_effect = sc
    with pytest.raises(OSError, match="service start failed"):
        manage.install("S-1-5-21-1-2-3-1001", app)
    assert executable.read_bytes() == b"old helper"
    assert registration.read_bytes() == b"old registration"
    assert attempts == 2


def test_remove_stops_service_before_deleting_protected_files(setup_manager):
    manage, directory, app, calls = setup_manager
    (directory / "RemoteMouseInput.exe").write_bytes(b"helper")
    manage.remove("S-1-5-21-1-2-3-1001")
    assert [call.args[0] for call in calls.call_args_list] == ["query", "stop", "delete"]
    assert not directory.exists()


def test_upgrade_waits_for_bootloader_file_release(setup_manager, monkeypatch):
    manage, directory, app, calls = setup_manager
    executable = directory / "RemoteMouseInput.exe"
    executable.write_bytes(b"old helper")
    original_replace = manage.os.replace
    attempts = 0

    def replace(source, target):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("bootloader is exiting")
        original_replace(source, target)

    monkeypatch.setattr(manage.os, "replace", replace)
    monkeypatch.setattr(manage.time, "sleep", Mock())
    manage.install("S-1-5-21-1-2-3-1001", app)
    assert attempts == 2
    assert executable.read_bytes() == b"new helper"
    assert not (directory / "update.exe").exists()


def test_remove_waits_for_bootloader_file_release(setup_manager, monkeypatch):
    manage, directory, app, calls = setup_manager
    original_remove = manage.shutil.rmtree
    attempts = 0

    def remove(path):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("bootloader is exiting")
        original_remove(path)

    monkeypatch.setattr(manage.shutil, "rmtree", remove)
    monkeypatch.setattr(manage.time, "sleep", Mock())
    manage.remove("S-1-5-21-1-2-3-1001")
    assert attempts == 2
    assert not directory.exists()


def test_drag_crossing_to_uac_is_released_before_moving(monkeypatch, fake_native):
    monkeypatch.setattr(support.sys, "platform", "win32")
    monkeypatch.setattr(support, "_ordinary_drag", True)
    fake_native.OpenInputDesktop.return_value = None
    request = Mock(return_value=support.HANDLED)
    monkeypatch.setattr(support.client, "request", request)
    assert support.route(support.MOVE, x=5, y=6)
    assert [call.args[0] for call in request.call_args_list] == [
        support.packet(support.RELEASE),
        support.packet(support.MOVE, x=5, y=6),
    ]
    assert not support._ordinary_drag


def test_failed_cross_desktop_release_drops_move(monkeypatch, fake_native):
    monkeypatch.setattr(support.sys, "platform", "win32")
    monkeypatch.setattr(support, "_ordinary_drag", True)
    fake_native.OpenInputDesktop.return_value = None
    request = Mock(return_value=support.FAILED)
    monkeypatch.setattr(support.client, "request", request)
    assert support.route(support.MOVE, x=5) is False
    request.assert_called_once_with(support.packet(support.RELEASE))
    assert support._ordinary_drag


def test_desktop_switch_failure_preserves_pending_releases(monkeypatch, worker, fake_native):
    desktop = worker.DesktopMouse()
    desktop.name = "Winlogon"
    desktop.held = [worker.mouse(4)]
    monkeypatch.setattr(desktop, "send", Mock(side_effect=OSError("desktop inactive")))
    fake_native.SetThreadDesktop.return_value = False
    with pytest.raises(OSError):
        desktop.refresh()
    assert len(desktop.held) == 1
    assert desktop.name == "Winlogon"
    fake_native.CloseDesktop.assert_called_once_with(20)


def test_ordinary_client_authenticates_protected_helper_without_debug_privilege(
    monkeypatch, fake_native, tmp_path
):
    sid = "S-1-5-21-1-2-3-1001"
    fake_native.process_sid = Mock(return_value=sid)
    fake_native.CreateFile = Mock(return_value=1)
    fake_native.GetNamedPipeServerProcessId = Mock(return_value=True)
    fake_native.OpenProcess = Mock(return_value=2)
    fake_native.handle = lambda value: nullcontext(value)
    fake_native.session_id = Mock(return_value=1)
    fake_native.image_path = Mock(return_value=tmp_path / "RemoteMouseInput.exe")
    monkeypatch.setattr(support, "install_directory", lambda owner: tmp_path)
    transaction = Mock(return_value=bytes((support.VERSION, support.HANDLED)))
    monkeypatch.setitem(
        sys.modules, "server.windows.transport", SimpleNamespace(transact=transaction)
    )
    connection = support.Client()
    assert connection.request(support.packet(support.PING)) == support.HANDLED
    fake_native.process_sid.assert_called_once_with()
    assert connection.last_error is None


@pytest.mark.parametrize("acknowledgement", [support.HANDLED, support.FAILED])
def test_return_to_default_releases_helper_before_ordinary_input(
    monkeypatch, fake_native, acknowledgement
):
    monkeypatch.setattr(support.sys, "platform", "win32")
    monkeypatch.setattr(support, "_secure_input_active", True)
    monkeypatch.setattr(support, "_ordinary_drag", True)
    monkeypatch.setattr(support.client, "pipe", 42)
    calls = []
    monkeypatch.setattr(
        support.client, "request", lambda data: calls.append(("release", data)) or acknowledgement
    )
    monkeypatch.setattr(support.client, "close", lambda: calls.append(("close",)))
    monkeypatch.setattr(protocol, "_left_button_held", True)
    monkeypatch.setattr(protocol.pyautogui, "press", lambda key: calls.append(("key", key)))
    assert protocol.process_binary_command(bytes([protocol.OP_KEY_ACTION, 0]) + b"enter")
    assert calls == [("release", support.packet(support.RELEASE)), ("close",), ("key", "enter")]
    assert not protocol._left_button_held
    assert not support._secure_input_active
    assert not support._ordinary_drag
    assert not support.resume_ordinary()


def test_secure_desktop_does_not_resume_ordinary_input(monkeypatch, fake_native):
    monkeypatch.setattr(support.sys, "platform", "win32")
    monkeypatch.setattr(support, "_secure_input_active", True)
    fake_native.OpenInputDesktop.return_value = None
    release = Mock()
    monkeypatch.setattr(support, "disconnect", release)
    assert not support.resume_ordinary()
    assert support._secure_input_active
    release.assert_not_called()


def test_elevated_default_window_keeps_privileged_input(monkeypatch, fake_native):
    monkeypatch.setattr(support.sys, "platform", "win32")
    fake_native.foreground_elevated.return_value = True
    request = Mock(return_value=support.HANDLED)
    monkeypatch.setattr(support.client, "request", request)
    assert support.route(support.MOVE, x=10)
    request.assert_called_once_with(support.packet(support.MOVE, x=10))
    assert not support.resume_ordinary()


@pytest.mark.parametrize(
    "action,text", [(support.TEXT, "你好🙂"), (support.KEY, "enter"), (support.KEY, "select_all")]
)
def test_privileged_keyboard_packet_round_trip(action, text):
    assert support.decode(support.packet(action, text=text)) == (action, text, 0, 0, 0)


@pytest.mark.parametrize(
    "data",
    [
        bytes([support.VERSION, support.KEY, 0]) + b"run arbitrary command",
        support.packet(support.TEXT, text="x" * 4097),
        support.packet(support.TEXT, text="x", modifiers=1),
    ],
)
def test_privileged_keyboard_rejects_invalid_packets(data):
    with pytest.raises(ValueError):
        support.decode(data)


def test_keyboard_is_rejected_on_uac_desktop(monkeypatch, worker):
    desktop = worker.DesktopMouse()
    desktop.name = "Winlogon"
    monkeypatch.setattr(desktop, "refresh", Mock())
    monkeypatch.setattr(desktop, "consent", lambda: True)
    send = Mock()
    monkeypatch.setattr(desktop, "send", send)
    assert desktop.execute(support.packet(support.TEXT, text="hello")) == support.FAILED
    send.assert_not_called()


def test_elevated_unicode_input_uses_utf16_and_releases_state(monkeypatch, worker, fake_native):
    desktop = worker.DesktopMouse()
    desktop.name = "Default"
    monkeypatch.setattr(desktop, "refresh", Mock())
    fake_native.foreground_elevated.return_value = True
    send = Mock()
    monkeypatch.setattr(desktop, "send", send)
    assert desktop.execute(support.packet(support.TEXT, text="中🙂")) == support.HANDLED
    events = send.call_args.args[0]
    assert [event.keyboard.scan for event in events[::2]] == [0x4E2D, 0xD83D, 0xDE42]
    assert all(event.keyboard.flags == 6 for event in events[1::2])
    assert not desktop.held


def test_elevated_keyboard_failure_releases_modifiers(monkeypatch, worker, fake_native):
    desktop = worker.DesktopMouse()
    desktop.name = "Default"
    monkeypatch.setattr(desktop, "refresh", Mock())
    fake_native.foreground_elevated.return_value = True
    send = Mock(side_effect=[None, OSError("partial send"), None])
    monkeypatch.setattr(desktop, "send", send)
    with pytest.raises(OSError):
        desktop.execute(support.packet(support.KEY, text="enter", modifiers=1))
    assert not desktop.held
    assert [event.keyboard.key for event in send.call_args.args[0]] == [13, 17]


def test_ordinary_shortcut_releases_modifier_after_privileged_focus_change(
    monkeypatch, fake_native
):
    monkeypatch.setattr(support.sys, "platform", "win32")
    monkeypatch.setattr(support, "route", Mock(return_value=None))
    request = Mock(return_value=support.HANDLED)
    monkeypatch.setattr(support.client, "request", request)
    monkeypatch.setattr(protocol.pyautogui, "hold", lambda key: nullcontext())
    monkeypatch.setattr(
        protocol.pyautogui,
        "press",
        lambda key: setattr(fake_native.foreground_elevated, "return_value", True),
    )
    assert protocol.process_binary_command(bytes([protocol.OP_KEY_ACTION, 4]) + b"esc")
    request.assert_called_once_with(support.packet(support.RELEASE, modifiers=4))
    assert support._secure_input_active


def test_ordinary_modifier_cleanup_keeps_original_backend(monkeypatch, fake_native):
    monkeypatch.setattr(support.sys, "platform", "win32")
    request = Mock()
    monkeypatch.setattr(support.client, "request", request)
    with support.ordinary_modifiers(1):
        pass
    request.assert_not_called()


@pytest.mark.parametrize("secure", [False, True])
def test_modifier_cleanup_sends_only_requested_key_ups(monkeypatch, worker, secure):
    desktop = worker.DesktopMouse()
    desktop.name = "Winlogon" if secure else "Default"
    monkeypatch.setattr(desktop, "refresh", Mock())
    send = Mock()
    monkeypatch.setattr(desktop, "send", send)
    assert desktop.execute(support.packet(support.RELEASE, modifiers=5)) == support.HANDLED
    events = send.call_args.args[0]
    assert {(event.kind, event.keyboard.key, event.keyboard.flags) for event in events} == {
        (1, 0x11, 2),
        (1, 0x12, 2),
    }
    assert not desktop.held


def test_modifier_cleanup_failure_retains_pending_key_ups(monkeypatch, worker):
    desktop = worker.DesktopMouse()
    monkeypatch.setattr(desktop, "refresh", Mock())
    send = Mock(side_effect=[OSError("partial release"), None])
    monkeypatch.setattr(desktop, "send", send)
    with pytest.raises(OSError):
        desktop.execute(support.packet(support.RELEASE, modifiers=4))
    assert len(desktop.held) == 1
    desktop.release()
    assert not desktop.held
