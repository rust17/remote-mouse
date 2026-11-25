"""Platform-specific mouse input."""

import ctypes
import sys
import time

import pyautogui
from server.windows import input as windows_input

_CURSOR_SHOWING = 0x00000001
_INPUT_MOUSE = 0
_MOUSEEVENTF_MOVE = 0x0001


class _CursorInfo(ctypes.Structure):
    _fields_ = [
        ("size", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("cursor", ctypes.c_void_p),
        ("x", ctypes.c_int32),
        ("y", ctypes.c_int32),
    ]


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_int32),
        ("dy", ctypes.c_int32),
        ("mouse_data", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("extra_info", ctypes.c_size_t),
    ]


class _Input(ctypes.Structure):
    # MOUSEINPUT determines the native INPUT union's size and alignment.
    _fields_ = [("type", ctypes.c_uint32), ("mouse", _MouseInput)]


def _move_hidden_windows_cursor(dx: int, dy: int) -> bool:
    user32 = ctypes.windll.user32
    cursor = _CursorInfo(size=ctypes.sizeof(_CursorInfo))
    if not user32.GetCursorInfo(ctypes.byref(cursor)) or cursor.flags & _CURSOR_SHOWING:
        return False

    # PyAutoGUI uses SetCursorPos on Windows. A mouse input event can reveal a hidden cursor.
    event = _Input(type=_INPUT_MOUSE, mouse=_MouseInput(dx=dx, dy=dy, flags=_MOUSEEVENTF_MOVE))
    return user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event)) == 1


def move_relative(dx: int, dy: int, *, dragging: bool) -> None:
    if sys.platform == "win32" and (dx or dy) and _move_hidden_windows_cursor(dx, dy):
        return
    if dragging:
        # macOS requires dragged events while the button is held between packets.
        pyautogui.dragRel(dx, dy, button="left", mouseDownUp=False)
    else:
        pyautogui.moveRel(dx, dy)


def double_click():
    """Send a left double-click at the current desktop cursor position."""
    routed = windows_input.route(windows_input.DOUBLE_CLICK)
    if routed is not None:
        if not routed:
            raise OSError("UAC mouse input unavailable")
        return
    if sys.platform != "darwin":
        pyautogui.doubleClick(button="left", interval=0.12)
        return

    import Quartz

    # PyAutoGUI 0.9.54 sends two independent macOS clicks without click state.
    # AppKit/browser receivers need count 2 on both halves of the second click.
    cursor = Quartz.CGEventCreate(None)
    if cursor is None:
        raise RuntimeError("Cannot read desktop cursor")
    position = Quartz.CGEventGetLocation(cursor)
    for count in (1, 2):
        down = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseDown, position, Quartz.kCGMouseButtonLeft
        )
        up = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseUp, position, Quartz.kCGMouseButtonLeft
        )
        if down is None or up is None:
            raise RuntimeError("Cannot create mouse click events")
        for event in (down, up):
            Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, count)
        try:
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        finally:
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
        if count == 1:
            time.sleep(0.12)
