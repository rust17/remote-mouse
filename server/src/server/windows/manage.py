"""Explicit elevation for installation, repair and removal of input support."""

import ctypes as c
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from ctypes import wintypes as w
from pathlib import Path

from server.windows.input import VERSION, client, identity, install_directory


class ShellExecuteInfo(c.Structure):
    _fields_ = [
        ("size", w.DWORD),
        ("mask", w.ULONG),
        ("window", w.HWND),
        ("verb", w.LPCWSTR),
        ("file", w.LPCWSTR),
        ("parameters", w.LPCWSTR),
        ("directory", w.LPCWSTR),
        ("show", c.c_int),
        ("instance", w.HINSTANCE),
        ("id_list", c.c_void_p),
        ("class_name", w.LPCWSTR),
        ("class_key", w.HKEY),
        ("hot_key", w.DWORD),
        ("icon", w.HANDLE),
        ("process", w.HANDLE),
    ]


def change(enable):
    from server.windows import native as n
    from server.windows.transport import WaitForSingleObject

    if not getattr(sys, "frozen", False):
        raise RuntimeError("UAC support requires a packaged Windows build")
    if not enable and not install_directory(n.process_sid()).exists():
        return
    helper = Path(sys.executable).parent / "RemoteMouseInput.exe"
    execute = n.bind("shell32", "ShellExecuteExW", w.BOOL, c.POINTER(ShellExecuteInfo))
    args = ["install" if enable else "remove", "--sid", n.process_sid()]
    if enable:
        args += ["--client", str(Path(sys.executable).resolve())]
    info = ShellExecuteInfo(
        size=c.sizeof(ShellExecuteInfo),
        mask=0x40 | 0x100,
        verb="runas",
        file=str(helper),
        parameters=subprocess.list2cmdline(args),
        show=0,
    )
    n.check(execute(c.byref(info)))
    with n.handle(info.process):
        # Management can take time while SCM waits for input releases.
        if WaitForSingleObject(info.process, 60000) != 0:
            raise TimeoutError("Input service setup has not finished")
        code = w.DWORD()
        get_code = n.bind("kernel32", "GetExitCodeProcess", w.BOOL, w.HANDLE, c.c_void_p)
        n.check(get_code(info.process, c.byref(code)))
        if code.value:
            raise OSError(f"Input service setup failed ({code.value})")
    with client.lock:
        client.close()
        client.retry_at = 0


def sc(*args, allowed=()):
    from server.windows import native as n

    result = subprocess.run(
        [str(n.system_directory() / "sc.exe"), *args], capture_output=True, creationflags=0x08000000
    )
    if result.returncode and result.returncode not in allowed:
        raise OSError(f"Service operation failed ({result.returncode})")
    return result.returncode


def replace_executable(source, destination):
    # SCM reports STOPPED before a one-file bootloader finishes exiting.
    deadline = time.monotonic() + 15
    while True:
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.2)


def install(sid, client_path):
    from server.windows import native as n
    from server.windows.service import wait_stopped
    from server.windows.worker import digest

    if not re.fullmatch(r"S-1-(?:\d+-)+\d+", sid):
        raise ValueError("Expected a user SID")
    client_path = Path(client_path).resolve(strict=True)
    if client_path.name.casefold() != "remotemouse.exe":
        raise ValueError("Unexpected client executable")
    directory = install_directory(sid)
    directory.mkdir(parents=True, exist_ok=True)
    # Apply a protected DACL before placing executable code or registration here.
    subprocess.run(
        [
            str(n.system_directory() / "icacls.exe"),
            str(directory),
            "/inheritance:r",
            "/grant:r",
            "*S-1-5-18:(OI)(CI)F",
            "*S-1-5-32-544:(OI)(CI)F",
            f"*{sid}:(OI)(CI)RX",
        ],
        check=True,
        capture_output=True,
        creationflags=0x08000000,
    )
    name = identity(sid)
    existed = sc("query", name, allowed=(1060,)) == 0
    if existed:
        sc("stop", name, allowed=(1062,))
        wait_stopped(name)
    executable = directory / "RemoteMouseInput.exe"
    config = directory / "registration.json"
    old_config = config.read_bytes() if config.exists() else None
    backup = directory / "previous.exe"
    if executable.exists():
        shutil.copy2(executable, backup)
    try:
        staged = directory / "update.exe"
        shutil.copy2(sys.executable, staged)
        replace_executable(staged, executable)
        config.write_text(
            json.dumps(
                {
                    "version": VERSION,
                    "sid": sid,
                    "client": str(client_path),
                    "sha256": digest(client_path),
                }
            ),
            encoding="utf-8",
        )
        command = subprocess.list2cmdline([str(executable), "service", "--config", str(config)])
        sc(
            "config" if existed else "create",
            name,
            "binPath=",
            command,
            "start=",
            "auto",
            "obj=",
            "LocalSystem",
            "DisplayName=",
            "Remote Mouse UAC Input",
        )
        sc("start", name)
    except BaseException:
        if backup.exists():
            replace_executable(backup, executable)
        if old_config is not None:
            config.write_bytes(old_config)
        if existed:
            sc("start", name, allowed=(1056,))
        else:
            sc("delete", name, allowed=(1060,))
            shutil.rmtree(directory)
        raise
    finally:
        backup.unlink(missing_ok=True)
        staged.unlink(missing_ok=True)


def remove(sid):
    from server.windows.service import wait_stopped

    if not re.fullmatch(r"S-1-(?:\d+-)+\d+", sid):
        raise ValueError("Expected a user SID")
    name = identity(sid)
    if sc("query", name, allowed=(1060,)) == 0:
        sc("stop", name, allowed=(1062,))
        wait_stopped(name)
        sc("delete", name)
    directory = install_directory(sid)
    if directory.exists():
        deadline = time.monotonic() + 15
        while True:
            try:
                shutil.rmtree(directory)
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)


@contextmanager
def management_lock(sid):
    from server.windows import native as n
    from server.windows.transport import WaitForSingleObject

    create = n.bind("kernel32", "CreateMutexW", w.HANDLE, c.c_void_p, w.BOOL, w.LPCWSTR)
    release = n.bind("kernel32", "ReleaseMutex", w.BOOL, w.HANDLE)
    with n.handle(create(None, False, "Global\\" + identity(sid) + "-Setup")) as mutex:
        if WaitForSingleObject(mutex, 20000) not in (0, 128):
            raise TimeoutError("Another input service setup is still running")
        try:
            yield
        finally:
            n.check(release(mutex))
