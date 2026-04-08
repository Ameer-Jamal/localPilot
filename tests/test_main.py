import importlib
import sys
import tempfile
import types
from pathlib import Path


def load_main(monkeypatch):
    sys.modules.pop("main", None)
    sys.modules.pop("ipc", None)

    pyside6 = types.ModuleType("PySide6")
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QApplication = type("QApplication", (), {"__init__": lambda self, *a, **k: None})
    qtnetwork = types.ModuleType("PySide6.QtNetwork")
    qtnetwork.QLocalSocket = type("QLocalSocket", (), {"__init__": lambda self, *a, **k: None})
    monkeypatch.setitem(sys.modules, "PySide6", pyside6)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PySide6.QtNetwork", qtnetwork)

    ui_mod = types.ModuleType("ui.main_window")
    ui_mod.SOCKET_NAME = "dummy"
    ui_mod.MainWindow = object
    monkeypatch.setitem(sys.modules, "ui.main_window", ui_mod)

    ipc_mod = types.ModuleType("ipc")
    ipc_mod.send_open_session = lambda *a, **k: False
    monkeypatch.setitem(sys.modules, "ipc", ipc_mod)

    history_mod = types.ModuleType("history_store")
    history_mod.HistoryStore = object
    monkeypatch.setitem(sys.modules, "history_store", history_mod)

    import main
    return importlib.reload(main)


def test_get_selection_uses_explicit_selection(monkeypatch):
    main = load_main(monkeypatch)
    args = main.parse_args.__globals__["argparse"].Namespace(
        file="demo.py",
        filepath="/tmp/demo.py",
        selection="print('x')",
        sel_start=None,
        sel_end=None,
        sel_start_line=None,
        sel_start_col=None,
        sel_end_line=None,
        sel_end_col=None,
    )
    payload = main.get_selection(args)
    assert payload.code == "print('x')"
    assert payload.display_name == "demo.py"
    assert payload.file_path == "/tmp/demo.py"


def test_get_selection_uses_offsets(monkeypatch):
    main = load_main(monkeypatch)
    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        tmp.write("abcdef")
        tmp.flush()
        args = main.parse_args.__globals__["argparse"].Namespace(
            file=None,
            filepath=tmp.name,
            selection=None,
            sel_start="1",
            sel_end="4",
            sel_start_line=None,
            sel_start_col=None,
            sel_end_line=None,
            sel_end_col=None,
        )
        payload = main.get_selection(args)
    assert payload.code == "bcd"
    assert payload.display_name == Path(tmp.name).name


def test_get_selection_uses_line_column(monkeypatch):
    main = load_main(monkeypatch)
    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        tmp.write("line1\nline2\n")
        tmp.flush()
        args = main.parse_args.__globals__["argparse"].Namespace(
            file=None,
            filepath=tmp.name,
            selection=None,
            sel_start=None,
            sel_end=None,
            sel_start_line="1",
            sel_start_col="2",
            sel_end_line="2",
            sel_end_col="3",
        )
        payload = main.get_selection(args)
    assert payload.code == "ine1\nli"
