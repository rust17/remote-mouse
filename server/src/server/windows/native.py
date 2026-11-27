"""Typed Windows APIs shared by the input service and its client."""

import ctypes as c
from contextlib import contextmanager
from ctypes import wintypes as w
from pathlib import Path

DWORD = w.DWORD
HANDLE = w.HANDLE
PTR = c.c_void_p
INVALID_HANDLE = c.c_void_p(-1).value
SYSTEM_SID = "S-1-5-18"


def bind(dll, name, result, *args):
    fn = getattr(c.WinDLL(dll, use_last_error=True), name)
    fn.restype = result
    fn.argtypes = list(args)
    return fn


CloseHandle = bind("kernel32", "CloseHandle", w.BOOL, HANDLE)
OpenProcess = bind("kernel32", "OpenProcess", HANDLE, DWORD, w.BOOL, DWORD)
GetCurrentProcess = bind("kernel32", "GetCurrentProcess", HANDLE)
GetCurrentProcessId = bind("kernel32", "GetCurrentProcessId", DWORD)
ProcessIdToSessionId = bind("kernel32", "ProcessIdToSessionId", w.BOOL, DWORD, PTR)
OpenProcessToken = bind("advapi32", "OpenProcessToken", w.BOOL, HANDLE, DWORD, PTR)
GetTokenInformation = bind(
    "advapi32", "GetTokenInformation", w.BOOL, HANDLE, DWORD, PTR, DWORD, PTR
)
ConvertSidToStringSid = bind("advapi32", "ConvertSidToStringSidW", w.BOOL, PTR, PTR)
LocalFree = bind("kernel32", "LocalFree", PTR, PTR)
QueryFullProcessImageName = bind(
    "kernel32", "QueryFullProcessImageNameW", w.BOOL, HANDLE, DWORD, w.LPWSTR, PTR
)
CreateFile = bind(
    "kernel32", "CreateFileW", HANDLE, w.LPCWSTR, DWORD, DWORD, PTR, DWORD, DWORD, HANDLE
)
ReadFile = bind("kernel32", "ReadFile", w.BOOL, HANDLE, PTR, DWORD, PTR, PTR)
WriteFile = bind("kernel32", "WriteFile", w.BOOL, HANDLE, PTR, DWORD, PTR, PTR)
CreateNamedPipe = bind(
    "kernel32", "CreateNamedPipeW", HANDLE, w.LPCWSTR, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, PTR
)
ConnectNamedPipe = bind("kernel32", "ConnectNamedPipe", w.BOOL, HANDLE, PTR)
DisconnectNamedPipe = bind("kernel32", "DisconnectNamedPipe", w.BOOL, HANDLE)
GetNamedPipeClientProcessId = bind("kernel32", "GetNamedPipeClientProcessId", w.BOOL, HANDLE, PTR)
GetNamedPipeServerProcessId = bind("kernel32", "GetNamedPipeServerProcessId", w.BOOL, HANDLE, PTR)
ImpersonateNamedPipeClient = bind("advapi32", "ImpersonateNamedPipeClient", w.BOOL, HANDLE)
OpenThreadToken = bind("advapi32", "OpenThreadToken", w.BOOL, HANDLE, DWORD, w.BOOL, PTR)
GetCurrentThread = bind("kernel32", "GetCurrentThread", HANDLE)
RevertToSelf = bind("advapi32", "RevertToSelf", w.BOOL)
ConvertStringSecurityDescriptor = bind(
    "advapi32",
    "ConvertStringSecurityDescriptorToSecurityDescriptorW",
    w.BOOL,
    w.LPCWSTR,
    DWORD,
    PTR,
    PTR,
)
OpenInputDesktop = bind("user32", "OpenInputDesktop", HANDLE, DWORD, w.BOOL, DWORD)
GetThreadDesktop = bind("user32", "GetThreadDesktop", HANDLE, DWORD)
GetCurrentThreadId = bind("kernel32", "GetCurrentThreadId", DWORD)
SetThreadDesktop = bind("user32", "SetThreadDesktop", w.BOOL, HANDLE)
CloseDesktop = bind("user32", "CloseDesktop", w.BOOL, HANDLE)
GetUserObjectInformation = bind(
    "user32", "GetUserObjectInformationW", w.BOOL, HANDLE, c.c_int, PTR, DWORD, PTR
)
GetForegroundWindow = bind("user32", "GetForegroundWindow", HANDLE)
GetWindowThreadProcessId = bind("user32", "GetWindowThreadProcessId", DWORD, HANDLE, PTR)
GetSystemDirectory = bind("kernel32", "GetSystemDirectoryW", w.UINT, w.LPWSTR, w.UINT)
SendInput = bind("user32", "SendInput", w.UINT, w.UINT, PTR, c.c_int)


