import struct
import pyautogui
import logging
import pyperclip
import sys
import time

from loguru import logger

# 禁用 PyAutoGUI 的故障保险
pyautogui.FAILSAFE = False
# 移除每个指令后的默认暂停
pyautogui.PAUSE = 0

OP_MOVE = 0x01
OP_CLICK = 0x02
OP_SCROLL = 0x03
OP_DRAG = 0x04
OP_TEXT = 0x05
OP_KEY_ACTION = 0x06


def process_binary_command(data: bytes):
    if not data:
        return

    opcode = data[0]

    try:
        if opcode == OP_MOVE:
            if len(data) < 5:
                return
            dx, dy = struct.unpack(">hh", data[1:5])
            pyautogui.moveRel(dx, dy)

        elif opcode == OP_CLICK:
            if len(data) < 2:
                return
            button_code = data[1]
            button = "left" if button_code == 0x01 else "right"
            pyautogui.click(button=button)

        elif opcode == OP_SCROLL:
            if len(data) < 5:
                return
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
                return
            state = data[1]
            if state == 0x01:
                pyautogui.mouseDown(button="left")
            else:
                pyautogui.mouseUp(button="left")

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
            key_name = data[1:].decode("utf-8")
            pyautogui.press(key_name)

    except Exception as e:
        logger.error(f"Error processing opcode {opcode}: {e}")


def reset_input_state():
    """重置输入状态，例如释放所有按下的键"""
    try:
        pyautogui.mouseUp(button="left")
    except Exception as e:
        logger.error(f"Error resetting input state: {e}")
