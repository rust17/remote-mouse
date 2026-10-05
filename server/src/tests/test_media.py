import asyncio
import struct
import threading
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from server.core.protocol import MediaAction, MediaCommand, decode_media_command
from server.services.audio import AudioState
from server.services.media import AudioWorker, InputWorker, MediaService
from server.services.web import create_app


class FakeAudio:
    def __init__(self, volume=50, muted=False):
        self.state = AudioState(volume, muted)

    def read(self):
        return self.state

    def set_volume(self, volume):
        self.state = AudioState(volume, self.state.muted)

    def set_muted(self, muted):
        self.state = AudioState(self.state.volume, muted)


@pytest.mark.parametrize(
    "action,key",
    [
        (MediaAction.REWIND, "left"),
        (MediaAction.PLAY_PAUSE, "space"),
        (MediaAction.FORWARD, "right"),
    ],
)
def test_media_key_mapping(monkeypatch, action, key):
    press = Mock()
    monkeypatch.setattr("server.services.media.pyautogui.press", press)
    assert InputWorker(probe=lambda: None).media(action) is None
    press.assert_called_once_with(key)


def test_double_click_never_infers_fullscreen(monkeypatch):
    click = Mock()
    monkeypatch.setattr("server.services.media.double_click", click)
    worker = InputWorker(probe=lambda: None)
    assert worker.media(MediaAction.FULLSCREEN) is None
    assert worker.media(MediaAction.FULLSCREEN) is None
    assert click.call_count == 2
    click.assert_called_with()
    click.side_effect = RuntimeError("input rejected")
    assert worker.media(MediaAction.FULLSCREEN) == "input_failed"
    assert worker.capabilities()[MediaAction.FULLSCREEN] == "input_failed"


@pytest.mark.parametrize(
    "start,action,target",
    [
        (0, MediaAction.VOLUME_DOWN, 0),
        (98, MediaAction.VOLUME_UP, 100),
        (50, MediaAction.VOLUME_DOWN, 45),
        (120, MediaAction.VOLUME_UP, 100),
    ],
)
def test_volume_clamp_unmute_and_readback(start, action, target):
    worker = AudioWorker(FakeAudio(start, True))
    error, observation = worker.media(action)
    assert error is None
    assert observation.state == AudioState(target, False)
    assert observation.revision == 2


def test_mute_uses_measured_state():
    worker = AudioWorker(FakeAudio())
    assert worker.media(MediaAction.MUTE)[1].state.muted is True
    assert worker.media(MediaAction.MUTE)[1].state.muted is False


@pytest.mark.parametrize(
    "exception",
    [
        FileNotFoundError("pactl"),
        ModuleNotFoundError("pycaw"),
        PermissionError(),
        RuntimeError("no output"),
    ],
)
def test_missing_audio_does_not_disable_input(exception):
    async def run():
        backend = Mock()
        backend.read.side_effect = exception
        service = MediaService(audio=backend, probe=lambda: None)
        try:
            snapshot = await service.snapshot()
            assert snapshot["capabilities"] == ["rewind", "play_pause", "forward", "fullscreen"]
            assert snapshot["state"] == {
                "volume": None,
                "muted": None,
                "playing": None,
                "fullscreen": None,
            }
            result, _ = await service.execute_media(MediaCommand(MediaAction.MUTE, 123))
            assert result["status"] == "error"
            assert result["requestId"] == 123
        finally:
            await service.close()

    asyncio.run(run())


def test_audio_write_failure_and_unverified_result():
    backend = FakeAudio()
    backend.set_volume = Mock(side_effect=PermissionError())
    error, observation = AudioWorker(backend).media(MediaAction.VOLUME_UP)
    assert error == "audio_permission"
    assert observation.state.volume == 50
    assert observation.errors[MediaAction.VOLUME_UP] == error
    backend.set_volume = Mock()  # No actual change must never be verified.
    assert AudioWorker(backend).media(MediaAction.VOLUME_UP)[0] == "audio_not_verified"


def test_drag_owner_conflicts_disconnect_and_shutdown(monkeypatch):
    commands = []
    released = threading.Event()

    def process(data):
        commands.append(data)
        if data == b"\x04\x00":
            released.set()

    service = MediaService(processor=process, audio=FakeAudio(), probe=lambda: None)
    click = Mock()
    monkeypatch.setattr("server.services.media.double_click", click)
    with TestClient(create_app(lambda: service)) as client:
        with client.websocket_connect("/ws") as owner:
            owner.send_bytes(b"\x04\x01")
            # Query is a deterministic barrier after the drag packet.
            owner.send_bytes(b"\x08")
            assert owner.receive_json()["unavailable"]["fullscreen"] == "drag_busy"
            with client.websocket_connect("/ws") as other:
                for packet in [b"\x04\x00", b"\x04\x01", b"\x02\x01", struct.pack(">Bhh", 1, 1, 1)]:
                    other.send_bytes(packet)
                other.send_bytes(b"\x07\x07\x00\x00\x00\x01")
                assert other.receive_json()["errorCode"] == "drag_busy"
                other.receive_json()
            owner.send_bytes(struct.pack(">Bhh", 1, 2, 3))
            owner.send_bytes(b"\x08")
            owner.receive_json()
            assert commands == [b"\x04\x01", struct.pack(">Bhh", 1, 2, 3)]
        # Session exit can precede shielded cleanup on the input worker.
        assert released.wait(2), "Owner disconnect did not release the mouse button"
        assert commands[-1] == b"\x04\x00"
        released.clear()
        with client.websocket_connect("/ws") as owner:
            owner.send_bytes(b"\x04\x01")
            owner.send_bytes(b"\x08")
            owner.receive_json()
    assert released.is_set()
    assert commands[-1] == b"\x04\x00"
    click.assert_not_called()


