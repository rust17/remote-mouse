import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from server.services import audio


def test_mac_scripts(monkeypatch):
    command = Mock(return_value="69,true")
    monkeypatch.setattr(audio, "run_audio_command", command)
    monkeypatch.setattr(audio.MacAudio, "check_output", staticmethod(lambda: None))
    backend = audio.MacAudio()
    assert backend.read() == audio.AudioState(69, True)
    backend.set_volume(74)
    assert command.call_args.args[0][-1] == "set volume output volume 74"
    backend.set_muted(False)
    assert command.call_args.args[0][-1] == "set volume output muted false"
    command.return_value = "NaN,true"
    with pytest.raises(ValueError):
        backend.read()


def test_windows_core_audio_and_com_cleanup(monkeypatch):
    endpoint = Mock()
    endpoint.GetMasterVolumeLevelScalar.return_value = 0.37
    endpoint.GetMute.return_value = 1
    utilities = Mock()
    utilities.GetSpeakers.return_value = SimpleNamespace(EndpointVolume=endpoint)
    com = Mock()
    monkeypatch.setitem(sys.modules, "comtypes", com)
    monkeypatch.setitem(sys.modules, "pycaw.pycaw", SimpleNamespace(AudioUtilities=utilities))
    backend = audio.WindowsAudio()
    assert backend.read() == audio.AudioState(37, True)
    backend.set_volume(42)
    backend.set_muted(False)
    endpoint.SetMasterVolumeLevelScalar.assert_called_once_with(0.42, None)
    endpoint.SetMute.assert_called_once_with(0, None)
    utilities.GetSpeakers.return_value = None
    with pytest.raises(RuntimeError):
        backend.read()
    assert com.CoInitialize.call_count == com.CoUninitialize.call_count == 4


def test_linux_default_sink_locale_and_channel_readback(monkeypatch):
    real_command = audio.run_audio_command
    command = Mock(
        side_effect=[
            "Volume: front-left: 90 / 70% / -dB, front-right: 80 / 60% / -dB",
            "Mute: no",
            "",
            "",
        ]
    )
    monkeypatch.setattr(audio, "run_audio_command", command)
    backend = audio.LinuxAudio()
    assert backend.read() == audio.AudioState(65, False)
    backend.set_volume(100)
    assert command.call_args.args[0] == ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "100%"]
    backend.set_muted(True)
    assert command.call_args.args[0][-1] == "1"
    runner = Mock(return_value=SimpleNamespace(stdout="Mute: yes\n"))
    monkeypatch.setattr(audio.subprocess, "run", runner)
    assert real_command(["pactl"]) == "Mute: yes"
    assert runner.call_args.kwargs["env"]["LC_ALL"] == "C"
    assert runner.call_args.kwargs["timeout"] == 2


@pytest.mark.parametrize("response", [("", "Mute: no"), ("Volume: 50%", "invalid")])
def test_linux_invalid_response(monkeypatch, response):
    monkeypatch.setattr(audio, "run_audio_command", Mock(side_effect=response))
    with pytest.raises(ValueError):
        audio.LinuxAudio().read()


@pytest.mark.parametrize(
    "platform,kind",
    [("darwin", audio.MacAudio), ("win32", audio.WindowsAudio), ("linux", audio.LinuxAudio)],
)
def test_platform_factory(monkeypatch, platform, kind):
    monkeypatch.setattr(audio.sys, "platform", platform)
    assert isinstance(audio.create_audio_backend(), kind)


def test_mac_no_default_device(monkeypatch):
    from server.services.audio import NoAudioDevice

    getter = Mock(return_value=0)  # Leaves the returned AudioDeviceID at zero.
    monkeypatch.setattr(
        audio.ctypes, "CDLL", lambda _: SimpleNamespace(AudioObjectGetPropertyData=getter)
    )
    with pytest.raises(NoAudioDevice):
        audio.MacAudio().read()
    getter.assert_called_once()
