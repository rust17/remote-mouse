"""SCM lifecycle and per-session SYSTEM input workers."""

import ctypes as c
import json
import logging
import subprocess
import sys
import threading
import time
import uuid
from ctypes import wintypes as w

from server.windows import native as n
from server.windows.input import identity
from server.windows.transport import CreateEvent, WaitForSingleObject

CALLBACK = c.WINFUNCTYPE
HANDLER = CALLBACK(w.DWORD, w.DWORD, w.DWORD, n.PTR, n.PTR)
SERVICE_MAIN = CALLBACK(None, w.DWORD, n.PTR)
RegisterHandler = n.bind(
    "advapi32", "RegisterServiceCtrlHandlerExW", w.HANDLE, w.LPCWSTR, HANDLER, n.PTR
)
SetServiceStatus = n.bind("advapi32", "SetServiceStatus", w.BOOL, w.HANDLE, n.PTR)
StartDispatcher = n.bind("advapi32", "StartServiceCtrlDispatcherW", w.BOOL, n.PTR)
SetEvent = n.bind("kernel32", "SetEvent", w.BOOL, w.HANDLE)
WTSQueryUserToken = n.bind("wtsapi32", "WTSQueryUserToken", w.BOOL, w.ULONG, n.PTR)
WTSEnumerateSessions = n.bind(
    "wtsapi32", "WTSEnumerateSessionsW", w.BOOL, w.HANDLE, w.DWORD, w.DWORD, n.PTR, n.PTR
)
WTSFreeMemory = n.bind("wtsapi32", "WTSFreeMemory", None, n.PTR)
DuplicateTokenEx = n.bind(
    "advapi32", "DuplicateTokenEx", w.BOOL, w.HANDLE, w.DWORD, n.PTR, w.DWORD, w.DWORD, n.PTR
)
SetTokenInformation = n.bind(
    "advapi32", "SetTokenInformation", w.BOOL, w.HANDLE, w.DWORD, n.PTR, w.DWORD
)
CreateProcessAsUser = n.bind(
    "advapi32",
    "CreateProcessAsUserW",
    w.BOOL,
    w.HANDLE,
    w.LPCWSTR,
    w.LPWSTR,
    n.PTR,
    n.PTR,
    w.BOOL,
    w.DWORD,
    n.PTR,
    w.LPCWSTR,
    n.PTR,
    n.PTR,
)


class ServiceStatus(c.Structure):
    _fields_ = [
        (name, w.DWORD)
        for name in ("kind", "state", "accepted", "exit_code", "specific", "checkpoint", "hint")
    ]


class ServiceTable(c.Structure):
    _fields_ = [("name", w.LPWSTR), ("main", SERVICE_MAIN)]


class Session(c.Structure):
    _fields_ = [("id", w.DWORD), ("station", w.LPWSTR), ("state", w.DWORD)]


class StartupInfo(c.Structure):
    _fields_ = [
        ("size", w.DWORD),
        ("reserved", w.LPWSTR),
        ("desktop", w.LPWSTR),
        ("title", w.LPWSTR),
        ("x", w.DWORD),
        ("y", w.DWORD),
        ("width", w.DWORD),
        ("height", w.DWORD),
        ("chars_x", w.DWORD),
        ("chars_y", w.DWORD),
        ("fill", w.DWORD),
        ("flags", w.DWORD),
        ("show", w.WORD),
        ("reserved_size", w.WORD),
        ("reserved_bytes", n.PTR),
        ("stdin", w.HANDLE),
        ("stdout", w.HANDLE),
        ("stderr", w.HANDLE),
    ]


class ProcessInfo(c.Structure):
    _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]


def sessions(sid):
    entries = c.POINTER(Session)()
    count = w.DWORD()
    n.check(WTSEnumerateSessions(None, 0, 1, c.byref(entries), c.byref(count)))
    result = set()
    try:
        for entry in entries[: count.value]:
            if entry.id == 0 or entry.state != 0:  # WTSActive
                continue
            token = w.HANDLE()
            if WTSQueryUserToken(entry.id, c.byref(token)):
                with n.handle(token.value):
                    if n.token_sid(token) == sid:
                        result.add(entry.id)
    finally:
        WTSFreeMemory(entries)
    return result


