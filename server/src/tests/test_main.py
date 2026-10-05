from contextlib import suppress
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from server import main


@pytest.mark.parametrize(
    "failure", [KeyboardInterrupt(), RuntimeError("tray failure"), SystemExit(0)]
)
def test_entrypoint_always_stops_service(monkeypatch, failure):
    manager, tray = Mock(), Mock()
    tray.run.side_effect = failure
    monkeypatch.setattr(main, "parse_args", lambda: SimpleNamespace(port=9997, log=False))
    monkeypatch.setattr(main, "configure_logging", lambda _: None)
    monkeypatch.setattr(main, "ServiceManager", lambda **_: manager)
    monkeypatch.setattr(main, "TrayIcon", lambda **_: tray)
    monkeypatch.setattr(main, "MDNSResponder", lambda **_: Mock())
    with suppress(SystemExit):
        main.main()
    manager.start.assert_called_once()
    manager.stop.assert_called_once()


@pytest.mark.parametrize("argument_count", [1, 2])
def test_termination_callback_accepts_native_signal_signature(monkeypatch, argument_count):
    registry = main.signal
    if main.sys.platform == "darwin":
        from PyObjCTools import MachSignals

        registry = MachSignals
    callbacks = []
    monkeypatch.setattr(registry, "signal", lambda signum, handler: callbacks.append(handler))
    manager, tray = Mock(), Mock()
    tray.run.side_effect = lambda: callbacks[0](
        *([main.signal.SIGTERM] + [None] * (argument_count - 1))
    )
    monkeypatch.setattr(main, "parse_args", lambda: SimpleNamespace(port=9997, log=False))
    monkeypatch.setattr(main, "configure_logging", lambda _: None)
    monkeypatch.setattr(main, "ServiceManager", lambda **_: manager)
    monkeypatch.setattr(main, "TrayIcon", lambda **_: tray)
    monkeypatch.setattr(main, "MDNSResponder", lambda **_: Mock())
    with suppress(SystemExit):
        main.main()
    tray.icon.stop.assert_called_once()
    assert manager.stop.call_count == 2  # Signal cleanup, then the idempotent finally cleanup.
