"""Bounded overlapped pipe I/O. Commands are never retried after a timeout."""

import ctypes as c
from ctypes import wintypes as w

from server.windows import native as n


class Overlapped(c.Structure):
    _fields_ = [
        ("internal", c.c_size_t),
        ("internal_high", c.c_size_t),
        ("offset", w.DWORD),
        ("offset_high", w.DWORD),
        ("event", w.HANDLE),
    ]


CreateEvent = n.bind("kernel32", "CreateEventW", w.HANDLE, n.PTR, w.BOOL, w.BOOL, w.LPCWSTR)
WaitForSingleObject = n.bind("kernel32", "WaitForSingleObject", w.DWORD, w.HANDLE, w.DWORD)
CancelIoEx = n.bind("kernel32", "CancelIoEx", w.BOOL, w.HANDLE, n.PTR)
GetOverlappedResult = n.bind(
    "kernel32", "GetOverlappedResult", w.BOOL, w.HANDLE, n.PTR, n.PTR, w.BOOL
)


def transfer(pipe, buffer, write):
    with n.handle(CreateEvent(None, True, False, None)) as event:
        operation = Overlapped(event=event)
        count = w.DWORD()
        fn = n.WriteFile if write else n.ReadFile
        if not fn(pipe, buffer, len(buffer), c.byref(count), c.byref(operation)):
            if c.get_last_error() != 997:
                n.check(False)
            if WaitForSingleObject(event, 250) != 0:
                CancelIoEx(pipe, c.byref(operation))
                # The kernel must finish referencing the buffer before it is freed.
                GetOverlappedResult(pipe, c.byref(operation), c.byref(count), True)
                raise TimeoutError("Input service timed out")
            n.check(GetOverlappedResult(pipe, c.byref(operation), c.byref(count), False))
        return count.value


def transact(pipe, data):
    buffer = c.create_string_buffer(data, len(data))
    if transfer(pipe, buffer, True) != len(data):
        raise OSError("Incomplete input command")
    reply = c.create_string_buffer(2)
    if transfer(pipe, reply, False) != 2:
        raise OSError("Incomplete input response")
    return reply.raw