def launch(session, config_path, sid):
    event_name = "Global\\RemoteMouseStop-" + uuid.uuid4().hex
    with n.security(n.SYSTEM_SID) as attributes:
        event = n.check(CreateEvent(c.byref(attributes), True, False, event_name))
    try:
        source, token = w.HANDLE(), w.HANDLE()
        n.check(n.OpenProcessToken(n.GetCurrentProcess(), 0xB, c.byref(source)))
        with n.handle(source.value):
            n.check(DuplicateTokenEx(source, 0xF01FF, None, 2, 1, c.byref(token)))
        with n.handle(token.value):
            session_value = w.DWORD(session)
            n.check(SetTokenInformation(token, 12, c.byref(session_value), c.sizeof(session_value)))
            startup = StartupInfo(size=c.sizeof(StartupInfo), desktop="winsta0\\default")
            process = ProcessInfo()
            command = c.create_unicode_buffer(
                subprocess.list2cmdline(
                    [
                        sys.executable,
                        "worker",
                        "--config",
                        str(config_path),
                        "--stop",
                        event_name,
                        "--parent",
                        str(n.GetCurrentProcessId()),
                    ]
                )
            )
            # The client authenticates this image using PROCESS_QUERY_LIMITED_INFORMATION.
            with n.security(sid, access="0x1000") as process_security:
                n.check(
                    CreateProcessAsUser(
                        token,
                        sys.executable,
                        command,
                        c.byref(process_security),
                        None,
                        False,
                        0x08000000,
                        None,
                        str(config_path.parent),
                        c.byref(startup),
                        c.byref(process),
                    )
                )
            n.CloseHandle(process.thread)
            return process.process, event
    except BaseException:
        n.CloseHandle(event)
        raise


def stop_worker(worker):
    process, event = worker
    try:
        n.check(SetEvent(event))
        if WaitForSingleObject(process, 5000) != 0:
            # Graceful release gets five seconds before a hung helper is terminated.
            terminate = n.bind("kernel32", "TerminateProcess", w.BOOL, w.HANDLE, w.UINT)
            n.check(terminate(process, 1))
            WaitForSingleObject(process, 1000)
    finally:
        n.CloseHandle(event)
        n.CloseHandle(process)


def run(config_path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    stop = threading.Event()
    name = identity(config["sid"])

    @HANDLER
    def handler(control, event, data, context):
        if control in (1, 5):
            stop.set()
        return 0

    @SERVICE_MAIN
    def main(argc, argv):
        status_handle = RegisterHandler(name, handler, None)
        if not status_handle:
            return
        status = ServiceStatus(kind=0x10, state=4, accepted=5)
        SetServiceStatus(status_handle, c.byref(status))
        workers = {}
        try:
            while not stop.is_set():
                active = sessions(config["sid"])
                for session in list(workers):
                    if session not in active or WaitForSingleObject(workers[session][0], 0) == 0:
                        stop_worker(workers.pop(session))
                for session in active - workers.keys():
                    try:
                        workers[session] = launch(session, config_path, config["sid"])
                    except OSError:
                        logging.exception("Could not start input worker for session %s", session)
                stop.wait(1)
        except OSError:
            status.exit_code = 1066
            status.specific = 1
        finally:
            status.state, status.accepted, status.hint = 3, 0, 15000
            SetServiceStatus(status_handle, c.byref(status))
            for worker in workers.values():
                stop_worker(worker)
            status.state = 1
            SetServiceStatus(status_handle, c.byref(status))

    table = (ServiceTable * 2)(ServiceTable(name, main), ServiceTable(None, SERVICE_MAIN()))
    n.check(StartDispatcher(table))


def wait_stopped(name):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        result = subprocess.run(["sc.exe", "query", name], capture_output=True, text=True)
        if result.returncode == 1060 or "STOPPED" in result.stdout or ": 1 " in result.stdout:
            return
        time.sleep(0.2)
    raise TimeoutError("Input service did not stop")
