import struct
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from enum import IntEnum

import pyautogui
import pyperclip
from loguru import logger

# 禁用 PyAutoGUI 的故障保险
pyautogui.FAILSAFE = False
# 移除每个指令后的默认暂停
pyautogui.PAUSE = 0

# Commands run on the serial input worker; disconnect/shutdown releases this state.
_left_button_held = False

OP_MOVE = 0x01
OP_CLICK = 0x02
OP_SCROLL = 0x03
OP_DRAG = 0x04
OP_TEXT = 0x05
OP_KEY_ACTION = 0x06
OP_MEDIA = 0x07
OP_MEDIA_QUERY = 0x08


class MediaAction(IntEnum):
    REWIND = 1
    PLAY_PAUSE = 2
    FORWARD = 3
    VOLUME_DOWN = 4
    MUTE = 5
    VOLUME_UP = 6
    FULLSCREEN = 7


@dataclass(frozen=True)
class MediaCommand:
    action: MediaAction
    request_id: int


@dataclass(frozen=True)
class MediaQuery:
    pass


def decode_media_command(data: bytes) -> MediaCommand | MediaQuery:
    if data == bytes([OP_MEDIA_QUERY]):
        return MediaQuery()
    if len(data) != 6 or data[0] != OP_MEDIA:
        raise ValueError("Invalid media packet length or opcode")
    return MediaCommand(MediaAction(data[1]), struct.unpack(">I", data[2:6])[0])


def get_modifiers_list(mask: int):
    """
    根据 mask 获取需要按下的修饰键列表。
    Bit 0: Ctrl
    Bit 1: Shift
    Bit 2: Alt
    Bit 3: Win/Cmd
    """
    modifiers = []
    if mask & 1:
        modifiers.append("ctrl")
    if mask & 2:
        modifiers.append("shift")
    if mask & 4:
        modifiers.append("alt")
    if mask & 8:
        if sys.platform == "darwin":
            modifiers.append("command")
        else:
            modifiers.append("win")
    return modifiers


def process_binary_command(data: bytes):
    global _left_button_held

    if not data:
        return False

    opcode = data[0]

    # Media commands are decoded here and dispatched by the async service to
    # the input or audio worker; they must not become arbitrary key names.
    if opcode in (OP_MEDIA, OP_MEDIA_QUERY):
        return decode_media_command(data)

    try:
        if opcode == OP_MOVE:
            if len(data) < 5:
                return False
            dx, dy = struct.unpack(">hh", data[1:5])
            if _left_button_held:
                # macOS requires dragged events; keep the button down between packets.
                pyautogui.dragRel(dx, dy, button="left", mouseDownUp=False)
            else:
                pyautogui.moveRel(dx, dy)

        elif opcode == OP_CLICK:
            # [OpCode] [Button] [ModifierMask]
            if len(data) < 2:
                return False

            button_code = data[1]
            button = "left" if button_code == 0x01 else "right"

            mask = 0
            if len(data) >= 3:
                mask = data[2]

            modifiers = get_modifiers_list(mask)

            with ExitStack() as stack:
                for key in modifiers:
                    stack.enter_context(pyautogui.hold(key))
                pyautogui.click(button=button)

        elif opcode == OP_SCROLL:
            if len(data) < 5:
                return False
            # aiortc/pyautogui scroll might need adjustment
            # pyautogui.scroll(clicks, x, y) - vertical
            # hscroll for horizontal if available
            sx, sy = struct.unpack(">hh", data[1:5])
            if sy != 0:
                pyautogui.scroll(sy)
            if sx != 0:
                pyautogui.hscroll(sx)

        elif opcode == OP_DRAG:
            if len(data) < 2:
                return False
            state = data[1]
            if state == 0x01:
                # Retain state if mouseDown fails after partially executing.
                _left_button_held = True
                pyautogui.mouseDown(button="left")
            else:
                pyautogui.mouseUp(button="left")
                _left_button_held = False

        elif opcode == OP_TEXT:
            text = data[1:].decode("utf-8")
            # Use clipboard paste to support unicode (Chinese, etc.)
            try:
                # Save old clipboard content (best effort)
                try:
                    old_content = pyperclip.paste()
                except Exception:
                    old_content = ""

                # Set new content
                pyperclip.copy(text)

                # Wait briefly for clipboard to update
                time.sleep(0.1)

                # Paste
                if sys.platform == "darwin":
                    pyautogui.hotkey("command", "v")
                else:
                    pyautogui.hotkey("ctrl", "v")

                # Wait briefly for paste to complete
                time.sleep(0.1)

                # Restore old clipboard content
                if old_content:
                    pyperclip.copy(old_content)
            except Exception as e:
                logger.error(f"Clipboard paste failed: {e}")
                # Fallback to write if clipboard fails?
                # might be better to just fail or try write as last resort
                pyautogui.write(text)

        elif opcode == OP_KEY_ACTION:
            # [OpCode] [ModifierMask] [KeyName: UTF8]
            if len(data) < 2:
                return False

            mask = data[1]
            key_name = data[2:].decode("utf-8")

            # Semantic shortcut: the phone's OS does not identify the controlled computer's OS.
            if key_name == "select_all":
                pyautogui.hotkey("command" if sys.platform == "darwin" else "ctrl", "a")
                return True

            modifiers = get_modifiers_list(mask)

            # 特殊键名映射 (客户端发来的可能是 'enter', 'backspace' 等，pyautogui 需要对应)
            # 大部分一致，除了 'win'/'cmd' 等
            if key_name.lower() in ["win", "cmd", "meta"]:
                if sys.platform == "darwin":
                    key_name = "command"
                else:
                    key_name = "win"

            with ExitStack() as stack:
                for key in modifiers:
                    stack.enter_context(pyautogui.hold(key))
                pyautogui.press(key_name)

        else:
            return False
        return True

    except Exception as e:
        logger.error(f"Error processing opcode {opcode}: {e}")
        return False
