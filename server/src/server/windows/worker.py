"""Session-local SYSTEM worker. Only consent.exe on Winlogon receives input."""

import ctypes as c
import hashlib
import logging
import queue
import threading
import time
from contextlib import suppress
from ctypes import wintypes as w

from server.windows import native as n
from server.windows.input import (
    CLICK,
    DOUBLE_CLICK,
    DRAG,
    FAILED,
    HANDLED,
    MOVE,
    NORMAL,
    PING,
    RELEASE,
    SCROLL,
    VERSION,
    decode,
    pipe_name,
)


class MouseInput(c.Structure):
    _fields_ = [
        ("dx", c.c_int32),
        ("dy", c.c_int32),
        ("data", w.DWORD),
        ("flags", w.DWORD),
        ("time", w.DWORD),
        ("extra", c.c_size_t),
    ]


class KeyboardInput(c.Structure):
    _fields_ = [
        ("key", w.WORD),
        ("scan", w.WORD),
        ("flags", w.DWORD),
        ("time", w.DWORD),
        ("extra", c.c_size_t),
    ]


class InputUnion(c.Union):
    _fields_ = [("mouse", MouseInput), ("keyboard", KeyboardInput)]


class Input(c.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("kind", w.DWORD), ("value", InputUnion)]


def mouse(flags, x=0, y=0, data=0):
    return Input(kind=0, value=InputUnion(mouse=MouseInput(x, y, data & 0xFFFFFFFF, flags)))


def key(code, up=False):
    return Input(kind=1, value=InputUnion(keyboard=KeyboardInput(code, 0, 2 if up else 0)))


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def authorized(pipe, config):
    pid = w.DWORD()
    n.check(n.GetNamedPipeClientProcessId(pipe, c.byref(pid)))
    n.check(n.ImpersonateNamedPipeClient(pipe))
    try:
        token = w.HANDLE()
        n.check(n.OpenThreadToken(n.GetCurrentThread(), 8, True, c.byref(token)))
        with n.handle(token.value):
            if n.token_sid(token) != config["sid"]:
                return False
    finally:
        n.check(n.RevertToSelf())
    with n.handle(n.OpenProcess(0x1000, False, pid)) as process:
        path = n.image_path(process)
        return (
            n.session_id(pid.value) == n.session_id()
            and n.process_sid(process) == config["sid"]
            and str(path).casefold() == config["client"].casefold()
            and digest(path) == config["sha256"]
        )


def listen(config, commands, disconnected, stop):
    first = True
    while not stop.is_set():
        with n.security(config["sid"]) as attributes:
            # FIRST_PIPE_INSTANCE prevents silently attaching to a squatted pipe.
            pipe = n.CreateNamedPipe(
                pipe_name(config["sid"], n.session_id()),
                3 | (0x80000 if first else 0),
                4 | 2 | 8,
                1,
                64,
                64,
                0,
                c.byref(attributes),
            )
        with n.handle(pipe):
            first = False
            if not n.ConnectNamedPipe(pipe, None) and c.get_last_error() != 535:
                continue
            try:
                # Impersonation requires reading the client's first message.
                data = n.pipe_read(pipe)
                if not authorized(pipe, config):
                    logging.warning("Input pipe client failed identity verification")
                    continue
                disconnected.clear()
                while not stop.is_set():
                    decode(data)
                    response = queue.Queue(maxsize=1)
                    commands.put((data, response))
                    result = response.get(timeout=1)
                    n.pipe_write(pipe, bytes((VERSION, result)))
                    data = n.pipe_read(pipe)
            except (BrokenPipeError, EOFError):
                # A closed client is expected during disconnect, repair or shutdown.
                pass
            except (OSError, ValueError, queue.Empty):
                logging.exception("Input pipe disconnected or rejected")
            finally:
                disconnected.set()
                n.DisconnectNamedPipe(pipe)


