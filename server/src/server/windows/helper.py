"""Standalone frozen helper entry point. Never imports the web or tray runtime."""

import argparse
import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def main():
    from server.windows import native as n
    from server.windows.input import VERSION

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("install", "remove", "service", "worker"))
    parser.add_argument("--sid")
    parser.add_argument("--client")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--stop")
    parser.add_argument("--parent", type=int)
    args = parser.parse_args()
    if args.mode == "install":
        from server.windows.manage import install, management_lock

        with management_lock(args.sid):
            install(args.sid, args.client)
    elif args.mode == "remove":
        from server.windows.manage import management_lock, remove

        with management_lock(args.sid):
            remove(args.sid)
    else:
        if n.process_sid() != n.SYSTEM_SID:
            raise PermissionError("SYSTEM identity required")
        log = RotatingFileHandler(
            args.config.parent / f"{args.mode}-{n.session_id()}.log",
            maxBytes=262144,
            backupCount=1,
            encoding="utf-8",
        )
        logging.basicConfig(handlers=[log], level=logging.WARNING)
        if args.mode == "service":
            from server.windows.service import run

            run(args.config)
        else:
            from server.windows.worker import run

            config = json.loads(args.config.read_text(encoding="utf-8"))
            if config["version"] != VERSION:
                raise ValueError("Incompatible service registration")
            open_event = n.bind("kernel32", "OpenEventW", n.HANDLE, n.DWORD, n.w.BOOL, n.w.LPCWSTR)
            with (
                n.handle(open_event(0x100000, False, args.stop)) as event,
                n.handle(n.OpenProcess(0x100000, False, args.parent)) as parent,
            ):
                run(config, event, parent)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        logging.exception("Input helper failed")
        if len(sys.argv) > 1 and sys.argv[1] in ("install", "remove"):
            from server.windows import native as n

            message = n.bind(
                "user32", "MessageBoxW", n.c.c_int, n.w.HWND, n.w.LPCWSTR, n.w.LPCWSTR, n.w.UINT
            )
            message(None, str(error), "Remote Mouse UAC setup", 0x10)
        # A windowless helper reports management failure through its exit code.
        sys.exit(1)
