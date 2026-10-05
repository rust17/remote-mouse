"""Ordered input execution and independently ordered system audio execution."""

import asyncio
import ctypes
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pyautogui
from loguru import logger
from server.core.protocol import (
    OP_CLICK,
    OP_DRAG,
    OP_MOVE,
    OP_SCROLL,
    MediaAction,
    MediaCommand,
    process_binary_command,
)
from server.services.audio import AudioState, NoAudioDevice, create_audio_backend
from server.services.mouse import double_click

INPUT_ACTIONS = {
    MediaAction.REWIND,
    MediaAction.PLAY_PAUSE,
    MediaAction.FORWARD,
    MediaAction.FULLSCREEN,
}
AUDIO_ACTIONS = set(MediaAction) - INPUT_ACTIONS


def input_unavailable() -> str | None:
    if sys.platform == "darwin":
        api = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        api.AXIsProcessTrusted.restype = ctypes.c_bool
        if not api.AXIsProcessTrusted():
            return "input_permission"
    elif (
        sys.platform == "linux"
        and os.environ.get("XDG_SESSION_TYPE") == "wayland"
        or sys.platform not in ("darwin", "win32", "linux")
    ):
        return "input_unsupported"
    return None


class InputWorker:
    def __init__(self, processor=process_binary_command, probe=input_unavailable):
        self.processor = processor
        self.probe = probe
        self.drag_owner = None
        self.failed_actions = {}

    def capabilities(self, reprobe=False):
        if reprobe:
            self.failed_actions.clear()
        try:
            error = self.probe()
        except Exception:
            logger.exception("Input capability probe failed")
            error = "input_unavailable"
        errors = {action: error for action in INPUT_ACTIONS} if error else dict(self.failed_actions)
        if self.drag_owner is not None:
            errors[MediaAction.FULLSCREEN] = "drag_busy"
        return errors

    def execute(self, owner, data: bytes):
        opcode = data[0] if data else None
        if opcode == OP_DRAG:
            if len(data) != 2 or data[1] not in (0, 1):
                return False
            if data[1] == 1:
                if self.drag_owner is not None:
                    return self.drag_owner is owner
                # Retain ownership even if mouseDown throws after partially executing.
                self.drag_owner = owner
                return self.processor(data) is not False
            if self.drag_owner is owner:
                return self.release(owner)
            return False
        if self.drag_owner is not None and (
            opcode in (OP_CLICK, OP_SCROLL) or (opcode == OP_MOVE and self.drag_owner is not owner)
        ):
            return False
        return self.processor(data) is not False

    def release(self, owner):
        if self.drag_owner is not owner or owner is None:
            return True
        if self.processor(bytes([OP_DRAG, 0])) is False:
            logger.warning("Failed to release drag; retaining owner for shutdown retry")
            return False
        self.drag_owner = None
        return True

    def media(self, action: MediaAction):
        error = self.capabilities().get(action)
        if error:
            return error
        try:
            if action == MediaAction.FULLSCREEN:
                double_click()
            else:
                pyautogui.press(
                    {
                        MediaAction.REWIND: "left",
                        MediaAction.PLAY_PAUSE: "space",
                        MediaAction.FORWARD: "right",
                    }[action]
                )
        except Exception:
            logger.exception("Media input failed: {}", action.name)
            self.failed_actions[action] = "input_failed"
            return "input_failed"
        return None


@dataclass(frozen=True)
class Observation:
    revision: int
    state: AudioState | None
    errors: dict