class DesktopMouse:
    def __init__(self):
        self.original = n.GetThreadDesktop(n.GetCurrentThreadId())
        self.desktop = None
        self.name = ""
        self.held = []

    def send(self, events):
        if events:
            batch = (Input * len(events))(*events)
            c.set_last_error(0)
            if n.SendInput(len(batch), batch, c.sizeof(Input)) != len(batch):
                raise OSError(
                    f"Windows rejected mouse input ({c.get_last_error()}, size={c.sizeof(Input)})"
                )

    def release(self):
        if self.held:
            # Retain pending releases if Windows rejects them, for the next poll.
            self.send(list(reversed(self.held)))
            self.held.clear()

    def refresh(self):
        desktop = n.check(n.OpenInputDesktop(0, False, 0x1FF))
        text = c.create_unicode_buffer(64)
        try:
            n.check(n.GetUserObjectInformation(desktop, 2, text, c.sizeof(text), None))
            if text.value != self.name:
                with suppress(OSError):
                    self.release()
                n.check(n.SetThreadDesktop(desktop))
                if self.desktop:
                    n.CloseDesktop(self.desktop)
                self.desktop, desktop = desktop, None
                self.name = text.value
                self.release()
        finally:
            if desktop:
                n.CloseDesktop(desktop)

    def consent(self):
        if self.name.casefold() != "winlogon":
            return False
        pid = w.DWORD()
        n.GetWindowThreadProcessId(n.GetForegroundWindow(), c.byref(pid))
        if not pid.value or n.session_id(pid.value) != n.session_id():
            return False
        with n.handle(n.OpenProcess(0x1000, False, pid)) as process:
            return n.image_path(process) == n.system_directory() / "consent.exe"

    def execute(self, data):
        action, x, y, button, modifiers = decode(data)
        self.refresh()
        if action == PING:
            return HANDLED
        if action == RELEASE:
            self.release()
            # Also cancel a drag that began in the ordinary user process.
            self.send([mouse(4)])
            return HANDLED
        if self.name.casefold() == "default":
            self.release()
            return NORMAL
        if not self.consent():
            logging.warning("Input rejected on desktop %s", self.name)
            self.release()
            return FAILED
        if action == MOVE:
            point = w.POINT()
            get_position = n.bind("user32", "GetCursorPos", w.BOOL, n.PTR)
            metrics = n.bind("user32", "GetSystemMetrics", c.c_int, c.c_int)
            n.check(get_position(c.byref(point)))
            left, top, width, height = (metrics(index) for index in (76, 77, 78, 79))
            px = min(max(point.x + x - left, 0), width - 1)
            py = min(max(point.y + y - top, 0), height - 1)
            # Match ordinary desktop pixel movement without applying Windows
            # pointer acceleration a second time to phone deltas.
            self.send(
                [mouse(0xC001, (px * 65536 + 32768) // width, (py * 65536 + 32768) // height)]
            )
        elif action == SCROLL:
            if y:
                self.send([mouse(0x800, data=y * 120)])
            if x:
                self.send([mouse(0x1000, data=x * 120)])
        elif action == DRAG:
            if button:
                if not self.held:
                    self.held.append(mouse(4))
                    self.send([mouse(2)])
            else:
                self.release()
        elif action in (CLICK, DOUBLE_CLICK):
            if self.held:
                return FAILED
            codes = [
                code for bit, code in enumerate((0x11, 0x10, 0x12, 0x5B)) if modifiers & (1 << bit)
            ]
            down, up = (8, 16) if button == 2 else (2, 4)
            try:
                for code in codes:
                    self.held.append(key(code, True))
                    self.send([key(code)])
                for index in range(2 if action == DOUBLE_CLICK else 1):
                    if index:
                        time.sleep(0.12)
                    self.refresh()
                    if not self.consent():
                        return FAILED
                    self.held.append(mouse(up))
                    self.send([mouse(down), mouse(up)])
                    self.held.pop()
            finally:
                self.release()
        return HANDLED

    def close(self):
        self.release()
        n.check(n.SetThreadDesktop(self.original))
        if self.desktop:
            n.CloseDesktop(self.desktop)
            self.desktop = None


def run(config, stop_handle, parent_handle):
    if n.process_sid() != n.SYSTEM_SID or n.session_id() == 0:
        raise PermissionError("Input worker requires a SYSTEM interactive session")
    aware = n.bind("user32", "SetProcessDPIAware", w.BOOL)
    aware()
    # A one-file bootloader creates a second process with its own default DACL.
    # Grant query access on the process that actually owns the named pipe.
    set_security = n.bind("advapi32", "SetKernelObjectSecurity", w.BOOL, w.HANDLE, w.DWORD, n.PTR)
    with n.security(config["sid"], access="0x1000") as attributes:
        n.check(set_security(n.GetCurrentProcess(), 4, attributes.descriptor))
    from server.windows.transport import WaitForSingleObject

    commands = queue.Queue(maxsize=16)
    disconnected, stop = threading.Event(), threading.Event()
    disconnected.set()
    threading.Thread(
        target=listen, args=(config, commands, disconnected, stop), daemon=True
    ).start()
    desktop = DesktopMouse()
    try:
        while (
            WaitForSingleObject(stop_handle, 0) == 258
            and WaitForSingleObject(parent_handle, 0) == 258
        ):
            try:
                desktop.refresh()
                if disconnected.is_set():
                    desktop.release()
            except OSError:
                pass
            try:
                data, response = commands.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                result = desktop.execute(data)
            except (OSError, ValueError):
                logging.exception("Input command failed")
                result = FAILED
            response.put(result)
    finally:
        stop.set()
        desktop.close()
