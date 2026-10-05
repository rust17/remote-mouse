"""Platform-specific mouse gestures used by media controls."""

import sys
import time

import pyautogui


def double_click():
    """Send a left double-click at the current desktop cursor position."""
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