class AudioWorker:
    def __init__(self, backend):
        self.backend = backend
        self.revision = 0
        self.failed_actions = {}
        self.last_error = None

    @staticmethod
    def error_code(error):
        if isinstance(error, (FileNotFoundError, ImportError)):
            return "audio_dependency"
        if isinstance(error, PermissionError):
            return "audio_permission"
        if isinstance(error, NoAudioDevice):
            return "audio_no_device"
        return "audio_unavailable"

    def observe(self, reprobe=False):
        if reprobe:
            self.failed_actions.clear()
        self.revision += 1
        try:
            state = self.backend.read()
            self.last_error = None
            return Observation(self.revision, state, dict(self.failed_actions))
        except Exception as error:
            code = self.error_code(error)
            if self.last_error != (code, str(error)):
                logger.warning("System audio query failed ({}): {}", code, error)
                self.last_error = (code, str(error))
            return Observation(self.revision, None, dict.fromkeys(AUDIO_ACTIONS, code))

    def media(self, action):
        before = self.observe()
        if action in before.errors:
            return before.errors[action], before
        try:
            if action == MediaAction.MUTE:
                target_mute = not before.state.muted
                self.backend.set_muted(target_mute)
                target_volume = None
            else:
                delta = 5 if action == MediaAction.VOLUME_UP else -5
                target_volume = max(0, min(100, before.state.volume + delta))
                target_mute = False
                self.backend.set_volume(target_volume)
                self.backend.set_muted(False)
        except Exception as error:
            logger.exception("System audio operation failed: {}", action.name)
            code = self.error_code(error)
            if code == "audio_unavailable":
                code = "audio_failed"
            self.failed_actions[action] = code
            return code, self.observe()
        after = self.observe()
        if after.state is None:
            return "audio_unavailable", after
        if after.state.muted != target_mute or (
            target_volume is not None and abs(after.state.volume - target_volume) > 1
        ):
            self.failed_actions[action] = "audio_not_verified"
            return "audio_not_verified", self.observe()
        return None, after


class MediaService:
    def __init__(self, processor=process_binary_command, audio=None, probe=input_unavailable):
        self.input = InputWorker(processor, probe)
        self.audio = AudioWorker(audio if audio is not None else create_audio_backend())
        self.input_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="remote-input")
        self.audio_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="remote-audio")

    async def input_call(self, function, *args):
        return await asyncio.get_running_loop().run_in_executor(
            self.input_executor, function, *args
        )

    async def audio_call(self, function, *args):
        return await asyncio.get_running_loop().run_in_executor(
            self.audio_executor, function, *args
        )

    async def snapshot(self, observation=None, reprobe=False):
        input_errors, observation = await asyncio.gather(
            self.input_call(self.input.capabilities, reprobe),
            self.audio_call(self.audio.observe, reprobe)
            if observation is None
            else self._observed(observation),
        )
        errors = {**input_errors, **observation.errors}
        state = observation.state
        return {
            "type": "media_snapshot",
            "version": 1,
            "revision": observation.revision,
            "capabilities": [a.name.lower() for a in MediaAction if a not in errors],
            "unavailable": {a.name.lower(): reason for a, reason in errors.items()},
            "state": {
                "volume": state.volume if state else None,
                "muted": state.muted if state else None,
                "playing": None,
                "fullscreen": None,
            },
        }

    @staticmethod
    async def _observed(observation):
        return observation

    async def execute_media(self, command: MediaCommand, on_result=None):
        action = command.action
        observation = None
        if action in INPUT_ACTIONS:
            error = await self.input_call(self.input.media, action)
            status = "issued"
        else:
            error, observation = await self.audio_call(self.audio.media, action)
            status = "verified"
        result = {
            "type": "media_result",
            "version": 1,
            "requestId": command.request_id,
            "action": action.name.lower(),
            "status": "error" if error else status,
        }
        if error:
            result["errorCode"] = error
        if on_result is not None:
            await on_result(result)
        snapshot = await self.snapshot(observation)
        snapshot["requestId"] = command.request_id
        return result, snapshot

    async def release(self, owner):
        await self.input_call(self.input.release, owner)

    async def close(self):
        await self.input_call(lambda: self.input.release(self.input.drag_owner))
        # Shutdown off the event loop, including audio operations still finishing after disconnect.
        await asyncio.to_thread(self.input_executor.shutdown, wait=True)
        await asyncio.to_thread(self.audio_executor.shutdown, wait=True)