def check(value):
    if not value or value == INVALID_HANDLE:
        raise c.WinError(c.get_last_error())
    return value


@contextmanager
def handle(value):
    value = check(value)
    try:
        yield value
    finally:
        CloseHandle(value)


def token_sid(token):
    size = DWORD()
    GetTokenInformation(token, 1, None, 0, c.byref(size))
    buffer = c.create_string_buffer(size.value)
    check(GetTokenInformation(token, 1, buffer, size, c.byref(size)))
    text = w.LPWSTR()
    check(ConvertSidToStringSid(c.cast(buffer, c.POINTER(PTR))[0], c.byref(text)))
    try:
        return text.value
    finally:
        LocalFree(c.cast(text, PTR))


def process_sid(process=None):
    token = HANDLE()
    check(OpenProcessToken(process or GetCurrentProcess(), 8, c.byref(token)))
    with handle(token.value):
        return token_sid(token)


def session_id(pid=None):
    result = DWORD()
    check(ProcessIdToSessionId(pid or GetCurrentProcessId(), c.byref(result)))
    return result.value


def image_path(process):
    length = DWORD(32768)
    path = c.create_unicode_buffer(length.value)
    check(QueryFullProcessImageName(process, 0, path, c.byref(length)))
    return Path(path.value).resolve()


def system_directory():
    text = c.create_unicode_buffer(32768)
    check(GetSystemDirectory(text, len(text)))
    return Path(text.value)


class SecurityAttributes(c.Structure):
    _fields_ = [("length", DWORD), ("descriptor", PTR), ("inherit", w.BOOL)]


@contextmanager
def security(sid, access="GRGW"):
    descriptor = PTR()
    # Protected DACL. Network clients are also rejected at the pipe itself.
    check(
        ConvertStringSecurityDescriptor(
            f"D:P(A;;GA;;;SY)(A;;{access};;;{sid})", 1, c.byref(descriptor), None
        )
    )
    try:
        yield SecurityAttributes(c.sizeof(SecurityAttributes), descriptor, False)
    finally:
        LocalFree(descriptor)


def pipe_read(pipe):
    data = c.create_string_buffer(4099)
    count = DWORD()
    check(ReadFile(pipe, data, len(data), c.byref(count), None))
    if not count.value:
        raise EOFError("Input pipe closed")
    return data.raw[: count.value]


def pipe_write(pipe, data):
    count = DWORD()
    check(WriteFile(pipe, data, len(data), c.byref(count), None))
    if count.value != len(data):
        raise OSError("Incomplete input pipe write")


def foreground_elevated():
    """A foreground process that cannot be queried also requires privileged input."""
    pid = DWORD()
    GetWindowThreadProcessId(GetForegroundWindow(), c.byref(pid))
    if not pid.value:
        return False
    try:
        with handle(OpenProcess(0x1000, False, pid.value)) as process:
            token = HANDLE()
            check(OpenProcessToken(process, 8, c.byref(token)))
            with handle(token.value):
                elevation, size = DWORD(), DWORD()
                check(
                    GetTokenInformation(
                        token, 20, c.byref(elevation), c.sizeof(elevation), c.byref(size)
                    )
                )
                return bool(elevation.value)
    except OSError:
        return True