def test_input_permission_and_failed_drag_cleanup():
    processor = Mock(side_effect=[False, True])
    worker = InputWorker(processor, probe=lambda: "input_permission")
    assert len(worker.capabilities()) == 4
    owner, other = object(), object()
    assert worker.execute(owner, b"\x04\x01") is False
    worker.release(other)
    assert processor.call_count == 1
    worker.release(owner)
    assert worker.drag_owner is None


@pytest.mark.parametrize(
    "packet",
    [
        b"",
        b"\x08\x00",
        b"\x07",
        b"\x07\x00\x00\x00\x00\x01",
        b"\x07\x08\x00\x00\x00\x01",
        b"\x07\x01\x00\x00\x00\x01\x00",
    ],
)
def test_invalid_packets(packet):
    with pytest.raises(ValueError):
        decode_media_command(packet)


def test_web_protocol_results_and_invalid_packets():
    service = MediaService(audio=FakeAudio(), probe=lambda: None)
    with TestClient(create_app(lambda: service)) as client, client.websocket_connect("/ws") as ws:
        ws.send_bytes(b"\x07\x08\x00\x00\x00\x01")
        assert ws.receive_json()["errorCode"] == "invalid_packet"
        ws.send_bytes(b"\x07\x06\x12\x34\x56\x78")
        result, snapshot = ws.receive_json(), ws.receive_json()
        assert result["status"] == "verified"
        assert result["requestId"] == 0x12345678
        assert snapshot["state"]["volume"] == 55
        assert snapshot["state"]["playing"] is None


def test_audio_thread_does_not_block_input_or_event_loop():
    async def run():
        audio_started, finish_audio = threading.Event(), threading.Event()
        backend = FakeAudio()

        def slow_read():
            audio_started.set()
            assert finish_audio.wait(2)
            return AudioState(50, False)

        backend.read = slow_read
        thread_ids = []
        service = MediaService(
            processor=lambda _: thread_ids.append(threading.get_ident()),
            audio=backend,
            probe=lambda: None,
        )
        task = asyncio.create_task(service.snapshot())
        try:
            assert await asyncio.to_thread(audio_started.wait, 1)
            owner = object()
            await asyncio.wait_for(service.input_call(service.input.execute, owner, b""), 0.2)
            assert thread_ids[0] != threading.get_ident()
            assert not task.done()
        finally:
            finish_audio.set()
            await task
            await service.close()

    asyncio.run(run())


def test_query_does_not_hold_up_same_connection_input():
    started, finish, moved = threading.Event(), threading.Event(), threading.Event()
    backend = FakeAudio()

    def slow_read():
        started.set()
        assert finish.wait(2)
        return AudioState(50, False)

    backend.read = slow_read
    service = MediaService(processor=lambda _: moved.set(), audio=backend, probe=lambda: None)
    try:
        with (
            TestClient(create_app(lambda: service)) as client,
            client.websocket_connect("/ws") as ws,
        ):
            ws.send_bytes(b"\x08")
            assert started.wait(1)
            ws.send_bytes(struct.pack(">Bhh", 1, 1, 1))
            assert moved.wait(1)
            finish.set()
            assert ws.receive_json()["queryId"] == 1
    finally:
        finish.set()


def test_shutdown_retries_failed_owner_release():
    async def run():
        processor = Mock(side_effect=[True, False, True])
        service = MediaService(processor=processor, audio=FakeAudio(), probe=lambda: None)
        owner = object()
        await service.input_call(service.input.execute, owner, b"\x04\x01")
        await service.release(owner)
        assert service.input.drag_owner is owner
        await service.close()
        assert service.input.drag_owner is None
        assert processor.call_args.args[0] == b"\x04\x00"

    asyncio.run(run())


def test_abnormal_websocket_message_releases_its_drag():
    commands = []
    service = MediaService(processor=commands.append, audio=FakeAudio(), probe=lambda: None)
    with TestClient(create_app(lambda: service)) as client, client.websocket_connect("/ws") as ws:
        ws.send_bytes(b"\x04\x01")
        ws.send_bytes(b"\x08")
        ws.receive_json()
        ws.send_text("unsupported text frame")
    assert commands == [b"\x04\x01", b"\x04\x00"]


def test_input_media_order_and_single_worker(monkeypatch):
    operations = []
    monkeypatch.setattr(
        "server.services.media.pyautogui.press",
        lambda key: operations.append((key, threading.get_ident())),
    )
    service = MediaService(
        processor=lambda data: operations.append((data, threading.get_ident())),
        audio=FakeAudio(),
        probe=lambda: None,
    )
    move = struct.pack(">Bhh", 1, 1, 1)
    with TestClient(create_app(lambda: service)) as client, client.websocket_connect("/ws") as ws:
        ws.send_bytes(b"\x07\x01\x00\x00\x00\x01")
        ws.send_bytes(move)
        ws.send_bytes(b"\x08")
        for _ in range(3):
            ws.receive_json()
    assert [operation[0] for operation in operations] == ["left", move]
    assert len({operation[1] for operation in operations}) == 1


def test_new_connection_reprobes_failed_capabilities():
    async def run():
        service = MediaService(audio=FakeAudio(), probe=lambda: None)
        service.input.failed_actions[MediaAction.FULLSCREEN] = "input_failed"
        service.audio.failed_actions[MediaAction.MUTE] = "audio_failed"
        try:
            assert "mute" not in (await service.snapshot())["capabilities"]
            snapshot = await service.snapshot(reprobe=True)
            assert "mute" in snapshot["capabilities"]
            assert "fullscreen" in snapshot["capabilities"]
        finally:
            await service.close()

    asyncio.run(run())
