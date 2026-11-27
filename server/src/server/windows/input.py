"""Small, versioned local mouse protocol and optional Windows service client."""

import hashlib
import logging
import struct
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

VERSION = 3
NORMAL, HANDLED, FAILED = 0, 1, 2
MOVE, CLICK, SCROLL, DRAG, DOUBLE_CLICK, RELEASE, PING = range(1, 8)
TEXT, KEY = 8, 9
KEY_CODES = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 9,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 8,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "space": 0x20,
    "win": 0x5B,
    "cmd": 0x5B,
    "meta": 0x5B,
    "ctrl": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "capslock": 0x14,
}
KEY_CODES.update({f"f{index}": 0x6F + index for index in range(1, 25)})
PACKET = struct.Struct("<BBhhBB")


def identity(sid):
    return "RemoteMouseInput-" + hashlib.sha256(sid.encode()).hexdigest()[:16]


def pipe_name(sid, session):
    return rf"\\.\pipe\{identity(sid)}-{session}"


def packet(action, x=0, y=0, button=0, modifiers=0, text=""):
    if action in (TEXT, KEY):
        return bytes((VERSION, action, modifiers)) + text.encode("utf-8")
    return PACKET.pack(VERSION, action, x, y, button, modifiers)


def decode(data):
    if len(data) >= 3 and data[0] == VERSION and data[1] in (TEXT, KEY):
        action, modifiers = data[1:3]
        if len(data) > 4099 or modifiers > 15 or (action == TEXT and modifiers):
            raise ValueError("Invalid keyboard command")
        text = data[3:].decode("utf-8")
        if action == KEY and not (
            text in KEY_CODES
            or text == "select_all"
            or len(text) == 1
            and text.isascii()
            and text.isprintable()
        ):
            raise ValueError("Unsupported key")
        return action, text, 0, 0, modifiers
    if len(data) != PACKET.size:
        raise ValueError("Invalid mouse command size")
    version, action, x, y, button, modifiers = PACKET.unpack(data)
    if version != VERSION or action not in range(1, 8) or modifiers > 15:
        raise ValueError("Unsupported mouse command")
    if action == CLICK and button not in (1, 2):
        raise ValueError("Invalid button")
    if action not in (CLICK, DRAG) and button:
        raise ValueError("Unexpected mouse button")
    if action == DRAG and button not in (0, 1):
        raise ValueError("Invalid drag state")
    if action not in (MOVE, SCROLL) and (x or y):
        raise ValueError("Unexpected mouse coordinates")
    if action not in (CLICK, RELEASE) and modifiers:
        raise ValueError("Unexpected modifiers")
    return action, x, y, button, modifiers


def install_directory(sid):
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows\CurrentVersion",
        0,
        winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
    ) as key:
        program_files = winreg.QueryValueEx(key, "ProgramFilesDir")[0]
    return Path(program_files) / "RemoteMouseInput" / identity(sid)


class Client:
    def __init__(self):
        self.pipe = None
        self.retry_at = 0
        self.last_error = None
        self.lock = threading.Lock()

    def close(self):
        if self.pipe is not None:
            from server.windows import native as n

            n.CloseHandle(self.pipe)
            self.pipe = None

    def request(self, data):
        from server.windows import native as n
        from server.windows.transport import transact

        with self.lock:
            try:
                if self.pipe is None:
                    if time.monotonic() < self.retry_at:
                        return FAILED
                    sid = n.process_sid()
                    name = pipe_name(sid, n.session_id())
                    pipe = n.check(n.CreateFile(name, 0xC0000000, 0, None, 3, 0x40110000, None))
                    self.pipe = pipe
                    pid = n.DWORD()
                    n.check(n.GetNamedPipeServerProcessId(pipe, n.c.byref(pid)))
                    with n.handle(n.OpenProcess(0x1000, False, pid)) as process:
                        expected = install_directory(sid) / "RemoteMouseInput.exe"
                        # The protected helper requires SYSTEM before opening its pipe.
                        # Ordinary users cannot query a SYSTEM process token.
                        if (
                            n.image_path(process) != expected
                            or n.session_id(pid.value) != n.session_id()
                        ):
                            raise PermissionError("Unexpected input service")
                reply = transact(self.pipe, data)
                if (
                    len(reply) != 2
                    or reply[0] != VERSION
                    or reply[1] not in (NORMAL, HANDLED, FAILED)
                ):
                    raise ValueError("Incompatible input service")
                self.last_error = None if reply[1] != FAILED else "Input service rejected command"
                return reply[1]
            except (OSError, ValueError) as error:
                if self.last_error != str(error):
                    logging.warning("UAC input connection failed: %s", error)
                self.last_error = str(error)
                self.close()
                self.retry_at = time.monotonic() + 1
                return FAILED


