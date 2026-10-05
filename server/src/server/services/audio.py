"""System output volume adapters. Imports stay local to their supported platform."""

import ctypes
import math
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from statistics import mean
from typing import Protocol


@dataclass(frozen=True)
class AudioState:
    volume: float
    muted: bool

    def __post_init__(self):
        if not math.isfinite(self.volume) or self.volume < 0:
            raise ValueError("Invalid system volume")


class AudioBackend(Protocol):
    def read(self) -> AudioState: ...
    def set_volume(self, volume: float) -> None: ...
    def set_muted(self, muted: bool) -> None: ...


def run_audio_command(args: list[str]) -> str:
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=True,
        timeout=2,
        env={**os.environ, "LC_ALL": "C"},
    )
    return result.stdout.strip()


class NoAudioDevice(RuntimeError):
    pass


class MacAudio:
    @staticmethod
    def check_output():
        class Address(ctypes.Structure):
            _fields_ = [
                ("selector", ctypes.c_uint32),
                ("scope", ctypes.c_uint32),
                ("element", ctypes.c_uint32),
            ]

        api = ctypes.CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")
        getter = api.AudioObjectGetPropertyData
        getter.restype = ctypes.c_int32
        getter.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(Address),
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_void_p,
        ]
        address = Address(int.from_bytes(b"dOut", "big"), int.from_bytes(b"glob", "big"), 0)
        device, size = ctypes.c_uint32(), ctypes.c_uint32(4)
        status = getter(1, ctypes.byref(address), 0, None, ctypes.byref(size), ctypes.byref(device))
        if status != 0 or device.value == 0:
            raise NoAudioDevice("No default audio output")

    def read(self) -> AudioState:
        self.check_output()
        script = (
            "set s to get volume settings\n"
            'return ((output volume of s) as text) & "," & ((output muted of s) as text)'
        )
        volume, muted = run_audio_command(["/usr/bin/osascript", "-e", script]).split(",")
        if muted.strip() not in ("true", "false"):
            raise ValueError("Invalid system mute state")
        return AudioState(float(volume), muted.strip() == "true")

    def set_volume(self, volume: float) -> None:
        run_audio_command(["/usr/bin/osascript", "-e", f"set volume output volume {round(volume)}"])

    def set_muted(self, muted: bool) -> None:
        run_audio_command(
            ["/usr/bin/osascript", "-e", f"set volume output muted {str(muted).lower()}"]
        )


class WindowsAudio:
    @contextmanager
    def endpoint(self):
        import comtypes
        from pycaw.pycaw import AudioUtilities

        comtypes.CoInitialize()
        try:
            device = AudioUtilities.GetSpeakers()
            if device is None:
                raise NoAudioDevice("No default audio output")
            yield device.EndpointVolume
        finally:
            comtypes.CoUninitialize()

    def read(self) -> AudioState:
        with self.endpoint() as endpoint:
            return AudioState(endpoint.GetMasterVolumeLevelScalar() * 100, bool(endpoint.GetMute()))

    def set_volume(self, volume: float) -> None:
        with self.endpoint() as endpoint:
            endpoint.SetMasterVolumeLevelScalar(volume / 100, None)

    def set_muted(self, muted: bool) -> None:
        with self.endpoint() as endpoint:
            endpoint.SetMute(int(muted), None)


class LinuxAudio:
    def read(self) -> AudioState:
        volume_text = run_audio_command(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        volumes = [float(v) for v in re.findall(r"(\d+(?:\.\d+)?)%", volume_text)]
        mute_text = run_audio_command(["pactl", "get-sink-mute", "@DEFAULT_SINK@"])
        match = re.fullmatch(r"Mute:\s*(yes|no)", mute_text)
        if not volumes or match is None:
            raise ValueError("Unrecognized pactl response")
        return AudioState(round(mean(volumes), 2), match[1] == "yes")

    def set_volume(self, volume: float) -> None:
        run_audio_command(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume:g}%"])

    def set_muted(self, muted: bool) -> None:
        run_audio_command(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if muted else "0"])


class UnsupportedAudio:
    def read(self) -> AudioState:
        raise RuntimeError("Unsupported system audio backend")

    def set_volume(self, volume: float) -> None:
        raise RuntimeError("Unsupported system audio backend")

    def set_muted(self, muted: bool) -> None:
        raise RuntimeError("Unsupported system audio backend")


def create_audio_backend() -> AudioBackend:
    if sys.platform == "darwin":
        return MacAudio()
    if sys.platform == "win32":
        return WindowsAudio()
    if sys.platform == "linux":
        return LinuxAudio()
    return UnsupportedAudio()
