#!/usr/bin/env python3
import argparse
import json
import os
import sys

from PySide6.QtNetwork import QLocalSocket
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow, SOCKET_NAME


# -------- file + selection utilities --------

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _int_or_none(v):
    """Return int(v) or None. Treat unexpanded JetBrains macros like $SelectionStartOffset$ as None."""
    if v is None:
        return None
    s = str(v)
    if "$" in s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def slice_by_offsets(text: str, start: int, end: int) -> str:
    n = len(text)
    s = max(0, min(start, n))
    e = max(s, min(end, n))
    return text[s:e]


def slice_by_lc(text: str, s_line: int, s_col: int, e_line: int, e_col: int) -> str:
    """Lines/cols are 1-based (JetBrains). Column 1 maps to index 0."""
    lines = text.splitlines(keepends=True)
    if not lines:
        return ""

    def to_abs(line_1b: int, col_1b: int) -> int:
        L = max(1, min(int(line_1b), len(lines)))
        base = sum(len(x) for x in lines[: L - 1])
        cur = lines[L - 1]
        idx = max(0, min(int(col_1b) - 1, len(cur)))
        return base + idx

    s = to_abs(s_line, s_col)
    e = to_abs(e_line, e_col)
    if e < s:
        s, e = e, s
    return text[s:e]


# -------- argparse + selection resolution --------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--file")  # display name
    p.add_argument("--filepath")  # absolute path

    # absolute offsets (accept strings; convert later to avoid argparse aborts)
    p.add_argument("--sel-start", nargs="?")
    p.add_argument("--sel-end", nargs="?")

    # line/column (1-based; accept strings; convert later)
    p.add_argument("--sel-start-line", nargs="?")
    p.add_argument("--sel-start-col", nargs="?")
    p.add_argument("--sel-end-line", nargs="?")
    p.add_argument("--sel-end-col", nargs="?")

    # raw selection text
    p.add_argument("--selection", nargs="?")
    return p.parse_args()


def get_selection(args) -> tuple[str, str]:
    """Return (selection_text, display_title)."""
    title = args.file or (os.path.basename(args.filepath) if args.filepath else "selection")

    # 1) explicit selection text
    if args.selection and "$" not in args.selection:
        return args.selection, title

    file_text = ""
    if args.filepath:
        try:
            file_text = read_file(args.filepath)
        except OSError:
            file_text = ""

    # 2) absolute offsets
    s = _int_or_none(args.sel_start)
    e = _int_or_none(args.sel_end)
    if file_text and s is not None and e is not None:
        return slice_by_offsets(file_text, s, e), title

    # 3) line/column
    sl = _int_or_none(args.sel_start_line)
    sc = _int_or_none(args.sel_start_col)
    el = _int_or_none(args.sel_end_line)
    ec = _int_or_none(args.sel_end_col)
    if file_text and None not in (sl, sc, el, ec):
        return slice_by_lc(file_text, sl, sc, el, ec), title

    # 4) stdin
    if not sys.stdin.isatty():
        return sys.stdin.read(), title

    return "", title


# -------- single-instance IPC --------

def send_to_running_instance(code: str, file_name: str) -> bool:
    """Return True if a running instance was found and the message was delivered."""
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if not sock.waitForConnected(200):  # no instance listening
        return False
    payload = json.dumps({"cmd": "open_session", "code": code, "file": file_name}).encode("utf-8")
    sock.write(payload)
    sock.flush()
    sock.waitForBytesWritten(200)
    sock.disconnectFromServer()
    return True


# -------- entrypoint --------

def main():
    args = parse_args()
    code, display_name = get_selection(args)

    # If an instance is running, hand off via IPC and exit.
    if send_to_running_instance(code, display_name):
        return

    # Otherwise, start the UI and begin listening for future selections.
    app = QApplication(sys.argv)
    win = MainWindow(code, display_name)
    win.listen_ipc()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