client = Client()
_ordinary_drag = False
_secure_input_active = False


@contextmanager
def ordinary_modifiers(mask):
    """Release our modifiers even if a shortcut activates a privileged window."""
    global _secure_input_active

    try:
        yield
    finally:
        if sys.platform == "win32" and mask:
            from server.windows import native as n

            desktop = n.OpenInputDesktop(0, False, 1)
            protected = not desktop
            if desktop:
                name = n.c.create_unicode_buffer(64)
                try:
                    n.check(n.GetUserObjectInformation(desktop, 2, name, n.c.sizeof(name), None))
                    protected = name.value.casefold() != "default" or n.foreground_elevated()
                finally:
                    n.CloseDesktop(desktop)
            if protected:
                # UIPI can reject the ordinary key-up after Alt+Tab/Alt+Esc
                # changes focus. Release only modifiers pressed by this command.
                _secure_input_active = True
                client.request(packet(RELEASE, modifiers=mask))


def resume_ordinary():
    """Finish the secure input session before the next ordinary mouse or key event."""
    global _ordinary_drag, _secure_input_active

    if sys.platform != "win32" or not _secure_input_active:
        return False
    from server.windows import native as n

    desktop = n.OpenInputDesktop(0, False, 1)
    if not desktop:
        return False
    name = n.c.create_unicode_buffer(64)
    try:
        n.check(n.GetUserObjectInformation(desktop, 2, name, n.c.sizeof(name), None))
        if name.value.casefold() != "default" or n.foreground_elevated():
            return False
    finally:
        n.CloseDesktop(desktop)
    # RELEASE makes the worker refresh its desktop synchronously. Closing the
    # connection also requests cleanup if the helper could not acknowledge it.
    # This cleanup is independent of the next command, which is never replayed.
    disconnect()
    _secure_input_active = False
    _ordinary_drag = False
    return True


def route(action, **kwargs):
    """None selects the ordinary backend. False must never replay a failed click."""
    global _ordinary_drag, _secure_input_active

    if sys.platform != "win32":
        return None
    from server.windows import native as n

    desktop = n.OpenInputDesktop(0, False, 1)
    if desktop:
        name = n.c.create_unicode_buffer(64)
        try:
            n.check(n.GetUserObjectInformation(desktop, 2, name, n.c.sizeof(name), None))
            if name.value.casefold() == "default" and not n.foreground_elevated():
                resume_ordinary()
                if action == DRAG:
                    _ordinary_drag = kwargs.get("button") == 1
                return None
        finally:
            n.CloseDesktop(desktop)
    if _ordinary_drag:
        if client.request(packet(RELEASE)) != HANDLED:
            return False
        _ordinary_drag = False
    _secure_input_active = True
    if action == TEXT:
        text = kwargs.get("text", "")
        for offset in range(0, len(text), 1024):
            if client.request(packet(TEXT, text=text[offset : offset + 1024])) != HANDLED:
                return False
        return True
    result = client.request(packet(action, **kwargs))
    # A desktop change between probing and dispatch must drop this command.
    return result == HANDLED


def status():
    if sys.platform != "win32":
        return "unavailable"
    result = client.request(packet(PING))
    return "enabled" if result == HANDLED else "unavailable"


def disconnect():
    if sys.platform == "win32" and client.pipe is not None:
        client.request(packet(RELEASE))
        with client.lock:
            client.close()
