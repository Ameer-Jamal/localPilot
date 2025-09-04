import importlib
import sys
import types
import tempfile
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))


def load_app(monkeypatch):
    sys.modules.pop("app", None)
    pyside6 = types.ModuleType("PySide6")
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QApplication = type("QApplication", (), {"__init__": lambda self, *a, **k: None})
    qtnetwork = types.ModuleType("PySide6.QtNetwork")
    qtnetwork.QLocalSocket = type("QLocalSocket", (), {"__init__": lambda self, *a, **k: None})
    monkeypatch.setitem(sys.modules, "PySide6", pyside6)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PySide6.QtNetwork", qtnetwork)

    ipc_mod = types.ModuleType("ipc")
    ipc_mod.send_open_session = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "ipc", ipc_mod)
    ui_mod = types.ModuleType("ui.main_window")
    ui_mod.SOCKET_NAME = "dummy"
    ui_mod.MainWindow = object
    monkeypatch.setitem(sys.modules, "ui.main_window", ui_mod)

    import app
    return importlib.reload(app)


def test_read_selection_from_ranges(monkeypatch):
    app = load_app(monkeypatch)
    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        tmp.write("line1\nline2\n")
        tmp.flush()
        text = app._read_selection_from_ranges(tmp.name, 1, 2, 2, 3)
    assert text == "ine1\nli"
